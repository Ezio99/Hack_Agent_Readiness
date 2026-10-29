"""evidence-v1 rules (plan D6/D8): a hypothesis is never a fact; only code promotes; novel hypotheses stay unverified and only back EXPERIMENTAL proposals."""
import pytest

from agent_readiness.investigate.models import Effect, Finding, Hypothesis, Observation, Proposal, Provenance, Verification
from agent_readiness.investigate.store import EvidenceError, EvidenceStore, PromotionError

P = Provenance(mode="scripted", source="test")
LIVE = Provenance(mode="live", source="test")


def store_with_obs(path=None):
    s = EvidenceStore(path)
    o = s.add_observation(Observation(kind="k", summary="listing lacks X", data={"n": 1}, provenance=P))
    return s, o


def verifiable(o, **kw):
    return Hypothesis(tier="verifiable", statement="X is only on detail pages", claim_kind="info_absent_on_template", citations=[o.id], provenance=P, **kw)


def novel(o):
    return Hypothesis(tier="novel", statement="agents loop because of Y", prediction="if Y changed, requests fall", citations=[o.id], provenance=P)


def supported(s, o, support=("t1", "t2")):
    h = s.add_hypothesis(verifiable(o))
    s.record_verification(h.id, Verification(verifier="v", result="supported", provenance=P))
    return h


def test_hypothesis_shape_rules():
    o = Observation(kind="k", summary="s", provenance=P)
    with pytest.raises(ValueError):
        Hypothesis(tier="verifiable", statement="s", claim_kind="made_up_claim", citations=[o.id], provenance=P)
    with pytest.raises(ValueError):
        Hypothesis(tier="verifiable", statement="s", citations=[o.id], provenance=P)
    with pytest.raises(ValueError):
        Hypothesis(tier="novel", statement="s", citations=[o.id], provenance=P)              # no falsifiable prediction
    with pytest.raises(ValueError):
        Hypothesis(tier="novel", statement="s", prediction="p", claim_kind="control_unlabeled", citations=[o.id], provenance=P)
    with pytest.raises(ValueError):
        Hypothesis(tier="novel", statement="s", prediction="p", citations=[], provenance=P)  # must cite evidence


def test_citations_must_exist_and_hypotheses_arrive_unverified():
    s, o = store_with_obs()
    with pytest.raises(EvidenceError):
        s.add_hypothesis(Hypothesis(tier="novel", statement="s", prediction="p", citations=["obs-missing"], provenance=P))
    h = verifiable(o)
    h.status = "supported"
    with pytest.raises(EvidenceError):
        s.add_hypothesis(h)                                                                 # a model cannot self-declare "supported"


def test_novel_hypothesis_can_never_be_verified_or_promoted():
    s, o = store_with_obs()
    h = s.add_hypothesis(novel(o))
    with pytest.raises(EvidenceError):
        s.record_verification(h.id, Verification(verifier="v", result="supported", provenance=P))
    with pytest.raises(PromotionError):
        s.promote(h.id, attribution="website", support=["t1", "t2"])
    assert h.status == "unverified" and s.outcome() == "no_supported_issue"                  # a novel hypothesis alone is not a supported issue


def test_promotion_requires_verifier_support_attribution_and_independent_support():
    s, o = store_with_obs()
    h = s.add_hypothesis(verifiable(o))
    with pytest.raises(PromotionError):
        s.promote(h.id, attribution="website", support=["t1", "t2"])                         # not yet verified
    s.record_verification(h.id, Verification(verifier="v", result="supported", provenance=P))
    with pytest.raises(PromotionError):
        s.promote(h.id, attribution="agent", support=["t1", "t2"])                           # agent-side cause is not a website finding
    with pytest.raises(PromotionError):
        s.promote(h.id, attribution="website", support=["t1", "t1"])                         # not independent
    with pytest.raises(PromotionError):
        s.promote(h.id, attribution="undetermined", support=["t1", "t2"])
    f = s.promote(h.id, attribution="website", support=["t1", "t2"])
    assert isinstance(f, Finding) and s.outcome() == "findings"
    s2, o2 = store_with_obs()
    h2 = s2.add_hypothesis(verifiable(o2))
    s2.record_verification(h2.id, Verification(verifier="v", result="supported", provenance=P))
    assert s2.promote(h2.id, attribution="tool_interface", support=["t1"], structural_proof=True)          # one deterministic structural proof suffices


def test_refuted_or_unverifiable_never_promote():
    for result in ("refuted", "unverifiable"):
        s, o = store_with_obs()
        h = s.add_hypothesis(verifiable(o))
        s.record_verification(h.id, Verification(verifier="v", result=result, provenance=P))
        with pytest.raises(PromotionError):
            s.promote(h.id, attribution="website", support=["t1", "t2"])
        with pytest.raises(EvidenceError):
            s.record_verification(h.id, Verification(verifier="v", result="supported", provenance=P))   # a verification cannot be overwritten


