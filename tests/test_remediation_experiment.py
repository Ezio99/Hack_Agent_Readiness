"""Task 015 pilot/experiment driver: frozen manifest, approvals, durable AUD-aware stage ledger, void-vs-result classification, no retry/replacement, effect record that
references the product-generated ids without rewriting the audit. Stub runners and the mock provider only: no model call, no key, no spend."""
import asyncio
import copy
import json
import sys

import pytest

from agent_readiness import budget
from agent_readiness.remediation import experiment as ex
from agent_readiness.remediation.engine import attach_measured_effects, report_sha256
from agent_readiness.remediation.targets import DEFAULT_INITIAL
from agent_readiness.scanner.live import Halt, Ledger

REPORT = None


def baseline_report():
    global REPORT
    if REPORT is None:
        from agent_readiness.remediation import cli_impl
        REPORT = cli_impl.audit_demo_target(DEFAULT_INITIAL)
    return copy.deepcopy(REPORT)


def plan(stage="pilot", seed=7, **kw):
    rep = baseline_report()
    rid = next(r["id"] for r in rep["recommendations"] if r["change_id"] == "availability-on-listing-cards")
    return rep, ex.build_manifest(stage, rep, rid, DEFAULT_INITIAL, seed, **kw)


def fake_record(entry, status="completed", requests=6, visits=5, passed=True, rejected=0, extra=None, cost=0.09):
    path = [{"step": i + 1, "path": f"/p/item-{i}", "query": "", "actions": [], "executed": []} for i in range(visits)]
    return {"scan": {"mode": "mock", "model": "m", "profile": "p"}, "task": {"task_id": entry}, "outcome": {"run_status": status, "stop_reason": "x", "errors": [], "answer": {}},
            "evaluation": {"passed": passed, "evidence_backed": passed, "reasons": [] if passed else ["x"], "details": {"extra": extra or []}},
            "metrics": {"model_requests": requests, "page_views": visits, "elapsed_seconds": 5.0, "calculated_cost_usd": cost}, "journey": path,
            "protocol": {"recovery_rejected": rejected}, "finished_at": "t"}


def scripted_runner(table, reserve=True):
    """Returns a runner; table maps run_id -> kwargs for fake_record or an Exception instance to raise."""
    calls = []

    async def runner(task_id, variant, *, provider, mock_behavior, output, model_config=None, api_key=None, profile_id=None, request_gate=None):
        run_id = request_gate.run_id
        calls.append(run_id)
        spec = table.get(run_id, {})
        if isinstance(spec, BaseException):
            raise spec
        if reserve and request_gate is not None:
            request_gate.ledger.reserve(f"{run_id}:req01", 0.01)
            request_gate.ledger.settle(f"{run_id}:req01", 0.004)
        return fake_record(task_id, **spec)
    runner.calls = calls
    return runner


def go(m, root, runner, **kw):
    return asyncio.run(ex.run_stage(m, root, mode=kw.pop("mode", "mock"), runner=runner, **kw))


