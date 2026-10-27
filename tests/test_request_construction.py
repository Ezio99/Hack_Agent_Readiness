"""Offline interception of the real Stage D request path (real runner, Chromium and storefront; mock model transport)."""
import json
import os
import subprocess
import httpx
import pytest
from openai import DefaultAsyncHttpxClient
from agent_readiness import runner
from agent_readiness.agent import ModelConfig, create_model
from agent_readiness.probe import STAGE_B_REASONING_EFFORT, _schema_digest, build_agent_output_schema, stage_b_body

pytestmark = pytest.mark.browser
SENTINEL = "sentinel-model-credential-0123456789-not-real"


def done_reply(n):
    out = {"evaluation_previous_goal": "n/a", "memory": "", "next_goal": "finish", "thinking": "t",
           "current_plan_item": 0, "plan_update": None,
           "action": [{"done": {"data": {"product_id": "X-0", "price_cents": 100, "available": True}}}]}
    return httpx.Response(200, headers={"x-request-id": f"mock-{n}"}, json={
        "id": "m", "object": "chat.completion", "created": 0, "model": "muse-spark-1.3",
        "choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": json.dumps(out)}}],
        "usage": {"prompt_tokens": 9000, "completion_tokens": 300, "total_tokens": 9300,
                  "completion_tokens_details": {"reasoning_tokens": 200}}})


async def mocked_live_run(tmp_path, monkeypatch):
    bodies = []
    def handler(request):
        bodies.append(json.loads(request.content))
        return done_reply(len(bodies))
    original = runner.create_model
    def make(config, effective):
        model = original(config, effective)  # real adapter construction with the key from the environment
        model.http_client = DefaultAsyncHttpxClient(transport=httpx.MockTransport(handler))
        sdk = model.get_client()
        sdk._platform = "Linux"  # avoid the SDK platform probe in the restricted sandbox
        model.get_client = lambda: sdk
        return model
    monkeypatch.setattr(runner, "create_model", make)
    path, record = await runner.run(mode="live", allow_model_calls=True, output=tmp_path, seed=0, kind="discovery",
                                    max_steps=5, timeout_seconds=120, max_model_requests=5)
    return path, record, bodies


async def test_stage_d_request_matches_stage_b_except_token_cap_and_messages(tmp_path, monkeypatch):
    monkeypatch.setenv("META_MODEL_API_KEY", SENTINEL)
    path, record, bodies = await mocked_live_run(tmp_path, monkeypatch)
    assert record["status"] == "completed" and len(bodies) == 1, record.get("errors")
    wire = bodies[0]
    schema, _ = build_agent_output_schema()
    stage_b = stage_b_body(ModelConfig(), schema)
    # Same parameters and the byte-identical strict response_format the successful Stage B request used.
    assert set(wire) == set(stage_b) == {"model", "messages", "response_format", "reasoning_effort", "max_completion_tokens"}
    assert wire["model"] == stage_b["model"] and wire["reasoning_effort"] == stage_b["reasoning_effort"] == STAGE_B_REASONING_EFFORT
    assert wire["response_format"] == stage_b["response_format"]
    assert _schema_digest(wire["response_format"]["json_schema"]["schema"]) == _schema_digest(schema)
    assert wire["response_format"]["json_schema"]["strict"] is True
    # The two intended differences: the v3 completion cap and the message structure.
    assert (wire["max_completion_tokens"], stage_b["max_completion_tokens"]) == (4096, 1024)
    roles = [m["role"] for m in wire["messages"]]
    assert roles == ["system", "user"]
    parts = wire["messages"][1]["content"]
    assert [p["type"] for p in parts] == ["text", "text", "image_url"] and parts[2]["image_url"]["detail"] == "high"
    assert len(wire["messages"][0]["content"]) > 20_000
    # Capture recorded the same facts at the HTTP layer.
    request_event = next(json.loads(l) for l in (path / "trace.jsonl").read_text().splitlines() if '"model_http_request"' in l)
    assert request_event["response_format"]["schema_sha256"] == _schema_digest(schema)[0]
    assert request_event["parameters"] == {"model": "muse-spark-1.3", "reasoning_effort": "low", "max_completion_tokens": 4096}
    assert request_event["timeout"]["read"] == 30 and request_event["url"] == "https://api.meta.ai/v1/chat/completions"
    assert record["http_captures"][0]["request_id"] == "mock-1" and record["http_captures"][0]["reasoning_tokens"] == 200
    assert record["browser_version"]  # recorded without depending on a completed observation


