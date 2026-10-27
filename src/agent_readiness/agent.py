"""Browser Use adapter. Receives public tasks only; never imports private truth."""
import asyncio
from dataclasses import dataclass
import json
import os
from pathlib import Path
from urllib.parse import urlsplit
from .contracts import Answer, PublicTask
from .recorder import Recorder

PROFILE_PATH = Path(__file__).parent / "profiles" / "natural-v1.json"


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


@dataclass
class ModelConfig:
    provider: str = "meta"
    model: str = "muse-spark-1.3"
    base_url: str = "https://api.meta.ai/v1"
    key_env: str = "MODEL_API_KEY"


def create_model(config: ModelConfig, *, http_client=None, api_key=None):
    if config.provider not in {"meta", "openai-compatible"}:
        raise ValueError("Supported provider configurations: meta, openai-compatible")
    key = api_key or os.getenv(config.key_env)
    if not key:
        raise ValueError(f"Missing credential: set {config.key_env}; use smoke for a credential-free run")
    prepare_browser_environment()
    from browser_use import ChatOpenAI
    return ChatOpenAI(model=config.model, base_url=config.base_url, api_key=key,
                      http_client=http_client, temperature=None, frequency_penalty=None,
                      max_retries=0, timeout=60, remove_min_items_from_schema=True,
                      max_completion_tokens=profile()["max_completion_tokens"])


class RecordingModel:
    def __init__(self, inner, recorder: Recorder):
        self.inner = inner
        self.recorder = recorder
        self.model = inner.model
        self._verified_api_keys = True
        self.usages = []
        self.last_error = None

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
        self.recorder.event("model_request", messages=self.recorder.messages(messages),
                            output_schema=output_format.model_json_schema() if output_format else None)
        try:
            result = await self.inner.ainvoke(messages, output_format=output_format, **kwargs)
        except Exception as exc:
            self.last_error = type(exc).__name__
            self.recorder.event("model_error", error_type=type(exc).__name__, error=str(exc))
            raise
        usage = result.usage.model_dump(mode="json") if result.usage else None
        if usage:
            self.usages.append(usage)
        self.recorder.event("model_response", completion=result.completion,
                            usage=usage, stop_reason=result.stop_reason)
        return result


def browser_options(url: str, executable: str):
    parsed = urlsplit(url)
    return dict(headless=True, executable_path=executable, enable_default_extensions=False, use_cloud=False,
                allowed_domains=[f"{parsed.scheme}://{parsed.netloc}"],
                viewport=profile()["viewport"], chromium_sandbox=profile()["chromium_sandbox"],
                user_data_dir=None, keep_alive=True)


def create_agent(task: PublicTask, url: str, llm, browser, recorder: Recorder):
    prepare_browser_environment()
    from browser_use import Agent, Tools
    p = profile()
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
                 tools=tools, use_vision=True, vision_detail_level="high",
                 output_model_schema=Answer, extend_system_message=p["instructions"],
                 register_new_step_callback=observe, use_judge=False, calculate_cost=False,
                 max_actions_per_step=p["max_actions_per_step"], max_failures=2,
                 generate_gif=False, enable_planning=False,
                 file_system_path=str(recorder.path / "agent-workspace"),
                 display_files_in_done_text=False, available_file_paths=[],
                 initial_actions=[{"navigate": {"url": url, "new_tab": False}}])


async def attempt(task: PublicTask, url: str, llm, recorder: Recorder, max_steps: int):
    prepare_browser_environment()
    from browser_use import Browser
    from playwright.async_api import async_playwright
    async with async_playwright() as pw:
        browser = Browser(**browser_options(url, pw.chromium.executable_path))
        wrapped = RecordingModel(llm, recorder)
        agent = create_agent(task, url, wrapped, browser, recorder)
        try:
            async def completed_step(current):
                if current.history.history:
                    recorder.event("step_result", result=current.history.history[-1].model_dump())
            recorder.event("initial_actions", actions=[{"navigate": {"url": url}}])
            history = await agent.run(max_steps=max_steps, on_step_end=completed_step)
            final = history.final_result()
            if final is not None:
                try:
                    final = json.loads(final)
                except (ValueError, TypeError):
                    pass  # Independent evaluator will reject malformed output.
            status = ("completed" if history.is_done() else "infrastructure_error" if wrapped.last_error
                      else "step_limit" if len(history.history) >= max_steps else "agent_failure")
            return dict(answer=final, status=status,
                        stop_reason="agent_done" if history.is_done() else wrapped.last_error or status,
                        steps=len(history.history), action_count=sum(len(h.result) for h in history.history),
                        usage=wrapped.usages or None, errors=[e for e in history.errors() if e])
        finally:
            recorder.write("history.json", agent.history.model_dump())
            try:
                await asyncio.wait_for(browser.kill(), timeout=15)
            except Exception as exc:
                recorder.event("cleanup_error", error=str(exc))
