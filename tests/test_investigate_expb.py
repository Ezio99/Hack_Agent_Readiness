"""EXP-B (offline): owner-selected exploratory proposals, fork that carries a completed investigator, the placebo (unmodified-repeat) arm with a fixed execution order, durable arm/combined spend caps,
control integrity and the separately-labelled exploratory analysis. No network, no key, no model; trial execution is faked where a browser would run."""
import json
import shutil

import pytest

from agent_readiness.cli import main as cli_main
from agent_readiness.investigate import allocation as alloc
from agent_readiness.investigate import flow, zoo
from agent_readiness.investigate import fork as forkmod
from agent_readiness.investigate.evaluate import design, exploratory
from agent_readiness.investigate.evaluate import stage as ev
from agent_readiness.investigate.investigator.stage import final_report_stage
from agent_readiness.investigate.models import Proposal, Provenance
from agent_readiness.investigate.owner import add_owner_proposal
from agent_readiness.investigate.pipeline import Context, Pipeline, Stage
from agent_readiness.investigate.recommend import stage as rec
from agent_readiness.investigate.run import ArtifactExists, InvestigationRun
from agent_readiness.investigate.sitemodel.snapshot import Snapshot
from agent_readiness.investigate.taskgen import freeze as freezer
from agent_readiness.investigate.trials import stage as ts
from agent_readiness.capture import GateRefused
from agent_readiness.ledger import Halt
from agent_readiness.spend_gate import RequestGate

from .test_investigate_investigator import fake_trial, smooth, struggling, ws_for


# ------------------------------------------------------------------------------------------------------------ fixtures
def base_run(tmp_path, name="b", live=False):
    """A frozen site-1 run with synthetic baseline trials and an owner-selected exploratory proposal (label `price`, a field the listing lacks). Not applied."""
    run = ws_for(tmp_path, struggling, "site-1", name).run
    if live:
        src, run = run, InvestigationRun.create(tmp_path, f"{name}-live", target="site-1", mode="live", stages=flow.STAGES)
        for d in ("artifacts", "private", "snapshot", "trial-data"):
            shutil.copytree(src.dir / d, run.dir / d, dirs_exist_ok=True)
        shutil.copy2(src.dir / "evidence.jsonl", run.dir / "evidence.jsonl")
        run = InvestigationRun(run.dir)
    obs = sorted(run.evidence.observations)[:2]
    p = add_owner_proposal(run, owner="owner-1", claim_kind="info_absent_on_template", params={"label": "price"}, hypothesis="Showing the price in the listing reduces browsing effort on price tasks.",
                           prediction="Requests on price-dependent tasks fall by at least 25 %.", cites=obs)
    run.write_artifact("arm-config", ts.arm_config(Context(run)))
    return run, p


def apply(run, pid):
    ctx = Context(run, options={"fix": pid})
    st = Stage("apply_fix", rec.apply_fix_stage, gate=True, manifest=rec.apply_manifest)
    r = Pipeline([st]).run(ctx)
    assert r.status == "awaiting_approval"
    run.approve("apply_fix", r.manifest_sha256, "owner approves the exploratory patch for the mirror")
    assert Pipeline([st]).run(ctx).status == "done"
    return ctx


def plan_for(run, pid):
    snap = Snapshot.load(run.dir / "patched" / pid)
    ok, _, _ = ev.still_valid(run, snap)
    ids = [t["task_id"] for t in ok]
    assert len(ids) >= 5
    return {"placebo_tasks": ids[:3], "affected": ids[:2], "same_shape_controls": [ids[2]], "detail_controls": ids[3:5]}, ids


def exp_ctx(tmp_path, name="x", live=False, **opts):
    run, p = base_run(tmp_path, name, live)
    apply(run, p.id)
    plan, ids = plan_for(run, p.id)
    return run, p, plan, Context(run, options={"fix": p.id, "post_plan": plan, "total_cap_usd": 2.05, **opts})


# ------------------------------------------------------------------------------------------------------------ 1. owner-selected proposal path
def test_owner_proposal_is_an_unverified_labelled_experiment_never_a_finding(tmp_path):
    run, p = base_run(tmp_path)
    h = run.evidence.hypotheses[p.source_id]
    assert p.basis == "unverified_hypothesis" and p.label == "EXPERIMENTAL — OWNER-SELECTED change; not an investigator-verified finding" and p.provenance.source == "owner:owner-1"
    assert h.tier == "novel" and h.status == "unverified" and h.verification is None and h.prediction and h.provenance.source == "owner:owner-1"
    assert not run.evidence.findings and p.validation == "unvalidated" and p.status == "proposed" and p.change["owner_selected"] and p.change["exploratory"] and p.change["static_recheck"]["passed"]
    assert p.auto_applicable and p.change["patch_sha256"] and run.evidence.outcome() == "experimental_only"                       # an unverified idea is never a supported issue


