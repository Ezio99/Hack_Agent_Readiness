"""Task 010: T1-T4 feasibility, independent oracle, grading (PASS and deliberately wrong FAIL), evidence semantics, determinism and result records."""
import json
import re

import pytest

from agent_readiness.environments.electronics import catalog as C
from agent_readiness.environments.electronics import tasks as T
from agent_readiness.environments.electronics.variants import all_variants
from agent_readiness.suite import core, registry, runner

registry.load_all()
INSTANCES = registry.instances()
IDS = [i.spec.task_id for i in INSTANCES]
VARIANTS = all_variants()
by_id = {i.spec.task_id: i for i in INSTANCES}


def solved(inst, variant=None):
    return runner.run_scripted(inst, variant or core.ENVIRONMENTS["electronics-v1"].default_variant())


def verdict(inst, answer, visited=None):
    return core.evaluate(inst, answer, core.ENVIRONMENTS["electronics-v1"].default_variant(), visited)


def test_suite_inventory_four_templates_ten_fixtures_unique_ids():
    assert sorted({i.spec.template_id for i in INSTANCES}) == ["t1-discovery-anc-headphones", "t2-compare-laptops", "t3-cheapest-monitor", "t4-policy-delivery"]
    assert len(INSTANCES) == 10 and len(set(IDS)) == 10
    assert {i.spec.outcome_type for i in INSTANCES} == {"set", "any_valid", "unique"}
    assert all(i.spec.limits == core.Limits(12, 240, 12) and i.spec.start_path == "/" and i.spec.environment_id == "electronics-v1" for i in INSTANCES)


@pytest.mark.parametrize("task_id", IDS)
def test_tasks_are_deterministic_and_their_public_spec_hides_the_truth(task_id):
    a, b = registry.get_instance(task_id), registry.get_instance(task_id)
    assert a.spec == b.spec and a.truth == b.truth and a.evidence == b.evidence
    public = json.dumps(a.spec.public())
    assert a.spec.answer_schema["type"] == "object" and a.spec.answer_schema["additionalProperties"] is False
    rest = public.replace(json.dumps(a.spec.objective)[1:-1], "")
    assert not re.search(r"[A-Z]{2}-\d{4}", rest) and not re.search(r"/p/", rest)                    # no SKU or product URL outside the objective text itself
    assert "truth" not in public and "eligible" not in public


@pytest.mark.parametrize("task_id", IDS)
def test_scripted_navigator_passes_with_evidence_in_every_variant(task_id):
    for v in VARIANTS:
        r = solved(by_id[task_id], v)
        e = r["evaluation"]
        assert e["passed"] and e["evidence_backed"] and e["answer_valid"], (v.variant_id, e)
        assert r["mode"] == "scripted_smoke" and r["page_requests"] <= 12            # feasible within the 12-step budget (page requests as a proxy for steps)
        assert e["variant_id"] == v.variant_id and e["data_version"] == C.DATA_VERSION and e["evaluator_version"] == "1.0.0"


def test_result_records_carry_task_template_version_environment_data_variant_and_evaluator_ids(tmp_path):
    r = runner.run_scripted(by_id["t3-cheapest-monitor-27in-usbc-120hz"], VARIANTS[2], tmp_path)
    saved = json.loads((tmp_path / r["artifact_path"].split("/")[-1] / "result.json").read_text())
    assert saved["mode"] == "scripted_smoke" and "not a model run" in saved["note"]
    ev = saved["evaluation"]
    assert (ev["task_id"], ev["template_id"], ev["task_version"], ev["environment_id"], ev["data_version"], ev["variant_id"], ev["evaluator_id"], ev["evaluator_version"], ev["contract_version"]) == (
        "t3-cheapest-monitor-27in-usbc-120hz", "t3-cheapest-monitor", "1.0.0", "electronics-v1", C.DATA_VERSION, "electronics-v1/availability-detail+specs-structured",
        "electronics-t3-grader", "1.0.0", "suite-contract-v1")
    assert saved["task"]["contract_version"] == "suite-contract-v1" and saved["variant"]["factors"] == {"availability": "detail", "specs": "structured"}


# ---- T1 --------------------------------------------------------------------------------------------------------------------------

def test_t1_oracle_sets_and_decoys():
    assert [p.sku for p in T.oracle_anc_in_stock(25000)] == ["HP-1004", "HP-1006", "HP-1007"]
    assert [p.sku for p in T.oracle_anc_in_stock(20000)] == ["HP-1006", "HP-1007"]
    assert [p.sku for p in T.oracle_anc_in_stock(30000)] == ["HP-1003", "HP-1004", "HP-1006", "HP-1007"]
    assert by_id["t1-anc-headphones-under-250-all"].spec.outcome_type == "set" and by_id["t1-anc-headphones-under-300-any"].spec.outcome_type == "any_valid"


def refs(*skus):
    return {"products": [{"sku": s, "price_cents": C.BY_SKU[s].price_cents} for s in skus]}


