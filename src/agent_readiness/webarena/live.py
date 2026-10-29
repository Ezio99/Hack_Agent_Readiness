"""Guarded LIVE path for one WebArena Verified shopping task (Task 014 follow-up). This module has never made a live request: every test uses stub transports.

Spend safety, enforced in code and independent of the agent:
- every outgoing model HTTP request first passes the fidelity guard, then the DURABLE `RequestGate`: a conservative upper bound (estimated input incl. a generous
  screenshot allowance + the FULL completion allowance, +10 % margin) is appended to the fsync'd ledger BEFORE the request can reach the network;
- the gate refuses (nothing is sent) when the run cap, the ledger ceiling, the request-count cap or the per-request cap would be exceeded, or after any bound violation;
- the reservation is replaced by the actual calculated cost only when the provider returns usage; a timeout, transport error, non-200, or missing usage keeps the FULL
  upper bound counted, forever (also across process restarts, since the ledger is a file);
- every HTTP attempt reserves separately (SDK retries are off, but a retry would still be gated and counted);
- one attempt per run id, ever; no automatic retry; guard-class failures halt.
Calculated cost uses the verified published prices; the provider reports no cost, so this is an estimate and not a bill."""
from __future__ import annotations

import asyncio
import json
import os
import re
import time
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from ..agent import ModelConfig, attempt, create_model, profile
from ..capture import (IMAGE_TOKENS_ESTIMATE, INPUT_SAFETY_MARGIN, PRICE_INPUT_PER_M, PRICE_OUTPUT_PER_M, GateRefused, estimate_cost_usd, message_texts)
from ..env import load_repo_env, scrubbed_environment
from ..probe import SAFE_HEADERS, STAGE_B_MAX_COMPLETION_TOKENS, STAGE_B_REASONING_EFFORT, STAGE_B_TIMEOUT_SECONDS
from ..recorder import Recorder, utcnow
from ..scanner.live import VERIFIED_PRICES, Halt, Ledger, cost_of
from ..scanner.schema import hashes_for, output_schemas
from .adapter import WAAnswer, WATask, WebArenaShopping
from .har import NetworkCapture, sanitize_har

TASK_ID = 286
PROFILE_ID = "suite-v2-compat1"
LEDGER_CEILING_USD = 0.60          # whole step: optional probe + the run + slack
PROBE_CAP_USD = 0.04
RUN_CAP_USD = 0.50                 # cumulative upper-bound reservations of the run
PER_REQUEST_CAP_USD = 0.05         # upper bound of any single request (raised from 0.04 by owner decision 2026-10-29; run cap and ledger ceiling unchanged)
MAX_STEPS, MAX_REQUESTS, RUN_TIMEOUT_S, REQUEST_TIMEOUT_S, STEP_TIMEOUT_S = 16, 16, 300, 30, 60
IMAGE_UPPER_BOUND_TOKENS = 4_000   # per screenshot; the calibrated estimate is 1,430 (measured 8,128/9,443 prompt tokens) -> ~2.8x headroom
PROBE_PROMPT = ("Schema compatibility test only; no browser or website is involved. Return an output whose action list contains exactly one done action with "
                "success=true and data {task_type: NAVIGATE, status: SUCCESS, retrieved_data: null, error_details: null}. Fill the other fields briefly.")
GUARD_STOPS = {"diagnostic_fidelity_violation", "estimated_cost_limit", "infrastructure_error", "cancelled"}


class _Public:
    def __init__(self, prompt: str):
        self.prompt = prompt


def upper_bound_usd(body: dict) -> tuple[float, dict]:
    """Conservative upper bound of one request: the guard's estimate (full completion cap, schema, +10 %) plus extra screenshot headroom."""
    est = estimate_cost_usd(body)
    _s, _u, images = message_texts(body)
    extra_tokens = round(images * max(0, IMAGE_UPPER_BOUND_TOKENS - IMAGE_TOKENS_ESTIMATE) * INPUT_SAFETY_MARGIN)
    usd = round(est["usd"] + extra_tokens * PRICE_INPUT_PER_M / 1e6, 6)
    return usd, {**est, "images": images, "image_headroom_tokens": extra_tokens, "upper_bound_usd": usd}