@pytest.mark.parametrize("kw,err", [({"owner": " "}, "owner"), ({"cites": []}, "cite"), ({"cites": ["obs-nope"]}, "unknown observation"), ({"params": {"label": "no such field"}}, "no safe patch")])
def test_owner_proposal_refuses_bad_input(tmp_path, kw, err):
    run = ws_for(tmp_path, struggling, "site-1", "bad").run
    args = dict(owner="o", claim_kind="info_absent_on_template", params={"label": "price"}, hypothesis="h", prediction="p", cites=sorted(run.evidence.observations)[:1]) | kw
    with pytest.raises(ValueError, match=err):
        add_owner_proposal(run, **args)
    assert not run.evidence.proposals


def test_only_owner_selected_patches_can_be_applied_and_only_with_the_exact_approval(tmp_path):
    run, p = base_run(tmp_path)
    ctx = Context(run, options={"fix": p.id})
    m = rec.apply_manifest(ctx)
    assert m["proposals"][0]["exploratory_owner_selected"] is True and "OWNER-SELECTED" in m["proposals"][0]["label"] and "LOCAL MIRROR" in m["applies_to"]
    st = Stage("apply_fix", rec.apply_fix_stage, gate=True, manifest=rec.apply_manifest)
    assert Pipeline([st]).run(ctx).status == "awaiting_approval" and not (run.dir / "patched").exists()                       # nothing applied before approval
    run.approve("apply_fix", "0" * 64, "wrong hash")
    assert Pipeline([st]).run(ctx).status == "awaiting_approval"
    other = Proposal(basis="unverified_hypothesis", source_id=p.source_id, change={**{k: v for k, v in p.change.items() if k != "owner_selected"}}, expected_effect="x", provenance=Provenance(mode="scripted", source="llm:investigator"))
    run.evidence.proposals[other.id] = other                                                                                  # an investigator-originated unverified proposal with ops
    with pytest.raises(ValueError, match="owner-selected"):
        rec.apply_manifest(Context(run, options={"fix": other.id}))
    ctx2 = apply(run, p.id)
    patched = Snapshot.load(run.dir / "patched" / p.id)
    assert patched.sha256 == m["proposals"][0]["result_snapshot_sha256"] != freezer.load(run)[0]["snapshot_sha256"] and run.evidence.proposals[p.id].status == "applied"


def test_cli_propose_owner_records_without_applying(tmp_path, monkeypatch, capsys):
    run = ws_for(tmp_path, struggling, "site-1", "cli").run
    obs = sorted(run.evidence.observations)[0]
    monkeypatch.setattr("sys.argv", ["readiness", "investigate", "propose-owner", str(run.dir), "--owner", "o1", "--label", "price", "--hypothesis", "h", "--prediction", "p", "--cite", obs])
    cli_main()
    out = capsys.readouterr().out
    assert "OWNER-SELECTED" in out and "not applied" in out and not (run.dir / "patched").exists()
    assert len(InvestigationRun(run.dir).evidence.proposals) == 1


# ------------------------------------------------------------------------------------------------------------ 2. fork carrying a completed investigator
def carried_source(tmp_path, status="completed"):
    src, p = base_run(tmp_path, "carry", live=True)
    for s in ("inspect", "taskgen", "freeze", "baseline_trials", "trace", "investigate", "recommend"):
        src.set_status(s, "done")
    src.write_artifact("investigation", {"skipped": False, "finished": status == "completed", "status": status, "incomplete": None, "model_requests": 8, "cost_usd": 0.037})
    src.write_artifact("recommendations", {"verified_finding_proposals": [], "not_offered": [], "experimental_manual_proposals": []})
    led = src.ledger(2.05)
    led.reserve("carry-live-taskgen:req01", 0.03); led.settle("carry-live-taskgen:req01", 0.02)
    return InvestigationRun(src.dir)


