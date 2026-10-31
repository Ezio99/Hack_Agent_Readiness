"""Experiment-2 driver for the baseline on Ironbark, built on the existing investigation machinery (durable run directory, write-once artifacts, approvals bound to the SHA-256 of an exact
manifest, a fsync'd reserve-before-send ledger with its OWN US$20 ceiling, void/quarantine handling, no automatic retries).

  inspect -> pool -> freeze -> baseline_pilot [paid, approval] -> pilot_review [approval] -> baseline_main [paid, approval] -> baseline_report

Nothing paid runs in `mock` mode (scripted agent through the real browser, no key, no network). In `live` mode each paid stage stops at `awaiting_approval` until the owner approves ITS exact manifest;
`pilot_review` is a free checkpoint where the measured cost per request replaces the planning assumption and the main phase is trimmed to fit its cap. This module never touches EXP-B."""
from __future__ import annotations

from collections import Counter
from pathlib import Path

from ..agent import ModelConfig
from ..investigate.inspect.stage import load_snapshot, run_inspect
from ..investigate.pipeline import Context, Pipeline, Stage
from ..investigate.run import InvestigationRun
from ..investigate.trials.stage import VOID_STATUSES, run_plan
from ..ledger import Halt
from ..suite.core import canonical_hash
from . import costs
from .instances import instance, private_record
from .pool import build_pool, facts_invariance, summary
from .snapshot import assess, snapshot
from .analysis import RULES_SHA256
from .study import PILOT_TRIALS, QUOTAS, REPEAT_TASKS, build_plan
from ..sites.ironbark import variants as V

STAGES = ("inspect", "pool", "freeze", "baseline_pilot", "pilot_review", "baseline_main", "baseline_report")
STOPPING_CONDITIONS = [
    "any void trial (provider, budget, infrastructure, fidelity guard) stops the phase; it is never retried automatically",
    "any single request whose upper bound exceeds the per-request cap is refused; any trial that would exceed the per-trial cap is stopped",
    "the phase cap or the Experiment-2 ledger ceiling would be exceeded: the spend gate refuses and the phase stops (no top-up)",
    "a bound violation (settled cost above the reservation) closes the gate for good until the owner reviews it",
    "an integrity failure (snapshot, plan, task or criteria hash differs from the approved one) quarantines the trial and stops the phase",
    "measured cost per request above 1.5x the planning rate at the pilot review means the main phase is re-planned, not run as approved",
]


def _opts(ctx: Context) -> dict:
    return ctx.options


def _plan_args(ctx: Context) -> dict:
    o = _opts(ctx)
    return {"seed": o.get("seed", 0), "quotas": o.get("quotas", QUOTAS), "pilot_trials": o.get("pilot_trials", PILOT_TRIALS), "repeat_tasks": o.get("repeat_tasks", REPEAT_TASKS)}


def inspect_stage(ctx: Context) -> dict:
    a = assess(V.CONTROL)
    if not a["ok"]:
        raise ValueError(f"integration assessment failed: {a['problems'][:3]}")
    out = run_inspect(ctx, snapshot(V.CONTROL))
    inv = {v.name: facts_invariance(v) for v in V.all_single()[1:]}
    ctx.run.write_artifact("integration-assessment", {"control": a, "variant_fact_invariance": inv})
    if any(inv.values()):
        raise ValueError(f"a variant changes facts, not just access: {inv}")
    return out


def pool_stage(ctx: Context) -> dict:
    report, cands = build_pool()
    ctx.run.write_artifact("task-pool", summary(report, cands))
    ctx.run.write_artifact("task-pool-rejections", report.rejected)
    return {"generated": len(cands), "accepted": len(report.accepted), "rejected": len(report.rejected)}


def freeze_stage(ctx: Context) -> dict:
    report, _ = build_pool()
    a = _plan_args(ctx)
    plan = build_plan(report.accepted, seed=a["seed"], quotas=a["quotas"], pilot_trials=a["pilot_trials"], repeat_tasks=a["repeat_tasks"])
    snap = load_snapshot(ctx.run)
    plan["snapshot_sha256"] = snap.sha256
    plan["plan_sha256"] = canonical_hash({k: v for k, v in plan.items() if k != "plan_sha256"})
    by_id = {c.task_id: c for c in report.accepted}
    ctx.run.write_private("criteria", {t["task_id"]: private_record(by_id[t["task_id"]]) for t in plan["tasks"]})
    ctx.run.write_artifact("study-plan", plan)
    return {"tasks": plan["counts"]["tasks"], "trials": plan["counts"]["trials"], "plan_sha256": plan["plan_sha256"]}


def _load(ctx: Context):
    run = ctx.run
    plan, priv, snap = run.artifact("study-plan"), run.private("criteria"), load_snapshot(run)
    if snap.sha256 != plan["snapshot_sha256"]:
        raise Halt("the snapshot is not the one the plan was frozen against")
    return plan, priv, snap