def test_manifest_freezes_everything_before_execution_and_references_the_product_ids():
    rep, m = plan()
    assert m["audit"]["audit_id"] == rep["audit_id"] and m["audit"]["recommendation_id"] == "rec-show-availability-on-listing-cards"
    assert m["audit"]["finding_fingerprints"] == ["attribute_detail_only:availability", "filter_absent:availability"] and m["audit"]["report_sha256"] == report_sha256(rep)
    assert m["audit"]["validation_as_issued"] == "unvalidated" and m["audit"]["state_check"]["reproduced"]
    f = m["frozen"]
    assert f["agent_profile"] == "suite-v2-compat1" and f["model"] == "muse-spark-1.3" and set(f["tasks"]) == {"T1", "T4"} and len(f["agent_profile_sha256"]) == 64
    assert f["states"]["unmodified"]["variant_id"].endswith("availability-detail+specs-structured+sku-listing") and f["states"]["modified"]["variant_id"].endswith("availability-listing+specs-structured+sku-listing")
    assert m["limits"]["per_request_usd"] == 0.05 and m["limits"]["per_run_usd"] == 0.50 and m["limits"]["stage_cap_aud"] == 1.50 and m["limits"]["stage_cap_usd"] == 1.0 and m["limits"]["usd_to_aud"] == 1.5
    assert m["stopping_rules"]["retries"] == "never" and m["stopping_rules"]["replacements"] == "never" and m["pilot_gate"] and m["seed"] == 7
    assert [(e["task_code"]) for e in m["schedule"]] == ["T1", "T1"] and {e["state"] for e in m["schedule"]} == {"unmodified", "modified"}
    assert m["manifest_sha256"] == ex.manifest_hash(m) and set(m["code"]["files_sha256"]) == set(ex.FROZEN_FILES)
    assert m["budget_check"]["remaining_before_aud"] == pytest.approx(44.115, abs=1e-2) and m["budget_check"]["remaining_after_stage_cap_aud"] == pytest.approx(42.615, abs=1e-2)


def test_main_schedule_is_seeded_balanced_and_deterministic():
    _, a = plan("main", 11)
    _, b = plan("main", 11)
    _, c = plan("main", 12)
    assert a["schedule"] == b["schedule"] and a["schedule_sha256"] != c["schedule_sha256"] and len(a["schedule"]) == 18
    assert sum(e["task_code"] == "T1" for e in a["schedule"]) == 12 and sum(e["task_code"] == "T4" for e in a["schedule"]) == 6
    for blk in range(1, 7):
        e = [x for x in a["schedule"] if x["block"] == blk and x["task_code"] == "T1"]
        assert sorted(x["state"] for x in e) == ["modified", "unmodified"]


def test_manifest_is_write_once_and_tamper_evident(tmp_path):
    _, m = plan()
    p = tmp_path / "m.json"
    ex.save_manifest(p, m)
    with pytest.raises(Halt):
        ex.save_manifest(p, m)
    assert ex.load_manifest(p)["manifest_sha256"] == m["manifest_sha256"]
    t = json.loads(p.read_text())
    t["limits"]["stage_cap_aud"] = 99
    p.write_text(json.dumps(t))
    with pytest.raises(Halt, match="edited after freezing"):
        ex.load_manifest(p)


def test_planning_refuses_a_different_site_than_the_one_audited():
    rep = baseline_report()
    rid = next(r["id"] for r in rep["recommendations"] if r["change_id"] == "availability-on-listing-cards")
    with pytest.raises(Halt, match="does not reproduce"):
        ex.build_manifest("pilot", rep, rid, {**DEFAULT_INITIAL, "availability": "listing"}, 1)       # the supplied state no longer shows the audited finding
    with pytest.raises(Halt):
        ex.build_manifest("pilot", rep, "rec-made-up", DEFAULT_INITIAL, 1)


def test_planning_refuses_a_stage_that_would_break_the_programme_ceiling(monkeypatch):
    rep = baseline_report()
    rid = next(r["id"] for r in rep["recommendations"] if r["change_id"] == "availability-on-listing-cards")
    led = budget.load()
    led["entries"].append({"id": "spent", "usd": 30.0, "source": "test"})                             # leaves < A$1.50 of the A$50
    monkeypatch.setattr(budget, "load", lambda *a, **k: led)
    with pytest.raises(ValueError, match="exceeds the remaining programme budget"):
        ex.build_manifest("pilot", rep, rid, DEFAULT_INITIAL, 1)