def test_fork_can_carry_a_completed_investigators_evidence_as_a_verified_prefix(tmp_path):
    src = carried_source(tmp_path)
    before = (src.dir / "evidence.jsonl").read_bytes()
    new = InvestigationRun(forkmod.fork(src.dir, tmp_path, "carry-fork", carry_investigation=True))
    assert (src.dir / "evidence.jsonl").read_bytes() == before                                                                 # source only read
    assert [new.status(s) for s in ("investigate", "recommend", "taskgen", "report", "apply_fix")] == ["done", "done", "done", "pending", "pending"] and new.approvals() == []
    prov = forkmod.load_fork(new)
    assert prov["carried_investigation"]["investigation_status"] == "completed" and prov["carried_investigation"]["evidence_lines"] == len((src.dir / "evidence.jsonl").read_text().splitlines())
    assert "artifacts/investigation.json" in prov["imported_sha256"] and (new.dir / "evidence.jsonl").read_bytes() == before
    forkmod.verify_fork(new)
    InvestigationRun(new.dir).evidence.add_observation(next(iter(InvestigationRun(new.dir).evidence.observations.values())).model_copy(update={"id": "", "summary": "a new observation"}))      # growing the store is fine
    forkmod.verify_fork(InvestigationRun(new.dir))
    lines = (new.dir / "evidence.jsonl").read_text().splitlines()
    (new.dir / "evidence.jsonl").write_text("\n".join(lines[1:]) + "\n")                                                       # rewriting the carried history is not
    with pytest.raises(Halt, match="carried investigator evidence"):
        forkmod.verify_fork(new)


def test_carry_requires_a_completed_investigator_and_a_plain_fork_does_not_carry(tmp_path):
    bad = carried_source(tmp_path / "a", status="incomplete_due_to_infrastructure_error")
    with pytest.raises(ValueError, match="completed"):
        forkmod.fork(bad.dir, tmp_path, "nope", carry_investigation=True)
    good = carried_source(tmp_path / "b")
    plain = InvestigationRun(forkmod.fork(good.dir, tmp_path, "plain"))
    assert plain.status("investigate") == "pending" and not (plain.dir / "evidence.jsonl").exists() and forkmod.load_fork(plain)["carried_investigation"] is None


# ------------------------------------------------------------------------------------------------------------ 3. plan, fixed order, manifest
def test_plan_validation_and_a_fixed_counterbalanced_execution_order():
    ids = [f"t{i}" for i in range(6)]
    plan = exploratory.validate_plan({"placebo_tasks": ids[:3], "affected": ids[:2], "same_shape_controls": [ids[2]], "detail_controls": ids[3:5]}, ids)
    steps = exploratory.execution_plan(plan, ids, "prp-1")
    assert [s["name"] for s in steps] == ["placebo:t0:r1", "patched:t0:r1", "patched:t1:r1", "placebo:t1:r1", "placebo:t2:r1", "patched:t2:r1", "patched:t3:r1", "patched:t4:r1", "patched:t5:r1"]
    assert exploratory.execution_plan(plan, ids, "prp-1") == steps                                                              # deterministic
    base = {"placebo_tasks": ids[:3], "affected": ids[:2], "same_shape_controls": [ids[2]], "detail_controls": ids[3:5]}
    for bad in ({**base, "affected": []}, {**base, "same_shape_controls": []}, {**base, "detail_controls": [ids[0]]}, {**base, "placebo_tasks": ids[:3] + ["zz"]}, {**base, "affected": ids[:2] + [ids[2]]}, {"placebo_tasks": []}):
        with pytest.raises(ValueError):
            exploratory.validate_plan(bad, ids)
    with pytest.raises(ValueError, match="not valid on the patched mirror"):
        exploratory.execution_plan(plan, ids[1:], "prp-1")


def test_post_manifest_lists_order_caps_rules_and_the_identical_control(tmp_path):
    run, p, plan, ctx = exp_ctx(tmp_path)
    m = ev.post_manifest(ctx)
    steps = exploratory.execution_plan(plan, m["arms"][0]["task_ids"], p.id)
    assert m["execution_order"] == [s["name"] for s in steps] and len(m["execution_order"]) == 3 + len(m["arms"][0]["task_ids"]) and m["execution_order_sha256"] == run.manifest_sha256(m["execution_order"])
    assert m["caps_usd"]["patched_arm"] == 0.80 and m["caps_usd"]["placebo_arm"] == 0.55 and m["caps_usd"]["post_trials_combined"] == 1.35 and m["caps_usd"]["per_trial"] == 0.50 and m["caps_usd"]["per_request"] == 0.05
    assert m["exploratory"]["rules_sha256"] == exploratory.RULES_SHA256 and "never its replacement" in m["exploratory"]["label"] and "OWNER-SELECTED" in m["exploratory"]["proposal_label"]
    base_cfg = ts.shared_arm_config(ctx)
    ident = m["placebo"]["identical_to_baseline"]
    assert ident["snapshot_sha256"] == m["placebo"]["snapshot_sha256"] == freezer.load(run)[0]["snapshot_sha256"] and ident["arm_config_sha256"] == run.manifest_sha256(base_cfg) and ident["model"] == base_cfg["model"]
    assert m["evaluation_rule_sha256"] == run.manifest_sha256(freezer.load(run)[0]["evaluation_rule"])                      # the frozen rule is unchanged and still pinned
    assert run.has_artifact("post-plan") and ev.post_manifest(Context(run, options={"fix": p.id, "total_cap_usd": 2.05})) == m   # the plan is stored write-once; the stored plan reproduces the manifest
    with pytest.raises(ArtifactExists):
        ev.post_manifest(Context(run, options={"fix": p.id, "total_cap_usd": 2.05, "post_plan": {**plan, "detail_controls": plan["detail_controls"][:1]}}))      # a changed plan after approval is refused


