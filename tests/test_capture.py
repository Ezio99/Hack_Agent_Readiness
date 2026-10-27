"""Response capture before Browser Use parses model output, and the model_output_error classification."""
import json
import httpx
import pytest
from openai import DefaultAsyncHttpxClient
from agent_readiness import agent as adapter
from agent_readiness.agent import (ModelCallError, ModelConfig, RecordingModel, classify_outcome, create_model,
                                   profile, prepare_browser_environment)
from agent_readiness.capture import analyze_content, attach_capture, request_summary
from agent_readiness.recorder import Recorder

KEY = "sk-capture-test-not-real-0123456789"
USAGE = {"prompt_tokens": 8000, "completion_tokens": 900, "total_tokens": 8900,
         "completion_tokens_details": {"reasoning_tokens": 850}, "prompt_tokens_details": {"cached_tokens": 0}}


def chat(content, finish="stop", usage=USAGE, status=200, headers=None):
    body = {"id": "x", "object": "chat.completion", "created": 0, "model": "muse-spark-1.3",
            "choices": [{"index": 0, "finish_reason": finish,
                         "message": {"role": "assistant", "content": content, "refusal": None}}], "usage": usage}
    return httpx.Response(status, json=body, headers={"x-request-id": "req-123", **(headers or {})})


def good_output():
    return json.dumps({"evaluation_previous_goal": "", "memory": "", "next_goal": "",
                       "action": [{"done": {"data": {"product_id": "P", "price_cents": 1, "available": True}}}]})


async def invoke(tmp_path, handler, *, content_messages=None):
    """Real ChatOpenAI + real AgentOutput schema; only the transport is replaced."""
    from agent_readiness.probe import build_agent_output_schema
    from browser_use.llm.messages import UserMessage
    prepare_browser_environment()
    _, output_model = build_agent_output_schema()
    model = create_model(ModelConfig(), profile(), api_key=KEY)
    calls = []
    def counted(request):
        calls.append(request)
        return handler(request)
    model.http_client = DefaultAsyncHttpxClient(transport=httpx.MockTransport(counted))
    recorder = Recorder(tmp_path, (KEY,))
    capture = attach_capture(model, recorder)
    wrapped = RecordingModel(model, recorder, profile(), capture=capture)
    sdk = model.get_client()
    sdk._platform = "Linux"
    model.get_client = lambda: sdk
    error = None
    try:
        result = await wrapped.ainvoke(content_messages or [UserMessage(content="hello")], output_format=output_model)
    except ModelCallError as exc:
        result, error = None, exc
    return wrapped, capture, recorder, result, error, calls


def trace(recorder):
    return [json.loads(line) for line in (recorder.path / "trace.jsonl").read_text().splitlines()]


STAGE_D_LIKE = (f"Found the Fern Home item that matches the constraints, so I will open it (note {KEY}). "
                '{"evaluation_previous_goal": "ok", "memory": "", "next_goal": "click its link index 174", "action": []}')


async def test_prose_before_json_is_captured_and_classified(tmp_path):
    wrapped, capture, recorder, result, error, calls = await invoke(tmp_path, lambda r: chat(STAGE_D_LIKE))
    assert result is None and error is not None and len(calls) == 1
    record = capture.records[0]
    assert record["http_status"] == 200 and record["request_id"] == "req-123" and record["finish_reason"] == "stop"
    assert record["reasoning_tokens"] == 850 and record["completion_tokens"] == 900 and record["prompt_tokens"] == 8000
    analysis = record["content_analysis"]
    assert analysis["kind"] == "non_json" and not analysis["starts_with_brace"] and analysis["ends_with_brace"]
    assert analysis["embedded_json"]["offset"] > 0 and analysis["embedded_json"]["trailing_chars"] == 0  # prose, then valid JSON
    assert wrapped.output_errors[0]["subtype"] == "malformed_json" and wrapped.last_error_class == "model_output_error"
    assert wrapped.usages[-1]["completion_tokens_details"]["reasoning_tokens"] == 850
    assert wrapped.usages[-1]["source"] == "http_capture_after_error"
    saved = json.loads((recorder.path / "model-response-01.json").read_text())
    assert saved["content"].startswith("Found the Fern Home item") and saved["output_error"]["subtype"] == "malformed_json"
    assert KEY not in (recorder.path / "model-response-01.json").read_text() and KEY not in (recorder.path / "trace.jsonl").read_text()
    kinds = [e["kind"] for e in trace(recorder)]
    assert kinds.index("model_http_response") < kinds.index("model_output_error") < kinds.index("model_error")
    assert classify_outcome(wrapped, False, 1, 5) == ("model_output_error", "model_output_error:malformed_json")


@pytest.mark.parametrize("finish,subtype", [("length", "length_without_content"), ("stop", "null_content")])
async def test_null_content(tmp_path, finish, subtype):
    wrapped, capture, recorder, _, error, _ = await invoke(tmp_path, lambda r: chat(None, finish))
    assert error is not None and capture.records[0]["content_analysis"] == {"kind": "null"}
    assert wrapped.output_errors[0]["subtype"] == subtype and wrapped.output_errors[0]["finish_reason"] == finish
    assert wrapped.output_errors[0]["reasoning_tokens"] == 850
    assert classify_outcome(wrapped, False, 1, 5)[0] == "model_output_error"


