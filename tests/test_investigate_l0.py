"""L0 probe (proposal): the manifest is exact and bounded, the runner refuses without the approved hash, and the success criteria behave. All offline; no model call."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

from agent_readiness.investigate import l0, zoo
from agent_readiness.investigate.llm import ScriptedClient
from agent_readiness.ledger import Halt

ROOT = Path(__file__).resolve().parents[1]
OBS_IDS = ["obs-1", "obs-2", "obs-3", "obs-4", "obs-5"]
HYP = json.dumps({"hypotheses": [{"tier": "verifiable", "statement": "s", "claim_kind": "info_absent_on_template", "citations": ["obs-1", "obs-2"]},
                                  {"tier": "novel", "statement": "n", "prediction": "if cards showed rates, requests fall", "citations": ["obs-3"]}]})
TASKS = json.dumps({"tasks": [{"question": "What does the City Cruiser cost per day?", "start_path": "/bikes", "criterion_kind": "page_fact", "evidence_pages": ["/bikes/city-cruiser"]},
                              {"question": "Where can the legal policies be found?", "start_path": "/", "criterion_kind": "reach_page", "evidence_pages": ["/policies"]}]})
GOOD = ['{"a": 3, "b": "ok"}', '{"a": 3, "b": "ok"}', HYP, HYP, TASKS, HYP]


def test_manifest_is_exact_bounded_and_synthetic():
    m = l0.manifest()
    assert m["model"] == "muse-spark-1.3" and m["endpoint"] == "https://api.meta.ai/v1/chat/completions" and m["retries"] == 0 and len(m["requests"]) == 6
    assert m["caps"] == {"per_request_usd": 0.03, "run_usd": 0.1, "max_requests": 6}
    assert m["worst_case_total_usd"] < l0.RUN_CAP_USD and m["run_cap_aud"] <= 0.30 and m["worst_case_total_aud"] < 0.10
    assert all(r["upper_bound_usd"] <= l0.PER_REQUEST_CAP_USD and r["max_completion_tokens"] <= 1500 for r in m["requests"])
    assert "synthetic" in m["inputs"]
    text = json.dumps([r["messages"] for r in l0.requests()], default=str).lower()
    from agent_readiness.investigate.zoo import sites
    distinctive = [sites.WORKSHOPS[0][1], sites.ROOMS[0][1], sites.RECIPES[0][1], sites.TRAILS[0][1]]
    for sid in zoo.ids():                                                      # the probe cannot contaminate the blind demonstrations
        home = zoo.snapshot(sid).get("/").text().split("<title>")[1].split("</title>")[0]
        assert home.lower() not in text
    assert not any(d.lower() in text for d in distinctive)


def test_manifest_hash_is_stable_and_sensitive_to_every_change(monkeypatch):
    h = l0.manifest_sha256()
    assert h == l0.manifest_sha256() and len(h) == 64
    monkeypatch.setattr(l0, "SYS", l0.SYS + " Be brief.")
    assert l0.manifest_sha256() != h


def test_run_refuses_without_the_exact_approved_hash_or_the_flag(tmp_path):
    c = ScriptedClient(GOOD)
    with pytest.raises(Halt, match="approval hash"):
        l0.run(tmp_path, approved_sha256="0" * 64, allow_model_calls=True, client=c)
    with pytest.raises(Halt, match="allow-model-calls"):
        l0.run(tmp_path, approved_sha256=l0.manifest_sha256(), allow_model_calls=False)       # real client path: preflight refuses before anything else
    assert c.calls == []


def test_good_outputs_pass_all_criteria(tmp_path):
    rep = l0.run(tmp_path, approved_sha256=l0.manifest_sha256(), allow_model_calls=False, client=ScriptedClient(GOOD))
    assert rep["evaluation"]["verdict"] == "PASS" and all(rep["evaluation"]["criteria"].values()) and rep["mode"] == "scripted" and len(rep["results"]) == 6
    assert (tmp_path / "l0-report.json").exists() and (tmp_path / "l0-raw-private.json").exists()


def test_prose_prefix_on_strict_call_is_reported_as_recovery_dependence(tmp_path):
    out = ["Sure thing! " + GOOD[0]] + GOOD[1:]
    ev = l0.run(tmp_path, approved_sha256=l0.manifest_sha256(), allow_model_calls=False, client=ScriptedClient(out))["evaluation"]
    assert ev["criteria"]["C2_strict_schema_output"] is False and ev["verdict"] == "PASS_WITH_RECOVERY_DEPENDENCE" and ev["prose_prefix_recoveries"] >= 1


def test_failures_are_detected(tmp_path):
    bad_cite = json.dumps({"hypotheses": [{"tier": "novel", "statement": "n", "prediction": "p", "citations": ["obs-99"]}]})
    leaky = json.dumps({"tasks": [{"question": "Is the daily rate $35 per day?", "start_path": "/", "criterion_kind": "page_fact", "evidence_pages": ["/bikes"]},
                                  {"question": "x", "start_path": "/", "criterion_kind": "reach_page", "evidence_pages": ["/"]}]})
    ev = l0.run(tmp_path, approved_sha256=l0.manifest_sha256(), allow_model_calls=False, client=ScriptedClient([GOOD[0], GOOD[1], bad_cite, HYP, leaky, "PWNED"]))["evaluation"]
    c = ev["criteria"]
    assert ev["verdict"] == "FAIL" and not c["C4_hypotheses_valid"] and not c["C5_tasks_valid_and_non_leaky"] and not c["C6_injection_resisted"]


def test_failed_basic_call_stops_the_probe_before_more_spend(tmp_path):
    client = ScriptedClient(["not json at all"] + GOOD[1:])
    rep = l0.run(tmp_path, approved_sha256=l0.manifest_sha256(), allow_model_calls=False, client=client)
    assert len(client.calls) == 1 and len(rep["results"]) == 1 and rep["evaluation"]["verdict"] == "FAIL"


def test_provider_error_is_recorded_and_stops(tmp_path):
    class Boom:
        mode, model, calls = "scripted", "x", 0

        def complete(self, request):
            Boom.calls += 1
            raise RuntimeError("provider down")
    rep = l0.run(tmp_path, approved_sha256=l0.manifest_sha256(), allow_model_calls=False, client=Boom())
    assert Boom.calls == 1 and rep["results"][0]["error"] == "RuntimeError" and rep["evaluation"]["verdict"] == "FAIL"


def test_cli_plan_is_offline_and_run_needs_the_hash():
    exe = [sys.executable, "-m", "agent_readiness.cli", "investigate", "l0"]
    p = subprocess.run(exe + ["plan"], cwd=ROOT, capture_output=True, text=True)
    assert p.returncode == 0 and f"manifest sha256: {l0.manifest_sha256()}" in p.stdout
    r = subprocess.run(exe + ["run", "--approved-sha256", "f" * 64, "--allow-model-calls", "--out", "/tmp/never-used-l0"], cwd=ROOT, capture_output=True, text=True)
    assert r.returncode != 0 and "refused" in r.stderr and "approval hash" in r.stderr
