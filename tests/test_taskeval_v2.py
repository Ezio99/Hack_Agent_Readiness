"""Lifecycle M2: evaluator v2 (taskeval-2) with gate-nl-1, the four wording categories, intent preservation, ambiguity classification, coverage.

Offline and free. Uses the developer-written fixture batch and, when present (git-ignored, local), the 20 recorded Muse Spark proposals."""
import hashlib
import json
from pathlib import Path

import pytest

from agent_readiness.framework.site import get
from agent_readiness.research.taskplan import catalogue as K
from agent_readiness.research.taskplan import context as X
from agent_readiness.research.taskplan import planner as P
from agent_readiness.suites import boundary as B
from agent_readiness.suites.records import InputRef, content_hash
from agent_readiness.suites.store import WriteOnceStore
from agent_readiness.taskeval import evaluator as E1
from agent_readiness.taskeval.v2 import evaluator as E2
from agent_readiness.suites.stage_a import taskrecords as R2
from agent_readiness.taskeval.v2.nl import Analyser

ROOT = Path(__file__).resolve().parents[1]
RECORDED = ROOT / "scanner-data/research/taskplan/taskplan-20261102T203537-meta-7aca17/proposals.json"
# evaluator v1, grader v1 / v2, the acceptance gate v1, the oracle and the planner verifier are NOT modified by the lifecycle work
PINNED = {"src/agent_readiness/taskeval/evaluator.py": "d1a90921509d31ff3c86130433d3fb28dd456b063b52cf43869ca20b7234470f",
          "src/agent_readiness/taskeval/select.py": "9279c91f442dd2d64ab121502771b26da551e32a976083cf9416725755d458ae",
          "src/agent_readiness/investigate/taskgen/criteria.py": "70f377675d5c54ef02bf2cd9b1b543c51fcd0108403fedd81689209d6b549127",
          "src/agent_readiness/investigate/taskgen/gate.py": "4e4e41ce6dce0f6838d7b5427973f24e9cd3ce951c74e45d126929cc44b1c65f",
          "src/agent_readiness/grading/key.py": "785425df3d3a7559a0663b95ac84da31ef2ff14d80b10398d0bbd4e251384ce1",
          "src/agent_readiness/grading/v2.py": "4e1f027c0ec036324135d56ac2d53955fd5880dfbdb02f442c9f78df723391b3",
          "src/agent_readiness/framework/oracle.py": "3799bc8d564166afb29281a5bd0acdb3edfe977e45a454c48ee89afadf5a3a9d",
          "src/agent_readiness/research/taskplan/verify.py": "fb4d6fef880348935fb89e170a9a93d9dbc8784c3e82e60ca2d4661c0e6964c9",
          "src/agent_readiness/research/taskplan/schema.py": "a0b6465b4e09b258dcc50333538c3cefc08559bc9808d54e5f66096c90cc3192",
          "src/agent_readiness/investigate/taskgen/freeze.py": "f1eed6844ba5c9eea593ce50469c2159b938f07e898a12d61cfe3d870d134c9d"}


def fixture_candidates():
    return [{"candidate_id": t.get("intent_id") or f"idx{i}", "provenance": {"source": "fixture", "index": i}, "raw": t}
            for i, t in enumerate(json.loads(P.FIXTURE.read_text())["tasks"])]


def recorded_candidates():
    if not RECORDED.exists():
        pytest.skip("recorded Muse Spark proposals are local, git-ignored data")
    return [{"candidate_id": it["raw"].get("intent_id") or f"idx{it['index']}", "provenance": {"source": "llm", "index": it["index"]}, "raw": it["raw"]}
            for it in json.loads(RECORDED.read_text())["items"]]


def synthetic(scenario, task_type="filter", constraints=(), ranking=None, entity=None, attribute=None, answer_form=None, persona="career_switcher", journey="fit_schedule", cid="s1"):
    raw = {"intent_id": cid, "persona": persona, "journey": journey, "scenario": scenario, "task_type": task_type, "entity": entity, "attribute": attribute,
           "constraints": [dict(zip(("attribute", "operator", "value"), c)) for c in constraints], "ranking": ranking,
           "answer_form": answer_form or {"filter": "list", "lookup": "single", "best": "single", "open": "explanation"}[task_type]}
    return {"candidate_id": cid, "provenance": {"source": "synthetic-test"}, "raw": raw}


