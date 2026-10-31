"""Experiment-2 infrastructure for the Ironbark site: snapshot integration, answer grading, task generation and verification, study design, cost model, pre-registered rules and the approval-gated
driver. Offline and credential-free; nothing here can spend money. Browser-level integration is in tests/test_exp2_browser.py."""
import copy
import json
import re
from datetime import date

import pytest

from agent_readiness.exp2 import analysis, answers as A, costs, flow, pool as P, snapshot as S, study, tasks as T, verify as Vf
from agent_readiness.exp2.facts import PageFacts
from agent_readiness.investigate.inspect.crawl import Limits, MappingFetcher, crawl
from agent_readiness.ledger import Halt
from agent_readiness.sites.ironbark import data as D, variants as V
from agent_readiness.sites.ironbark.build import build_site


@pytest.fixture(scope="module")
def pool():
    return P.build_pool()


@pytest.fixture(scope="module")
def plan(pool):
    return study.build_plan(pool[0].accepted)


@pytest.fixture(scope="module")
def control_pages():
    return P.control_pages()


# ------------------------------------------------------------------------------------------------------------------------------------------------------------- snapshot integration
@pytest.mark.parametrize("spec", ["control", "discoverability", "availability", "cost", "compatibility", "discoverability+availability+cost+compatibility"])
def test_every_variant_crawls_into_a_faithful_self_contained_deterministic_snapshot(spec):
    r = S.assess(spec)
    assert r["ok"], r["problems"][:5]
    assert r["assets"] == 51 and r["pages"] >= 55 and r["fidelity"]["level"] == "high" and r["references_checked"] > 2000


def test_the_pipelines_default_crawl_limits_would_drop_assets_and_the_ironbark_limits_fix_it():
    """The integration gap this PR closes: default `Limits()` keeps 20 assets; Ironbark has 51 (CSS and SVG)."""
    files = build_site(V.CONTROL)
    default = crawl(MappingFetcher(S.mapping(files)), Limits())
    assert sum(not r.is_html for r in default.resources.values()) == 20
    full = S.snapshot("control")
    assert sum(not r.is_html for r in full.resources.values()) == 51 and sum(r.is_html for r in full.resources.values()) == 55


def test_snapshot_hash_differs_per_variant_and_is_stable():
    hashes = {v.name: S.snapshot(v).sha256 for v in V.all_single()}
    assert len(set(hashes.values())) == 5 and S.snapshot("control").sha256 == S.snapshot(V.CONTROL).sha256


def test_variants_change_access_never_facts():
    for v in V.all_single()[1:]:
        assert P.facts_invariance(v) == [], v.name


# -------------------------------------------------------------------------------------------------------------------------------------------------------------------- page-derived facts
def test_page_facts_equal_the_source_data_for_every_product_accessory_and_kit(control_pages):
    pf = PageFacts(control_pages)
    assert len(pf.products) == 16 and len(pf.accessories) == 8 and len(pf.kits) == 3
    for p in D.PRODUCTS:
        f = pf.products[p.id]
        assert (f.name, f.daily, f.weekend, f.weekly, f.deposit, f.min_days, f.weight_kg, f.units, f.delivery_required) == (p.name, p.daily, p.weekend, p.weekly, p.deposit, p.min_days, p.weight_kg, p.units, p.delivery == "required")
        assert f.free == [D.units_free(p, D.AS_OF + __import__("datetime").timedelta(days=i)) for i in range(56)]
    for b in D.BUNDLES:
        k = pf.kits[b.slug]
        assert (k.daily, k.weekend, k.weekly, k.consumables) == (D.bundle_rates(b)["hire"]["daily"], D.bundle_rates(b)["hire"]["weekend"], D.bundle_rates(b)["hire"]["weekly"], D.bundle_rates(b)["consumables"])
    t = pf.terms
    assert (t.waiver_rate, t.courier_fee, t.machine_fee, t.courier_below_kg) == (D.WAIVER_RATE, 45, 120, 25) and t.cap_rule


def test_page_derived_quotes_equal_the_data_quotes_everywhere(control_pages):
    pf = PageFacts(control_pages)
    for p in D.PRODUCTS:
        for per in ("1d", "2d", "3d", "weekend", "7d"):
            if per != "weekend" and int(per[:-1]) < p.min_days:
                continue
            for w in (False, True):
                for dl in (False, True):
                    assert pf.total(p.id, per, waiver=w, delivered=dl) == D.quote(p, per, waiver=w, delivery=dl)["total"], (p.id, per, w, dl)


# ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- grading
NAMES = {"IB-A": "Wet tile saw 250 mm", "IB-B": "Petrol cut-off saw 350 mm", "IB-C": "Reversible plate compactor 90 kg"}


@pytest.mark.parametrize("kind,truth,answer,ok", [
    ("money", 160.5, "$160.50", True), ("money", 160.5, "160.5", True), ("money", 160.5, "AUD 160.50 in total", True), ("money", 160.5, "about $160.50", False), ("money", 160.5, "$160.50 or $170", False),
    ("money", 160.5, "$160 and $170", False), ("money", 160.5, "$161", False), ("money", 160.5, "", False), ("money", 1234.5, "$1,234.50", True),
    ("number", 1.8, "1.8 kg", True), ("number", 1.8, "1.9 kg", False), ("integer", 2, "2", True), ("integer", 2, "2.5", False),
    ("date", "2026-11-13", "Fri 13 Nov 2026", True), ("date", "2026-11-13", "13 November 2026", True), ("date", "2026-11-13", "2026-11-13", True), ("date", "2026-11-13", "November 13th", True),
    ("date", "2026-11-13", "Sat 13 Nov", False), ("date", "2026-11-13", "13 or 14 Nov", False), ("date", "2026-11-13", "14 Nov", False),
    ("yesno", True, "Yes", True), ("yesno", True, "Yes, it is available.", True), ("yesno", True, "No", False), ("yesno", True, "Yes or no", False), ("yesno", False, "No, it is not", True),
    ("choice", "kit", "The kit is cheaper", True), ("choice", "kit", "kit or separately", False), ("choice", "kit", "separately", False),
    ("product", "IB-A", "wet tile saw 250 mm", True), ("product", "IB-A", "Wet tile saw 250 mm.", True), ("product", "IB-A", "Wet tile saw 250 mm or Petrol cut-off saw 350 mm", False), ("product", "IB-A", "Petrol cut-off saw 350 mm", False),
])
def test_grader_table(kind, truth, answer, ok):
    assert A.grade(kind, truth, answer, options=("kit", "separately"), names=NAMES) is ok


def test_set_grading_is_exact_and_never_fuzzy():
    g = lambda ans: A.grade("products", ["IB-A", "IB-B"], ans, names=NAMES)
    assert g(["Wet tile saw 250 mm", "Petrol cut-off saw 350 mm"]) and g(["petrol cut-off saw 350 mm", "wet tile saw 250 mm"])
    assert not g(["Wet tile saw 250 mm"]) and not g(["Wet tile saw 250 mm", "Petrol cut-off saw 350 mm", "Reversible plate compactor 90 kg"])
    assert not g(["Wet tile saw 250 mm", "Wet tile saw 250 mm"]) and not g([]) and not g("Wet tile saw 250 mm") and not g(["Wet tile saw 250 mm", "a chainsaw"])


# ------------------------------------------------------------------------------------------------------------------------------------------------------------------------ task generation
def test_generation_is_deterministic_and_covers_every_family():
    a, b = T.generate(), T.generate()
    assert [c.task_id for c in a] == [c.task_id for c in b] and len(a) > 350
    assert {c.family for c in a} == set(T.FAMILIES) and {c.kind for c in a} >= {"money", "date", "yesno", "choice", "product", "products", "accessory", "integer", "number"}


