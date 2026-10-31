"""Live product quality fixes: homepage-answerable tasks are tagged (not rejected) in live evaluations only, selection prefers navigation, category-scoped comparisons compile, coverage is exportable. Offline."""
import json
from types import SimpleNamespace

import pytest

from agent_readiness.exp2 import snapshot as S
from agent_readiness.investigate.inspect.profile import build_profile
from agent_readiness.investigate.run import InvestigationRun
from agent_readiness.investigate.taskgen import criteria, goal as G, freeze as freezer
from agent_readiness.investigate.taskgen.criteria import CriterionError, compile_criterion
from agent_readiness.investigate.taskgen.gate import FIRST_PAGE_TAG, Accepted, Draft, evaluate
from agent_readiness.live import jobs, worker

_state = {}


def profile():
    if "p" not in _state:
        _state["p"] = build_profile(S.snapshot("control"))
    return _state["p"]


CAT = "/hire/category/cutting"
EASY = Draft("What is the per day hire rate shown on the Wet tile saw 250 mm product page?", "/", {"kind": "page_fact", "page": "/hire/wet-tile-saw-250mm", "label": "per day"}, "model", "")
HARD = Draft("What is the per week hire charge listed for the Wet tile saw 250 mm?", "/", {"kind": "page_fact", "page": "/hire/wet-tile-saw-250mm", "label": "per week"}, "model", "")


# ------------------------------------------------------------------------------------------------------------------------------------------------ homepage-answerable tasks
def test_the_benchmark_rule_is_the_default_and_rejects_a_homepage_answerable_task():
    r = evaluate(EASY, profile(), [])
    assert not isinstance(r, Accepted) and r.reason == "the expected answer is visible on the start page"
    assert isinstance(evaluate(HARD, profile(), []), Accepted)
    assert evaluate(HARD, profile(), []).tags == []


def test_in_live_mode_the_same_task_is_kept_and_tagged_and_nothing_else_is_relaxed():
    a = evaluate(EASY, profile(), [], first_page="tag")
    assert isinstance(a, Accepted) and a.tags == [FIRST_PAGE_TAG] and a.compiled.truth == compile_criterion(EASY.criterion, profile()).truth
    assert evaluate(HARD, profile(), [], first_page="tag").tags == []
    leak = Draft("What is the per day hire rate of $65 for the Wet tile saw 250 mm?", "/", EASY.criterion, "model", "")
    assert not isinstance(evaluate(leak, profile(), [], first_page="tag"), Accepted), "an answer inside the question is still rejected"
    on_start = Draft("What is the heading on the home page?", "/", {"kind": "reach_page", "target": "/"}, "model", "")
    assert not isinstance(evaluate(on_start, profile(), [], first_page="tag"), Accepted), "evidence on the start page itself is still rejected"


def test_the_frozen_manifest_carries_the_tag_only_for_tagged_tasks_and_the_live_policy_is_in_the_approval_manifest(tmp_path):
    a = [evaluate(EASY, profile(), [], first_page="tag")]
    a.append(evaluate(HARD, profile(), a, first_page="tag"))
    m, _ = freezer.build(a, snapshot_sha256="x", generator={}, agent_profile="p")
    tagged = [t for t in m["tasks"] if "tags" in t]
    assert len(tagged) == 1 and tagged[0]["tags"] == [FIRST_PAGE_TAG] and len(m["tasks"]) == 2
    m2, _ = freezer.build([evaluate(HARD, profile(), [])], snapshot_sha256="x", generator={}, agent_profile="p")
    assert all("tags" not in t for t in m2["tasks"]), "benchmark and untagged manifests keep their previous shape"
    from agent_readiness.agent import ModelConfig
    assert worker.live_options(None, "g goal text", None, budget=2.0, cfg=ModelConfig())["first_page_policy"] == "tag"


def _assessed(cells, easy=False, hops=1):
    return {"goal_relevant": True, "aspects_matched": cells, "entities_touched": ["/x"], "first_page_answerable": easy, "nav_hops": hops}


def test_selection_covers_the_goal_first_then_prefers_tasks_that_need_navigation():
    easy_new = _assessed(["price"], easy=True)
    hard_same = _assessed(["price"], easy=False, hops=2)
    assert G.select([easy_new, hard_same], 1) == [1], "equal coverage: the navigation task wins"
    hard_other = _assessed(["availability"], easy=False)
    assert G.select([easy_new, hard_other], 2) == [0, 1]
    only_easy_covers = _assessed(["price", "availability"], easy=True)
    assert G.select([only_easy_covers, hard_other], 1) == [0], "an easy task is still chosen when it is the only one that adds coverage"
    assert G.select([_assessed(["price"], hops=1), _assessed(["price"], hops=3)], 1) == [1], "deeper navigation preferred on a tie"


# ------------------------------------------------------------------------------------------------------------------------------------------------ category-scoped comparisons
def test_a_category_page_compares_its_own_products_not_the_category_navigation_links():
    p = profile()
    ext = compile_criterion({"kind": "extremum", "listing": CAT, "label": "per day", "direction": "min"}, p)
    assert ext.truth == "Wet tile saw 250 mm" and ext.evidence_paths == [CAT]
    mx = compile_criterion({"kind": "extremum", "listing": CAT, "label": "per day", "direction": "max"}, p)
    assert mx.truth == "Petrol cut-off saw 350 mm"
    st = compile_criterion({"kind": "item_set", "listing": CAT, "conditions": [{"label": "per day", "op": "lt", "value": "$100"}]}, p)
    assert sorted(st.truth) == ["Petrol chainsaw 45 cm", "Wet tile saw 250 mm"] and st.detail["items"] == 3, "exactly the cutting tools, not 'All equipment' or the other categories"


