"""natural-shopping-v3: explicit low reasoning effort and a 4,096-token cap; v2 preserved."""
import hashlib
import json
from contextlib import asynccontextmanager
import httpx
import pytest
from agent_readiness import agent as adapter, runner
from agent_readiness.agent import ModelConfig, PROFILE_DIR, create_model, profile

V2_FILE_SHA256 = "c3412b450d72277663e6e50d467834a8e32ee305f58c32b798b99d2275c9c943"
V2, V3 = "natural-shopping-v2", "natural-shopping-v3"


def test_v2_file_is_preserved_byte_for_byte():
    assert hashlib.sha256((PROFILE_DIR / "natural-v2.json").read_bytes()).hexdigest() == V2_FILE_SHA256
    v2 = profile(V2)
    assert v2["id"] == V2 and v2["max_completion_tokens"] == 2048 and "reasoning_effort" not in v2


def test_v3_differs_from_v2_only_in_id_reasoning_and_completion_cap():
    v2, v3 = profile(V2), profile(V3)
    changed = {k for k in v2.keys() | v3.keys() if v2.get(k, "<absent>") != v3.get(k, "<absent>")}
    assert changed == {"id", "max_completion_tokens", "reasoning_effort"}
    assert v3["id"] == V3 and v3["reasoning_effort"] == "low" and v3["max_completion_tokens"] == 4096
    # Unchanged on purpose: observation method, tools, and request/step/time caps.
    for key in ("observation_mode", "use_vision", "vision_detail_level", "viewport", "allowed_tools", "instructions",
                "max_steps", "timeout_seconds", "max_model_requests", "max_actions_per_step",
                "model_timeout_seconds", "step_timeout_seconds", "chromium_sandbox"):
        assert v3[key] == v2[key]
    assert profile() == v3 and profile(None) == v3
    with pytest.raises(ValueError):
        profile("natural-shopping-v9")


def capture_body(model):
    import asyncio
    from browser_use.llm.messages import UserMessage
    from agent_readiness.probe import build_agent_output_schema, stage_c_body
    schema, output_model = build_agent_output_schema()
    captured = {}
    async def go():
        async def handle(request):
            captured["body"] = json.loads(request.content)
            return httpx.Response(200, json={"id": "x", "object": "chat.completion", "created": 0, "model": "m",
                "choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": json.dumps(
                    {"evaluation_previous_goal": "", "memory": "", "next_goal": "",
                     "action": [{"done": {"data": {"product_id": "P", "price_cents": 1, "available": True}}}]})}}]})
        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
            model.http_client = client
            sdk = model.get_client()
            sdk._platform = "Linux"
            model.get_client = lambda: sdk
            content = stage_c_body(ModelConfig(), b"\x89PNG-synthetic")["messages"][0]["content"]
            from browser_use.llm.messages import ContentPartTextParam, ContentPartImageParam, ImageURL
            parts = [ContentPartTextParam(text="t"), ContentPartImageParam(image_url=ImageURL(
                url=content[1]["image_url"]["url"], media_type="image/png", detail="high"))]
            await model.ainvoke([UserMessage(content=parts)], output_format=output_model)
    asyncio.run(go())
    return captured["body"], schema


def test_v3_reaches_the_wire_through_the_real_adapter_with_schema_and_image():
    body, schema = capture_body(create_model(ModelConfig(), profile(V3), api_key="synthetic-key"))
    assert body["reasoning_effort"] == "low" and body["max_completion_tokens"] == 4096
    assert "temperature" not in body and "frequency_penalty" not in body
    assert body["response_format"]["json_schema"]["strict"] is True
    assert body["response_format"]["json_schema"]["schema"] == schema
    assert any(p["type"] == "image_url" and p["image_url"]["detail"] == "high" for p in body["messages"][0]["content"])


def test_v2_wire_behaviour_is_unchanged():
    body, _ = capture_body(create_model(ModelConfig(), profile(V2), api_key="synthetic-key"))
    assert "reasoning_effort" not in body and body["max_completion_tokens"] == 2048


def test_reasoning_effort_is_sent_only_to_the_meta_provider():
    other = create_model(ModelConfig(provider="openai-compatible", base_url="https://example.test/v1"), profile(V3), api_key="k")
    body, _ = capture_body(other)
    assert "reasoning_effort" not in body and body["max_completion_tokens"] == 4096


@pytest.mark.parametrize("value", ["none", "max", "xhigh", "", None, 5, "LOW"])
def test_invalid_reasoning_effort_is_rejected_before_any_model_is_built(tmp_path, monkeypatch, value):
    bad = {**profile(V3), "reasoning_effort": value}
    with pytest.raises(ValueError, match="reasoning_effort"):
        create_model(ModelConfig(), bad, api_key="k")
    def must_not_build(*args, **kwargs):
        raise AssertionError("model constructed despite invalid reasoning_effort")
    monkeypatch.setattr(runner, "create_model", must_not_build)
    import asyncio
    _, record = asyncio.run(runner.run(mode="live", allow_model_calls=True, output=tmp_path,
                                       profile_overrides={"reasoning_effort": value}))
    assert record["status"] == "setup_error" and "reasoning_effort" in record["errors"][0]
    assert record["model_request_count"] == 0


@asynccontextmanager
async def _fake_target(url):
    yield "http://127.0.0.1:8000/"


async def test_runner_records_v3_effective_values_and_distinct_hashes(tmp_path, monkeypatch):
    async def stop(*args, **kwargs):
        raise RuntimeError("stop after setup")
    monkeypatch.setattr(runner, "target", _fake_target)
    monkeypatch.setattr(runner, "attempt", stop)
    monkeypatch.setattr(runner, "create_model", lambda config, effective: object())
    records = {}
    for pid in (V2, V3):
        _, records[pid] = await runner.run(mode="live", allow_model_calls=True, output=tmp_path, profile_id=pid)
    v3 = records[V3]
    assert v3["profile"]["id"] == V3 and v3["profile"]["reasoning_effort"] == "low"
    assert v3["model_parameters"]["reasoning_effort"] == "low" and v3["model_parameters"]["max_completion_tokens"] == 4096
    assert records[V2]["model_parameters"]["reasoning_effort"] is None
    assert v3["profile_hash"] != records[V2]["profile_hash"] and v3["configuration_hash"] != records[V2]["configuration_hash"]
    assert v3["limits"] == records[V2]["limits"] == {"max_steps": 10, "timeout_seconds": 120, "max_model_requests": 10}


def test_timeout_budget_invariants_and_documented_latency_risk():
    p = profile(V3)
    # Per-request < per-step < whole-run budgets, so one slow model call cannot outlast a step or the run.
    assert p["model_timeout_seconds"] < p["step_timeout_seconds"] < p["timeout_seconds"]
    # Observed (Stage A-C) marginal generation ~3.8 ms/token => 4,096 tokens ~ 16.6 s: inside the 30 s model
    # timeout only by ~1.8x and extrapolated from <=994 observed tokens. Record the ratio so a change is deliberate.
    estimated_full_generation_seconds = 1.0 + 0.0038 * p["max_completion_tokens"]
    assert 30 / estimated_full_generation_seconds > 1.5
    # Whole-run budget must exceed one worst-case model call plus the step overhead for at least 2 steps.
    assert p["timeout_seconds"] >= 2 * estimated_full_generation_seconds
