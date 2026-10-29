"""Verification of the main-stage statistics, verdict rule, prospective-only gate, and halting semantics (offline; no model call). The statistical thresholds are NOT tuned here: they are
the ones in the proposal (min 5 valid pairs, mean delta requests <= -3, mean delta visits <= -2, pass-rate not worse, two-sided exact sign-flip p <= 0.07, control within +/-2)."""
import inspect
import itertools
import json
from fractions import Fraction

import pytest

from agent_readiness.remediation import experiment as ex
from agent_readiness.scanner.live import Halt, Ledger
from tests.test_remediation_experiment import go, make_rows, plan, scripted_runner


def brute_p(diffs):
    """Independent exact two-sided sign-flip p: enumerate all 2^n sign assignments with exact rational arithmetic (no floats, no rounding)."""
    d = [Fraction(x).limit_denominator(10 ** 6) for x in diffs]
    obs = abs(sum(d))
    n = len(d)
    hits = sum(1 for s in itertools.product((1, -1), repeat=n) if abs(sum(si * di for si, di in zip(s, d))) >= obs)
    return Fraction(hits, 2 ** n)


@pytest.mark.parametrize("diffs,expected", [
    ([-4, -5, -4, -3, -6, -4], Fraction(1, 32)),             # six consistently favourable (all nonzero): exactly 2/64 = 0.03125
    ([-4, -5, -4, -3, -6], Fraction(1, 16)),                  # five consistently favourable: exactly 2/32 = 0.0625
    ([-4, -5, -4, -3], Fraction(1, 8)),                       # four: 2/16 = 0.125
])
def test_exact_sign_flip_p_for_consistent_effects(diffs, expected):
    assert brute_p(diffs) == expected
    assert ex._sign_flip_p([float(x) for x in diffs]) == float(expected)          # exact, NOT rounded (0.03125, not 0.0312)


@pytest.mark.parametrize("diffs", [
    [-4, -5, 3, -3, -6, 2],                 # mixed favourable and unfavourable
    [-4, 0, -5, 0, -3, -6],                 # zero differences
    [-3, 3, -3, 3, -3, 3],                  # tied absolute values, balanced signs
    [-3, -3, -3, -3, -3, -3],               # all tied absolute values, same sign
    [0, 0, 0, 0, 0, 0],                     # all zero => no evidence at all
    [-2, -2, 1, 1, -1, 4],                  # ties in several magnitudes
    [-1.5, -2.5, -0.5, 3.0, -2.0],          # fractional values
])
def test_sign_flip_matches_an_independent_exact_enumeration(diffs):
    assert ex._sign_flip_p([float(x) for x in diffs]) == pytest.approx(float(brute_p(diffs)), abs=1e-12)


def test_sign_flip_boundary_values():
    assert ex._sign_flip_p([0.0] * 6) == 1.0                                       # all zero => p = 1
    assert ex._sign_flip_p([-3.0] * 6) == 0.03125 and ex._sign_flip_p([-3.0] * 5) == 0.0625
    assert ex._sign_flip_p([-3.0, 3.0] * 3) == 1.0                                 # perfectly balanced tied magnitudes
    mixed = ex._sign_flip_p([-4.0, -5.0, 3.0, -3.0, -6.0, 2.0])
    assert 0.0625 < mixed < 1.0
    assert ex._sign_flip_p([-4.0, -5.0, 3.0, -3.0, -6.0, 2.0]) == ex._sign_flip_p([4.0, 5.0, -3.0, 3.0, 6.0, -2.0])      # symmetric: two-sided


def verdict_of(deltas, **kw):
    _, m = plan("main", 1)
    rows = make_rows(m, deltas)
    for r in rows:
        if r["task_code"] == "T1" and r["state"] == "modified":
            r.update(kw)
    return ex.analyze(rows, m)


