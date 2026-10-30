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


# ---- reasoning effort, sanitized response diagnostics and the under-reservation regression (L0 attempt 2) --------------------------------------------------------------------------------
from agent_readiness.investigate.llm.client import LLMResponse, response_diagnostics
from agent_readiness.investigate.llm.meta import INPUT_OVERHEAD_TOKENS
from agent_readiness.capture import GateRefused


def test_reasoning_effort_is_sent_validated_and_optional(tmp_path):
    seen = []
    led, gate, client = meta(tmp_path, ok_handler(seen))
    client.complete(REQ)
    assert json.loads(seen[0].content)["reasoning_effort"] == "low"
    for bad in ("none", "max", ""):
        with pytest.raises(ValueError):
            MetaClient(ModelConfig(), "k", gate, transport=httpx.MockTransport(ok_handler([])), reasoning_effort=bad)
    off = MetaClient(ModelConfig(), "k", gate_for(tmp_path / "off")[1], transport=httpx.MockTransport(ok_handler(seen)), reasoning_effort=None)
    off.complete(REQ)
    assert "reasoning_effort" not in json.loads(seen[-1].content)


def test_finish_reason_and_reasoning_tokens_are_captured_without_changing_usage_or_cost(tmp_path):
    body = {"choices": [{"message": {"content": None}, "finish_reason": "length"}], "usage": {"prompt_tokens": 105, "completion_tokens": 200, "completion_tokens_details": {"reasoning_tokens": 198}}}
    led, gate, client = meta(tmp_path, lambda r: httpx.Response(200, json=body))
    resp = client.complete(REQ)
    assert resp.text == "" and resp.finish_reason == "length" and resp.reasoning_tokens == 198 and resp.usage == {"prompt_tokens": 105, "completion_tokens": 200}
    assert resp.cost_usd == round(105 * 1.25e-6 + 200 * 4.25e-6, 6)
    odd = {"choices": [{"message": {"content": "{}"}}], "usage": {"prompt_tokens": 1, "completion_tokens": 1, "completion_tokens_details": "weird"}}
    led, gate, client = meta(tmp_path / "odd", lambda r: httpx.Response(200, json=odd))
    r2 = client.complete(REQ)
    assert r2.reasoning_tokens is None and r2.finish_reason is None


def test_structured_failure_diagnostics_classify_without_leaking_text(tmp_path):
    cases = [("", "length", "empty_content"), ('{"a": 1', "length", "truncated"), ("sorry, here you go", "stop", "not_json"), ('{"a": "PRIVATE-VALUE-1"}', "stop", "schema_mismatch")]
    for text, finish, kind in cases:
        resp = LLMResponse(text=text, mode="live", model="m", usage={"prompt_tokens": 10, "completion_tokens": 20}, cost_usd=0.1, finish_reason=finish, reasoning_tokens=7)
        d = response_diagnostics(resp)
        assert d["kind"] == kind and d["finish_reason"] == finish and d["content_chars"] == len(text) and d["reasoning_tokens"] == 7 and "PRIVATE" not in json.dumps(d)

    class C:
        mode, model = "live", "m"
        def complete(self, request):
            return LLMResponse(text='{"a": "PRIVATE-VALUE-1"}', mode="live", model="m", usage={"prompt_tokens": 3, "completion_tokens": 4}, finish_reason="stop")
    with pytest.raises(StructuredOutputError) as ei:
        complete_structured(C(), REQ, Out, retries=0)
    d = ei.value.diagnostics
    assert d["kind"] == "schema_mismatch" and d["schema_errors"] == [{"loc": "a", "type": "int_parsing"}] and "PRIVATE" not in json.dumps(d) and "PRIVATE" not in str(ei.value)


def test_input_overhead_prevents_the_l0_attempt2_under_reservation_without_weakening_the_ceiling(tmp_path):
    """L0 attempt 2: the P1 request reserved US$0.00096 (estimate 89 input tokens + the 200-token cap) but settled at US$0.000981 (>= 105 prompt tokens): a bound violation that closes the gate."""
    import types
    from agent_readiness.investigate import l0
    from agent_readiness.ledger import cost_of
    r = l0.requests()[0]
    body = MetaClient.body(types.SimpleNamespace(model="muse-spark-1.3", reasoning_effort=None), LLMRequest(messages=r["messages"], purpose=r["purpose"], max_tokens=200, response_schema=l0._schema(r["model"])))
    usage = {"prompt_tokens": 105, "completion_tokens": 200}                               # the smallest usage that reproduces the observed 0.000981
    assert cost_of(usage) == 0.000981
    old = RequestGate(Ledger(tmp_path / "old", ceiling=1.0), "x", input_overhead_tokens=0)
    old.reserve(1, body)
    assert old.settle(1, {"http_status": 200, "usage": usage}).get("bound_violation") and old.violation              # reproduces the failure
    new = RequestGate(Ledger(tmp_path / "new", ceiling=1.0), "x", input_overhead_tokens=INPUT_OVERHEAD_TOKENS)
    reserved = new.reserve(1, body)
    assert reserved["upper_bound_usd"] > cost_of(usage) and reserved["upper_bound_usd"] > 0.00096
    out = new.settle(1, {"http_status": 200, "usage": usage})
    assert out["settled"] and not new.violation and out["actual_usd"] == 0.000981
    tight = RequestGate(Ledger(tmp_path / "tight", ceiling=0.001), "x", input_overhead_tokens=INPUT_OVERHEAD_TOKENS)     # the hard ceiling still binds, and the larger reservation counts against it
    with pytest.raises(GateRefused):
        tight.reserve(1, body)
    assert tight.ledger.entries() == []
    with pytest.raises(GateRefused):
        RequestGate(Ledger(tmp_path / "cap", ceiling=1.0), "x", per_request_cap=0.001, input_overhead_tokens=INPUT_OVERHEAD_TOKENS).reserve(1, body)


