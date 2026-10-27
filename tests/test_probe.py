import json
import httpx
import pytest
from agent_readiness import probe
from agent_readiness.agent import ModelConfig

KEY = "sk-probe-test-not-real-0123456789"


def run_probe(tmp_path, monkeypatch, handler, key=KEY):
    if key:
        monkeypatch.setenv("META_MODEL_API_KEY", key)
    else:
        monkeypatch.delenv("META_MODEL_API_KEY", raising=False)
    calls = []
    def counted(request):
        calls.append(request)
        return handler(request)
    path, record = probe.stage_a(ModelConfig(), tmp_path, transport=httpx.MockTransport(counted))
    return path, record, calls


def test_success_records_status_model_usage_and_cost(tmp_path, monkeypatch):
    def handler(request):
        assert request.url == "https://api.meta.ai/v1/chat/completions"
        assert request.headers["authorization"] == f"Bearer {KEY}"
        body = json.loads(request.content)
        assert body["max_completion_tokens"] == 512 and body["reasoning_effort"] == "low" and body["model"] == "muse-spark-1.3"
        return httpx.Response(200, json={"model": "muse-spark-1.3", "choices": [{"message": {"content": "OK"}, "finish_reason": "stop"}],
                                         "usage": {"prompt_tokens": 9, "completion_tokens": 1, "total_tokens": 10, "cost": 0.0001}})
    path, record, calls = run_probe(tmp_path, monkeypatch, handler)
    assert len(calls) == 1 and record["request_attempts"] == 1
    assert record["success"] and record["http_status"] == 200 and record["response_model"] == "muse-spark-1.3"
    assert record["usage"]["total_tokens"] == 10 and record["provider_reported_cost"] == {"cost": 0.0001}
    assert KEY not in (path / "probe.json").read_text()


def test_unreported_usage_and_cost_stay_null(tmp_path, monkeypatch):
    _, record, _ = run_probe(tmp_path, monkeypatch, lambda r: httpx.Response(200, json={"choices": [{"message": {"content": "OK"}}]}))
    assert record["success"] and record["usage"] is None and record["provider_reported_cost"] is None


@pytest.mark.parametrize("status", [401, 404, 429, 500])
def test_http_error_is_single_attempt_sanitized_failure(tmp_path, monkeypatch, status):
    body = {"error": {"message": f"bad credential {KEY}", "authorization": f"Bearer {KEY}"}}
    path, record, calls = run_probe(tmp_path, monkeypatch, lambda r: httpx.Response(status, json=body))
    assert len(calls) == 1 and record["request_attempts"] == 1  # no retries
    assert not record["success"] and record["http_status"] == status and record["status"] == "failed"
    assert KEY not in (path / "probe.json").read_text()


def test_timeout_is_recorded_without_retry(tmp_path, monkeypatch):
    def handler(request):
        raise httpx.ReadTimeout(f"timed out talking to {request.url}", request=request)
    _, record, calls = run_probe(tmp_path, monkeypatch, handler)
    assert len(calls) == 1 and not record["success"] and "ReadTimeout" in record["error"] and record["http_status"] is None


def test_missing_key_makes_no_request(tmp_path, monkeypatch):
    _, record, calls = run_probe(tmp_path, monkeypatch, lambda r: httpx.Response(200, json={}), key=None)
    assert calls == [] and record["request_attempts"] == 0 and record["status"] == "setup_error"


def test_insecure_or_credentialed_endpoint_rejected(tmp_path, monkeypatch):
    monkeypatch.setenv("META_MODEL_API_KEY", KEY)
    for url in ["http://api.meta.ai/v1", "https://user:pw@api.meta.ai/v1", "https://api.meta.ai/v1?key=x"]:
        with pytest.raises(ValueError):
            probe.stage_a(ModelConfig(base_url=url), tmp_path, transport=httpx.MockTransport(lambda r: httpx.Response(200)))


def test_cli_probe_requires_explicit_flag(monkeypatch, capsys):
    import sys
    from agent_readiness import cli
    monkeypatch.setattr(sys, "argv", ["readiness", "probe", "--stage", "a"])
    monkeypatch.setattr(cli, "load_repo_env", lambda: None)
    with pytest.raises(SystemExit) as exc:
        cli.main()
    assert "disabled" in str(exc.value)


# ---- Stage B ----------------------------------------------------------------

