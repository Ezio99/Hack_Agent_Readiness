"""Guards of the approved live validation, tested with stubs/mock transports ONLY (no provider contact, no credentials needed)."""
import json

import httpx
import pytest

from agent_readiness.agent import ModelConfig
from agent_readiness.scanner import live


def rec(status="completed", passed=True, cost=0.05):
    return {"outcome": {"run_status": status, "stop_reason": "x"}, "evaluation": {"passed": passed, "evidence_backed": passed}, "metrics": {"model_requests": 3, "elapsed_seconds": 1.0, "calculated_cost_usd": cost}}


@pytest.fixture(autouse=True)
def key(monkeypatch):
    monkeypatch.setenv("META_MODEL_API_KEY", "test-key-not-real")
    monkeypatch.setattr("agent_readiness.env.load_repo_env", lambda *a, **k: False)


def runner_with(results, calls):
    async def r(task_id, variant, **kw):
        calls.append((task_id, kw["provider"], variant.variant_id))
        v = results[len(calls) - 1]
        if isinstance(v, BaseException):
            raise v
        return v
    return r


def test_refuses_without_explicit_flag_and_without_probe(tmp_path):
    L = live.Ledger(tmp_path)
    with pytest.raises(live.Halt):
        live.run_fixtures(ModelConfig(), L, tmp_path, allow_model_calls=False)
    with pytest.raises(live.Halt, match="probe has not succeeded"):
        live.run_fixtures(ModelConfig(), L, tmp_path, allow_model_calls=True, runner=runner_with([], []))


def test_ledger_ceiling_includes_probe_and_unsettled_reservations(tmp_path):
    L = live.Ledger(tmp_path)
    L.reserve("probe", live.PROBE_CAP_USD)
    L.settle("probe", 0.01)
    for t in live.FIXTURES[:3]:
        L.reserve(t, live.RUN_RESERVE_USD)
    assert L.committed() == pytest.approx(0.01 + 3 * 0.48)
    L.reserve(live.FIXTURES[3], live.RUN_RESERVE_USD)       # 0.01 + 1.92 = 1.93 <= 2.00
    with pytest.raises(live.Halt, match="ceiling"):
        L.reserve("extra", 0.2)
    with pytest.raises(live.Halt, match="already attempted"):
        L.reserve(live.FIXTURES[0], 0.1)                      # no repeat of any attempt


def test_full_sequence_is_sequential_default_variant_no_retry_and_in_order(tmp_path):
    L = live.Ledger(tmp_path)
    L.mark_probe_ok()
    calls = []
    out = live.run_fixtures(ModelConfig(), L, tmp_path, allow_model_calls=True, runner=runner_with([rec(), rec(passed=False), rec(status="request_limit", passed=False), rec()], calls))
    assert [c[0] for c in calls] == list(live.FIXTURES) and {c[1] for c in calls} == {"live"}
    assert {c[2] for c in calls} == {"electronics-v1/availability-listing+specs-structured"}
    assert len(out) == 4 and L.committed() == pytest.approx(0.2)
    again = live.run_fixtures(ModelConfig(), L, tmp_path, allow_model_calls=True, runner=runner_with([], []))
    assert all("never repeated" in r["skipped"] for r in again)    # a rerun never repeats a recorded attempt


@pytest.mark.parametrize("status", ["diagnostic_fidelity_violation", "estimated_cost_limit", "infrastructure_error"])
def test_guard_class_failure_stops_the_sequence(tmp_path, status):
    L = live.Ledger(tmp_path)
    L.mark_probe_ok()
    calls = []
    out = live.run_fixtures(ModelConfig(), L, tmp_path, allow_model_calls=True, runner=runner_with([rec(status=status, passed=False)], calls))
    assert len(calls) == 1 and out[0]["halted_after"]


