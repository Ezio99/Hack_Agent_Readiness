"""Research experiment (isolated): LLM task planning for Larkspur with independent verification. Offline: fixture client only, no network."""
import json
from pathlib import Path

import pytest

from agent_readiness.framework import site as S
from agent_readiness.research.taskplan import catalogue as K
from agent_readiness.research.taskplan import context as X
from agent_readiness.research.taskplan import planner as P
from agent_readiness.research.taskplan.schema import parse_item
from agent_readiness.research.taskplan.verify import Verifier

EXPECTED = {  # fixture intent -> (raw outcome/class-or-category, framed outcome/class-or-category)
    "f01": ("deterministic", "deterministic"), "f02": ("gate_rejected", "deterministic"), "f03": ("gate_rejected", "deterministic"), "f04": ("duplicate", "duplicate"),
    "f05": ("gate_rejected", "deterministic"), "f06": ("deterministic", "deterministic"), "f07": ("gate_rejected", "deterministic"), "f08": ("unsupported_attribute",) * 2,
    "f09": ("human_review",) * 2, "f10": ("unsupported_attribute",) * 2, "f11": ("value_not_in_domain",) * 2, "f12": ("value_type_mismatch",) * 2, "f13": ("rubric",) * 2,
    "f14": ("human_review",) * 2, "f15": ("deterministic",) * 2, "f16": ("unknown_entity",) * 2, "f17": ("not_answerable",) * 2, "f18": ("gate_rejected", "deterministic"),
    None: ("schema_invalid",) * 2, "f20": ("gate_rejected",) * 2}


@pytest.fixture(scope="module")
def batch():
    view = K.view(S.get("larkspur"))
    items, err = P.parse_batch(P.fixture_client().complete(P.build_request(view, 20)).text)
    assert err is None and len(items) == 20
    return view, items


def _run(batch, framing):
    view, items = batch
    v = Verifier(S.get("larkspur"), view, framing)
    return {d.intent_id: d for d in (v.verify(it["index"], it["proposal"], it["schema_errors"]) for it in items)}


@pytest.mark.parametrize("framing,col", [("raw", 0), ("framed", 1)])
def test_every_fixture_proposal_gets_the_expected_decision(batch, framing, col):
    got = _run(batch, framing)
    for intent, exp in EXPECTED.items():
        d = got[intent]
        assert (d.cls if d.outcome == "accepted" else d.category) == exp[col], (framing, intent, d.outcome, d.cls, d.category, d.reasons)


def test_only_deterministic_accepted_tasks_are_eligible_and_their_answers_come_from_the_oracle(batch):
    got = _run(batch, "framed")
    oracle = S.get("larkspur").oracle()
    for d in got.values():
        assert d.eligible == (d.outcome == "accepted" and d.cls == "deterministic")
        if d.eligible:
            ans = oracle.answer(d.criterion)
            assert ans.supported and (sorted(ans.truth) if isinstance(ans.truth, list) else ans.truth) == (sorted(d.truth) if isinstance(d.truth, list) else d.truth)


def test_answer_like_fields_from_the_llm_are_stripped_and_never_used(batch):
    _, items = batch
    f17 = next(it for it in items if it["raw"].get("intent_id") == "f17")
    assert f17["stripped_answer_fields"] == {"expected_answer": "Advanced joinery"} and f17["proposal"] is not None
    p, stripped, errs = parse_item({"intent_id": "x", "persona": "budget_learner", "journey": "find_affordable", "scenario": "Which course is cheapest overall?", "task_type": "best",
                                   "ranking": {"attribute": "course fee", "direction": "lowest"}, "answer_form": "single", "answer": "Mindful meditation"})
    assert p is not None and stripped == {"answer": "Mindful meditation"} and not errs


def test_framed_questions_are_generated_from_the_verified_criterion_and_still_gated(batch):
    got = _run(batch, "framed")
    assert "Precisely: Which courses have level 'Beginner' and materials 'Included'? List every one by name." in got["f02"].reasons[-1]
    assert got["f20"].category == "gate_rejected" and "contains the expected answer" in got["f20"].reasons[0]      # a leak in the scenario is still caught


def test_malformed_batches_and_items_are_rejected_explicitly():
    assert P.parse_batch("not json")[1].startswith("response is not JSON")
    assert P.parse_batch(json.dumps({"items": []}))[1] == "response has no 'tasks' list"
    items, err = P.parse_batch(json.dumps({"tasks": ["text", {"intent_id": "a"}]}))
    assert err is None and [it["proposal"] for it in items] == [None, None] and items[0]["schema_errors"] == ["not an object"] and items[1]["schema_errors"]