def test_post_manifest_without_a_plan_is_the_legacy_manifest_and_k_must_be_one(tmp_path):
    run, p = base_run(tmp_path, "leg")
    apply(run, p.id)
    m = ev.post_manifest(Context(run, options={"fix": p.id}))
    assert "execution_order" not in m and "placebo" not in m and "exploratory" not in m
    plan, _ = plan_for(run, p.id)
    run.write_artifact("post-plan", plan)
    cfg = run.artifact("arm-config")
    run_dir = run.dir / "artifacts" / "arm-config.json"
    run_dir.write_text(json.dumps({**cfg, "repeats": 2}))
    with pytest.raises(ValueError, match="K = 1"):
        ev.post_manifest(Context(run, options={"fix": p.id}))


def test_caps_fit_the_ceiling_only_when_the_imported_history_leaves_room():
    a = alloc.post_trials_caps(2.05, 0.670252)
    assert a["combined_cap_fits_ceiling"] and a["headroom_after_combined_cap_usd"] == round(2.05 - 0.670252 - 1.35, 6) == 0.029748
    assert alloc.PATCHED_ARM_CAP_USD + alloc.PLACEBO_ARM_CAP_USD == alloc.POST_TRIALS_CAP_USD
    assert not alloc.post_trials_caps(2.05, 0.8)["combined_cap_fits_ceiling"] and "combined_cap_fits_ceiling" not in alloc.post_trials_caps(2.05)


# ------------------------------------------------------------------------------------------------------------ 4. execution matches the manifest; caps enforced
def faked(run, monkeypatch, calls, status="completed", mutate=None, reserve_usd=None):
    async def fake_trial_run(inst, snap, *, output, request_gate, label, **kw):
        calls.append({"task": inst.spec.task_id, "label": label, "snap": snap.sha256, "gate": request_gate, "inst": inst})
        out = run.dir / "trial-data" / f"fake-{len(calls)}" / "x"
        out.mkdir(parents=True, exist_ok=True)
        (out / "observations.json").write_text(json.dumps([{"path": "/", "text": ""}]))
        st = status
        if reserve_usd is not None:
            try:
                request_gate.reserve(1, {"model": "m", "max_completion_tokens": int(reserve_usd / 4.25e-6), "messages": [{"role": "user", "content": "x"}]})
            except GateRefused as exc:
                st = "estimated_cost_limit"
                calls[-1]["refused"] = str(exc)
        rec_ = {"trial": {"label": label, "mode": "mock"}, "task": {}, "outcome": {"run_status": st, "stop_reason": "x", "errors": [], "answer": None},
                "evaluation": {"passed": True, "evidence_backed": True, "answer_valid": True, "missing_evidence": [], "reasons": [], "details": {}},
                "metrics": {"model_requests": 3, "steps": 2, "page_views": 3, "limits": {"max_steps": 10}},
                "journey": [{"step": 1, "path": "/", "query": "", "actions": [{"name": "navigate", "params": {"url": "/"}}], "executed": [{"result": "ok", "error": None}]}],
                "mirror": {"log": [{"method": "GET", "path": "/", "status": 200}], "blocked": []}, "artifact_path": str(out)}
        if mutate:
            mutate(rec_, label, inst)
        return rec_
    monkeypatch.setattr(ts, "run_trial", fake_trial_run)
    monkeypatch.setattr(ts, "preflight", lambda cfg, allow: "k")


def approved_post(tmp_path, monkeypatch, name="p", **kw):
    run, p, plan, ctx = exp_ctx(tmp_path, name, live=True, allow_model_calls=True)
    calls = []
    faked(run, monkeypatch, calls, **kw)
    return run, p, plan, ctx, calls


