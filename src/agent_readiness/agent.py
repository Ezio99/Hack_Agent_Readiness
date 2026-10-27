"""Browser Use adapter. Receives public tasks only; never imports private truth."""
import asyncio
from dataclasses import dataclass
import json
import os
from pathlib import Path
from urllib.parse import urlsplit
from .contracts import Answer, PublicTask
from .recorder import Recorder

PROFILE_PATH = Path(__file__).parent / "profiles" / "natural-v2.json"


def profile():
    return json.loads(PROFILE_PATH.read_text())


def prepare_browser_environment():
    # Disable framework cloud sync, telemetry, and extension downloads, including
    # credential-free tests. Do this BEFORE importing Browser Use.
    os.environ["ANONYMIZED_TELEMETRY"] = "false"
    os.environ["BROWSER_USE_CLOUD_SYNC"] = "false"
    os.environ["BROWSER_USE_DISABLE_EXTENSIONS"] = "1"
    os.environ.setdefault("BROWSER_USE_CONFIG_DIR", str(Path("artifacts/browser-config").resolve()))
    os.environ.setdefault("BROWSER_USE_LOGGING_LEVEL", "error")


@dataclass(frozen=True)
class ModelConfig:
    provider: str = "meta"
    model: str = "muse-spark-1.3"
    base_url: str = "https://api.meta.ai/v1"
    key_env: str = "META_MODEL_API_KEY"


def create_model(config: ModelConfig, effective: dict, *, http_client=None, api_key=None):
    if config.provider not in {"meta", "openai-compatible"}:
        raise ValueError("Supported provider configurations: meta, openai-compatible")
    key = api_key or os.getenv(config.key_env)
    if not key:
        raise ValueError(f"Missing credential: set {config.key_env}; use smoke for a credential-free run")
    endpoint = urlsplit(config.base_url)
    if endpoint.scheme not in {"http", "https"} or not endpoint.hostname or endpoint.username or endpoint.password or endpoint.query or endpoint.fragment:
        raise ValueError("Model endpoint must not contain credentials, query parameters or fragments")
    prepare_browser_environment()
    from browser_use import ChatOpenAI
    return ChatOpenAI(model=config.model, base_url=config.base_url, api_key=key,
                      http_client=http_client, temperature=None, frequency_penalty=None,
                      max_retries=0, timeout=effective["model_timeout_seconds"], remove_min_items_from_schema=True,
                      max_completion_tokens=effective["max_completion_tokens"])


class ModelRequestLimitReached(RuntimeError):
    """The next model invocation is blocked before reaching the provider adapter."""


class ModelCallError(RuntimeError):
    """A provider error safe to expose to framework history and console logging."""


class RecordingModel:
    def __init__(self, inner, recorder: Recorder, effective: dict):
        self.inner = inner
        self.recorder = recorder
        self.model = inner.model
        self._verified_api_keys = True
        self.usages = []
        self.last_error = None
        self.max_requests = effective["max_model_requests"]
        self.request_count = 0
        self.limit_reached = False
        # The SDK key never enters browser tools/context. Register it before
        # recording any model input, output, exception or framework history.
        recorder.add_secret(getattr(inner, "api_key", None))

    @property
    def provider(self):
        return self.inner.provider

    @property
    def name(self):
        return self.inner.name

    @property
    def model_name(self):
        return self.model

    async def ainvoke(self, messages, output_format=None, **kwargs):
        if self.request_count >= self.max_requests:
            self.limit_reached = True
            self.recorder.event("model_request_limit", count=self.request_count, limit=self.max_requests)
            raise ModelRequestLimitReached(f"Model request limit reached ({self.max_requests})")
        self.request_count += 1
        self.recorder.event("model_request", request_count=self.request_count, messages=self.recorder.messages(messages),
                            output_schema=output_format.model_json_schema() if output_format else None)
        try:
            result = await self.inner.ainvoke(messages, output_format=output_format, **kwargs)
        except Exception as exc:
            self.last_error = type(exc).__name__
            message = self.recorder.clean(str(exc))
            self.recorder.event("model_error", error_type=type(exc).__name__, error=message)
            raise ModelCallError(message) from None
        usage = result.usage.model_dump(mode="json") if result.usage else None
        if usage:
            self.usages.append(usage)
        self.recorder.event("model_response", completion=result.completion,
                            usage=usage, stop_reason=result.stop_reason)
        return result