def test_catalogue_view_contains_only_oracle_attributes_and_is_fingerprinted():
    view = K.view(S.get("larkspur"))
    assert {a["attribute"] for a in view["attributes"]} == set(S.get("larkspur").oracle().fields) and "category" not in {a["attribute"] for a in view["attributes"]}
    assert len(view["items"]) == 14 and K.fingerprint(view) == K.fingerprint(K.view(S.get("larkspur")))


def test_business_context_is_labelled_synthetic():
    assert "SYNTHETIC" in X.LABEL and "not customer research" in X.LABEL and "illustrative" in X.CONTEXT["weights_note"]
    assert abs(sum(j["weight"] for j in X.CONTEXT["journeys"]) - 1.0) < 1e-9 and len(X.CONTEXT["personas"]) == 4


def test_paid_client_refuses_without_an_owner_approval_note(tmp_path):
    with pytest.raises(PermissionError):
        P.meta_client(tmp_path, approval_note=" ", run_cap_usd=0.1, max_requests=1)


def test_experiment_preserves_every_artefact_outside_the_repository_tracked_tree(tmp_path):
    from agent_readiness.research.taskplan.experiment import run
    r = run(client="fixture", out=tmp_path)
    d = Path(r["dir"])
    assert {p.name for p in d.iterdir()} >= {"request.json", "response.json", "proposals.json", "decisions.raw.private.json", "decisions.framed.private.json",
                                             "decisions.raw.public.json", "decisions.framed.public.json", "metrics.json", "examples.public.json"}
    req = json.loads((d / "request.json").read_text())
    assert req["prompt_version"] == P.PROMPT_VERSION and req["catalogue_fingerprint"] and req["context_label"] == X.LABEL and req["model"]["provider"] == "fixture"
    pub = (d / "decisions.framed.public.json").read_text()
    assert '"truth"' not in pub and '"criterion"' not in pub
    assert r["llm"]["framed"]["eligible_deterministic"] == 8 and r["llm"]["raw"]["eligible_deterministic"] == 3 and r["cost"]["calculated_usd"] == 0.0


def test_the_experiment_is_isolated():
    root = Path(__file__).resolve().parents[1] / "src" / "agent_readiness"
    for pkg in ("hosted", "framework", "diagnostics", "grading", "investigate", "live"):
        assert not any("research" in p.read_text() for p in (root / pkg).rglob("*.py")), pkg


def test_schema_v2_is_strict_uses_only_proven_keywords_and_keeps_v1_intact():
    from agent_readiness.research.taskplan import preflight as PF
    from agent_readiness.research.taskplan.schema import PROVEN_KEYWORDS, json_schema, json_schema_v2
    v2 = json_schema_v2()
    assert all(set(o["required"]) == set(o["properties"]) and o["additionalProperties"] is False for _, o in PF._objects(v2))
    assert PF._keywords(v2) <= PROVEN_KEYWORDS
    v1 = json_schema()
    item = v1["properties"]["tasks"]["items"]
    assert "attribute" not in item.get("required", v1["$defs"].get("Proposal", {}).get("required", []))          # v1 itself is unchanged (it is what run 1 sent)


def test_parser_treats_v2_nulls_and_empties_exactly_like_absent_fields(batch):
    from agent_readiness.research.taskplan.preflight import _v2_shape
    _, items = batch
    for it in items:
        if it["proposal"] is not None:
            p2, _, errs = parse_item(_v2_shape({k: v for k, v in it["raw"].items()}))
            assert not errs and p2 == it["proposal"]
    p, _, errs = parse_item(_v2_shape({"intent_id": "x", "persona": "budget_learner", "journey": "find_affordable", "scenario": "short", "task_type": "best", "answer_form": "single"}))
    assert p is None and any("scenario" in e for e in errs)                                                       # constraints are still enforced by the parser


def test_paid_v2_run_refuses_when_preflight_fails(tmp_path, monkeypatch):
    from agent_readiness.research.taskplan import experiment, preflight
    monkeypatch.setattr(preflight, "run_checks", lambda **kw: {"passed": False, "checks": {"x": {"ok": False, "detail": "forced"}}})
    called = []
    monkeypatch.setattr(P, "meta_client", lambda *a, **k: called.append(1))
    with pytest.raises(PermissionError, match="Meta was NOT called"):
        experiment.run(client="meta", out=tmp_path, approval_note="x", schema_version="taskplan-schema-v2")
    assert called == [] and not any(tmp_path.iterdir())