def test_the_stage_executes_exactly_the_approved_order_snapshots_instances_and_caps(tmp_path, monkeypatch):
    run, p, plan, ctx, calls = approved_post(tmp_path, monkeypatch)
    m = ev.post_manifest(ctx)
    ev.post_trials_stage(ctx)
    assert [f"{c['label']}:{c['task']}:r1" for c in calls] == m["execution_order"]                                              # order = manifest order
    patched_sha, orig_sha = m["arms"][0]["patched_snapshot_sha256"], m["placebo"]["snapshot_sha256"]
    assert all(c["snap"] == (patched_sha if c["label"] == "patched" else orig_sha) for c in calls) and patched_sha != orig_sha            # placebo = the ORIGINAL source snapshot
    base_inst = {i.spec.task_id: i for i in freezer.instances(run)}
    for c in calls:
        if c["label"] == "placebo":
            assert c["inst"].spec == base_inst[c["task"]].spec and c["inst"].truth == base_inst[c["task"]].truth                # the original frozen task and criteria, untouched
    caps = m["caps_usd"]
    placebo_ids = {f"placebo-{p.id}-{t}-r1" for t in plan["placebo_tasks"]}
    patched_ids = {c["gate"].run_id for c in calls if c["label"] == "patched"}
    for c in calls:
        g = c["gate"]
        arm_scope, combined = g.scopes
        assert arm_scope[1] == (caps["patched_arm"] if c["label"] == "patched" else caps["placebo_arm"]) and combined[1] == caps["post_trials_combined"] == 1.35
        assert set(arm_scope[0]) == (patched_ids if c["label"] == "patched" else placebo_ids) and set(combined[0]) == patched_ids | placebo_ids
        assert g.run_cap == m["run_cap_usd"] == 0.5 and g.per_request_cap == m["per_request_cap_usd"] == 0.05 and g.max_requests == m["max_requests_per_trial"]
    assert len(patched_ids) == len(m["arms"][0]["task_ids"]) and len(placebo_ids) == 3


def _pre(run, gate_id, usd):
    """Commit `usd` in the durable ledger under the gate id of a trial that has NOT run yet (so the per-trial cap of the trial under test is not what refuses)."""
    run.ledger(2.05).reserve(f"{gate_id}:req09", usd)


def test_the_patched_arm_cap_binds_durably_and_names_itself(tmp_path, monkeypatch):
    run, p, plan, ctx, calls = approved_post(tmp_path, monkeypatch, reserve_usd=0.02)
    m = ev.post_manifest(ctx)
    steps = exploratory.execution_plan(plan, m["arms"][0]["task_ids"], p.id)
    last_patched = [s for s in steps if s["arm"] == "patched"][-1]["task_id"]
    _pre(run, f"patched-{p.id}-{last_patched}-r1", 0.79)                                                                       # 0.79 already committed in the patched arm (cap 0.80)
    with pytest.raises(Halt, match="void trial"):
        ev.post_trials_stage(ctx)
    refused = [c for c in calls if c.get("refused")]
    assert refused and refused[0]["label"] == "patched" and "patched-arm cap US$0.8" in refused[0]["refused"]                 # the ARM cap refused, not the per-trial or combined cap
    assert [c["label"] for c in calls if not c.get("refused")][:1] == ["placebo"]                                               # the placebo arm ran normally before the patched arm was stopped
    calls.clear()
    with pytest.raises(Halt, match="void trial"):                                                                               # restart: a NEW gate instance reads the same durable ledger and refuses again
        ev.post_trials_stage(Context(run, options=dict(ctx.options)))
    assert calls and "patched-arm cap" in calls[-1]["refused"]


def test_the_placebo_arm_cap_binds_on_its_own(tmp_path, monkeypatch):
    run, p, plan, ctx, calls = approved_post(tmp_path, monkeypatch, reserve_usd=0.02)
    _pre(run, f"placebo-{p.id}-{plan['placebo_tasks'][-1]}-r1", 0.54)
    with pytest.raises(Halt, match="void trial"):
        ev.post_trials_stage(ctx)
    assert calls[-1]["label"] == "placebo" and "placebo-arm cap US$0.55" in calls[-1]["refused"]