@pytest.fixture(scope="module")
def larkspur():
    site = get("larkspur")
    return site, K.view(site)


def ev(larkspur, cands, **kw):
    site, view = larkspur
    return E2.TaskEvaluatorV2(site, view, X.CONTEXT, **kw).evaluate(cands)


def strip(records):
    return [{k: v for k, v in r.items() if k != "_accepted"} for r in records]


# --------------------------------------------------------------------------------------------------------------------------- v1 parity
def test_v1_code_is_unchanged():
    for path, sha in PINNED.items():
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == sha, f"{path} changed: evaluator/grader/gate v1 must stay unchanged"


@pytest.mark.parametrize("source", ["fixture", "recorded"])
def test_checks_disabled_reproduces_evaluator_v1_exactly(larkspur, source):
    cands = fixture_candidates() if source == "fixture" else recorded_candidates()
    site, view = larkspur
    v1 = E1.TaskEvaluator(site, view, X.CONTEXT).evaluate(cands)
    v2_off = E2.TaskEvaluatorV2(site, view, X.CONTEXT, checks=False).evaluate(cands)
    assert len(cands) == 20
    assert json.dumps(strip(v1), sort_keys=True, default=str) == json.dumps(strip(v2_off), sort_keys=True, default=str)
    assert [r["hard_pass"] for r in v1] == [r["hard_pass"] for r in v2_off] and [r["decision"] for r in v1] == [r["decision"] for r in v2_off]


@pytest.mark.parametrize("source", ["fixture", "recorded"])
def test_checks_enabled_embed_v1_untouched_and_never_relax_v1_gates(larkspur, source):
    cands = fixture_candidates() if source == "fixture" else recorded_candidates()
    site, view = larkspur
    v1 = {r["candidate_id"]: r for r in strip(E1.TaskEvaluator(site, view, X.CONTEXT).evaluate(cands))}
    for r in ev(larkspur, cands):
        cid = r["derived_from"] or r["candidate_id"]
        assert json.dumps(r["v1"], sort_keys=True, default=str) == json.dumps(v1[cid], sort_keys=True, default=str)
        if r["admission"] in ("natural", "assisted") and r["kind"] in ("page_fact", "item_set", "extremum"):
            nonwording = {k: g for k, g in v1[cid]["hard_gates"].items() if k != "executable_wording_unambiguous"}
            assert all(g["pass"] for g in nonwording.values())                                   # every v1 hard gate except the wording rule
            if r["admission"] == "assisted":
                assert v1[cid]["hard_pass"] and r["wording"]["executed"] == v1[cid]["wordings"]["restated_question"]   # the full v1 gate on the restated text


def test_fixture_natural_admissions_equal_v1_passes(larkspur):
    recs = ev(larkspur, fixture_candidates())
    natural = {r["candidate_id"] for r in recs if r["admission"] == "natural"}
    assert natural == {"f01", "f02", "f03", "f05", "f06", "f07", "f15", "f18"}
    assert {r["candidate_id"]: r["wording"]["category"] for r in recs if r["admission"] in ("rubric", "human_review")} == {"f13": "natural_judgment", "f14": "natural_judgment"}
    for cid, why in (("f20", "the question contains the expected answer"), ("f04", "unique"), ("f19", "schema_valid"), ("f16", "grounded")):
        r = next(x for x in recs if x["candidate_id"] == cid)
        assert r["admission"] == "rejected" and any(why in x for x in r["rejection_reasons"])


