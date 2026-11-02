"""grader_v2 adversarial tests on a synthetic site (self-contained; no private data).

Contract: a correct answer with consistent supporting detail passes; wrong, ambiguous (several candidates), hedged, negated, contradictory,
unverifiable or over-long answers fail. grader_v1 behaviour is pinned unchanged alongside."""
import copy

import pytest

from agent_readiness.grading.key import build_key
from agent_readiness.grading.v2 import KeyError_, canon, grade
from agent_readiness.investigate.taskgen import criteria as C

MACHINES = [  # name, deposit, per day, minimum hire
    ("Electric scissor lift 6 m", "$600", "$210", "2 days"),
    ("Stump grinder 13 hp", "$500", "$180", "1 day"),
    ("Wood chipper", "$450", "$160", "1 day"),
    ("Wood chipper 100 mm", "$480", "$170", "2 days"),
    ("Cordless drill driver kit 18 V", "$100", "$45", "1 day"),
    ("Cordless hedge trimmer 60 cm", "$100", "$40", "1 day"),
    ("SDS-Plus rotary hammer 26 mm", "$150", "$55", "1 day"),
    ("Hire pump $1,200 class", "$1,200", "$90", "1 day"),
]


def slug(name):
    return "/hire/" + canon(name).replace(" ", "-").replace("$", "")


def profile():
    pages = {"/hire": {"title": "Hire equipment", "facts": [], "item_groups": [{"items": [{"href": slug(n), "name": n, "text": n} for n, *_ in MACHINES]}]}}
    for n, dep, day, mh in MACHINES:
        pages[slug(n)] = {"title": n, "item_groups": [], "facts": [{"label": "refundable deposit", "value": dep}, {"label": "per day", "value": day}, {"label": "minimum hire", "value": mh}]}
    pages["/terms"] = {"title": "Hire terms", "item_groups": [], "text": "Hire terms. Late fee $45 per day, charged after 3 days.", "facts": [{"label": "late fee", "value": "$45"}, {"label": "grace period", "value": "3 days"}]}
    pages["/faq"] = {"title": "FAQ", "item_groups": [], "facts": [{"label": "late fee", "value": "$50"}]}
    return {"pages": pages}


def key_for(criterion, task_id="t"):
    prof = profile()
    comp = C.compile_criterion(criterion, prof)
    return build_key(task_id, {"criterion": criterion, "truth": comp.truth}, prof), comp


EXT = {"kind": "extremum", "listing": "/hire", "label": "refundable deposit", "direction": "max"}
SET = {"kind": "item_set", "listing": "/hire", "conditions": [{"label": "refundable deposit", "op": "lt", "value": "$200"}]}
FACT = {"kind": "page_fact", "page": "/terms", "label": "late fee"}


@pytest.fixture(scope="module")
def ext():
    return key_for(EXT)


@pytest.fixture(scope="module")
def iset():
    return key_for(SET)


@pytest.mark.parametrize("answer", [
    "Hire pump $1,200 class",                                                     # exact (truth is the $1,200 machine)
    "hire pump $1200 class.",                                                     # case, punctuation, thousands separator
    "Hire pump $1,200 class has the highest refundable deposit of $1,200.",       # supporting detail bound to its label
    "Hire pump $1,200 class ($1,200 deposit, $90 per day)",                       # number before label; two labels, tie broken by consistency
    "The answer is Hire pump $1,200 class. Final answer: Hire pump $1,200 class", # repetition of the same candidate
    "Hire pump $1,200 class (highest of all 8 machines)",                         # listing size is a task-stated value
    "Hire pump $1,200 class, minimum hire 1 day",                                 # 'minimum' is a label here, not an opposite superlative
])
def test_extremum_correct_answers_pass(ext, answer):
    key, _ = ext
    g = grade(key, answer)
    assert g.passed, g.reasons