def test_the_combined_scope_is_enforced_by_the_same_durable_mechanism(tmp_path):
    """In production the combined cap (1.35) equals the sum of the two arm caps, so an arm cap always binds first; it stays attached as a second line of defence. The mechanism itself is proven here with
    unequal numbers: the combined scope refuses while the arm scope still has room, across a restart."""
    from agent_readiness.ledger import Ledger
    led = Ledger(tmp_path, 2.05)
    a, b = frozenset({"patched-x"}), frozenset({"placebo-x"})
    led.reserve("patched-x:req01", 0.70)
    led.reserve("placebo-x:req01", 0.45)
    mk = lambda: RequestGate(led, "placebo-x", per_request_cap=0.5, run_cap=1.0, scope_run_ids=b, scope_cap=0.55, extra_scopes=((a | b, 1.20, "post-trials"),))
    body = {"model": "m", "max_completion_tokens": int(0.08 / 4.25e-6), "messages": [{"role": "user", "content": "x"}]}
    with pytest.raises(GateRefused, match="post-trials cap US\\$1.2"):                                                         # arm: 0.45 + 0.08 <= 0.55 fits; combined: 1.15 + 0.08 > 1.20
        mk().reserve(2, body)
    with pytest.raises(GateRefused, match="post-trials cap"):                                                                    # a new instance (restart) sees the same ledger
        mk().reserve(2, body)


def test_a_completed_stage_resumes_without_rerunning_finished_trials(tmp_path, monkeypatch):
    run, p, plan, ctx, calls = approved_post(tmp_path, monkeypatch)
    ev.post_trials_stage(ctx)
    n = len(calls)
    ev.post_trials_stage(Context(run, options=dict(ctx.options)))
    assert len(calls) == n                                                                                                      # every trial artifact exists: nothing re-sent


def test_a_control_that_differs_from_the_baseline_stops_the_stage(tmp_path, monkeypatch):
    for key, value in (("model", "other-model"), ("profile_hash", "deadbeef")):
        run, p, plan, ctx, calls = approved_post(tmp_path / key, monkeypatch)
        base = run.artifact(f"trials/baseline-{plan['placebo_tasks'][0]}-r1")
        (run.dir / "artifacts" / "trials" / f"baseline-{plan['placebo_tasks'][0]}-r1.json").write_text(json.dumps({**base, "trial": {**base["trial"], "model": "muse-spark-1.3", "profile_hash": "abc"}}))
        faked(run, monkeypatch, calls, mutate=lambda r, label, inst, k=key, v=value: r["trial"].update({"model": "muse-spark-1.3", "profile_hash": "abc", k: v}))
        with pytest.raises(Halt, match="control integrity"):
            ev.post_trials_stage(ctx)
        assert len(calls) == 1                                                                                                  # stopped after the first trial: never compare against a changed control
    run, p, plan, ctx, calls = approved_post(tmp_path / "snap", monkeypatch)
    b = plan["placebo_tasks"][0]
    base = run.artifact(f"trials/baseline-{b}-r1")
    (run.dir / "artifacts" / "trials" / f"baseline-{b}-r1.json").write_text(json.dumps({**base, "trial": {**base["trial"], "snapshot_sha256": "a" * 64}}))
    faked(run, monkeypatch, calls, mutate=lambda r, label, inst: r["trial"].update({"snapshot_sha256": "b" * 64}))
    with pytest.raises(Halt, match="control integrity.*snapshot_sha256"):
        ev.post_trials_stage(ctx)                                                                                                # the placebo must use the baseline's source snapshot


# ------------------------------------------------------------------------------------------------------------ 5. exploratory analysis
PLAN = {"placebo_tasks": ["a1", "a2", "c1"], "affected": ["a1", "a2"], "same_shape_controls": ["c1"], "detail_controls": ["d1", "d2"]}


def rows(req, pv=None, passed=True, void=False):
    return [{"void": void, "passed": passed, "evidence_backed": passed, "model_requests": req, "page_views": req if pv is None else pv, "primary": "x"}]


def arms(base=(13, 13, 13, 3, 3), placebo=(13, 13, 13), patched=(3, 3, 13, 3, 3), **over):
    names = ["a1", "a2", "c1", "d1", "d2"]
    return ({t: rows(b) for t, b in zip(names, base)}, {t: rows(x) for t, x in zip(names[:3], placebo)}, {t: rows(x) for t, x in zip(names, patched)})


def test_support_requires_the_contemporaneous_comparison_noise_page_views_and_agreement():
    out = exploratory.analyze(PLAN, *arms())
    assert out["verdict"] == "consistent_with_h1" and out["affected"]["a1"]["primary_meets_floor"] and out["noise_estimate_requests"] == 0 and "never its replacement" in out["label"]