def good_content(**over):
    data = {"product_id": "PROBE-0", "price_cents": 100, "available": False}
    data.update(over)
    return json.dumps({"evaluation_previous_goal": "n/a", "memory": "", "next_goal": "finish",
                       "action": [{"done": {"data": data}}]})


def b_reply(content, finish="stop", usage=None):
    return httpx.Response(200, headers={"x-request-id": "req-b"}, json={
        "model": "muse-spark-1.3", "choices": [{"finish_reason": finish, "message": {"role": "assistant", "content": content}}],
        "usage": usage or {"prompt_tokens": 2100, "completion_tokens": 150, "total_tokens": 2250,
                           "completion_tokens_details": {"reasoning_tokens": 100}}})


def run_b(tmp_path, monkeypatch, handler, key=KEY):
    if key:
        monkeypatch.setenv("META_MODEL_API_KEY", key)
    else:
        monkeypatch.delenv("META_MODEL_API_KEY", raising=False)
    calls = []
    def counted(request):
        calls.append(request)
        return handler(request)
    path, record = probe.stage_b(ModelConfig(), tmp_path, transport=httpx.MockTransport(counted))
    return path, record, calls


def test_stage_b_success_sends_exact_real_schema_and_records_evidence(tmp_path, monkeypatch):
    seen = {}
    def handler(request):
        seen["body"] = json.loads(request.content)
        return b_reply(good_content())
    path, record, calls = run_b(tmp_path, monkeypatch, handler)
    body = seen["body"]
    assert len(calls) == 1 and record["request_attempts"] == 1
    assert body["reasoning_effort"] == "low" and body["max_completion_tokens"] == 1024
    assert body["response_format"]["json_schema"]["strict"] is True and body["model"] == "muse-spark-1.3"
    assert body["messages"][0]["content"] == probe.STAGE_B_PROMPT
    schema, _ = probe.build_agent_output_schema()
    assert body["response_format"]["json_schema"]["schema"] == schema  # unmodified
    digest, size = probe._schema_digest(schema)
    assert record["schema_sha256"] == digest and record["schema_canonical_bytes"] == size
    assert record["success"] and record["http_status"] == 200 and record["request_id"] == "req-b"
    g = record["grading"]
    assert g["json_parsed"] and g["agent_output_valid"] and g["single_done_action"] and g["values_match"]
    assert record["usage"]["completion_tokens_details"]["reasoning_tokens"] == 100
    assert (path / "schema.json").exists() and KEY not in (path / "probe.json").read_text()


def test_stage_b_request_matches_what_the_browser_use_adapter_emits(tmp_path):
    """Same response_format as ChatOpenAI.ainvoke; only messages/reasoning_effort differ."""
    import asyncio
    from browser_use.llm.messages import UserMessage
    from agent_readiness.agent import create_model, profile
    from agent_readiness.probe import build_agent_output_schema
    schema, output_model = build_agent_output_schema()
    model = create_model(ModelConfig(), profile(), api_key="synthetic-key")
    captured = {}
    async def go():
        async def handle(request):
            captured["body"] = json.loads(request.content)
            return httpx.Response(200, json={"id": "x", "object": "chat.completion", "created": 0, "model": "m",
                "choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": good_content()}}]})
        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
            model.http_client = client
            sdk = model.get_client()
            sdk._platform = "Linux"
            model.get_client = lambda: sdk
            await model.ainvoke([UserMessage(content="x")], output_format=output_model)
    asyncio.run(go())
    ours = probe.stage_b_body(ModelConfig(), schema)
    assert captured["body"]["response_format"] == ours["response_format"]
    assert captured["body"]["max_completion_tokens"] == 4096 and captured["body"]["reasoning_effort"] == "low"  # v3 default


def test_stage_b_schema_rejection_is_recorded_verbatim_and_not_retried(tmp_path, monkeypatch):
    err = {"error": {"message": f"Invalid schema: nesting depth exceeds 10 (key {KEY})", "type": "invalid_request_error"}}
    path, record, calls = run_b(tmp_path, monkeypatch, lambda r: httpx.Response(400, headers={"x-request-id": "req-400"}, json=err))
    assert len(calls) == 1 and not record["success"] and record["http_status"] == 400
    assert record["failure_class"] == "schema_or_request_rejected" and record["request_id"] == "req-400"
    assert "nesting depth exceeds 10" in json.dumps(record["error"]) and KEY not in (path / "probe.json").read_text()


