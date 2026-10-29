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


class LLMClient(Protocol):
    mode: str
    model: str

    def complete(self, request: LLMRequest) -> LLMResponse: ...


class StructuredOutputError(ValueError):
    pass


def request_sha256(request: LLMRequest) -> str:
    return hashlib.sha256(json.dumps({"m": request.messages, "p": request.purpose, "t": request.max_tokens, "s": request.response_schema}, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def complete_structured(client: LLMClient, request: LLMRequest, output_model, *, retries: int = 1):
    """Call the model and validate the text against `output_model` (pydantic). Accepts strict JSON, or the documented Muse 'one prose line + one JSON object' pattern via the
    existing byte-preserving parser (`compat.recover`). Each retry is a NEW call (and is gated/billed like any other). Returns (parsed, last_response, attempts)."""
    last_err = "no attempt"
    for attempt in range(retries + 1):
        resp = client.complete(request)
        try:
            return output_model.model_validate_json(resp.text), resp, attempt + 1
        except Exception:
            rec = recover(resp.text, output_model)
            if rec["status"] == "recovered" and rec["validated"]:
                return output_model.model_validate_json(rec["normalized"]), resp, attempt + 1
            last_err = rec.get("reason") or "schema_invalid"
    raise StructuredOutputError(f"model output did not match the required schema after {retries + 1} attempt(s): {last_err}")
