import base64
import json
import httpx
import pytest
from agent_readiness.agent import (ModelConfig, RecordingModel, create_agent, create_model,
                                   prepare_browser_environment, profile)
from agent_readiness.contracts import Answer
from agent_readiness.recorder import Recorder
from agent_readiness.tasks import generate

PNG = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/l9sAAAAASUVORK5CYII="


async def test_meta_adapter_wire_contract_with_synthetic_response(tmp_path):
    """Real Browser Use serializer and SDK; MockTransport prevents all network."""
    prepare_browser_environment()
    from browser_use.llm.messages import SystemMessage, UserMessage, ContentPartTextParam, ContentPartImageParam, ImageURL
    requests = []

    async def handle(request):
        requests.append(request)
        assert str(request.url) == "https://api.meta.ai/v1/chat/completions"
        assert request.headers["authorization"] == "Bearer synthetic-key"
        body = json.loads(request.content)
        assert body["model"] == "muse-spark-1.3"
        assert body["response_format"]["type"] == "json_schema"
        assert body["response_format"]["json_schema"]["strict"] is True
        assert "temperature" not in body and "frequency_penalty" not in body
        assert "reasoning_effort" not in body  # Do not force an undocumented adapter default.
        parts = body["messages"][1]["content"]
        assert any(p["type"] == "image_url" and p["image_url"]["url"].startswith("data:image/png;base64,") for p in parts)
        return httpx.Response(200, json={"id": "synthetic", "object": "chat.completion", "created": 0,
            "model": "muse-spark-1.3", "choices": [{"index": 0, "finish_reason": "stop",
            "message": {"role": "assistant", "content": json.dumps({"product_id": "FAKE", "price_cents": 100, "available": True})}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        model = create_model(ModelConfig(), http_client=client, api_key="synthetic-key")
        # Avoid the SDK's asynchronous platform probe in this restricted sandbox.
        # The request serializer, schema, transport and response parser remain real.
        sdk = model.get_client()
        sdk._platform = "Linux"
        model.get_client = lambda: sdk
        recorder = Recorder(tmp_path, ("synthetic-key",))
        wrapped = RecordingModel(model, recorder)
        response = await wrapped.ainvoke([
            SystemMessage(content="Return the requested fields."),
            UserMessage(content=[ContentPartTextParam(text="Synthetic DOM. synthetic-key"),
                ContentPartImageParam(image_url=ImageURL(url=f"data:image/png;base64,{PNG}"))])], output_format=Answer)
        assert response.completion.product_id == "FAKE"
        assert len(requests) == 1 and wrapped.usages[0]["total_tokens"] == 15
        trace = (recorder.path / "trace.jsonl").read_text()
        assert "synthetic-key" not in trace and "[REDACTED]" in trace
        assert PNG not in trace
        assert list(recorder.path.glob("model-input-*.png"))[0].read_bytes() == base64.b64decode(PNG)


def test_profile_and_tools_are_fixed_and_truth_is_not_in_prompt(tmp_path):
    prepare_browser_environment()
    from browser_use import Browser
    p = profile()
    browser = Browser(headless=True, enable_default_extensions=False)
    model = create_model(ModelConfig(), api_key="synthetic")
    task = generate().public
    agent = create_agent(task, "http://127.0.0.1:8000/", model, browser, Recorder(tmp_path))
    assert agent.settings.use_vision is True
    assert agent.settings.vision_detail_level == "high"
    assert agent.settings.use_judge is False
    actions = set(agent.tools.registry.registry.actions)
    assert actions <= set(p["allowed_tools"])
    assert {"navigate", "click", "input", "select_dropdown", "done"} <= actions
    assert not {"evaluate", "read_file", "write_file", "extract", "search"} & actions
    assert "expected_id" not in agent.task
    assert p["observation_mode"] == "dom+screenshot"


def test_missing_credential(monkeypatch):
    monkeypatch.delenv("MODEL_API_KEY", raising=False)
    with pytest.raises(ValueError, match="Missing credential"):
        create_model(ModelConfig())


async def test_full_agent_schema_matches_documented_meta_strict_subset(tmp_path):
    prepare_browser_environment()
    from browser_use import Browser
    from browser_use.llm.messages import UserMessage
    from browser_use.llm.schema import SchemaOptimizer
    model = create_model(ModelConfig(), api_key="synthetic-key")
    agent = create_agent(generate().public, "http://127.0.0.1:8000/", model,
                         Browser(headless=True, enable_default_extensions=False), Recorder(tmp_path))
    schema = SchemaOptimizer.create_optimized_json_schema(agent.AgentOutput, remove_min_items=True)
    assert schema["type"] == "object"
    assert not {"anyOf", "oneOf", "allOf", "enum", "not"} & schema.keys()

    def check(node):
        if isinstance(node, dict):
            assert not {"allOf", "oneOf", "min_items"} & node.keys()
            if node.get("type") == "object":
                assert node["additionalProperties"] is False
                assert set(node.get("required", [])) == set(node.get("properties", {}))
            for value in node.values():
                check(value)
        elif isinstance(node, list):
            for value in node:
                check(value)
    check(schema)
    synthetic = {"evaluation_previous_goal": "Synthetic only", "memory": "", "next_goal": "Finish",
                 "action": [{"done": {"success": True, "data": {"product_id": "FAKE", "price_cents": 100, "available": False}}}]}

    async def handle(request):
        assert json.loads(request.content)["response_format"]["json_schema"]["schema"] == schema
        return httpx.Response(200, json={"id": "synthetic", "object": "chat.completion", "created": 0,
            "model": "muse-spark-1.3", "choices": [{"index": 0, "finish_reason": "stop",
            "message": {"role": "assistant", "content": json.dumps(synthetic)}}]})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        model.http_client = client
        sdk = model.get_client()
        sdk._platform = "Linux"
        model.get_client = lambda: sdk
        result = await model.ainvoke([UserMessage(content="Synthetic schema contract test")], output_format=agent.AgentOutput)
        assert result.completion.action[0].model_dump()["done"]["data"]["product_id"] == "FAKE"
        assert result.usage is None


def test_browser_launch_flags_do_not_depend_on_container_detection(tmp_path, monkeypatch):
    prepare_browser_environment()
    import browser_use.config as config_module
    from browser_use.browser.profile import BrowserProfile
    from agent_readiness.agent import browser_options
    monkeypatch.delenv("IN_DOCKER", raising=False)
    for in_container in [True, False]:
        monkeypatch.setattr(config_module, "is_running_in_docker", lambda: in_container)
        options = browser_options("http://127.0.0.1:8000/", "/unused/chromium")
        options["user_data_dir"] = str(tmp_path / "profile")
        launch = BrowserProfile(**options)
        assert launch.chromium_sandbox is False
        assert "--no-sandbox" in launch.get_args()
        assert launch.use_cloud is False
