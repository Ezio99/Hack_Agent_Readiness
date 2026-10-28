"""Task 012 infrastructure: schedule, manifest/drift, ledger, driver safety paths, metrics, analysis. Stub runners only - no browser, no model, no network."""
import copy
import json
import random

import pytest

from agent_readiness.environments.electronics.variants import make_variant
from agent_readiness.experiments import analysis, design, driver, manifest as manifest_mod, metrics, schedule as S
from agent_readiness.experiments.ledger import ExperimentLedger
from agent_readiness.scanner.live import Halt
from agent_readiness.suite import core, registry

registry.load_all()


@pytest.fixture(scope="module")
def frozen():
    return manifest_mod.build_manifest()


def fake(task_id, variant, *, status="completed", passed=True, cost=0.08, requests=5, rejected=0, mode="mock", ev=True, answer=None):
    inst = registry.get_instance(task_id)
    return {"scan": {"mode": mode}, "task": {"task_id": task_id}, "variant": {"id": variant.variant_id}, "artifact_path": "/nonexistent",
            "outcome": {"run_status": status, "stop_reason": status, "errors": [], "answer": answer},
            "evaluation": {"passed": passed, "evidence_backed": passed and ev, "answer_valid": passed, "missing_evidence": [] if ev else ["observed_text:x"], "reasons": []},
            "metrics": {"model_requests": requests, "steps": requests, "elapsed_seconds": 10.0, "prompt_tokens": 1, "completion_tokens": 1, "calculated_cost_usd": cost},
            "journey": [{"step": 1, "path": "/", "query": "", "actions": [{"name": "navigate", "params": {}}], "executed": []}], "protocol": {"recovery_rejected": rejected},
            "diagnostics": {"findings": [{"category": "task_outcome", "title": "t"}]}}


def runner(script):
    calls = []
    async def r(task_id, variant, **kw):
        calls.append((task_id, variant.variant_id, kw["provider"]))
        spec = script(len(calls), task_id, variant)
        if isinstance(spec, BaseException):
            raise spec
        return spec
    r.calls = calls
    return r


def go(tmp_path, frozen, stage=1, run=None, ledger=None, **kw):
    sched = S.build_schedule(stage)
    ledger = ledger or ExperimentLedger(tmp_path / "led")
    run = run or runner(lambda n, t, v: fake(t, v))
    rep = driver.run_stage(stage, sched, frozen, ledger, tmp_path / "out", runner=run, current_manifest=lambda: frozen, **kw)
    return sched, ledger, run, rep


# ---- schedule ----------------------------------------------------------------------------------------------------------------------
def test_stage1_matrix_is_exactly_the_eight_approved_runs():
    s = S.build_schedule(1)
    cells = sorted((e["task_code"], e["variant_code"]) for e in s["entries"])
    assert cells == [(t, v) for t in ("T1", "T2", "T3", "T4") for v in ("V0", "V3")]
    for b in (1, 2):                                    # each block: every task once
        assert sorted(e["task_code"] for e in s["entries"] if e["block"] == b) == ["T1", "T2", "T3", "T4"]
    assert {e["task_id"] for e in s["entries"]} == set(design.PRIMARY_TASKS.values()) and {e["variant_id"] for e in s["entries"]} == {design.variant_id("V0"), design.variant_id("V3")}
    leaders = [next(e for e in s["entries"] if e["task_code"] == t and e["block"] == 1)["variant_code"] for t in ("T1", "T2", "T3", "T4")]
    assert sorted(leaders) == ["V0", "V0", "V3", "V3"]       # leading variant balanced
    assert "NOT a causal comparison" in s["purpose"]


def test_stage2_matrix_and_counts():
    s = S.build_schedule(2)
    assert len(s["entries"]) == 29
    count = lambda t, v: sum(1 for e in s["entries"] if (e["task_code"], e["variant_code"]) == (t, v))
    assert all(count(t, v) == 3 for t in ("T1", "T2", "T3") for v in ("V0", "V1", "V2")) and count("T4", "V0") == 2 and not any(e["variant_code"] == "V3" for e in s["entries"])


def test_schedule_is_deterministic_from_seed_and_validates():
    assert S.build_schedule(1) == S.build_schedule(1) and S.build_schedule(1, 7)["schedule_hash"] != S.build_schedule(1)["schedule_hash"]
    assert [e["run_id"] for e in S.build_schedule(1, 7)["entries"]] == [e["run_id"] for e in S.build_schedule(1, 7)["entries"]]
    bad = copy.deepcopy(S.build_schedule(1))
    bad["entries"][0]["variant_code"], bad["entries"][0]["variant_id"] = "V1", design.variant_id("V1")
    with pytest.raises(ValueError):
        S.validate(bad)
    tampered = copy.deepcopy(S.build_schedule(1)); tampered["seed"] = 1
    with pytest.raises(ValueError, match="hash"):
        S.validate(tampered)