# --------------------------------------------------------------------------------------------------------------------------- categories
def test_recorded_proposals_category_distribution(larkspur):
    recs = ev(larkspur, recorded_candidates())
    d = E2.distribution(recs)
    assert d["categories"] == {"natural_verifiable": 12, "natural_underspecified": 5, "natural_judgment": 1, "none (rejected before classification)": 2}
    assert d["admissions"] == {"natural": 12, "preserved_unexecuted": 5, "rubric": 1, "rejected": 2} and d["assisted_derivatives"] == 5
    for r in recs:
        if r["admission"] == "rejected":
            assert r["rejection_reasons"][0].startswith("not_expressible")                       # the two ranked-within-a-filter intents (M2b)


@pytest.mark.parametrize("scenario,constraints,cue", [
    ("I just graduated and money is tight. What courses do you have for under a tight budget?", [("course fee", "at_most", "$180")], "budget"),
    ("Which courses only last a few weeks?", [("duration", "at_most", "4 weeks")], "a few weeks"),
    ("Which low-cost courses still have several places left?", [("course fee", "at_most", "$250"), ("seats left", "at_least", "5")], "several"),
])
def test_implied_thresholds_are_preserved_as_underspecified_never_invented(larkspur, scenario, constraints, cue):
    recs = ev(larkspur, [synthetic(scenario, constraints=constraints, journey="find_affordable")])
    keep = recs[0]
    assert keep["admission"] == "preserved_unexecuted" and keep["wording"]["category"] == "natural_underspecified"
    assert keep["wording"]["executed"] is None and keep["verifiability"] == "human_review" and keep["expected_answer"] is None
    assert any(cue in u for u in keep["wording"]["unresolved"]) and keep["wording"]["customer"] == scenario
    derived = [r for r in recs if r["derived_from"]]
    if derived:                                                                                      # labelled assisted, never natural
        a = derived[0]
        assert a["wording"]["category"] == "assisted_restatement" and a["wording"]["condition"] == "assisted" and a["wording"]["executed"] != scenario
        assert all(x.startswith("generator assumption") for x in a["wording"]["assumptions"][:len(keep["wording"]["unresolved"])])


def test_value_in_two_domains_is_ambiguous():
    view = K.view(get("larkspur"))
    view = {**view, "attributes": view["attributes"] + [{"attribute": "region", "kind": "text", "unit": None, "values": ["Riverside", "Hills"]}]}
    a = Analyser(view).analyse("Which courses are at Riverside?", {"kind": "item_set", "listing": "/courses", "conditions": [{"label": "campus", "op": "eq", "value": "Riverside"}]})
    assert a.verdict() == "underspecified" and a.traces[0].status == "ambiguous" and "campus" in a.traces[0].detail and "region" in a.traces[0].detail
    named = Analyser(view).analyse("Which courses are at the Riverside campus?", {"kind": "item_set", "listing": "/courses", "conditions": [{"label": "campus", "op": "eq", "value": "Riverside"}]})
    assert named.verdict() == "verifiable"                                                          # naming the field resolves the collision


def test_money_cue_is_ambiguous_when_the_catalogue_has_several_money_attributes():
    view = K.view(get("ironbark"))
    item = view["items"][0]
    a = Analyser(view).analyse(f"How much is the {item['name']}?", {"kind": "page_fact", "page": item["page"], "label": "per day"})
    assert a.verdict() == "underspecified" and any(t.status == "ambiguous" for t in a.traces)
    b = Analyser(view).analyse(f"What is the per day rate for the {item['name']}?", {"kind": "page_fact", "page": item["page"], "label": "per day"})
    assert b.verdict() == "verifiable"


