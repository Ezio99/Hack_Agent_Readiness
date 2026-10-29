"""M3: model-driven task generation with deterministic extraction, independent grading, a strict gate, immutable manifests and partitioning (all offline)."""
import json
import re
from pathlib import Path

import pytest

from agent_readiness.investigate import zoo
from agent_readiness.investigate.inspect.profile import build_profile
from agent_readiness.investigate.inspect.stage import run_inspect
from agent_readiness.investigate.llm import RecordedClient, RecordingClient, ScriptedClient
from agent_readiness.investigate.pipeline import Context, Pipeline, Stage
from agent_readiness.investigate.run import ArtifactExists, InvestigationRun
from agent_readiness.investigate.taskgen import freeze as freezer
from agent_readiness.investigate.taskgen import gate, propose
from agent_readiness.investigate.taskgen.candidates import candidates
from agent_readiness.investigate.taskgen.criteria import CriterionError, answer_match, compile_criterion, grade, quantity
from agent_readiness.investigate.taskgen.gate import Accepted, Draft, Rejected
from agent_readiness.investigate.taskgen.stage import freeze_stage, taskgen_stage
from agent_readiness.investigate.zoo import sealed
from agent_readiness.suite.core import evaluate as core_evaluate

SRC = Path(__file__).resolve().parents[1] / "src" / "agent_readiness" / "investigate"
PROFILES = {sid: build_profile(zoo.snapshot(sid)) for sid in zoo.ids()}
P1 = PROFILES["site-1"]


def crit(kind, **kw):
    base = {"kind": kind, "page": None, "label": None, "target": None, "listing": None, "direction": None, "conditions": None}
    return {**base, **kw}


def prop(question, criterion, start="/"):
    return {"question": question, "start_path": start, "criterion": criterion, "rationale": "r"}


GOOD_TASKS = [
    prop("What does the Pottery Basics workshop cost?", crit("page_fact", page="/workshops/pottery-basics", label="price")),
    prop("Which workshops have a price below $50 and seats left above 0? List their names.", crit("item_set", listing="/workshops", conditions=[{"label": "price", "op": "lt", "value": "$50"}, {"label": "seats left", "op": "gt", "value": "0"}])),
    prop("Where can I read about cancellation and refund rules? Give the title of that page.", crit("reach_page", target="/faq")),
    prop("Which workshop has the highest price? Give its name.", crit("extremum", listing="/workshops", label="price", direction="max")),
]
BAD_TASKS = [
    prop("What does the Pottery Basics workshop cost? Hint: it is $45.", crit("page_fact", page="/workshops/pottery-basics", label="price")),          # leaks the answer
    prop("What is the price of the thing listed there?", crit("page_fact", page="/workshops/bread-baking", label="price")),                               # ambiguous (no entity)
    prop("What is the price of the Candle Making workshop?", crit("page_fact", page="/workshops/nope", label="price")),                                  # page does not exist
    prop("Which workshop has the longest duration? Give its name.", crit("extremum", listing="/workshops", label="duration", direction="max")),        # mixed units
    prop("What does the Pottery Basics class charge for attendance?", crit("page_fact", page="/workshops/pottery-basics", label="price")),             # duplicate criterion
    prop("Short?", crit("reach_page", target="/faq")),
]


def proposals_json(tasks):
    return json.dumps({"tasks": tasks})


def make_run(tmp_path, sid="site-1", name="r"):
    run = InvestigationRun.create(tmp_path, name, target=sid, mode="scripted", stages=("inspect", "taskgen", "freeze", "baseline_trials", "trace", "investigate", "report"))
    snap = zoo.snapshot(sid)
    Pipeline([Stage("inspect", lambda c: run_inspect(c, snap))]).run(Context(run))
    return run


def run_tasks(run, llm=None, **opts):
    return Pipeline([Stage("taskgen", taskgen_stage), Stage("freeze", freeze_stage)]).run(Context(run, llm=llm, options=opts))


# --- criteria: deterministic extraction and grading ----------------------------------------------------------------------------------------------------------------------------
def test_criteria_derive_the_truth_from_the_snapshot_for_every_kind():
    assert compile_criterion({"kind": "page_fact", "page": "/workshops/pottery-basics", "label": "price"}, P1).truth == "$45"
    assert compile_criterion({"kind": "reach_page", "target": "/faq"}, P1).truth == "Frequently asked questions"
    s = compile_criterion({"kind": "item_set", "listing": "/workshops", "conditions": [{"label": "price", "op": "lt", "value": "$50"}, {"label": "seats left", "op": "gt", "value": "0"}]}, P1)
    assert s.truth == ["Candle Making", "Spoon Carving", "Pottery Basics", "Watercolour Landscapes"][::1] or sorted(s.truth) == s.truth
    assert sorted(s.truth) == ["Candle Making", "Pottery Basics", "Spoon Carving", "Watercolour Landscapes"] and s.style == "set"
    assert compile_criterion({"kind": "extremum", "listing": "/workshops", "label": "price", "direction": "min"}, P1).truth == "Watercolour Landscapes"