@pytest.mark.parametrize("content,finish,klass", [
    (None, "length", "cap_exhausted"),
    ("{not json", "stop", "unparsable_or_invalid"),
    (json.dumps({"action": "wrong"}), "stop", "unparsable_or_invalid"),
    (good_content(price_cents=101), "stop", "accepted_but_values_mismatch"),
    (good_content(available=True), "stop", "accepted_but_values_mismatch"),
    (good_content(product_id="probe-0"), "stop", "accepted_but_values_mismatch"),
    (good_content(), "length", "not_stopped"),
])
def test_stage_b_failure_classes(tmp_path, monkeypatch, content, finish, klass):
    _, record, calls = run_b(tmp_path, monkeypatch, lambda r: b_reply(content, finish))
    assert len(calls) == 1 and not record["success"] and record["failure_class"] == klass


def test_stage_b_rejects_bool_for_integer_and_extra_actions(tmp_path, monkeypatch):
    _, record, _ = run_b(tmp_path, monkeypatch, lambda r: b_reply(good_content(price_cents=True)))
    assert not record["success"]
    two = json.loads(good_content()); two["action"].append({"wait": {"seconds": 1}})
    _, record, _ = run_b(tmp_path, monkeypatch, lambda r: b_reply(json.dumps(two)))
    assert record["failure_class"] == "accepted_but_values_mismatch"


def test_stage_b_timeout_missing_key_and_cli(tmp_path, monkeypatch):
    def boom(request):
        raise httpx.ReadTimeout("slow", request=request)
    _, record, calls = run_b(tmp_path, monkeypatch, boom)
    assert len(calls) == 1 and record["failure_class"] == "timeout" and not record["success"]
    _, record, calls = run_b(tmp_path, monkeypatch, lambda r: b_reply(good_content()), key=None)
    assert calls == [] and record["request_attempts"] == 0 and record["status"] == "setup_error"
    import sys
    from agent_readiness import cli
    monkeypatch.setattr(sys, "argv", ["readiness", "probe", "--stage", "b"])
    monkeypatch.setattr(cli, "load_repo_env", lambda: None)
    with pytest.raises(SystemExit) as exc:
        cli.main()
    assert "disabled" in str(exc.value)


# ---- Stage C ----------------------------------------------------------------

def c_reply(content, finish="stop", usage=None):
    return httpx.Response(200, headers={"x-request-id": "req-c"}, json={
        "model": "muse-spark-1.3", "choices": [{"finish_reason": finish, "message": {"role": "assistant", "content": content}}],
        "usage": usage or {"prompt_tokens": 120, "completion_tokens": 140, "total_tokens": 260,
                           "completion_tokens_details": {"reasoning_tokens": 120}}})


def run_c(tmp_path, monkeypatch, handler, key=KEY):
    if key:
        monkeypatch.setenv("META_MODEL_API_KEY", key)
    else:
        monkeypatch.delenv("META_MODEL_API_KEY", raising=False)
    calls = []
    def counted(request):
        calls.append(request)
        return handler(request)
    path, record = probe.stage_c(ModelConfig(), tmp_path, transport=httpx.MockTransport(counted))
    return path, record, calls


def test_stage_c_image_is_deterministic_synthetic_and_metadata_free():
    import hashlib
    png = probe.stage_c_png()
    assert hashlib.sha256(png).hexdigest() == probe.STAGE_C_IMAGE_SHA256 and len(png) == 410
    assert png == probe.stage_c_png()
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    assert [png[i + 4:i + 8] for i in (8, 8 + 12 + 13, 8 + 12 + 13 + 8 + int.from_bytes(png[8 + 12 + 13:8 + 12 + 13 + 4], "big") + 4)] == [b"IHDR", b"IDAT", b"IEND"]
    for marker in (b"tEXt", b"iTXt", b"zTXt", b"eXIf", b"pHYs", b"tIME"):
        assert marker not in png


