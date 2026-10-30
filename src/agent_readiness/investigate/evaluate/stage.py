"""Stages `post_trials` (spends), `evaluate` (free) and `final_report` (free): retest the SAME frozen tasks on each patched mirror and compare with the pre-registered rule."""
from __future__ import annotations

from collections import defaultdict

from ...agent import ModelConfig
from ...suite.core import canonical_hash
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
from . import design


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
    return {**base, "stage": "post_trials", "mock_behavior": shared["mock_behavior"], "arms": arms, "same_tasks_profile_model_and_limits_as_baseline": True, "evaluation_rule_sha256": canonical_hash(run.artifact("tasks-manifest").get("evaluation_rule"))}


def post_trials_stage(ctx: Context) -> dict:
    run = ctx.run
    m = post_manifest(ctx)
    manifest_ = freezer.load(run)[0]
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
    run.write_artifact("evaluation", {"evaluated": True, "rule": rule or design.RULE, "results": results})
    return {"evaluated": True, "verdicts": {pid: r["verdict"] for pid, r in results.items()}}