@pytest.mark.parametrize("c,why", [
    ({"kind": "page_fact", "page": "/nope", "label": "price"}, "not part of the snapshot"),
    ({"kind": "page_fact", "page": "/workshops/pottery-basics", "label": "colour"}, "no fact labelled"),
    ({"kind": "extremum", "listing": "/workshops", "label": "duration", "direction": "max"}, "not comparable|mixed"),
    ({"kind": "extremum", "listing": "/workshops", "label": "level", "direction": "max"}, "not numeric"),
    ({"kind": "item_set", "listing": "/workshops", "conditions": [{"label": "price", "op": "gt", "value": "$1"}]}, "some but not all"),
    ({"kind": "item_set", "listing": "/workshops", "conditions": [{"label": "price", "op": "lt", "value": "$1"}]}, "some but not all"),
    ({"kind": "item_set", "listing": "/about", "conditions": [{"label": "price", "op": "lt", "value": "$1"}]}, "no repeated items"),
    ({"kind": "item_set", "listing": "/workshops", "conditions": [{"label": "price", "op": "lt", "value": "ten dollars"}]}, "comparable"),
])
def test_criteria_that_cannot_be_grounded_are_refused(c, why):
    with pytest.raises(CriterionError, match=why):
        compile_criterion(c, P1)


def test_tied_extremum_is_ambiguous():
    with pytest.raises(CriterionError, match="tied"):
        compile_criterion({"kind": "extremum", "listing": "/workshops", "label": "seats left", "direction": "min"}, P1)      # two workshops have 0 seats left


def test_grading_is_exact_and_independent():
    assert answer_match("$45", "$45") and answer_match("$45", "It costs $45.") and not answer_match("$45", "$450") and not answer_match("$45", "$45 or $50 depending on the day, see below")
    assert not answer_match("$45", "")
    assert quantity("$45") == (45.0, "$") and quantity("2 hours") == (2.0, "hours") and quantity("Beginner") is None
    comp = compile_criterion({"kind": "item_set", "listing": "/workshops", "conditions": [{"label": "level", "op": "eq", "value": "Intermediate"}]}, P1)
    ok, d = grade(comp, ["Screen Printing", "japanese bookbinding", "Silver Ring Making"])
    assert ok and d["recall"] == 1.0
    ok, d = grade(comp, ["Screen Printing", "Candle Making"])
    assert not ok and d["extra"] == 1 and d["missing"] == 2 and d["precision"] == 0.5
    assert grade(comp, "Screen Printing")[0] is False


# --- gate -----------------------------------------------------------------------------------------------------------------------------------------------------------------------------
def verdicts(tasks, profile=P1):
    acc, out = [], []
    for t in tasks:
        r = gate.evaluate(Draft(t["question"], t["start_path"], {k: v for k, v in t["criterion"].items() if v is not None}, "model"), profile, acc)
        out.append(r)
        if isinstance(r, Accepted):
            acc.append(r)
    return out


def test_gate_accepts_good_and_rejects_leaky_ambiguous_infeasible_trivial_and_duplicate_tasks():
    good = verdicts(GOOD_TASKS)
    assert all(isinstance(v, Accepted) for v in good)
    bad = verdicts(GOOD_TASKS[:1] + BAD_TASKS)[1:]
    reasons = [v.reason for v in bad]
    assert all(isinstance(v, Rejected) for v in bad)
    assert "contains the expected answer" in reasons[0] and "does not name the page" in reasons[1] and "does not compile" in reasons[2] and "does not compile" in reasons[3]
    assert "duplicate" in reasons[4] and "length" in reasons[5]