# ---- manifest / drift --------------------------------------------------------------------------------------------------------------
def test_manifest_is_stable_and_covers_the_frozen_configuration(frozen):
    again = manifest_mod.build_manifest()
    assert again["manifest_hash"] == frozen["manifest_hash"]
    assert frozen["agent"]["output_parser"] == "muse-prose-prefix-json-v1" and frozen["agent"]["model"] == "muse-spark-1.3" and frozen["agent"]["profile_id"] == "suite-v1-compat1"
    assert set(frozen["fixtures"]) == {"T1", "T2", "T3", "T4"} and frozen["budget"]["programme_ceiling_usd"] == 6.0 and frozen["environment"]["data_version"].startswith("electronics-v1+")
    assert all(f["limits"] == {"max_steps": 12, "max_model_requests": 12, "timeout_seconds": 240} for f in frozen["fixtures"].values())


@pytest.mark.parametrize("mutate,expect", [
    (lambda m: m["agent"].update(output_parser="other"), "manifest section changed: agent"),
    (lambda m: m["fixtures"]["T1"].update(spec_hash="x"), "manifest section changed: fixtures"),
    (lambda m: m["environment"].update(data_version="electronics-v1+changed"), "manifest section changed: environment"),
    (lambda m: m["budget"].update(run_reserve_usd=9), "manifest section changed: budget"),
])
def test_configuration_drift_is_detected_and_halts_before_the_run(tmp_path, frozen, mutate, expect):
    cur = copy.deepcopy(frozen); mutate(cur); cur["manifest_hash"] = core.canonical_hash({k: v for k, v in cur.items() if k not in ("manifest_hash", "provenance")})
    assert expect in manifest_mod.drift(frozen, cur)
    run = runner(lambda n, t, v: fake(t, v))
    rep = driver.run_stage(1, S.build_schedule(1), frozen, ExperimentLedger(tmp_path / "l"), tmp_path / "o", runner=run, current_manifest=lambda: cur)
    assert rep["halted"] and "drift" in rep["halt_reason"] and not run.calls and rep["partial"] and len(rep["not_started"]) == 8


def test_commit_drift_halts(tmp_path, frozen):
    cur = copy.deepcopy(frozen); cur["provenance"]["commit"] = "0" * 40
    rep = driver.run_stage(1, S.build_schedule(1), frozen, ExperimentLedger(tmp_path / "l"), tmp_path / "o", runner=runner(lambda n, t, v: fake(t, v)), current_manifest=lambda: cur)
    assert rep["halted"] and "code commit changed" in rep["halt_reason"]


# ---- ledger ------------------------------------------------------------------------------------------------------------------------
def test_ledger_stage_and_programme_ceilings(tmp_path):
    L = ExperimentLedger(tmp_path, 6.0, {1: 1.5, 2: 4.5})
    L.reserve("a", 0.48, 1); L.settle("a", 0.10, 1)
    assert L.committed() == pytest.approx(0.10) and L.remaining(1) == pytest.approx(1.40)
    for i in range(2):
        L.reserve(f"x{i}", 0.48, 1)                             # unsettled reservations stay fully counted
    assert L.committed(1) == pytest.approx(0.10 + 0.96) and L.unsettled() == ["x0", "x1"]
    with pytest.raises(Halt, match="stage 1 ceiling"):
        L.reserve("y", 0.48, 1)
    L2 = ExperimentLedger(tmp_path / "p", 6.0, {1: 5.9, 2: 5.9})
    for i in range(12):
        L2.reserve(f"s1-{i}", 0.48, 1)
    with pytest.raises(Halt, match="programme ceiling"):
        L2.reserve("s2-1", 0.48, 2)                             # programme-wide across stages
    with pytest.raises(Halt, match="already attempted"):
        L2.reserve("s1-0", 0.01, 1)


def test_settled_runs_release_unused_budget(tmp_path):
    L = ExperimentLedger(tmp_path, 1.0, {1: 1.0, 2: 1.0})
    for i in range(10):
        L.reserve(f"r{i}", 0.48, 1); L.settle(f"r{i}", 0.05, 1)       # ten runs fit because each settles far below its reservation
    assert L.committed() == pytest.approx(0.5)


