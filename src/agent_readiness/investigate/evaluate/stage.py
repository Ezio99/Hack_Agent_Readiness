"""Stages `post_trials` (spends), `evaluate` (free) and `final_report` (free): retest the SAME frozen tasks on each patched mirror and compare with the pre-registered rule."""
from __future__ import annotations

from collections import defaultdict

from ...agent import ModelConfig
from ...suite.core import canonical_hash
from .. import allocation as alloc
from ..models import Effect, Provenance
from ..pipeline import Context
from ..recommend.stage import fix_ids
from ..sitemodel.snapshot import Snapshot
from ..taskgen import freeze as freezer
from ..taskgen.criteria import compile_criterion
from ..taskgen.gate import Accepted, Draft, evaluate as gate_evaluate
from ..trials import stage as trials
from ..trials.attribution import attribute
from ..trials.trace import load_observations
from ...ledger import Halt
from ..fork import provenance_summary
from ..inspect.stage import load_snapshot
from . import design, exploratory


def _applied(ctx: Context) -> list[str]:
    return [pid for pid in fix_ids(ctx) if ctx.run.evidence.proposals.get(pid) and ctx.run.evidence.proposals[pid].status in ("applied", "measured")]


def still_valid(run, snap: Snapshot) -> tuple[list[dict], list[dict], dict]:
    """Frozen tasks that remain valid and unchanged on the patched mirror, those excluded (expected answer changed, or the acceptance gate now fails e.g. the patch put the answer on the start
    page), and `priv`: for each valid task the private record RE-DERIVED ON THE PATCHED SITE. Same question, same expected answer, same limits; only the evidence requirements change, because
    after a fix the decisive values may legitimately sit where the agent no longer has to open a detail page. Scoring patched trials with the baseline's requirements would call a correct answer
    'not evidence-backed' and manufacture a regression."""
    from ..inspect.profile import build_profile
    manifest, private = freezer.load(run)
    prof = build_profile(snap)
    ok, out, priv_new = [], [], {}
    for t in manifest["tasks"]:
        priv = private[t["task_id"]]
        try:
            same = compile_criterion(priv["criterion"], prof).truth == priv["truth"]
        except Exception:
            same = False
        verdict = gate_evaluate(Draft(t["question"], t["start_path"], priv["criterion"], t["source"]), prof, []) if same else None
        if same and isinstance(verdict, Accepted):
            c = verdict.compiled
            ok.append(t)
            priv_new[t["task_id"]] = {**priv, "evidence_paths": c.evidence_paths, "evidence_texts": [list(x) for x in c.evidence_texts], "detail": c.detail, "min_hops": max(verdict.hops.values(), default=0),
                                      "distractors": c.distractors}
        else:
            out.append({"task_id": t["task_id"], "reason": "the expected answer changed on the patched mirror" if not same else getattr(verdict, "reason", "no longer passes the acceptance gate")})
    return ok, out, priv_new


def _plan(ctx: Context) -> dict | None:
    """The validated exploratory retest plan: from `options['post_plan']` (stored write-once as `artifacts/post-plan`, so a changed plan after approval is refused) or the stored artifact; else None."""
    run = ctx.run
    opt = ctx.options.get("post_plan")
    if opt is not None:
        plan = exploratory.validate_plan(opt, [t["task_id"] for t in freezer.load(run)[0]["tasks"]])
        run.write_artifact("post-plan", plan)
        return plan
    return run.artifact("post-plan") if run.has_artifact("post-plan") else None