class RequestGate:
    """Durable per-request spend gate (see module docstring). Plugged into `ResponseCapture` through `recorder.request_gate`."""

    def __init__(self, ledger: Ledger, run_id: str, *, run_cap: float = RUN_CAP_USD, per_request_cap: float = PER_REQUEST_CAP_USD, max_requests: int = MAX_REQUESTS):
        self.ledger, self.run_id, self.run_cap, self.per_request_cap, self.max_requests = ledger, run_id, run_cap, per_request_cap, max_requests
        self.violation: str | None = None
        self.log: list[dict] = []

    def _id(self, index: int) -> str:
        return f"{self.run_id}:req{index:02d}"

    def run_committed(self) -> float:
        state: dict[str, float] = {}
        for e in self.ledger.entries():
            if e["kind"] in ("reserve", "settle") and e["id"].startswith(self.run_id + ":req"):
                if e["kind"] == "reserve":
                    state.setdefault(e["id"], e["usd"])
                else:
                    state[e["id"]] = e["usd"]
        return round(sum(state.values()), 6)

    def request_count(self) -> int:
        return sum(1 for e in self.ledger.entries() if e["kind"] == "reserve" and e["id"].startswith(self.run_id + ":req"))

    def reserve(self, index: int, body: dict, estimate: dict | None = None) -> dict:
        if self.violation:
            raise GateRefused(f"gate closed after a bound violation: {self.violation}")
        usd, detail = upper_bound_usd(body)
        if usd > self.per_request_cap:
            raise GateRefused(f"upper bound US${usd} for this request exceeds the per-request cap US${self.per_request_cap}")
        if self.request_count() >= self.max_requests:
            raise GateRefused(f"request-count cap {self.max_requests} reached")
        if self.run_committed() + usd > self.run_cap + 1e-9:
            raise GateRefused(f"run cap US${self.run_cap}: committed US${self.run_committed()} + this request's upper bound US${usd}")
        try:
            self.ledger.reserve(self._id(index), usd)            # raises Halt over the ledger ceiling or on a repeated id; fsync'd before returning
        except Halt as exc:
            raise GateRefused(str(exc)) from exc
        self.log.append({"event": "reserved", "index": index, **detail})
        return detail

    def settle(self, index: int, record: dict) -> dict:
        reserved = next((e["usd"] for e in self.ledger.entries() if e["kind"] == "reserve" and e["id"] == self._id(index)), None)
        usage = record.get("usage") if record.get("http_status") == 200 else None
        if reserved is None:
            self.violation = f"response for request {index} without a reservation"
            return {"settled": False, "reason": self.violation}
        if not usage or usage.get("prompt_tokens") is None or usage.get("completion_tokens") is None:
            self.log.append({"event": "kept_full", "index": index, "usd": reserved})
            return {"settled": False, "reason": "no usage in the response; the full upper bound stays counted", "kept_usd": reserved}
        actual = cost_of(usage)
        if actual > reserved + 1e-9:
            self.violation = f"actual calculated cost US${actual} exceeded the reserved upper bound US${reserved} on request {index}"
            self.ledger.settle(self._id(index), actual)           # record the truth even though it exceeds the bound
            self.log.append({"event": "bound_violation", "index": index, "actual": actual, "reserved": reserved})
            return {"settled": True, "actual_usd": actual, "bound_violation": self.violation}
        self.ledger.settle(self._id(index), actual)
        self.log.append({"event": "settled", "index": index, "actual": actual, "reserved": reserved})
        return {"settled": True, "actual_usd": actual, "reserved_usd": reserved}

    def unsettled(self) -> list[str]:
        sett = {e["id"] for e in self.ledger.entries() if e["kind"] == "settle"}
        return [e["id"] for e in self.ledger.entries() if e["kind"] == "reserve" and e["id"].startswith(self.run_id + ":req") and e["id"] not in sett]


# ---------- leak checks ----------
def forbidden_strings(shop: WebArenaShopping, task_id: int) -> list[str]:
    """Strings that would reveal the evaluator's expected answer (taken from the official task definition, in process only)."""
    out: list[str] = []
    for e in shop.wa.get_task(task_id).model_dump(mode="json")["eval"]:
        exp = e.get("expected") or {}
        url = exp.get("url")
        if isinstance(url, str):
            path = url.replace("__SHOPPING__", "").strip("/")
            out += [path, path.removesuffix(".html")]
        for v in (exp.get("retrieved_data") or []):
            if isinstance(v, str) and len(v) > 3:
                out.append(v)
    return sorted({s for s in out if len(s) >= 8})