def test_the_whole_catalogue_listing_is_unchanged_and_scoped_comparisons_pass_the_gate_with_the_category_named():
    p = profile()
    assert compile_criterion({"kind": "extremum", "listing": "/hire", "label": "per day", "direction": "min"}, p).truth == "Cordless drill driver kit 18 V"
    d = Draft("Among the cutting tools in the Cutting category, which has the lowest per day hire rate?", "/", {"kind": "extremum", "listing": CAT, "label": "per day", "direction": "min"}, "model", "")
    assert isinstance(evaluate(d, p, [], first_page="tag"), Accepted)


def test_edge_cases_still_fail_precisely():
    p = profile()
    with pytest.raises(CriterionError, match="missing, ambiguous or not numeric"):
        compile_criterion({"kind": "extremum", "listing": CAT, "label": "no such label", "direction": "min"}, p)
    with pytest.raises(CriterionError, match="missing or ambiguous"):
        compile_criterion({"kind": "item_set", "listing": CAT, "conditions": [{"label": "no such label", "op": "eq", "value": "x"}]}, p)
    with pytest.raises(CriterionError, match="no repeated items"):
        compile_criterion({"kind": "extremum", "listing": "/about", "label": "per day", "direction": "min"}, p)
    two = json.loads(json.dumps(p))
    for g in two["pages"][CAT]["item_groups"]:
        if len(g["items"]) == 3:
            g["items"] = g["items"][:2]
    with pytest.raises(CriterionError):
        compile_criterion({"kind": "extremum", "listing": CAT, "label": "per day", "direction": "min"}, two)


def test_items_without_labels_keep_the_largest_group_rule():
    p = profile()
    assert len(criteria._items(p, CAT)) == max(len(g["items"]) for g in p["pages"][CAT]["item_groups"] if sum(i["href"] in p["pages"] for i in g["items"]) >= 3)
    assert len(criteria._items(p, CAT, ("per day",))) == 3


# ------------------------------------------------------------------------------------------------------------------------------------------------ coverage in the export
def test_goal_coverage_is_none_for_runs_without_goal_bound_generation_and_complete_for_those_with(tmp_path):
    run = InvestigationRun.create(tmp_path, "r", target="ironbark", mode="live", stages=("inspect",))
    assert jobs.goal_coverage(run) is None
    run.write_artifact("taskgen-report", {"accepted": [], "rejected": []})
    assert jobs.goal_coverage(run) is None
    run = InvestigationRun.create(tmp_path, "r2", target="ironbark", mode="live", stages=("inspect",))
    prof = {"pages": {"/a": {"headings": [{"text": "Saw A"}], "title": "Saw A | Site"}, "/b": {"headings": [], "title": "Saw B | Site"}}}
    run.write_artifact("site-profile", prof)
    run.write_artifact("taskgen-report", {"accepted": [{"question": "q1", "source": "model", "kind": "page_fact", "fingerprint": "f", "tags": ["first_page_answerable"]}], "rejected": [],
        "goal_binding": {"selected": 1, "gate_accepted_tasks": 2, "relevant_tasks": 1, "assessments": [{"question": "q1", "first_page_answerable": True}],
                         "coverage": {"status": "partial", "covered": ["price"], "missing_supported": [], "entities_total": 2, "entities_covered": ["/a"], "partial_because": ["entities not covered: 1 of 2"]},
                         "analysis": {"asked_aspects": ["price"], "entity_items": ["/a", "/b"], "limitation_details": [{"aspect": "ordering", "kind": "verifier", "detail": "d"}]}}})
    c = jobs.goal_coverage(run)
    assert c["status"] == "partial" and [e["name"] for e in c["entities"]] == ["Saw A", "Saw B"] and [e["covered"] for e in c["entities"]] == [True, False]
    assert c["first_page_answerable_selected"] == 1 and c["limitations"][0]["aspect"] == "ordering" and "SELECTED" in c["note"]


def test_only_a_live_policy_changes_the_approval_manifest(tmp_path):
    from agent_readiness.investigate import flow
    from agent_readiness.agent import ModelConfig
    manifests = {}
    for pol in ("reject", "tag"):
        run, pipe, ctx = flow.build(tmp_path / pol, "p", "ironbark", mode="live", options={"snapshot": S.snapshot("control"), "goals": {"focus": "compare the hire price of cutting tools"}, "goal_binding": True,
                                                                                         "first_page_policy": pol, "model_config": ModelConfig(), "total_cap_usd": 2.0})
        assert pipe.run(ctx, until="inspect").status == "done"
        manifests[pol] = flow.taskgen_manifest(ctx)
    assert "first_page_policy" not in manifests["reject"] and manifests["tag"]["first_page_policy"] == "tag"
    assert {k: v for k, v in manifests["tag"].items() if k != "first_page_policy"} == manifests["reject"], "the policy is the only difference, so it is bound into the approval hash and nothing else moved"
