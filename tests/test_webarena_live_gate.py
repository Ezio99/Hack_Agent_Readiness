"""Credential-free proof of the WebArena live path's spend safety. Every request here goes through stub transports; no provider is contacted, no key is used."""
import asyncio
import json
from pathlib import Path

import httpx
import pytest

from agent_readiness.capture import ResponseCapture, EstimatedCostLimit, estimate_cost_usd, IMAGE_TOKENS_ESTIMATE
from agent_readiness.recorder import Recorder
from agent_readiness.scanner.live import Halt, Ledger
from agent_readiness.webarena import live
from agent_readiness.webarena.live import RequestGate, upper_bound_usd, leak_scan, scan_requests


def body(user_chars=10_000, images=1, cap=4096, system_chars=22_000):
    content = [{"type": "text", "text": "u" * user_chars}] + [{"type": "image_url", "image_url": {"url": "data:image/png;base64,AAAA", "detail": "high"}}] * images
    b = {"model": "muse-spark-1.3", "messages": [{"role": "system", "content": "s" * system_chars}, {"role": "user", "content": content}]}
    if cap:
        b["max_completion_tokens"] = cap
    return b


def ok_response(prompt=9000, completion=400):
    return httpx.Response(200, json={"id": "x", "model": "m", "choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": "{}"}}],
                                     "usage": {"prompt_tokens": prompt, "completion_tokens": completion}})


class Rig:
    """An httpx client with the real capture hooks + durable gate; `handler` plays the provider and records whether the ledger already held the reservation."""

    def __init__(self, tmp_path, handler, ledger_ceiling=0.60, **gate_kw):
        self.ledger = Ledger(tmp_path / "ledger", ceiling=ledger_ceiling)
        self.gate = RequestGate(self.ledger, "t", **gate_kw)
        self.recorder = Recorder(tmp_path / "trace", ())
        self.recorder.request_gate = self.gate
        self.network_hits = 0
        self.seen_reserved = []

        def wrapped(request):
            self.network_hits += 1
            i = self.network_hits
            self.seen_reserved.append(any(e["kind"] == "reserve" and e["id"].startswith("t:req") for e in self.ledger.entries()))
            return handler(request)
        self.client = httpx.AsyncClient(transport=httpx.MockTransport(wrapped))
        self.capture = ResponseCapture(self.recorder, None)
        self.capture.attach(self.client)

    async def send(self, b=None):
        return await self.client.post("https://api.meta.ai/v1/chat/completions", json=b or body())


def run(coro):
    return asyncio.run(coro)


def test_reservation_is_durable_and_precedes_the_network(tmp_path):
    r = Rig(tmp_path, lambda req: ok_response())
    run(r.send())
    assert r.seen_reserved == [True]
    entries = r.ledger.entries()
    ub, _ = upper_bound_usd(body())
    reserve = next(e for e in entries if e["kind"] == "reserve" and e["id"] == "t:req01")
    assert reserve["usd"] == pytest.approx(ub) and reserve["usd"] > 0.02            # the full-completion upper bound, not an average
    settle = next(e for e in entries if e["kind"] == "settle")
    assert settle["usd"] < reserve["usd"]                                           # settled to the (lower) calculated actual cost


def test_upper_bound_includes_screenshot_headroom_and_full_completion():
    plain = estimate_cost_usd(body(images=0))
    one, d1 = upper_bound_usd(body(images=1))
    two, d2 = upper_bound_usd(body(images=2))
    no_img, d0 = upper_bound_usd(body(images=0))
    assert d0["image_headroom_tokens"] == 0 and d1["image_headroom_tokens"] > 2_000 and d2["image_headroom_tokens"] == 2 * d1["image_headroom_tokens"]
    assert one > estimate_cost_usd(body(images=1))["usd"] > plain["usd"]            # headroom is on top of the guard's own image estimate
    assert one - no_img > (live.IMAGE_UPPER_BOUND_TOKENS * 1.25 / 1e6) * 0.99      # a screenshot is bounded at the generous 4,000-token allowance
    assert d1["output_tokens_cap"] == 4096 and one > 4096 * 4.25 / 1e6              # full completion allowance always included


def test_timeout_keeps_the_full_reservation_even_across_restart(tmp_path):
    def boom(req):
        raise httpx.ReadTimeout("simulated 30 s timeout")
    r = Rig(tmp_path, boom)
    with pytest.raises(httpx.ReadTimeout):
        run(r.send())
    ub, _ = upper_bound_usd(body())
    assert r.gate.run_committed() == pytest.approx(ub) and r.gate.unsettled() == ["t:req01"]
    again = Ledger(tmp_path / "ledger", ceiling=0.60)                              # a new process reading the same file
    assert again.committed() == pytest.approx(ub)


@pytest.mark.parametrize("make", [lambda: httpx.Response(500, json={"error": "x"}), lambda: httpx.Response(400, json={"error": "schema"}),
                                  lambda: httpx.Response(200, json={"choices": [{"message": {"content": "{}"}, "finish_reason": "stop"}]})])