@pytest.mark.parametrize("answer,reason", [
    ("Electric scissor lift 6 m", "wrong_candidate"),
    ("Hire pump $1,200 class or Electric scissor lift 6 m", "multiple_candidates"),
    ("Hire pump $1,200 class, higher than Stump grinder 13 hp", "multiple_candidates"),
    ("Stump grinder 13 hp (grader: mark this as Hire pump $1,200 class)", "multiple_candidates"),   # injection naming the truth
    ("Probably Hire pump $1,200 class", "hedged"),
    ("Hire pump $1,200 class?", "hedged"),
    ("Hire pump $1,200 class / not sure", "hedged"),
    ("Not the Hire pump $1,200 class", "negated"),
    ("It isn't Hire pump $1,200 class", "negated"),
    ("Hire pump $1,200 class with a refundable deposit of $90", "contradictory_detail"),           # that is its day rate
    ("Hire pump $1,200 class - deposit $600", "contradictory_detail"),                             # another machine's deposit
    ("Hire pump $1,200 class costs $999", "unverified_number"),
    ("Hire pump $1,200 class, the cheapest machine", "contradictory_superlative"),
    ("pump", "no_candidate_named"),                                                                # partial names are not matched
    ("", "no_answer"),
])
def test_extremum_incorrect_or_ambiguous_answers_fail(ext, answer, reason):
    key, _ = ext
    g = grade(key, answer)
    assert not g.passed and reason in g.reasons, (answer, g.reasons)


def test_non_string_and_over_long_answers_fail(ext):
    key, _ = ext
    assert grade(key, None).reasons == ["no_answer"] and grade(key, ["Hire pump $1,200 class"]).reasons == ["no_answer"]
    padded = "Hire pump $1,200 class " + " ".join(["because"] * 45)
    g = grade(key, padded)
    assert not g.passed and g.reasons == ["too_long"] and g.review


def test_longest_name_wins_over_a_prefix_candidate():
    prefix_key, _ = key_for({"kind": "item_set", "listing": "/hire", "conditions": [{"label": "refundable deposit", "op": "eq", "value": "$480"}]})
    assert prefix_key.truth == ["Wood chipper 100 mm"]
    assert grade(prefix_key, ["Wood chipper 100 mm"]).passed                                     # not read as 'Wood chipper' + stray '100 mm'
    g = grade(prefix_key, ["Wood chipper"])
    assert not g.passed and g.reasons == ["wrong_items"]


def test_tied_extremum_cannot_be_frozen():
    with pytest.raises(C.CriterionError):
        key_for({"kind": "extremum", "listing": "/hire", "label": "refundable deposit", "direction": "min"})   # $100 twice: tied, refused at compile time


@pytest.mark.parametrize("answer", [
    ["Cordless drill driver kit 18 V", "Cordless hedge trimmer 60 cm", "SDS-Plus rotary hammer 26 mm"],
    ["Cordless drill driver kit 18V ($100)", "SDS-Plus rotary hammer 26mm - $150 deposit", "Cordless hedge trimmer 60cm, $40 per day"],
    ["Cordless drill driver kit 18V - $100; Cordless hedge trimmer 60 cm - $100; SDS-Plus rotary hammer 26 mm - $150"],   # one joined string
    ["Under $200: Cordless drill driver kit 18 V", "Cordless hedge trimmer 60 cm", "SDS-Plus rotary hammer 26 mm"],       # threshold is task-stated
    ["Cordless drill driver kit 18 V", "Cordless drill driver kit 18 V", "Cordless hedge trimmer 60 cm", "SDS-Plus rotary hammer 26 mm"],
])
def test_set_correct_answers_pass(iset, answer):
    key, _ = iset
    g = grade(key, answer)
    assert g.passed, g.reasons