@pytest.mark.parametrize("kw,verdict", [
    (dict(patched=(11, 3, 13, 3, 3)), "not_supported"),                                    # a1 only 15 % fewer than the placebo
    (dict(placebo=(13, 13, 13), base=(13, 13, 13, 3, 3), patched=(3, 3, 16, 3, 3)), "uninterpretable"),   # same-shape control moved by 3 + ... (16 vs 13 = 3 is allowed) -> see below
    (dict(patched=(3, 3, 17, 3, 3)), "uninterpretable"),                                   # control moved by 4 > 3
    (dict(patched=(3, 3, 13, 5, 3)), "uninterpretable"),                                   # detail-page control moved by 2 > 1
    (dict(base=(13, 13, 13, 3, 3), placebo=(13, 13, 8), patched=(3, 3, 8, 3, 3)), "consistent_with_h1"),   # noise 5; reductions of 10 exceed it
    (dict(placebo=(13, 13, 5), base=(13, 13, 13, 3, 3), patched=(3, 9, 5, 3, 3)), "not_supported"),   # a2: reduction 4 does not exceed noise 8
    (dict(base=(4, 13, 13, 3, 3), placebo=(13, 13, 13), patched=(3, 3, 13, 3, 3)), "inconclusive_conflicting_comparisons"),   # historical a1=4: 3 vs 4 misses the floor, placebo says support
    (dict(base=(20, 13, 13, 3, 3), placebo=(13, 13, 13), patched=(3, 3, 13, 3, 3)), "inconclusive_conflicting_comparisons"),  # drift: placebo 35 % below the historical value
])
def test_exploratory_verdict_table(kw, verdict):
    got = exploratory.analyze(PLAN, *arms(**kw))["verdict"]
    if kw.get("patched") == (3, 3, 16, 3, 3):
        assert got == "consistent_with_h1"                                                 # |16 - 13| = 3 is exactly the tolerance: still inside
    else:
        assert got == verdict


def test_a_supportive_historical_comparison_alone_never_creates_support():
    out = exploratory.analyze(PLAN, *arms(placebo=(4, 13, 13), patched=(3, 3, 13, 3, 3)))                 # historical says 13 -> 3, but the unmodified repeat already took 4 requests
    assert out["verdict"] == "not_supported" and "contemporaneous" in out["reasons"][0] and out["affected"]["a1"]["secondary_meets_floor"] is True


def test_a_lost_pass_or_unchanged_page_views_defeat_support_and_gaps_make_it_uninterpretable():
    base, placebo, patched = arms()
    patched["a1"] = rows(3, passed=False)
    assert exploratory.analyze(PLAN, base, placebo, patched)["verdict"] == "not_supported"
    base, placebo, patched = arms()
    patched["a2"] = rows(3, pv=13)
    assert exploratory.analyze(PLAN, base, placebo, patched)["verdict"] == "not_supported"
    base, placebo, patched = arms()
    patched["a1"] = rows(3, void=True)
    out = exploratory.analyze(PLAN, base, placebo, patched)
    assert out["verdict"] == "uninterpretable" and "patched:a1" in out["missing_or_void"]
    base, placebo, patched = arms()
    del placebo["c1"]
    assert exploratory.analyze(PLAN, base, placebo, patched)["verdict"] == "uninterpretable"


def test_the_frozen_rule_is_reported_unchanged_next_to_the_separate_exploratory_verdict(tmp_path):
    run, p, plan, ctx = exp_ctx(tmp_path, "full")
    m, private = freezer.load(run)
    steps = exploratory.execution_plan(plan, [t["task_id"] for t in m["tasks"]], p.id)
    _, _, priv_new = ev.still_valid(run, Snapshot.load(run.dir / "patched" / p.id))
    for s in steps:
        t = next(x for x in m["tasks"] if x["task_id"] == s["task_id"])
        prefix = f"{s['arm']}-{p.id}"
        priv = private[s["task_id"]] if s["arm"] == "placebo" else priv_new[s["task_id"]]
        kw = struggling(t, priv) if s["arm"] == "placebo" else smooth(t, priv)
        fake_trial(run, t, priv, prefix=prefix, **kw)
    for t in m["tasks"]:
        if not any(s["task_id"] == t["task_id"] for s in steps):
            fake_trial(run, t, priv_new[t["task_id"]], prefix=f"patched-{p.id}", **smooth(t, priv_new[t["task_id"]]))
    ev.evaluate_stage(ctx)
    doc = run.artifact("evaluation")
    frozen = doc["results"][p.id]
    assert frozen["rule"] == "paired-signflip-v1" and frozen["verdict"] in ("improvement", "regression", "inconclusive") and "exploratory" in doc
    expl = doc["exploratory"]
    assert expl["verdict"] in ("consistent_with_h1", "not_supported", "inconclusive_conflicting_comparisons", "uninterpretable") and expl["rules_sha256"] == exploratory.RULES_SHA256
    assert frozen["rule_preregistered_at_freeze"] is True and doc["rule"]["id"] == "paired-signflip-v1"
    # the frozen verdict is exactly what the frozen rule says about baseline vs patched, with or without the exploratory arm
    from agent_readiness.investigate.trials.attribution import attribute
    final_report_stage(ctx)
    rep = run.artifact("report-final")
    assert "never its replacement" in rep["exploratory_statement"] and "not an investigator-verified finding" in rep["exploratory_statement"] and rep["evaluation"]["results"][p.id]["verdict"] == frozen["verdict"]
    assert any("OWNER-SELECTED" in pr["label"] for pr in rep["proposals"]) and not rep["findings"]


