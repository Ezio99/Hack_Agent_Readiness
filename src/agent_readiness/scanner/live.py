"""Approved, bounded live validation of the suite on Meta Muse Spark (Task 011 follow-up). PRIVATE outputs under ``runs/`` (Git-ignored).

Guarantees enforced in code (and unit-tested with stubs; the tests never contact a provider):
- a persistent append-only ledger with a hard calculated ceiling (default US$2.00 INCLUDING the schema probe); amounts are reserved BEFORE any request and an
  unsettled/interrupted reservation keeps counting in full;
- the probe must have succeeded before any run; probe: one request, calculated cost <= US$0.04;
- fixed fixture order, sequential, one attempt per fixture ever (a recorded attempt is never repeated), no automatic retry;
- stop after a guard-class failure (fidelity violation, estimated-cost limit, infrastructure/provider error); a wrong answer or a model-driven limit stop is a result, not a guard failure;
- calculated cost uses the verified published prices ($1.25 / $4.25 per M tokens); the provider reports no cost, so this is an estimate, not a bill."""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from ..agent import ModelConfig
from ..capture import PRICE_INPUT_PER_M, PRICE_OUTPUT_PER_M
from ..ledger import DEFAULT_CEILING_USD, Halt, Ledger, cost_of      # noqa: F401  (re-exported: shared primitives now live in agent_readiness.ledger)
from ..environments.electronics.variants import make_variant
from ..probe import SAFE_HEADERS, STAGE_B_MAX_COMPLETION_TOKENS, STAGE_B_REASONING_EFFORT, STAGE_B_TIMEOUT_SECONDS, _find_cost, _schema_digest
from ..recorder import Recorder, utcnow
from ..suite import registry
from .execute import execute_scan
from .schema import output_schemas

CEILING_USD = DEFAULT_CEILING_USD
PROBE_CAP_USD = 0.04
RUN_RESERVE_USD = 0.48                      # 12 requests x US$0.04 per-request estimate ceiling
VERIFIED_PRICES = (1.25, 4.25)              # https://dev.meta.ai/docs/pricing-rate-limits (muse-spark-1.3 Standard), verified 2026-10-28
FIXTURES = ("t1-anc-headphones-under-250-all", "t2-compare-air14-vs-probook15", "t3-cheapest-monitor-27in-usbc-120hz", "t4-policy-delivery-tessera-whisper")
VARIANT = ("listing", "structured")         # availability-listing+specs-structured
GUARD_STOPS = {"diagnostic_fidelity_violation", "estimated_cost_limit", "infrastructure_error", "cancelled"}
PROBE_PROMPT = ("Schema compatibility test only; no browser or website is involved. Return an output whose action list contains exactly one done action with "
                "success=true and data {products: [{sku: \"PROBE-0\", price_cents: 100}]}. Fill the other fields briefly.")


def preflight(config: ModelConfig, allow_model_calls: bool) -> str:
    if not allow_model_calls:
        raise Halt("refusing: live calls need --allow-model-calls")
    if (PRICE_INPUT_PER_M, PRICE_OUTPUT_PER_M) != VERIFIED_PRICES:
        raise Halt("price constants differ from the verified published prices; re-verify before spending")
    if urlsplit(config.base_url).scheme != "https":
        raise Halt("endpoint must be https")
    from ..env import load_repo_env
    load_repo_env()
    key = os.environ.get(config.key_env, "")
    if not key:
        raise Halt(f"{config.key_env} is not set")
    return key


