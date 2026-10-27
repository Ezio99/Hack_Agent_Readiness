"""Offline configuration/budget integration. No real browser or provider requests."""
from contextlib import asynccontextmanager
from copy import deepcopy
import hashlib
import json
from types import SimpleNamespace
import asyncio
import httpx
import pytest
from agent_readiness import agent as adapter, runner
from agent_readiness.agent import ModelConfig, RecordingModel, ModelRequestLimitReached, ModelCallError
from agent_readiness.contracts import Answer
from agent_readiness.recorder import Recorder
from .test_benchmark import answer_for
from agent_readiness.tasks import generate


async def test_one_effective_configuration_reaches_sdk_browser_agent_and_artifacts(tmp_path, monkeypatch):
    adapter.prepare_browser_environment()
    import browser_use
    import playwright.async_api
    from browser_use.llm.messages import UserMessage
    defaults = adapter.profile()
    seen = {"profile_loads": 0}
    overrides = dict(max_steps=99, timeout_seconds=99, max_model_requests=99,
                     viewport={"width": 992, "height": 640}, max_actions_per_step=1,
                     max_completion_tokens=37, model_timeout_seconds=7, step_timeout_seconds=9,
                     vision_detail_level="low", instructions="Use this overridden instruction.",
                     allowed_tools=["navigate", "done"])
    expected = {**defaults, **deepcopy(overrides), "max_steps": 2,
                "timeout_seconds": 12, "max_model_requests": 3}

    def load_once():
        seen["profile_loads"] += 1
        return deepcopy(defaults)

    def no_defaults():
        raise AssertionError("A component reloaded defaults instead of using effective settings")

    class FakeBrowser:
        def __init__(self, **options):
            seen["browser"] = options
        async def kill(self):
            seen["closed"] = True

    final = answer_for(generate())
    history = SimpleNamespace(history=[], final_result=lambda: json.dumps(final),
                              is_done=lambda: True, errors=lambda: [], model_dump=lambda: {})

    class FakeAgent:
        def __init__(self, **options):
            seen["agent"] = options
            self.history = history
            self.llm = options["llm"]
        async def run(self, *, max_steps, on_step_end):
            seen["steps"] = max_steps
            await self.llm.ainvoke([UserMessage(content="Offline wiring fixture")], output_format=Answer)
            return history

    @asynccontextmanager
    async def fake_playwright():
        yield SimpleNamespace(chromium=SimpleNamespace(executable_path="/mock/chromium"))

    @asynccontextmanager
    async def fake_target(url):
        yield "http://127.0.0.1:8000/"

    async def respond(request):
        seen["wire"] = json.loads(request.content)
        return httpx.Response(200, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": "muse-spark-1.3", "choices": [{"index": 0, "finish_reason": "stop",
            "message": {"role": "assistant", "content": json.dumps(final)}}]})

    monkeypatch.setenv("MODEL_API_KEY", "offline-fixture-key")
    monkeypatch.setattr(runner, "profile", load_once)
    monkeypatch.setattr(adapter, "profile", no_defaults)
    monkeypatch.setattr(browser_use, "Browser", FakeBrowser)
    monkeypatch.setattr(browser_use, "Agent", FakeAgent)
    monkeypatch.setattr(playwright.async_api, "async_playwright", fake_playwright)
    monkeypatch.setattr(runner, "target", fake_target)
    original_create = adapter.create_model
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        def offline_model(config, effective):
            seen["effective"] = effective
            model = original_create(config, effective, http_client=client)
            sdk = model.get_client()
            sdk._platform = "Linux"  # Avoid the SDK's unrelated async platform probe.
            model.get_client = lambda: sdk
            seen["model"] = model
            return model
        monkeypatch.setattr(runner, "create_model", offline_model)
        path, record = await runner.run(mode="live", allow_model_calls=True, output=tmp_path,
            max_steps=2, timeout_seconds=12, max_model_requests=3, profile_overrides=overrides)
    assert record["status"] == "completed", record.get("errors")
    assert seen["profile_loads"] == 1 and seen["effective"] == expected
    assert seen["steps"] == 2 and seen["closed"]
    assert seen["model"].timeout == 7 and seen["model"].max_retries == 0
    assert seen["wire"]["max_completion_tokens"] == 37
    assert seen["browser"]["viewport"] == expected["viewport"]
    assert seen["browser"]["chromium_sandbox"] == expected["chromium_sandbox"]
    for name, value in {"max_actions_per_step": 1, "llm_timeout": 7, "step_timeout": 9,
                        "vision_detail_level": "low", "use_vision": True,
                        "extend_system_message": expected["instructions"]}.items():
        assert seen["agent"][name] == value
    assert set(seen["agent"]["tools"].registry.registry.actions) == {"navigate", "done"}
    saved = json.loads((path / "run.json").read_text())
    assert saved["profile"] == expected
    assert saved["profile_hash"] == hashlib.sha256(json.dumps(expected, sort_keys=True).encode()).hexdigest()
    assert saved["configuration_hash"] == hashlib.sha256(json.dumps({"profile": expected,
        "model": saved["model"], "model_parameters": saved["model_parameters"]}, sort_keys=True).encode()).hexdigest()
    assert saved["limits"] == {"max_steps": 2, "timeout_seconds": 12, "max_model_requests": 3}
    assert saved["model_request_count"] == 1 and saved["usage"] is None
    assert "offline-fixture-key" not in (path / "trace.jsonl").read_text()
    assert defaults == adapter.json.loads(adapter.PROFILE_PATH.read_text())