def browser_options(url: str, executable: str, effective: dict):
    parsed = urlsplit(url)
    return dict(headless=True, executable_path=executable, enable_default_extensions=False, use_cloud=False,
                allowed_domains=[f"{parsed.scheme}://{parsed.netloc}"],
                viewport=effective["viewport"], chromium_sandbox=effective["chromium_sandbox"],
                user_data_dir=None, keep_alive=True)


def create_agent(task: PublicTask, url: str, llm, browser, recorder: Recorder, effective: dict):
    prepare_browser_environment()
    from browser_use import Agent, Tools
    p = effective
    tools = Tools()
    # Enforce the profile, rather than relying on instructions for permissions.
    for name in list(tools.registry.registry.actions):
        if name not in p["allowed_tools"]:
            tools.exclude_action(name)

    version_recorded = False

    async def observe(state, output, step):
        nonlocal version_recorded
        if not version_recorded:
            info = await browser.cdp_client.send.Browser.getVersion()
            recorder.event("browser_version", version=info["product"])
            version_recorded = True
        image = recorder.image(f"step-{step:03d}", state.screenshot) if state.screenshot else None
        recorder.event("observation", step=step, url=state.url, title=state.title,
                       dom=state.dom_state.llm_representation(), screenshot=image,
                       proposed_actions=[a.model_dump(mode="json", exclude_none=True) for a in output.action])

    return Agent(task=f"Start at {url}\n{task.prompt}", llm=llm, browser_session=browser,
                 tools=tools, use_vision=p["use_vision"], vision_detail_level=p["vision_detail_level"],
                 output_model_schema=Answer, extend_system_message=p["instructions"],
                 register_new_step_callback=observe, use_judge=False, calculate_cost=False,
                 max_actions_per_step=p["max_actions_per_step"], max_failures=2,
                 llm_timeout=p["model_timeout_seconds"], step_timeout=p["step_timeout_seconds"],
                 final_response_after_failure=False,
                 generate_gif=False, enable_planning=False,
                 file_system_path=str(recorder.path / "agent-workspace"),
                 display_files_in_done_text=False, available_file_paths=[],
                 initial_actions=[{"navigate": {"url": url, "new_tab": False}}])


async def attempt(task: PublicTask, url: str, llm, recorder: Recorder, effective: dict):
    prepare_browser_environment()
    from browser_use import Browser
    from playwright.async_api import async_playwright
    async with async_playwright() as pw:
        browser = Browser(**browser_options(url, pw.chromium.executable_path, effective))
        wrapped = RecordingModel(llm, recorder, effective)
        agent = create_agent(task, url, wrapped, browser, recorder, effective)
        try:
            async def completed_step(current):
                if current.history.history:
                    recorder.event("step_result", result=current.history.history[-1].model_dump())
            recorder.event("initial_actions", actions=[{"navigate": {"url": url}}])
            history = await agent.run(max_steps=effective["max_steps"], on_step_end=completed_step)
            final = history.final_result()
            if final is not None:
                try:
                    final = json.loads(final)
                except (ValueError, TypeError):
                    pass  # Independent evaluator will reject malformed output.
            status = ("request_limit" if wrapped.limit_reached else "completed" if history.is_done() else "infrastructure_error" if wrapped.last_error
                      else "step_limit" if len(history.history) >= effective["max_steps"] else "agent_failure")
            return dict(answer=final, status=status,
                        stop_reason="model_request_limit" if wrapped.limit_reached else "agent_done" if history.is_done() else wrapped.last_error or status,
                        steps=len(history.history), action_count=sum(len(h.result) for h in history.history),
                        usage=wrapped.usages or None, model_request_count=wrapped.request_count, errors=[e for e in history.errors() if e])
        finally:
            recorder.write("history.json", agent.history.model_dump())
            try:
                await asyncio.wait_for(browser.kill(), timeout=15)
            except Exception as exc:
                recorder.event("cleanup_error", error=str(exc))
