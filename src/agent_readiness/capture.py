"""Bounded, sanitized capture of model HTTP exchanges, taken before Browser Use parses the response.

The Browser Use adapter parses and validates model output inside ``ainvoke``. If that raises, the raw
content, finish reason, request id and usage are otherwise lost. These httpx event hooks record them first.
Nothing here changes what is sent to, or accepted from, the provider.
"""
import hashlib
import json
import time

from .recorder import Recorder, utcnow

MAX_CONTENT_CHARS = 20_000       # raw model content kept per response
MAX_ERROR_BODY_CHARS = 2_000     # non-200 bodies
MAX_JSON_PROBES = 20             # '{' positions tried when looking for embedded JSON


def _sha(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def request_summary(body: dict) -> dict:
    """Structure of a chat-completions request without message text or image bytes."""
    messages = []
    for message in body.get("messages") or []:
        content = message.get("content")
        if isinstance(content, str):
            parts = [{"type": "text", "chars": len(content)}]
        else:
            parts = []
            for part in content or []:
                if part.get("type") == "text":
                    parts.append({"type": "text", "chars": len(part.get("text", ""))})
                elif part.get("type") == "image_url":
                    image = part.get("image_url") or {}
                    parts.append({"type": "image_url", "detail": image.get("detail"),
                                  "url_chars": len(image.get("url", "")),
                                  "data_url": str(image.get("url", "")).startswith("data:image/")})
                else:
                    parts.append({"type": part.get("type")})
        messages.append({"role": message.get("role"), "parts": parts})
    fmt = body.get("response_format") or {}
    schema_info = None
    if fmt:
        spec = fmt.get("json_schema") or {}
        schema = spec.get("schema")
        schema_info = {"type": fmt.get("type"), "name": spec.get("name"), "strict": spec.get("strict"),
                       "schema_sha256": _sha(schema) if schema is not None else None,
                       "schema_canonical_bytes": len(json.dumps(schema, sort_keys=True, separators=(",", ":")))
                       if schema is not None else None}
    scalars = {k: v for k, v in body.items() if k not in {"messages", "response_format"}}
    return {"body_keys": sorted(body), "model": body.get("model"), "parameters": scalars,
            "response_format": schema_info, "messages": messages}


def analyze_content(content) -> dict:
    """Facts about the returned text, independent of any output model."""
    if content is None:
        return {"kind": "null"}
    if not isinstance(content, str):
        return {"kind": "non_string", "python_type": type(content).__name__}
    try:
        json.loads(content)
        return {"kind": "json", "chars": len(content)}
    except ValueError:
        pass
    info = {"kind": "non_json", "chars": len(content), "starts_with_brace": content.lstrip().startswith("{"),
            "ends_with_brace": content.rstrip().endswith("}"), "embedded_json": None}
    decoder = json.JSONDecoder()
    probes = 0
    for start, char in enumerate(content):
        if char != "{":
            continue
        probes += 1
        if probes > MAX_JSON_PROBES:
            break
        try:
            value, end = decoder.raw_decode(content, start)
        except ValueError:
            continue
        info["embedded_json"] = {"offset": start, "chars": end - start, "trailing_chars": len(content) - end,
                                 "is_object": isinstance(value, dict)}
        break
    return info


class ResponseCapture:
    """httpx event hooks writing ``model_http_request``/``model_http_response`` events and a response file."""

    def __init__(self, recorder: Recorder):
        self.recorder = recorder
        self.records: list[dict] = []
        self._started: list[float] = []
        self._claimed = 0

    def attach(self, client):
        client.event_hooks["request"].append(self.on_request)
        client.event_hooks["response"].append(self.on_response)
        return client

    async def on_request(self, request):
        self._started.append(time.monotonic())
        try:
            body = json.loads(request.content)
        except ValueError:
            body = {}
        self.recorder.event("model_http_request", index=len(self._started), method=request.method,
                            url=str(request.url.copy_with(query=None)),
                            timeout=dict(request.extensions.get("timeout") or {}), **request_summary(body))

    async def on_response(self, response):
        index = len(self.records) + 1
        await response.aread()
        started = self._started[index - 1] if index - 1 < len(self._started) else None
        record = {"index": index, "captured_at": utcnow(), "http_status": response.status_code,
                  "request_id": response.headers.get("x-request-id") or response.headers.get("request-id"),
                  "elapsed_seconds": round(time.monotonic() - started, 3) if started else None,
                  "body_bytes": len(response.content)}
        try:
            payload = response.json()
        except ValueError:
            payload = None
        if response.status_code == 200 and isinstance(payload, dict):
            choice = (payload.get("choices") or [{}])[0]
            message = choice.get("message") or {}
            content = message.get("content")
            usage = payload.get("usage")
            details = (usage or {}).get("completion_tokens_details") or {}
            record.update(
                response_model=payload.get("model"), finish_reason=choice.get("finish_reason"),
                refusal=message.get("refusal"), usage=usage,
                prompt_tokens=(usage or {}).get("prompt_tokens"),
                completion_tokens=(usage or {}).get("completion_tokens"),
                reasoning_tokens=details.get("reasoning_tokens"),
                content_analysis=analyze_content(content),
                content=content if not isinstance(content, str) else content[:MAX_CONTENT_CHARS],
                content_truncated=isinstance(content, str) and len(content) > MAX_CONTENT_CHARS)
        else:
            record["error_body"] = (payload if payload is not None else response.text[:MAX_ERROR_BODY_CHARS])
        self.records.append(record)
        self.recorder.write(f"model-response-{index:02d}.json", record)
        summary = {k: v for k, v in record.items() if k not in {"content", "error_body"}}
        self.recorder.event("model_http_response", file=f"model-response-{index:02d}.json", **summary)

    def take(self) -> list[dict]:
        """Records captured since the previous call (one per model invocation; SDK retries are off)."""
        fresh = self.records[self._claimed:]
        self._claimed = len(self.records)
        return fresh

    def summary(self) -> list[dict]:
        keys = ("index", "http_status", "request_id", "finish_reason", "prompt_tokens", "completion_tokens",
                "reasoning_tokens", "elapsed_seconds", "content_analysis", "output_error")
        return [{k: r.get(k) for k in keys if k in r} for r in self.records]


def attach_capture(llm, recorder: Recorder):
    """Add capture hooks to the model's httpx client; return None for models without one."""
    if not hasattr(llm, "http_client"):
        return None
    if llm.http_client is None:
        from openai import DefaultAsyncHttpxClient  # same defaults the SDK would have used
        llm.http_client = DefaultAsyncHttpxClient()
    capture = ResponseCapture(recorder)
    capture.attach(llm.http_client)
    return capture


def classify_output(record: dict, output_format) -> dict | None:
    """Return a ``model_output_error`` description for a 200 response that cannot become the output model."""
    if record.get("http_status") != 200 or "content_analysis" not in record:
        return None
    analysis, finish = record["content_analysis"], record.get("finish_reason")
    if record.get("content_truncated"):
        return {"subtype": "unclassified_truncated_capture", "finish_reason": finish}
    if analysis["kind"] == "null":
        return {"subtype": "length_without_content" if finish == "length" else "null_content",
                "finish_reason": finish, "reasoning_tokens": record.get("reasoning_tokens"),
                "completion_tokens": record.get("completion_tokens")}
    if analysis["kind"] == "non_json":
        return {"subtype": "malformed_json", "finish_reason": finish,
                "starts_with_brace": analysis["starts_with_brace"], "embedded_json": analysis["embedded_json"]}
    if analysis["kind"] == "json" and output_format is not None:
        try:
            output_format.model_validate_json(record["content"])
        except Exception as exc:  # pydantic.ValidationError; input values are deliberately not recorded
            errors = exc.errors(include_input=False, include_url=False)[:20] if hasattr(exc, "errors") else []
            return {"subtype": "schema_validation", "finish_reason": finish,
                    "errors": [{"loc": [str(p) for p in e.get("loc", ())], "type": e.get("type")} for e in errors]}
    if finish == "length":
        return {"subtype": "truncated", "finish_reason": finish}
    return None