@pytest.mark.slow
def test_verdict_uses_the_predeclared_rule_and_threshold_exactly():
    six = verdict_of([-4, -5, -4, -3, -6, -4])
    assert six["verdict"] == "supports" and six["T1"]["p_two_sided_sign_flip"] == 0.03125
    _, m = plan("main", 1)
    rows = [r for r in make_rows(m, [-4, -5, -4, -3, -6, -4]) if r["block"] != 6]            # one block lost: five pairs, p = 0.0625 <= 0.07
    five = ex.analyze(rows, m)
    assert five["T1"]["valid_pairs"] == 5 and five["T1"]["p_two_sided_sign_flip"] == 0.0625 and five["verdict"] == "supports"
    assert ex.VERDICT_RULE["min_valid_pairs"] == 5 and "0.07" in ex.VERDICT_RULE["supports"] and "-3" in ex.VERDICT_RULE["supports"]
    mixed = verdict_of([-4, -5, 3, -3, -6, 2])
    assert mixed["verdict"] in ("inconclusive", "not_supported") and mixed["verdict"] != "supports"
    small_effect = verdict_of([-2, -2, -2, -2, -2, -2])                                    # consistent but below the -3 threshold => not supported as predeclared
    assert small_effect["verdict"] == "inconclusive"
    no_effect = verdict_of([0, 0, 0, 0, 0, 0])
    assert no_effect["verdict"] == "not_supported" and no_effect["T1"]["p_two_sided_sign_flip"] == 1.0


@pytest.mark.slow
def test_pass_rate_must_not_be_worse_for_support():
    worse = verdict_of([-4, -5, -4, -3, -6, -4], passed=False)
    assert worse["verdict"] == "inconclusive" and worse["T1"]["pass_rate"]["modified"] == 0.0


@pytest.mark.parametrize("pairs", [0, 1, 2, 3, 4])
@pytest.mark.slow
def test_fewer_than_five_valid_pairs_is_always_inconclusive_whatever_the_p_value(pairs, monkeypatch):
    _, m = plan("main", 1)
    rows = [r for r in make_rows(m, [-9, -9, -9, -9, -9, -9]) if r["block"] <= pairs]        # enormous, perfectly consistent effect
    monkeypatch.setattr(ex, "_sign_flip_p", lambda diffs: 0.0)                               # even a p-value of exactly 0 must not matter
    an = ex.analyze(rows, m)
    assert an["verdict"] == "inconclusive" and "fewer than 5" in an["verdict_reason"]


@pytest.mark.slow
def test_void_pairs_reduce_the_pair_count_and_can_force_inconclusive():
    _, m = plan("main", 1)
    rows = make_rows(m, [-9] * 6)
    voided = 0
    for r in rows:
        if r["task_code"] == "T1" and r["state"] == "modified" and r["block"] <= 2:
            r["void"], r["outcome_class"] = True, "provider_failure"
            voided += 1
    an = ex.analyze(rows, m)
    assert an["T1"]["valid_pairs"] == 6 - voided == 4 and an["verdict"] == "inconclusive" and len(an["void_rows"]) == 2


# ---------- the gate is prospective-only and never touches the verdict ----------
@pytest.mark.slow
def test_the_verdict_function_cannot_depend_on_the_gate():
    src = inspect.getsource(ex.analyze) + inspect.getsource(ex.effect_record) + inspect.getsource(ex._pairs)
    assert "room_to_act" not in src and "interim_gate" not in src and "GATE_V2" not in src
    _, m = plan("main", 1)
    a = ex.analyze(make_rows(m, [-4, -5, -4, -3, -6, -4]), m)
    rows = make_rows(m, [-4, -5, -4, -3, -6, -4])
    for r in rows:
        if r["state"] == "unmodified" and r["task_code"] == "T1":
            r.update(passed=False, recall=0.33, missing_items=["HP-1006"])                  # give the baseline "room": the gate would say continue, the H1 verdict logic is separate
    b = ex.analyze(rows, m)
    assert a["T1"]["delta_model_requests"] == b["T1"]["delta_model_requests"] and a["T1"]["p_two_sided_sign_flip"] == b["T1"]["p_two_sided_sign_flip"]


