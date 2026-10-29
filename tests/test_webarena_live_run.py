"""Stub-provider end-to-end tests of the guarded WebArena live path (real Chromium, loopback stub storefront, official evaluator). NO provider is contacted; the
'model' is a scripted httpx handler, so results are labelled mode='stub'. Needs the optional `webarena-verified` package (skipped otherwise)."""
import asyncio
import json

import httpx
import pytest

pytest.importorskip("webarena_verified")
from tests.test_webarena_spike import SLUG, factory, go_direct, stub_app            # noqa: E402

from agent_readiness.scanner.live import Halt, Ledger                         # noqa: E402
from agent_readiness.scanner.serve import serve_app                           # noqa: E402
from agent_readiness.webarena import live                                     # noqa: E402
from agent_readiness.webarena.adapter import WebArenaShopping                 # noqa: E402

pytestmark = pytest.mark.browser


def go(tmp_path, handler_script=None, ledger=None, **kw):
    ledger = ledger or Ledger(tmp_path / "ledger", ceiling=live.LEDGER_CEILING_USD)

    async def main():
        async with serve_app(stub_app()) as base:
            shop = WebArenaShopping(base)
            handler = kw.pop("handler", None) or factory(handler_script or go_direct)(shop.task(286), base)
            return await live.run_live(shop, ledger, tmp_path / "out", stub_handler=handler, **kw)
    return ledger, asyncio.run(main())


def test_stub_run_passes_official_evaluation_and_accounts_every_request(tmp_path):
    ledger, r = go(tmp_path)
    assert r["mode"] == "stub" and r["official_verdict"]["passed"] and r["model_requests"] == 2 and r["har_entries"] > 0
    assert r["spend"]["requests_reserved"] == 2 and r["spend"]["unsettled_reservations"] == [] and r["gate_violation"] is None and not r["guard_halt"]
    assert 0 < r["spend"]["run_committed_usd"] < 0.10 and ledger.committed() == r["spend"]["ledger_total_committed_usd"]
    assert r["leak_scan"]["pre_run_hits"] == [] and r["leak_scan"]["system_message_hits"] == []
    assert r["limits"]["max_steps"] == 16 and r["limits"]["run_cap_usd"] == 0.50 and r["limits"]["request_timeout_seconds"] == 30


def test_second_run_with_the_same_ledger_is_refused(tmp_path):
    ledger, _ = go(tmp_path)
    with pytest.raises(Halt, match="already attempted"):
        go(tmp_path / "again", ledger=ledger)


def test_unhealthy_environment_halts_before_any_spend(tmp_path):
    ledger = Ledger(tmp_path / "ledger")
    with pytest.raises(Halt, match="environment health check failed"):
        go(tmp_path, ledger=ledger, health={"ok": False, "storefront_status": 503})
    assert ledger.entries() == []


def test_static_leak_halts_before_any_spend(tmp_path, monkeypatch):
    ledger = Ledger(tmp_path / "ledger")
    real = live.static_inputs
    monkeypatch.setattr(live, "static_inputs", lambda *a, **k: {**real(*a, **k), "planted": SLUG})
    with pytest.raises(Halt, match="leak scan"):
        go(tmp_path, ledger=ledger)
    assert ledger.entries() == []


def test_provider_failure_still_captures_har_runs_official_evaluation_and_keeps_full_reservations(tmp_path):
    ledger, r = go(tmp_path, handler=lambda req: httpx.Response(500, json={"error": "stub outage"}))
    assert r["answer"] is None and r["official_verdict"]["passed"] is False and "no answer" in r["official_verdict"]["error"]
    sp = r["spend"]
    assert r["run_status"] == "infrastructure_error" and r["guard_halt"] and sp["requests_reserved"] == 2 and len(sp["unsettled_reservations"]) == 2
    assert 0.06 < sp["run_committed_usd"] <= 0.08                                      # two failed requests, each still counted at its full ~US$0.035 upper bound
    assert r["spend"]["ledger_total_committed_usd"] <= live.LEDGER_CEILING_USD


def test_run_requires_a_successful_probe_when_live(tmp_path, monkeypatch):
    monkeypatch.setenv("META_MODEL_API_KEY", "stub-key")
    monkeypatch.setattr("agent_readiness.env.load_repo_env", lambda *a, **k: False)

    async def main():
        async with serve_app(stub_app()) as base:
            return await live.run_live(WebArenaShopping(base), Ledger(tmp_path / "l"), tmp_path / "o", allow_model_calls=True)
    with pytest.raises(Halt, match="probe has not succeeded"):
        asyncio.run(main())
