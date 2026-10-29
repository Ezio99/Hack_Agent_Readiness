"""The scripted end-to-end path: pipeline + evidence rules + report + CLI work together (no model, no network)."""
import json
import subprocess
import sys
from pathlib import Path

from agent_readiness.investigate.demo import run_demo
from agent_readiness.investigate.run import InvestigationRun

ROOT = Path(__file__).resolve().parents[1]


def test_demo_runs_end_to_end_and_report_keeps_the_kinds_apart(tmp_path):
    run, rep = run_demo(tmp_path)
    assert rep["schema"] == "investigation-report-v1" and rep["mode"] == "scripted" and rep["outcome"] == "findings"
    assert any("SCRIPTED" in n for n in rep["notices"])
    assert len(rep["findings"]) == 1 and rep["findings"][0]["attribution"] == "website"
    assert len(rep["hypotheses"]["verifiable"]) == 1 and len(rep["hypotheses"]["novel"]) == 1
    assert "UNVERIFIED" in rep["hypotheses"]["novel"][0]["label"] and rep["hypotheses"]["novel"][0]["status"] == "unverified"
    labels = {p["basis"]: p["label"] for p in rep["proposals"]}
    assert "EXPERIMENTAL" in labels["unverified_hypothesis"] and "EXPERIMENTAL" not in labels["verified_finding"]
    assert all(p["validation"] == "unvalidated" and p["status"] == "proposed" for p in rep["proposals"])
    assert rep["effects"]["measured"] == []
    assert all(run.status(s) == "done" for s in ("inspect", "investigate", "recommend", "report"))


def test_demo_state_is_reloadable_from_disk(tmp_path):
    run, rep = run_demo(tmp_path)
    again = InvestigationRun(run.dir)
    assert again.evidence.outcome() == "findings" and len(again.evidence.proposals) == 2
    assert again.artifact("report")["run_id"] == rep["run_id"]


def test_cli_demo_and_status(tmp_path):
    exe = [sys.executable, "-m", "agent_readiness.cli"]
    r = subprocess.run(exe + ["investigate", "demo", "--root", str(tmp_path)], cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0 and "scripted demo finished" in r.stdout and "outcome=findings" in r.stdout
    s = subprocess.run(exe + ["investigate", "status", str(tmp_path / "scripted-demo")], cwd=ROOT, capture_output=True, text=True)
    assert s.returncode == 0 and "report" in s.stdout and "done" in s.stdout


def test_cli_approve_records_an_approval(tmp_path):
    run, _ = run_demo(tmp_path)
    exe = [sys.executable, "-m", "agent_readiness.cli"]
    r = subprocess.run(exe + ["investigate", "approve", str(run.dir), "--stage", "report", "--sha256", "a" * 64, "--note", "test approval"], cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0 and json.loads(r.stdout)["stage"] == "report"
    assert InvestigationRun(run.dir).is_approved("report", "a" * 64)
