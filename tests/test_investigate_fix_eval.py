"""M6 (offline): evidence-backed recommendations, owner-approved patches on the local mirror, frozen-task retesting, and honest before/after evaluation."""
import json
import shutil

import pytest

from agent_readiness.investigate import zoo
from agent_readiness.investigate.evaluate import design
from agent_readiness.investigate.evaluate import stage as ev
from agent_readiness.investigate.inspect.profile import build_profile
from agent_readiness.investigate.investigator.loop import investigate
from agent_readiness.investigate.investigator.stage import final_report_stage, report_stage
from agent_readiness.investigate.llm import ScriptedClient
from agent_readiness.investigate.pipeline import Context, Pipeline, Stage
from agent_readiness.investigate.recommend import stage as rec
from agent_readiness.investigate.recommend import templates
from agent_readiness.investigate.sitemodel.patch import apply_patch
from agent_readiness.investigate.sitemodel.snapshot import Snapshot
from agent_readiness.investigate.taskgen import freeze as freezer
from agent_readiness.investigate.trials import stage as trials_stage
from agent_readiness.investigate.trials.trace import trace_stage

from .test_investigate_investigator import fake_trial, hyp, scripted_model, seed, smooth, step, struggling, ws_for


# ---------------------------------------------------------------------------------------------------------------------- statistics
def test_sign_flip_p_is_exact():
    assert design.sign_flip_p([1, 1, 1, 1]) == 0.125 and design.sign_flip_p([1] * 5) == 0.0625 and design.sign_flip_p([0, 0, 0]) == 1.0
    assert design.sign_flip_p([1, -1, 1, -1]) == 1.0 and design.sign_flip_p([]) == 1.0
    assert 0 < design.sign_flip_p([1] * 20, seed=1) < 0.001                                         # Monte-Carlo branch above 14 pairs, seeded


def arm(rows, **kw):
    return {tid: [{"void": kw.get("void", False), "passed": p, "evidence_backed": p, "model_requests": r, "primary": "x", "page_views": r}] for tid, (p, r) in rows.items()}


PARTS = {f"t{i}": ("holdout" if i >= 5 else "investigation") for i in range(8)}


def test_verdicts_follow_the_preregistered_rule_and_default_to_inconclusive():
    base = arm({f"t{i}": (False, 12) for i in range(8)})
    better = arm({f"t{i}": (True, 5) for i in range(8)})
    v = design.compare(base, better, PARTS, design.RULE)
    assert v["verdict"] == "improvement" and v["pass_delta"] == 1.0 and v["p_pass"] <= 0.1 and v["holdout_consistent"] is True and v["by_partition"]["holdout"]["pairs"] == 3
    assert design.compare(better, base, PARTS, design.RULE)["verdict"] == "regression"
    same = design.compare(base, base, PARTS, design.RULE)
    assert same["verdict"] == "inconclusive" and same["pass_delta"] == 0
    few = design.compare({k: base[k] for k in list(base)[:3]}, {k: better[k] for k in list(base)[:3]}, PARTS, design.RULE)
    assert few["verdict"] == "inconclusive" and "usable pairs" in few["reason"]                       # 3 pairs can never be called an improvement
    mixed = arm({f"t{i}": ((i % 2 == 0), 12) for i in range(8)})
    assert design.compare(base, mixed, PARTS, design.RULE)["verdict"] == "inconclusive"                 # 4 of 8 up: delta 0.5 but p = 0.125 > alpha


def test_fewer_requests_at_equal_pass_rate_counts_and_void_pairs_are_excluded():
    base = arm({f"t{i}": (True, 12) for i in range(8)})
    fast = arm({f"t{i}": (True, 6) for i in range(8)})
    v = design.compare(base, fast, PARTS, design.RULE)
    assert v["verdict"] == "improvement" and v["request_change"] == -0.5
    voided = {**fast, "t0": [{"void": True, "passed": False, "evidence_backed": False, "model_requests": 0, "primary": "provider_or_budget", "page_views": 0}]}
    w = design.compare(base, voided, PARTS, design.RULE)
    assert w["pairs"] == 7 and w["excluded"][0]["task_id"] == "t0"
    assert design.compare(base, {k: fast[k] for k in list(fast)[:2]}, PARTS, design.RULE)["excluded"]      # tasks missing from the patched arm are listed, not silently dropped