def test_live_needs_the_exact_hash_the_flag_the_pilot_for_main_and_unchanged_code(tmp_path, monkeypatch):
    _, m = plan()
    sl = ex.StageLedger(tmp_path, "pilot", m)
    with pytest.raises(Halt, match="approve-manifest-sha256"):
        ex.preflight(m, None, "live", True, sl)
    with pytest.raises(Halt, match="approve-manifest-sha256"):
        ex.preflight(m, "0" * 64, "live", True, sl)
    with pytest.raises(Halt, match="allow-model-calls"):
        ex.preflight(m, m["manifest_sha256"], "live", False, sl)
    _, mm = plan("main", 3)
    with pytest.raises(Halt, match="completed pilot"):
        ex.preflight(mm, mm["manifest_sha256"], "live", True, ex.StageLedger(tmp_path, "main", mm))     # a pilot approval is not a main approval
    real = ex.code_hashes()
    monkeypatch.setattr(ex, "code_hashes", lambda: {**real, ex.FROZEN_FILES[0]: "0" * 64})
    with pytest.raises(Halt, match="code changed since the manifest was frozen"):
        ex.preflight(m, m["manifest_sha256"], "mock", False, sl)


def test_every_stage_ledger_counts_toward_the_programme_ceiling(tmp_path):
    _, pm = plan()
    _, mm = plan("main", 5)
    pilot, main = ex.StageLedger(tmp_path, "pilot", pm), ex.StageLedger(tmp_path, "main", mm)
    pilot.ledger.reserve("pilot-x", 0.40)
    assert main.others_committed_usd() == pytest.approx(0.40) and pilot.others_committed_usd() == 0.0
    s = main.summary()
    assert s["programme_spent_aud"] == pytest.approx(5.885 + 0.60, abs=1e-2) and s["stage_cap_aud"] == 7.5
    pilot.ledger.reserve("pilot-y", 0.30)
    assert main.summary()["programme_spent_aud"] == pytest.approx(5.885 + 1.05, abs=1e-2)


def test_budget_and_provider_stops_are_void_never_website_results(tmp_path):
    _, m = plan("main", 2)
    sched = [e["run_id"] for e in m["schedule"]]
    table = {sched[0]: {"status": "estimated_cost_limit", "requests": 0, "visits": 0, "passed": False}}
    r = go(m, tmp_path, scripted_runner(table))
    rows = ex.read_rows(tmp_path / "main" / "rows.jsonl")
    assert r["halt"]["reason"] == "budget_stop" and len(rows) == 1 and rows[0]["void"] and rows[0]["outcome_class"] == "budget_stop"
    assert "not attributable to the website" in rows[0]["attribution"] and rows[0]["recommendation_id"] == m["audit"]["recommendation_id"] and rows[0]["finding_fingerprints"]
    an = ex.analyze(rows, m)
    assert an["T1"]["valid_pairs"] == 0 and an["void_rows"][0]["class"] == "budget_stop"


def test_two_provider_failures_halt_and_nothing_is_replaced_or_retried(tmp_path):
    _, m = plan("main", 4)
    s = [e["run_id"] for e in m["schedule"]]
    runner = scripted_runner({s[0]: {"status": "infrastructure_error", "passed": False}, s[1]: {"status": "infrastructure_error", "passed": False}})
    r = go(m, tmp_path, runner)
    assert r["halt"]["reason"] == "max_void_runs" and runner.calls == s[:2] and r["runs_attempted"] == 2 and not r["complete"]
    again = scripted_runner({})
    go(m, tmp_path, again)                                                    # resuming: the two attempted runs are never repeated; the rest may run only because no rule is violated now
    assert not set(again.calls) & set(s[:2])
    rows = ex.read_rows(tmp_path / "main" / "rows.jsonl")
    assert [r["run_id"] for r in rows if r["outcome_class"] == "provider_failure"] == s[:2]       # failures stay recorded as such; no replacement entries exist
    assert len({r["run_id"] for r in rows}) == len(rows)


def test_interruption_is_recorded_void_keeps_reservations_and_is_not_retried(tmp_path):
    _, m = plan("main", 6)
    s = [e["run_id"] for e in m["schedule"]]
    with pytest.raises(KeyboardInterrupt):
        go(m, tmp_path, scripted_runner({s[0]: {}, s[1]: KeyboardInterrupt()}))
    rows = ex.read_rows(tmp_path / "main" / "rows.jsonl")
    assert rows[-1]["run_id"] == s[1] and rows[-1]["void"] and "interrupted" in rows[-1]["attribution"]
    runner = scripted_runner({})
    go(m, tmp_path, runner)
    assert s[0] not in runner.calls and s[1] not in runner.calls                  # neither the finished nor the interrupted run is repeated
    assert Ledger(tmp_path / "main" / "ledger").attempted(s[1])


