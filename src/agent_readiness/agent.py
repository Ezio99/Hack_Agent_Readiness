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
PROFILE_FILES = {"natural-shopping-v2": "natural-v2.json", "natural-shopping-v3": "natural-v3.json",
                 "natural-shopping-v3-compat1": "natural-v3-compat1.json"}
DEFAULT_PROFILE_ID = "natural-shopping-v3"
# Documented Meta levels; "none" returns HTTP 400 on Muse Spark. "xhigh"/"max" are excluded by this project.
REASONING_EFFORTS = ("minimal", "low", "medium", "high")


def profile(profile_id: str | None = None):
    """Load one frozen profile snapshot. v2 is preserved for reproducing earlier runs."""
    name = PROFILE_FILES.get(profile_id or DEFAULT_PROFILE_ID)
    if name is None:
        raise ValueError(f"Unknown profile: {profile_id}")
    return json.loads((PROFILE_DIR / name).read_text())


def validate_output_parser(effective: dict):
    from .compat import SUPPORTED_PARSERS
    if "output_parser" in effective and effective["output_parser"] not in SUPPORTED_PARSERS:
        raise ValueError(f"output_parser must be one of {', '.join(SUPPORTED_PARSERS)}")


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
    validate_output_parser(effective)
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
        self.parser = effective.get("output_parser")
        self.inner = inner
        self.capture = capture
        self.output_errors = []
        self.last_error_class = None
        self.recorder = recorder
        self.model = inner.model
        self._verified_api_keys = True
        self.usages = []
        self.last_error = None
        self.invocation_failures = []   # every invocation that produced no model response (blocked or errored)
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

    def _classify_captured_responses(self, output_format, records=None):
        """After an adapter exception: use the response captured before parsing, if any."""
        from .capture import classify_output
        for record in (records if records is not None else (self.capture.take() if self.capture else [])):
            outcome = classify_output(record, output_format)
            record["output_error"] = outcome
            record["raw_protocol_compliant"] = False if record.get("http_status") == 200 else None
            usage = record.get("usage")
            if usage:  # the adapter discarded this usage when it raised
                self.usages.append({**usage, "source": "http_capture_after_error"})
            if outcome:
                self.last_error_class = "model_output_error"
                self.output_errors.append({"request_count": self.request_count, **outcome})
                self.recorder.event("model_output_error", request_count=self.request_count, **outcome)
            self.recorder.write(f"model-response-{record['index']:02d}.json", record)

    def _try_recover(self, records, output_format):
        """Opt-in compatibility parser; returns a completion built from the validated slice, or None.

        Raw protocol compliance and recovered-action validity are tracked separately on each record."""
        from browser_use.llm.views import ChatInvokeCompletion, ChatInvokeUsage
        from . import compat
        if len(records) != 1 or output_format is None:
            return None
        record = records[0]
        if record.get("http_status") != 200 or "content" not in record or record.get("content_truncated"):
            return None
        recovery = compat.recover(record["content"], output_format)
        if recovery["status"] == "not_needed":
            # Strict JSON that the adapter nevertheless rejected (schema-invalid): nothing to recover, and the
            # raw response did not meet the contract.
            record["raw_protocol_compliant"] = False
            record["recovery"] = {"parser": recovery["parser"], "status": "not_applicable",
                                  "reason": "strict_json_failed_validation", "validated": False}
            record["recovered_action_valid"] = None
            self.recorder.write(f"model-response-{record['index']:02d}.json", record)
            return None
        record["raw_protocol_compliant"] = recovery["raw_protocol_compliant"]
        record["recovery"] = {k: v for k, v in recovery.items() if k != "normalized"}
        record["recovered_action_valid"] = recovery["validated"] if recovery["status"] != "not_needed" else None
        record["normalized_content"] = recovery["normalized"]
        self.recorder.event("model_output_recovery", request_count=self.request_count,
                            file=f"model-response-{record['index']:02d}.json",
                            original_response=record["content"], normalized_response=recovery["normalized"],
                            **{k: v for k, v in recovery.items() if k != "normalized"})
        self.recorder.write(f"model-response-{record['index']:02d}.json", record)
        if recovery["status"] != "recovered":
            return None
        usage = record.get("usage") or {}
        cached = (usage.get("prompt_tokens_details") or {}).get("cached_tokens")
        return ChatInvokeCompletion(
            completion=output_format.model_validate_json(recovery["normalized"]),
            usage=ChatInvokeUsage(prompt_tokens=usage.get("prompt_tokens") or 0, prompt_cached_tokens=cached,
                                  prompt_cache_creation_tokens=None, prompt_image_tokens=None,
                                  completion_tokens=usage.get("completion_tokens") or 0,
                                  total_tokens=usage.get("total_tokens") or 0) if usage else None,
            stop_reason=record.get("finish_reason"))

    async def ainvoke(self, messages, output_format=None, **kwargs):
        if self.request_count >= self.max_requests:
            self.limit_reached = True
            self.recorder.event("model_request_limit", count=self.request_count, limit=self.max_requests)
            self.recorder.event("model_request_blocked", reason="model_request_limit", reached_provider=False)
            self.invocation_failures.append({"reason": "model_request_limit", "reached_provider": False})
            raise ModelRequestLimitReached(f"Model request limit reached ({self.max_requests})")
        self.request_count += 1
        self.recorder.event("model_request", request_count=self.request_count, messages=self.recorder.messages(messages),
                            output_schema=output_format.model_json_schema() if output_format else None)
        try:
            result = await self.inner.ainvoke(messages, output_format=output_format, **kwargs)
            compliant = True
        except Exception as exc:
            fresh = self.capture.take() if self.capture else []
            violated = bool(self.capture and self.capture.violations)
            cost_blocked = bool(self.capture and self.capture.last_block == "cost")
            result = self._try_recover(fresh, output_format) if (self.parser and not violated and not cost_blocked) else None
            if result is None:
                self.last_error = type(exc).__name__
                self.last_error_class = ("diagnostic_fidelity_violation" if violated else
                                         "estimated_cost_limit" if cost_blocked else "infrastructure_error")
                blocked_reason = ("fidelity_violation" if violated else "estimated_cost_limit" if cost_blocked else None)
                self.invocation_failures.append({"reason": blocked_reason or "model_error",
                                                 "reached_provider": blocked_reason is None})
                if blocked_reason:
                    self.recorder.event("model_request_blocked", reason=blocked_reason, reached_provider=False)
                self._classify_captured_responses(output_format, fresh)
                message = self.recorder.clean(str(exc))
                self.recorder.event("model_error", error_type=type(exc).__name__, error=message,
                                    error_class=self.last_error_class)
                raise ModelCallError(message) from None
            compliant = False  # recovered: the raw response broke the protocol; the recovered action validated
        if self.capture:
            for record in self.capture.take():  # success path: not yet claimed
                record["raw_protocol_compliant"] = True
                self.recorder.write(f"model-response-{record['index']:02d}.json", record)
        self.last_error_class = None  # the terminal state is decided by the latest invocation
        usage = result.usage.model_dump(mode="json") if result.usage else None
        if usage:
            self.usages.append(usage)
        self.recorder.event("model_response", completion=result.completion, usage=usage,
                            stop_reason=result.stop_reason, raw_protocol_compliant=compliant)
        return result

    def protocol_compliance(self):
        """Raw-contract compliance and recovered-action validity, tracked separately (HTTP 200 responses)."""
        records = [r for r in (self.capture.records if self.capture else []) if r.get("http_status") == 200]
        return {"parser": self.parser, "http_200_responses": len(records),
                "raw_protocol_compliant": sum(1 for r in records if r.get("raw_protocol_compliant") is True),
                "raw_protocol_noncompliant": sum(1 for r in records if r.get("raw_protocol_compliant") is False),
                "recovery_attempted": sum(1 for r in records if r.get("recovery")),
                "recovered_action_valid": sum(1 for r in records if r.get("recovered_action_valid") is True),
                "recovery_rejected": sum(1 for r in records if (r.get("recovery") or {}).get("status") == "rejected")}