@pytest.mark.parametrize("answer,reason", [
    (refs("HP-1004", "HP-1006"), "Missing eligible"),                                    # incomplete set
    (refs("HP-1004", "HP-1006", "HP-1007", "HP-1005"), "not eligible"),                  # out-of-stock ANC decoy included
    (refs("HP-1004", "HP-1006", "HP-1007", "HP-1003"), "not eligible"),                  # over budget
    (refs("HP-1004", "HP-1006", "HP-1007", "HP-1009"), "not eligible"),                  # in stock, cheap, but no ANC
    (refs(), "Missing eligible"),
    ({"products": [{"sku": "HP-1004", "price_cents": 1}, *refs("HP-1006", "HP-1007")["products"]]}, "Price differs"),
    (refs("HP-1004", "HP-1004", "HP-1006", "HP-1007"), "Duplicate"),
])
def test_t1_set_task_wrong_answers_fail(answer, reason):
    inst = by_id["t1-anc-headphones-under-250-all"]
    assert verdict(inst, refs("HP-1004", "HP-1006", "HP-1007")).passed
    r = verdict(inst, answer)
    assert not r.passed and any(reason in x for x in r.reasons), r.reasons


def test_t1_any_valid_accepts_each_eligible_choice_and_rejects_sets_and_ineligible():
    inst = by_id["t1-anc-headphones-under-300-any"]
    assert all(verdict(inst, refs(s)).passed for s in ("HP-1003", "HP-1004", "HP-1006", "HP-1007"))
    assert not verdict(inst, refs("HP-1004", "HP-1006")).passed and not verdict(inst, refs("HP-1005")).passed and not verdict(inst, refs()).passed
    r = verdict(inst, refs("HP-1001"))
    assert not r.passed                                                                  # in stock ANC but over the A$300 budget
    assert solved(inst)["evaluation"]["passed"] and len(solved(inst)["answer"]["products"]) == 1


def test_t1_grading_reports_precision_and_recall_details():
    r = verdict(by_id["t1-anc-headphones-under-250-all"], refs("HP-1004", "HP-1005"))
    assert r.details["precision"] == 0.5 and r.details["recall"] == round(1 / 3, 3) and r.details["extra"] == ["HP-1005"]


# ---- T2 --------------------------------------------------------------------------------------------------------------------------

def t2(a, b, ram, bat):
    f = lambda s: {"sku": s, "ram_gb": C.BY_SKU[s].spec("ram_gb"), "battery_hours": C.BY_SKU[s].spec("battery_hours")}
    return {"a": f(a), "b": f(b), "more_ram": ram, "longer_battery": bat}


def test_t2_truth_including_a_tie_and_wrong_answers():
    one, tie = by_id["t2-compare-air14-vs-probook15"], by_id["t2-compare-slate16-vs-air14"]
    assert (one.truth["more_ram"], one.truth["longer_battery"]) == ("b", "a") and (tie.truth["more_ram"], tie.truth["longer_battery"]) == ("tie", "b")
    assert verdict(one, t2("LT-2001", "LT-2003", "b", "a")).passed and verdict(tie, t2("LT-2006", "LT-2001", "tie", "b")).passed
    assert not verdict(one, t2("LT-2001", "LT-2003", "a", "a")).passed                         # wrong RAM conclusion
    assert not verdict(one, t2("LT-2001", "LT-2003", "b", "b")).passed                         # wrong battery conclusion
    assert not verdict(tie, t2("LT-2006", "LT-2001", "a", "b")).passed                         # a tie reported as a winner
    swapped = t2("LT-2003", "LT-2001", "a", "b")                                              # sides swapped
    assert not verdict(one, swapped).passed
    bad = t2("LT-2001", "LT-2003", "b", "a")
    bad["a"]["ram_gb"] = 32
    assert not verdict(one, bad).passed
    bad = t2("LT-2001", "LT-2003", "b", "a")
    bad["b"]["battery_hours"] = 12                                                            # the Lite model's figure: a plausible confusion
    r = verdict(one, bad)
    assert not r.passed and any("battery" in x for x in r.reasons)
    near = t2("LT-2001", "LT-2002", "b", "a")                                                 # similar product name (Air 14 Plus)
    assert not verdict(one, near).passed


# ---- T3 --------------------------------------------------------------------------------------------------------------------------

def test_t3_unique_cheapest_and_every_cheaper_decoy_fails():
    inst = by_id["t3-cheapest-monitor-27in-usbc-120hz"]
    assert inst.truth["answer_sku"] == "MN-3006" and sorted(inst.truth["eligible"]) == ["MN-3006", "MN-3007", "MN-3008"]
    ok = lambda s: {"sku": s, "price_cents": C.BY_SKU[s].price_cents}
    assert verdict(inst, ok("MN-3006")).passed
    for decoy in ("MN-3001", "MN-3002", "MN-3003", "MN-3004", "MN-3005"):           # each cheaper monitor violates a criterion (size, refresh, USB-C or stock)
        r = verdict(inst, ok(decoy))
        assert not r.passed and "does not satisfy" in r.reasons[0], decoy
    for pricier in ("MN-3007", "MN-3008"):                                            # eligible but not the cheapest
        assert not verdict(inst, ok(pricier)).passed and "not the cheapest" in verdict(inst, ok(pricier)).reasons[0]
    assert not verdict(inst, {"sku": "MN-3006", "price_cents": 44000}).passed and not verdict(inst, {"sku": "ZZ-0000", "price_cents": 1}).passed
    assert not verdict(inst, ok("HP-1004")).passed                                    # not even a monitor
    other = by_id["t3-cheapest-monitor-32in-usbc-60hz"]
    assert other.truth["answer_sku"] == "MN-3009" and not verdict(other, ok("MN-3006")).passed and not verdict(other, ok("MN-3011")).passed and not verdict(other, ok("MN-3012")).passed


