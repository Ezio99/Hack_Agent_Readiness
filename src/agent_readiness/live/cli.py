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
    s.add_argument("--tasks-file", type=Path, default=None, help="optional operator-authored tasks (JSON; labelled OWNER-AUTHORED; bound into the grant); `model_tasks: false` makes task generation request nothing")
    s.add_argument("--plan", action="store_true", help="print the exact manifest and limits; no key, no network, no spend")
    s.add_argument("--confirm-spend", type=float, default=None, help="must equal the smoke cap (0.15): your explicit confirmation of the maximum spend")
    s.add_argument("--wait", type=int, default=600, help="seconds to wait for the job")
    register_replay(ls)
    ab = ls.add_parser("ab-experiment", help="Controlled Ironbark before/after (EXP-C): fork the finished live run, record the ONE owner-selected three-field listing proposal, and present the apply_fix then post_trials manifests. Free by default")
    ab.add_argument("--id", required=True, help="id of the new fork run (a directory name under --root)")
    ab.add_argument("--root", type=Path, default=Path("scanner-data/live"))
    ab.add_argument("--source", type=Path, default=None, help="the finished live run to fork (default: the pre-registered source)")
    ab.add_argument("--approve-hash", action="append", default=[], help="exact manifest hash to approve (repeatable: apply_fix, then post_trials)")
    ab.add_argument("--allow-model-calls", action="store_true", help="REQUIRED for the post_trials hash: this is the only paid stage (real model, hard caps in its manifest)")
    f = ls.add_parser("run", help="ONE full live investigation of Ironbark (task generation, browser trials, investigator, recommendations) under a single user grant; hard cap US$2.00")
    f.add_argument("--goal", required=True)
    f.add_argument("--context-file", type=Path, default=None)
    f.add_argument("--tasks-file", type=Path, default=None, help="optional operator-authored tasks (JSON; labelled OWNER-AUTHORED; bound into the grant); `model_tasks: false` makes task generation request nothing")
    f.add_argument("--plan", action="store_true", help="offline: print the task-generation manifest hash and the grant scope; no key, no network")
    f.add_argument("--confirm-spend", type=float, default=None, help="must equal the job cap (2.00)")
    f.add_argument("--wait", type=int, default=1800)


def register_replay(ls) -> None:
    r = ls.add_parser("replay-investigator", help="Re-run ONLY the investigator (and the free stages after it) against the immutable frozen tasks and baseline trials of a finished live run: a fork, no task generation, no browser trial")
    r.add_argument("source", type=Path, help="the finished live run directory, e.g. scanner-data/live/live-2d58a80e14 (only read)")
    r.add_argument("--id", required=True, help="id of the new fork run")
    r.add_argument("--root", type=Path, default=None, help="where the fork is created (default: the live root next to the source)")
    r.add_argument("--max-calls", type=int, default=12)
    r.add_argument("--approve-hash", default=None, help="the investigator manifest hash printed by the plan, to approve and RUN it (needs --allow-model-calls; paid)")
    r.add_argument("--allow-model-calls", action="store_true")
    r.add_argument("--export", type=Path, default=None, help="write the dashboard export of the finished fork here")