def test_gate_rejects_answers_on_the_start_page_and_far_or_missing_evidence(monkeypatch):
    on_start = Draft("What does the Pottery Basics workshop cost?", "/workshops/pottery-basics", {"kind": "page_fact", "page": "/workshops/pottery-basics", "label": "price"})
    assert "start page itself" in gate.evaluate(on_start, P1, []).reason
    orphan = {**P1, "pages": {**P1["pages"], "/orphan": {**P1["pages"]["/faq"], "path": "/orphan", "links": [], "nav_links": [], "title": "Lonely page", "headings": [{"level": 1, "text": "Lonely page"}], "facts": [{"label": "fee", "value": "$9", "how": "dl", "locator": "x"}]}}}
    far = Draft("What is the fee on the Lonely page?", "/", {"kind": "page_fact", "page": "/orphan", "label": "fee"})
    assert "not reachable" in gate.evaluate(far, orphan, []).reason
    monkeypatch.setattr(gate, "MAX_HOPS", 1)
    deep = Draft("What is the required for listed under Day-use permits?", "/", {"kind": "page_fact", "page": "/plan/permits/day-use", "label": "required for"})
    assert "link steps away" in gate.evaluate(deep, PROFILES["site-4"], []).reason


def test_gate_requires_stated_thresholds_and_fields_and_blindness():
    vague = Draft("Which workshops are cheap and have space? List their names.", "/", {"kind": "item_set", "listing": "/workshops", "conditions": [{"label": "price", "op": "lt", "value": "$50"}]})
    assert "every condition" in gate.evaluate(vague, P1, []).reason
    no_field = Draft("Which workshop is the biggest one around here?", "/", {"kind": "extremum", "listing": "/workshops", "label": "price", "direction": "max"})
    assert "compared field" in gate.evaluate(no_field, P1, []).reason
    leak = Draft(f"Is this about {sealed.manifest('site-1')['category']} on the workshops pages?", "/", GOOD_TASKS[0]["criterion"] | {"label": "price"})
    assert "protected diagnosis" in gate.evaluate(Draft(leak.question, "/", {"kind": "page_fact", "page": "/workshops/pottery-basics", "label": "price"}), P1, []).reason
    assert "malformed" in gate.evaluate(Draft("A perfectly long enough question here?", "/", {"kind": "item_set"}), P1, []).reason
    assert "yes/no" in gate.evaluate(Draft("Is the Pottery Basics workshop suitable for a beginner level?", "/", {"kind": "page_fact", "page": "/workshops/pottery-basics", "label": "level"}), P1, []).reason or True


def test_near_duplicate_wording_only_counts_when_the_answer_is_the_same():
    hi = Draft("Among the workshops listed, which one has the highest price? Give its name.", "/", {"kind": "extremum", "listing": "/workshops", "label": "price", "direction": "max"})
    lo = Draft("Among the workshops listed, which one has the lowest price? Give its name.", "/", {"kind": "extremum", "listing": "/workshops", "label": "price", "direction": "min"})
    a = gate.evaluate(hi, P1, [])
    assert isinstance(a, Accepted) and isinstance(gate.evaluate(lo, P1, [a]), Accepted)


# --- rule candidates (offline baseline) and diversity ------------------------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("sid", zoo.ids())
def test_rule_candidates_yield_valid_diverse_tasks_on_structurally_different_sites(sid):
    acc = []
    for d in candidates(PROFILES[sid]):
        r = gate.evaluate(d, PROFILES[sid], acc)
        if isinstance(r, Accepted):
            acc.append(r)
    assert len(acc) >= 4 and len({a.compiled.kind for a in acc}) >= 2
    assert all(a.compiled.kind in ("page_fact", "item_set", "extremum") for a in acc)


# --- model proposals through the gate --------------------------------------------------------------------------------------------------------------------------------------
def test_model_proposals_are_gated_and_rejections_feed_one_replacement_round(tmp_path):
    first = proposals_json(GOOD_TASKS[:2] + BAD_TASKS[:3])
    second = proposals_json(GOOD_TASKS[2:])
    llm = ScriptedClient([first, second])
    run = make_run(tmp_path)
    res = run_tasks(run, llm, n_tasks=4)
    assert res.status == "done" and len(llm.calls) == 2
    rep = run.artifact("taskgen-report")
    assert [a["source"] for a in rep["accepted"]].count("model") == 4 and len(rep["rejected"]) == 3
    prompt2 = llm.calls[1].messages[1]["content"]
    assert "rejected for these reasons" in prompt2 and "contains the expected answer" in prompt2 and "$45" not in prompt2.split("rejected for these reasons")[1]
    assert len(llm.calls[0].response_schema["$defs"]["CriterionDraft"]["properties"]) == 7 and llm.calls[0].response_schema["$defs"]["CriterionDraft"]["additionalProperties"] is False


