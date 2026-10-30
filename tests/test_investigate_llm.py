"""Provider interfaces: scripted / recorded make no network calls; the Meta client is only reachable through the spend gate (all offline, httpx.MockTransport)."""
import json
from pathlib import Path

import httpx
import pytest
from pydantic import BaseModel

from agent_readiness.agent import ModelConfig
from agent_readiness.investigate.llm import (LLMRequest, RecordedClient, RecordingClient, ScriptedClient, StructuredOutputError, complete_structured, request_sha256)
from agent_readiness.investigate.llm.meta import MetaClient, ProviderError
from agent_readiness.ledger import Halt, Ledger
from agent_readiness.spend_gate import RequestGate

ROOT = Path(__file__).resolve().parents[1]
REQ = LLMRequest(messages=[{"role": "user", "content": "hello"}], purpose="investigate", max_tokens=256, response_schema={"type": "object", "properties": {"a": {"type": "integer"}}, "required": ["a"], "additionalProperties": False})


class Out(BaseModel):
    a: int


def test_scripted_client_is_deterministic_and_fails_loudly_when_exhausted():
    c = ScriptedClient(['{"a": 1}'])
    r = c.complete(REQ)
    assert r.mode == "scripted" and r.text == '{"a": 1}' and r.request_sha256 == request_sha256(REQ)
    with pytest.raises(RuntimeError):
        c.complete(REQ)


def test_structured_strict_json_prose_prefix_and_failure():
    p, _, n = complete_structured(ScriptedClient(['{"a": 2}']), REQ, Out)
    assert p.a == 2 and n == 1
    p, _, n = complete_structured(ScriptedClient(['Here is my answer.{"a": 3}']), REQ, Out)          # the documented Muse pattern, via the byte-preserving parser
    assert p.a == 3
    p, _, n = complete_structured(ScriptedClient(["nonsense", '{"a": 4}']), REQ, Out, retries=1)
    assert p.a == 4 and n == 2
    with pytest.raises(StructuredOutputError):
        complete_structured(ScriptedClient(["nonsense", "still nonsense"]), REQ, Out, retries=1)
    with pytest.raises(StructuredOutputError):
        complete_structured(ScriptedClient(['Answer.{"a": 1} trailing words']), REQ, Out, retries=0)     # trailing material is never repaired


def test_record_then_replay_round_trip_and_drift_detection(tmp_path):
    path = tmp_path / "t.jsonl"
    rec = RecordingClient(ScriptedClient(['{"a": 5}']), path)
    rec.complete(REQ)
    rp = RecordedClient(path)
    r = rp.complete(REQ)
    assert r.mode == "recorded" and r.text == '{"a": 5}' and r.cost_usd == 0.0
    other = LLMRequest(messages=[{"role": "user", "content": "different"}], purpose="investigate")
    with pytest.raises(KeyError):
        rp.complete(other)


def gate_for(tmp_path, **kw):
    led = Ledger(tmp_path / "spend", ceiling=kw.pop("ceiling", 1.0))
    return led, RequestGate(led, "inv1", **kw)


def meta(tmp_path, handler, **kw):
    led, gate = gate_for(tmp_path, **kw)
    cfg = ModelConfig()
    return led, gate, MetaClient(cfg, "sk-test-SECRET-KEY", gate, transport=httpx.MockTransport(handler))


def ok_handler(seen):
    def h(request: httpx.Request):
        seen.append(request)
        return httpx.Response(200, json={"choices": [{"message": {"content": '{"a": 1}'}}], "usage": {"prompt_tokens": 120, "completion_tokens": 30}})
    return h


def test_meta_client_cannot_touch_the_network_without_unlock():
    cfg = ModelConfig()
    with pytest.raises(Halt):
        MetaClient(cfg, "k", gate=None)                                    # no transport and no live unlock


def test_meta_live_requires_flag_key_and_https(tmp_path, monkeypatch):
    led = Ledger(tmp_path / "s", 1.0)
    monkeypatch.delenv("META_MODEL_API_KEY", raising=False)
    monkeypatch.setattr("agent_readiness.env.load_repo_env", lambda *a, **k: None)
    with pytest.raises(Halt, match="allow-model-calls"):
        MetaClient.live(ModelConfig(), led, "r", allow_model_calls=False, run_cap_usd=0.1)
    with pytest.raises(Halt, match="not set"):
        MetaClient.live(ModelConfig(), led, "r", allow_model_calls=True, run_cap_usd=0.1)
    monkeypatch.setenv("META_MODEL_API_KEY", "k")
    with pytest.raises(Halt, match="https"):
        MetaClient.live(ModelConfig(base_url="http://example.test/v1"), led, "r", allow_model_calls=True, run_cap_usd=0.1)
    assert led.entries() == []                                              # nothing reserved, nothing sent