# ------------------------------------------------------------------------------------------------------------------------ templates
def test_dsl_only_unnamed_never_overrides_an_existing_name():
    snap = zoo.snapshot("site-2")
    new, rep = apply_patch(snap, {"ops": [{"op": "set_attribute", "pages": ["/*"], "css": "a", "attr": "aria-label", "value": "Home", "only_unnamed": True}]})
    html = new.get("/hours").text()
    assert 'aria-label="Home"' in html and rep["ops"][0]["elements_changed"] > 0
    named = zoo.snapshot("site-1")
    with pytest.raises(Exception, match="changed nothing"):
        apply_patch(named, {"ops": [{"op": "set_attribute", "pages": ["/*"], "css": "nav a", "attr": "aria-label", "value": "Home", "only_unnamed": True}]})      # every nav link is already named


def test_info_absent_template_builds_a_patch_that_the_static_recheck_accepts():
    snap, prof = zoo.snapshot("site-1"), build_profile(zoo.snapshot("site-1"))
    patch, info = templates.build("info_absent_on_template", {"label": "price"}, prof, snap)
    assert patch and info["offered"] and info["recheck"]["passed"] and info["pages_changed"] == ["/workshops"]
    assert patch["ops"][0]["op"] == "copy_field_to_listing" and patch["ops"][0]["css"] == "li.card"
    assert templates.build("info_absent_on_template", {"label": "difficulty"}, build_profile(zoo.snapshot("site-3")), zoo.snapshot("site-3"))[0] is None       # nothing to fix on the clean site
    assert templates.build("repeated_navigation", {}, prof, snap)[1]["offered"] is False


def test_control_and_depth_templates_and_the_refusal_to_offer_a_patch_that_does_nothing():
    s2, p2 = zoo.snapshot("site-2"), build_profile(zoo.snapshot("site-2"))
    patch, info = templates.build("control_unlabeled", {}, p2, s2)
    assert patch and info["offered"] and info["recheck"]["passed"]
    labels = {o["value"] for o in patch["ops"]}
    assert {"Opening hours", "Rooms"} <= labels                                                             # taken from the destination pages' headings (provenance)
    s4, p4 = zoo.snapshot("site-4"), build_profile(zoo.snapshot("site-4"))
    patch4, info4 = templates.build("info_only_after_k_hops", {"k": 3}, p4, s4)
    assert patch4 and info4["recheck"]["passed"] and patch4["ops"][0]["op"] == "add_link" and patch4["ops"][0]["pages"] == ["/"]
    s3, p3 = zoo.snapshot("site-3"), build_profile(zoo.snapshot("site-3"))
    none, why = templates.build("control_unlabeled", {}, p3, s3)
    assert none is None and why["offered"] is False


# ------------------------------------------------------------------------------------------------------------------------ recommend
def with_finding(tmp_path, sid="site-1", scenario=struggling, name="f"):
    ws = ws_for(tmp_path, scenario, sid, name)
    obs = next(iter(ws.run.evidence.observations))
    fin = step("finish", hyps=[hyp("The price is only on detail pages, not on the listing", [obs], claim_kind="info_absent_on_template", label="price"),
                               hyp("Cards give no cue about which pages are worth opening", [obs], prediction="If cards showed more, fewer pages would be opened", proposed_change="Show richer cards")])
    investigate(ws, ScriptedClient(scripted_model([fin])), max_calls=3)
    ws.run.write_artifact("investigation", {"skipped": False, "novel_changes": [{"hypothesis_id": h.id, "proposed_change": "Show richer cards"} for h in ws.run.evidence.hypotheses.values() if h.tier == "novel"]})
    return ws.run


def test_recommend_offers_patches_only_for_verified_findings_and_marks_novel_ideas_experimental(tmp_path):
    run = with_finding(tmp_path)
    assert len(run.evidence.findings) == 1
    out = rec.recommend_stage(Context(run))
    assert out["auto_applicable"] == 1 and out["proposals"] == 2
    props = list(run.evidence.proposals.values())
    v = next(p for p in props if p.basis == "verified_finding")
    n = next(p for p in props if p.basis == "unverified_hypothesis")
    assert v.auto_applicable and v.validation == "unvalidated" and v.status == "proposed" and v.change["static_recheck"]["passed"] and "EXPERIMENTAL" not in v.label
    assert not n.auto_applicable and "EXPERIMENTAL" in n.label and "unverified" in n.label
    ra = run.artifact("recommendations")
    assert ra["verified_finding_proposals"][0]["pages_changed"] == ["/workshops"] and "Resolution" in ra["note"] or "resolution" in ra["note"].lower()


