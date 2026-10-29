"""Main-stage design for Task 015 (offline): the stock-filter factor that isolates labels from the filter, product recognition of the intermediate state, the corrected prospective gate
(including the pilot's incomplete-answer scenario), interim stopping, preservation of the original pilot artifacts, and the programme ledger. No model call."""
import asyncio
import hashlib
import json
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from agent_readiness import budget
from agent_readiness.environments.electronics.variants import make_variant
from agent_readiness.remediation import experiment as ex
from agent_readiness.remediation.engine import build_report
from agent_readiness.remediation.probe import SiteProbe
from agent_readiness.remediation.targets import DEFAULT_INITIAL, ManagedTarget
from agent_readiness.scanner.serve import serve_app
from agent_readiness.suite import core, registry

PILOT = Path(__file__).resolve().parents[1] / "collaboration" / "experiments" / "task015" / "pilot"
PINS = {"manifest.json": "6e9174acec0f39b652a164d050a9c9ee3a18092606ce5a72da806bf28f94b648", "audit-baseline.json": "6d88a8683f484f06b16d1a7305a021103d4609b3e2cd072c6888916ef5a28272",
        "results/rows.jsonl": "98ffe4f7d472f93109ee3e007578c688bbbffb76d58f5a3ef702cefec9d3430f", "results/pilot-gate.json": "f16a07de8d2c148090fa16d8c64259d46a2c2cee1b173358b013a926a553c0de",
        "results/effect-record.json": "334466c23e658b0b05cd0a6617ccf9e8f8c4bf0a11fca8c2bbd78c109e0a1a44", "results/ledger.jsonl": "402ac98e96175e7f9189ecbadb0f2f7fea5f947b21ae3becec9f54f313d883e3",
        "results/status.json": "c3ca9253aa0bc1891b793f879535e762d97fafbe70d484fb5aa780db9ad023f5", "results/reaudit.json": "ef4fd6442dea0eb9d57f0fe78262851870d1858ce7ec276acfb73bb480076dbc"}


def audit_factors(factors, previous=None):
    registry.load_all()

    async def go():
        async with serve_app(core.ENVIRONMENTS["electronics-v1"].create_app(ex.variant_of(factors))) as base:
            return build_report(await asyncio.to_thread(lambda: SiteProbe(base, allow_private_hosts=True).run()), objective="every in-stock ANC headphone under A$250", previous=previous, target="demo-shop")
    return asyncio.run(go())


U = dict(DEFAULT_INITIAL)
C = {**U, "availability": "listing", "stockfilter": "off"}
M = {**U, "availability": "listing"}


# ---------- the isolating factor ----------
def test_stock_filter_factor_isolates_labels_from_the_filter_without_touching_original_variants():
    registry.load_all()
    assert make_variant("listing", "structured").variant_id == "electronics-v1/availability-listing+specs-structured"                 # original ids unchanged
    assert make_variant("listing", "structured", "listing", "off").variant_id.endswith("availability-listing+specs-structured+sku-listing+stockfilter-off")
    with pytest.raises(ValueError):
        make_variant("detail", "structured", "listing", "off")                                       # meaningless combination refused
    env = core.ENVIRONMENTS["electronics-v1"]
    page = lambda f, q="": TestClient(env.create_app(ex.variant_of(f))).get("/c/headphones" + q).text
    u, c, m = page(U), page(C), page(M)
    assert "In stock" not in u.split("<main")[1] and 'id="f-stock"' not in u                                                              # unmodified: no labels, no filter
    assert "In stock" in c and "Out of stock" in c and 'id="f-stock"' not in c                                                            # labels only: labels yes, filter no
    assert "In stock" in m and 'id="f-stock"' in m                                                                                        # as issued: both
    n = lambda f: TestClient(env.create_app(ex.variant_of(f))).get("/c/headphones?anc=1&in_stock=1&max_price=250").text.count('class="card"')
    assert n(C) == n(U) == 5 and n(M) == 3                                                                                                # the in_stock parameter works only when the filter exists
    originals = [make_variant(a, s) for a in ("listing", "detail") for s in ("structured", "fragmented")]
    assert len({v.variant_id for v in originals}) == 4 and not any("stockfilter" in v.variant_id for v in originals)


def test_product_recognises_the_labels_only_state_and_recommends_the_remaining_change():
    base = audit_factors(U)
    mid = audit_factors(C, previous=base)
    fp = {f["fingerprint"] for f in mid["findings"]}
    assert "attribute_on_cards:availability" in fp and "attribute_detail_only:availability" not in fp and "filter_absent:availability" in fp
    life = {i["fingerprint"]: i["status"] for i in mid["lifecycle"]["items"]}
    assert life["attribute_detail_only:availability"] == "resolved" and life["filter_absent:availability"] == "persisting"
    rec = [r for r in mid["recommendations"] if r["template"] == "offer-in-stock-filter"]
    assert len(rec) == 1 and rec[0]["change_id"] == "in-stock-filter" and rec[0]["validation"] == "unvalidated" and rec[0]["addresses"] == ["filter_absent:availability"]
    assert [r["template"] for r in base["recommendations"] if "availability" in r["template"] or "stock" in r["template"]] == ["show-availability-on-listing-cards"]    # the baseline still gets ONE bundled stock recommendation
    t = ManagedTarget("demo-shop", "d", dict(C), [])
    t.apply("in-stock-filter")
    assert t.factors == {**C, "stockfilter": "on"}
    final = audit_factors(M, previous=mid)
    assert {i["fingerprint"]: i["status"] for i in final["lifecycle"]["items"]}["filter_absent:availability"] == "resolved"


