from contextlib import asynccontextmanager
import json
import asyncio
import pytest
from agent_readiness import runner
from agent_readiness.recorder import Recorder
from agent_readiness.tasks import generate
from .test_benchmark import answer_for


async def test_paid_calls_disabled_and_missing_credentials(tmp_path, monkeypatch):
    def must_not_call(*args, **kwargs):
        raise AssertionError("Model adapter should not be constructed")
    monkeypatch.setattr(runner, "create_model", must_not_call)
    path, record = await runner.run(mode="live", output=tmp_path)
    assert record["status"] == "setup_error"
    assert "disabled" in record["errors"][0]
    assert (path / "trace.jsonl").exists()
    monkeypatch.undo()
    monkeypatch.delenv("MODEL_API_KEY", raising=False)
    _, record = await runner.run(mode="live", allow_model_calls=True, output=tmp_path)
    assert record["status"] == "setup_error"
    assert "Missing credential" in record["errors"][0]


@asynccontextmanager
async def synthetic_target(url):
    yield "http://127.0.0.1:8000/"


async def test_trial_artifacts_evaluation_and_distinct_runs(tmp_path, monkeypatch):
    async def scripted(public, url, recorder, effective):
        assert public == generate().public
        assert not hasattr(public, "expected_id")
        return dict(answer=answer_for(generate()), status="completed", steps=3, action_count=5, usage=None, errors=[])
    monkeypatch.setattr(runner, "target", synthetic_target)
    monkeypatch.setattr(runner, "smoke", scripted)
    first, record = await runner.run(output=tmp_path)
    second, _ = await runner.run(output=tmp_path)
    assert first != second
    assert record["evaluation"]["passed"] is True
    saved = json.loads((first / "run.json").read_text())
    assert saved["usage"] is None and saved["inventory_hash"] and saved["profile"]["use_vision"]
    assert saved["provenance"]["packages"]["browser-use"] == "0.11.13"
    assert "not a live agent measurement" in (first / "summary.md").read_text()


@pytest.mark.parametrize("failure,status", [(RuntimeError("synthetic failure"), "infrastructure_error"), (None, "timeout")])
async def test_failures_and_timeouts_preserve_records(tmp_path, monkeypatch, failure, status):
    async def broken(*args):
        if failure:
            raise failure
        await asyncio.sleep(1)
    monkeypatch.setattr(runner, "target", synthetic_target)
    monkeypatch.setattr(runner, "smoke", broken)
    path, record = await runner.run(output=tmp_path, timeout_seconds=0.05)
    assert record["status"] == status and record["evaluation"] is None
    assert json.loads((path / "run.json").read_text())["finished_at"]
    assert (path / "summary.md").exists()


async def test_invalid_limits_and_external_storefront_rejected(tmp_path):
    _, result = await runner.run(output=tmp_path, max_steps=0)
    assert result["status"] == "setup_error"
    _, result = await runner.run(output=tmp_path, url="https://example.com/")
    assert result["status"] == "setup_error"


def test_nested_secret_redaction(tmp_path):
    recorder = Recorder(tmp_path, ("secret-value",))
    recorder.event("test", nested={"authorization": "abc", "message": "contains secret-value"})
    assert "secret-value" not in (recorder.path / "trace.jsonl").read_text()
    assert "abc" not in (recorder.path / "trace.jsonl").read_text()


async def test_timeout_retains_reported_usage_and_executed_steps(tmp_path, monkeypatch):
    async def interrupted(public, url, recorder, effective):
        recorder.event("model_response", usage={"total_tokens": 15})
        recorder.event("step_result", result={"result": [{"is_done": False}, {"is_done": False}]})
        recorder.event("observation", url=url)
        recorder.event("browser_version", version="Synthetic Chromium")
        await asyncio.sleep(1)
    monkeypatch.setattr(runner, "target", synthetic_target)
    monkeypatch.setattr(runner, "smoke", interrupted)
    _, record = await runner.run(output=tmp_path, timeout_seconds=0.05)
    assert record["status"] == "timeout"
    assert record["usage"] == [{"total_tokens": 15}]
    assert record["steps"] == 1 and record["action_count"] == 2
    assert record["navigation"][0]["url"].startswith("http://127.0.0.1")
    assert record["browser_version"] == "Synthetic Chromium"


async def test_internal_operation_timeout_is_not_a_wall_clock_limit(tmp_path, monkeypatch):
    async def startup_timeout(*args):
        raise TimeoutError("browser startup")
    monkeypatch.setattr(runner, "target", synthetic_target)
    monkeypatch.setattr(runner, "smoke", startup_timeout)
    _, record = await runner.run(output=tmp_path, timeout_seconds=30)
    assert record["status"] == "infrastructure_error"
    assert record["stop_reason"] == "operation_timeout"
    assert "browser startup" in record["errors"][0]