def post_manifest(ctx: Context) -> dict | None:
    run = ctx.run
    ids = _applied(ctx)
    if not ids:
        return None
    shared = trials.shared_arm_config(ctx)
    base = {k: v for k, v in trials.manifest(ctx, shared).items() if k not in ("stage_cap_usd", "stage_cap_note", "allocation")}      # the baseline stage cap does not apply to patched arms; their manifest is unchanged
    arms = []
    for pid in ids:
        snap = Snapshot.load(run.dir / "patched" / pid)
        ok, excluded, _ = still_valid(run, snap)
        arms.append({"proposal_id": pid, "patched_snapshot_sha256": snap.sha256, "task_ids": [t["task_id"] for t in ok], "excluded": excluded})
    m = {**base, "stage": "post_trials", "mock_behavior": shared["mock_behavior"], "arms": arms, "same_tasks_profile_model_and_limits_as_baseline": True,
         "evaluation_rule_sha256": canonical_hash(run.artifact("tasks-manifest").get("evaluation_rule"))}
    plan = _plan(ctx)
    if plan is None:
        return m
    if len(ids) != 1 or shared["repeats"] != 1:
        raise ValueError("an exploratory retest needs exactly one applied proposal and K = 1 (single trial per task per arm)")
    manifest_, _private = freezer.load(run)
    pid, arm = ids[0], arms[0]
    steps = exploratory.execution_plan(plan, arm["task_ids"], pid)
    forked = provenance_summary(run)
    ceiling = base["ledger_ceiling_usd"]
    task_by_id = {t["task_id"]: t for t in manifest_["tasks"]}
    return {**({"forked_from": forked} if forked else {}), **m,
            "exploratory": {"label": exploratory.RULES["label"], "proposal_id": pid, "proposal_label": run.evidence.proposals[pid].label, "plan": plan, "rules": exploratory.RULES, "rules_sha256": exploratory.RULES_SHA256,
                            "note": "owner-selected, NOT an investigator-verified finding; the frozen rule is computed and reported unchanged and is not replaced by these rules"},
            "execution_order": [s["name"] for s in steps], "execution_order_sha256": canonical_hash([s["name"] for s in steps]),
            "placebo": {"arm": "unmodified repeat of the baseline (placebo)", "tasks": plan["placebo_tasks"], "snapshot_sha256": manifest_["snapshot_sha256"],
                        "identical_to_baseline": {"snapshot_sha256": manifest_["snapshot_sha256"], "arm_config_sha256": canonical_hash(shared), "agent_profile": shared["agent_profile"], "model": shared["model"],
                                                  "endpoint": shared["endpoint"], "frozen_task_sha256": {t: canonical_hash(task_by_id[t]) for t in plan["placebo_tasks"]}},
                        "runtime_check": "after every placebo and patched trial the recorded model, profile, profile hash, schema hashes and limits must equal the baseline trial's (placebo: also the source snapshot); a mismatch stops the stage"},
            "caps_usd": {**alloc.post_trials_caps(ceiling, (forked or {}).get("imported_spend_committed_usd")), "per_trial": base["run_cap_usd"]},
            "cap_enforcement": "durable spend gate: every trial gate carries its arm cap AND the combined cap (reserved + settled, read from the ledger, so they hold across restarts); a refused trial is void and halts the stage"}


def _check_control(run, st: dict, rec: dict) -> None:
    """The unmodified repeat (and the patched arm) must use the SAME model, profile, tool interface and limits as the baseline trial of that task; the placebo also the same source snapshot."""
    base = run.artifact(f"trials/baseline-{st['task']['task_id']}-r1")
    keys = ("model", "profile", "profile_hash", "schema_hashes", "mode") + (("snapshot_sha256",) if st["label"] == "placebo" else ())
    diff = [k for k in keys if k in base.get("trial", {}) and rec.get("trial", {}).get(k) != base["trial"][k]]
    if (base.get("task") or {}).get("limits") != (rec.get("task") or {}).get("limits"):
        diff.append("limits")
    if diff:
        raise Halt(f"control integrity: the {st['label']} trial of {st['task']['task_id']} differs from its baseline trial in {diff}; stopping (never compare against a changed control)")


def post_trials_stage(ctx: Context) -> dict:
    run = ctx.run
    m = post_manifest(ctx)
    manifest_ = freezer.load(run)[0]
    plan = _plan(ctx)
    if plan is not None:
        return _post_trials_exploratory(ctx, m, manifest_, plan)
    total = {"trials": 0, "void": 0}
    for arm in m["arms"]:
        snap = Snapshot.load(run.dir / "patched" / arm["proposal_id"])
        _, _, priv_new = still_valid(run, snap)
        insts = {t["task_id"]: freezer.instance(t, priv_new[t["task_id"]], manifest_["snapshot_sha256"]) for t in manifest_["tasks"] if t["task_id"] in priv_new}
        tasks = [t for t in manifest_["tasks"] if t["task_id"] in arm["task_ids"]]
        r = trials.run_arm(ctx, label="patched", snap=snap, tasks=tasks, insts=insts, prefix=f"patched-{arm['proposal_id']}", manifest_=m, repeats=m["repeats"], mock_behavior=m["mock_behavior"])
        total = {k: total[k] + r[k] for k in total}
        run.write_artifact(f"post-exclusions-{arm['proposal_id']}", arm["excluded"])
    return total