def test_parser_rejections_and_guard_violations_halt(tmp_path):
    _, m = plan("main", 8)
    s = [e["run_id"] for e in m["schedule"]]
    first_block = [e["run_id"] for e in m["schedule"] if e["block"] == 1]
    r = go(m, tmp_path / "a", scripted_runner({first_block[0]: {"rejected": 1}, first_block[1]: {"rejected": 1}}))
    assert r["halt"]["reason"] == "parser_rejections"
    r2 = go(m, tmp_path / "b", scripted_runner({s[0]: {"status": "diagnostic_fidelity_violation", "passed": False}}))
    assert r2["halt"]["reason"] == "guard_violation"


def test_stage_cap_in_aud_stops_a_real_mock_run_before_any_request_leaves(tmp_path, monkeypatch):
    monkeypatch.setitem(ex.STAGES["pilot"], "stage_cap_aud", 0.03)              # US$0.02: below one request's upper bound (~US$0.035)
    _, m = plan("pilot", 9)
    assert m["limits"]["stage_cap_usd"] == pytest.approx(0.02)
    r = go(m, tmp_path, ex.execute_scan)
    rows = ex.read_rows(tmp_path / "pilot" / "rows.jsonl")
    assert r["halt"]["reason"] in ("budget_stop", "stage_cap") and rows[0]["void"] and rows[0]["outcome_class"] == "budget_stop"
    assert Ledger(tmp_path / "pilot" / "ledger").committed() == 0.0              # nothing was reserved or spent past the cap


def test_pilot_gate_rules():
    row = lambda state, visits=5, extra=None, void=False: {"task_code": "T1", "state": state, "product_page_visits": visits, "extra_items": extra or [], "void": void, "outcome_class": "completed"}
    assert ex.pilot_gate([row("unmodified"), row("modified")])["decision"] == "continue"
    assert ex.pilot_gate([row("unmodified", 2, ["HP-1005"]), row("modified")])["decision"] == "continue"
    stop = ex.pilot_gate([row("unmodified", 2), row("modified", 2)])
    assert stop["decision"] == "stop" and "ceiling effect" in stop["reason"]
    void = ex.pilot_gate([row("unmodified", void=True), row("modified")])
    assert void["decision"] == "stop" and "NOT a website result" in void["reason"]


def make_rows(m, deltas, cls_override=None):
    rows = []
    for e in m["schedule"]:
        if e["task_code"] == "T1":
            base = 10
            req = base if e["state"] == "unmodified" else base + deltas[e["block"] - 1]
            rows.append({**e, "void": False, "model_requests": req, "product_page_visits": req - 3, "passed": True, "calculated_cost_usd": req * 0.01, "outcome_class": "completed", "mock": False})
        else:
            rows.append({**e, "void": False, "model_requests": 6, "product_page_visits": 3, "passed": True, "calculated_cost_usd": 0.06, "outcome_class": "completed", "mock": False})
    return rows


def test_analysis_verdicts_follow_the_pre_registered_rule():
    _, m = plan("main", 1)
    assert ex.analyze(make_rows(m, [-4, -5, -4, -3, -6, -4]), m)["verdict"] == "supports"
    assert ex.analyze(make_rows(m, [0, 1, 0, -1, 0, 0]), m)["verdict"] == "not_supported"
    assert ex.analyze(make_rows(m, [-2, -1, -3, 0, -2, 1]), m)["verdict"] == "inconclusive"
    few = ex.analyze([r for r in make_rows(m, [-4] * 6) if r["block"] <= 2], m)
    assert few["verdict"] == "inconclusive" and "fewer than 4" in few["verdict_reason"]
    pilot_m = plan()[1]
    assert ex.analyze(make_rows(pilot_m, [-5]), pilot_m)["verdict"] == "inconclusive"                  # a pilot never supports an effect claim


