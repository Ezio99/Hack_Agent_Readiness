from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Protocol

from ...compat import recover


@dataclass(frozen=True)
class LLMRequest:
    messages: list[dict]
    purpose: str                                   # e.g. "taskgen", "investigate"; recorded with every call
    max_tokens: int = 2048
    response_schema: dict | None = None            # JSON schema for strict structured output (optional)


@dataclass
class LLMResponse:
    text: str
    mode: str                                      # scripted | recorded | live
    model: str
    usage: dict = field(default_factory=dict)      # provider-reported {prompt_tokens, completion_tokens}; empty when the provider reported none
    cost_usd: float = 0.0                          # calculated at published prices (live only); never a bill
    request_sha256: str = ""
    finish_reason: str | None = None               # provider's stop reason (`stop` | `length` | ...); None when not reported (scripted / recorded)
    reasoning_tokens: int | None = None            # hidden reasoning tokens (already INCLUDED in completion_tokens); None when not reported


class LLMClient(Protocol):
    mode: str
    model: str

    def complete(self, request: LLMRequest) -> LLMResponse: ...


class StructuredOutputError(ValueError):
    """The model answered but the text did not validate. `diagnostics` is a sanitized description of the LAST response (see `response_diagnostics`); it never contains model text."""

    def __init__(self, message: str, diagnostics: dict | None = None):
        super().__init__(message)
        self.diagnostics = diagnostics or {}


def response_diagnostics(resp: LLMResponse, schema_errors: list[dict] | None = None) -> dict:
    """Sanitized facts about one response: why it was unusable (kind), stop reason, visible length, token usage. Never the text itself. `kind`: `empty_content` (no visible text; with
    finish_reason `length` this is the hidden-reasoning-exhausted-the-cap signature), `truncated` (text present but cut at the cap), `not_json`, `schema_mismatch`, `not_text` (non-string content)."""
    text = resp.text if isinstance(resp.text, str) else ""
    if not isinstance(resp.text, str) and resp.text:
        kind = "not_text"                                     # the provider sent non-string content (e.g. a list of parts)
    elif not text.strip():
        kind = "empty_content"
    elif resp.finish_reason == "length":
        kind = "truncated"
    else:
        try:
            json.loads(text)
            kind = "schema_mismatch"
        except ValueError:
            kind = "not_json"
    u = resp.usage or {}
    return {"kind": kind, "finish_reason": resp.finish_reason, "content_chars": len(text), "prompt_tokens": u.get("prompt_tokens"), "completion_tokens": u.get("completion_tokens"),
            "reasoning_tokens": resp.reasoning_tokens, "cost_usd": resp.cost_usd, "mode": resp.mode, "schema_errors": (schema_errors or [])[:5]}


def request_sha256(request: LLMRequest) -> str:
    return hashlib.sha256(json.dumps({"m": request.messages, "p": request.purpose, "t": request.max_tokens, "s": request.response_schema}, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def complete_structured(client: LLMClient, request: LLMRequest, output_model, *, retries: int = 1):
    """Call the model and validate the text against `output_model` (pydantic). Accepts strict JSON, or the documented Muse 'one prose line + one JSON object' pattern via the
    existing byte-preserving parser (`compat.recover`). Each retry is a NEW call (and is gated/billed like any other). Returns (parsed, last_response, attempts)."""
    last_err, diag = "no attempt", {}
    for attempt in range(retries + 1):
        resp = client.complete(request)
        try:
            return output_model.model_validate_json(resp.text), resp, attempt + 1
        except Exception as exc:
            rec = recover(resp.text, output_model)
            if rec["status"] == "recovered" and rec["validated"]:
                return output_model.model_validate_json(rec["normalized"]), resp, attempt + 1
            last_err = rec.get("reason") or "schema_invalid"
            errors = [{"loc": ".".join(str(x) for x in e.get("loc", ())), "type": e.get("type")} for e in exc.errors()] if hasattr(exc, "errors") else []        # locations and types only, never input values
            diag = response_diagnostics(resp, errors)
    raise StructuredOutputError(f"model output did not match the required schema after {retries + 1} attempt(s): {last_err}", diag)