def test_default_gate_is_unchanged_for_other_live_paths(tmp_path):
    from agent_readiness.spend_gate import upper_bound_usd
    body = {"model": "m", "messages": [{"role": "user", "content": "hello"}], "max_completion_tokens": 100}
    assert upper_bound_usd(body) == upper_bound_usd(body, 0) and upper_bound_usd(body, 128)[0] > upper_bound_usd(body)[0]
    assert RequestGate(Ledger(tmp_path, ceiling=1.0), "x").input_overhead_tokens == 0


def test_diagnostics_tolerate_non_string_content():
    d = response_diagnostics(LLMResponse(text=[{"type": "text", "text": "PRIVATE"}], mode="live", model="m", finish_reason="stop"))     # type: ignore[arg-type]
    assert d["kind"] == "not_text" and d["content_chars"] == 0 and "PRIVATE" not in json.dumps(d)


# ---- reservation guarantees (reviewer finding): what the bound covers, what it does not, and that the failure mode is detected -------------------------------------------------------------
def _body(chars: int, schema_props: int = 1, cap: int = 512) -> dict:
    schema = {"type": "object", "additionalProperties": False, "required": [f"p{i}" for i in range(schema_props)], "properties": {f"p{i}": {"type": "string", "description": "x" * 40} for i in range(schema_props)}}
    return {"model": "m", "max_completion_tokens": cap, "messages": [{"role": "system", "content": "s" * (chars // 2)}, {"role": "user", "content": "u" * (chars - chars // 2)}],
            "response_format": {"type": "json_schema", "json_schema": {"name": "o", "strict": True, "schema": schema}}}


def test_bound_grows_with_prompt_and_schema_size_and_includes_the_fixed_allowance_exactly_once():
    from agent_readiness.spend_gate import upper_bound_usd
    from agent_readiness.ledger import PRICE_INPUT_PER_M
    sizes = [(100, 1), (2_000, 5), (20_000, 20), (80_000, 60)]
    bounds = [upper_bound_usd(_body(c, p))[0] for c, p in sizes]
    assert bounds == sorted(bounds) and len(set(bounds)) == len(bounds)
    for c, p in sizes:
        plain, with_overhead = upper_bound_usd(_body(c, p)), upper_bound_usd(_body(c, p), INPUT_OVERHEAD_TOKENS)
        step = INPUT_OVERHEAD_TOKENS * PRICE_INPUT_PER_M / 1e6
        assert step - 1e-9 <= with_overhead[0] - plain[0] <= step + 6e-6          # a constant (plus at most the rounding of the old 5-decimal estimate), not scaled with size
        assert with_overhead[1]["input_overhead_tokens"] == INPUT_OVERHEAD_TOKENS and plain[1]["input_overhead_tokens"] == 0


def test_bound_covers_larger_prompts_and_schemas_under_its_stated_assumptions(tmp_path):
    """Stated assumption: the provider tokenises at >= ~3.6 characters per token (chars/4 with a 10 % margin) and adds at most INPUT_OVERHEAD_TOKENS of fixed framing. Under that model no size violates."""
    from agent_readiness.spend_gate import upper_bound_usd
    from agent_readiness.capture import message_texts
    for i, (c, p) in enumerate([(100, 1), (2_000, 5), (20_000, 20), (80_000, 60)]):
        body = _body(c, p)
        sysm, usr, _ = message_texts(body)
        schema_bytes = len(json.dumps(body["response_format"]["json_schema"]["schema"], sort_keys=True, separators=(",", ":")))
        actual_prompt = round((len(sysm) + len(usr) + schema_bytes) / 3.7) + INPUT_OVERHEAD_TOKENS            # slightly denser than the estimate's 4.0, plus the full allowance
        gate = RequestGate(Ledger(tmp_path / str(i), ceiling=10.0), "x", per_request_cap=1.0, run_cap=10.0, input_overhead_tokens=INPUT_OVERHEAD_TOKENS)
        gate.reserve(1, body)
        out = gate.settle(1, {"http_status": 200, "usage": {"prompt_tokens": actual_prompt, "completion_tokens": body["max_completion_tokens"]}})      # worst case: the whole cap is used
        assert out["settled"] and not gate.violation, (c, p)


def test_text_denser_than_the_assumption_is_not_covered_but_is_detected_and_closes_the_gate(tmp_path):
    """Documented non-guarantee: if tokenisation is much denser (here 2 characters per token) a large prompt is under-reserved. The truth is recorded, a violation is flagged and the gate refuses the next send."""
    from agent_readiness.capture import message_texts
    body = _body(40_000, 10)
    sysm, usr, _ = message_texts(body)
    gate = RequestGate(Ledger(tmp_path, ceiling=10.0), "x", per_request_cap=1.0, run_cap=10.0, input_overhead_tokens=INPUT_OVERHEAD_TOKENS)
    reserved = gate.reserve(1, body)["upper_bound_usd"]
    out = gate.settle(1, {"http_status": 200, "usage": {"prompt_tokens": (len(sysm) + len(usr)) // 2, "completion_tokens": 512}})
    assert out.get("bound_violation") and gate.violation and out["actual_usd"] > reserved
    assert gate.ledger.committed() == out["actual_usd"]                                                        # the ledger holds the actual cost, not the smaller reservation
    with pytest.raises(GateRefused):
        gate.reserve(2, body)


def test_details_separate_image_headroom_from_the_fixed_input_overhead():
    from agent_readiness.spend_gate import upper_bound_usd, IMAGE_UPPER_BOUND_TOKENS
    from agent_readiness.capture import IMAGE_TOKENS_ESTIMATE, INPUT_SAFETY_MARGIN
    img = {"model": "m", "max_completion_tokens": 100, "messages": [{"role": "user", "content": [{"type": "text", "text": "hi"}, {"type": "image_url", "image_url": {"url": "data:image/png;base64,AAAA"}}]}]}
    expected_headroom = round((IMAGE_UPPER_BOUND_TOKENS - IMAGE_TOKENS_ESTIMATE) * INPUT_SAFETY_MARGIN)
    _u0, d0 = upper_bound_usd(img)
    _u1, d1 = upper_bound_usd(img, 128)
    assert d0["image_headroom_tokens"] == d1["image_headroom_tokens"] == expected_headroom and d0["input_overhead_tokens"] == 0 and d1["input_overhead_tokens"] == 128
    text_only = upper_bound_usd({"model": "m", "max_completion_tokens": 100, "messages": [{"role": "user", "content": "hi"}]}, 128)[1]
    assert text_only["image_headroom_tokens"] == 0 and text_only["input_overhead_tokens"] == 128


# ---- non-string provider content: the whole validation/recovery path fails cleanly (reviewer finding) -----------------------------------------------------------------------------------
def test_non_string_content_never_reaches_validation_or_recovery(monkeypatch):
    import agent_readiness.investigate.llm.client as C

    def boom(*a, **k):
        raise AssertionError("recover() must not be called with non-string content")
    monkeypatch.setattr(C, "recover", boom)
    for content in ([{"type": "text", "text": "PRIVATE-PART"}], {"text": "PRIVATE"}, 42):
        class Cl:
            mode, model = "live", "m"
            def complete(self, request, content=content):
                return LLMResponse(text=content, mode="live", model="m", usage={"prompt_tokens": 5, "completion_tokens": 6}, cost_usd=0.01, finish_reason="stop")   # type: ignore[arg-type]
        with pytest.raises(StructuredOutputError) as ei:
            complete_structured(Cl(), REQ, Out, retries=1)
        d = ei.value.diagnostics
        assert d["kind"] == "not_text" and d["completion_tokens"] == 6 and "non_string_content" in str(ei.value) and "PRIVATE" not in json.dumps(d) + str(ei.value)


def test_non_string_content_end_to_end_through_the_real_client_and_l0(tmp_path):
    from agent_readiness.investigate import l0
    body = {"choices": [{"message": {"content": [{"type": "text", "text": "PRIVATE-PART"}]}, "finish_reason": "stop"}], "usage": {"prompt_tokens": 120, "completion_tokens": 30, "completion_tokens_details": {"reasoning_tokens": 12}}}
    led, gate, client = meta(tmp_path / "c", lambda r: httpx.Response(200, json=body), run_cap=0.10, per_request_cap=0.03, max_requests=6)
    cfg = ModelConfig()
    rep = l0.run(tmp_path / "out", approved_sha256=l0.manifest_sha256(l0.manifest(cfg)), allow_model_calls=True, client=client, config=cfg)
    (only,) = rep["results"]                                                                              # P1 unusable: the probe stops without crashing
    assert only["valid"] is False and only["diagnostics"]["kind"] == "not_text" and only["diagnostics"]["reasoning_tokens"] == 12 and only["cost_usd"] > 0
    assert rep["total_calculated_usd"] == only["cost_usd"] and "PRIVATE" not in json.dumps(rep)
    assert [e["kind"] for e in led.entries()] == ["reserve", "settle"]                                    # a 200 with usage settles the actual cost