class FakeModel:
    model = name = "offline-fixture"
    provider = "offline"
    api_key = "adapter-only-fixture-key"
    def __init__(self, fail=False):
        self.calls = 0
        self.fail = fail
    async def ainvoke(self, *args, **kwargs):
        self.calls += 1
        if self.fail:
            raise RuntimeError("Authorization: Bearer unknown-error-token; " + self.api_key)
        await asyncio.sleep(0)
        return SimpleNamespace(completion="offline response", usage=None, stop_reason="stop")


async def test_request_cap_blocks_before_provider_and_counts_failed_calls(tmp_path):
    effective = adapter.profile()
    effective["max_model_requests"] = 2
    inner = FakeModel(fail=True)
    recorder = Recorder(tmp_path)
    wrapped = RecordingModel(inner, recorder, effective)
    for _ in range(2):
        with pytest.raises(ModelCallError) as error:
            await wrapped.ainvoke([])
        assert inner.api_key not in str(error.value)
        assert "unknown-error-token" not in str(error.value)
    for _ in range(3):  # Framework retries cannot exceed the cap.
        with pytest.raises(ModelRequestLimitReached):
            await wrapped.ainvoke([])
    assert inner.calls == wrapped.request_count == 2 and wrapped.limit_reached
    trace = [json.loads(line) for line in (recorder.path / "trace.jsonl").read_text().splitlines()]
    assert sum(e["kind"] == "model_request" for e in trace) == 2
    assert sum(e["kind"] == "model_error" for e in trace) == 2
    assert inner.api_key not in json.dumps(trace) and "unknown-error-token" not in json.dumps(trace)


async def test_concurrent_invocations_share_one_request_cap(tmp_path):
    effective = adapter.profile()
    effective["max_model_requests"] = 1
    inner = FakeModel()
    wrapped = RecordingModel(inner, Recorder(tmp_path), effective)
    results = await asyncio.gather(*(wrapped.ainvoke([]) for _ in range(4)), return_exceptions=True)
    assert inner.calls == wrapped.request_count == 1
    assert sum(isinstance(r, ModelRequestLimitReached) for r in results) == 3


async def test_runner_records_budget_exhaustion_and_actual_count(tmp_path, monkeypatch):
    @asynccontextmanager
    async def fake_target(url):
        yield "http://127.0.0.1:8000/"
    inner = FakeModel()
    async def limited_attempt(public, url, model, recorder, effective):
        wrapped = RecordingModel(model, recorder, effective)
        for _ in range(3):
            await wrapped.ainvoke([])
    monkeypatch.setattr(runner, "target", fake_target)
    monkeypatch.setattr(runner, "create_model", lambda config, effective: inner)
    monkeypatch.setattr(runner, "attempt", limited_attempt)
    path, record = await runner.run(mode="live", allow_model_calls=True, output=tmp_path, max_model_requests=2)
    assert record["status"] == "request_limit" and record["stop_reason"] == "model_request_limit"
    assert record["model_request_count"] == inner.calls == 2
    assert record["limits"]["max_model_requests"] == 2 and record["evaluation"] is None
    assert json.loads((path / "run.json").read_text())["model_request_count"] == 2


async def test_runner_retains_request_count_on_timeout(tmp_path, monkeypatch):
    @asynccontextmanager
    async def fake_target(url):
        yield "http://127.0.0.1:8000/"
    inner = FakeModel()
    async def interrupted(public, url, model, recorder, effective):
        await RecordingModel(model, recorder, effective).ainvoke([])
        await asyncio.sleep(1)
    monkeypatch.setattr(runner, "target", fake_target)
    monkeypatch.setattr(runner, "create_model", lambda config, effective: inner)
    monkeypatch.setattr(runner, "attempt", interrupted)
    _, record = await runner.run(mode="live", allow_model_calls=True, output=tmp_path, timeout_seconds=0.05)
    assert record["status"] == "timeout" and record["model_request_count"] == inner.calls == 1