def _phase_trials(ctx: Context, phase: str) -> list[dict]:
    plan = ctx.run.artifact("study-plan")
    return plan["phases"]["baseline_pilot"]["trials"] if phase == "baseline_pilot" else ctx.run.artifact("main-plan")["trials"]


def _phase_cap(ctx: Context, phase: str) -> float:
    plan = ctx.run.artifact("study-plan")
    return plan["phases"]["baseline_pilot"]["cost"]["cap_usd"] if phase == "baseline_pilot" else ctx.run.artifact("main-plan")["cap_usd"]


def manifest(ctx: Context, phase: str) -> dict:
    plan = ctx.run.artifact("study-plan")
    cfg = _opts(ctx).get("model_config") or ModelConfig()
    trials = _phase_trials(ctx, phase)
    extra = {"main_plan_sha256": canonical_hash(ctx.run.artifact("main-plan"))} if phase == "baseline_main" else {}
    cost = plan["phases"]["baseline_pilot"]["cost"] if phase == "baseline_pilot" else ctx.run.artifact("main-plan")["cost"]
    return {"stage": phase, "experiment": "EXP-2 Ironbark baseline", "site_variant": "control", "snapshot_sha256": plan["snapshot_sha256"], "plan_sha256": plan["plan_sha256"],
            "trials": [f"{t['task_id']}-r{t['repeat']}" for t in trials], "trial_count": len(trials), "trial_order_sha256": canonical_hash(trials), "model": cfg.model, "endpoint": cfg.base_url,
            "agent_profile": "suite-v2-compat1", "phase_cap_usd": _phase_cap(ctx, phase), "expected_phase_cost_usd": cost["p50_usd"], "per_trial_cap_usd": costs.PER_TRIAL_CAP_USD,
            "per_request_cap_usd": costs.PER_REQUEST_CAP_USD, "max_requests_per_trial": costs.MAX_STEPS, "retries": 0, "ledger": "this experiment's own ledger (investigations/<run>/spend), never EXP-B's",
            "ledger_ceiling_usd": costs.CEILING_USD, "reserve_usd": costs.RESERVE_USD, "allocation": plan["allocation"], "stopping_conditions": STOPPING_CONDITIONS, "evidence_rule": EVIDENCE_RULE, "rules_sha256": RULES_SHA256,
            "cost_basis": "calculated at published prices; planning assumptions in exp2/costs.py; not a bill", **extra}


def _steps(ctx: Context, trials: list[dict], cap: float) -> list[dict]:
    plan, priv, snap = _load(ctx)
    tasks = {t["task_id"]: t for t in plan["tasks"]}
    insts = {tid: instance(tasks[tid], priv[tid], snap.sha256[:12], mock=ctx.run.mode == "mock") for tid in tasks}
    scope = frozenset(f"baseline-{t['task_id']}-r{t['repeat']}" for t in trials)
    return [{"label": "baseline", "prefix": "baseline", "snap": snap, "inst": insts[t["task_id"]], "task": {"task_id": t["task_id"], "partition": tasks[t["task_id"]]["partition"]}, "repeat": t["repeat"],
             "scopes": [(scope, cap, "stage")]} for t in trials]


def _run_phase(ctx: Context, phase: str) -> dict:
    m = manifest(ctx, phase)
    gm = {"ledger_ceiling_usd": costs.CEILING_USD, "run_cap_usd": costs.PER_TRIAL_CAP_USD, "per_request_cap_usd": costs.PER_REQUEST_CAP_USD, "max_requests_per_trial": costs.MAX_STEPS}
    out = run_plan(ctx, _steps(ctx, _phase_trials(ctx, phase), m["phase_cap_usd"]), manifest_=gm)
    return {"trials": out["trials"], "void": out["void"], "manifest_sha256": canonical_hash(m)}


EVIDENCE_RULE = ("evidence sufficiency is assessed from what the model was SHOWN (exp2/evidence.py): the facts an answer depends on must appear on some page, by any route; no particular page is required, "
                 "the rule is identical in every arm, and it is reported separately from correctness and from browsing efficiency")


def annotate(run: InvestigationRun) -> dict[str, dict]:
    """Evidence-sufficiency assessment per recorded trial, from the private task facts and the observations the trial stored."""
    import json
    from . import evidence as E
    priv = run.private("criteria")
    out = {}
    for rec in trial_records(run):
        f = run.dir / rec["trial_dir"] / "observations.json"
        obs = json.loads(f.read_text()) if f.exists() else None
        out[rec["trial_id"]] = E.assess(E.from_json(priv[rec["task_id"]]["facts"]), obs) if obs is not None else {"sufficient": False, "missing": ["observations unavailable"], "facts": 0, "pages_seen": 0}
    return out


def trial_records(run: InvestigationRun) -> list[dict]:
    d = run.dir / "artifacts" / "trials"
    return [run.artifact(f"trials/{p.stem}") for p in sorted(d.glob("baseline-*.json"))] if d.exists() else []