@pytest.mark.parametrize("status,klass", [("estimated_cost_limit", "budget_stop"), ("infrastructure_error", "provider_failure"), ("model_output_error", "provider_failure"), ("cancelled", "provider_failure"),
                                          ("timeout", "ambiguous_timeout"), ("diagnostic_fidelity_violation", "guard_violation"), ("request_limit", "agent_limit"), ("completed", "completed")])
def test_run_status_classification_and_voiding(status, klass):
    from agent_readiness.spend_gate import RequestGate
    gate = RequestGate(Ledger.__new__(Ledger), "x") if False else type("G", (), {"violation": None})()
    rec = {"outcome": {"run_status": status, "stop_reason": "s"}, "protocol": {}}
    c = ex.classify(rec, gate)
    assert c["outcome_class"] == klass and c["void"] is (klass not in ("completed", "agent_limit"))
    bound = ex.classify(rec, type("G", (), {"violation": "bound exceeded"})())
    assert bound["outcome_class"] == "guard_violation" and bound["void"]


# ---------- halts are final; interim edge cases ----------
@pytest.mark.slow
def test_a_halted_stage_cannot_be_resumed_by_simply_running_the_command_again(tmp_path):
    _, m = plan("main", 41)
    s = [e["run_id"] for e in m["schedule"]]
    r = go(m, tmp_path, scripted_runner({s[0]: {"status": "infrastructure_error", "passed": False}, s[1]: {"status": "infrastructure_error", "passed": False}}))
    assert r["halt"]["reason"] == "max_void_runs"
    again = scripted_runner({})
    with pytest.raises(Halt, match="halted"):
        go(m, tmp_path, again)
    assert again.calls == []                                                                  # no further run was started
    assert len(ex.read_rows(tmp_path / "main" / "rows.jsonl")) == 2


@pytest.mark.slow
def test_no_room_and_budget_halts_are_final_too(tmp_path):
    _, m = plan("main", 42)
    easy = {e["run_id"]: {"requests": 4, "visits": 2} for e in m["schedule"] if e["task_code"] == "T1" and e["state"] == "unmodified"}
    r = go(m, tmp_path / "a", scripted_runner(easy))
    assert r["halt"]["reason"] == "no_room_to_act_after_block_2"
    with pytest.raises(Halt, match="halted"):
        go(m, tmp_path / "a", scripted_runner({}))
    r2 = go(m, tmp_path / "b", scripted_runner({m["schedule"][0]["run_id"]: {"status": "estimated_cost_limit", "requests": 0, "visits": 0, "passed": False}}))
    assert r2["halt"]["reason"] == "budget_stop"
    with pytest.raises(Halt, match="halted"):
        go(m, tmp_path / "b", scripted_runner({}))


@pytest.mark.slow
def test_a_run_that_started_but_left_no_row_is_recovered_as_void_and_halts_the_stage(tmp_path):
    _, m = plan("main", 43)
    first = m["schedule"][0]["run_id"]
    led = Ledger(tmp_path / "main" / "ledger", ceiling=4.0)
    led.reserve(first, 0.0)                                                                   # simulate a crash: the run marker exists, no row was written
    runner = scripted_runner({})
    with pytest.raises(Halt, match="halted"):
        go(m, tmp_path, runner)
    rows = ex.read_rows(tmp_path / "main" / "rows.jsonl")
    assert runner.calls == [] and rows[0]["run_id"] == first and rows[0]["void"] and "crash" in rows[0]["attribution"]


def test_interim_gate_with_one_void_and_one_no_room_is_inconclusive_not_a_ceiling_finding():
    mk = lambda block, **kw: {"task_code": "T1", "state": "unmodified", "block": block, "void": False, "model_requests": 5, "request_limit": 12, "product_page_visits": 2, "passed": True,
                              "recall": 1.0, "missing_items": [], "extra_items": [], "repeated_action_runs": 0, "visibility_gap_steps": 0, "stop_reason": "agent_done", **kw}
    g = ex.interim_gate([mk(1, void=True), mk(2)])
    assert g["decision"] == "halt_inconclusive" and "one valid baseline" in g["reason"]
    assert ex.interim_gate([mk(1), mk(2)])["decision"] == "halt_no_room"                      # a ceiling is claimed only from two valid baselines
