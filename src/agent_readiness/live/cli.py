"""`readiness live smoke`: the operator's task-generation-only smoke test of the live path (US$0.15, at most 3 provider requests, no retries, stops before any browser trial).

  readiness live smoke --goal "..." --plan                        offline: print the exact approval manifest (hash, caps, request count); no key, no network
  readiness live smoke --goal "..." --confirm-spend 0.15          runs it for real (needs SCANNER_LIVE_ENABLED=1, SCANNER_LIVE_BUDGET_USD, the key, and the approval of this spend)

It uses the same job manager, grant, approver, spend gate, ledger and worker as the UI; the only difference is that the grant covers `taskgen` alone."""
from __future__ import annotations

import dataclasses
import json
import sys
import tempfile
import time
from pathlib import Path

COMMANDS = ("live",)


def register(sub) -> None:
    p = sub.add_parser("live", help="Live evaluation operator tools (task-generation-only smoke test)")
    ls = p.add_subparsers(dest="live_command", required=True)
    s = ls.add_parser("smoke", help="Task-generation-only smoke test: at most 3 requests, US$0.15, stops before browser trials")
    s.add_argument("--goal", required=True)
    s.add_argument("--context-file", type=Path, default=None, help="optional Website Context (a client briefing; max 2000 characters; unverified, never evidence)")
    s.add_argument("--plan", action="store_true", help="print the exact manifest and limits; no key, no network, no spend")
    s.add_argument("--confirm-spend", type=float, default=None, help="must equal the smoke cap (0.15): your explicit confirmation of the maximum spend")
    s.add_argument("--wait", type=int, default=600, help="seconds to wait for the job")
    f = ls.add_parser("run", help="ONE full live investigation of Ironbark (task generation, browser trials, investigator, recommendations) under a single user grant; hard cap US$2.00")
    f.add_argument("--goal", required=True)
    f.add_argument("--context-file", type=Path, default=None)
    f.add_argument("--plan", action="store_true", help="offline: print the task-generation manifest hash and the grant scope; no key, no network")
    f.add_argument("--confirm-spend", type=float, default=None, help="must equal the job cap (2.00)")
    f.add_argument("--wait", type=int, default=1800)


def plan(goal: str, context: str | None = None) -> dict:
    from ..agent import ModelConfig
    from ..investigate import flow
    from ..investigate.taskgen import propose
    from . import grant as G, worker
    from .lexicon import RENTAL
    from .targets import TARGETS
    target = TARGETS["ironbark"]
    with tempfile.TemporaryDirectory() as tmp:
        run, pipe, ctx = flow.build(Path(tmp), "smoke-plan", "ironbark", mode="live", options={"snapshot": target.snapshot(), "n_tasks": 4, "goals": {"focus": worker.sanitize_goal(goal)}, "rule_topup": False, "goal_binding": True, "goal_lexicon": RENTAL, "context": context,
                                                                                                   "model_config": ModelConfig(), "total_cap_usd": G.SMOKE_CAP_USD})
        res = pipe.run(ctx, until="inspect")
        if res.status != "done":
            raise SystemExit(f"plan failed: {res.status} {res.error}")
        m = flow.taskgen_manifest(ctx)
        return {"manifest_sha256": run.manifest_sha256(m), "stage": m["stage"], "model": m["model"], "endpoint": m["endpoint"], "max_provider_requests": m["max_requests"], "batches": m["batches"],
                "retries_per_request": m["retries_per_request"], "run_cap_usd": m["run_cap_usd"], "per_request_cap_usd": m["per_request_cap_usd"], "per_request_reservation_usd": m["per_request_reservation_usd"],
                "worst_case_stage_usd": m["worst_case_stage_usd"], "grant_budget_usd": G.SMOKE_CAP_USD, "snapshot_sha256": m["snapshot_sha256"], "goal": worker.sanitize_goal(goal), "client_context_sha256": m.get("client_context_sha256"),
                "stops_after": "taskgen and freeze; no browser trial, investigator or recommendation", "rule_topup": False}


def G_LIVE_STAGES():
    from .grant import LIVE_STAGES
    return LIVE_STAGES


def _context(args) -> str | None:
    from .jobs import clean_context
    return clean_context(args.context_file.read_text()) if getattr(args, "context_file", None) else None


def main(args) -> int:
    smoke = args.live_command == "smoke"
    if args.plan:
        out = plan(args.goal, _context(args))
        if not smoke:
            out = {**out, "full_run_scope": {"stages": list(G_LIVE_STAGES()), "grant_budget_usd": 2.0, "stage_caps_usd": {"taskgen": 0.15, "baseline_trials": 1.40, "investigate": 0.40}, "max_tasks": 4,
                                             "note": "baseline and investigate manifests depend on the tasks that are generated, so their hashes exist only at run time; they are approved only if they stay inside this grant"}}
        print(json.dumps(out, indent=2))
        return 0
    from ..scanner.service.config import load_config
    from .jobs import JobError, JobManager, LiveSettings
    from . import grant as G
    cfg = load_config()
    base = LiveSettings.from_config(cfg)
    settings = dataclasses.replace(base, smoke_until="taskgen") if smoke else dataclasses.replace(base, smoke_until="")
    cap = G.SMOKE_CAP_USD if smoke else settings.cap_usd
    if not settings.available():
        print("live smoke is not available: set SCANNER_LIVE_ENABLED=1, SCANNER_LIVE_BUDGET_USD (>= 0.15) and the model key in the environment or .env (a loopback endpoint also needs LIVE_ALLOW_DEV_PROVIDER=1)", file=sys.stderr)
        return 2
    if args.confirm_spend is None or abs(args.confirm_spend - cap) > 1e-9:
        print(f"refusing: pass --confirm-spend {cap:.2f} to confirm the maximum spend of this {'smoke test (at most 3 requests)' if smoke else 'full investigation'}", file=sys.stderr)
        return 2
    m = JobManager(cfg.live_root, live=settings, killed=lambda: cfg.kill_switch_path.exists())
    try:
        job = m.create("operator-cli", "ironbark", args.goal, "live", args.confirm_spend, _context(args))
    except JobError as exc:
        print(f"refused: {exc.message}", file=sys.stderr)
        return 2
    print(f"started {job['id']} ({'taskgen only' if smoke else 'full investigation'}, cap US${cap:.2f}, endpoint {settings.base_url})", file=sys.stderr)
    t0, last = time.time(), None
    while time.time() - t0 < args.wait:
        v = m.get(job["id"], "operator-cli")
        cur = (v["state"], v["spend"]["committed_usd"])
        if cur != last:
            print(f"  {v['state']}  spend US${v['spend']['committed_usd']:.4f}", file=sys.stderr)
            last = cur
        if v["state"] not in ("queued", "running"):
            break
        time.sleep(2)
    else:
        m.cancel(job["id"], "operator-cli")
        print("timed out; cancelled", file=sys.stderr)
        return 1
    print(json.dumps({"job": {k: v[k] for k in ("id", "state", "error", "stop", "spend", "stages", "trials")}, "smoke": v["smoke"], "client_context": v["client_context"]}, indent=2, default=str))
    return 0 if v["state"] == "completed" and (not smoke or (v["smoke"] and v["smoke"]["yield"]["meets_minimum"])) else 1