def test_error_or_usage_less_responses_keep_the_full_reservation(tmp_path, make):
    r = Rig(tmp_path, lambda req: make())
    run(r.send())
    ub, _ = upper_bound_usd(body())
    assert r.gate.run_committed() == pytest.approx(ub)


def test_retry_storm_cannot_exceed_the_run_cap(tmp_path):
    def boom(req):
        raise httpx.ConnectTimeout("t")
    r = Rig(tmp_path, boom)
    ub, _ = upper_bound_usd(body())
    refused = 0
    for _ in range(60):                                                              # far more attempts than allowed, every one failing
        try:
            run(r.send())
        except httpx.TransportError:
            pass
        except EstimatedCostLimit:
            refused += 1
    assert r.network_hits == int(0.50 / ub) and r.network_hits <= 16 and refused == 60 - r.network_hits
    assert r.gate.run_committed() <= 0.50 and r.ledger.committed() <= 0.60


def test_ledger_ceiling_binds_below_the_run_cap(tmp_path):
    r = Rig(tmp_path, lambda req: httpx.Response(500, json={}))
    r.ledger.reserve("probe", 0.04)
    r.ledger.reserve("other", 0.30)
    for _ in range(30):
        try:
            run(r.send())
        except EstimatedCostLimit:
            pass
    assert r.ledger.committed() <= 0.60 + 1e-9 and r.gate.run_committed() < 0.50          # 0.26 left in the ledger, not 0.50


def test_request_count_cap(tmp_path):
    r = Rig(tmp_path, lambda req: ok_response(20, 2), max_requests=16)
    tiny = body(user_chars=100, images=0, cap=10, system_chars=100)
    hits = refused = 0
    for _ in range(20):
        try:
            run(r.send(tiny))
            hits += 1
        except EstimatedCostLimit:
            refused += 1
    assert (hits, refused) == (16, 4) and r.network_hits == 16


def test_oversize_request_is_refused_before_any_ledger_write_or_network(tmp_path):
    r = Rig(tmp_path, lambda req: ok_response())
    with pytest.raises(EstimatedCostLimit):
        run(r.send(body(user_chars=60_000)))
    assert r.network_hits == 0 and r.ledger.entries() == []


def test_bound_violation_closes_the_gate(tmp_path):
    r = Rig(tmp_path, lambda req: ok_response(prompt=10_000_000, completion=10))     # the provider reports far more input than we bounded
    run(r.send())
    assert r.gate.violation and "exceeded the reserved upper bound" in r.gate.violation
    with pytest.raises(EstimatedCostLimit):
        run(r.send())
    assert r.network_hits == 1


def test_one_attempt_per_request_id_and_run_marker(tmp_path):
    ledger = Ledger(tmp_path / "l")
    ledger.reserve("wa286", 0.0)
    with pytest.raises(Halt):
        ledger.reserve("wa286", 0.0)
    g = RequestGate(ledger, "wa286")
    g.reserve(1, body())
    with pytest.raises(Exception):
        g.reserve(1, body())


def test_preflight_refuses_without_flag_key_or_with_changed_prices(monkeypatch):
    cfg = live.ModelConfig()
    with pytest.raises(Halt, match="allow-model-calls"):
        live.preflight(cfg, False)
    monkeypatch.delenv(cfg.key_env, raising=False)
    monkeypatch.setattr("agent_readiness.env.load_repo_env", lambda *a, **k: False)            # preflight (shared, scanner.live) loads the repo .env lazily
    with pytest.raises(Halt, match="not set"):
        live.preflight(cfg, True)
    monkeypatch.setattr("agent_readiness.ledger.PRICE_INPUT_PER_M", 9.99)
    with pytest.raises(Halt, match="verified published prices"):
        live.preflight(cfg, True)


def test_leak_scan_and_request_scan(tmp_path):
    forbidden = ["portable-ssd-2tb-external-hard-drive"]
    assert leak_scan({"task_prompt": "find the cheapest ssd", "schema": "{}"}, forbidden) == []
    assert leak_scan({"task_prompt": "go to /Portable-SSD-2TB-External-Hard-Drive.html"}, forbidden)
    trace = tmp_path / "trace.jsonl"
    rows = [{"kind": "model_request", "request_count": 1, "messages": [{"role": "system", "content": "clean"}, {"role": "user", "content": "home page"}]},
            {"kind": "model_request", "request_count": 2, "messages": [{"role": "system", "content": "clean"}, {"role": "user", "content": [{"type": "text", "text": "…portable-ssd-2tb-external-hard-drive…"}]}]},
            {"kind": "model_request", "request_count": 3, "messages": [{"role": "system", "content": "planted portable-ssd-2tb-external-hard-drive"}]}]
    trace.write_text("\n".join(json.dumps(r) for r in rows))
    res = scan_requests(tmp_path, forbidden)
    assert res["first_request_with_expected_page_in_observation"] == 2 and res["system_message_hits"][0]["request"] == 3


