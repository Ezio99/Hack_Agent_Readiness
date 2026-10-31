"""reach_page targets (paths or unique titles) and the goal-bound prompt's distribution / scope guidance. Offline only; no provider is called."""
import pytest

from agent_readiness.exp2 import snapshot as S
from agent_readiness.investigate.inspect.profile import build_profile
from agent_readiness.investigate.taskgen import goal as G, propose
from agent_readiness.investigate.taskgen.criteria import CriterionError, compile_criterion, resolve_target
from agent_readiness.investigate.taskgen.gate import Accepted, Draft, evaluate

_state = {}
QUESTION = "From the home page, find the page that lists the cutting equipment you can hire."
PATH, TITLE = "/hire/category/cutting", "Cutting | Ironbark Hire Co."


def profile():
    if "p" not in _state:
        _state["p"] = build_profile(S.snapshot("control"))
    return _state["p"]


def draft(target, question=QUESTION):
    return Draft(question, "/", {"kind": "reach_page", "target": target}, "model", "r")


def test_a_captured_path_is_kept_as_is_and_a_unique_title_resolves_to_its_path():
    p = profile()
    assert resolve_target(p, PATH) == PATH
    assert resolve_target(p, TITLE) == PATH
    assert resolve_target(p, "  cutting |  IRONBARK hire co. ") == PATH, "case and spacing are ignored"
    assert compile_criterion({"kind": "reach_page", "target": TITLE}, p).truth == compile_criterion({"kind": "reach_page", "target": PATH}, p).truth == TITLE


def test_a_path_always_wins_over_a_title_that_equals_another_pages_path():
    pr = {"pages": {"/a": {"title": "/b"}, "/b": {"title": "B"}}}
    assert resolve_target(pr, "/b") == "/b"


def test_an_ambiguous_title_is_refused_and_the_message_says_so():
    p = profile()
    with pytest.raises(CriterionError, match=r"title matches \d+ pages"):
        resolve_target(p, "Hire equipment | Ironbark Hire Co.")
    r = evaluate(draft("Hire equipment | Ironbark Hire Co."), p, [])
    assert not isinstance(r, Accepted) and "title matches" in r.reason and "use the page path" in r.reason


def test_a_missing_target_is_refused_with_an_accurate_message():
    p = profile()
    for t in ("No such page | Ironbark Hire Co.", "/no/such/path", ""):
        r = evaluate(draft(t), p, [])
        assert not isinstance(r, Accepted) and "neither a captured page path nor the title" in r.reason, (t, r)
    assert "is not part of the snapshot" not in r.reason


def test_the_gate_stores_the_resolved_path_so_title_and_path_forms_are_the_same_task():
    p = profile()
    a = evaluate(draft(TITLE), p, [])
    assert isinstance(a, Accepted) and a.criterion["target"] == PATH and a.draft.criterion["target"] == TITLE and a.compiled.evidence_paths == [PATH]
    b = evaluate(draft(PATH, "Starting at the home page, locate the page that lists the saws and cutters for hire."), p, [a])
    assert not isinstance(b, Accepted) and "duplicate" in b.reason, "the same page by path is a duplicate of the same page by title"
    c = evaluate(draft(PATH), p, [])
    assert isinstance(c, Accepted) and c.fingerprint == a.fingerprint


def test_existing_gate_rules_still_apply_to_a_title_target():
    p = profile()
    r = evaluate(draft(TITLE, "Find the page titled Cutting | Ironbark Hire Co. please"), p, [])
    assert not isinstance(r, Accepted), "a question that names the target page's title is still rejected by the unchanged leak rules"


def test_the_goal_bound_prompt_states_accepted_target_formats_distribution_and_scope_without_site_specifics():
    t = G.bound_text("Can a shopper compare X and Y of the cheapest widgets?")
    assert "page path exactly as written in the summary" in t and "exact title" in t
    assert "preference, not a quota" in t and "name its entity scope" in t and "different items" in t
    for site_specific in ("Ironbark", "tile saw", "chainsaw", "cutting", "$", "Marrickville"):
        assert site_specific not in t, site_specific


def test_prompts_that_are_not_goal_bound_are_unchanged_by_the_new_guidance():
    p = profile()
    plain = propose.build_prompt(p, 4, None, None, propose.BATCH_ANGLES[0])
    assert "page path exactly as written" not in plain and "entity scope" not in plain
    assert all("EVALUATION GOAL" not in r.messages[1]["content"] for r in propose.batch_requests(p, None))
