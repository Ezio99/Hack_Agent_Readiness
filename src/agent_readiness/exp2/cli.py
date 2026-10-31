"""`readiness exp2 ...`: credential-free planning, assessment and the (approval-gated) Experiment-2 baseline driver. Nothing here spends money unless a live run is explicitly approved per phase."""
from __future__ import annotations

import json
from pathlib import Path

COMMANDS = ("exp2",)
DEFAULT_ROOT = Path("investigations")


def register(sub) -> None:
    e = sub.add_parser("exp2", help="Experiment 2 on the fictional Ironbark Hire Co. site: assess, pool, plan, run (mock/live, approval-gated), rules")
    s = e.add_subparsers(dest="exp2_command", required=True)
    a = s.add_parser("assess", help="Credential-free integration assessment of a site variant (snapshot fidelity, assets, links, determinism)")
    a.add_argument("--variant", default="control")
    p = s.add_parser("pool", help="Generate and verify the candidate task pool; print the summary (no answers)")
    p.add_argument("--out", type=Path)
    pl = s.add_parser("plan", help="Build the balanced baseline study plan, cost model and allocation (no answers)")
    pl.add_argument("--out", type=Path)
    r = s.add_parser("run", help="Run the baseline pipeline in its own run directory (mock never spends; live stops at each approval gate)")
    r.add_argument("run_id")
    r.add_argument("--mode", choices=["mock", "live"], default="mock")
    r.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    r.add_argument("--allow-model-calls", action="store_true", help="Live only, and only after the owner approved the exact manifest of the stage being run")
    r.add_argument("--until", help="stop after this stage")
    st = s.add_parser("status", help="Stage statuses and committed spend of a run")
    st.add_argument("run_id")
    st.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    s.add_parser("rules", help="Print the pre-registered eligibility and comparison rules and their hash")
    v = s.add_parser("views", help="Check (default) or re-capture (--write, needs Chromium) the model-visible text of every page of every arm that evidence criteria are verified against")
    v.add_argument("--write", action="store_true")
    am = s.add_parser("amend", help="Adopt the revised plan and corrected private criteria as NEW artifacts next to the frozen ones of a run (executed pilot, snapshot and kept tasks' truths must be unchanged). Free; no model call")
    am.add_argument("run_id")
    am.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    ra = s.add_parser("reanalyse", help="Read-only corrected re-analysis of a finished run beside its original outcomes (no model call, the run is not modified)")
    ra.add_argument("run_id")
    ra.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    ra.add_argument("--out", type=Path, required=True)


def main(args) -> None:
    from . import analysis, flow, pool as P, snapshot as S, study
    cmd = args.exp2_command
    if cmd == "assess":
        r = S.assess(args.variant)
        print(json.dumps({k: v for k, v in r.items() if k != "problems"} | {"problems": r["problems"][:10]}, indent=2))
        raise SystemExit(0 if r["ok"] else 1)
    if cmd == "pool":
        report, cands = P.build_pool()
        out = P.summary(report, cands)
        text = json.dumps(out, indent=2)
        if args.out:
            args.out.write_text(text + "\n"); print(f"wrote {args.out}")
        else:
            print(text)
    elif cmd == "plan":
        report, _ = P.build_pool()
        plan = study.build_plan(report.accepted, executed=study.EXECUTED_PILOT)
        text = json.dumps(plan, indent=2)
        if args.out:
            args.out.write_text(text + "\n"); print(f"wrote {args.out}  plan_sha256={plan['plan_sha256']}")
        else:
            print(json.dumps({k: plan[k] for k in ("counts", "allocation", "warnings", "plan_sha256")} | {"phases": {k: v["cost"] for k, v in plan["phases"].items()}}
                             | {"variant_tests": {v: {"trials": x["trial_count"], "repeats": x["repeats"], "expected_usd": x["cost"]["p50_usd"], "cap_usd": x["cost"]["cap_usd"]} for v, x in plan["variant_tests"].items()}}, indent=2))
    elif cmd == "rules":
        print(json.dumps({"eligibility": analysis.ELIGIBILITY, "compare": analysis.COMPARE, "rules_sha256": analysis.RULES_SHA256}, indent=2))
    elif cmd == "views":
        from . import modelview
        if args.write:
            import asyncio
            print("raw sha256", modelview.write(asyncio.run(modelview.capture_all())))
        stale = modelview.stale()
        print(json.dumps({"stale": stale, "views_sha256": modelview.views_sha256()}, indent=2))
        raise SystemExit(1 if stale else 0)
    elif cmd == "amend":
        from ..investigate.run import InvestigationRun
        print(json.dumps(flow.amend(InvestigationRun(args.root / args.run_id)), indent=2))
    elif cmd == "reanalyse":
        from . import reanalysis
        out = reanalysis.reanalyse(args.root / args.run_id)
        args.out.write_text(json.dumps(out, indent=2) + "\n")
        print(f"wrote {args.out}  unchanged_original={out['integrity']['unchanged']}  {out['summary']['original']} -> {out['summary']['corrected']}")
    elif cmd == "status":
        from ..investigate.run import InvestigationRun
        run = InvestigationRun(args.root / args.run_id)
        print(json.dumps({"mode": run.mode, "stages": {s: v["status"] for s, v in run.state["stages"].items()}, "committed_usd": run.ledger(20.0).committed(), "ceiling_usd": 20.0}, indent=2))
    else:
        from ..agent import ModelConfig
        from ..env import load_repo_env
        if args.mode == "live":
            load_repo_env()                      # makes the key available to the process; it is only READ after the stage manifest is approved and `--allow-model-calls` is given
        run, pipe, ctx = flow.build(args.root, args.run_id, mode=args.mode, options={"allow_model_calls": args.allow_model_calls, "model_config": ModelConfig()})
        res = pipe.run(ctx, until=args.until)
        print(f"{args.run_id}: {res.status}" + (f" at {res.stage}" if res.stage else ""))
        if res.status == "awaiting_approval":
            print(f"stage {res.stage} needs the owner's approval of manifest sha256 {res.manifest_sha256}\n  readiness investigate approve {args.root / args.run_id} --stage {res.stage} --sha256 {res.manifest_sha256} --note '<who approved what>'")
        if res.error:
            print(res.error)