async def test_valid_json_that_fails_agent_output_validation(tmp_path):
    secret_value = "SECRET-INPUT-VALUE-SHOULD-NOT-BE-LOGGED"
    wrapped, capture, recorder, _, error, _ = await invoke(tmp_path, lambda r: chat(json.dumps({"action": secret_value})))
    assert error is not None and capture.records[0]["content_analysis"]["kind"] == "json"
    out = wrapped.output_errors[0]
    assert out["subtype"] == "schema_validation" and out["errors"] and all("loc" in e and "type" in e for e in out["errors"])
    assert secret_value not in json.dumps(out)  # error summary carries locations/types, not input values
    assert classify_outcome(wrapped, False, 1, 5) == ("model_output_error", "model_output_error:schema_validation")


async def test_http_errors_stay_infrastructure_and_are_not_retried(tmp_path):
    wrapped, capture, recorder, _, error, calls = await invoke(
        tmp_path, lambda r: httpx.Response(500, json={"error": {"message": f"boom {KEY}"}}, headers={"x-request-id": "r5"}))
    assert len(calls) == 1 and error is not None  # SDK retries are off
    record = capture.records[0]
    assert record["http_status"] == 500 and record["request_id"] == "r5" and "error_body" in record
    assert wrapped.output_errors == [] and classify_outcome(wrapped, False, 1, 5)[0] == "infrastructure_error"
    assert KEY not in (recorder.path / "model-response-01.json").read_text()


async def test_success_is_captured_and_not_counted_as_error(tmp_path):
    wrapped, capture, recorder, result, error, _ = await invoke(tmp_path, lambda r: chat(good_output()))
    assert error is None and result is not None and wrapped.output_errors == []
    assert capture.records[0]["content_analysis"]["kind"] == "json" and capture.take() == []
    assert classify_outcome(wrapped, True, 1, 5) == ("completed", "agent_done")


async def test_capture_is_bounded(tmp_path):
    wrapped, capture, recorder, _, error, _ = await invoke(tmp_path, lambda r: chat("x" * 100_000))
    record = capture.records[0]
    assert len(record["content"]) == 20_000 and record["content_truncated"] and record["content_analysis"]["chars"] == 100_000
    assert wrapped.output_errors[0]["subtype"] == "unclassified_truncated_capture"
    assert (recorder.path / "model-response-01.json").stat().st_size < 40_000


async def test_request_event_records_structure_without_text_or_credentials(tmp_path):
    _, capture, recorder, _, _, _ = await invoke(tmp_path, lambda r: chat(good_output()))
    event = next(e for e in trace(recorder) if e["kind"] == "model_http_request")
    assert event["model"] == "muse-spark-1.3" and event["url"] == "https://api.meta.ai/v1/chat/completions"
    assert event["parameters"]["reasoning_effort"] == "low" and event["parameters"]["max_completion_tokens"] == 4096
    assert "temperature" not in event["parameters"] and "frequency_penalty" not in event["parameters"]
    assert event["response_format"]["strict"] is True and event["response_format"]["name"] == "agent_output"
    assert len(event["response_format"]["schema_sha256"]) == 64 and event["timeout"]["read"] == 30
    assert event["messages"] == [{"role": "user", "parts": [{"type": "text", "chars": 5}]}]
    assert KEY not in (recorder.path / "trace.jsonl").read_text()


def test_attach_capture_creates_a_default_client_when_none_and_skips_other_models(tmp_path):
    class Plain:
        http_client = None
    plain = Plain()
    capture = attach_capture(plain, Recorder(tmp_path))
    assert capture is not None and plain.http_client.event_hooks["response"] and plain.http_client.follow_redirects
    assert attach_capture(object(), Recorder(tmp_path)) is None


def test_analyze_content_and_request_summary_helpers():
    assert analyze_content("{}")["kind"] == "json" and analyze_content(None)["kind"] == "null"
    assert analyze_content("prose {not json")["embedded_json"] is None
    assert analyze_content('x {"a": 1} y')["embedded_json"] == {"offset": 2, "chars": 8, "trailing_chars": 2, "is_object": True}
    body = {"model": "m", "messages": [{"role": "system", "content": "abc"},
            {"role": "user", "content": [{"type": "text", "text": "hi"}, {"type": "image_url", "image_url": {"url": "data:image/png;base64,AAAA", "detail": "high"}}]}]}
    summary = request_summary(body)
    assert summary["messages"][1]["parts"][1] == {"type": "image_url", "detail": "high", "url_chars": 26, "data_url": True}
    assert "AAAA" not in json.dumps(summary)


@pytest.mark.parametrize("limit,done,error_class,expected", [
    (True, False, None, "request_limit"), (False, True, "model_output_error", "completed"),
    (False, False, "infrastructure_error", "infrastructure_error"), (False, False, None, "step_limit")])
def test_classify_outcome_precedence(limit, done, error_class, expected):
    class W:
        limit_reached, last_error, last_error_class = limit, ("X" if error_class else None), error_class
        output_errors = [{"subtype": "null_content"}]
    status, reason = classify_outcome(W, done, 5, 5)
    assert status == expected