def test_meta_request_shape_reserves_before_sending_and_settles(tmp_path):
    seen, order = [], []
    led, gate, _ = meta(tmp_path, ok_handler(seen))

    def handler(request):
        order.append(("send", len([e for e in led.entries() if e["kind"] == "reserve"])))     # the reservation must already be on disk when the request leaves
        return ok_handler(seen)(request)
    client = MetaClient(ModelConfig(), "sk-test-SECRET-KEY", gate, transport=httpx.MockTransport(handler))
    r = client.complete(REQ)
    body = json.loads(seen[0].content)
    assert order == [("send", 1)] and r.mode == "live" and r.text == '{"a": 1}'
    assert str(seen[0].url) == "https://api.meta.ai/v1/chat/completions" and seen[0].headers["authorization"] == "Bearer sk-test-SECRET-KEY"
    assert body["model"] == "muse-spark-1.3" and body["max_completion_tokens"] == 256 and "temperature" not in body
    assert body["response_format"]["json_schema"]["strict"] is True and body["response_format"]["type"] == "json_schema"
    kinds = [e["kind"] for e in led.entries()]
    assert kinds == ["reserve", "settle"] and r.usage == {"prompt_tokens": 120, "completion_tokens": 30} and 0 < r.cost_usd < 0.01
    assert led.committed() == r.cost_usd                                                                  # settled to the calculated actual


def test_meta_gate_refusal_sends_nothing(tmp_path):
    seen = []
    led, gate, client = meta(tmp_path, ok_handler(seen), per_request_cap=0.000001)
    with pytest.raises(Halt, match="spend gate refused"):
        client.complete(REQ)
    assert seen == [] and led.entries() == []
    led2, gate2, client2 = meta(tmp_path / "b", ok_handler(seen), max_requests=1)
    client2.complete(REQ)
    with pytest.raises(Halt):
        client2.complete(REQ)
    assert len(seen) == 1


def test_meta_failures_keep_the_reservation_and_never_leak_the_key(tmp_path):
    for response in (httpx.Response(500, text="boom sk-test-SECRET-KEY"), httpx.Response(200, json={"choices": []})):
        led, gate, client = meta(tmp_path / str(id(response)), lambda r, resp=response: resp)
        with pytest.raises(RuntimeError) as ei:
            client.complete(REQ)
        assert "SECRET" not in str(ei.value) and "SECRET" not in repr(ei.value.__cause__)
        reserved = [e for e in led.entries() if e["kind"] == "reserve"][0]["usd"]
        assert led.committed() == reserved and reserved > 0                                              # full upper bound still counted
    def net_error(request):
        raise httpx.ConnectError("no route")
    led, gate, client = meta(tmp_path / "net", net_error)
    with pytest.raises(RuntimeError):
        client.complete(REQ)
    assert led.committed() > 0 and [e["kind"] for e in led.entries()] == ["reserve"]


def test_only_the_two_sanctioned_modules_may_use_the_network():
    """llm/meta.py (model calls, behind the spend gate) and inspect/crawl.py (site inspection, behind the origin/SSRF/robots rules) are the only network-capable modules."""
    allowed = {"llm/meta.py", "inspect/crawl.py"}
    base = ROOT / "src" / "agent_readiness" / "investigate"
    offenders = []
    for f in base.rglob("*.py"):
        text = f.read_text()
        if f.relative_to(base).as_posix() not in allowed and any(w in text for w in ("import httpx", "import requests", "import socket", "urllib.request", "import aiohttp")):
            offenders.append(f.relative_to(base).as_posix())
    assert offenders == []


# ---- classified provider errors (L0 diagnostics): the cause of a failed request is kept, sanitized, and never leaks the key, headers, request body or model text -------------------
KEY = "sk-test-SECRET-KEY"
PROVIDER_JSON = {"error": {"type": "invalid_request_error", "code": "bad_schema", "message": f"schema rejected near additionalProperties; echoed {KEY} Bearer abcdefghijkl"}}


