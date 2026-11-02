"""Lifecycle M6, Stage A only: ONE paid task-generation experiment on Larkspur, owner-authorised with a hard total cap.

    python -m agent_readiness.suites.experiments.m6_stage_a --preflight-only              # zero cost: every check, no paid call
    python -m agent_readiness.suites.experiments.m6_stage_a --approval-note "..."          # paid: refuses unless every preflight check passes

Configuration (owner, 2026-11-02): muse-spark-1.3, reasoning_effort low, max_completion_tokens 6000, prompt taskplan-v2, schema taskplan-schema-v3,
12 proposals per round, at most 3 rounds and 3 model requests, hard total cap US$0.10, suite name larkspur-core (UNAPPROVED proposal only).

Enforcement: the durable spend gate (reserve-before-send into an fsync'd ledger in a FIXED directory, so a restart can never add requests or spend
beyond the caps), the loop's own budget stop (checked before each round), no retries anywhere. The experiment refuses to start if the fixed
ledger already holds reservations: the authorisation is for one experiment. Nothing here approves or freezes a suite, runs Stage B or calls a browser
agent. Outputs: scanner-data/research/stage-a/ (git-ignored)."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from ...framework.site import get
from ...research.taskplan import catalogue as K
from ...research.taskplan import context as X
from ...research.taskplan import planner_v2 as PV2
from ...research.taskplan.schema_v3 import SCHEMA_V3, json_schema_v3, parse_item_v3

RUN_ID = "m6-larkspur-core"
ROOT = Path(__file__).resolve().parents[4]
BASE = ROOT / "scanner-data" / "research" / "stage-a"
LEDGER_DIR = BASE / "ledgers" / RUN_ID                                      # FIXED for this authorisation
SETTINGS = {"site": "larkspur", "model": "muse-spark-1.3", "reasoning_effort": "low", "max_completion_tokens": 6000, "prompt_version": "taskplan-v2",
            "schema_version": SCHEMA_V3, "proposals_per_round": 12, "max_rounds": 3, "max_requests": 3, "cap_usd": 0.10, "per_request_cap_usd": 0.04,
            "suite_name": "larkspur-core", "gate_run_id": RUN_ID}


def _loop_config(S: dict):
    from ...suites.stage_a import loop as LP
    from ...suites.stage_a import stopping as ST
    return LP.LoopConfig(suite_name=S["suite_name"], n_per_round=S["proposals_per_round"], max_tokens=S["max_completion_tokens"],
                         stop=ST.StopRule(max_rounds=S["max_rounds"], budget_cap_usd=S["cap_usd"]))


def _fake_response(request, prompt_tokens: int = 3000, completion_tokens: int = 5000) -> dict:
    """A provider-shaped 200 for the zero-cost gate rehearsal: developer-written pool items (NOT model output) and plausible usage."""
    from ...suites.stage_a.generators import POOL
    pool = json.loads(POOL.read_text())["tasks"][:12]
    return {"choices": [{"message": {"content": json.dumps({"tasks": pool})}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens, "completion_tokens_details": {"reasoning_tokens": 1000}}}


def gate_rehearsal(S: dict) -> dict:
    """Zero cost: the REAL MetaClient and spend gate over an httpx MockTransport (no network), with this experiment's caps, request bodies and loop."""
    import httpx
    from ...agent import ModelConfig
    from ...investigate.llm.meta import INPUT_OVERHEAD_TOKENS, MetaClient
    from ...ledger import Ledger
    from ...spend_gate import RequestGate
    from ...suites.stage_a import loop as LP
    from ...research.taskplan.planner_v2 import MetaGenerator
    out = {}
    site, view = get(S["site"]), K.view(get(S["site"]))
    with tempfile.TemporaryDirectory() as d:
        ledger_dir = Path(d) / "ledger"
        calls = []

        def handler(req: httpx.Request):
            entries = Ledger(ledger_dir, S["cap_usd"]).entries()
            calls.append({"reserved_before_send": sum(e["kind"] == "reserve" for e in entries) == len(calls) + 1, "body": json.loads(req.content)})
            return httpx.Response(200, json=_fake_response(None))

        def client(transport):
            ledger = Ledger(ledger_dir, S["cap_usd"])
            gate = RequestGate(ledger, RUN_ID, run_cap=S["cap_usd"], per_request_cap=S["per_request_cap_usd"], max_requests=S["max_requests"], input_overhead_tokens=INPUT_OVERHEAD_TOKENS)
            return MetaClient(ModelConfig(), "rehearsal-key-not-real", gate, transport=transport)
        gen = MetaGenerator(ledger_dir, approval_note="ZERO-COST GATE REHEARSAL", run_cap_usd=S["cap_usd"], max_requests=S["max_requests"],
                            per_request_cap_usd=S["per_request_cap_usd"], run_id=RUN_ID, client=client(httpx.MockTransport(handler)))
        res = LP.run(site, view, X.CONTEXT, gen, config=_loop_config(S), created_at="2026-11-02T00:00:00+00:00")
        entries = Ledger(ledger_dir, S["cap_usd"]).entries()
        body = calls[0]["body"] if calls else {}
        out["requests_sent"] = len(calls)
        out["reserved_before_every_send"] = all(c["reserved_before_send"] for c in calls)
        out["settled"] = sum(e["kind"] == "settle" for e in entries)
        out["committed_usd"] = Ledger(ledger_dir, S["cap_usd"]).committed()
        out["body_settings"] = {"model": body.get("model"), "reasoning_effort": body.get("reasoning_effort"), "max_completion_tokens": body.get("max_completion_tokens"),
                                "strict_schema": ((body.get("response_format") or {}).get("json_schema") or {}).get("strict")}
        out["loop_stop"] = res["summary"]["stop_reason"]
        out["reservations_usd"] = [e["usd"] for e in entries if e["kind"] == "reserve"]
        # after a "restart" (a new client on the same ledger): the request-count cap and committed spend persist
        restarted = client(httpx.MockTransport(handler))
        req = PV2.build_request(view, X.CONTEXT, S["proposals_per_round"], max_tokens=S["max_completion_tokens"])
        sent_before = len(calls)
        for _ in range(S["max_requests"] + 1 - out["requests_sent"]):
            try:
                restarted.complete(req)
            except Exception as exc:
                out["after_restart"] = f"{type(exc).__name__}: {str(exc)[:160]}"
                break
        out["requests_after_restart_total"] = len(calls)
        out["restart_cannot_exceed_max_requests"] = len(calls) <= S["max_requests"] and "after_restart" in out
        out["restart_sent"] = len(calls) - sent_before
    with tempfile.TemporaryDirectory() as d:                                  # a provider error keeps the FULL reservation and is never retried
        n = []
        ledger = Ledger(Path(d), S["cap_usd"])
        gate = RequestGate(ledger, RUN_ID, run_cap=S["cap_usd"], per_request_cap=S["per_request_cap_usd"], max_requests=S["max_requests"], input_overhead_tokens=INPUT_OVERHEAD_TOKENS)
        c = MetaClient(ModelConfig(), "rehearsal-key-not-real", gate, transport=httpx.MockTransport(lambda r: (n.append(1), httpx.Response(400, json={"error": {"type": "invalid_request_error", "message": "schema rejected (rehearsal)"}}))[1]))
        try:
            c.complete(PV2.build_request(view, X.CONTEXT, S["proposals_per_round"], max_tokens=S["max_completion_tokens"]))
        except Exception as exc:
            out["http_400"] = f"{type(exc).__name__}: {str(exc)[:200]}"
        out["http_400_sends"] = len(n)
        out["http_400_kept_full_reservation"] = ledger.committed() == next(e["usd"] for e in ledger.entries() if e["kind"] == "reserve")
    out["ok"] = (out["requests_sent"] <= S["max_requests"] and out["reserved_before_every_send"] and out["settled"] == out["requests_sent"]
                 and out["committed_usd"] <= S["cap_usd"] and out["restart_cannot_exceed_max_requests"] and out["http_400_sends"] == 1 and out["http_400_kept_full_reservation"]
                 and out["body_settings"] == {"model": S["model"], "reasoning_effort": S["reasoning_effort"], "max_completion_tokens": S["max_completion_tokens"], "strict_schema": True})
    return out