async def test_model_credential_never_reaches_any_spawned_process(tmp_path, monkeypatch):
    monkeypatch.setenv("META_MODEL_API_KEY", SENTINEL)
    spawned = []
    original = subprocess.Popen.__init__
    def spy(self, args, *a, **k):
        env = k.get("env")
        env = os.environ if env is None else env
        name = args[0] if isinstance(args, (list, tuple)) else args
        spawned.append((os.path.basename(str(name)), "META_MODEL_API_KEY" in env or any(SENTINEL in str(v) for v in env.values())))
        return original(self, args, *a, **k)
    monkeypatch.setattr(subprocess.Popen, "__init__", spy)
    _, record, _ = await mocked_live_run(tmp_path, monkeypatch)
    assert record["status"] == "completed"
    names = {n for n, _ in spawned}
    assert any("chrom" in n.lower() or "headless" in n.lower() for n in names), names  # the browser was observed
    assert any("node" in n.lower() for n in names), names  # and the Playwright driver
    assert "git" in names  # provenance lookup also ran
    assert [n for n, has_key in spawned if has_key] == [], spawned
    assert os.environ["META_MODEL_API_KEY"] == SENTINEL  # restored for the caller


async def test_one_step_one_request_replay_with_unparseable_output_makes_exactly_one_call(tmp_path, monkeypatch):
    """The diagnostic replay configuration: nothing is extracted or executed from a malformed response."""
    monkeypatch.setenv("META_MODEL_API_KEY", SENTINEL)
    calls = []
    prose = ("Found the Fern Home item, so I will open it " + SENTINEL + '. {"evaluation_previous_goal": "", "memory": "", '
             '"next_goal": "click index 174", "action": [{"click": {"index": 174}}]}')
    def handler(request):
        calls.append(request)
        return httpx.Response(200, headers={"x-request-id": "mock-r"}, json={
            "id": "m", "object": "chat.completion", "created": 0, "model": "muse-spark-1.3",
            "choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": prose}}],
            "usage": {"prompt_tokens": 9000, "completion_tokens": 500, "total_tokens": 9500,
                      "completion_tokens_details": {"reasoning_tokens": 400}}})
    original = runner.create_model
    def make(config, effective):
        model = original(config, effective)
        model.http_client = DefaultAsyncHttpxClient(transport=httpx.MockTransport(handler))
        sdk = model.get_client()
        sdk._platform = "Linux"
        model.get_client = lambda: sdk
        return model
    monkeypatch.setattr(runner, "create_model", make)
    path, record = await runner.run(mode="live", allow_model_calls=True, output=tmp_path, seed=0, kind="discovery",
                                    max_steps=1, timeout_seconds=120, max_model_requests=1)
    assert len(calls) == 1 and record["model_request_count"] == 1
    assert record["status"] == "model_output_error" and record["stop_reason"] == "model_output_error:malformed_json"
    assert record["action_count"] == 1 and record["answer"] is None and record["evaluation"]["passed"] is False
    trace = [json.loads(l) for l in (path / "trace.jsonl").read_text().splitlines()]
    executed = [e for e in trace if e["kind"] == "step_result"]
    assert all(r["model_output"] is None for r in (e["result"] for e in executed))  # nothing was parsed or executed
    saved = json.loads((path / "model-response-01.json").read_text())
    assert saved["finish_reason"] == "stop" and saved["request_id"] == "mock-r" and saved["reasoning_tokens"] == 400
    assert saved["content_analysis"]["embedded_json"]["offset"] > 0 and saved["output_error"]["subtype"] == "malformed_json"
    assert record["usage"][0]["completion_tokens_details"]["reasoning_tokens"] == 400
    assert SENTINEL not in "".join(p.read_text() for p in path.glob("*.json*"))