def measured_rate(records: list[dict]) -> dict | None:
    """Calculated cost per model request over the pilot's NON-void trials (the planning assumption is replaced by this)."""
    rows = [(r["metrics"]["calculated_cost_usd"], r["metrics"]["model_requests"]) for r in records if r["outcome"]["run_status"] not in VOID_STATUSES and r["metrics"]["model_requests"]]
    if not rows:
        return None
    per = sorted(c / n for c, n in rows)
    return {"trials": len(rows), "p50": round(per[len(per) // 2], 5), "p90": round(per[min(len(per) - 1, int(len(per) * 0.9))], 5), "total_usd": round(sum(c for c, _ in rows), 4), "requests": sum(n for _, n in rows)}


def review_manifest(ctx: Context) -> dict:
    """The checkpoint the owner approves before ANY main-phase spending: what the pilot measured and exactly which trials the main phase would run, trimmed to fit its cap at the measured rate."""
    run, plan = ctx.run, ctx.run.artifact("study-plan")
    recs = trial_records(run)
    rate = measured_rate(recs)
    main = plan["phases"]["baseline_main"]["trials"]
    pages = {t["task_id"]: t["pages_needed"] for t in plan["tasks"]}
    per = (rate["p50"], max(rate["p90"], rate["p50"] * 1.4)) if rate and ctx.run.mode == "live" else (costs.USD_PER_REQUEST_P50, costs.USD_PER_REQUEST_P90)
    n = costs.trim_to_cap([pages[t["task_id"]] for t in main], plan["phases"]["baseline_main"]["cost"]["cap_usd"], per)
    kept = main[:n]
    cost = costs.phase_cost([pages[t["task_id"]] for t in kept], per_request=per)
    committed = round(run.ledger(costs.CEILING_USD).committed(), 6)
    return {"stage": "pilot_review", "plan_sha256": plan["plan_sha256"], "pilot_trials_done": len(recs), "pilot_statuses": dict(Counter(r["outcome"]["run_status"] for r in recs)),
            "pilot_passed": sum(bool(r["evaluation"]["passed"]) for r in recs), "measured_rate_usd_per_request": rate, "planning_rate_usd_per_request": [costs.USD_PER_REQUEST_P50, costs.USD_PER_REQUEST_P90],
            "rate_ratio_to_plan": round(rate["p50"] / costs.USD_PER_REQUEST_P50, 3) if rate else None, "committed_usd": committed, "main_trials_planned": len(main), "main_trials_proposed": len(kept),
            "dropped_trials": [f"{t['task_id']}-r{t['repeat']}" for t in main[n:]], "proposed_cap_usd": cost.cap_usd, "proposed_expected_usd": cost.p50_usd,
            "replan_required": bool(rate and rate["p50"] > 1.5 * costs.USD_PER_REQUEST_P50), "note": "approving this fixes the main-phase trial list; baseline_main then needs its own manifest approval"}


def review_stage(ctx: Context) -> dict:
    m = review_manifest(ctx)
    if m["replan_required"]:
        raise Halt("the measured cost per request is more than 1.5x the planning rate; the main phase must be re-planned by the owner, not run as approved")
    plan = ctx.run.artifact("study-plan")
    main = plan["phases"]["baseline_main"]["trials"][:m["main_trials_proposed"]]
    ctx.run.write_artifact("main-plan", {"trials": main, "cap_usd": m["proposed_cap_usd"], "cost": {"p50_usd": m["proposed_expected_usd"], "cap_usd": m["proposed_cap_usd"]}, "review": m})
    return {"main_trials": len(main), "cap_usd": m["proposed_cap_usd"]}


def report_stage(ctx: Context) -> dict:
    from .analysis import baseline_summary
    plan = ctx.run.artifact("study-plan")
    out = baseline_summary(trial_records(ctx.run), plan, annotate(ctx.run))
    ctx.run.write_artifact("baseline-report", out)
    return {"trials": out["trials"], "void": out["void"]}


def build(root: Path, run_id: str, *, mode: str, options: dict | None = None) -> tuple[InvestigationRun, Pipeline, Context]:
    opts = dict(options or {})
    d = Path(root) / run_id
    run = InvestigationRun(d) if (d / "run.json").exists() else InvestigationRun.create(root, run_id, target="ironbark-hire", mode=mode,
                                                                                     stages=STAGES, config={k: v for k, v in opts.items() if k not in ("model_config", "allow_model_calls")})
    if run.mode != mode:
        raise Halt(f"{run_id} was created in {run.mode} mode; it cannot be resumed as {mode}")
    stages = [Stage("inspect", inspect_stage), Stage("pool", pool_stage), Stage("freeze", freeze_stage),
              Stage("baseline_pilot", lambda c: _run_phase(c, "baseline_pilot"), spends=True, manifest=lambda c: manifest(c, "baseline_pilot")),
              Stage("pilot_review", review_stage, gate=True, manifest=review_manifest),
              Stage("baseline_main", lambda c: _run_phase(c, "baseline_main"), spends=True, manifest=lambda c: manifest(c, "baseline_main")),
              Stage("baseline_report", report_stage)]
    return run, Pipeline(stages), Context(run, options=opts)