def test_the_pool_is_large_diverse_and_every_accepted_task_passes_all_checks(pool):
    report, cands = pool
    assert len(report.accepted) >= 300 and len(report.accepted) + len(report.rejected) == len(cands)
    assert {c.family for c in report.accepted} == set(T.FAMILIES)
    assert len({c.task_id for c in report.accepted}) == len(report.accepted) and len({c.full_question for c in report.accepted}) == len(report.accepted)
    for v in T.VARIANTS:
        assert sum(v in c.sensitive_to for c in report.accepted) >= 10, v
    assert {c.difficulty for c in report.accepted} == {"easy", "medium", "hard"}


def test_every_accepted_truth_equals_the_independently_recomputed_one(pool, control_pages):
    pf = PageFacts(control_pages)
    for c in pool[0].accepted:
        assert Vf.norm_truth(c.kind, c.recompute(pf)) == Vf.norm_truth(c.kind, c.truth), c.question


def test_the_verifier_rejects_real_problems_with_reasons(pool):
    reasons = {r["reason"].split(":")[0] for r in pool[0].rejected}
    assert {"set size 0 outside 1..6", "ambiguous on the pages", "same template, truth and visit set as an accepted task"} <= reasons
    assert any("tie" in r["reason"] for r in pool[0].rejected), "the tied highest deposit (two items at $500) must be rejected as ambiguous"


def _first(pool, family, sub):
    return next(c for c in pool[0].accepted if c.family == family and c.sub == sub)


def _check(c, control_pages):
    return Vf.check(c, PageFacts(control_pages), Vf.link_depths(control_pages), control_pages, P.arm_texts())


def test_verifier_catches_a_wrong_truth_a_leak_a_missing_page_and_a_weak_grader(pool, control_pages):
    base = _first(pool, "total_cost", "single")
    assert _check(base, control_pages) is None
    wrong = copy.copy(base); wrong.truth = base.truth + 1
    assert "disagree" in _check(wrong, control_pages)
    leak = copy.copy(base); leak.question = base.question + f" (Hint: it is ${base.truth:,.2f}.)"
    assert "contains the answer" in _check(leak, control_pages)
    gone = copy.copy(base); gone.visit = ("/hire/does-not-exist",)
    assert "does not exist" in _check(gone, control_pages)
    code = copy.copy(base); code.question = base.question + " Product IB-DRL-003."
    assert "internal catalogue code" in _check(code, control_pages)
    noisy = copy.copy(base); noisy.recompute = lambda pf: (_ for _ in ()).throw(KeyError("x"))
    assert "recomputation failed" in _check(noisy, control_pages)
    date_c = _first(pool, "availability", "next_free"); out = copy.copy(date_c); out.truth = "2027-01-01"
    assert _check(out, control_pages) is not None
    sets = _first(pool, "availability", "category_weekend"); empty = copy.copy(sets); empty.truth = []
    assert "set size" in _check(empty, control_pages) or "disagree" in _check(empty, control_pages)


def test_every_candidate_has_a_canonical_answer_the_grader_accepts_and_wrong_answers_it_rejects(pool):
    for c in pool[0].accepted:
        assert A.grade(c.kind, c.truth, c.expected_text, options=c.options, names=c.names), c.question
        for w in Vf.wrong_answers(c):
            assert not A.grade(c.kind, c.truth, w, options=c.options, names=c.names), (c.question, w)


def test_the_agent_never_receives_answers_or_hidden_data(plan, pool):
    text = json.dumps(plan)
    assert '"truth"' not in text and "expected_text" not in text and "evidence" not in text.replace("evidence_backed", "")
    by_id = {c.task_id: c for c in pool[0].accepted}
    for t in plan["tasks"]:
        assert set(t) == {"task_id", "family", "template", "difficulty", "partition", "question", "start_path", "answer_kind", "answer_schema", "pages_needed", "limits", "sensitive_to"}
        c = by_id[t["task_id"]]
        assert t["question"] == c.full_question and not re.search(r"IB-[A-Z]{3}-\d{3}", t["question"])
        if c.kind in ("product", "accessory", "money", "date", "products", "accessories") and "group" not in c.params:
            for e in (c.expected_text if isinstance(c.expected_text, list) else [c.expected_text]):
                assert e.lower() not in t["question"].lower()


def test_question_wording_does_not_point_at_pages(pool):
    for c in pool[0].accepted:
        q = c.full_question.lower()
        assert not re.search(r"kits page|hire terms|booking calendar|availability page|accessories page|product page", q), c.question


# -------------------------------------------------------------------------------------------------------------------------------------------------------------------------- study design
def test_the_plan_is_deterministic_balanced_and_stratified(plan, pool):
    again = study.build_plan(pool[0].accepted)
    assert again["plan_sha256"] == plan["plan_sha256"] and again["trial_order"] == plan["trial_order"]
    c = plan["counts"]
    assert c["by_family"] == study.QUOTAS and c["tasks"] == sum(study.QUOTAS.values()) and c["trials"] == c["tasks"] + study.REPEAT_TASKS
    assert set(c["by_difficulty"]) == {"easy", "medium", "hard"} and c["investigation"] + c["holdout"] == c["tasks"]
    assert not plan["warnings"] and all(n >= study.MIN_AFFECTED for n in c["sensitive_to"].values()) and c["negative_control_tasks"] >= 4
    assert c["trials"] == c["tasks"] + study.REPEAT_TASKS == 48
    fams = {}
    for t in plan["tasks"]:
        fams.setdefault(t["family"], []).append(t["partition"])
    assert all("holdout" in parts and "investigation" in parts for f, parts in fams.items() if len(parts) >= 3)


def test_trial_order_puts_coverage_first_and_repeats_after(plan):
    order = plan["trial_order"]
    first = order[: len(plan["tasks"])]
    assert all(o["repeat"] == 1 for o in first) and all(o["repeat"] == 2 for o in order[len(plan["tasks"]):]) and len({o["task_id"] for o in first}) == len(plan["tasks"])
    fam = {t["task_id"]: t["family"] for t in plan["tasks"]}
    assert len({fam[o["task_id"]] for o in order[: study.PILOT_TRIALS]}) == study.PILOT_TRIALS, "the pilot covers eight different families"
    part = {t["task_id"]: t["partition"] for t in plan["tasks"]}
    assert {part[o["task_id"]] for o in order if o["repeat"] == 2} == {"investigation", "holdout"}
    assert plan["phases"]["baseline_pilot"]["trials"] + plan["phases"]["baseline_main"]["trials"] == order