def preflight(S: dict = SETTINGS, *, ledger_dir: Path = LEDGER_DIR) -> dict:
    """Every safety condition; the experiment refuses to send anything unless all pass. Zero cost (no network)."""
    from ...agent import ModelConfig
    from ...capture import PRICE_INPUT_PER_M, PRICE_OUTPUT_PER_M
    from ...investigate.llm.meta import DEFAULT_REASONING_EFFORT, reservation_bound_usd
    from ...ledger import VERIFIED_PRICES, Ledger
    from ...suites import boundary as B
    from ...suites.stage_a import generators as G
    from ...suites.stage_a import loop as LP
    from ...research.taskplan.schema import PROVEN_KEYWORDS
    from ...research.taskplan.preflight import _keywords, _objects
    checks = {}
    cfg = ModelConfig()
    checks["model_settings"] = (cfg.model == S["model"] and DEFAULT_REASONING_EFFORT == S["reasoning_effort"] and cfg.base_url.startswith("https://"),
                                {"model": cfg.model, "reasoning_effort": DEFAULT_REASONING_EFFORT, "endpoint_https": cfg.base_url.startswith("https://")})
    checks["prices_verified"] = ((PRICE_INPUT_PER_M, PRICE_OUTPUT_PER_M) == VERIFIED_PRICES, {"usd_per_m_input_output": [PRICE_INPUT_PER_M, PRICE_OUTPUT_PER_M]})
    import os
    from ...env import load_repo_env
    load_repo_env()
    checks["credential_present"] = (bool(os.environ.get(cfg.key_env)), {"env": cfg.key_env, "value": "never printed"})
    schema = json_schema_v3()
    extra = sorted(_keywords(schema) - PROVEN_KEYWORDS)
    lax = [p for p, o in _objects(schema) if set(o.get("required", [])) != set(o["properties"]) or o.get("additionalProperties") is not False]
    try:
        import jsonschema
        pool = json.loads(G.POOL.read_text())["tasks"]
        jsonschema.validate({"tasks": pool}, schema)
        parsed = all(parse_item_v3(t)[0] is not None for t in pool)
        wire = True
    except Exception as exc:
        wire, parsed = f"{type(exc).__name__}: {str(exc)[:200]}", False
    checks["schema_v3"] = (not extra and not lax and wire is True and parsed and PV2.PROMPT_VERSION == S["prompt_version"],
                           {"keywords_beyond_proven": extra, "non_strict_objects": lax, "pool_validates": wire, "pool_parses": parsed, "prompt": PV2.PROMPT_VERSION})
    site, view = get(S["site"]), K.view(get(S["site"]))
    gen = G.FeedbackFixture(["p04", "p05", "p08", "p09", "p18", "u01", "u02", "r01", "r02", "r03"], n=8)
    LP.run(site, view, X.CONTEXT, gen, config=_loop_config(S), created_at="2026-11-02T00:00:00+00:00")
    bounds = [reservation_bound_usd(r) for r in gen.calls]
    big_fb = {"round": 3, "note": "synthetic large feedback for the bound estimate", "rejections": {f"c{i}": {"count": 3, "wording_examples": ["x" * 380] * 2} for i in range(8)},
              "underspecified": [{"wording": "y" * 380, "unresolved": ["z" * 160] * 2}] * 8, "avoid_signatures": ["s" * 120] * 30}
    worst = reservation_bound_usd(PV2.build_request(view, X.CONTEXT, S["proposals_per_round"], feedback=big_fb, round_no=3, targets=_loop_config(S).as_dict()["targets"],
                                                    max_tokens=S["max_completion_tokens"]))
    checks["reservation_bounds"] = (max(bounds + [worst]) <= S["per_request_cap_usd"] and 3 * max(bounds) <= S["cap_usd"],
                                    {"rehearsed_round_bounds_usd": bounds, "large_feedback_bound_usd": worst, "per_request_cap_usd": S["per_request_cap_usd"],
                                     "three_rounds_worst_usd": round(3 * max(bounds), 6), "cap_usd": S["cap_usd"],
                                     "note": "the durable gate enforces the per-request cap, the 3-request cap and the US$0.10 run cap on every ACTUAL request regardless of these estimates"})
    existing = [e for e in Ledger(ledger_dir, S["cap_usd"]).entries()] if (Path(ledger_dir) / "ledger.jsonl").exists() else []
    checks["ledger_fresh"] = (not existing, {"ledger_dir": str(ledger_dir), "entries": len(existing)})
    checks["gate_rehearsal"] = (lambda r: (r["ok"], r))(gate_rehearsal(S))
    branch = subprocess.run(["git", "branch", "--show-current"], capture_output=True, text=True, cwd=ROOT).stdout.strip()
    checks["isolation"] = (branch == "research/llm-task-planning" and B.forbidden_imports(ROOT / "src/agent_readiness/suites") == [],
                           {"branch": branch, "stage_a_boundary": "clean" if not B.forbidden_imports(ROOT / "src/agent_readiness/suites") else "violations",
                            "writes": "scanner-data/research/stage-a only (git-ignored); store suite left UNAPPROVED"})
    return {"settings": S, "passed": all(ok for ok, _ in checks.values()), "checks": {k: {"ok": ok, "detail": d} for k, (ok, d) in checks.items()}}