def test_schema_probe_success_rejection_and_cap(tmp_path, monkeypatch):
    monkeypatch.setenv("META_MODEL_API_KEY", "stub-key")
    monkeypatch.setattr("agent_readiness.env.load_repo_env", lambda *a, **k: False)
    cfg = live.ModelConfig()
    good = {"evaluation_previous_goal": "x", "memory": "", "next_goal": "x", "thinking": "x", "current_plan_item": 0, "plan_update": None,
            "action": [{"done": {"data": {"task_type": "NAVIGATE", "status": "SUCCESS", "retrieved_data": None, "error_details": None}, "success": True}}]}
    ok = lambda req: httpx.Response(200, headers={"content-type": "application/json"}, json={"choices": [{"finish_reason": "stop", "message": {"content": json.dumps(good)}}], "usage": {"prompt_tokens": 2600, "completion_tokens": 300}})
    ledger = Ledger(tmp_path / "a")
    rec = live.run_schema_probe(cfg, ledger, tmp_path / "pa", allow_model_calls=True, transport=httpx.MockTransport(ok))
    assert rec["success"] and ledger.probe_succeeded() and ledger.committed() < live.PROBE_CAP_USD and rec["calculated_cost_usd"] <= live.PROBE_CAP_USD
    rej = lambda req: httpx.Response(400, headers={"content-type": "application/json"}, json={"error": {"message": "unsupported schema: items"}})
    ledger2 = Ledger(tmp_path / "b")
    rec2 = live.run_schema_probe(cfg, ledger2, tmp_path / "pb", allow_model_calls=True, transport=httpx.MockTransport(rej))
    assert not rec2["success"] and rec2["failure_class"] == "schema_or_request_rejected" and not ledger2.probe_succeeded() and ledger2.committed() == live.PROBE_CAP_USD
    with pytest.raises(Halt):                                                         # the probe is also a single attempt
        live.run_schema_probe(cfg, ledger2, tmp_path / "pc", allow_model_calls=True, transport=httpx.MockTransport(ok))
    with pytest.raises(Halt, match="allow-model-calls"):
        live.run_schema_probe(cfg, Ledger(tmp_path / "c"), tmp_path / "pd", allow_model_calls=False)


def test_authorized_limits_are_pinned_and_the_new_per_request_cap_admits_a_larger_page(tmp_path):
    assert (live.PER_REQUEST_CAP_USD, live.RUN_CAP_USD, live.LEDGER_CEILING_USD, live.MAX_REQUESTS, live.MAX_STEPS, live.RUN_TIMEOUT_S, live.REQUEST_TIMEOUT_S, live.PROBE_CAP_USD) \
        == (0.05, 0.50, 0.60, 16, 16, 300, 30, 0.04)
    big = body(user_chars=40_000)                                  # ~US$0.043 upper bound: refused under the old US$0.04 cap, admitted under US$0.05
    ub, _ = upper_bound_usd(big)
    assert 0.04 < ub <= 0.05
    r = Rig(tmp_path, lambda req: ok_response(), per_request_cap=live.PER_REQUEST_CAP_USD)
    run(r.send(big))
    assert r.network_hits == 1
    r2 = Rig(tmp_path / "old", lambda req: ok_response(), per_request_cap=0.04)
    with pytest.raises(EstimatedCostLimit):
        run(r2.send(big))
    assert r2.network_hits == 0


def test_synthetic_suite_scan_can_use_the_same_durable_gate(tmp_path):
    """execute_scan(request_gate=...) reserves before and settles after every model request (mock provider: no network, no key)."""
    import asyncio as aio
    from agent_readiness.environments.electronics.variants import make_variant
    from agent_readiness.scanner.execute import execute_scan
    from agent_readiness.spend_gate import RequestGate as Gate
    from agent_readiness.suite import registry
    registry.load_all()
    ledger = Ledger(tmp_path / "ledger", ceiling=0.60)
    gate = Gate(ledger, "scan1")
    rec = aio.run(execute_scan("t4-policy-delivery-tessera-whisper", make_variant(), provider="mock", output=tmp_path / "o", request_gate=gate))
    n = rec["metrics"]["model_requests"]
    assert n >= 2 and gate.request_count() == n and gate.unsettled() == [] and gate.violation is None
    assert 0 < gate.run_committed() < 0.05 * n                     # settled to the (mock) actual cost, far below the reserved bounds
    ledger2 = Ledger(tmp_path / "ledger2", ceiling=0.60)
    tight = Gate(ledger2, "scan2", run_cap=0.03)                   # a run cap below one request's bound: nothing may be sent
    rec2 = aio.run(execute_scan("t4-policy-delivery-tessera-whisper", make_variant(), provider="mock", output=tmp_path / "o2", request_gate=tight))
    assert ledger2.entries() == [] and tight.request_count() == 0 and rec2["evaluation"]["passed"] is False      # every attempted request was refused before the network; nothing reserved or spent
