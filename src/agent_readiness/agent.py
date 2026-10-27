"""Browser Use adapter. Receives public tasks only; never imports private truth."""
import asyncio
from dataclasses import dataclass
import json
import os
import subprocess
from pathlib import Path
from urllib.parse import urlsplit
from .contracts import Answer, PublicTask
from .capture import attach_capture
from .recorder import Recorder

PROFILE_DIR = Path(__file__).parent / "profiles"
PROFILE_FILES = {"natural-shopping-v2": "natural-v2.json", "natural-shopping-v3": "natural-v3.json"}
DEFAULT_PROFILE_ID = "natural-shopping-v3"
# Documented Meta levels; "none" returns HTTP 400 on Muse Spark. "xhigh"/"max" are excluded by this project.
REASONING_EFFORTS = ("minimal", "low", "medium", "high")


def profile(profile_id: str | None = None):
    """Load one frozen profile snapshot. v2 is preserved for reproducing earlier runs."""
    name = PROFILE_FILES.get(profile_id or DEFAULT_PROFILE_ID)
    if name is None:
        raise ValueError(f"Unknown profile: {profile_id}")
    return json.loads((PROFILE_DIR / name).read_text())


def validate_reasoning_effort(effective: dict):
    if "reasoning_effort" in effective and effective["reasoning_effort"] not in REASONING_EFFORTS:
        raise ValueError(f"reasoning_effort must be one of {', '.join(REASONING_EFFORTS)}")


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
    validate_reasoning_effort(effective)
    prepare_browser_environment()
    from browser_use import ChatOpenAI
    options = {}
    if config.provider == "meta" and "reasoning_effort" in effective:
        # Browser Use sends reasoning_effort only for model names in `reasoning_models`; match Muse Spark
        # explicitly so the profile's value reaches the wire (it also drops temperature/penalties).
        options = dict(reasoning_models=["muse-spark"], reasoning_effort=effective["reasoning_effort"])
    return ChatOpenAI(model=config.model, base_url=config.base_url, api_key=key,
                      http_client=http_client, temperature=None, frequency_penalty=None,
                      max_retries=0, timeout=effective["model_timeout_seconds"], remove_min_items_from_schema=True,
                      max_completion_tokens=effective["max_completion_tokens"], **options)


class ModelRequestLimitReached(RuntimeError):
    """The next model invocation is blocked before reaching the provider adapter."""


class ModelCallError(RuntimeError):
    """A provider error safe to expose to framework history and console logging."""


class RecordingModel:
    def __init__(self, inner, recorder: Recorder, effective: dict, capture=None):
        self.inner = inner
        self.capture = capture
        self.output_errors = []
        self.last_error_class = None
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

    def _classify_captured_responses(self, output_format):
        """After an adapter exception: use the response captured before parsing, if any."""
        from .capture import classify_output
        for record in (self.capture.take() if self.capture else []):
            outcome = classify_output(record, output_format)
            record["output_error"] = outcome
            usage = record.get("usage")
            if usage:  # the adapter discarded this usage when it raised
                self.usages.append({**usage, "source": "http_capture_after_error"})
            if outcome:
                self.last_error_class = "model_output_error"
                self.output_errors.append({"request_count": self.request_count, **outcome})
                self.recorder.event("model_output_error", request_count=self.request_count, **outcome)
            self.recorder.write(f"model-response-{record['index']:02d}.json", record)

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
            self.last_error_class = "infrastructure_error"
            self._classify_captured_responses(output_format)
            message = self.recorder.clean(str(exc))
            self.recorder.event("model_error", error_type=type(exc).__name__, error=message,
                                error_class=self.last_error_class)
            raise ModelCallError(message) from None
        if self.capture:
            self.capture.take()  # keep the per-invocation pointer aligned on success
        usage = result.usage.model_dump(mode="json") if result.usage else None
        if usage:
            self.usages.append(usage)
        self.recorder.event("model_response", completion=result.completion,
                            usage=usage, stop_reason=result.stop_reason)
        return result


def classify_outcome(wrapped, done: bool, steps: int, max_steps: int):
    """(status, stop_reason). Model-output failures are distinct from infrastructure and task failures."""
    if wrapped.limit_reached:
        return "request_limit", "model_request_limit"
    if done:
        return "completed", "agent_done"
    if wrapped.last_error:
        if wrapped.last_error_class == "model_output_error":
            return "model_output_error", f"model_output_error:{wrapped.output_errors[-1]['subtype']}"
        return "infrastructure_error", wrapped.last_error
    status = "step_limit" if steps >= max_steps else "agent_failure"
    return status, status


def executable_version(path: str):
    """Version string of the Chromium that will be launched, without extra dependencies or network."""
    try:
        out = subprocess.run([path, "--version"], capture_output=True, text=True, timeout=10)
        return out.stdout.strip() or None
    except Exception:
        return None


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
        recorder.event("browser_version", version=executable_version(pw.chromium.executable_path), source="executable --version")
        capture = attach_capture(llm, recorder)
        wrapped = RecordingModel(llm, recorder, effective, capture=capture)
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
            status, stop_reason = classify_outcome(wrapped, history.is_done(), len(history.history), effective["max_steps"])
            return dict(answer=final, status=status, stop_reason=stop_reason,
                        steps=len(history.history), action_count=sum(len(h.result) for h in history.history),
                        usage=wrapped.usages or None, model_request_count=wrapped.request_count, errors=[e for e in history.errors() if e],
                        http_captures=capture.summary() if capture else None,
                        model_output_errors=wrapped.output_errors or None)
        finally:
            recorder.write("history.json", agent.history.model_dump())
            try:
                await asyncio.wait_for(browser.kill(), timeout=15)
            except Exception as exc:
                recorder.event("cleanup_error", error=str(exc))