def test_stage_c_success_request_shape_and_evidence(tmp_path, monkeypatch):
    seen = {}
    def handler(request):
        seen["body"] = json.loads(request.content)
        return c_reply("color=red; digit=7")
    path, record, calls = run_c(tmp_path, monkeypatch, handler)
    body = seen["body"]
    assert len(calls) == 1 and record["request_attempts"] == 1 and record["success"]
    assert body["reasoning_effort"] == "low" and body["max_completion_tokens"] == 512 and body["model"] == "muse-spark-1.3"
    text, image = body["messages"][0]["content"]
    assert text == {"type": "text", "text": probe.STAGE_C_PROMPT}
    assert image["type"] == "image_url" and image["image_url"]["detail"] == "high"
    assert image["image_url"]["url"].startswith("data:image/png;base64,")
    import base64, hashlib
    assert hashlib.sha256(base64.b64decode(image["image_url"]["url"].split(",", 1)[1])).hexdigest() == probe.STAGE_C_IMAGE_SHA256
    assert record["reasoning_token_share"] == round(120 / 140, 3) and record["low_reasoning_headroom"] is False
    assert record["image"]["sha256"] == probe.STAGE_C_IMAGE_SHA256 and record["image"]["synthetic"] is True
    assert (path / "stage-c-input.png").read_bytes() == probe.stage_c_png()
    text = (path / "probe.json").read_text()
    assert KEY not in text and "iVBORw0KGgo" not in text  # no inline base64 in artifact


def test_stage_c_request_matches_browser_use_message_format(tmp_path):
    import asyncio, base64
    from browser_use.llm.messages import UserMessage, ContentPartTextParam, ContentPartImageParam, ImageURL
    from agent_readiness.agent import create_model, profile
    png = probe.stage_c_png()
    msg = UserMessage(content=[ContentPartTextParam(text=probe.STAGE_C_PROMPT), ContentPartImageParam(
        image_url=ImageURL(url="data:image/png;base64," + base64.b64encode(png).decode(), media_type="image/png", detail="high"))])
    model = create_model(ModelConfig(), profile(), api_key="synthetic-key")
    captured = {}
    async def go():
        async def handle(request):
            captured["body"] = json.loads(request.content)
            return httpx.Response(200, json={"id": "x", "object": "chat.completion", "created": 0, "model": "m",
                "choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": "ok"}}]})
        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
            model.http_client = client
            sdk = model.get_client()
            sdk._platform = "Linux"
            model.get_client = lambda: sdk
            await model.ainvoke([msg])
    asyncio.run(go())
    assert captured["body"]["messages"] == probe.stage_c_body(ModelConfig(), png)["messages"]


@pytest.mark.parametrize("content,finish,klass", [
    (None, "length", "cap_exhausted"),
    ("color=red; digit=7", "length", "not_stopped"),
    ("The square is red and the digit is 7.", "stop", "accepted_but_format_mismatch"),
    ("color=blue; digit=3", "stop", "wrong_answer"),
])
def test_stage_c_failure_classes(tmp_path, monkeypatch, content, finish, klass):
    _, record, calls = run_c(tmp_path, monkeypatch, lambda r: c_reply(content, finish))
    assert len(calls) == 1 and not record["success"] and record["failure_class"] == klass


def test_stage_c_case_and_whitespace_normalized_and_headroom_flag(tmp_path, monkeypatch):
    usage = {"prompt_tokens": 100, "completion_tokens": 500, "completion_tokens_details": {"reasoning_tokens": 480}}
    _, record, _ = run_c(tmp_path, monkeypatch, lambda r: c_reply("  Color=Red; Digit=7\n", usage=usage))
    assert record["success"] and record["low_reasoning_headroom"] is True


def test_stage_c_rejection_timeout_missing_key_and_cli(tmp_path, monkeypatch):
    err = {"error": {"message": f"unsupported field image_url.detail {KEY}"}}
    path, record, calls = run_c(tmp_path, monkeypatch, lambda r: httpx.Response(400, json=err))
    assert len(calls) == 1 and record["failure_class"] == "image_or_param_rejected" and KEY not in (path / "probe.json").read_text()
    def boom(request):
        raise httpx.ReadTimeout("slow", request=request)
    _, record, calls = run_c(tmp_path, monkeypatch, boom)
    assert len(calls) == 1 and record["failure_class"] == "timeout"
    _, record, calls = run_c(tmp_path, monkeypatch, lambda r: c_reply("x"), key=None)
    assert calls == [] and record["status"] == "setup_error"
    import sys
    from agent_readiness import cli
    monkeypatch.setattr(sys, "argv", ["readiness", "probe", "--stage", "c"])
    monkeypatch.setattr(cli, "load_repo_env", lambda: None)
    with pytest.raises(SystemExit) as exc:
        cli.main()
    assert "disabled" in str(exc.value)
