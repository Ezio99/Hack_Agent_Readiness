"""Run ONE generated task against a site snapshot (served by the read-only mirror) with the real Browser Use agent, bounded, and grade it independently.

A copy-adapt of `scanner.execute.execute_scan` for generated tasks (that module is frozen and tied to registered tasks/variants); same profile, fidelity guard, optional
reserve-before-send `request_gate`, wall-clock timeout and journey/evaluation record. Modes: `mock` (scripted agent behaviour through the real browser, no network, no key) and `live`
(Meta model; the caller must have passed the approval gates — see `trials.stage`). Mock results say nothing about model behaviour."""
from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path

from ...agent import ModelConfig, attempt, create_model, profile
from ...env import scrubbed_environment
from ...recorder import Recorder, utcnow
from ...scanner.execute import PER_REQUEST_COST_CEILING_USD, build_journey, calculated_cost
from ...scanner.mock import _reply, attach_mock
from ...scanner.schema import hashes_for
from ...scanner.serve import serve_app
from ...suite import core
from ..sitemodel.server import Mirror
from ..sitemodel.snapshot import Snapshot
from ..taskgen import freeze as freezer

MODES = ("mock", "live")
MOCK_BEHAVIORS = ("correct", "lazy", "wrong", "stuck", "provider_error")
PROFILE_ID = "suite-v2-compat1"


class _PublicTask:
    def __init__(self, prompt: str):
        self.prompt = prompt


def _answer_payload(instance: core.TaskInstance, correct: bool):
    truth = instance.truth["expected"]
    if isinstance(truth, list):
        return {"answers": list(truth) if correct else list(truth)[:-1] or ["(none)"]}
    return {"answer": truth if correct else "(not sure)"}


def mock_handler(instance: core.TaskInstance, base_url: str, behavior: str, evidence_paths: list[str]):
    """Scripted agent: visit the start page and the evidence pages in order, then answer (correct | wrong), answer after the start page only (lazy), or never finish (stuck)."""
    if behavior not in MOCK_BEHAVIORS:
        raise ValueError(f"unknown mock behavior {behavior!r}")
    nav = lambda p: [{"navigate": {"url": base_url + p, "new_tab": False}}]
    route = [instance.spec.start_path] + [p for p in evidence_paths if p != instance.spec.start_path]
    state = {"n": 0}

    def handler(request):
        state["n"] += 1
        n = state["n"]
        if behavior == "provider_error":
            raise ConnectionError("mock provider failure")
        last = "this is your last step" in json.dumps(json.loads(request.content)["messages"]).lower()
        steps = {"lazy": 1, "stuck": 10_000}.get(behavior, len(route))
        if n <= min(steps, len(route)) and not last:
            return _reply(n, nav(route[n - 1]))
        if behavior == "stuck" and not last:
            return _reply(n, [{"wait": {"seconds": 1}}])
        return _reply(n, [{"done": {"data": _answer_payload(instance, behavior in ("correct", "lazy")), "success": True}}])
    return handler