def proposal(basis, source, **kw):
    return Proposal(basis=basis, source_id=source, change=kw.pop("change", {"ops": [{"op": "x"}]}), expected_effect="e", provenance=P, **kw)


def test_proposal_basis_rules_and_labels():
    s, o = store_with_obs()
    h = supported(s, o)
    with pytest.raises(EvidenceError):
        s.add_proposal(proposal("verified_finding", h.id))                                   # a hypothesis is not a finding
    with pytest.raises(EvidenceError):
        s.add_proposal(proposal("unverified_hypothesis", h.id))                              # verified-supported: must be promoted first
    f = s.promote(h.id, attribution="website", support=["t1", "t2"])
    p = s.add_proposal(proposal("verified_finding", f.id))
    assert p.validation == "unvalidated" and "EXPERIMENTAL" not in p.label
    n = s.add_hypothesis(novel(o))
    e = s.add_proposal(proposal("unverified_hypothesis", n.id))
    assert "EXPERIMENTAL" in e.label and "not a verified finding" in e.label
    with pytest.raises(EvidenceError):
        s.add_proposal(proposal("unverified_hypothesis", f.id))
    with pytest.raises(EvidenceError):
        s.add_proposal(proposal("unverified_hypothesis", "hyp-nope"))
    assert s.outcome() == "findings"


def test_experimental_only_outcome_and_approval_gates_everything():
    s, o = store_with_obs()
    n = s.add_hypothesis(novel(o))
    p = s.add_proposal(proposal("unverified_hypothesis", n.id))
    assert s.outcome() == "experimental_only"
    with pytest.raises(EvidenceError):
        s.mark_applied(p.id)                                                                 # no owner approval yet
    with pytest.raises(EvidenceError):
        s.add_effect(Effect(proposal_id=p.id, verdict="improvement", provenance=LIVE))        # not applied
    with pytest.raises(EvidenceError):
        s.approve(p.id, manifest_sha256="", note="x")
    s.approve(p.id, manifest_sha256="abc", note="owner approves experiment")
    s.mark_applied(p.id)
    s.add_effect(Effect(proposal_id=p.id, verdict="inconclusive", n_pairs=6, provenance=P))
    assert s.proposals[p.id].status == "applied"                                              # a scripted effect is a pipeline check, not a measurement
    e = s.add_effect(Effect(proposal_id=p.id, verdict="improvement", n_pairs=12, provenance=LIVE))
    assert e.measured and s.proposals[p.id].status == "measured"
    assert s.hypotheses[n.id].status == "unverified"                                          # a measured effect never verifies the hypothesis


def test_manual_change_is_not_auto_applicable():
    s, o = store_with_obs()
    n = s.add_hypothesis(novel(o))
    p = s.add_proposal(proposal("unverified_hypothesis", n.id, change={"manual": "rewrite the footer"}))
    s.approve(p.id, manifest_sha256="abc", note="ok")
    assert not p.auto_applicable
    with pytest.raises(EvidenceError):
        s.mark_applied(p.id)


def test_proposal_cannot_arrive_pre_approved():
    s, o = store_with_obs()
    n = s.add_hypothesis(novel(o))
    pr = proposal("unverified_hypothesis", n.id)
    pr.status = "approved"
    with pytest.raises(EvidenceError):
        s.add_proposal(pr)


def test_store_is_durable_and_replays_identically(tmp_path):
    path = tmp_path / "evidence.jsonl"
    s, o = store_with_obs(path)
    h = supported(s, o)
    f = s.promote(h.id, attribution="website", support=["t1", "t2"])
    n = s.add_hypothesis(novel(o))
    p = s.add_proposal(proposal("unverified_hypothesis", n.id))
    s.approve(p.id, manifest_sha256="abc", note="ok")
    s.mark_applied(p.id)
    s.add_effect(Effect(proposal_id=p.id, verdict="improvement", provenance=LIVE))
    r = EvidenceStore(path)
    assert r.observations.keys() == s.observations.keys() and r.findings.keys() == s.findings.keys()
    assert r.hypotheses[h.id].status == "supported" and r.hypotheses[n.id].status == "unverified"
    assert r.proposals[p.id].status == "measured" and r.proposals[p.id].approvals[0]["note"] == "ok"
    assert f.id in r.findings and r.outcome() == "findings"
    assert all('"event"' in l for l in path.read_text().splitlines())


def test_ids_are_content_derived():
    a = Observation(kind="k", summary="s", data={"a": 1}, provenance=P)
    b = Observation(kind="k", summary="s", data={"a": 1}, provenance=Provenance(mode="live", source="other"))
    assert a.id == b.id and a.id.startswith("obs-")