def replay_investigator(args) -> int:
    """Free plan by default: fork the source run, re-derive the free stages, print the investigator manifest and hash. With --approve-hash + --allow-model-calls: record the operator's approval of exactly that
    manifest and run the investigator and everything after it. The ceiling is the imported spend plus the investigator stage cap, so the replay can add at most that stage cap."""
    from ..agent import ModelConfig
    from ..investigate import allocation as alloc, flow
    from ..investigate.fork import fork
    from ..investigate.run import InvestigationRun
    from ..ledger import Halt
    from .jobs import CONTEXT_LABEL, augment_export
    from .targets import TARGETS
    from . import worker
    src = InvestigationRun(Path(args.source))
    root = Path(args.root) if args.root else Path(args.source).parent
    grant = src.artifact("live-grant")
    context = src.artifact("client-context")["text"] if src.has_artifact("client-context") else None
    target = TARGETS[src.state["target"]]
    if target.snapshot().sha256 != grant["snapshot_sha256"]:
        raise SystemExit("refusing: the registered site no longer matches the source run's captured snapshot")
    new_dir = Path(root) / args.id
    if not new_dir.exists():
        fork(src.dir, root, args.id)
    imported = json.loads((new_dir / "fork.json").read_text())["source_ledger"]["committed_usd"]
    ceiling = round(int((imported + alloc.INVESTIGATE_CAP_USD) * 100) / 100 + 0.01, 2)                       # imported spend + the investigator stage cap, rounded up to the cent
    opts = worker.live_options(target.snapshot(), grant["goal"], context, budget=ceiling, cfg=ModelConfig(model=grant["model"], base_url=grant["endpoint"]), target=target)
    opts.update({"max_calls": args.max_calls, "allow_model_calls": bool(args.approve_hash and args.allow_model_calls)})
    if opts["allow_model_calls"]:
        from ..env import load_repo_env
        load_repo_env()
    try:
        run, pipe, ctx = flow.build(root, args.id, src.state["target"], mode="live", options=opts)
        res = pipe.run(ctx)
        if res.status == "awaiting_approval" and res.stage == "investigate":
            manifest = run.artifact(f"manifests/investigate-{res.manifest_sha256[:16]}")
            if args.approve_hash:
                if args.approve_hash != res.manifest_sha256:
                    raise SystemExit(f"refusing: the manifest hash is {res.manifest_sha256}, not the one you approved")
                if not args.allow_model_calls:
                    raise SystemExit("refusing: --allow-model-calls is required to run the approved investigator")
                run.approve("investigate", res.manifest_sha256, f"OPERATOR replay approval of exactly this investigator manifest for fork {args.id} of {src.state['id']} (no taskgen, no browser trial)")
                res = pipe.run(ctx)
            else:
                print(json.dumps({"fork": str(run.dir), "source_run": src.state["id"], "stage": "investigate", "manifest_sha256": res.manifest_sha256, "model": manifest["model"], "endpoint": manifest["endpoint"],
                                  "run_cap_usd": manifest["run_cap_usd"], "per_request_cap_usd": manifest["per_request_cap_usd"], "max_tool_calls": manifest.get("max_tool_calls"), "retries_per_request": manifest["retries_per_request"],
                                  "imported_spend_usd": imported, "ledger_ceiling_usd": ceiling, "maximum_new_spend_usd": round(ceiling - imported, 6), "forked_from": manifest.get("forked_from", {}).get("source_run"),
                                  "paid_stages_rerun": False, "goal": grant["goal"], "owner_tasks": "tasks come from the imported frozen task set", "context_label": CONTEXT_LABEL if context else None}, indent=2))
                return 0
    except Halt as exc:
        raise SystemExit(f"refused: {exc}")
    print(f"{run.state['id']}: {res.status}" + (f" at {res.stage}" if res.stage else "") + (f": {res.error}" if getattr(res, "error", None) else ""))
    if res.status == "done" and args.export:
        from ..investigate import export as exporter
        data = exporter.export_run(run.dir)
        exporter.check_clean(data)
        augment_export(run, data, grant["goal"], context, grant["context_sha256"] or None)
        data["notices"] = ["INVESTIGATOR REPLAY: the frozen tasks and baseline trials of the source run were imported unchanged (see fork provenance); only the investigator and later free stages were re-run.", *data.get("notices", [])]
        args.export.write_text(json.dumps(data))
        print(f"export written: {args.export}")
    return 0 if res.status == "done" else 1