@pytest.mark.parametrize("scenario,constraints,expect", [
    ("Which courses cost under $250?", [("course fee", "at_most", "$250")], "intent_not_preserved"),           # comparator changed
    ("Which beginner courses run on Saturdays?", [("class day", "equals", "Saturday")], "intent_not_preserved"),  # stated value dropped
    ("I can only do weekends. Which courses run then?", [("class day", "equals", "Saturday")], "intent_not_preserved"),   # weekend narrowed to Saturday
    ("Which courses run on Saturdays?", [("class day", "equals", "Saturday"), ("materials", "equals", "Included")], "assisted_only"),  # constraint added
    ("I work Monday to Wednesday. Which courses are held on Saturdays?", [("class day", "equals", "Saturday")], "verifiable"),          # negative context
    ("Which intermediate courses still have seats?", [("level", "equals", "Intermediate"), ("seats left", "greater_than", "0")], "verifiable"),
    ("Which courses cost $250 or less and run for six weeks or less?", [("course fee", "at_most", "$250"), ("duration", "at_most", "6 weeks")], "verifiable"),
    ("I need a course that still has at least 5 seats left. What qualifies?", [("seats left", "at_least", "5")], "verifiable"),          # M6 false rejection: 'at least' is a comparator
    ("Which courses cost at most $300 and have at least 5 seats left?", [("course fee", "at_most", "$300"), ("seats left", "at_least", "5")], "verifiable"),
    ("Which course has the most seats left?", [("course fee", "at_most", "$300")], "intent_not_preserved"),                              # a real superlative is still caught
])
def test_intent_preservation_both_ways(larkspur, scenario, constraints, expect):
    from agent_readiness.research.taskplan.verify import OPS
    crit = {"kind": "item_set", "listing": "/courses", "conditions": [{"label": a, "op": OPS[o], "value": v} for a, o, v in constraints]}
    a = Analyser(larkspur[1]).analyse(scenario, crit)
    assert a.verdict() == expect, a.as_dict()


def test_added_constraint_is_assisted_with_recorded_assumption(larkspur):
    recs = ev(larkspur, [synthetic("Which courses run on Saturdays?", constraints=[("class day", "equals", "Saturday"), ("materials", "equals", "Included")])])
    assert len(recs) == 1 and recs[0]["admission"] == "assisted" and recs[0]["wording"]["category"] == "assisted_restatement"
    assert any("materials" in x and "not stated by the customer" in x for x in recs[0]["wording"]["assumptions"])


def test_leaked_answer_is_rejected_for_natural_wording(larkspur):
    recs = ev(larkspur, [synthetic("Is the Beginners yoga fee $150? What is the course fee for Beginners yoga?", task_type="lookup", entity="Beginners yoga",
                                   attribute="course fee", journey="find_affordable")])
    assert recs[0]["admission"] == "rejected" and any("contains the expected answer" in x for x in recs[0]["rejection_reasons"])


def test_interpretation_decisions_are_recorded(larkspur):
    recs = ev(larkspur, [synthetic("I need a course at Northside that meets on Tuesdays. What runs then?", constraints=[("campus", "equals", "Northside"), ("class day", "equals", "Tuesday")])])
    r = recs[0]
    assert r["admission"] == "natural" and r["wording"]["executed"] == r["wording"]["customer"]
    joined = " ".join(r["wording"]["interpretation_decisions"])
    assert "implied by 'northside'" in joined and "inflected form of 'Tuesday'" in joined and "replaced by gate-nl-1" in joined


# --------------------------------------------------------------------------------------------------------------------------- records, privacy, boundary
@pytest.mark.parametrize("source", ["fixture", "recorded"])
def test_outputs_map_one_to_one_onto_m1_records_and_store(tmp_path, larkspur, source):
    site, view = larkspur
    recs = ev(larkspur, fixture_candidates() if source == "fixture" else recorded_candidates())
    store = WriteOnceStore(tmp_path / "store")
    snap = site.snapshot("original").sha256
    inputs = (InputRef(kind="catalogue", name="larkspur", sha256=K.fingerprint(view)), InputRef(kind="context", name="larkspur-synthetic", sha256=X.fingerprint()))
    built = 0
    for r in recs:
        if r["admission"] == "rejected":
            continue
        task, priv = R2.build(r, site="larkspur", snapshot_sha256=snap, oracle_label=site.oracle().label, created_at="2026-11-02T12:00:00+00:00", inputs=inputs, tool_version="test")
        if priv:
            store.put(priv)
        sha = store.put(task)
        assert store.get("task", sha) == task and task.wording.category == r["wording"]["category"]
        assert task.condition == r["wording"]["condition"] and (task.private_sha256 is not None) == (r["verifiability"] == "deterministic")
        if task.wording.category == "natural_verifiable":
            assert task.wording.executed == task.wording.customer
        built += 1
    assert built >= 10


