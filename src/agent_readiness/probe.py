"""Independently bounded Meta API compatibility probes (not part of the agent request gate).

Stage A: exactly one minimal text Chat Completions request, one attempt, no retries.
"""
import json
import os
import platform
import time
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from .agent import ModelConfig
from .recorder import Recorder, utcnow

STAGE_A_PROMPT = "Reply with exactly the text: OK"
STAGE_A_MAX_COMPLETION_TOKENS = 128
STAGE_A_TIMEOUT_SECONDS = 30.0
SAFE_HEADERS = {"content-type", "date", "x-request-id", "request-id", "retry-after"}


def _find_cost(value):
    """Provider-reported cost fields anywhere in a usage object; never estimated."""
    found = {}
    if isinstance(value, dict):
        for key, item in value.items():
            if "cost" in str(key).lower() and isinstance(item, (int, float, str)):
                found[key] = item
            elif isinstance(item, dict):
                found.update(_find_cost(item))
    return found


def stage_a(config: ModelConfig, output: Path = Path("runs"), *, transport=None) -> tuple[Path, dict]:
    api_key = os.environ.get(config.key_env, "")
    recorder = Recorder(Path(output), (api_key,))
    endpoint = urlsplit(config.base_url)
    if endpoint.scheme != "https" or not endpoint.hostname or endpoint.username or endpoint.password \
            or endpoint.query or endpoint.fragment:
        raise ValueError("Probe endpoint must be an https URL without credentials, query or fragment")
    record = dict(schema_version="probe-v1", stage="A", started_at=utcnow(),
                  provider=config.provider, endpoint=config.base_url, requested_model=config.model,
                  limits=dict(max_attempts=1, retries=0, timeout_seconds=STAGE_A_TIMEOUT_SECONDS,
                              max_completion_tokens=STAGE_A_MAX_COMPLETION_TOKENS),
                  python=platform.python_version(), httpx=httpx.__version__,
                  request_attempts=0, http_status=None, success=False, response_model=None,
                  completion=None, finish_reason=None, usage=None, provider_reported_cost=None,
                  response_headers=None, error=None)
    if not api_key:
        record["error"] = f"Missing credential: set {config.key_env}"
        record["status"] = "setup_error"
    else:
        body = {"model": config.model, "max_completion_tokens": STAGE_A_MAX_COMPLETION_TOKENS,
                "messages": [{"role": "user", "content": STAGE_A_PROMPT}]}
        record["request_body"] = body
        started = time.monotonic()
        # follow_redirects stays off so the bearer token is never forwarded elsewhere.
        client = httpx.Client(timeout=STAGE_A_TIMEOUT_SECONDS, follow_redirects=False, transport=transport)
        record["request_attempts"] = 1  # counted before sending: a failed attempt still consumes it
        try:
            with client:
                response = client.post(config.base_url.rstrip("/") + "/chat/completions", json=body,
                                       headers={"Authorization": f"Bearer {api_key}"})
            record["http_status"] = response.status_code
            record["response_headers"] = {k: v for k, v in response.headers.items() if k.lower() in SAFE_HEADERS}
            try:
                payload = response.json()
            except ValueError:
                payload = None
                record["error"] = "Non-JSON response body: " + response.text[:300]
            if response.status_code == 200 and isinstance(payload, dict):
                choice = (payload.get("choices") or [{}])[0]
                message = choice.get("message") or {}
                record.update(response_model=payload.get("model"), completion=message.get("content"),
                              finish_reason=choice.get("finish_reason"), usage=payload.get("usage"),
                              provider_reported_cost=_find_cost(payload.get("usage") or {}) or _find_cost(payload) or None,
                              success=message.get("content") is not None)
                if not record["success"]:
                    record["error"] = "Response lacked choices[0].message.content"
                    record["response_body"] = payload
            elif payload is not None:
                record["error"] = payload
        except httpx.HTTPError as exc:
            record["error"] = f"{type(exc).__name__}: {exc}"
        record["elapsed_seconds"] = round(time.monotonic() - started, 3)
        record["status"] = "completed" if record["success"] else "failed"
    record["finished_at"] = utcnow()
    recorder.write("probe.json", record)
    cleaned = json.loads((recorder.path / "probe.json").read_text())
    return recorder.path, cleaned