def plan(goal: str, context: str | None = None, smoke: bool = False, owner_tasks: dict | None = None) -> dict:
    """The approval manifest of the task-generation stage EXACTLY as the worker will present it: same options (`worker.live_options`), same model/endpoint (the server configuration) and the same ledger
    ceiling (the smoke cap for a smoke job, else the job cap), so the printed hash is the hash of the real run."""
    from ..agent import ModelConfig
    from ..investigate import flow
    from ..scanner.service.config import load_config
    from . import grant as G, worker
    from .jobs import LiveSettings
    from .targets import TARGETS
    settings = LiveSettings.from_config(load_config())
    budget = G.SMOKE_CAP_USD if smoke else settings.cap_usd
    target = TARGETS["ironbark"]
    with tempfile.TemporaryDirectory() as tmp:
        opts = worker.live_options(target.snapshot(), goal, context, budget=budget, cfg=ModelConfig(model=settings.model, base_url=settings.base_url), owner_tasks=owner_tasks)
        run, pipe, ctx = flow.build(Path(tmp), "plan", "ironbark", mode="live", options=opts)
        res = pipe.run(ctx, until="inspect")
        if res.status != "done":
            raise SystemExit(f"plan failed: {res.status} {res.error}")
        m = flow.taskgen_manifest(ctx)
        out = {"manifest_sha256": run.manifest_sha256(m), "stage": m["stage"], "model": m["model"], "endpoint": m["endpoint"], "max_provider_requests": m["max_requests"], "batches": m["batches"],
               "retries_per_request": m["retries_per_request"], "run_cap_usd": m["run_cap_usd"], "per_request_cap_usd": m["per_request_cap_usd"], "per_request_reservation_usd": m["per_request_reservation_usd"],
               "worst_case_stage_usd": m["worst_case_stage_usd"], "grant_budget_usd": budget, "ledger_ceiling_usd": m["allocation"]["ledger_ceiling_usd"], "snapshot_sha256": m["snapshot_sha256"], "goal": worker.sanitize_goal(goal),
               "client_context_sha256": m.get("client_context_sha256"), "owner_tasks_sha256": m.get("owner_tasks_sha256"), "rule_topup": False}
        if smoke:
            return {**out, "stops_after": "taskgen and freeze; no browser trial, investigator or recommendation"}
        lim = G.default_limits()
        return {**out, "full_run_scope": {"stages": list(G.LIVE_STAGES), "grant_budget_usd": budget, "stage_caps_usd": lim["stage_caps_usd"], "allocated_usd": m["allocation"]["allocated_usd"], "max_tasks": lim["max_tasks"],
                                           "repeats": lim["repeats"], "per_request_cap_usd": lim["per_request_cap_usd"], "max_retries_per_request": lim["max_retries_per_request"],
                                           "note": "baseline and investigate manifests depend on the tasks that are generated, so their hashes exist only at run time; they are approved only if they stay inside this grant"}}


def _context(args) -> str | None:
    from .jobs import clean_context
    return clean_context(args.context_file.read_text()) if getattr(args, "context_file", None) else None


def _owner_tasks(args):
    from .jobs import clean_owner_tasks
    import json as _json
    return clean_owner_tasks(_json.loads(args.tasks_file.read_text())) if getattr(args, "tasks_file", None) else None


def ab_experiment(args) -> int:
    from ..agent import ModelConfig
    from . import abtest
    from .targets import TARGETS
    out = abtest.drive(args.source or abtest.SOURCE, args.root, args.id, cfg=ModelConfig(), snapshot=TARGETS["ironbark"].snapshot(), approve=frozenset(args.approve_hash), allow_model_calls=args.allow_model_calls)
    manifest = out.pop("manifest", None)
    print(json.dumps(out, indent=2))
    if manifest is not None:
        print(f"manifest: {Path(out['fork']) / 'artifacts' / 'manifests'}/{out['stage']}-{out['manifest_sha256'][:16]}.json")
    return 0 if out["status"] in ("awaiting_approval", "done") else 1


def main(args) -> int:
    if args.live_command == "replay-investigator":
        return replay_investigator(args)
    if args.live_command == "ab-experiment":
        return ab_experiment(args)
    smoke = args.live_command == "smoke"
    if args.plan:
        out = plan(args.goal, _context(args), smoke, _owner_tasks(args))
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
        job = m.create("operator-cli", "ironbark", args.goal, "live", args.confirm_spend, _context(args), _owner_tasks(args))
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