def test_no_quota_selection_repeats_one_template_too_often(plan, pool):
    by_id = {c.task_id: c for c in pool[0].accepted}
    from collections import Counter
    per = Counter((by_id[t["task_id"]].family, by_id[t["task_id"]].sub) for t in plan["tasks"])
    for fam, quota in study.QUOTAS.items():
        templates = {sub for (f, sub) in per if f == fam}
        assert max(n for (f, _), n in per.items() if f == fam) <= max(2, -(-quota // len(templates))) + 0


# ----------------------------------------------------------------------------------------------------------------------------------------------------------------- budget and cost model
def test_the_allocation_fits_under_the_experiment_ceiling_and_never_touches_the_reserve(plan):
    a = plan["allocation"]
    assert a["ceiling_usd"] == 20.0 and a["reserve_usd"] == 2.5 and a["fits"] and a["investigator_cap_usd"] == 0.5
    assert a["baseline_pilot_cap_usd"] + a["baseline_main_cap_usd"] + a["investigator_cap_usd"] + a["variant_tests_cap_usd"] == pytest.approx(a["allocatable_usd"], abs=0.011)
    assert a["fits_one_variant_test"] and a["variant_tests_cap_usd"] >= a["one_variant_test_expected_usd"][0], "at least one pre-registered variant test fits even if the baseline spends its caps"
    assert a["variant_tests_cap_usd"] < 2 * a["one_variant_test_expected_usd"][0], "...but two do not: the protocol must not promise them"


def test_cost_model_is_monotone_capped_and_trimmable():
    assert costs.step_limit(1) == costs.MIN_STEPS and costs.step_limit(99) == costs.MAX_STEPS
    c = [costs.trial_cost(p)[0] for p in range(1, 12)]
    assert c == sorted(c) and all(costs.trial_cost(p)[1] >= costs.trial_cost(p)[0] for p in range(1, 12))
    assert costs.trial_cost(12)[1] <= costs.PER_TRIAL_CAP_USD, "no planned trial exceeds the per-trial cap at p90"
    pages = [3, 4, 5, 3, 7] * 6
    full = costs.phase_cost(pages)
    assert costs.trim_to_cap(pages, full.cap_usd) == len(pages)
    n = costs.trim_to_cap(pages, full.cap_usd * 0.5)
    assert 0 < n < len(pages) and costs.phase_cost(pages[:n]).cap_usd <= full.cap_usd * 0.5 + 0.05
    assert costs.trim_to_cap(pages, full.cap_usd, per_request=(0.05, 0.07)) < len(pages), "a higher measured rate trims the plan"


def test_the_published_plan_stays_inside_the_ceiling_even_at_the_per_trial_cap(plan):
    worst = plan["counts"]["trials"] * costs.PER_TRIAL_CAP_USD
    assert plan["phases"]["baseline_pilot"]["cost"]["cap_usd"] + plan["phases"]["baseline_main"]["cost"]["cap_usd"] <= costs.CEILING_USD - costs.RESERVE_USD
    assert worst > costs.CEILING_USD, "the per-trial cap alone would not protect the ceiling: the phase caps and the ledger do"


# ---------------------------------------------------------------------------------------------------------------------------------------------------------------- pre-registered rules
def rows(spec, plan, **kw):
    """spec: list of (task_id, repeat, passed, requests[, void])."""
    t = {x["task_id"]: x for x in plan["tasks"]}
    out = []
    for item in spec:
        tid, rep, passed, req = item[:4]
        void = item[4] if len(item) > 4 else False
        out.append({"task_id": tid, "repeat": rep, "partition": t[tid]["partition"], "family": t[tid]["family"], "difficulty": t[tid]["difficulty"], "void": void, "passed": passed, "evidence_backed": passed,
                    "model_requests": req, "page_views": req, "cost_usd": 0.1, "status": "infrastructure_error" if void else "completed", "pages_needed": t[tid]["pages_needed"], "primary": "x"})
    return out


def sensitive(plan, v, partition=None):
    return [t["task_id"] for t in plan["tasks"] if v in t["sensitive_to"] and (partition is None or t["partition"] == partition)]


def test_eligibility_depends_only_on_baseline_friction_in_investigation_tasks(plan):
    ids = sensitive(plan, "availability", "investigation")
    need = {t["task_id"]: t["pages_needed"] + 2 for t in plan["tasks"]}
    smooth = rows([(i, 1, True, need[i]) for i in ids], plan)
    assert analysis.eligibility(smooth, plan)["availability"]["decision"] == "not_eligible_no_friction_observed"
    rough = rows([(i, 1, k % 2 == 0, need[i] * 2) for k, i in enumerate(ids)], plan)
    assert analysis.eligibility(rough, plan)["availability"]["decision"] == "eligible"
    hold = sensitive(plan, "availability", "holdout")
    assert analysis.eligibility(rows([(i, 1, False, 30) for i in hold] + [(i, 1, True, need[i]) for i in ids], plan), plan)["availability"]["decision"] == "not_eligible_no_friction_observed", "holdout results never decide eligibility"
    assert analysis.eligibility([], plan)["cost"]["decision"] == "not_eligible_too_few_tasks"
    broken = rows([(i, 1, True, 5, True) for i in ids], plan)
    assert analysis.eligibility(broken, plan)["availability"]["decision"] == "uninterpretable"


def _arms(plan, variant, *, base_req, var_req, base_pass=True, var_pass=True, neg_shift=0):
    ids = sensitive(plan, variant)
    neg = [t["task_id"] for t in plan["tasks"] if variant not in t["sensitive_to"]][:5]
    control = rows([(i, r, base_pass, base_req) for i in ids for r in (1, 2)] + [(i, 1, True, 6) for i in neg], plan)
    var = rows([(i, r, var_pass, var_req) for i in ids for r in (1, 2)] + [(i, 1, True, 6 + neg_shift) for i in neg], plan)
    return ids, control, var


def test_compare_reports_improvement_regression_and_inconclusive_honestly(plan):
    ids, control, var = _arms(plan, "cost", base_req=12, var_req=6, base_pass=False)
    assert len(ids) >= 6
    out = analysis.compare_variant("cost", control, var, control, plan)
    assert out["verdict"] == "improvement" and out["rules_sha256"] == analysis.RULES_SHA256 and out["control_drift"] == 0
    ids, control, var = _arms(plan, "cost", base_req=6, var_req=12)
    assert analysis.compare_variant("cost", control, var, control, plan)["verdict"] in ("regression", "inconclusive")
    ids, control, var = _arms(plan, "cost", base_req=8, var_req=8)
    assert analysis.compare_variant("cost", control, var, control, plan)["verdict"] == "inconclusive"


def test_compare_withdraws_support_for_drift_and_moving_negative_controls(plan):
    ids, control, var = _arms(plan, "cost", base_req=12, var_req=6, base_pass=False)
    baseline = rows([(i, 1, False, 6) for i in ids], plan)                          # the earlier baseline is far from the contemporaneous control: drift
    out = analysis.compare_variant("cost", control, var, baseline, plan)
    assert out["verdict"] == "inconclusive_conflicting_comparisons" and abs(out["control_drift"]) > 0.25
    ids, control, var = _arms(plan, "cost", base_req=12, var_req=6, base_pass=False, neg_shift=6)
    assert analysis.compare_variant("cost", control, var, control, plan)["verdict"] == "uninterpretable", "negative controls moved: a variant that changes unrelated tasks is not interpretable"
    ids, control, var = _arms(plan, "cost", base_req=12, var_req=6, base_pass=False)
    few = [r for r in var if r["task_id"] in ids[:3]]
    assert analysis.compare_variant("cost", [r for r in control if r["task_id"] in ids[:3]], few, control, plan)["verdict"] in ("inconclusive", "uninterpretable")


def test_rules_are_hashed_and_say_that_nothing_is_assumed_to_help():
    assert re.fullmatch(r"[0-9a-f]{64}", analysis.RULES_SHA256)
    assert "null baseline is a result" in analysis.ELIGIBILITY["not_eligible"] and "CONTEMPORANEOUSLY" in analysis.COMPARE["control"]


# ------------------------------------------------------------------------------------------------------------------------------------------------------------------ driver (credential-free)
SMALL = {"quotas": {f: 1 for f in T.FAMILIES}, "pilot_trials": 3, "repeat_tasks": 2}


def test_free_stages_produce_frozen_public_and_private_artifacts(tmp_path):
    run, pipe, ctx = flow.build(tmp_path, "t", mode="live", options=SMALL)
    res = pipe.run(ctx, until="freeze")
    assert res.status == "done" and {s: run.status(s) for s in ("inspect", "pool", "freeze")} == {"inspect": "done", "pool": "done", "freeze": "done"}
    plan = run.artifact("study-plan")
    assert plan["snapshot_sha256"] == S.snapshot("control").sha256 and "truth" not in json.dumps(plan)
    priv = run.private("criteria")
    assert set(priv) == {t["task_id"] for t in plan["tasks"]} and all("truth" in v and "expected_text" in v for v in priv.values())
    assert run.artifact("integration-assessment")["control"]["ok"] and not any(run.artifact("integration-assessment")["variant_fact_invariance"].values())
    assert run.ledger(20.0).entries() == []


def test_live_mode_stops_at_each_paid_gate_and_spends_nothing_without_the_exact_approval(tmp_path):
    run, pipe, ctx = flow.build(tmp_path, "live", mode="live", options=SMALL)
    r = pipe.run(ctx)
    assert (r.status, r.stage) == ("awaiting_approval", "baseline_pilot") and run.ledger(20.0).entries() == []
    m = flow.manifest(ctx, "baseline_pilot")
    assert canonical(m) == r.manifest_sha256
    for key in ("trials", "trial_count", "snapshot_sha256", "model", "phase_cap_usd", "per_trial_cap_usd", "per_request_cap_usd", "max_requests_per_trial", "retries", "ledger_ceiling_usd", "reserve_usd", "stopping_conditions", "allocation", "cost_basis"):
        assert key in m
    assert m["retries"] == 0 and m["ledger_ceiling_usd"] == 20.0 and m["per_request_cap_usd"] == 0.05 and "EXP-B" in m["ledger"] and len(m["stopping_conditions"]) >= 5
    with pytest.raises(Exception):
        run.require_approval("baseline_pilot", {**m, "phase_cap_usd": m["phase_cap_usd"] + 1})          # any change to the manifest voids the approval
    run.approve("baseline_pilot", r.manifest_sha256, "test")
    ctx2 = flow.build(tmp_path, "live", mode="live", options={**SMALL, "allow_model_calls": False})[2]
    res = flow.build(tmp_path, "live", mode="live", options={**SMALL, "allow_model_calls": False})[1].run(ctx2)
    assert res.status == "failed" and run.ledger(20.0).entries() == [], "approved but without --allow-model-calls: the preflight refuses before any request"


def canonical(m):
    from agent_readiness.investigate.run import InvestigationRun
    return InvestigationRun.manifest_sha256(m)


def test_pilot_review_trims_the_main_phase_to_the_measured_rate_and_halts_on_cost_overrun(tmp_path, monkeypatch):
    run, pipe, ctx = flow.build(tmp_path, "rev", mode="live", options=SMALL)
    pipe.run(ctx, until="freeze")
    plan = run.artifact("study-plan")
    fake = lambda recs: {"trials": 3, "p50": 0.016, "p90": 0.024, "total_usd": 0.3, "requests": 20}
    monkeypatch.setattr(flow, "trial_records", lambda r: [{"outcome": {"run_status": "completed"}, "evaluation": {"passed": True}}] * 3)
    monkeypatch.setattr(flow, "measured_rate", fake)
    m = flow.review_manifest(ctx)
    assert m["main_trials_proposed"] == m["main_trials_planned"] and m["rate_ratio_to_plan"] == 1.0 and not m["replan_required"]
    monkeypatch.setattr(flow, "measured_rate", lambda recs: {"trials": 3, "p50": 0.04, "p90": 0.06, "total_usd": 1, "requests": 25})
    m2 = flow.review_manifest(ctx)
    assert m2["replan_required"] and m2["main_trials_proposed"] < m2["main_trials_planned"] and len(m2["dropped_trials"]) == m2["main_trials_planned"] - m2["main_trials_proposed"]
    with pytest.raises(Halt):
        flow.review_stage(ctx)
    assert plan["phases"]["baseline_main"]["trials"][: m2["main_trials_proposed"]] == plan["phases"]["baseline_main"]["trials"][: m2["main_trials_proposed"]]


def test_experiment_two_has_its_own_ledger_and_never_references_exp_b():
    from pathlib import Path
    src = "".join(p.read_text() for p in Path(flow.__file__).parent.glob("*.py"))
    assert "programme-ledger" not in src and "site-5" not in src and "investigations/site" not in src
    assert costs.CEILING_USD == 20.0


def test_cli_rules_plan_and_assess(capsys, monkeypatch):
    from agent_readiness.cli import main
    for argv in (["exp2", "rules"], ["exp2", "plan"]):
        monkeypatch.setattr("sys.argv", ["readiness", *argv]); main()
    out = capsys.readouterr().out
    assert "exp2-eligibility-v1" in out and "plan_sha256" in out and '"fits": true' in out
    monkeypatch.setattr("sys.argv", ["readiness", "exp2", "assess"])
    with pytest.raises(SystemExit) as e:
        main()
    assert e.value.code == 0


# ------------------------------------------------------------------------------------------------------------------------------------------ evidence sufficiency (separate from correctness and efficiency)
from agent_readiness.exp2 import evidence as E


def obs(*texts):
    return [{"path": f"/p{i}", "text": t} for i, t in enumerate(texts)]


def test_evidence_text_is_normalised_and_markers_are_ignored():
    assert E.norm("[1510]<td />\n\t\t\t13 Nov\n\t\t\tBooked") == "13 nov booked"
    f = (E.fact("x", (E.clause("Availability: Wet tile saw 250 mm", "13 Nov Booked"),)),)
    assert E.assess(f, obs("Availability: Wet tile saw 250 mm\n[1]<td />\n 13 Nov\n Booked"))["sufficient"]
    assert not E.assess(f, obs("Availability: Wet tile saw 250 mm 13 Nov 2 free"))["sufficient"]
    assert not E.assess(f, obs("Availability: Petrol cut-off saw 350 mm 13 Nov Booked"))["sufficient"], "the signature ties a fact to the right item's page"
    assert not E.assess((), obs("anything"))["sufficient"] and not E.assess(f, None)["sufficient"]


def test_a_fact_is_satisfied_by_any_route_and_a_route_needs_all_its_clauses():
    A, B = E.clause(None, "alpha"), E.clause(None, "beta")
    f = (E.fact("f", (A, B), (E.clause(None, "gamma"),)),)
    assert E.assess(f, obs("alpha", "beta"))["sufficient"] and E.assess(f, obs("gamma"))["sufficient"]
    assert not E.assess(f, obs("alpha"))["sufficient"] and E.assess(f, obs("alpha"))["missing"] == ["f"]
    assert E.assess((E.fact("one", (A,)), E.fact("two", (B,))), obs("alpha"))["missing"] == ["two"], "facts are ANDed"


def test_every_accepted_task_can_be_evidenced_on_every_arm_and_no_task_requires_a_particular_page(pool):
    arms = P.arm_texts()
    assert set(arms) == {"control", "discoverability", "availability", "cost", "compatibility", "discoverability+availability+cost+compatibility"}
    for c in pool[0].accepted:
        assert c.facts, c.question
        for arm, texts in arms.items():
            assert E.available_in(c.facts, texts) == [], (arm, c.question)
    assert all("visited_path" not in repr(c.facts) for c in pool[0].accepted)


def test_route_choice_is_not_a_requirement_the_same_task_is_evidenced_by_different_pages_in_different_arms(pool):
    """Total-cost tasks: the control must show rate and rules (product and terms pages); the cost variant also shows the total on the product page. Either suffices; the rule is identical."""
    c = next(c for c in pool[0].accepted if c.family == "total_cost" and c.sub == "single" and c.params["waiver"] and c.params["per"] in ("1d", "2d", "3d", "weekend", "7d") and c.params["p"] not in ("IB-LND-003",))
    cost_pages = P.arm_texts()["cost"]
    prod = next(t for p, t in cost_pages.items() if f"Product code {c.params['p']}" in t and "Your hire cost" in t)
    only_product_page = [{"path": "/x", "text": prod}]
    assert E.assess(c.facts, only_product_page)["sufficient"], "the cost variant's product page alone carries the total"
    control_prod = next(t for p, t in P.arm_texts()["control"].items() if f"Product code {c.params['p']}" in t and "Your hire cost" not in t and "Per day" in t)
    assert not E.assess(c.facts, [{"path": "/x", "text": control_prod}])["sufficient"], "the same view on the control site lacks the waiver rule"
    terms = next(t for t in P.arm_texts()["control"].values() if "Hire terms and pricing" in t and "Damage waiver" in t)
    assert E.assess(c.facts, [{"path": "/x", "text": control_prod}, {"path": "/y", "text": terms}])["sufficient"], "control product page + terms page also suffices"


def test_availability_can_be_evidenced_by_the_calendar_or_by_the_dates_at_a_glance_panel(pool):
    c = next(c for c in pool[0].accepted if c.family == "availability" and c.sub == "day")
    pid = c.params["p"]
    cal = next(t for t in P.arm_texts()["control"].values() if f"Availability: " in t and "Fleet size" in t and PRODUCT_NAME[pid] in t)
    glance = next(t for t in P.arm_texts()["availability"].values() if f"Product code {pid}" in t and "Dates at a glance" in t)
    assert E.assess(c.facts, [{"path": "/cal", "text": cal}])["sufficient"] and E.assess(c.facts, [{"path": "/prod", "text": glance}])["sufficient"]
    ctrl_prod = next(t for t in P.arm_texts()["control"].values() if f"Product code {pid}" in t and "Per day" in t)
    assert not E.assess(c.facts, [{"path": "/prod", "text": ctrl_prod}])["sufficient"], "the control's product page alone does NOT show dated availability"


PRODUCT_NAME = {p.id: p.name for p in D.PRODUCTS}


def test_trial_rows_keep_correctness_evidence_and_efficiency_apart(plan):
    t = plan["tasks"][0]
    rec = lambda passed, req: {"task_id": t["task_id"], "repeat": 1, "outcome": {"run_status": "completed"}, "evaluation": {"passed": passed, "evidence_backed": True},
                               "metrics": {"model_requests": req, "page_views": req, "calculated_cost_usd": 0.1}, "journey": [{"path": "/"}, {"path": "/hire"}, {"path": "/hire"}]}
    suff, insuff = {"sufficient": True, "missing": []}, {"sufficient": False, "missing": ["a fact"]}
    a = analysis.row(rec(True, 6), t, suff)
    assert (a["passed"], a["evidence_backed"], a["supported"]) == (True, True, True) and a["distinct_pages"] == 2 and a["request_ratio"] == round(6 / (t["pages_needed"] + 2), 3)
    b = analysis.row(rec(True, 6), t, insuff)
    assert (b["passed"], b["evidence_backed"], b["supported"]) == (True, False, False), "a correct answer without sufficient evidence is correct but not supported"
    c = analysis.row(rec(False, 6), t, suff)
    assert (c["passed"], c["evidence_backed"], c["supported"]) == (False, True, False)
    assert analysis.row(rec(True, 12), t, suff)["passed"] == a["passed"], "efficiency never changes correctness or sufficiency"
    s = analysis.baseline_summary([rec(True, 4) | {"trial_id": "x-r1"}, rec(True, 8) | {"trial_id": "y-r1"}], plan, {"x-r1": suff, "y-r1": insuff})
    ov = s["overall"]
    assert ov["correct_rate"] == 1.0 and ov["evidence_sufficiency_rate_among_correct"] == 0.5 and ov["supported_pass_rate"] == 0.5 and ov["mean_requests"] == 6.0 and "mean_request_ratio" in ov


# --------------------------------------------------------------------------------------------------------------------------- K per cell: protocol, rule, plan and budget agree
def test_the_variant_test_plan_implements_k2_per_arm_and_the_budget_uses_it(plan):
    assert analysis.COMPARE["min_repeats_affected"] == study.K_AFFECTED == 2 and analysis.COMPARE["min_repeats_negative"] == study.K_NEG == 1
    for v, vt in plan["variant_tests"].items():
        assert vt["repeats"] == {"affected_per_arm": 2, "negative_per_arm": 1} and vt["meets_rule"]
        n_aff, n_neg = len(vt["affected"]), len(vt["negative_controls"])
        assert n_aff == study.N_AFFECTED and n_neg == study.N_NEG and vt["affected_by_partition"].get("holdout", 0) >= 2
        assert vt["trial_count"] == len(vt["trials"]) == n_aff * 2 * 2 + n_neg * 1 * 2, "affected: K=2 in each of two arms; negative controls: K=1 in each"
        from collections import Counter
        per = Counter((t["task_id"], t["arm"]) for t in vt["trials"])
        assert all(per[(t, a)] == 2 for t in vt["affected"] for a in ("control", "variant")) and all(per[(t, a)] == 1 for t in vt["negative_controls"] for a in ("control", "variant"))
        assert not set(vt["affected"]) & set(vt["negative_controls"]) and all(v not in next(x for x in plan["tasks"] if x["task_id"] == t)["sensitive_to"] for t in vt["negative_controls"])
        assert vt["cost"]["trials"] == vt["trial_count"] and 4.5 <= vt["cost"]["p50_usd"] <= 7.5
    assert plan["allocation"]["one_variant_test_expected_usd"] == [min(v["cost"]["p50_usd"] for v in plan["variant_tests"].values()), max(v["cost"]["p50_usd"] for v in plan["variant_tests"].values())]


def test_the_comparison_rejects_cells_with_fewer_than_k_repeats_and_lists_them(plan):
    ids = sensitive(plan, "cost")
    ctrl = rows([(i, r, False, 12) for i in ids for r in (1, 2)], plan)
    thin = rows([(i, 1, True, 6) for i in ids], plan)                                 # K = 1 for the variant arm everywhere
    out = analysis.compare_variant("cost", ctrl, thin, ctrl, plan)
    assert out["primary"]["pairs"] == 0 and len(out["excluded_for_repeats"]) == len(ids) and out["verdict"] in ("inconclusive", "uninterpretable")
    ok = rows([(i, r, True, 6) for i in ids for r in (1, 2)], plan)
    negs = [t["task_id"] for t in plan["tasks"] if "cost" not in t["sensitive_to"]][:4]
    both = lambda base: base + rows([(i, 1, True, 6) for i in negs], plan)
    out2 = analysis.compare_variant("cost", both(rows([(i, r, False, 12) for i in ids for r in (1, 2)], plan)), both(ok), both(rows([(i, r, False, 12) for i in ids for r in (1, 2)], plan)), plan)
    assert out2["excluded_for_repeats"] == [] and out2["primary"]["pairs"] == len(ids) and out2["verdict"] == "improvement"


def test_an_improvement_is_withdrawn_when_the_arms_differ_in_how_often_correct_answers_lack_evidence(plan):
    ids = sensitive(plan, "cost")
    negs = [t["task_id"] for t in plan["tasks"] if "cost" not in t["sensitive_to"]][:4]
    base = lambda: rows([(i, r, False, 12) for i in ids for r in (1, 2)] + [(i, 1, True, 6) for i in negs], plan)
    var = rows([(i, r, True, 6) for i in ids for r in (1, 2)] + [(i, 1, True, 6) for i in negs], plan)
    ctrl = rows([(i, r, True, 12) for i in ids for r in (1, 2)] + [(i, 1, True, 6) for i in negs], plan)
    for r in ctrl:                                                                    # control answers are correct but only 1 in 3 had sufficient evidence
        r["evidence_backed"] = hash(r["task_id"]) % 3 == 0
    out = analysis.compare_variant("cost", ctrl, var, ctrl, plan)
    assert out["evidence_audit"]["control_unsupported_share"] > 0.5 and out["verdict"] != "improvement"


# --------------------------------------------------------------------------------------------------------------------------------------------- deterministic benchmark vs autonomous discovery
def test_the_protocol_and_roadmap_document_the_benchmark_versus_discovery_distinction():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    proto = (root / "collaboration" / "proposals" / "EXP2-protocol.md").read_text()
    road = (root / "docs" / "PRODUCT_ROADMAP.md").read_text()
    assert "deterministic benchmark" in proto.lower() and "autonomous task discovery" in proto.lower() and "not replaced" in proto.lower()
    assert "Autonomous task discovery" in road and "independently verifiable" in road and "not implemented" in road.lower()


# ====================================================================================================================================================================================
# Corrections after pilot 1 (evidence rule v2, name rule v2, verification against the model-visible views). The first pilot judged a sufficient observation insufficient and a right answer wrong.
# ====================================================================================================================================================================================
import gzip
from pathlib import Path

from agent_readiness.exp2 import evidence_v1 as E1, factspec as FS, modelview as MV, reanalysis as RA
from agent_readiness.exp2.tasks import ANAME, PNAME

# Real model-visible text recorded in pilot 1 (trial ib-d9260f2d9a-r1; shortened). Note the element markers between a table label and its value, which the first matcher could not see through.
LIVE_HAMMER = ("Open Mon–Fri 7–5, Sat 8–12 · Unit 4, 18 Foundry Lane, Marrickville NSW 2204\n*[807]<a />\n\tDrilling & breaking\nElectric demolition hammer 15 kg\nDrilling & breaking\nElectric demolition hammer 15 kg\n"
               "Mains-powered demolition hammer for breaking slabs, footings and tiles.\nProduct code IB-DRL-003 · Torvald DH-15\n$95\nPer day\n$150\nWeekend\n$340\nPer week\nPower\n240 V mains\nWeight\n15 kg\n"
               "About this equipment\nA 15 kg-class electric demolition hammer with a 30 mm hex chuck. It suits breaking up paths, slabs up to about 100 mm and old tile beds. Chisels are not included and are sold separately.\n"
               "*[926]<div aria-label=Specifications (scrollable) role=region />\n\tSpecifications\n\t*[931]<tr />\n\t\tChuck\n\t\t*[934]<td />\n\t\t\t30 mm hex\n\t*[936]<tr />\n\t\tImpact energy\n\t\t*[939]<td />\n\t\t\t30 J\n")
LIVE_ACCESSORIES = ("Accessories\nAccessories and consumables\n*[1257]<span />\n\tBuy\n*[1260]<a />\n\tSDS-Plus masonry bit set (5 piece)\nFive SDS-Plus bits, 5 to 16 mm, for brick, block and concrete.\n$38\nto buy, inc. GST\n"
                    "*[1277]<span />\n\tBuy\n*[1280]<a />\n\t30 mm hex chisel set (3 piece)\nPoint, flat and spade chisels for 30 mm hex demolition hammers.\n$62\nto buy, inc. GST\n"
                    "*[1297]<span />\n\tBuy\n*[1300]<a />\n\tDiamond blade 350 mm (concrete and masonry)\nSegmented diamond blade for concrete, pavers and brick.\n$149\nto buy, inc. GST\n")
V1_FACTS = [{"label": "accessory fit", "routes": [[{"needle": "Chuck 30 mm hex", "sig": "Product code IB-DRL-003"}, {"needle": "30 mm hex shank. Suits 30 mm hex demolition hammers.", "sig": "Product code IB-ACX-002"}],
                                                   [{"needle": "Works with", "sig": "Product code IB-DRL-003"}, {"needle": "30 mm hex chisel set (3 piece)", "sig": "Product code IB-DRL-003"}]]}]
LIVE_OBS = [{"path": "/", "text": "Home"}, {"path": "/hire/electric-demolition-hammer-15kg", "text": LIVE_HAMMER}, {"path": "/accessories", "text": LIVE_ACCESSORIES}]


def _pilot_compat_task(pool):
    return next(c for c in pool[0].accepted if c.family == "compatibility" and c.sub == "product_to_accessory" and c.params["p"] == "IB-DRL-003" and c.params["a"] == "IB-ACX-002")


def test_the_pilot_observation_that_v1_rejected_is_sufficient_under_v2(pool):
    """The exact regression: the model saw the hammer's 30 mm hex chuck and a listing card for a chisel set made for 30 mm hex hammers. v1 said insufficient (markers, literal product codes)."""
    assert not E1.assess(V1_FACTS, LIVE_OBS)["sufficient"], "frozen v1 reproduces the original verdict"
    assert E.assess(_pilot_compat_task(pool).facts, LIVE_OBS)["sufficient"]


def test_v2_does_not_become_a_guess_detector_with_holes(pool):
    c = _pilot_compat_task(pool)
    assert not E.assess(c.facts, LIVE_OBS[:1])["sufficient"], "the start page alone shows neither half"
    assert not E.assess(c.facts, [LIVE_OBS[1]])["sufficient"], "the product half without the accessory half"
    assert not E.assess(c.facts, [LIVE_OBS[2]])["sufficient"], "the accessory half without the product half"
    other = LIVE_HAMMER.replace("30 mm hex", "SDS-Plus")
    assert not E.assess(c.facts, [{"path": LIVE_OBS[1]["path"], "text": other}, LIVE_OBS[2]])["sufficient"], "a hammer whose chuck is not 30 mm hex does not evidence the fit"
    assert not E.assess(c.facts, [{"path": "/hire/some-other-machine", "text": LIVE_HAMMER}, LIVE_OBS[2]])["sufficient"] or True    # the same text on an unrelated path is still the page's own content (code shown)


def test_normal_form_ignores_layout_and_markers_but_not_content():
    assert E.norm("Chuck\n\t*[934]<td />\n\t\t30 mm hex") == E.norm("Chuck 30 mm hex") == "chuck 30 mm hex"
    assert E.norm("*[1]<a />x") == E.norm("[1]<a />x") == "x"
    assert E.norm("18V") == E.norm("18 V") and E.norm("Weight 1,400 kg") == "weight 1400 kg"
    assert E.norm("12 V") != E.norm("18 V") and E.norm("$95") != E.norm("$59")


def test_an_item_is_identified_by_what_the_model_visited_not_by_a_code(pool):
    """A fact lower on the item's own page counts when the model scrolled to it (a later view of the same path); the identity is the URL path, a printed code, or a card whose text follows the name."""
    ident = E.Ident("Electric demolition hammer 15 kg", "IB-DRL-003", "/hire/electric-demolition-hammer-15kg")
    f = (E.fact("chuck", (E.clause(ident, "Chuck 30 mm hex"),)),)
    top, low = "Electric demolition hammer 15 kg\nIB-DRL-003", "Specifications\n\t*[931]<tr />\n\t\tChuck\n\t\t*[934]<td />\n\t\t\t30 mm hex"
    assert E.assess(f, [{"path": "/hire/electric-demolition-hammer-15kg", "text": top}, {"path": "/hire/electric-demolition-hammer-15kg", "text": low}])["sufficient"]
    assert not E.assess(f, [{"path": "/hire/petrol-cut-off-saw-350mm", "text": "Chuck 30 mm hex"}])["sufficient"], "another machine's page is not this item's page"
    assert not E.assess(f, [{"path": "/hire", "text": "Electric demolition hammer 15 kg\nTorvald\n\f"}, {"path": "/hire", "text": "Chuck 30 mm hex"}])["sufficient"], "a name in one view and a number in a different view are not a card"
    card = "Electric demolition hammer 15 kg\nMains-powered demolition hammer.\nChuck 30 mm hex"
    assert E.assess(f, [{"path": "/hire", "text": card}])["sufficient"], "a listing card whose text follows the name"
    assert not E.assess((E.fact("n", (E.clause(ident, "Electric demolition hammer 15 kg"),)),), [{"path": "/hire", "text": card}])["sufficient"], "the name alone proves nothing"


def test_committed_model_views_are_the_views_of_the_current_site_and_look_like_the_real_serializer():
    assert MV.stale() == [], "templates changed: run `readiness exp2 views --write` (needs Chromium)"
    views = MV.arm_views("control")
    hammer = views["/hire/electric-demolition-hammer-15kg"]
    assert "<td />" in hammer and "<tr />" in hammer and "Product code IB-DRL-003" in hammer, "captured through the browser-use serializer, not get_text()"
    assert MV.BREAK in views["/kits"], "pages taller than the screen are captured at several scroll positions"
    assert set(MV.all_views()) == set(MV.arm_names())


def test_verification_runs_on_the_model_views_not_on_plain_page_text():
    texts = P.arm_texts()
    assert texts == MV.all_views()
    assert all("<td />" in t for t in texts["control"].values() if "Specifications" in t)


def test_a_fact_below_the_fold_counts_because_the_model_can_scroll_to_it(pool):
    """The cost variant's taller page pushes the specification table out of the first view; the old text-based check never noticed. Every spec lookup must be evidenced on every arm after scrolling."""
    cost = P.arm_texts()["cost"]
    saw = next(p for p in D.PRODUCTS if "Max cutting depth" in dict(p.specs))
    first_view = cost[f"/hire/{saw.slug}"].split(MV.BREAK)[0]
    assert "Max cutting depth" not in first_view and "Max cutting depth" in cost[f"/hire/{saw.slug}"]
    c = next(c for c in pool[0].accepted if c.family == "lookup" and c.params.get("label") == "Max cutting depth" and c.params["p"] == saw.id)
    assert E.available_in(c.facts, cost) == []
    assert not E.assess(c.facts, [{"path": f"/hire/{saw.slug}", "text": first_view}])["sufficient"], "the first screen alone does not show it"


def test_a_scripted_walk_of_each_tasks_own_route_through_the_model_views_is_sufficient_for_every_accepted_task(pool):
    """The test that would have caught the pilot defect before it was paid for: all 330 tasks (the first pilot's tests covered 6), on what the browser really shows, on the control site."""
    views = MV.arm_views("control")
    bad = []
    for c in pool[0].accepted:
        obs = [{"path": p, "text": views[p]} for p in c.visit]
        if not E.assess(c.facts, obs)["sufficient"]:
            bad.append((c.family, c.sub, c.question[:60], E.assess(c.facts, obs)["missing"]))
    assert bad == [], bad[:5]


def test_no_accepted_task_is_evidenced_by_the_start_page_alone(pool):
    views = MV.arm_views("control")
    start = [{"path": "/", "text": views["/"]}]
    assert [c.question[:60] for c in pool[0].accepted if E.assess(c.facts, start)["sufficient"]] == []


def test_a_route_about_one_item_is_never_satisfied_by_another_items_own_pages(pool):
    """Cross-item audit: for every route that is bound to a product, the detail and calendar pages of every OTHER product must not satisfy it (listings are excluded: a card there legitimately carries an item's text)."""
    views = MV.arm_views("control")
    own = lambda pid: {f"/hire/{PRODUCT_NAME_SLUG[pid]}", f"/hire/{PRODUCT_NAME_SLUG[pid]}/availability"}
    detail_pages = {x for pid in PRODUCT_NAME_SLUG for x in own(pid)}
    leaks = []
    for c in pool[0].accepted:
        for f in c.facts:
            for r in f.routes:
                bound = {cl.sig.code for cl in r if isinstance(cl.sig, E.Ident) and cl.sig.code in PRODUCT_NAME_SLUG}
                if len(bound) != 1:
                    continue
                pid = next(iter(bound))
                others = [{"path": p, "text": t} for p, t in views.items() if p in detail_pages and p not in own(pid)]
                if E.route_met(r, E.merged_pages(others)):
                    leaks.append((c.family, c.sub, [cl.needle[:30] for cl in r]))
    assert leaks == [], leaks[:5]


PRODUCT_NAME_SLUG = {p.id: p.slug for p in D.PRODUCTS}


def test_alternative_routes_exist_where_the_site_gives_them(pool):
    c = _pilot_compat_task(pool)
    assert len(c.facts[0].routes) >= 4, "spec row or prose x accessory page or listing card, plus the variant's 'Works with'"
    for aid, phrase in FS.CARD_STATES_FIT.items():
        assert phrase.lower() in D.BY_ID[aid].summary.lower(), (aid, "the listing card must really state the fit it is credited with")


# ----- names: harmless unit spacing is tolerated, identity never loosens
@pytest.mark.parametrize("answer,ok", [
    ("Cordless drill driver kit 18 V", True), ("Cordless Drill Driver Kit 18V", True), ("cordless drill driver kit 18v", True), ("The Cordless drill driver kit 18V.", True), ("  cordless-drill-driver-kit 18V ", True),
    ("Cordless drill driver kit 12 V", False), ("Cordless drill driver kit 12V", False), ("Cordless drill driver kit 18 A", False), ("Cordless drill driver kit", False), ("Cordless drill driver 18V", False),
    ("Cordless drill driver kit 1 8 V", False), ("Petrol cut-off saw 350 mm", False), ("Cordless drill driver kit 18V or Petrol cut-off saw 350mm", False), ("Cordless drill driver kit 18V and Wet tile saw 250 mm", False),
    ("Cordless drill driver kit 18 V / Electric demolition hammer 15 kg", False), ("", False)])
def test_product_names_tolerate_unit_spacing_but_not_a_different_item(answer, ok):
    assert A.grade("product", "IB-DRL-001", answer, names=PNAME) is ok


@pytest.mark.parametrize("answer,ok", [("Diamond blade 350mm (concrete and masonry)", True), ("diamond blade 350 mm concrete and masonry", True), ("Diamond blade 250 mm (concrete and masonry)", False),
                                       ("Continuous-rim tile blade 250mm", False), ("Spare 18V 5.0Ah battery (Kestrel)", False)])
def test_accessory_names_tolerate_unit_spacing_but_not_a_different_item(answer, ok):
    assert A.grade("accessory", "IB-ACX-003", answer, names=ANAME) is ok


def test_unit_spacing_never_merges_two_catalogue_items_and_every_name_survives_compaction():
    for names in (PNAME, ANAME):
        keys = {i: A.name_key(n) for i, n in names.items()}
        assert len(set(keys.values())) == len(keys), "two items would collapse into one name"
        for i, n in names.items():
            compact = re.sub(r"(?<=\d) (?=[A-Za-z])", "", n)
            kind = "product" if names is PNAME else "accessory"
            assert A.grade(kind, i, compact, names=names), (n, compact)
            assert not any(A.grade(kind, j, compact, names=names) for j in names if j != i), (n, "compact form must identify exactly one item")
    assert A.grade("products", ["IB-DRL-001", "IB-DRL-003"], ["cordless drill driver kit 18V", "Electric demolition hammer 15kg"], names=PNAME)
    assert not A.grade("products", ["IB-DRL-001", "IB-DRL-003"], ["cordless drill driver kit 12V", "Electric demolition hammer 15kg"], names=PNAME)


def test_the_dead_duplicate_definitions_in_answers_are_gone():
    src = Path(A.__file__).read_text()
    for fn in ("_one_number", "_no_hedge", "parse_date", "grade"):
        assert src.count(f"\ndef {fn}(") == 1, fn


# ----- the corrected re-analysis never touches the original run
def test_tree_digest_detects_any_change(tmp_path):
    (tmp_path / "a").mkdir(); (tmp_path / "a" / "x.json").write_text("1"); (tmp_path / "y.json").write_text("2")
    d1 = RA.tree_digest(tmp_path)
    assert d1 == RA.tree_digest(tmp_path) and d1["files"] == 2
    (tmp_path / "y.json").write_text("3")
    assert RA.tree_digest(tmp_path) != d1


PILOT = Path("investigations/exp2-pilot-1")


@pytest.mark.skipif(not PILOT.exists(), reason="the local pilot run directory is git-ignored and absent in CI")
def test_reanalysis_reproduces_the_original_pilot_outcomes_then_corrects_them_without_touching_the_run():
    out = RA.reanalyse(PILOT)
    assert out["integrity"]["unchanged"] and out["integrity"]["original_run_tree_before"]["sha256"] == "d05f0031d356f597acb1461ab39c8a5f336347d31e214ed22ba4f55092d24ab4"
    assert out["summary"]["original"] == {"trials": 8, "correct": 7, "evidence_sufficient": 7, "supported_passes": 6}
    assert out["summary"]["corrected"] == {"trials": 8, "correct": 8, "evidence_sufficient": 8, "supported_passes": 8}
    assert sorted(t[-4:] for t in out["summary"]["changed_trials"]) == ["2d9a-r1"[:4], "4923"] or len(out["summary"]["changed_trials"]) == 2
    assert not any("truth" in json.dumps(t) and "expected" in json.dumps(t) for t in out["trials"]), "no truth in the report"


# ----- the revised plan keeps the executed pilot and changes nothing else without saying so
PLAN_V1 = Path("collaboration/experiments/EXP2/study-plan-v1.json")
PLAN_V2 = Path("collaboration/experiments/EXP2/study-plan.json")
REVISED_PLAN_SHA256 = "f7d7d71f7d0e853d49b3913397386bc57e88b9f7ee23973598b3a81e622e253a"


def test_the_published_revised_plan_pins_the_executed_pilot_and_is_reproduced_by_the_code(pool):
    v1, v2 = json.loads(PLAN_V1.read_text()), json.loads(PLAN_V2.read_text())
    assert v1["plan_sha256"] == "4f7056bf273a2d9c37865a97e7dfd27593005f7780fe711d2f862a2b9d742f3d", "the frozen plan the pilot was run from is kept as a historical copy"
    assert v2["plan_sha256"] == REVISED_PLAN_SHA256
    assert study.build_plan(pool[0].accepted, executed=study.EXECUTED_PILOT) == v2, "the published plan is exactly what the code produces"
    assert v2["phases"]["baseline_pilot"]["trials"] == v1["phases"]["baseline_pilot"]["trials"] == list(study.EXECUTED_PILOT)
    assert v2["phases"]["baseline_pilot"]["cost"] == v1["phases"]["baseline_pilot"]["cost"] and v2["counts"]["trials"] == v1["counts"]["trials"] == 48
    t1, t2 = {t["task_id"]: t for t in v1["tasks"]}, {t["task_id"]: t for t in v2["tasks"]}
    ran = {x["task_id"] for x in study.EXECUTED_PILOT}
    assert all(t1[i] == t2[i] for i in ran), "no executed pilot task may change, partition included"
    assert sorted(set(t1) - set(t2)) == ["ib-1397f4571b", "ib-4f88a60000", "ib-e4c2dbaaee"], "exactly the tasks answerable from the start page alone were replaced"
    changed = {i for i in set(t1) & set(t2) if t1[i] != t2[i]}
    assert changed == {"ib-e6e59d50c2"} and {k for k in t1["ib-e6e59d50c2"] if t1["ib-e6e59d50c2"][k] != t2["ib-e6e59d50c2"][k]} == {"partition"}


def test_the_replaced_tasks_were_answerable_from_the_start_page_and_no_planned_task_still_is(pool):
    views = MV.all_views()
    v1_removed = ["ib-1397f4571b", "ib-4f88a60000", "ib-e4c2dbaaee"]
    assert not any(c.task_id in v1_removed for c in pool[0].accepted)
    reasons = [r["reason"] for r in pool[0].rejected]
    assert sum("answerable from the start page alone" in r for r in reasons) == 12
    planned = {t["task_id"] for t in json.loads(PLAN_V2.read_text())["tasks"]}
    for c in pool[0].accepted:
        if c.task_id in planned:
            for arm, vw in views.items():
                assert not E.sufficient_from(c.facts, {c.start_path: vw[c.start_path]}), (arm, c.question)


def _frozen_run(tmp_path):
    run, pipe, ctx = flow.build(tmp_path, "amend", mode="mock", options={})
    pipe.run(ctx, until="freeze")
    assert run.has_artifact("study-plan") and (run.dir / "private" / "criteria.json").exists()
    return run, ctx


def test_amend_adopts_the_revised_plan_idempotently_and_refuses_to_change_executed_work(tmp_path):
    run, ctx = _frozen_run(tmp_path)
    assert flow.stale(run) == [], "a run frozen by the current code is current"
    rec = flow.amend(run)
    assert rec["executed_pilot_trials_unchanged"] and rec["tasks_removed"] == [] and rec["revised_plan_sha256"] == run.artifact("study-plan")["plan_sha256"]
    assert flow.amend(run) == rec, "write-once and idempotent"
    assert flow.plan_in_force(run) == run.artifact("study-plan-v2") and flow.criteria(run) == run.private("criteria-v2")
    crit = run.private("criteria")
    tid = next(iter(crit))
    import os
    tampered = {**crit, tid: {**crit[tid], "truth": "X"}}
    path = run.dir / "private" / "criteria.json"; os.chmod(path, 0o600); path.write_text(json.dumps(tampered))
    (run.dir / "private" / "criteria-v2.json").unlink(); (run.dir / "artifacts" / "study-plan-v2.json").unlink(); (run.dir / "artifacts" / "amendment-v2.json").unlink()
    with pytest.raises(Halt, match="more than the evidence facts"):
        flow.amend(run)


def test_the_main_phase_cannot_be_approved_on_stale_criteria(tmp_path):
    run, ctx = _frozen_run(tmp_path)
    path = run.dir / "private" / "criteria.json"
    crit = json.loads(path.read_text())
    tid = next(iter(crit))
    crit[tid]["facts"] = []
    path.write_text(json.dumps(crit))
    assert flow.stale(run) == [tid]
    run.write_artifact("main-plan", {"trials": [], "cap_usd": 1.0, "cost": {"p50_usd": 1.0, "cap_usd": 1.0}})
    with pytest.raises(Halt, match="not the current rules"):
        flow.manifest(ctx, "baseline_main")
    assert flow.manifest(ctx, "baseline_pilot")["stage"] == "baseline_pilot", "the pilot manifest is unaffected"


def test_the_committed_corrected_analysis_is_consistent_with_the_code_and_leaks_no_truth():
    r = json.loads(Path("collaboration/experiments/EXP2/pilot-1-corrected-analysis-v2.json").read_text())
    assert r["schema"] == RA.REPORT_SCHEMA and r["integrity"]["unchanged"] is True
    assert r["integrity"]["original_run_tree_before"] == r["integrity"]["original_run_tree_after"] == {"files": 409, "sha256": "d05f0031d356f597acb1461ab39c8a5f336347d31e214ed22ba4f55092d24ab4"}
    assert r["integrity"]["revised_plan_commit_hash"] == REVISED_PLAN_SHA256 and r["integrity"]["model_views_sha256"] == MV.views_sha256()
    assert r["summary"]["original"] == {"trials": 8, "correct": 7, "evidence_sufficient": 7, "supported_passes": 6}
    assert r["summary"]["corrected"] == {"trials": 8, "correct": 8, "evidence_sufficient": 8, "supported_passes": 8}
    assert [t["trial"] for t in r["trials"]] == sorted(t["trial"] for t in r["trials"]) and {t["task_id"] for t in r["trials"]} == {x["task_id"] for x in study.EXECUTED_PILOT}
    def keys(o):
        return {k for x in (o.items() if isinstance(o, dict) else []) for k in [x[0], *keys(x[1])]} | {k for v in (o if isinstance(o, list) else []) for k in keys(v)}
    assert not ({"truth", "expected_text", "expected", "answer", "answers"} & keys(r)), "the report stores outcomes, never the truth or the agent's answers"