# ---- driver ------------------------------------------------------------------------------------------------------------------------
def test_full_mock_schedule_in_order_labelled_mock_and_within_budget(tmp_path, frozen):
    sched, L, run, rep = go(tmp_path, frozen)
    assert [c[0] for c in run.calls] == [e["task_id"] for e in sched["entries"]] and [c[1] for c in run.calls] == [e["variant_id"] for e in sched["entries"]]
    assert {c[2] for c in run.calls} == {"mock"} and not rep["halted"] and not rep["partial"] and rep["banner"].startswith("MOCK")
    assert L.committed() == pytest.approx(0.64) and not L.unsettled()
    rows = analysis.load_rows(tmp_path / "out" / "stage1" / "results.jsonl")
    assert len(rows) == 8 and {r["mode"] for r in rows} == {"mock"}


def test_resume_never_repeats_an_attempt(tmp_path, frozen):
    L = ExperimentLedger(tmp_path / "led")
    r1 = runner(lambda n, t, v: fake(t, v) if n <= 3 else KeyboardInterrupt())
    with pytest.raises(KeyboardInterrupt):
        driver.run_stage(1, S.build_schedule(1), frozen, L, tmp_path / "out", runner=r1, current_manifest=lambda: frozen)
    assert len(r1.calls) == 4 and L.unsettled() == [S.build_schedule(1)["entries"][3]["run_id"]]       # interrupted run keeps its reservation
    assert L.committed() == pytest.approx(3 * 0.08 + 0.48)
    r2 = runner(lambda n, t, v: fake(t, v))
    rep = driver.run_stage(1, S.build_schedule(1), frozen, L, tmp_path / "out", runner=r2, current_manifest=lambda: frozen)
    assert len(r2.calls) == 4 and len(rep["skipped_previously_attempted"]) == 4 and rep["partial"] is True and len(rep["interrupted_runs"]) == 1       # the interrupted run is NOT retried; reported as partial
    rows = analysis.load_rows(tmp_path / "out" / "stage1" / "results.jsonl")
    assert [r["run_status"] for r in rows].count("interrupted") == 1 and len(rows) == 8


def test_budget_exhaustion_halts_safely_with_explicit_partial_report(tmp_path, frozen):
    L = ExperimentLedger(tmp_path / "led", 6.0, {1: 1.0, 2: 4.5})
    sched, L, run, rep = go(tmp_path, frozen, ledger=L, run=runner(lambda n, t, v: fake(t, v, cost=0.30)))
    # 0.3 each: after 2 runs committed 0.6; third reservation 0.48 -> 1.08 > 1.0 -> halt before starting it
    assert len(run.calls) == 2 and rep["halted"] and rep["halt_reason"].startswith("budget") and rep["partial"] and len(rep["not_started"]) == 6 and len(rep["completed"]) == 2
    assert rep["ledger"]["committed_usd"] == pytest.approx(0.6)
    res = analysis.analyze(analysis.load_rows(tmp_path / "out" / "stage1" / "results.jsonl"), sched)
    assert res["partial_schedule"] and res["runs_analysed"] == 2          # completed runs are kept and analysed


def test_programme_ceiling_spans_stages(tmp_path, frozen):
    L = ExperimentLedger(tmp_path / "led", 0.7, {1: 1.5, 2: 4.5})
    _, _, run, rep = go(tmp_path, frozen, ledger=L, run=runner(lambda n, t, v: fake(t, v, cost=0.2)))
    assert rep["halted"] and "programme ceiling" in rep["halt_reason"] and len(run.calls) == 2


def test_infrastructure_failures_are_preserved_not_retried_and_halt_at_two(tmp_path, frozen):
    sched, L, run, rep = go(tmp_path, frozen, run=runner(lambda n, t, v: fake(t, v, status="infrastructure_error", passed=False, cost=0.0, requests=0)))
    assert len(run.calls) == 2 and rep["halted"] and "infrastructure" in rep["halt_reason"] and len(rep["completed"]) == 2
    rows = analysis.load_rows(tmp_path / "out" / "stage1" / "results.jsonl")
    assert [r["run_status"] for r in rows] == ["infrastructure_error"] * 2
    assert len({c[0] + c[1] for c in run.calls}) == 2            # no run was repeated


@pytest.mark.parametrize("status", sorted(design.GUARD_STOPS))
def test_guard_class_failures_halt(tmp_path, frozen, status):
    _, _, run, rep = go(tmp_path, frozen, run=runner(lambda n, t, v: fake(t, v, status=status, passed=False)))
    assert len(run.calls) == 1 and rep["halted"] and status in rep["halt_reason"]