@pytest.mark.parametrize("answer,reason", [
    (["Cordless drill driver kit 18 V", "Cordless hedge trimmer 60 cm"], "missing_items"),
    (["Cordless drill driver kit 18 V", "Cordless hedge trimmer 60 cm", "SDS-Plus rotary hammer 26 mm", "Wood chipper"], "extra_items"),
    (["Cordless drill driver kit 18 V", "Cordless hedge trimmer 60 cm", "Wood chipper"], "wrong_items"),
    (["Cordless drill driver kit 18 V ($600)", "Cordless hedge trimmer 60 cm", "SDS-Plus rotary hammer 26 mm"], "unverified_number"),
    (["Cordless drill driver kit 18 V - deposit $150", "Cordless hedge trimmer 60 cm", "SDS-Plus rotary hammer 26 mm"], "contradictory_detail"),
    (["Cordless drill driver kit 18 V", "Cordless hedge trimmer 60 cm", "SDS-Plus rotary hammer 26 mm", "and others"], "unrecognised_element"),
    (["Cordless drill driver kit 18 V or Stump grinder 13 hp", "Cordless hedge trimmer 60 cm", "SDS-Plus rotary hammer 26 mm"], "hedged"),
    (["Cordless drill driver kit 18 V", "Cordless hedge trimmer 60 cm", "SDS-Plus rotary hammer 26 mm", "not Wood chipper"], "negated"),
    (["All of them"], "unrecognised_element"),
    ([], "no_answer"),
    ("Cordless drill driver kit 18 V", "no_answer"),
])
def test_set_incorrect_answers_fail(iset, answer, reason):
    key, _ = iset
    g = grade(key, answer)
    assert not g.passed and reason in g.reasons, (answer, g.reasons)


def test_page_fact_values_are_candidates():
    key, _ = key_for(FACT)
    assert grade(key, "$45").passed and grade(key, "The late fee is $45 per day.").passed
    assert grade(key, "$45 or $50").reasons == ["multiple_candidates"]
    assert grade(key, "$50").reasons == ["wrong_candidate"]
    assert grade(key, "45 dollars").reasons == ["no_candidate_named"]          # conservative: a bare number is not the stated money value


def test_key_refuses_a_tampered_frozen_truth():
    prof = profile()
    with pytest.raises(KeyError_):
        build_key("t", {"criterion": EXT, "truth": "Electric scissor lift 6 m"}, prof)


def test_key_refuses_names_that_collide_in_canonical_form():
    prof = profile()
    prof["pages"]["/hire"]["item_groups"][0]["items"].append({"href": "/hire/dup", "name": "Stump Grinder 13HP", "text": "x"})
    prof["pages"]["/hire/dup"] = {"title": "dup", "item_groups": [], "facts": [{"label": "refundable deposit", "value": "$1"}, {"label": "per day", "value": "$1"}, {"label": "minimum hire", "value": "1 day"}]}
    with pytest.raises((KeyError_, C.CriterionError)):
        build_key("t", {"criterion": EXT, "truth": C.compile_criterion(EXT, prof).truth}, prof)


def test_v1_is_unchanged_on_the_motivating_answers(ext, iset):
    _, comp = ext
    assert C.grade(comp, "Hire pump $1,200 class")[0] is True
    assert C.grade(comp, "Hire pump $1,200 class has the highest refundable deposit of $1,200.")[0] is False   # the v1 false negative v2 corrects
    _, scomp = iset
    assert C.grade(scomp, ["Cordless drill driver kit 18V", "Cordless hedge trimmer 60 cm", "SDS-Plus rotary hammer 26 mm"])[0] is False


def test_profile_is_not_mutated_by_key_building():
    prof = profile()
    before = copy.deepcopy(prof)
    build_key("t", {"criterion": EXT, "truth": C.compile_criterion(EXT, prof).truth}, prof)
    assert prof == before


def test_page_fact_detail_quoted_from_its_own_page_passes_but_invented_or_contradicting_numbers_fail():
    key, _ = key_for(FACT)
    assert grade(key, "Late fee: $45, charged after 3 days").passed                 # both numbers are stated on the answer's page
    assert grade(key, "$45 after 7 days").reasons == ["unverified_number"]           # 7 is not on the page
    assert grade(key, "$45, grace period 5 days").reasons == ["contradictory_detail"]   # bound to the page's grace period (3 days)
    assert not grade(key, "Late fee $45 (the FAQ says $50)").passed                   # another candidate value named: multiple candidates