def test_dry_run_pilot_end_to_end_records_references_and_never_attaches_mock_results(tmp_path):
    rep, m = plan("pilot", 21)
    r = go(m, tmp_path, ex.execute_scan)                                                                # the real mock provider through the real scanner and gate
    assert r["complete"] and r["runs_attempted"] == 2 and "MOCK dry run" in r["spend"]["note"]
    rows = ex.read_rows(tmp_path / "pilot" / "rows.jsonl")
    assert {x["audit_id"] for x in rows} == {rep["audit_id"]} and all(x["recommendation_id"] == "rec-show-availability-on-listing-cards" and x["mock"] for x in rows)
    assert all(x["unsettled_reservations"] == [] and x["reserved_usd"] > 0 for x in rows)
    before = report_sha256(rep)
    fin = ex.finalize(m, tmp_path, rep)
    rec = json.loads((tmp_path / "pilot" / "effect-record.json").read_text())
    assert rec["mode"] == "mock" and rec["audit_id"] == rep["audit_id"] and rec["recommendation_id"] == m["audit"]["recommendation_id"] and rec["verdict"] == "inconclusive"
    assert rec["independent_reaudit"]["lifecycle"]["attribute_detail_only:availability"] == "resolved" and "not an effect measurement" in rec["independent_reaudit"]["note"]
    assert fin["attached_view"] is None and report_sha256(rep) == before
    with pytest.raises(ValueError, match="only LIVE"):
        attach_measured_effects(rep, {**rec, "addresses": rec["addresses"]})
    assert json.loads((tmp_path / "pilot" / "pilot-gate.json").read_text())["decision"] in ("continue", "stop")


def test_live_effect_attaches_as_a_derived_view_without_rewriting_the_audit(tmp_path):
    rep, m = plan("main", 5)
    rows = make_rows(m, [-4, -5, -4, -3, -6, -4])
    for r in rows:
        r["mock"] = False
    (tmp_path / "main").mkdir()
    (tmp_path / "main" / "rows.jsonl").write_text("\n".join(json.dumps(r) for r in rows))
    before = copy.deepcopy(rep)
    fin = ex.finalize(m, tmp_path, rep)
    assert rep == before and fin["attached_view"] == "report-with-effects.json" and fin["original_report_sha256_unchanged"]
    view = json.loads((tmp_path / "main" / "report-with-effects.json").read_text())
    rec = next(r for r in view["recommendations"] if r["id"] == m["audit"]["recommendation_id"])
    assert rec["validation"] == "unvalidated" and rec["measured_validation"] == "measured_supports" and view["measured_effects"]["effects"][0]["audit_id"] == rep["audit_id"]


def test_cli_plan_prints_the_exact_paid_command_and_live_run_without_approval_halts(tmp_path, capsys, monkeypatch):
    from agent_readiness import cli
    monkeypatch.setattr(sys, "argv", ["readiness", "remediation-experiment", "plan", "--stage", "pilot", "--root", str(tmp_path), "--seed", "3"])
    cli.main()
    out = capsys.readouterr().out
    m = ex.load_manifest(tmp_path / "pilot" / "manifest.json")
    assert f"--approve-manifest-sha256 {m['manifest_sha256']}" in out and "--allow-model-calls" in out and "--mode live" in out and "do NOT run otherwise" in out
    monkeypatch.setattr(sys, "argv", ["readiness", "remediation-experiment", "run", "--manifest", str(tmp_path / "pilot" / "manifest.json"), "--audit", str(tmp_path / "pilot" / "audit-baseline.json"),
                                       "--root", str(tmp_path), "--mode", "live"])
    with pytest.raises(SystemExit) as e:
        cli.main()
    assert e.value.code == 2 and not (tmp_path / "pilot" / "rows.jsonl").exists()