def test_run_exceeding_its_reservation_and_parser_rejections_halt(tmp_path, frozen):
    _, _, run, rep = go(tmp_path, frozen, run=runner(lambda n, t, v: fake(t, v, cost=0.6)))
    assert len(run.calls) == 1 and "exceeded its reservation" in rep["halt_reason"]
    _, _, run2, rep2 = go(tmp_path / "b", frozen, run=runner(lambda n, t, v: fake(t, v, rejected=1)))
    assert len(run2.calls) == 2 and "recovery rejected" in rep2["halt_reason"]


def test_kill_switch_halts_before_next_run(tmp_path, frozen):
    out = tmp_path / "out"; out.mkdir()
    (out / "KILL_SWITCH").write_text("x")
    _, _, run, rep = go(tmp_path, frozen)
    assert not run.calls and rep["halt_reason"] == "kill switch file present"


def test_live_mode_is_refused_without_flag_hash_and_key(tmp_path, frozen, monkeypatch):
    sched, L = S.build_schedule(1), ExperimentLedger(tmp_path / "l")
    monkeypatch.setenv("META_MODEL_API_KEY", "k")
    run = runner(lambda n, t, v: fake(t, v, mode="live"))
    with pytest.raises(Halt, match="approved-schedule-hash"):
        driver.run_stage(1, sched, frozen, L, tmp_path / "o", mode="live", runner=run, current_manifest=lambda: frozen, allow_model_calls=True)
    with pytest.raises(Halt, match="allow-model-calls"):
        driver.run_stage(1, sched, frozen, L, tmp_path / "o", mode="live", runner=run, current_manifest=lambda: frozen, approved_schedule_hash=sched["schedule_hash"])
    monkeypatch.delenv("META_MODEL_API_KEY")
    monkeypatch.setattr("agent_readiness.env.load_repo_env", lambda *a, **k: False)
    with pytest.raises(Halt, match="not set"):
        driver.run_stage(1, sched, frozen, L, tmp_path / "o", mode="live", runner=run, current_manifest=lambda: frozen, allow_model_calls=True, approved_schedule_hash=sched["schedule_hash"])
    assert not run.calls


# ---- metrics -----------------------------------------------------------------------------------------------------------------------
def test_partial_accuracy_fields():
    t2 = registry.get_instance("t2-compare-air14-vs-probook15")
    good = dict(t2.truth)
    ans = {"a": {k: good["a"][k] for k in ("sku", "ram_gb", "battery_hours")}, "b": {k: good["b"][k] for k in ("sku", "ram_gb", "battery_hours")}, "more_ram": good["more_ram"], "longer_battery": good["longer_battery"]}
    assert metrics.partial_accuracy(t2, ans)["score"] == 1.0
    ans["a"]["ram_gb"] += 1
    r = metrics.partial_accuracy(t2, ans)
    assert r["score"] == 0.875 and r["fields"]["a.ram_gb"] is False
    assert metrics.partial_accuracy(t2, None)["score"] == 0.0
    t1 = registry.get_instance("t1-anc-headphones-under-250-all")
    el = dict(t1.truth["eligible"])
    sku = next(iter(el))
    p = metrics.partial_accuracy(t1, {"products": [{"sku": sku, "price_cents": el[sku]}, {"sku": "NOPE", "price_cents": 1}]})
    assert p["precision"] == 0.5 and 0 < p["score"] < 1
    t3 = registry.get_instance("t3-cheapest-monitor-27in-usbc-120hz")
    assert metrics.partial_accuracy(t3, {"sku": t3.truth["answer_sku"], "price_cents": 1})["score"] == pytest.approx(2 / 3, abs=1e-3)


def test_visit_taxonomy_separates_required_reverification_and_navigation():
    inst = registry.get_instance("t4-policy-delivery-tessera-whisper")
    from agent_readiness.suite.runner import page_text
    from fastapi.testclient import TestClient
    env = core.ENVIRONMENTS["electronics-v1"]
    c = TestClient(env.create_app(make_variant("listing", "structured")), base_url="http://shop.local")
    def ob(path):
        return core.Observation(path, c.get(path).text)
    tax = metrics.visit_taxonomy(inst, [ob("/"), ob("/p/tessera-whisper"), ob("/help/returns"), ob("/help/delivery"), ob("/help/returns")])
    assert [t["kind"] for t in tax] == ["navigation", "required", "required", "required", "re_verification"]