def _answer_strings(r):
    t = r["expected_answer"]
    return [t] if isinstance(t, str) else list(t or [])


def test_public_views_carry_no_answers_or_answer_pages(larkspur):
    site, view = larkspur
    pages = {it["name"]: it["page"] for it in view["items"]}
    recs = ev(larkspur, fixture_candidates())
    for r in recs:
        pub = json.dumps(E2.public(r))
        assert "expected_answer" not in pub and "_accepted" not in pub
        for ans in _answer_strings(r):
            assert json.dumps(ans) not in pub and (len(ans) < 4 or ans not in pub), (r["candidate_id"], ans)
            if ans in pages and r["kind"] != "page_fact":
                assert pages[ans] not in pub, (r["candidate_id"], pages[ans])        # evidence page paths of answer items are withheld
    # finding recorded in the M2 report: the v1 public view keeps evidence page paths, which for set tasks name answer items
    f02 = next(x for x in E1.TaskEvaluator(site, view, X.CONTEXT).evaluate(fixture_candidates()) if x["candidate_id"] == "f02")
    assert any(pages[a] in json.dumps(E1.public(f02)) for a in f02["expected_answer"] if a in pages and pages[a] != "/courses")


def test_task_records_publish_only_criterion_named_evidence_pages(larkspur):
    recs = [r for r in ev(larkspur, fixture_candidates()) if r["verifiability"] == "deterministic"]
    for r in recs:
        task, priv = R2.build(r, site="larkspur", snapshot_sha256="b" * 64, oracle_label="x", created_at="2026-11-02T12:00:00+00:00",
                              inputs=(InputRef(kind="catalogue", name="larkspur", sha256="a" * 64),), tool_version="t")
        assert set(task.spec.evidence_paths) <= {r["specification"].get("listing"), r["specification"].get("page")}
        assert priv.expected["truth"] == r["expected_answer"] and priv.spec_sha256 == content_hash(task.spec)


def test_deterministic_and_fingerprinted(larkspur):
    a = [E2.public(r) for r in ev(larkspur, fixture_candidates())]
    b = [E2.public(r) for r in ev(larkspur, fixture_candidates())]
    assert a == b and a[0]["evaluator"]["version"] == "taskeval-2" and a[0]["evaluator"]["v1"]["version"] == "taskeval-1"
    assert E2.config_fingerprint() != E2.config_fingerprint({**E2.CONFIG, "assisted_from_generator_assumptions": False})


def test_coverage_matrix_and_targets(larkspur):
    recs = ev(larkspur, fixture_candidates())
    cov = E2.coverage(recs, X.CONTEXT)
    assert cov["deterministic"] == 8 and cov["rubric"] == 1 and cov["natural_share"] == 1.0
    assert cov["capabilities"]["multi_condition_filter"] == 4 and cov["capabilities"]["policy_rubric"] == 1
    assert set(cov["matrix"]) == {p["id"] for p in X.CONTEXT["personas"]} and "natural_share_note" in cov
    assert all("persona" in g or "journey" in g or "capabilit" in g or "share" in g or "pair" in g or "task" in g for g in cov["gaps"])


def test_stage_a_boundary_still_clean():
    assert B.forbidden_imports(ROOT / "src/agent_readiness/suites") == []


def test_fingerprints_are_identical_across_processes():
    """Suite and task hashes embed the evaluator fingerprint: it may not depend on per-process hash randomisation."""
    import subprocess
    import sys
    code = "from agent_readiness.taskeval.v2 import evaluator as E; print(E.config_fingerprint({**E.CONFIG, 'new_kinds': ['ranked_subset', 'either_of']}))"
    outs = {subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=120, env={**__import__("os").environ, "PYTHONHASHSEED": str(seed)}).stdout.strip()
            for seed in (1, 2, 3)}
    assert len(outs) == 1 and len(next(iter(outs))) == 16
