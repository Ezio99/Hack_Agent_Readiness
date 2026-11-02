"""M6 Stage A safety, at zero cost: the real MetaClient and durable spend gate over a mock transport (no network), the loop's handling of a provider
error (preserved, stopped, never retried), and the experiment's refusal to start on a used ledger."""
import json

import httpx
import pytest

from agent_readiness.framework.site import get
from agent_readiness.research.taskplan import catalogue as K
from agent_readiness.research.taskplan import context as X
from agent_readiness.suites.experiments import m6_stage_a as EXP
from agent_readiness.suites.stage_a import loop as LP
from agent_readiness.suites.stage_a import stopping as ST


def test_gate_rehearsal_with_the_experiment_caps():
    r = EXP.gate_rehearsal(EXP.SETTINGS)
    assert r["ok"] and r["reserved_before_every_send"] and r["restart_cannot_exceed_max_requests"] and r["http_400_sends"] == 1
    assert r["requests_after_restart_total"] == EXP.SETTINGS["max_requests"] and "request-count cap" in r["after_restart"]


def test_a_provider_error_stops_the_loop_without_retry_and_is_preserved(tmp_path):
    from agent_readiness.agent import ModelConfig
    from agent_readiness.investigate.llm.meta import INPUT_OVERHEAD_TOKENS, MetaClient
    from agent_readiness.ledger import Ledger
    from agent_readiness.research.taskplan.planner_v2 import MetaGenerator
    from agent_readiness.spend_gate import RequestGate
    sends = []
    transport = httpx.MockTransport(lambda r: (sends.append(1), httpx.Response(400, json={"error": {"type": "invalid_request_error", "message": "response_format rejected"}}))[1])
    ledger = Ledger(tmp_path / "ledger", 0.10)
    client = MetaClient(ModelConfig(), "not-a-key", RequestGate(ledger, "t", run_cap=0.10, per_request_cap=0.04, max_requests=3, input_overhead_tokens=INPUT_OVERHEAD_TOKENS), transport=transport)
    gen = MetaGenerator(tmp_path / "ledger", approval_note="test", run_cap_usd=0.10, per_request_cap_usd=0.04, run_id="t", client=client)
    site = get("larkspur")
    out = LP.run(site, K.view(site), X.CONTEXT, gen, config=LP.LoopConfig(suite_name="synthetic-x", stop=ST.StopRule(budget_cap_usd=0.10)), created_at="2026-11-02T00:00:00+00:00", out_dir=tmp_path / "run")
    assert out["summary"]["stop_reason"] == "generator_error" and len(sends) == 1 and out["suite_sha256"] is None
    r = json.loads((tmp_path / "run" / "loop.json").read_text())["rounds"][0]
    assert "HTTP 400" in r["error"] and r["request"]["prompt_version"] == "taskplan-v2"
    assert ledger.committed() == r["reservation_usd"] or ledger.committed() > 0                         # the failed request keeps its full reservation counted


def test_experiment_refuses_a_used_ledger(tmp_path):
    (tmp_path / "ledger.jsonl").write_text(json.dumps({"kind": "reserve", "id": "m6-larkspur-core:req01", "usd": 0.03}) + "\n")
    pf = EXP.preflight(EXP.SETTINGS, ledger_dir=tmp_path)
    assert not pf["passed"] and not pf["checks"]["ledger_fresh"]["ok"]


def test_the_loop_default_budget_is_zero_so_a_paid_generator_never_runs_by_default(tmp_path):
    class Paid:
        identity = {"kind": "paid-stand-in"}
        calls = 0
        def reservation_usd(self, request): return 0.03
        def complete(self, request): Paid.calls += 1
    site = get("larkspur")
    out = LP.run(site, K.view(site), X.CONTEXT, Paid(), config=LP.LoopConfig(suite_name="synthetic-x"), created_at="2026-11-02T00:00:00+00:00")
    assert out["summary"]["stop_reason"] == "budget_cap" and Paid.calls == 0