# ---------- corrected prospective gate ----------
def row(**kw):
    base = {"task_code": "T1", "state": "unmodified", "block": 1, "void": False, "model_requests": 5, "request_limit": 12, "product_page_visits": 2, "passed": True, "recall": 1.0,
            "missing_items": [], "extra_items": [], "repeated_action_runs": 0, "visibility_gap_steps": 0, "stop_reason": "agent_done"}
    return {**base, **kw}


def test_the_pilots_incomplete_answer_scenario_now_shows_room_to_act_while_the_original_gate_stays_stop():
    rows = [json.loads(l) for l in (PILOT / "results" / "rows.jsonl").read_text().splitlines()]
    un = next(r for r in rows if r["state"] == "unmodified")
    assert ex.pilot_gate(rows)["decision"] == "stop"                                         # the ORIGINAL frozen rule, evaluated on the original data, is unchanged
    g = ex.room_to_act({**un, "request_limit": 12})
    assert g["room"] and {"R1_incomplete_answer", "R2_oracle_fail_on_recall", "R3_budget_exhausted_with_unchecked_candidates"} <= set(g["criteria"])
    assert g["evidence"]["missing"] == ["HP-1006", "HP-1007"] and g["evidence"]["model_requests"] == 11
    mod = next(r for r in rows if r["state"] == "modified")
    assert not ex.room_to_act({**mod, "request_limit": 12})["room"]                           # the modified pilot run (complete, 4 requests) offers no room, as it should not


@pytest.mark.parametrize("case,kw,room,criteria", [
    ("complete answer, few requests (a true ceiling)", {}, False, set()),
    ("missing eligible products", {"passed": False, "recall": 0.33, "missing_items": ["HP-1006", "HP-1007"]}, True, {"R1_incomplete_answer", "R2_oracle_fail_on_recall"}),
    ("budget exhausted with candidates unchecked", {"passed": False, "recall": 0.33, "missing_items": ["HP-1006"], "model_requests": 11}, True, {"R3_budget_exhausted_with_unchecked_candidates"}),
    ("complete but substantial effort", {"model_requests": 10, "product_page_visits": 5}, True, {"R4_substantial_task_effort"}),
    ("many requests only because of a tool loop (not task effort)", {"model_requests": 11, "repeated_action_runs": 1}, False, set()),
    ("tool-visibility gap inflates effort", {"model_requests": 11, "visibility_gap_steps": 3}, False, set()),
    ("an out-of-stock product was reported", {"passed": False, "extra_items": ["HP-1005"]}, True, {"R5_wrong_inclusion"}),
    ("request-limit stop with a complete answer", {"stop_reason": "request_limit", "model_requests": 12}, True, {"R4_substantial_task_effort"}),
])
def test_corrected_gate_cases(case, kw, room, criteria):
    g = ex.room_to_act(row(**kw))
    assert g["room"] is room and criteria <= set(g["criteria"]), case


@pytest.mark.parametrize("cls", ["budget_stop", "provider_failure", "ambiguous_timeout", "guard_violation"])
def test_void_runs_are_never_room_to_act_even_if_they_look_incomplete(cls):
    g = ex.room_to_act(row(void=True, outcome_class=cls, passed=False, recall=0.0, missing_items=["HP-1004"], model_requests=12))
    assert g["room"] is False and g["void"] is True and "never counted" in g["note"]


def test_interim_gate_decisions():
    mk = lambda block, **kw: row(block=block, **kw)
    assert ex.interim_gate([mk(1)])["decision"] == "pending"
    assert ex.interim_gate([mk(1), mk(2)])["decision"] == "halt_no_room"
    assert ex.interim_gate([mk(1, passed=False, recall=0.33, missing_items=["HP-1006"]), mk(2)])["decision"] == "continue"                 # one baseline run with room is enough
    assert ex.interim_gate([mk(1, void=True), mk(2, void=True)])["decision"] == "halt_inconclusive"                                           # two voids: not a website result, no replacement
    one_void = ex.interim_gate([mk(1, void=True), mk(2, model_requests=11, passed=False, recall=0.33, missing_items=["HP-1006"])])
    assert one_void["decision"] == "continue"
    assert ex.interim_gate([mk(1), mk(2), {**mk(1), "state": "modified", "passed": False}])["decision"] == "halt_no_room"                      # only the unmodified arm is judged