# ---- analysis ----------------------------------------------------------------------------------------------------------------------
def rows_for(stage, effect):
    s = S.build_schedule(stage); rows = []
    rng = random.Random(1)
    for e in s["entries"]:
        degraded = effect and e["variant_code"] in ("V3", "V1", "V2")
        base = dict(run_id=e["run_id"], stage=stage, block=e["block"], task_code=e["task_code"], variant_code=e["variant_code"], mode="live", run_status="completed",
                    success=not (degraded and rng.random() < 0.7), partial_accuracy=1.0, model_requests=(10 if degraded else 5) + rng.choice([0, 1]), page_loads=6, actions=6, revisits=0,
                    elapsed_seconds=20.0, calculated_cost_usd=0.1, attribution=["none"], evidence_coverage=1.0)
        rows.append(base)
    return s, rows


def test_stage1_analysis_never_attributes_to_a_factor_and_reports_signal():
    s, rows = rows_for(1, True)
    res = analysis.analyze(rows, s)
    c = res["contrasts"]["S1"]
    assert c["causal_contrast"] is False and c["tier"] == "observed_directional_signal" and any("must not be attributed" in n for n in c["tier_notes"])
    assert set(res["contrasts"]) == {"S1"} and not res["partial_schedule"]


def test_null_scenario_is_inconclusive_and_never_equivalence():
    s, rows = rows_for(2, False)
    for r in rows:
        r["model_requests"] = 5; r["success"] = True
    res = analysis.analyze(rows, s)
    for cid in ("C1", "C2", "C0"):
        c = res["contrasts"][cid]
        assert c["tier"] == "inconclusive_no_detected_effect" and any("NOT evidence of equivalence" in n for n in c["tier_notes"])
    assert "equivalen" in analysis.markdown(res)


def test_supported_requires_review_consistency_and_complete_schedule():
    s, rows = rows_for(2, True)
    for r in rows:
        if r["variant_code"] in ("V1", "V2"):
            r["success"], r["model_requests"] = False, 14
        elif r["variant_code"] == "V0":
            r["success"], r["model_requests"] = True, 5
    for r in rows:                       # placebo shows no effect
        if r["task_code"] == "T2" and r["variant_code"] == "V1":
            r["success"], r["model_requests"] = True, 5
    no_review = analysis.analyze(rows, s)
    assert no_review["contrasts"]["C1"]["tier"] == "observed_directional_signal" and any("mechanism review" in n for n in no_review["contrasts"]["C1"]["tier_notes"])
    yes = analysis.analyze(rows, s, mechanism_review={"C1": {"supported": True}})
    assert yes["contrasts"]["C1"]["tier"] == "supported_exploratory_effect"
    partial = analysis.analyze(rows[:-4], s, mechanism_review={"C1": {"supported": True}})
    assert partial["partial_schedule"] and partial["contrasts"]["C1"]["tier"] != "supported_exploratory_effect"
    assert "PARTIAL SCHEDULE" in analysis.markdown(partial)
    assert analysis.analyze(rows, s, mechanism_review={"C0": {"supported": True}})["contrasts"]["C0"]["tier"] != "supported_exploratory_effect"      # placebo is never "supported"


def test_failed_and_incomplete_runs_are_in_the_denominator():
    s, rows = rows_for(1, False)
    rows[0]["run_status"], rows[0]["success"] = "infrastructure_error", False
    rows.pop()
    res = analysis.analyze(rows, s)
    assert res["partial_schedule"] and res["runs_analysed"] == 7 and sum(c["infrastructure_errors"] for c in res["cells"].values()) == 1


def test_mock_banner_in_analysis_and_report():
    s, rows = rows_for(1, False)
    for r in rows:
        r["mode"] = "mock"
    res = analysis.analyze(rows, s)
    assert res["banner"].startswith("MOCK RESULTS") and analysis.markdown(res).startswith("> **MOCK RESULTS")


def test_per_run_attribution_never_blames_the_website_and_hypotheses_are_not_attributions():
    inst = registry.get_instance("t1-anc-headphones-under-250-all")
    rec = fake(inst.spec.task_id, make_variant("detail", "fragmented"), passed=False)
    rec["diagnostics"]["findings"] += [{"category": "website", "confidence": "observed", "title": "Stock status was only available on product pages"},
                                       {"category": "website", "confidence": "hypothesis", "title": "Possible contribution of fragmented specifications"},
                                       {"category": "agent_reasoning", "confidence": "inferred", "title": "x"}]
    row = metrics.extract(rec, [], inst)
    assert row["attribution"] == ["agent_reasoning"] and len(row["website_observations"]) == 2


def test_single_run_arms_get_no_interval():
    s, rows = rows_for(1, True)
    assert analysis.analyze(rows, s)["contrasts"]["S1"]["metrics"]["success"]["ci95_bootstrap"] is None