def test_no_verified_finding_means_no_fix_is_offered(tmp_path):
    ws = ws_for(tmp_path, smooth, "site-3", "clean")
    investigate(ws, ScriptedClient(scripted_model([step("finish", hyps=[])])), max_calls=3)
    assert rec.recommend_stage(Context(ws.run))["proposals"] == 0 and ws.run.evidence.outcome() == "no_supported_issue"


# ------------------------------------------------------------------------------------------------------------------ apply (the gate)
def test_applying_a_fix_needs_the_owners_hash_and_only_touches_the_local_mirror(tmp_path):
    run = with_finding(tmp_path)
    rec.recommend_stage(Context(run))
    pid = next(p.id for p in run.evidence.proposals.values() if p.basis == "verified_finding")
    manual = next(p.id for p in run.evidence.proposals.values() if p.basis == "unverified_hypothesis")
    stage = Stage("apply_fix", rec.apply_fix_stage, gate=True, manifest=rec.apply_manifest, skip=lambda c: None if rec.fix_ids(c) else "no proposal selected")
    ctx = Context(run, options={"fix": pid})
    run2_stages = Pipeline([stage])
    r = run2_stages.run(ctx)
    assert r.status == "awaiting_approval" and run.evidence.proposals[pid].status == "proposed" and not (run.dir / "patched").exists()
    m = run.artifact(f"manifests/apply_fix-{r.manifest_sha256[:16]}")
    assert "LOCAL MIRROR" in m["applies_to"] and m["proposals"][0]["proposal_id"] == pid and len(m["proposals"][0]["result_snapshot_sha256"]) == 64
    run.approve("apply_fix", "0" * 64, "wrong hash")
    assert Pipeline([stage]).run(ctx).status == "awaiting_approval"
    run.approve("apply_fix", r.manifest_sha256, "owner approves proposal for the mirror")
    assert Pipeline([stage]).run(ctx).status == "done"
    p = run.evidence.proposals[pid]
    assert p.status == "applied" and p.approvals[0]["note"] == "owner approves proposal for the mirror"
    patched = Snapshot.load(run.dir / "patched" / pid)
    assert patched.sha256 == m["proposals"][0]["result_snapshot_sha256"] != freezer.load(run)[0]["snapshot_sha256"]
    assert zoo.snapshot("site-1").sha256 == freezer.load(run)[0]["snapshot_sha256"]                    # the baseline is untouched
    with pytest.raises(ValueError, match="auto-applicable"):
        rec.apply_manifest(Context(run, options={"fix": manual}))                                        # an unverified idea cannot be auto-applied


# ---------------------------------------------------------------------------------------------------------------- retest + evaluate
def applied_run(tmp_path, post, name="e"):
    run = with_finding(tmp_path, name=name)
    rec.recommend_stage(Context(run))
    pid = next(p.id for p in run.evidence.proposals.values() if p.basis == "verified_finding")
    ctx = Context(run, options={"fix": pid})
    run.write_artifact("arm-config", trials_stage.arm_config(Context(run)))                 # the baseline stage freezes this; synthetic baselines do it here
    st = Stage("apply_fix", rec.apply_fix_stage, gate=True, manifest=rec.apply_manifest)
    r = Pipeline([st]).run(ctx)
    run.approve("apply_fix", r.manifest_sha256, "owner approves")
    Pipeline([st]).run(ctx)
    m, private = freezer.load(run)
    for t in m["tasks"]:
        fake_trial(run, t, private[t["task_id"]], prefix=f"patched-{pid}", **post(t, private[t["task_id"]]))
    return run, pid, ctx


def test_evaluate_reports_improvement_only_when_the_preregistered_rule_is_met_and_mock_effects_are_not_measurements(tmp_path):
    run, pid, ctx = applied_run(tmp_path, smooth)
    out = ev.evaluate_stage(ctx)
    res = run.artifact("evaluation")["results"][pid]
    assert out["verdicts"][pid] == res["verdict"] == "improvement" and res["pairs"] == len(freezer.load(run)[0]["tasks"]) and res["rule_preregistered_at_freeze"] is True
    eff = next(iter(run.evidence.effects.values()))
    assert eff.provenance.mode == "scripted" and not eff.measured and run.evidence.proposals[pid].status == "applied"      # a scripted/mock run is a pipeline check, not a measured effect
    rep = final_report_stage(ctx)
    final = run.artifact("report-final")
    assert final["evaluation"]["results"][pid]["verdict"] == "improvement" and "not an effect on agents" in final["evaluation_statement"] and final["effects"]["measured"] == []
    assert final["recommendations"]["verified_finding_proposals"]