def run_probe(config: ModelConfig, ledger: Ledger, out: Path, *, allow_model_calls: bool, transport=None) -> dict:
    """One request: the real full AgentOutput wire schema for the T1 answer model, strict json_schema, text only."""
    key = preflight(config, allow_model_calls)
    from ..environments.electronics.tasks import T1Answer
    full, _done, output_model = output_schemas(T1Answer)
    digest, size = _schema_digest(full)
    est_input = size // 3 + 200
    worst = est_input * PRICE_INPUT_PER_M / 1e6 + STAGE_B_MAX_COMPLETION_TOKENS * PRICE_OUTPUT_PER_M / 1e6
    if worst > PROBE_CAP_USD:
        raise Halt(f"probe worst-case estimate US${worst:.4f} exceeds the US${PROBE_CAP_USD} cap")
    ledger.reserve("probe", PROBE_CAP_USD)
    recorder = Recorder(Path(out), (key,))
    recorder.write("schema.json", full)
    body = {"model": config.model, "reasoning_effort": STAGE_B_REASONING_EFFORT, "max_completion_tokens": STAGE_B_MAX_COMPLETION_TOKENS,
            "response_format": {"type": "json_schema", "json_schema": {"name": "agent_output", "strict": True, "schema": full}}, "messages": [{"role": "user", "content": PROBE_PROMPT}]}
    rec = {"stage": "suite-schema-probe", "started_at": utcnow(), "endpoint": config.base_url, "model": config.model, "schema_sha256": digest, "schema_bytes": size,
           "worst_case_estimate_usd": round(worst, 6), "request_attempts": 1, "success": False, "failure_class": None, "usage": None, "http_status": None, "grading": None, "error": None}
    started = time.monotonic()
    try:
        with httpx.Client(timeout=STAGE_B_TIMEOUT_SECONDS, follow_redirects=False, transport=transport) as client:
            r = client.post(config.base_url.rstrip("/") + "/chat/completions", json=body, headers={"Authorization": f"Bearer {key}"})
        rec["http_status"], rec["request_id"] = r.status_code, r.headers.get("x-request-id")
        rec["response_headers"] = {k: v for k, v in r.headers.items() if k.lower() in SAFE_HEADERS}
        payload = r.json() if r.headers.get("content-type", "").startswith("application/json") else None
        if r.status_code != 200:
            rec.update(failure_class="schema_or_request_rejected" if r.status_code == 400 else "http_error", error=payload or r.text[:500])
        elif payload:
            choice = (payload.get("choices") or [{}])[0]
            content = (choice.get("message") or {}).get("content")
            rec.update(usage=payload.get("usage"), finish_reason=choice.get("finish_reason"), provider_reported_cost=_find_cost(payload.get("usage") or {}) or None, completion=content)
            g = {"json_parsed": False, "agent_output_valid": False, "single_done_action": False, "values_match": False, "validation_error": None}
            try:
                json.loads(content or "")
                g["json_parsed"] = True
                parsed = output_model.model_validate_json(content)
                g["agent_output_valid"] = True
                acts = [a.model_dump(mode="json", exclude_none=True) for a in parsed.action]
                if len(acts) == 1 and list(acts[0]) == ["done"]:
                    g["single_done_action"] = True
                    g["values_match"] = acts[0]["done"].get("data") == {"products": [{"sku": "PROBE-0", "price_cents": 100}]}
            except Exception as exc:
                g["validation_error"] = f"{type(exc).__name__}: {str(exc)[:300]}"
            rec["grading"] = g
            rec["success"] = bool(rec["finish_reason"] == "stop" and all(g[k] for k in ("json_parsed", "agent_output_valid", "single_done_action", "values_match")))
            if not rec["success"]:
                rec["failure_class"] = "cap_exhausted" if rec["finish_reason"] == "length" else "unparsable_or_mismatch"
    except httpx.HTTPError as exc:
        rec.update(failure_class=type(exc).__name__, error=str(exc)[:300])
    rec["elapsed_seconds"] = round(time.monotonic() - started, 3)
    rec["calculated_cost_usd"] = cost_of(rec["usage"])
    if rec["calculated_cost_usd"] > PROBE_CAP_USD:
        rec["success"], rec["failure_class"] = False, "probe_cost_cap_exceeded"
    rec["finished_at"] = utcnow()
    recorder.write("probe.json", rec)
    ledger.settle("probe", rec["calculated_cost_usd"] if rec["usage"] is not None else PROBE_CAP_USD)   # unknown spend keeps the full reservation
    if rec["success"]:
        ledger.mark_probe_ok()
    return rec


def run_fixtures(config: ModelConfig, ledger: Ledger, out: Path, *, allow_model_calls: bool, runner=execute_scan, fixtures=FIXTURES) -> list[dict]:
    import asyncio
    key = preflight(config, allow_model_calls)
    if not ledger.probe_succeeded():
        raise Halt("the schema probe has not succeeded; no runs allowed")
    registry.load_all()
    variant = make_variant(*VARIANT)
    results = []
    for task_id in fixtures:
        if ledger.attempted(task_id):
            results.append({"task_id": task_id, "skipped": "already attempted; never repeated"})
            continue
        ledger.reserve(task_id, RUN_RESERVE_USD)               # raises Halt if the ceiling would be exceeded
        try:
            rec = asyncio.run(runner(task_id, variant, provider="live", output=Path(out) / task_id, model_config=config, api_key=key))
        except BaseException as exc:                           # interrupted: keep the full reservation, stop, no retry
            results.append({"task_id": task_id, "error": type(exc).__name__, "reservation_kept_usd": RUN_RESERVE_USD})
            raise
        actual = rec["metrics"]["calculated_cost_usd"]
        ledger.settle(task_id, min(actual, RUN_RESERVE_USD) if actual <= RUN_RESERVE_USD else actual)
        summary = {"task_id": task_id, "run_status": rec["outcome"]["run_status"], "stop_reason": rec["outcome"]["stop_reason"], "passed": rec["evaluation"]["passed"],
                   "evidence_backed": rec["evaluation"]["evidence_backed"], "model_requests": rec["metrics"]["model_requests"], "elapsed_seconds": rec["metrics"]["elapsed_seconds"],
                   "calculated_cost_usd": actual, "artifact": str(Path(out) / task_id)}
        results.append(summary)
        (Path(out) / "summary.json").write_text(json.dumps(results, indent=1))
        if actual > RUN_RESERVE_USD or rec["outcome"]["run_status"] in GUARD_STOPS:
            summary["halted_after"] = "guard-class failure" if actual <= RUN_RESERVE_USD else "run exceeded its reservation"
            break
    (Path(out) / "summary.json").write_text(json.dumps(results, indent=1))
    return results
