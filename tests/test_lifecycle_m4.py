"""Lifecycle M4: human approval and immutable freezing, clarification capture, the statistical plan (alpha 0.05, tasks as the unit, feasibility and
power), pre-registration checks and the evaluation-manifest builder. Offline and free. Every approval here is of a SYNTHETIC fixture suite."""
import json

import pytest

from agent_readiness.evalruns import manifest as MF
from agent_readiness.framework.site import get
from agent_readiness.research.taskplan import catalogue as K
from agent_readiness.research.taskplan import context as X
from agent_readiness.suites import plan as PL
from agent_readiness.suites.records import StatisticalPlan, SuiteRecord
from agent_readiness.suites.stage_a import approval as AP
from agent_readiness.suites.stage_a import generators as G
from agent_readiness.suites.stage_a import loop as LP
from agent_readiness.suites.store import StoreError, WriteOnceStore

AT = "2026-11-02T13:00:00+00:00"
FIRST = ["p04", "p05", "p08", "p09", "p18", "u01", "u02", "r01", "r02", "r03"]


@pytest.fixture(scope="module")
def proposal(tmp_path_factory):
    site = get("larkspur")
    root = tmp_path_factory.mktemp("m4")
    store = WriteOnceStore(root / "store")
    out = LP.run(site, K.view(site), X.CONTEXT, G.FeedbackFixture(FIRST, n=8), config=LP.LoopConfig(suite_name="synthetic-larkspur-m4"), created_at=AT,
                 out_dir=root / "run", store=store)
    return site, store, out


def test_review_packet_is_public_and_complete(proposal):
    _, store, out = proposal
    p = AP.review_packet(store, out["suite_sha256"])
    assert p["synthetic"] and p["counts"]["tasks"] == 12 and p["counts"]["by_condition"] == {"natural": 12}
    assert all(t["customer_wording"] == t["executed_wording"] for t in p["tasks"] if t["condition"] == "natural")
    text = json.dumps(p)
    for t in out["selected"]:
        for a in ([t["expected_answer"]] if isinstance(t["expected_answer"], str) else t["expected_answer"]):
            assert json.dumps(a) not in text                                                    # no expected answer in the packet
    md = AP.render_markdown(p)
    assert "SYNTHETIC FIXTURE" in md and p["attestation"]["approve"] in md and "a few weeks" in md


def test_approval_needs_the_exact_attestation_and_freezing_needs_approval(proposal):
    _, store, out = proposal
    s = out["suite_sha256"]
    with pytest.raises(AP.ApprovalRefused):
        AP.decide(store, s, decision="approved", attestation="yes", at=AT)
    with pytest.raises(AP.ApprovalRefused):                                                     # the attestation names the decision
        AP.decide(store, s, decision="approved", attestation=AP.attestation_text(s, "rejected"), at=AT)
    rej = AP.decide(store, s, decision="rejected", attestation=AP.attestation_text(s, "rejected"), at=AT)
    with pytest.raises(StoreError):
        AP.freeze(store, s, rej, at=AT)                                                         # a rejection never freezes
    ok = AP.decide(store, s, decision="approved", attestation=AP.attestation_text(s, "approved"), at=AT, notes="m4 test")
    assert "SYNTHETIC FIXTURE" in store.get("approval", ok).notes and store.get("approval", ok).approver_role == "owner"
    fz = AP.freeze(store, s, ok, at=AT)
    assert store.resolve("frozen_suite", "synthetic-larkspur-m4@v1") == fz


def test_real_suites_cannot_be_decided_by_an_automated_process(tmp_path, proposal):
    site, store, out = proposal
    old = store.get("suite", out["suite_sha256"])
    real = store.put(SuiteRecord(**{**old.model_dump(), "suite_name": "larkspur-core"}))           # same content under a non-synthetic name
    with pytest.raises(AP.ApprovalRefused, match="interactive terminal"):
        AP.decide(store, real, decision="approved", attestation=AP.attestation_text(real, "approved"), at=AT)
    assert AP.main(["decide", str(store.root), real, "approved"]) == 2                          # the CLI refuses without a terminal too


def test_substantive_edit_creates_a_new_version_that_needs_new_approval(proposal):
    site, store, out = proposal
    s = out["suite_sha256"]
    raw = next(c["raw"] for c in json.loads((store.root.parent / "run" / "proposals.json").read_text()) if c["candidate_id"] == "r1-u02")
    clarified = AP.clarify(site, K.view(site), X.CONTEXT, raw, {"duration": "4 weeks"}, store=store, at=AT, candidate_id="r1-u02-clarified")
    t = store.get("task", clarified)
    assert t.wording.category == "assisted_restatement" and t.condition == "assisted" and t.wording.customer == raw["scenario"]
    assert any(a.startswith("clarification recorded by the owner at") and "4 weeks" in a for a in t.wording.assumptions)
    v2 = AP.revise(store, s, X.CONTEXT, add=(clarified,), at=AT, notes="owner clarified 'a few weeks' as at most 4 weeks")
    new = store.get("suite", v2)
    assert new.version == 2 and v2 != s and any(i.kind == "suite" and i.sha256 == s for i in new.provenance.inputs)
    assert new.coverage["deterministic"] == 13 and new.coverage["natural_share"] < 1.0
    old_ok = AP.decide(store, s, decision="approved", attestation=AP.attestation_text(s, "approved"), at=AT)
    with pytest.raises(StoreError):
        AP.freeze(store, v2, old_ok, at=AT)                                                      # the v1 approval does not apply to v2
    with pytest.raises(AP.ApprovalRefused):
        AP.decide(store, v2, decision="approved", attestation=AP.attestation_text(s, "approved"), at=AT)