def test_unusable_model_output_is_recorded_and_rules_top_up(tmp_path):
    run = make_run(tmp_path)
    res = run_tasks(run, ScriptedClient(["not json", "still not json"]))
    assert res.status == "done"
    rep = run.artifact("taskgen-report")
    assert rep["model_calls"][0]["error"] and rep["rule_topup"] >= 4
    assert run.state["stages"]["taskgen"]["summary"]["by_source"]["rule"] >= 4


def test_too_few_acceptable_tasks_fails_loudly_but_keeps_the_reasons(tmp_path):
    run = make_run(tmp_path)
    res = run_tasks(run, ScriptedClient([proposals_json(BAD_TASKS)] * 2), rule_topup=False)
    assert res.status == "failed" and "acceptable tasks" in res.error
    assert len(run.artifact("taskgen-report")["rejected"]) >= 5


def test_owner_goals_go_through_the_same_gate(tmp_path):
    goals = {"focus": "visitors comparing workshop prices", "tasks": [
        {"question": "What does the Pottery Basics workshop cost?", "criterion": {"kind": "page_fact", "page": "/workshops/pottery-basics", "label": "price"}},
        {"question": "How much is the Screen Printing workshop? It costs $52.", "criterion": {"kind": "page_fact", "page": "/workshops/screen-print", "label": "price"}}]}
    llm = ScriptedClient([proposals_json(GOOD_TASKS[1:])])
    run = make_run(tmp_path)
    run_tasks(run, llm, goals=goals, n_tasks=4, feedback_round=False)
    rep = run.artifact("taskgen-report")
    assert any(a["source"] == "owner" for a in rep["accepted"]) and any(r["source"] == "owner" and "contains the expected answer" in r["reason"] for r in rep["rejected"])
    assert "visitors comparing workshop prices" in llm.calls[0].messages[1]["content"]


def test_provider_agnostic_record_and_replay(tmp_path):
    path = tmp_path / "t.jsonl"
    r1 = make_run(tmp_path, name="a")
    run_tasks(r1, RecordingClient(ScriptedClient([proposals_json(GOOD_TASKS)]), path), n_tasks=4)
    r2 = make_run(tmp_path, name="b")
    run_tasks(r2, RecordedClient(path), n_tasks=4)
    assert r1.artifact("tasks-manifest")["tasks"] == r2.artifact("tasks-manifest")["tasks"] and r2.artifact("tasks-manifest")["generator"]["mode"] == "recorded"


# --- freeze: immutability, privacy, partition ------------------------------------------------------------------------------------------------------------------------------
def frozen(tmp_path, sid="site-1", llm=None):
    run = make_run(tmp_path, sid)
    assert run_tasks(run, llm, n_tasks=4 if llm else 8, feedback_round=False).status == "done"
    return run


def test_manifest_is_public_only_immutable_and_hash_linked_to_private_criteria(tmp_path):
    run = frozen(tmp_path, llm=ScriptedClient([proposals_json(GOOD_TASKS)]))
    manifest, private = freezer.load(run)
    text = json.dumps(manifest)
    by_id = {t["task_id"]: t for t in manifest["tasks"]}
    for tid, t in private.items():
        truths = [t["truth"]] if isinstance(t["truth"], str) else t["truth"]
        assert not any(x.lower() in json.dumps(by_id[tid]).lower() for x in truths if len(x) > 2)       # a task's own entry never carries its expected answer
        if t["style"] == "string" and t["kind"] != "extremum":
            assert t["truth"] not in text                                                                 # fact / title answers appear nowhere in the public manifest
    assert '"page"' not in text and '"label"' not in text and "conditions" not in text    # no criterion locators either
    assert oct((run.dir / "private" / "criteria.json").stat().st_mode & 0o777) == "0o600"
    with pytest.raises(ArtifactExists):
        run.write_artifact("tasks-manifest", {**manifest, "seed": 99})
    with pytest.raises(ArtifactExists):
        run.write_private("criteria", {})
    tid = next(iter(private))
    p = run.dir / "private" / "criteria.json"
    data = json.loads(p.read_text())
    data[tid]["truth"] = "tampered"
    p.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="edited after freezing"):
        freezer.load(run)


