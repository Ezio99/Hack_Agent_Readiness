"""Mock end-to-end of the EXACT eight-run Stage 1 schedule through the real browser agent, guard and evaluator with scripted model behaviour. No model, no network.
Everything is labelled MOCK; nothing here says anything about Muse Spark or the storefront variants."""
import json

import pytest

from agent_readiness.experiments import analysis, driver, manifest as manifest_mod, schedule as S
from agent_readiness.experiments.ledger import ExperimentLedger

pytestmark = pytest.mark.browser


def test_stage1_exact_schedule_end_to_end_mock(tmp_path):
    sched = S.build_schedule(1)
    frozen = manifest_mod.build_manifest()
    by = {(e["task_code"], e["variant_code"]): e["run_id"] for e in sched["entries"]}
    plan = {by[("T2", "V3")]: "wrong", by[("T3", "V3")]: "lazy", by[("T1", "V3")]: "loop"}       # scripted degradations in the stressed cells (demonstration only)
    ledger = ExperimentLedger(tmp_path / "led")
    rep = driver.run_stage(1, sched, frozen, ledger, tmp_path / "out", mode="mock", mock_plan=plan, current_manifest=lambda: frozen)
    assert not rep["halted"] and not rep["partial"] and len(rep["completed"]) == 8 and rep["banner"].startswith("MOCK RESULTS")
    rows = analysis.load_rows(tmp_path / "out" / "stage1" / "results.jsonl")
    assert [r["run_id"] for r in rows] == [e["run_id"] for e in sched["entries"]] and {r["mode"] for r in rows} == {"mock"}
    row = {(r["task_code"], r["variant_code"]): r for r in rows}
    assert all(row[(t, "V0")]["success"] for t in ("T1", "T2", "T3", "T4")) and row[("T4", "V3")]["success"]
    assert not row[("T2", "V3")]["success"] and row[("T2", "V3")]["partial_accuracy"] < 1          # wrong answer: partial accuracy reported separately
    assert row[("T3", "V3")]["passed"] and not row[("T3", "V3")]["evidence_backed"] and row[("T3", "V3")]["evidence_coverage"] < 1      # correct but nothing shown
    assert "agent_tool_interface" in row[("T1", "V3")]["attribution"]                                  # loop persona -> tool interface, not website
    assert row[("T4", "V0")]["visit_kinds"].get("required", 0) >= 1 and all(r["model_requests"] >= 2 for r in rows)
    assert ledger.committed() == pytest.approx(sum(r["calculated_cost_usd"] for r in rows)) and not ledger.unsettled() and ledger.committed() < 1.5
    res = analysis.analyze(rows, sched)
    md = analysis.markdown(res)
    assert res["banner"] and md.startswith("> **MOCK RESULTS") and "never" not in res["contrasts"]["S1"]["tier"]
    assert res["contrasts"]["S1"]["tier"] == "observed_directional_signal" and not res["partial_schedule"]
    assert any("must not be attributed" in n for n in res["contrasts"]["S1"]["tier_notes"])
    (tmp_path / "analysis.md").write_text(md)