# --------------------------------------------------------------------------------------------------------------------------- statistics
def test_exact_sign_flip_test():
    assert PL.sign_flip_p([1] * 6) == pytest.approx(2 / 64) and PL.sign_flip_p([1] * 5) == pytest.approx(2 / 32)
    assert PL.sign_flip_p([1, -1, 1, -1]) == 1.0 and PL.sign_flip_p([]) == 1.0
    assert PL.sign_flip_p([2 / 3, 1 / 3, 1, 1, 1, 2 / 3]) == pytest.approx(PL.sign_flip_p([2, 1, 3, 3, 3, 2]))   # scale-free; repetitions aggregate per task


@pytest.mark.parametrize("n,feasible_min_p", [(4, False), (5, False), (6, True), (12, True)])
def test_min_achievable_p_rule(n, feasible_min_p):
    f = PL.feasibility(n, 3, sims=200)
    assert (f["min_achievable_p"] <= 0.05) == feasible_min_p and f["alpha"] == 0.05 and f["method"]["unit_of_analysis"].startswith("task")


def test_confirmatory_is_refused_when_infeasible_and_power_is_reported():
    with pytest.raises(PL.InfeasibleError):
        PL.make_plan(n_tasks=8, repetitions=3, requested="confirmatory", sims=300)                 # 8 x 3 is not assumed sufficient
    p = PL.make_plan(n_tasks=8, repetitions=3, requested="confirmatory", allow_exploratory_fallback=True, sims=300)
    assert p.designation == "exploratory" and "fallback" in p.feasibility and p.feasibility["power"] < 0.8
    big = PL.make_plan(n_tasks=24, repetitions=3, requested="confirmatory", effect=0.45, between_task_sd=0.5, sims=300)
    assert big.designation == "confirmatory" and big.feasibility["feasible"] and big.feasibility["minimum_detectable_effect"] <= 0.45
    assert big.feasibility["assumptions"]["statement"].startswith("assumptions, not estimates")
    with pytest.raises(ValueError):
        StatisticalPlan(**{**big.model_dump(), "feasibility": {**big.feasibility, "feasible": False}})   # M1 record still guards it


def test_analysis_is_task_level_and_labels_exploratory():
    plan = PL.make_plan(n_tasks=3, repetitions=2, requested="exploratory", sims=50)
    res = PL.analyse(plan, {"a": {"o": [False, False], "m": [True, True]}, "b": {"o": [True, False], "m": [True, True]}, "c": {"o": [True], "m": []}}, ("o", "m"))
    assert res["pairs"] == 2 and res["per_task"][0]["difference"] == 1.0 and res["per_task"][2]["excluded"]
    assert res["confirmatory_result"] is None and res["label"].startswith("EXPLORATORY")


# --------------------------------------------------------------------------------------------------------------------------- manifests
def _frozen_suite(store, s):
    """The approved, frozen synthetic suite. When the approval test has not run in this process (this test alone, or in another CI shard), it is
    approved and frozen here with exactly that test's inputs: the store is write-once and content-addressed, so the records are identical and the
    tests pass in any order."""
    try:
        return store.resolve("frozen_suite", "synthetic-larkspur-m4@v1")
    except FileNotFoundError:
        ok = AP.decide(store, s, decision="approved", attestation=AP.attestation_text(s, "approved"), at=AT, notes="m4 test")
        return AP.freeze(store, s, ok, at=AT)


def test_manifest_builder_and_regression(tmp_path, proposal):
    site, store, out = proposal
    s = out["suite_sha256"]
    fz = _frozen_suite(store, s)
    plan = PL.make_plan(n_tasks=12, repetitions=1, allow_exploratory_fallback=True, sims=100)
    variants = [(v, site.snapshot(v).sha256) for v in site.variants]
    m = MF.build(store, fz, variants=variants, oracle=site.oracle().label, plan=plan, repetitions=1, seed=7, created_at=AT)
    assert m.conditions == ("natural",) and m.agent.model == "muse-spark-1.3" and m.agent.reasoning_effort == "low" and m.agent.jail_policy_sha256
    assert m.budget["worst_case_reservation_usd"] == MF.worst_case_usd(MF.suite_tasks(store, fz)[2], 2, 1, MF.PER_REQUEST_CAP_USD) and m.budget["paid_execution_approval"] is None
    assert {i.kind for i in m.provenance.inputs} >= {"frozen_suite", "snapshot", "profile", "jail_policy", "plan"}
    sha = store.put(m)
    assert store.put(MF.build(store, fz, variants=variants, oracle=site.oracle().label, plan=plan, repetitions=1, seed=7, created_at=AT)) == sha   # deterministic
    with pytest.raises(ValueError, match="plan"):
        MF.build(store, fz, variants=variants, oracle="x", plan=PL.make_plan(n_tasks=5, repetitions=1, requested="exploratory", sims=20), repetitions=1, seed=7, created_at=AT)
    with pytest.raises(StoreError):
        MF.build(store, s, variants=variants, oracle="x", plan=plan, repetitions=1, seed=7, created_at=AT)          # an unfrozen suite has no manifest
    m2, diff = MF.regression(store, sha, variants=[("modified", site.snapshot("modified").sha256)], created_at=AT)
    assert diff["frozen_suite_sha256"]["same"] and set(diff["changed_fields"]) <= {"variants", "budget"} and m2.plan == m.plan and m2.agent == m.agent