@pytest.mark.parametrize("status", [400, 401, 403, 429, 500])
def test_http_errors_keep_status_and_a_sanitized_provider_summary(tmp_path, status):
    led, gate, client = meta(tmp_path, lambda r: httpx.Response(status, json=PROVIDER_JSON))
    with pytest.raises(ProviderError) as ei:
        client.complete(REQ)
    e = ei.value
    assert isinstance(e, RuntimeError) and e.category == "http" and e.status == status
    assert "invalid_request_error" in e.summary and "bad_schema" in e.summary and "additionalProperties" in e.summary
    shown = str(e) + repr(e) + e.summary
    assert "SECRET" not in shown and "abcdefghijkl" not in shown and "hello" not in shown and "Authorization" not in shown      # no key, bearer, prompt or header
    assert f"HTTP {status}" in str(e) and e.__cause__ is None
    reserved = [x for x in led.entries() if x["kind"] == "reserve"][0]["usd"]
    assert [x["kind"] for x in led.entries()] == ["reserve"] and led.committed() == reserved      # unchanged accounting: the full upper bound stays counted, nothing settled


def test_non_json_and_oversized_http_bodies_never_surface_raw_text(tmp_path):
    for body in ("<html>gateway " + KEY + " dump</html>", "x" * 5000):
        led, gate, client = meta(tmp_path / str(len(body)), lambda r, b=body: httpx.Response(502, text=b))
        with pytest.raises(ProviderError) as ei:
            client.complete(REQ)
        assert ei.value.status == 502 and "SECRET" not in str(ei.value) and "gateway" not in ei.value.summary and len(ei.value.summary) <= 160


def test_transport_errors_are_distinguished_from_http_errors(tmp_path):
    for exc, expect in ((httpx.ReadTimeout("slow"), "timeout"), (httpx.ConnectTimeout("slow"), "timeout"), (httpx.ConnectError("no route"), "ConnectError"), (httpx.RemoteProtocolError("bad"), "RemoteProtocolError")):
        def boom(request, exc=exc):
            raise exc
        led, gate, client = meta(tmp_path / type(exc).__name__, boom)
        with pytest.raises(ProviderError) as ei:
            client.complete(REQ)
        assert ei.value.category == "transport" and ei.value.status is None and expect in ei.value.summary
        assert led.committed() > 0 and [x["kind"] for x in led.entries()] == ["reserve"]


def test_parse_errors_after_a_200_are_a_third_category_and_the_key_stays_counted(tmp_path):
    for resp in (httpx.Response(200, json={"choices": []}), httpx.Response(200, text="not json"), httpx.Response(200, json=[1, 2])):
        led, gate, client = meta(tmp_path / str(id(resp)), lambda r, x=resp: x)
        with pytest.raises(ProviderError) as ei:
            client.complete(REQ)
        assert ei.value.category == "parse" and ei.value.status == 200 and "unexpected response shape" in ei.value.summary
        assert led.committed() > 0                                                                  # no usage: the full reservation is still counted


def test_model_output_validation_stays_a_separate_layer(tmp_path):
    led, gate, client = meta(tmp_path, lambda r: httpx.Response(200, json={"choices": [{"message": {"content": "not the schema"}}], "usage": {"prompt_tokens": 10, "completion_tokens": 5}}))
    with pytest.raises(StructuredOutputError):
        complete_structured(client, REQ, Out, retries=0)


def test_l0_report_records_the_classified_cause_without_changing_caps_or_stopping_rules(tmp_path):
    from agent_readiness.investigate import l0
    led, gate, client = meta(tmp_path / "c", lambda r: httpx.Response(400, json=PROVIDER_JSON), run_cap=0.10, per_request_cap=0.03, max_requests=6)
    cfg = ModelConfig()
    rep = l0.run(tmp_path / "out", approved_sha256=l0.manifest_sha256(l0.manifest(cfg)), allow_model_calls=True, client=client, config=cfg)
    (only,) = rep["results"]                                                                        # P1 failed: the probe stops, no further requests (unchanged rule)
    assert only["error_category"] == "http" and only["http_status"] == 400 and "bad_schema" in only["error_summary"] and only["error"] == "ProviderError"
    assert rep["evaluation"]["verdict"] == "FAIL" and rep["total_calculated_usd"] == 0.0
    text = json.dumps(rep)
    assert "SECRET" not in text and "Return a=3" not in text and "Bearer" not in text
    assert len([e for e in led.entries() if e["kind"] == "reserve"]) == 1