def leak_scan(texts: dict[str, str], forbidden: list[str]) -> list[dict]:
    lowered = {k: v.lower() for k, v in texts.items()}
    return [{"where": k, "needle": f[:60]} for k, v in lowered.items() for f in forbidden if f.lower() in v]


def static_inputs(task: WATask, effective: dict, answer_schema: dict) -> dict[str, str]:
    """Everything the agent is given except page observations."""
    return {"task_prompt": task.prompt(), "start_urls": " ".join(task.start_urls), "profile_instructions": effective.get("instructions", ""), "answer_schema": json.dumps(answer_schema)}


def scan_requests(trace_dir: Path, forbidden: list[str]) -> dict:
    """Post-run scan of the recorded outgoing requests: system messages must be clean; report the first request whose OBSERVATIONS contain the expected page
    (legitimate after the agent navigated there; a hit on request 1 would mean the storefront entry page itself exposes it)."""
    path = Path(trace_dir) / "trace.jsonl"
    system_hits, first_user_hit = [], None
    if path.exists():
        for line in path.read_text().splitlines():
            e = json.loads(line)
            if e.get("kind") != "model_request":
                continue
            for m in e.get("messages", []):
                text = m["content"] if isinstance(m["content"], str) else json.dumps(m["content"])
                hits = leak_scan({"x": text}, forbidden)
                if hits and m["role"] == "system":
                    system_hits.append({"request": e["request_count"], **hits[0]})
                elif hits and first_user_hit is None:
                    first_user_hit = e["request_count"]
    return {"system_message_hits": system_hits, "first_request_with_expected_page_in_observation": first_user_hit}


# ---------- preflight ----------
def preflight(config: ModelConfig, allow_model_calls: bool) -> str:
    if not allow_model_calls:
        raise Halt("refusing: live calls need --allow-model-calls")
    if (PRICE_INPUT_PER_M, PRICE_OUTPUT_PER_M) != VERIFIED_PRICES:
        raise Halt("price constants differ from the verified published prices; re-verify before spending")
    if urlsplit(config.base_url).scheme != "https":
        raise Halt("endpoint must be https")
    load_repo_env()
    key = os.environ.get(config.key_env, "")
    if not key:
        raise Halt(f"{config.key_env} is not set")
    return key


def check_site(base_url: str, ctrl_url: str | None = None, *, client: httpx.Client | None = None) -> dict:
    """Environment health (HTTP 200 on the storefront; env-ctrl /status success when given). A failure is an ENVIRONMENT problem, not a task result."""
    own = client or httpx.Client(timeout=10)
    try:
        r = own.get(base_url.rstrip("/") + "/")
        health = {"storefront_status": r.status_code, "ok": r.status_code == 200}
        if ctrl_url:
            c = own.get(ctrl_url.rstrip("/") + "/status")
            health.update(env_ctrl_status=c.status_code, env_ctrl_ok=bool(c.status_code == 200 and c.json().get("success")))
            health["ok"] = health["ok"] and health["env_ctrl_ok"]
        return health
    except Exception as exc:
        return {"ok": False, "error": type(exc).__name__}
    finally:
        if client is None:
            own.close()