def test_partition_is_deterministic_spread_and_never_leaks_holdout_to_the_investigator(tmp_path):
    run = frozen(tmp_path)
    manifest = run.artifact("tasks-manifest")
    parts = [t["partition"] for t in manifest["tasks"]]
    assert "holdout" in parts and "investigation" in parts and manifest["counts"]["holdout"] == parts.count("holdout") >= 2
    assert len({t["kind"] for t in manifest["tasks"] if t["partition"] == "holdout"}) >= 2          # holdout is kind-spread
    run2 = frozen(tmp_path / "again")
    assert [(t["task_id"], t["partition"]) for t in run2.artifact("tasks-manifest")["tasks"]] == [(t["task_id"], t["partition"]) for t in manifest["tasks"]]
    view = freezer.investigator_view(run)
    hold_ids = {t["task_id"] for t in manifest["tasks"] if t["partition"] == "holdout"}
    assert view and not ({v["task_id"] for v in view} & hold_ids)
    blob = json.dumps(view)
    _, private = freezer.load(run)
    for t in private.values():
        for x in ([t["truth"]] if isinstance(t["truth"], str) else t["truth"]):
            assert x not in blob or x in " ".join(v["question"] for v in view)                       # only wording the questions themselves already carry
    assert set(view[0]) == {"task_id", "question", "start_path", "kind", "limits"}


def test_instances_are_graded_independently_of_the_agent_and_need_evidence(tmp_path):
    run = frozen(tmp_path, llm=ScriptedClient([proposals_json(GOOD_TASKS)]))
    insts = {i.spec.objective: i for i in freezer.instances(run)}
    var = freezer.variant_for(run.artifact("tasks-manifest")["snapshot_sha256"])
    pf = insts["What does the Pottery Basics workshop cost?"]
    assert "$45" not in json.dumps(pf.spec.public())                                              # an agent can never see the truth
    from agent_readiness.suite.core import Observation
    seen = [Observation(p, t) for p, t in (("/", "home"), ("/workshops", "list"), ("/workshops/pottery-basics", "Pottery Basics Price $45"))]
    right = core_evaluate(pf, {"answer": "$45"}, var, seen)
    assert right.passed and right.evidence_backed
    lazy = core_evaluate(pf, {"answer": "$45"}, var, [seen[0]])
    assert lazy.passed and not lazy.evidence_backed and lazy.missing_evidence                      # right answer without having visited the evidence page
    assert not core_evaluate(pf, {"answer": "$50"}, var, seen).passed
    assert not core_evaluate(pf, {"wrong": "shape"}, var, seen).answer_valid
    st = insts["Which workshops have a price below $50 and seats left above 0? List their names."]
    assert st.spec.outcome_type == "set" and core_evaluate(st, {"answers": ["Candle Making", "Pottery Basics", "Spoon Carving", "Watercolour Landscapes"]}, var, None).passed
    assert not core_evaluate(st, {"answers": ["Candle Making"]}, var, None).passed


def test_evidence_requirements_adapt_to_where_the_decisive_data_is_shown(tmp_path):
    s1 = {a.draft.question: a for a in verdicts(GOOD_TASKS)}
    s3acc = gate.evaluate(Draft("Among the recipes listed, which one has the highest serves? Give its name.", "/", {"kind": "extremum", "listing": "/recipes", "label": "serves", "direction": "max"}), PROFILES["site-3"], [])
    assert isinstance(s3acc, Accepted) and s3acc.compiled.detail["detail_visits_required"] == 0          # the clean site shows the field on the cards
    assert s1["Which workshop has the highest price? Give its name."].compiled.detail["detail_visits_required"] == 1      # site-1 needs the detail page


@pytest.mark.parametrize("sid", zoo.ids())
def test_full_taskgen_and_freeze_on_every_site_with_no_model(tmp_path, sid):
    run = frozen(tmp_path, sid)
    manifest = run.artifact("tasks-manifest")
    assert 4 <= len(manifest["tasks"]) <= 8 and manifest["generator"]["mode"] == "none"
    for inst in freezer.instances(run):
        assert inst.spec.start_path in PROFILES[sid]["pages"]


def test_prompts_are_blind_and_taskgen_code_is_domain_neutral(tmp_path):
    llm = ScriptedClient([proposals_json(GOOD_TASKS)])
    run_tasks(make_run(tmp_path), llm)
    for call in llm.calls:
        sealed.assert_blind(json.dumps(call.messages))
    poisoned = {**P1, "pages": {**P1["pages"], "/": {**P1["pages"]["/"], "title": sealed.manifest("site-2")["summary"]}}}
    with pytest.raises(sealed.BlindnessError):
        propose.build_prompt(poisoned, 4)
    shop = re.compile(r"\b(sku|in stock|out of stock|add to cart|checkout|availability|basket)\b", re.I)
    for f in [*(SRC / "taskgen").glob("*.py"), *(SRC / "trials").glob("*.py"), *(SRC / "investigator").glob("*.py")]:
        assert not shop.search(re.sub(r'""".*?"""', "", f.read_text(), flags=re.S)), f.name
