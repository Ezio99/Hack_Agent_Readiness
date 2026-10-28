"""Run one registered task against one registered environment variant through the real Browser Use agent, bounded and independently evaluated.

Provider modes: ``mock`` (default; deterministic scripted behaviour, no network, no credentials) and ``live`` (Meta model API; gated by the caller, never used by
tests or CI; this module has never made a live request). All limits are enforced per request/step by the existing fidelity guard, request gate and an overall wall-clock
timeout. The browser may only reach the single loopback origin of the environment under test."""
from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from urllib.parse import urlsplit

from ..agent import ModelConfig, attempt, create_model, profile
from ..capture import PRICE_INPUT_PER_M, PRICE_OUTPUT_PER_M
from ..env import scrubbed_environment
from ..recorder import Recorder, utcnow
from ..suite import core, registry
from . import diagnostics, mock
from .schema import PROFILE_ID, hashes_for
from .serve import serve_app

MODES = ("mock", "live")
PER_REQUEST_COST_CEILING_USD = 0.04      # same per-request estimate ceiling as Tasks 005-007
SAFE_ACTION_PARAMS = {"click": ["index"], "navigate": ["url"], "go_back": [], "select_dropdown": ["index", "text"], "input": ["index", "text"], "find_elements": ["selector"],
                      "scroll": ["down", "pages"], "wait": ["seconds"], "search_page": [], "done": []}


class _PublicTask:
    def __init__(self, prompt: str):
        self.prompt = prompt


def _paths(url: str) -> tuple[str, str]:
    parts = urlsplit(url or "")
    return parts.path or "/", parts.query


def safe_action(action: dict) -> dict:
    name = next(iter(action), "unknown")
    params = action.get(name) or {}
    allowed = SAFE_ACTION_PARAMS.get(name, [])
    out = {k: params[k] for k in allowed if k in params and params[k] is not None}
    if name == "navigate" and "url" in out:
        u = urlsplit(str(out["url"]))
        out["url"] = (u.path or "/") + (f"?{u.query}" if u.query else "") if u.hostname in ("127.0.0.1", "localhost") else f"[external] {u.scheme}://{u.hostname}"
    if name == "find_elements" and "selector" in out:
        out["selector"] = str(out["selector"])[:40]
    return {"name": name, "params": out}


def build_journey(events: list[dict]) -> tuple[list[core.Observation], list[dict]]:
    observations, journey = [], []
    results = [e["result"] for e in events if e["kind"] == "step_result"]
    for i, e in enumerate([e for e in events if e["kind"] == "observation"]):
        path, query = _paths(e.get("url", ""))
        observations.append(core.Observation(path, e.get("dom") or ""))
        res = results[i] if i < len(results) else {}
        executed = []
        for j, r in enumerate(res.get("result", [])):
            executed.append({"result": (r.get("extracted_content") or "")[:160].replace("\n", " "), "error": (r.get("error") or "")[:160] or None})
        journey.append({"step": e.get("step", i + 1), "path": path, "query": query, "actions": [safe_action(a) for a in e.get("proposed_actions", [])], "executed": executed})
    return observations, journey


def calculated_cost(usage: list[dict]) -> float:
    prompt = sum((u or {}).get("prompt_tokens") or 0 for u in usage)
    completion = sum((u or {}).get("completion_tokens") or 0 for u in usage)
    return round(prompt * PRICE_INPUT_PER_M / 1e6 + completion * PRICE_OUTPUT_PER_M / 1e6, 6)


