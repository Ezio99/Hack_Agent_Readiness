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
STAGE_A_MAX_COMPLETION_TOKENS = 512
STAGE_A_REASONING_EFFORT = "low"
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
                              max_completion_tokens=STAGE_A_MAX_COMPLETION_TOKENS,
                              reasoning_effort=STAGE_A_REASONING_EFFORT),
                  python=platform.python_version(), httpx=httpx.__version__,
                  request_attempts=0, http_status=None, success=False, response_model=None,
                  completion=None, finish_reason=None, usage=None, provider_reported_cost=None,
                  response_headers=None, error=None)
    if not api_key:
        record["error"] = f"Missing credential: set {config.key_env}"
        record["status"] = "setup_error"
    else:
        body = {"model": config.model, "reasoning_effort": STAGE_A_REASONING_EFFORT,
                "max_completion_tokens": STAGE_A_MAX_COMPLETION_TOKENS,
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


STAGE_B_MAX_COMPLETION_TOKENS = 1024
STAGE_B_TIMEOUT_SECONDS = 45.0
STAGE_B_REASONING_EFFORT = "low"
STAGE_B_PROMPT = ("Schema compatibility test only; no browser or website is involved. Return an output whose action "
                  "list contains exactly one done action with success=true and data {product_id: \"PROBE-0\", "
                  "price_cents: 100, available: false}. Fill the other fields briefly.")
STAGE_B_EXPECTED = {"product_id": "PROBE-0", "price_cents": 100, "available": False}


def build_agent_output_schema():
    """The exact optimized schema the Browser Use adapter sends for the frozen profile (no network)."""
    import tempfile
    from .agent import create_agent, create_model, prepare_browser_environment, profile
    from .tasks import generate
    prepare_browser_environment()
    from browser_use import Browser
    from browser_use.llm.schema import SchemaOptimizer
    effective = profile()
    model = create_model(ModelConfig(), effective, api_key="synthetic-not-sent")
    with tempfile.TemporaryDirectory() as tmp:
        agent = create_agent(generate().public, "http://127.0.0.1:8000/", model,
                             Browser(headless=True, enable_default_extensions=False), Recorder(Path(tmp)), effective)
        # Same call and flag as ChatOpenAI.ainvoke with remove_min_items_from_schema=True.
        schema = SchemaOptimizer.create_optimized_json_schema(agent.AgentOutput, remove_min_items=True)
        return schema, agent.AgentOutput


def _schema_digest(schema) -> tuple[str, int]:
    import hashlib
    canonical = json.dumps(schema, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(canonical).hexdigest(), len(canonical)


def stage_b_body(config: ModelConfig, schema) -> dict:
    return {"model": config.model, "reasoning_effort": STAGE_B_REASONING_EFFORT,
            "max_completion_tokens": STAGE_B_MAX_COMPLETION_TOKENS,
            "response_format": {"type": "json_schema",
                                "json_schema": {"name": "agent_output", "strict": True, "schema": schema}},
            "messages": [{"role": "user", "content": STAGE_B_PROMPT}]}


def _grade_stage_b(content, output_model) -> dict:
    """Independent checks; each recorded separately so failures stay classifiable."""
    result = dict(json_parsed=False, agent_output_valid=False, single_done_action=False,
                  values_match=False, validation_error=None)
    try:
        json.loads(content)
        result["json_parsed"] = True
        parsed = output_model.model_validate_json(content)
        result["agent_output_valid"] = True
        actions = [a.model_dump(mode="json", exclude_none=True) for a in parsed.action]
        result["actions"] = actions
        if len(actions) == 1 and list(actions[0]) == ["done"]:
            result["single_done_action"] = True
            data = actions[0]["done"].get("data")
            result["values_match"] = (isinstance(data, dict) and set(data) == set(STAGE_B_EXPECTED) and all(
                type(data[k]) is type(v) and data[k] == v for k, v in STAGE_B_EXPECTED.items()))
    except Exception as exc:  # recorded verbatim (sanitized on write), never raised
        result["validation_error"] = f"{type(exc).__name__}: {str(exc)[:500]}"
    return result


def stage_b(config: ModelConfig, output: Path = Path("runs"), *, transport=None) -> tuple[Path, dict]:
    api_key = os.environ.get(config.key_env, "")
    recorder = Recorder(Path(output), (api_key,))
    endpoint = urlsplit(config.base_url)
    if endpoint.scheme != "https" or not endpoint.hostname or endpoint.username or endpoint.password \
            or endpoint.query or endpoint.fragment:
        raise ValueError("Probe endpoint must be an https URL without credentials, query or fragment")
    schema, output_model = build_agent_output_schema()
    digest, size = _schema_digest(schema)
    recorder.write("schema.json", schema)
    body = stage_b_body(config, schema)
    record = dict(schema_version="probe-v1", stage="B", started_at=utcnow(),
                  provider=config.provider, endpoint=config.base_url, requested_model=config.model,
                  limits=dict(max_attempts=1, retries=0, timeout_seconds=STAGE_B_TIMEOUT_SECONDS,
                              max_completion_tokens=STAGE_B_MAX_COMPLETION_TOKENS,
                              reasoning_effort=STAGE_B_REASONING_EFFORT),
                  schema_sha256=digest, schema_canonical_bytes=size, strict=True,
                  python=platform.python_version(), httpx=httpx.__version__,
                  browser_use=__import__("importlib.metadata").metadata.version("browser-use"),
                  request_body={**body, "response_format": {"type": "json_schema", "json_schema": {
                      "name": "agent_output", "strict": True, "schema": f"[see schema.json sha256={digest}]"}}},
                  request_attempts=0, http_status=None, request_id=None, success=False, failure_class=None,
                  response_model=None, completion=None, finish_reason=None, usage=None,
                  provider_reported_cost=None, grading=None, response_headers=None, error=None)
    if not api_key:
        record.update(error=f"Missing credential: set {config.key_env}", status="setup_error",
                      failure_class="setup_error")
    else:
        started = time.monotonic()
        client = httpx.Client(timeout=STAGE_B_TIMEOUT_SECONDS, follow_redirects=False, transport=transport)
        record["request_attempts"] = 1
        try:
            with client:
                response = client.post(config.base_url.rstrip("/") + "/chat/completions", json=body,
                                       headers={"Authorization": f"Bearer {api_key}"})
            record["http_status"] = response.status_code
            record["response_headers"] = {k: v for k, v in response.headers.items() if k.lower() in SAFE_HEADERS}
            record["request_id"] = response.headers.get("x-request-id")
            try:
                payload = response.json()
            except ValueError:
                payload = None
                record["error"] = "Non-JSON response body: " + response.text[:500]
            if response.status_code != 200:
                record["error"] = payload if payload is not None else record["error"]
                record["failure_class"] = "schema_or_request_rejected" if response.status_code == 400 else "http_error"
            elif isinstance(payload, dict):
                choice = (payload.get("choices") or [{}])[0]
                message = choice.get("message") or {}
                content = message.get("content")
                record.update(response_model=payload.get("model"), completion=content,
                              finish_reason=choice.get("finish_reason"), usage=payload.get("usage"),
                              provider_reported_cost=_find_cost(payload.get("usage") or {}) or _find_cost(payload) or None)
                if content is None:
                    record["failure_class"] = "cap_exhausted" if record["finish_reason"] == "length" else "null_content"
                    record["response_body"] = payload
                else:
                    record["grading"] = _grade_stage_b(content, output_model)
                    g = record["grading"]
                    if record["finish_reason"] != "stop":
                        record["failure_class"] = "not_stopped"
                    elif not (g["json_parsed"] and g["agent_output_valid"]):
                        record["failure_class"] = "unparsable_or_invalid"
                    elif not (g["single_done_action"] and g["values_match"]):
                        record["failure_class"] = "accepted_but_values_mismatch"
                    else:
                        record["success"] = True
            else:
                record["failure_class"] = "unexpected_response"
        except httpx.TimeoutException as exc:
            record.update(error=f"{type(exc).__name__}: {exc}", failure_class="timeout")
        except httpx.HTTPError as exc:
            record.update(error=f"{type(exc).__name__}: {exc}", failure_class="network_error")
        record["elapsed_seconds"] = round(time.monotonic() - started, 3)
        record["status"] = "completed" if record["success"] else "failed"
    record["finished_at"] = utcnow()
    recorder.write("probe.json", record)
    return recorder.path, json.loads((recorder.path / "probe.json").read_text())