# ---------- schema probe ----------
def run_schema_probe(config: ModelConfig, ledger: Ledger, out: Path, *, allow_model_calls: bool, transport=None) -> dict:
    """ONE request (<= US$0.04): the real WAAnswer wire schema, strict json_schema, text only. Tests inject `transport`; nothing here ran live."""
    from ..probe import _schema_digest
    key = preflight(config, allow_model_calls)
    full, _done, output_model = output_schemas(WAAnswer)
    digest, size = _schema_digest(full)
    worst = (size // 3 + 200) * PRICE_INPUT_PER_M / 1e6 + STAGE_B_MAX_COMPLETION_TOKENS * PRICE_OUTPUT_PER_M / 1e6
    if worst > PROBE_CAP_USD:
        raise Halt(f"probe worst-case estimate US${worst:.4f} exceeds the US${PROBE_CAP_USD} cap")
    ledger.reserve("probe", PROBE_CAP_USD)
    recorder = Recorder(Path(out), (key,))
    recorder.write("schema.json", full)
    body = {"model": config.model, "reasoning_effort": STAGE_B_REASONING_EFFORT, "max_completion_tokens": STAGE_B_MAX_COMPLETION_TOKENS,
            "response_format": {"type": "json_schema", "json_schema": {"name": "agent_output", "strict": True, "schema": full}}, "messages": [{"role": "user", "content": PROBE_PROMPT}]}
    rec = {"stage": "webarena-answer-schema-probe", "started_at": utcnow(), "endpoint": config.base_url, "model": config.model, "schema_sha256": digest, "schema_bytes": size,
           "worst_case_estimate_usd": round(worst, 6), "request_attempts": 1, "success": False, "failure_class": None, "usage": None, "http_status": None, "error": None}
    started = time.monotonic()
    try:
        with httpx.Client(timeout=STAGE_B_TIMEOUT_SECONDS, follow_redirects=False, transport=transport) as client:
            r = client.post(config.base_url.rstrip("/") + "/chat/completions", json=body, headers={"Authorization": f"Bearer {key}"})
        rec["http_status"], rec["request_id"] = r.status_code, r.headers.get("x-request-id")
        rec["response_headers"] = {k: v for k, v in r.headers.items() if k.lower() in SAFE_HEADERS}
        payload = r.json() if r.headers.get("content-type", "").startswith("application/json") else None
        if r.status_code != 200:
            rec.update(failure_class="schema_or_request_rejected" if r.status_code == 400 else "http_error", error=recorder.clean(payload or r.text[:500]))
        elif payload:
            choice = (payload.get("choices") or [{}])[0]
            content = (choice.get("message") or {}).get("content")
            rec.update(usage=payload.get("usage"), finish_reason=choice.get("finish_reason"), completion=content)
            ok = False
            try:
                parsed = output_model.model_validate_json(content)
                acts = [a.model_dump(mode="json", exclude_none=True) for a in parsed.action]
                ok = len(acts) == 1 and list(acts[0]) == ["done"] and acts[0]["done"].get("data", {}).get("task_type") == "NAVIGATE" \
                    and acts[0]["done"]["data"].get("status") == "SUCCESS"
            except Exception as exc:
                rec["validation_error"] = f"{type(exc).__name__}: {str(exc)[:300]}"
            rec["success"] = bool(ok and rec["finish_reason"] == "stop")
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
    ledger.settle("probe", rec["calculated_cost_usd"] if rec["usage"] is not None else PROBE_CAP_USD)      # unknown spend keeps the full reservation
    if rec["success"]:
        ledger.mark_probe_ok()
    return rec


# ---------- the run ----------
async def run_live(shop: WebArenaShopping, ledger: Ledger, out: Path, *, config: ModelConfig | None = None, allow_model_calls: bool = False, api_key: str | None = None,
                   stub_handler=None, health: dict | None = None, require_probe: bool = True, task_id: int = TASK_ID, run_id: str = "wa286") -> dict:
    """Exactly one run. `stub_handler` (tests only) replaces the provider with a scripted httpx handler and needs no key; the result is then labelled mode='stub'."""
    config = config or ModelConfig()
    from ..scanner import mock
    if stub_handler is None:
        key = preflight(config, allow_model_calls)
        if require_probe and not ledger.probe_succeeded():
            raise Halt("the WAAnswer schema probe has not succeeded; no run allowed")
    else:
        key = "stub-not-a-key"
    health = health if health is not None else await asyncio.to_thread(check_site, shop.base_url)
    if not health.get("ok"):
        raise Halt(f"environment health check failed (an environment problem, nothing spent): {health}")
    task = shop.task(task_id)
    effective = profile(PROFILE_ID)
    effective.update(max_steps=MAX_STEPS, max_model_requests=MAX_REQUESTS, timeout_seconds=RUN_TIMEOUT_S, model_timeout_seconds=REQUEST_TIMEOUT_S, step_timeout_seconds=STEP_TIMEOUT_S)
    hashes = hashes_for(WAAnswer)
    full_schema, _done, _m = output_schemas(WAAnswer)
    forbidden = forbidden_strings(shop, task_id)
    pre_hits = leak_scan(static_inputs(task, effective, full_schema), forbidden)
    if pre_hits:
        raise Halt(f"pre-run leak scan found evaluator ground truth in the agent's static inputs: {pre_hits}")
    ledger.reserve(run_id, 0.0)                                  # one attempt per run id, ever (also blocks a retry after an interrupted run)
    out = Path(out)
    recorder = Recorder(out, (key,))
    gate = RequestGate(ledger, run_id)
    recorder.request_gate = gate
    recorder.expectations = {"schema_sha256": hashes["full"], "done_only_schema_sha256": hashes["done_only"], "task_prompt": task.prompt(),
                             "max_estimated_cost_usd": PER_REQUEST_CAP_USD, "max_cumulative_estimated_cost_usd": RUN_CAP_USD, "max_steps": MAX_STEPS,
                             "parameters": {"max_completion_tokens": effective["max_completion_tokens"], "reasoning_effort": effective["reasoning_effort"], "model": config.model}}
    llm = create_model(config, effective, api_key=key)
    if stub_handler is not None:
        mock.attach_mock(llm, stub_handler)
    capture = NetworkCapture(recorder.path / "network.har")
    started, started_at = time.monotonic(), utcnow()
    status, stop_reason, errors, att = "infrastructure_error", "not_started", [], {}
    try:
        with scrubbed_environment(config.key_env):
            async with asyncio.timeout(RUN_TIMEOUT_S):
                att = await attempt(_Public(task.prompt()), task.start_urls[0], llm, recorder, effective, WAAnswer, network_capture=capture)
        status, stop_reason, errors = att["status"], att["stop_reason"], att.get("errors", [])
    except TimeoutError:
        status, stop_reason, errors = "timeout", "wall_clock_limit", [f"run exceeded {RUN_TIMEOUT_S}s"]
    except asyncio.CancelledError:
        raise
    except Exception as exc:                                     # never retried automatically
        status, stop_reason, errors = "infrastructure_error", type(exc).__name__, [recorder.clean(str(exc))[:300]]
    har = recorder.path / "network.har"
    if not har.exists():                                         # attempt() always closes the capture; if it died before, write what we have
        await capture.close()
    answer = att.get("answer")
    verdict = shop.evaluate(task_id, answer, har) if har.exists() and answer is not None else {"passed": False, "error": "no answer from the agent" if answer is None else "no HAR", "evaluators": []}
    sanitized = sanitize_har(har, recorder.path / "network.sanitized.har") if har.exists() else None
    post = scan_requests(recorder.path, forbidden)
    end_health = await asyncio.to_thread(check_site, shop.base_url) if stub_handler is None else {"ok": True, "stub": True}
    committed = gate.run_committed()
    unsettled = gate.unsettled()
    record = {"mode": "live" if stub_handler is None else "stub", "task_id": task_id, "profile": PROFILE_ID, "model": config.model, "endpoint": config.base_url, "run_id": run_id,
              "run_status": status, "stop_reason": stop_reason, "errors": errors, "answer": answer, "official_verdict": verdict, "har_entries": len(capture.entries), "sanitized_har": sanitized,
              "limits": {"max_steps": MAX_STEPS, "max_model_requests": MAX_REQUESTS, "timeout_seconds": RUN_TIMEOUT_S, "request_timeout_seconds": REQUEST_TIMEOUT_S, "run_cap_usd": RUN_CAP_USD,
                         "per_request_cap_usd": PER_REQUEST_CAP_USD, "ledger_ceiling_usd": ledger.ceiling},
              "spend": {"requests_reserved": gate.request_count(), "run_committed_usd": committed, "unsettled_reservations": unsettled, "ledger_total_committed_usd": ledger.committed(),
                        "basis": "calculated from provider-reported tokens at published prices where usage was returned; otherwise the full upper bound; not a bill"},
              "gate_log": gate.log, "gate_violation": gate.violation, "model_requests": att.get("model_request_count"), "steps": att.get("steps"),
              "protocol": att.get("protocol_compliance"), "fidelity_violations": att.get("fidelity_violations"), "leak_scan": {"pre_run_hits": pre_hits, **post},
              "health": {"start": health, "end": end_health}, "elapsed_seconds": round(time.monotonic() - started, 2), "started_at": started_at, "finished_at": utcnow()}
    record["guard_halt"] = bool(status in GUARD_STOPS or gate.violation or post["system_message_hits"])
    recorder.write("live-result.json", record)
    return record
