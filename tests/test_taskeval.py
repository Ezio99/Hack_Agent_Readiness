"""Task-generation evaluator (taskeval-1), selection (selection-1) and pilot preparation. Offline; uses the developer-written fixture batch."""
import json

import pytest

from agent_readiness.framework.site import get
from agent_readiness.research.taskplan import catalogue as K
from agent_readiness.research.taskplan import context as X
from agent_readiness.research.taskplan import planner as P
from agent_readiness.taskeval import evaluator as TE
from agent_readiness.taskeval import select as TS


@pytest.fixture(scope="module")
def records():
    raw = json.loads(P.FIXTURE.read_text())["tasks"]
    cands = [{"candidate_id": t.get("intent_id") or f"idx{i}", "provenance": {"source": "fixture", "index": i}, "raw": t} for i, t in enumerate(raw)]
    site = get("larkspur")
    return TE.TaskEvaluator(site, K.view(site), X.CONTEXT).evaluate(cands)


def by(records, cid):
    return next(r for r in records if r["candidate_id"] == cid)


@pytest.mark.parametrize("cid,gate", [("f08", "grounded"), ("f10", "grounded"), ("f11", "grounded"), ("f12", "grounded"), ("f16", "grounded"),
                                      ("f09", "expressible"), ("f13", "expressible"), ("f14", "expressible"), ("f17", "answerable"), ("f04", "unique"),
                                      ("f20", "executable_wording_unambiguous"), ("f19", "schema_valid")])
def test_hard_gates_reject_with_the_right_gate(records, cid, gate):
    r = by(records, cid)
    assert not r["hard_pass"] and not r["hard_gates"][gate]["pass"] and any(x.startswith(gate) for x in r["rejection_reasons"])
    assert r["quality"] is None                                                         # soft scores never admit a failed candidate


def test_passing_candidates_pass_every_gate_with_evidence(records):
    passing = [r for r in records if r["hard_pass"]]
    assert {r["candidate_id"] for r in passing} == {"f01", "f02", "f03", "f05", "f06", "f07", "f15", "f18"}
    for r in passing:
        assert all(g["pass"] for g in r["hard_gates"].values()) and r["evidence_refs"] and r["quality"] is not None and r["specification_sha256"]
        assert r["evaluator"] == {"version": TE.VERSION, "config_fingerprint": TE.config_fingerprint(), "advisory_llm_judge": None}


def test_wordings_are_kept_apart_and_assumptions_recorded(records):
    r = by(records, "f05")                                                              # "six weeks or less and under $250": both values stated
    assert r["wordings"]["customer_question"].startswith("I want something short") and r["wordings"]["restated_question"].endswith("List every one by name.")
    assert r["wordings"]["customer_question"] in r["wordings"]["restated_question"] and r["soft"]["specificity"] == 0.5 and r["unsupported_assumptions"] == ["duration le 6 weeks"]
    assert not r["natural_wording_passes_gate"]


def test_public_records_carry_no_expected_answer_or_specification(records):
    for r in records:
        pub = TE.public(r)
        assert "expected_answer" not in pub and "specification" not in pub and "_accepted" not in pub


def test_selection_is_deterministic_covers_and_includes_a_multi_condition_task(records):
    a, log_a = TS.select([dict(r, wordings=dict(r["wordings"])) for r in records], 4)
    b, _ = TS.select([dict(r, wordings=dict(r["wordings"])) for r in reversed(records)], 4)
    assert [r["candidate_id"] for r in a] == [r["candidate_id"] for r in b]               # input order does not matter
    assert all(r["hard_pass"] for r in a) and any(len(r["specification"].get("conditions", [])) > 1 for r in a)
    assert len({r["persona"] for r in a}) >= 3 and all(r["wordings"]["executed"] == "restated_question" for r in a)
    assert all("agent" not in json.dumps(s) for s in log_a)                              # nothing about agent performance enters the rule


def test_config_fingerprint_is_stable():
    assert TE.config_fingerprint() == TE.config_fingerprint() and len(TE.config_fingerprint()) == 16


def test_pilot_freezes_the_selection_and_budget_before_execution(tmp_path, monkeypatch):
    from agent_readiness.research import pilot
    d = tmp_path / "proposals"
    d.mkdir()
    site = get("larkspur")
    (d / "request.json").write_text(json.dumps({"prompt_version": "taskplan-v1", "schema_version": "fixture", "model": {"model": "fixture"}, "catalogue_fingerprint": K.fingerprint(K.view(site))}))
    raw = json.loads(P.FIXTURE.read_text())["tasks"]
    (d / "proposals.json").write_text(json.dumps({"items": [{"index": i, "raw": t} for i, t in enumerate(raw)]}))
    run = pilot.prepare(d, tmp_path / "root", provider="dev")
    sel, prov = run.artifact("selection"), run.artifact("pilot-provenance")
    m = run.artifact("tasks-manifest")
    assert len(sel["selected"]) == len(m["tasks"]) == 4 and prov["budget"]["trials"] == 8 and prov["budget"]["within_cap"]
    assert prov["budget"]["worst_case_reservation_usd"] == round(sum(t["limits"]["max_model_requests"] for t in m["tasks"]) * 2 * pilot.PER_REQUEST_CAP_USD, 6)
    assert {t["question"] for t in m["tasks"]} == {s["restated_question"] for s in sel["selected"]}               # the executed wording is the restated question
    pub = run.artifact("taskeval-records")
    assert all("expected_answer" not in r and "specification" not in r for r in pub)
    assert "Advanced joinery" not in json.dumps([r["stripped_answer_fields"] for r in pub])                      # the LLM-claimed answer value is not published
    assert next(r for r in pub if r["candidate_id"] == "f17")["stripped_answer_fields"] == ["expected_answer"]
    monkeypatch.setattr(pilot, "PER_REQUEST_CAP_USD", 1.0)
    run2 = pilot.prepare(d, tmp_path / "root2", provider="live")
    with pytest.raises(PermissionError, match="exceeds"):
        pilot.execute(run2, approval_note="x")
    assert not (run2.dir / "trial-data").exists()


def test_paid_pilot_requires_an_approval_note(tmp_path, monkeypatch):
    from agent_readiness.research import pilot
    d = tmp_path / "proposals"
    d.mkdir()
    site = get("larkspur")
    (d / "request.json").write_text(json.dumps({"prompt_version": "taskplan-v1", "model": {"model": "fixture"}, "catalogue_fingerprint": K.fingerprint(K.view(site))}))
    (d / "proposals.json").write_text(json.dumps({"items": [{"index": i, "raw": t} for i, t in enumerate(json.loads(P.FIXTURE.read_text())["tasks"])]}))
    run = pilot.prepare(d, tmp_path / "root", provider="live")
    monkeypatch.setattr(pilot, "_enable_jail", lambda r: {"ok": True})
    with pytest.raises(PermissionError, match="approval"):
        pilot.execute(run, approval_note=" ")
    assert not (run.dir / "trial-data").exists()
