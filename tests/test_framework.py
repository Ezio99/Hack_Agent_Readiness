"""Phase 3 framework: site definitions, independent oracles, verifiability classes, validated task generation, and the second controlled site.
Offline: no model, no browser."""
import dataclasses
import json
from pathlib import Path

import pytest

from agent_readiness.framework import generate as G
from agent_readiness.framework import site as S
from agent_readiness.framework.oracle import Record, RecordOracle
from agent_readiness.framework.verifiability import DETERMINISTIC, HUMAN_REVIEW, RUBRIC, classify, eligible_for_scoring
from agent_readiness.grading import v2
from agent_readiness.grading.key import build_key
from agent_readiness.investigate.taskgen import freeze as freezer
from agent_readiness.live import ironbark_runner
from agent_readiness.sites.larkspur import data as LD
from agent_readiness.sites.larkspur import render as LR


@pytest.fixture(scope="module")
def ironbark():
    return G.generate("ironbark")


@pytest.fixture(scope="module")
def larkspur():
    return G.generate("larkspur")


def test_ironbark_variants_are_exactly_the_hosted_original_and_modified_sites():
    site = S.get("ironbark")
    assert site.snapshot("original").sha256 == ironbark_runner.ORIGINAL
    assert site.snapshot("modified").sha256 == ironbark_runner.MODIFIED


def test_larkspur_is_deterministic_and_variants_differ_only_on_the_listing():
    a, b = LR.pages("original"), LR.pages("modified")
    assert LR.pages("original") == a and set(a) == set(b)
    assert [p for p in a if a[p] != b[p]] == ["/courses"]                              # only the listing cards change
    assert "Course fee $480" in b["/courses"] and "Course fee" not in a["/courses"]
    assert LR.snapshot("original").sha256 != LR.snapshot("modified").sha256
    with pytest.raises(ValueError):
        LR.pages("other")


@pytest.mark.parametrize("name", ["ironbark", "larkspur"])
def test_controlled_sites_yield_validated_deterministic_tasks(request, name):
    ts = request.getfixturevalue(name)
    det = [t for t in ts["tasks"] if t["class"] == DETERMINISTIC]
    assert len(det) >= 5 and all(t["eligible"] and t["oracle"] == "agrees" and t["grader_v2_keyable"] and t["stable_across_variants"] for t in det)
    assert {t["kind"] for t in det} >= {"item_set", "extremum"}
    assert ts["eligible"] == len(det)
    assert all(not t["eligible"] for t in ts["tasks"] if t["class"] != DETERMINISTIC)


def test_ironbark_live_availability_is_not_in_the_oracle_and_goes_to_human_review(ironbark):
    avail = [t for t in ironbark["tasks"] if "availability" in t["question"]]
    assert avail and all(t["class"] == HUMAN_REVIEW and t["oracle"] == "declined" for t in avail)


def test_uncontrolled_site_tasks_are_never_eligible():
    ts = G.generate("zoo-site-1")
    assert ts["tasks"] and ts["eligible"] == 0 and all(t["class"] == HUMAN_REVIEW and t["oracle"] == "absent" for t in ts["tasks"])


def test_oracle_disagreement_is_caught_and_routed_to_review():
    site = S.get("larkspur")
    real = site.oracle()

    def lying_oracle():                                                                 # the data says the joinery course is cheap; the page says $480
        recs = [Record(r.name, r.path, {**r.values, "fee": 100 if r.name == "Advanced joinery" else r.values["fee"]}) for r in real.listings["/courses"]]
        return RecordOracle({"/courses": recs}, {k: v for k, v in real.fields.items()}, label="tampered")
    ts = G.generate(dataclasses.replace(site, oracle=lying_oracle))
    fee = [t for t in ts["tasks"] if "course fee" in t["question"]]
    assert fee and any(t["oracle"] == "disagrees" and t["class"] == HUMAN_REVIEW for t in fee)
    assert ts["eligible"] < G.generate(site)["eligible"]