async def run_trial(instance: core.TaskInstance, snapshot: Snapshot, *, provider: str = "mock", mock_behavior: str = "correct", output: Path, model_config: ModelConfig | None = None,
                    api_key: str | None = None, profile_id: str = PROFILE_ID, request_gate=None, label: str = "baseline") -> dict:
    if provider not in MODES:
        raise ValueError("provider must be mock or live")
    if provider == "live" and not api_key:
        raise ValueError("live mode requires an API key supplied by the caller after the approval gates")
    spec = instance.spec
    effective = profile(profile_id)
    effective.update(max_steps=spec.limits.max_steps, timeout_seconds=spec.limits.timeout_seconds, max_model_requests=spec.limits.max_model_requests)
    config = model_config or ModelConfig()
    recorder = Recorder(Path(output), (api_key or "",))
    hashes = hashes_for(instance.answer_model)
    started, mirror = time.monotonic(), Mirror(snapshot)
    variant = freezer.variant_for(snapshot.sha256)
    record: dict = {"trial": {"label": label, "mode": provider, "mock_behavior": mock_behavior if provider == "mock" else None, "started_at": utcnow(),
                              "model": config.model if provider == "live" else "mock-scripted-agent", "profile": profile_id, "profile_hash": core.canonical_hash(effective),
                              "schema_hashes": hashes, "snapshot_sha256": snapshot.sha256},
                    "task": spec.record()}
    status, stop_reason, errors, answer, att = "infrastructure_error", "not_started", [], None, {}
    try:
        async with serve_app(mirror) as base_url:
            llm = create_model(config, effective, api_key=(api_key if provider == "live" else "mock-not-a-key"))
            if provider == "mock":
                attach_mock(llm, mock_handler(instance, base_url, mock_behavior, [r.value for r in instance.evidence if r.kind == "visited_path"]))
            recorder.expectations = {"schema_sha256": hashes["full"], "done_only_schema_sha256": hashes["done_only"], "task_prompt": spec.objective,
                                     "max_estimated_cost_usd": PER_REQUEST_COST_CEILING_USD, "max_cumulative_estimated_cost_usd": round(PER_REQUEST_COST_CEILING_USD * spec.limits.max_model_requests, 4),
                                     "max_steps": spec.limits.max_steps, "parameters": {"max_completion_tokens": effective["max_completion_tokens"], "reasoning_effort": effective["reasoning_effort"], "model": config.model}}
            if request_gate is not None:
                recorder.request_gate = request_gate
            scope = scrubbed_environment(config.key_env) if provider == "live" else None
            try:
                if scope:
                    scope.__enter__()
                async with asyncio.timeout(spec.limits.timeout_seconds):
                    att = await attempt(_PublicTask(spec.objective), base_url + spec.start_path, llm, recorder, effective, instance.answer_model)
            finally:
                if scope:
                    scope.__exit__(None, None, None)
            status, stop_reason, answer, errors = att["status"], att["stop_reason"], att["answer"], att.get("errors", [])
    except TimeoutError:
        status, stop_reason, errors = "timeout", "wall_clock_limit", [f"trial exceeded {spec.limits.timeout_seconds}s"]
    except asyncio.CancelledError:
        raise
    except Exception as exc:                                       # infrastructure failure: never retried automatically (a retry could bill again)
        status, stop_reason, errors = "infrastructure_error", type(exc).__name__, [recorder.clean(str(exc))[:300]]
    events = [json.loads(l) for l in (recorder.path / "trace.jsonl").read_text().splitlines()] if (recorder.path / "trace.jsonl").exists() else []
    observations, journey = build_journey(events)
    evaluation = core.evaluate(instance, answer, variant, observations if events else [])
    recorder.write("observations.json", [{"path": o.path, "text": o.text} for o in observations])        # private: what the model was shown, for attribution
    usage = att.get("usage") or []
    record.update({
        "outcome": {"run_status": status, "stop_reason": stop_reason, "errors": errors, "answer": answer},
        "evaluation": evaluation.as_dict(),
        "metrics": {"model_requests": att.get("model_request_count", 0), "steps": att.get("steps"), "page_views": len(journey), "mirror_requests": len(mirror.log), "elapsed_seconds": round(time.monotonic() - started, 2),
                    "prompt_tokens": sum((u or {}).get("prompt_tokens") or 0 for u in usage), "completion_tokens": sum((u or {}).get("completion_tokens") or 0 for u in usage),
                    "calculated_cost_usd": calculated_cost(usage), "cost_basis": ("MOCK tokens at published prices - not billed, not a model result" if provider == "mock" else "calculated from provider-reported tokens at published prices; not a bill"),
                    "limits": {"max_steps": spec.limits.max_steps, "max_model_requests": spec.limits.max_model_requests, "timeout_seconds": spec.limits.timeout_seconds}},
        "mirror": {"log": mirror.log, "blocked": mirror.blocked}, "protocol": att.get("protocol_compliance"),
        "guard": {"fidelity_violations": att.get("fidelity_violations"), "final_step_schema_seen": bool(att.get("schema_narrowing_detected"))},
        "journey": journey, "finished_at": utcnow()})
    recorder.write("trial-result.json", record)
    record["artifact_path"] = str(recorder.path)
    return record