# ------------------------------------------------------------------------------------------------------------ 6. the whole post-investigation sequence on a carried fork, with the real stage definitions
def test_carried_fork_runs_apply_fix_then_post_trials_then_evaluation_behind_two_exact_approvals(tmp_path, monkeypatch):
    src = carried_source(tmp_path / "s")
    for stage in ("inspect", "trace"):
        src.set_status(stage, "done")
    new = InvestigationRun(forkmod.fork(src.dir, tmp_path / "f", "exp-fork", carry_investigation=True))
    assert (new.dir / "artifacts" / "site-profile.json").exists() and (new.dir / "snapshot" / "index.json").exists()                  # carried, so the owner can propose before any stage runs
    forkmod.verify_fork(new)
    pid = add_owner_proposal(new, owner="owner-1", claim_kind="info_absent_on_template", params={"label": "price"}, hypothesis="Showing the price in the listing reduces effort.",
                             prediction="Requests fall by at least 25 % on price tasks.", cites=sorted(new.evidence.observations)[:1]).id
    tasks = [t["task_id"] for t in freezer.load(new)[0]["tasks"]]
    snap_ok = [t["task_id"] for t in ev.still_valid(new, Snapshot.load(new.dir / "snapshot"))[0]]
    plan = {"placebo_tasks": tasks[:3], "affected": tasks[:2], "same_shape_controls": [tasks[2]], "detail_controls": tasks[3:5]}
    opts = {"fix": pid, "post_plan": plan, "total_cap_usd": 2.05, "allow_model_calls": True}
    calls = []
    faked(new, monkeypatch, calls)
    run, pipe, ctx = flow.build(tmp_path / "f", "exp-fork", "site-1", mode="live", options=opts)
    r = pipe.run(ctx)
    assert r.status == "awaiting_approval" and r.stage == "apply_fix" and not calls                                                  # free stages ran; the patch awaits the exact approval
    a_manifest = run.artifact(f"manifests/apply_fix-{r.manifest_sha256[:16]}")
    assert a_manifest["forked_from"]["source_run"] == "carry-live" and a_manifest["proposals"][0]["exploratory_owner_selected"] is True
    run.approve("apply_fix", r.manifest_sha256, "owner approves the exploratory patch")
    r2 = flow.build(tmp_path / "f", "exp-fork", "site-1", mode="live", options=opts)[1].run(flow.build(tmp_path / "f", "exp-fork", "site-1", mode="live", options=opts)[2])
    assert r2.status == "awaiting_approval" and r2.stage == "post_trials" and not calls                                              # a second, separate exact approval for the paid retest
    pm = run.artifact(f"manifests/post_trials-{r2.manifest_sha256[:16]}")
    assert pm["forked_from"]["paid_stages_rerun"] is False and pm["caps_usd"]["post_trials_combined"] == 1.35 and pm["exploratory"]["proposal_id"] == pid
    run.approve("post_trials", "f" * 64, "a different hash")
    run3 = flow.build(tmp_path / "f", "exp-fork", "site-1", mode="live", options=opts)
    assert run3[1].run(run3[2]).status == "awaiting_approval" and not calls                                                          # a different hash unlocks nothing
    run.approve("post_trials", r2.manifest_sha256, "owner approves the retest manifest")
    run4 = flow.build(tmp_path / "f", "exp-fork", "site-1", mode="live", options=opts)
    r4 = run4[1].run(run4[2])
    assert r4.status == "done", (r4.stage, r4.error)
    assert [f"{c['label']}:{c['task']}:r1" for c in calls] == pm["execution_order"] and len(calls) == len(pm["execution_order"])
    doc = run.artifact("evaluation")
    assert doc["evaluated"] and doc["results"][pid]["rule"] == "paired-signflip-v1" and doc["exploratory"]["rules_sha256"] == exploratory.RULES_SHA256
    assert run.artifact("report-final")["exploratory_statement"].startswith("EXPLORATORY") and run.artifact("report-final")["investigation_status"] == "completed"