@pytest.mark.parametrize("override", [{"max_model_requests": 0}, {"max_model_requests": -1},
    {"max_model_requests": True}, {"max_steps": 1.5}, {"timeout_seconds": float("nan")},
    {"timeout_seconds": float("inf")}, {"max_completion_tokens": 0}])
async def test_invalid_budget_never_constructs_model(tmp_path, monkeypatch, override):
    def forbidden(*args):
        raise AssertionError("Invalid configuration must not reach model setup")
    monkeypatch.setattr(runner, "create_model", forbidden)
    _, record = await runner.run(mode="live", allow_model_calls=True, output=tmp_path, profile_overrides=override)
    assert record["status"] == "setup_error" and record["model_request_count"] == 0


def test_real_agent_consumes_overridden_settings(tmp_path):
    adapter.prepare_browser_environment()
    from browser_use import Browser
    effective = adapter.profile()
    effective.update(max_actions_per_step=1, model_timeout_seconds=7, step_timeout_seconds=13,
                     vision_detail_level="low", instructions="Unique override instruction.")
    model = adapter.create_model(ModelConfig(), effective, api_key="offline-fixture-key")
    agent = adapter.create_agent(generate().public, "http://127.0.0.1:8000/", model,
        Browser(headless=True, enable_default_extensions=False), Recorder(tmp_path), effective)
    assert agent.settings.max_actions_per_step == 1
    assert agent.settings.llm_timeout == 7 and agent.settings.step_timeout == 13
    assert agent.settings.vision_detail_level == "low" and agent.settings.use_vision
    assert effective["instructions"] in agent.message_manager.system_prompt.text
    assert agent.settings.final_response_after_failure is False


async def test_provider_failure_is_redacted_in_every_run_artifact(tmp_path, monkeypatch):
    @asynccontextmanager
    async def fake_target(url):
        yield "http://127.0.0.1:8000/"
    inner = FakeModel(fail=True)
    async def fail(public, url, model, recorder, effective):
        await RecordingModel(model, recorder, effective).ainvoke([])
    monkeypatch.setenv("MODEL_API_KEY", inner.api_key)
    monkeypatch.setattr(runner, "target", fake_target)
    monkeypatch.setattr(runner, "create_model", lambda config, effective: inner)
    monkeypatch.setattr(runner, "attempt", fail)
    path, record = await runner.run(mode="live", allow_model_calls=True, output=tmp_path)
    assert record["status"] == "infrastructure_error" and record["model_request_count"] == 1
    for file in path.iterdir():
        text = file.read_text()
        assert inner.api_key not in text and "unknown-error-token" not in text
    assert "[REDACTED]" in (path / "summary.md").read_text()


def test_cli_forwards_all_budget_overrides_without_authorizing_calls(monkeypatch, tmp_path):
    from agent_readiness import cli
    captured = {}
    async def fake_run(**kwargs):
        captured.update(kwargs)
        return tmp_path, {"status": "setup_error", "evaluation": None, "errors": ["Model calls disabled"]}
    monkeypatch.setattr(cli, "run", fake_run)
    monkeypatch.setattr("sys.argv", ["readiness", "run", "--max-steps", "4", "--timeout", "20",
                                     "--max-model-requests", "2"])
    with pytest.raises(SystemExit) as exit_code:
        cli.main()
    assert exit_code.value.code == 1
    assert captured["max_steps"] == 4 and captured["timeout_seconds"] == 20
    assert captured["max_model_requests"] == 2 and captured["allow_model_calls"] is False


@pytest.mark.parametrize("endpoint", ["https://user:password@host/v1", "https://host/v1?api_key=secret", "https://host/v1#token"])
def test_credentials_are_not_accepted_inside_model_endpoints(endpoint):
    with pytest.raises(ValueError, match="endpoint"):
        adapter.create_model(ModelConfig(base_url=endpoint), adapter.profile(), api_key="fixture-key")


async def test_expired_setup_budget_stops_before_execution(tmp_path, monkeypatch):
    import time
    def slow_setup(config, effective):
        time.sleep(0.02)  # Simulates synchronous SDK setup; performs no network I/O.
        return FakeModel()
    async def forbidden(*args):
        raise AssertionError("An expired budget must stop before the attempt")
    monkeypatch.setattr(runner, "create_model", slow_setup)
    monkeypatch.setattr(runner, "attempt", forbidden)
    _, record = await runner.run(mode="live", allow_model_calls=True, output=tmp_path, timeout_seconds=0.01)
    assert record["status"] == "timeout" and record["model_request_count"] == 0
