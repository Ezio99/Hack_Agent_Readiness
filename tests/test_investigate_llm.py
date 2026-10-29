"""Provider interfaces: scripted / recorded make no network calls; the Meta client is only reachable through the spend gate (all offline, httpx.MockTransport)."""
import json
from pathlib import Path

import httpx
import pytest
from pydantic import BaseModel

from agent_readiness.agent import ModelConfig
from agent_readiness.investigate.llm import (LLMRequest, RecordedClient, RecordingClient, ScriptedClient, StructuredOutputError, complete_structured, request_sha256)
from agent_readiness.investigate.llm.meta import MetaClient
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


def test_only_the_meta_module_may_use_the_network():
    offenders = []
    for f in (ROOT / "src" / "agent_readiness" / "investigate").rglob("*.py"):
        text = f.read_text()
        if f.name != "meta.py" and any(w in text for w in ("import httpx", "import requests", "import socket", "urllib.request", "import aiohttp")):
            offenders.append(f.name)
    assert offenders == []