def classify_outcome(wrapped, done: bool, steps: int, max_steps: int):
    """(status, stop_reason). Model-output failures are distinct from infrastructure and task failures."""
    if getattr(wrapped, "capture", None) and wrapped.capture.violations:
        # A diagnostic request was blocked before the network; later retries hitting the gate must not mask it.
        return "diagnostic_fidelity_violation", "request blocked before the network"
    if getattr(wrapped, "capture", None) and wrapped.capture.cost_blocks:
        return "estimated_cost_limit", "cumulative_estimated_cost_limit"
    if done:
        return "completed", "agent_done"
    if wrapped.last_error_class == "model_output_error":
        # The unrecovered output error is the cause; a later gate trip is only the designed stop.
        return "model_output_error", f"model_output_error:{wrapped.output_errors[-1]['subtype']}"
    if wrapped.limit_reached:
        return "request_limit", "model_request_limit"
    if wrapped.last_error_class == "infrastructure_error":
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
            seen_failures = 0

            async def completed_step(current):
                nonlocal seen_failures
                if current.history.history:
                    result = current.history.history[-1].model_dump()
                    failed = wrapped.invocation_failures[seen_failures:]
                    seen_failures = len(wrapped.invocation_failures)
                    if failed:
                        # Browser Use leaves the previous step's output in this step's history entry when the model
                        # call produced no response; do not let the trace present it as this step's decision.
                        result["model_invocation"] = {"produced_response": False, "failures": failed,
                                                      "stale_model_output_discarded": result.get("model_output") is not None}
                        result["model_output"] = None
                    recorder.event("step_result", result=result)
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
                        protocol_compliance=wrapped.protocol_compliance(),
                        fidelity_violations=(capture.violations or None) if capture else None,
                        schema_narrowing_detected=any(r.get("schema_narrowed") for r in capture.requests) if capture else None,
                        model_output_errors=wrapped.output_errors or None,
                        estimated_cost=capture.cost_summary() if capture else None,
                        cost_limit_blocks=(capture.cost_blocks or None) if capture else None)
        finally:
            recorder.write("history.json", agent.history.model_dump())
            try:
                await asyncio.wait_for(browser.kill(), timeout=15)
            except Exception as exc:
                recorder.event("cleanup_error", error=str(exc))