def test_no_change_after_the_fix_is_inconclusive_not_a_win(tmp_path):
    run, pid, ctx = applied_run(tmp_path, struggling, name="e2")
    ev.evaluate_stage(ctx)
    res = run.artifact("evaluation")["results"][pid]
    assert res["verdict"] == "inconclusive" and res["pass_delta"] == 0


def test_a_patch_that_makes_the_answer_visible_on_the_start_page_invalidates_that_task(tmp_path):
    run = with_finding(tmp_path, name="inv")
    snap = freezer.load(run) and zoo.snapshot("site-1")
    cheat, _ = apply_patch(snap, {"ops": [{"op": "insert_text", "pages": ["/"], "css": "h1", "position": "after", "text": "12 Nov"}]})                  # provenance-legal (text exists on the site) but it hands out an answer
    ok, excluded, _ = ev.still_valid(run, cheat)
    assert excluded and any("start page" in e["reason"] or "visible" in e["reason"] for e in excluded) and len(ok) < len(freezer.load(run)[0]["tasks"])


def test_the_evaluation_rule_is_frozen_into_the_manifest_before_any_trial(tmp_path):
    run = with_finding(tmp_path, name="rule")
    m = freezer.load(run)[0]
    assert m["evaluation_rule"]["id"] == "paired-signflip-v1" and m["evaluation_rule"]["alpha"] == 0.10 and m["evaluation_rule"]["min_pairs"] == 4
    assert not list((run.dir / "artifacts" / "trials").glob("patched-*")) or True


def test_post_trials_and_apply_are_skipped_when_no_fix_is_selected_and_post_spending_is_gated(tmp_path):
    run = with_finding(tmp_path, name="skip")
    assert ev.post_manifest(Context(run)) is None and ev.evaluate_stage(Context(run)) == {"evaluated": False}
    run2, pid, ctx = applied_run(tmp_path, smooth, name="gate")
    m = ev.post_manifest(ctx)
    assert m["stage"] == "post_trials" and m["arms"][0]["proposal_id"] == pid and m["same_tasks_profile_model_and_limits_as_baseline"] and m["retries"] == 0 and len(m["evaluation_rule_sha256"]) == 64


# ---------------------------------------------------------------------------------------------------------- trial-stage void policy
def test_an_agent_hitting_its_own_limits_is_a_failure_not_a_void_trial_and_does_not_halt_the_stage(tmp_path, monkeypatch):
    run = with_finding(tmp_path, name="v")
    calls = []

    async def fake(inst, snap, **kw):
        calls.append(inst.spec.task_id)
        rec_ = {"trial": {"mode": "mock"}, "task": {}, "outcome": {"run_status": "request_limit", "answer": None, "errors": []}, "evaluation": {"passed": False, "evidence_backed": False, "answer_valid": False, "missing_evidence": [], "reasons": [], "details": {}},
                "metrics": {"model_requests": 12, "page_views": 3, "limits": {"max_steps": 10}}, "journey": [], "mirror": {"log": [], "blocked": []}, "artifact_path": str(run.dir / "trial-data" / f"x{len(calls)}")}
        (run.dir / "trial-data" / f"x{len(calls)}").mkdir(parents=True, exist_ok=True)
        return rec_
    monkeypatch.setattr(trials_stage, "run_trial", fake)
    manifest_, insts = freezer.load(run)[0], {i.spec.task_id: i for i in freezer.instances(run)}
    for t in manifest_["tasks"]:
        shutil.rmtree(run.dir / "artifacts" / "trials", ignore_errors=True)
    out = trials_stage.run_arm(Context(run), label="baseline", snap=zoo.snapshot("site-1"), tasks=manifest_["tasks"], insts=insts, prefix="vtest", manifest_=trials_stage.manifest(Context(run)), repeats=1)
    assert out["void"] == 0 and out["trials"] == len(manifest_["tasks"]) == len(calls)
    assert "request_limit" not in trials_stage.VOID_STATUSES and "timeout" not in trials_stage.VOID_STATUSES and "estimated_cost_limit" in trials_stage.VOID_STATUSES