def test_interruption_keeps_full_reservation_and_stops(tmp_path):
    L = live.Ledger(tmp_path)
    L.mark_probe_ok()
    with pytest.raises(KeyboardInterrupt):
        live.run_fixtures(ModelConfig(), L, tmp_path, allow_model_calls=True, runner=runner_with([KeyboardInterrupt()], []))
    assert L.committed() == pytest.approx(live.RUN_RESERVE_USD) and L.attempted(live.FIXTURES[0])


def test_a_run_costing_more_than_its_reservation_halts(tmp_path):
    L = live.Ledger(tmp_path)
    L.mark_probe_ok()
    calls = []
    live.run_fixtures(ModelConfig(), L, tmp_path, allow_model_calls=True, runner=runner_with([rec(cost=0.6)], calls))
    assert len(calls) == 1


def probe_transport(content, usage, status=200):
    def h(request):
        body = json.loads(request.content)
        assert body["response_format"]["type"] == "json_schema" and body["max_completion_tokens"] == 1024 and request.headers["authorization"] == "Bearer test-key-not-real"
        return httpx.Response(status, json={"model": "muse-spark-1.3", "choices": [{"finish_reason": "stop", "message": {"content": content}}], "usage": usage}, headers={"content-type": "application/json", "x-request-id": "r1"})
    return httpx.MockTransport(h)


GOOD = json.dumps({"evaluation_previous_goal": "n", "memory": "m", "next_goal": "g", "thinking": "t", "current_plan_item": 0, "plan_update": None,
                   "action": [{"done": {"text": "ok", "success": True, "data": {"products": [{"sku": "PROBE-0", "price_cents": 100}]}}}]})


def test_probe_success_records_cost_and_unlocks_runs(tmp_path):
    L = live.Ledger(tmp_path)
    r = live.run_probe(ModelConfig(), L, tmp_path / "probe", allow_model_calls=True, transport=probe_transport(GOOD, {"prompt_tokens": 5000, "completion_tokens": 200, "total_tokens": 5200}))
    assert r["success"], r
    assert r["calculated_cost_usd"] == pytest.approx(5000 * 1.25e-6 + 200 * 4.25e-6) and r["calculated_cost_usd"] <= live.PROBE_CAP_USD
    assert L.probe_succeeded() and L.committed() == pytest.approx(r["calculated_cost_usd"])
    assert "test-key-not-real" not in (tmp_path / "probe").rglob("probe.json").__next__().read_text()


def test_probe_incompatibility_is_reported_and_blocks_runs(tmp_path):
    L = live.Ledger(tmp_path)
    r = live.run_probe(ModelConfig(), L, tmp_path / "probe", allow_model_calls=True, transport=probe_transport("not json", {"prompt_tokens": 100, "completion_tokens": 5}))
    assert not r["success"] and not L.probe_succeeded()
    r2 = live.Ledger(tmp_path / "b")
    bad = live.run_probe(ModelConfig(), r2, tmp_path / "b" / "probe", allow_model_calls=True, transport=probe_transport("{}", None, status=400))
    assert bad["failure_class"] == "schema_or_request_rejected" and r2.committed() == live.PROBE_CAP_USD    # unknown spend keeps the reservation


def test_probe_cannot_run_twice(tmp_path):
    L = live.Ledger(tmp_path)
    live.run_probe(ModelConfig(), L, tmp_path / "p", allow_model_calls=True, transport=probe_transport(GOOD, {"prompt_tokens": 1, "completion_tokens": 1}))
    with pytest.raises(live.Halt, match="already attempted"):
        live.run_probe(ModelConfig(), L, tmp_path / "p2", allow_model_calls=True, transport=probe_transport(GOOD, {}))


def test_missing_key_halts(tmp_path, monkeypatch):
    monkeypatch.delenv("META_MODEL_API_KEY")
    with pytest.raises(live.Halt, match="not set"):
        live.run_probe(ModelConfig(), live.Ledger(tmp_path), tmp_path / "p", allow_model_calls=True)