async def execute_scan(task_id: str, variant: core.Variant, *, provider: str = "mock", mock_behavior: str = "correct", output: Path,
                       model_config: ModelConfig | None = None, api_key: str | None = None) -> dict:
    """Execute and evaluate one scan. Returns the PRIVATE result (full evaluation incl. reasons, journey, findings); callers must sanitize before sending it out."""
    if provider not in MODES:
        raise ValueError("provider must be mock or live")
    if provider == "live" and not api_key:
        raise ValueError("live mode requires an API key supplied by the server configuration")
    instance = registry.get_instance(task_id)
    spec = instance.spec
    effective = profile(PROFILE_ID)
    effective.update(max_steps=spec.limits.max_steps, timeout_seconds=spec.limits.timeout_seconds, max_model_requests=spec.limits.max_model_requests)
    hashes = hashes_for(instance.answer_model)
    config = model_config or ModelConfig()
    recorder = Recorder(Path(output), (api_key or "",))
    started, started_at = time.monotonic(), utcnow()
    env = core.ENVIRONMENTS[spec.environment_id]
    record: dict = {"scan": {"mode": provider, "mock_behavior": mock_behavior if provider == "mock" else None, "started_at": started_at,
                              "model": config.model if provider == "live" else "mock-scripted-agent", "profile": PROFILE_ID,
                              "profile_hash": core.canonical_hash(effective), "schema_hashes": hashes},
                    "task": spec.record(), "variant": {"id": variant.variant_id, "factors": dict(variant.factors)}}
    status, stop_reason, errors, answer, att = "infrastructure_error", "not_started", [], None, {}
    try:
        async with serve_app(env.create_app(variant)) as base_url:
            llm = create_model(config, effective, api_key=(api_key if provider == "live" else "mock-not-a-key"))
            if provider == "mock":
                mock.attach_mock(llm, mock.make_handler(instance, variant, base_url, mock_behavior))
            recorder.expectations = {
                "schema_sha256": hashes["full"], "done_only_schema_sha256": hashes["done_only"], "task_prompt": spec.objective,
                "max_estimated_cost_usd": PER_REQUEST_COST_CEILING_USD, "max_cumulative_estimated_cost_usd": round(PER_REQUEST_COST_CEILING_USD * spec.limits.max_model_requests, 4),
                "max_steps": spec.limits.max_steps,
                "parameters": {"max_completion_tokens": effective["max_completion_tokens"], "reasoning_effort": effective["reasoning_effort"], "model": config.model},
            }
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
        status, stop_reason, errors = "timeout", "wall_clock_limit", [f"scan exceeded {spec.limits.timeout_seconds}s"]
    except asyncio.CancelledError:
        status, stop_reason, errors = "cancelled", "cancelled", ["scan was cancelled"]
        raise
    except Exception as exc:          # infrastructure failure: never retried automatically (a retry could bill again)
        status, stop_reason, errors = "infrastructure_error", type(exc).__name__, [recorder.clean(str(exc))[:300]]
    events = [json.loads(l) for l in (recorder.path / "trace.jsonl").read_text().splitlines()] if (recorder.path / "trace.jsonl").exists() else []
    observations, journey = build_journey(events)
    evaluation = core.evaluate(instance, answer, variant, observations if events else [])
    usage = att.get("usage") or []
    elapsed = round(time.monotonic() - started, 2)
    record.update({
        "outcome": {"run_status": status, "stop_reason": stop_reason, "errors": errors, "answer": answer},
        "evaluation": evaluation.as_dict(),
        "metrics": {"model_requests": att.get("model_request_count", 0), "steps": att.get("steps"), "page_views": len(journey), "elapsed_seconds": elapsed,
                    "prompt_tokens": sum((u or {}).get("prompt_tokens") or 0 for u in usage), "completion_tokens": sum((u or {}).get("completion_tokens") or 0 for u in usage),
                    "calculated_cost_usd": calculated_cost(usage), "cost_basis": ("MOCK tokens at published prices — not billed, not a model result" if provider == "mock" else
                                                                                  "calculated from provider-reported tokens at published prices; not a bill"),
                    "limits": {"max_steps": spec.limits.max_steps, "max_model_requests": spec.limits.max_model_requests, "timeout_seconds": spec.limits.timeout_seconds}},
        "protocol": att.get("protocol_compliance"), "guard": {"fidelity_violations": att.get("fidelity_violations"), "final_step_schema_seen": bool(att.get("schema_narrowing_detected"))},
        "journey": journey, "finished_at": utcnow(),
    })
    record["diagnostics"] = diagnostics.analyze(record, events, instance, variant)
    recorder.write("scan-result.json", record)
    record["artifact_path"] = str(recorder.path)
    return record