# ---------- main stage runs, stopping, manifest ----------
from tests.test_remediation_experiment import go, plan, scripted_runner                                   # noqa: E402  (reuse the stub runner helpers)


def test_main_stage_halts_after_block_two_when_the_baseline_leaves_no_room(tmp_path):
    _, m = plan("main", 31)
    easy = {e["run_id"]: {"requests": 4, "visits": 2} for e in m["schedule"] if e["task_code"] == "T1" and e["state"] == "unmodified"}      # baseline solves it cheaply and completely
    r = go(m, tmp_path, scripted_runner(easy))
    assert r["halt"]["reason"] == "no_room_to_act_after_block_2" and r["runs_attempted"] < len(m["schedule"])
    assert json.loads((tmp_path / "main" / "interim-gate.json").read_text())["decision"] == "halt_no_room"
    rows = ex.read_rows(tmp_path / "main" / "rows.jsonl")
    assert max(r["block"] for r in rows) <= 2 and all(not r["void"] for r in rows)                          # a ceiling is reported as such, not as a website result


def test_main_stage_continues_when_a_baseline_run_shows_room_and_completes_without_replacements(tmp_path):
    _, m = plan("main", 32)
    table = {e["run_id"]: {"passed": False, "requests": 11, "visits": 3, "extra": []} for e in m["schedule"] if e["task_code"] == "T1" and e["state"] == "unmodified"}
    r = go(m, tmp_path, scripted_runner(table))
    assert r["complete"] and r["runs_attempted"] == 24 and r["halt"] is None
    rows = ex.read_rows(tmp_path / "main" / "rows.jsonl")
    assert len({x["run_id"] for x in rows}) == 24


def test_main_manifest_freezes_the_corrected_design_and_carries_the_original_pilot_result(tmp_path):
    from agent_readiness.remediation import cli_impl
    prior = cli_impl.prior_stage_from(PILOT / "results")
    _, m = plan("main", 20261030, prior_stage=prior)
    assert m["stage"] == "main" and m["arms"] == ["unmodified", "labels_only", "modified"] and m["gate"]["id"] == "room-to-act-v2" and m["causal_question"] and set(m["hypotheses"]) >= {"H1_confirmatory", "negative_control"}
    assert prior["original_gate_decision"] == "stop" and "ceiling effect" in prior["original_gate_reason"] and "wrong" in prior["erratum"] and prior["pilot_manifest_sha256"].startswith("25a22bfd")
    assert m["limits"]["stage_cap_aud"] == 6.0 and m["limits"]["stage_cap_usd"] == 4.0 and m["limits"]["per_request_usd"] == 0.05 and m["limits"]["per_run_usd"] == 0.50
    ce = m["cost_envelope"]
    assert ce["expected_aud"][0] < ce["expected_aud"][1] < ce["expected_aud"][2] < ce["worst_case_aud"] == 6.0 and 2.0 < ce["expected_aud"][1] < 4.5
    assert m["budget_check"]["remaining_before_aud"] == pytest.approx(43.7933, abs=1e-2) and m["budget_check"]["remaining_after_stage_cap_aud"] == pytest.approx(37.7933, abs=1e-2)
    assert m["stopping_rules"]["retries"] == "never" and "no_room_to_act_after_block_2" in m["stopping_rules"]["halt_on"]
    states = m["frozen"]["states"]
    assert states["unmodified"]["variant_id"].endswith("availability-detail+specs-structured+sku-listing") and states["labels_only"]["variant_id"].endswith("stockfilter-off") and states["modified"]["variant_id"].endswith("availability-listing+specs-structured+sku-listing")
    assert m["frozen"]["agent_profile"] == "suite-v2-compat1" and m["manifest_sha256"] == ex.manifest_hash(m)


# ---------- preservation ----------
def test_original_pilot_manifest_results_and_gate_are_preserved_byte_for_byte():
    for rel, sha in PINS.items():
        assert hashlib.sha256((PILOT / rel).read_bytes()).hexdigest() == sha, rel
    m = json.loads((PILOT / "manifest.json").read_text())
    assert m["manifest_sha256"] == "25a22bfdba02363b0b31eecbd1c3834b5744372dcf35ec79c2c111a1d6ae08b3" and ex.manifest_hash(m) == m["manifest_sha256"]
    gate = json.loads((PILOT / "results" / "pilot-gate.json").read_text())
    assert gate["decision"] == "stop" and "ceiling effect" in gate["reason"]                       # recorded as `stop`; the erratum lives in separate files


def test_programme_ledger_records_the_pilot_and_does_not_count_it_twice():
    led = budget.load()
    s = budget.summary(led)
    assert any(e["id"] == "task015-pilot" and e["usd"] == pytest.approx(0.214509) for e in led["entries"]) and "pilot" in led["recorded_runtime_stages"]
    assert s["spent_aud"] == pytest.approx(6.2067, abs=1e-3) and s["remaining_aud"] == pytest.approx(43.7933, abs=1e-3)
    assert budget.check_stage(6.0)["remaining_after_cap_aud"] == pytest.approx(37.7933, abs=1e-3)