def run(approval_note: str, S: dict = SETTINGS) -> dict:
    from ...ledger import Ledger
    from ...suites.stage_a import loop as LP
    from ...suites.store import WriteOnceStore
    from ...research.taskplan.planner_v2 import MetaGenerator
    pf = preflight(S)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = BASE / f"{RUN_ID}-{stamp}"
    BASE.mkdir(parents=True, exist_ok=True)
    (BASE / f"{RUN_ID}-{stamp}.preflight.json").write_text(json.dumps(pf, indent=1, default=str))
    if not pf["passed"]:
        raise PermissionError("preflight failed; NOTHING was sent: " + json.dumps({k: v for k, v in pf["checks"].items() if not v["ok"]}, default=str)[:600])
    site, view = get(S["site"]), K.view(get(S["site"]))
    gen = MetaGenerator(LEDGER_DIR, approval_note=approval_note, run_cap_usd=S["cap_usd"], max_requests=S["max_requests"], per_request_cap_usd=S["per_request_cap_usd"], run_id=RUN_ID)
    created = datetime.now(timezone.utc).isoformat(timespec="seconds")
    res = LP.run(site, view, X.CONTEXT, gen, config=_loop_config(S), created_at=created, out_dir=out_dir, store=WriteOnceStore(BASE / "store"), context_label=X.LABEL)
    led = Ledger(LEDGER_DIR, S["cap_usd"])
    entries = led.entries()
    reserved = {e["id"]: e["usd"] for e in entries if e["kind"] == "reserve"}
    settled = {e["id"]: e["usd"] for e in entries if e["kind"] == "settle"}
    doc = {"schema": "m6-stage-a-v1", "settings": S, "approval_note": approval_note, "created_at": created, "out_dir": str(out_dir), "suite_sha256": res["suite_sha256"],
           "suite_status": "UNAPPROVED proposal (approval and freezing are the owner's, at an interactive terminal)", "stop_reason": res["summary"]["stop_reason"],
           "cost": {"requests": len(reserved), "reserved_usd": round(sum(reserved.values()), 6), "settled_calculated_usd": round(sum(settled.values()), 6),
                    "committed_usd": led.committed(), "unsettled": sorted(set(reserved) - set(settled)),
                    "basis": "calculated from provider-reported usage at the published prices (US$1.25 / US$4.25 per M tokens); not a bill; an unsettled request counts its full reservation"},
           "ledger": entries, "rounds": [{k: v for k, v in r.items() if k not in ("response_text", "feedback_in", "feedback_out")} for r in res["summary"]["rounds"]]}
    (out_dir / "experiment.json").write_text(json.dumps(doc, indent=1, default=str))
    return doc


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="agent_readiness.suites.experiments.m6_stage_a")
    ap.add_argument("--preflight-only", action="store_true")
    ap.add_argument("--approval-note", default="")
    a = ap.parse_args(argv)
    if a.preflight_only:
        pf = preflight()
        print(json.dumps(pf, indent=1, default=str))
        return 0 if pf["passed"] else 1
    doc = run(a.approval_note)
    print(json.dumps({k: doc[k] for k in ("out_dir", "suite_sha256", "suite_status", "stop_reason", "cost", "rounds")}, indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
