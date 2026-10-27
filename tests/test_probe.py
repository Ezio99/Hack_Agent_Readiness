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