def test_oracle_answers_from_records_not_pages():
    o = S.get("larkspur").oracle()
    assert o.answer({"kind": "extremum", "listing": "/courses", "label": "course fee", "direction": "max"}).truth == "Advanced joinery"
    got = o.answer({"kind": "item_set", "listing": "/courses", "conditions": [{"label": "seats left", "op": "lt", "value": "1"}]})
    assert got.supported and got.truth == ["Japanese for travellers"]
    assert o.answer({"kind": "item_set", "listing": "/courses", "conditions": [{"label": "duration", "op": "lt", "value": "$5"}]}).supported is False   # unit mismatch
    assert o.answer({"kind": "reach_page", "target": "/about"}).supported is False
    assert o.answer({"kind": "page_fact", "page": "/courses/advanced-joinery", "label": "duration"}).truth == "10 weeks"


def test_classification_rules():
    assert classify(key_ok=True, stable=True, oracle="agrees") [0] == DETERMINISTIC
    for kw in ({"key_ok": False, "stable": True, "oracle": "agrees"}, {"key_ok": True, "stable": False, "oracle": "agrees"}, {"key_ok": True, "stable": True, "oracle": "absent"},
               {"key_ok": True, "stable": True, "oracle": "disagrees"}, {"key_ok": True, "stable": True, "oracle": "declined"}):
        cls, reasons = classify(**kw)
        assert cls == HUMAN_REVIEW and reasons
    assert classify(rubric=True)[0] == RUBRIC
    assert eligible_for_scoring(DETERMINISTIC) and not eligible_for_scoring(RUBRIC) and not eligible_for_scoring(HUMAN_REVIEW)


def test_rubric_tasks_come_from_site_tables_and_are_never_eligible(larkspur, ironbark):
    rub = larkspur["rubric"]
    assert len(rub) == 1 and rub[0]["page"] == "/enrolment-policy" and not rub[0]["eligible"] and rub[0]["class"] == RUBRIC
    assert [c["expected"] for c in rub[0]["checklist"]] == [r for _, r in LD.REFUNDS]
    assert ironbark["rubric"] and all(not r["page"].startswith("/hire/") for r in ironbark["rubric"]) and len(ironbark["rubric"]) <= G.MAX_RUBRIC


@pytest.mark.parametrize("name", ["ironbark", "larkspur"])
def test_eligible_tasks_freeze_and_grade_through_the_existing_pipeline(request, name):
    ts = request.getfixturevalue(name)
    manifest, private = G.freeze_eligible(ts)
    assert manifest["schema"] == freezer.SCHEMA and len(manifest["tasks"]) == ts["eligible"] and manifest["snapshot_sha256"] == ts["variants"]["original"]
    assert "truth" not in json.dumps(manifest["tasks"])
    for entry in manifest["tasks"]:
        priv = private[entry["task_id"]]
        inst = freezer.instance(entry, priv, manifest["snapshot_sha256"])
        field = "answers" if priv["style"] == "set" else "answer"
        right, wrong = priv["truth"], (["Nothing"] if priv["style"] == "set" else "Nothing")
        assert inst.grader(inst, inst.answer_model(**{field: right})).passed                 # grader_v1 (the frozen grader)
        assert not inst.grader(inst, inst.answer_model(**{field: wrong})).passed
        key = build_key(entry["task_id"], priv, G.build_profile(S.get(name).snapshot("original")))
        assert v2.grade(key, right).passed and not v2.grade(key, wrong).passed           # grader_v2 agrees


def test_public_view_has_no_expected_answers(larkspur):
    view = G.public(larkspur)
    pub = json.dumps(view)
    questions = " ".join(t["question"] for t in view["tasks"])
    _, private = G.freeze_eligible(larkspur)
    for p in private.values():
        for v in ([p["truth"]] if isinstance(p["truth"], str) else p["truth"]):
            assert v in questions or v not in pub                                       # an entity named in another task's question is not a leak
    assert not any(k in t for t in view["tasks"] for k in ("truth", "criterion", "checklist"))
    assert "Full refund less" not in pub and "_accepted" not in pub


def test_framework_is_isolated_from_the_hosted_path():
    hosted = Path(__file__).resolve().parents[1] / "src" / "agent_readiness" / "hosted"
    assert not any("framework" in p.read_text() for p in hosted.glob("*.py"))