def test_t3_oracle_refuses_ambiguous_fixtures():
    with pytest.raises(AssertionError):
        T.oracle_cheapest_monitor(40, 240)                                            # no eligible monitor: not a valid fixture


# ---- T4 --------------------------------------------------------------------------------------------------------------------------

def test_t4_policy_values_and_every_field_is_graded():
    inst = by_id["t4-policy-delivery-lumio-pro-27c"]
    assert dict(inst.truth) == {"sku": "MN-3006", "return_window_days": 30, "restocking_fee_percent": 10, "delivery_cost_cents": 2900, "delivery_days_min": 4, "delivery_days_max": 7}
    assert dict(by_id["t4-policy-delivery-kestrel-air-14"].truth) == {"sku": "LT-2001", "return_window_days": 14, "restocking_fee_percent": 15, "delivery_cost_cents": 0, "delivery_days_min": 2, "delivery_days_max": 4}
    assert dict(by_id["t4-policy-delivery-tessera-whisper"].truth)["delivery_cost_cents"] == 0
    good = dict(inst.truth)
    assert verdict(inst, good).passed
    for field, wrong in (("return_window_days", 14), ("restocking_fee_percent", 0), ("delivery_cost_cents", 995), ("delivery_days_min", 2), ("delivery_days_max", 4), ("sku", "MN-3007")):
        bad = {**good, field: wrong}
        r = verdict(inst, bad)
        assert not r.passed and any(field in x for x in r.reasons), field
    standard_policy = {**good, "delivery_cost_cents": 0, "delivery_days_min": 2, "delivery_days_max": 4, "return_window_days": 30, "restocking_fee_percent": 0}
    assert not verdict(inst, standard_policy).passed                                  # the headphones' policy applied to a monitor


# ---- cross-cutting: malformed answers, evidence semantics, isolation ---------------------------------------------------------------

@pytest.mark.parametrize("task_id", IDS)
def test_malformed_answers_and_extra_fields_fail_validation(task_id):
    inst = by_id[task_id]
    for raw in (None, {}, "answer", [], {"unexpected": 1}):
        r = verdict(inst, raw)
        assert not r.answer_valid and not r.passed
    good = solved(inst)["answer"]
    assert not verdict(inst, {**good, "extra": 1}).answer_valid
    assert verdict(inst, good).answer_valid


@pytest.mark.parametrize("task_id", [i for i in IDS if by_id[i].evidence])
def test_correct_answers_without_the_required_evidence_are_correct_but_not_evidence_backed(task_id):
    inst = by_id[task_id]
    run = solved(inst)
    answer, observed = run["answer"], run["_observed"]
    r = verdict(inst, answer, [core.Observation("/", "home"), core.Observation("/c/laptops", "listing")])
    assert r.passed and not r.evidence_backed and r.missing_evidence
    assert verdict(inst, answer, None).passed and not verdict(inst, answer, None).evidence_backed
    assert verdict(inst, answer, observed).evidence_backed and not verdict(inst, answer, observed).missing_evidence


@pytest.mark.parametrize("task_id", [i for i in IDS if any(e.kind.startswith("observed_text") for e in by_id[i].evidence)])
def test_visiting_a_page_is_not_the_same_as_being_shown_its_content(task_id):
    """Path-only observations (or pages whose text lacks the facts) cannot satisfy text evidence, even if every required URL was visited."""
    inst = by_id[task_id]
    run = solved(inst)
    paths_only = [o.path for o in run["_observed"]]
    r = verdict(inst, run["answer"], paths_only)
    assert r.passed and not r.evidence_backed and any(g.startswith("observed_text") for g in r.missing_evidence)
    emptied = [core.Observation(o.path, "no useful text here") for o in run["_observed"]]
    r2 = verdict(inst, run["answer"], emptied)
    assert r2.passed and not r2.evidence_backed and any(g.startswith("observed_text") for g in r2.missing_evidence)


def test_no_task_is_solved_by_the_start_page_alone_and_each_requires_navigation_beyond_it():
    for inst in INSTANCES:
        paths = solved(inst)["visited_paths"]
        assert len(paths) >= 3 and paths != ["/"]
        assert not verdict(inst, {}, [core.Observation("/", "home")]).passed
    for i in INSTANCES:
        assert i.spec.start_path == "/" and "/" not in [e.value for e in i.evidence]


def test_scripted_smoke_is_never_confused_with_a_model_run():
    r = solved(INSTANCES[0])
    assert r["mode"] == "scripted_smoke" and "not evidence about any agent" in r["note"]