def _post_trials_exploratory(ctx: Context, m: dict, manifest_: dict, plan: dict) -> dict:
    """Run the approved plan EXACTLY: the manifest's execution order, the snapshots, the caps. Placebo trials use the ORIGINAL snapshot, the original frozen instances and criteria."""
    run = ctx.run
    arm = m["arms"][0]
    pid = arm["proposal_id"]
    steps_spec = exploratory.execution_plan(plan, arm["task_ids"], pid)
    if [s["name"] for s in steps_spec] != m["execution_order"]:
        raise Halt("the execution order differs from the approved manifest")
    patched_snap, base_snap = Snapshot.load(run.dir / "patched" / pid), load_snapshot(run)
    _, _, priv_new = still_valid(run, patched_snap)
    insts_patched = {t["task_id"]: freezer.instance(t, priv_new[t["task_id"]], manifest_["snapshot_sha256"]) for t in manifest_["tasks"] if t["task_id"] in priv_new}
    insts_base = {i.spec.task_id: i for i in freezer.instances(run)}
    by_id = {t["task_id"]: t for t in manifest_["tasks"]}
    gid = lambda arm_, t: f"{arm_}-{pid}-{t}-r1"
    sets = {"patched": frozenset(gid("patched", s["task_id"]) for s in steps_spec if s["arm"] == "patched"), "placebo": frozenset(gid("placebo", s["task_id"]) for s in steps_spec if s["arm"] == "placebo")}
    every, caps = sets["patched"] | sets["placebo"], m["caps_usd"]
    steps = []
    for s in steps_spec:
        a_ = s["arm"]
        steps.append({"label": a_, "prefix": f"{a_}-{pid}", "snap": patched_snap if a_ == "patched" else base_snap, "inst": (insts_patched if a_ == "patched" else insts_base)[s["task_id"]],
                      "task": by_id[s["task_id"]], "repeat": s["repeat"],
                      "scopes": [(sets[a_], caps["patched_arm" if a_ == "patched" else "placebo_arm"], f"{a_}-arm"), (every, caps["post_trials_combined"], "post-trials")]})
    out = trials.run_plan(ctx, steps, manifest_=m, verify=lambda rec, st: _check_control(run, st, rec))
    run.write_artifact(f"post-exclusions-{pid}", arm["excluded"])
    return {"trials": out["trials"], "void": out["void"]}


def _collect(run, prefix: str, private, profile) -> dict[str, list[dict]]:
    by: dict[str, list[dict]] = defaultdict(list)
    for path in sorted((run.dir / "artifacts" / "trials").glob(f"{prefix}-*.json")):
        t = run.artifact(f"trials/{path.stem}")
        a = attribute(t, load_observations(run, t), private[t["task_id"]], profile)
        by[t["task_id"]].append({"void": a["void"], "passed": t["evaluation"]["passed"], "evidence_backed": t["evaluation"]["evidence_backed"], "model_requests": t["metrics"]["model_requests"],
                                 "primary": a["primary"], "page_views": t["metrics"]["page_views"]})
    return by


def evaluate_stage(ctx: Context) -> dict:
    run = ctx.run
    ids = _applied(ctx)
    if not ids:
        run.write_artifact("evaluation", {"evaluated": False, "reason": "no fix was applied"})
        return {"evaluated": False}
    manifest_, private = freezer.load(run)
    rule = manifest_.get("evaluation_rule")
    profile = run.artifact("site-profile")
    parts = {t["task_id"]: t["partition"] for t in manifest_["tasks"]}
    base = _collect(run, "baseline", private, profile)
    results = {}
    for pid in ids:
        _, _, priv_new = still_valid(run, Snapshot.load(run.dir / "patched" / pid))
        patched = _collect(run, f"patched-{pid}", {**private, **priv_new}, profile)
        cmp_ = design.compare(base, patched, parts, rule or design.RULE)
        excl = run.artifact(f"post-exclusions-{pid}") if run.has_artifact(f"post-exclusions-{pid}") else []
        cmp_["excluded"] = cmp_["excluded"] + [{**e, "reason": f"invalidated by the patch: {e['reason']}"} for e in excl]
        cmp_["rule_preregistered_at_freeze"] = rule is not None
        results[pid] = cmp_
        p = run.evidence.proposals[pid]
        run.evidence.add_effect(Effect(proposal_id=pid, verdict=cmp_["verdict"], metrics={k: cmp_.get(k) for k in ("pass_delta", "request_change", "p_pass", "p_requests", "by_partition", "holdout_consistent")}, n_pairs=cmp_["pairs"],
                                       note=cmp_["reason"], provenance=Provenance(mode=run.mode, source="code:evaluate")))
    doc = {"evaluated": True, "rule": rule or design.RULE, "results": results}
    plan = _plan(ctx)
    if plan is not None and len(ids) == 1:                                              # EXPLORATORY analysis: separate from, and never a replacement for, the frozen rule above
        pid = ids[0]
        _, _, priv_new = still_valid(run, Snapshot.load(run.dir / "patched" / pid))
        doc["exploratory"] = exploratory.analyze(plan, base, _collect(run, f"placebo-{pid}", private, profile), _collect(run, f"patched-{pid}", {**private, **priv_new}, profile))
    run.write_artifact("evaluation", doc)
    return {"evaluated": True, "verdicts": {pid: r["verdict"] for pid, r in results.items()}}
