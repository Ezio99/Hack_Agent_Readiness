"""Meta (OpenAI-compatible Chat Completions) client for the investigator.

Safety properties (tested offline with `httpx.MockTransport`; this module has never made a live request):
  * the network is reachable only through `MetaClient.live(...)`, which runs the shared `ledger.preflight` (explicit allow flag, verified prices, https, key present);
  * every request passes the durable `spend_gate.RequestGate` BEFORE it is sent (reserve-before-send, per-call / per-run / call-count / ledger-ceiling caps);
  * a transport error, non-200 or missing usage keeps the full reservation counted;
  * retries are never automatic here (callers decide; each retry is a new gated call); the key is never logged or placed in an exception message.
Request shape follows https://dev.meta.ai/docs/protocols/chat-completions and /structured-output; real behaviour against the hosted API is NOT yet verified (that is the L0 probe)."""
from __future__ import annotations

import re

import httpx

from ...agent import ModelConfig
from ...capture import GateRefused
from ...ledger import Halt, Ledger, cost_of, preflight
from ...spend_gate import RequestGate
from .client import LLMRequest, LLMResponse, request_sha256


REASONING_EFFORTS = ("minimal", "low", "medium", "high")        # `none` is rejected by Spark (Task 004)
DEFAULT_REASONING_EFFORT = "low"                               # as the validated agent profiles; Task 004: without it hidden reasoning exhausted small caps and returned content null
INPUT_OVERHEAD_TOKENS = 128                                    # fixed input-token allowance added to every reservation (see spend_gate.upper_bound_usd; L0 attempt 2 under-reserved by >= 16 tokens)


class ProviderError(RuntimeError):
    """A failed model request, classified so the cause is not lost. `category`: `transport` (no HTTP response: timeout / connection / other httpx error), `http` (a non-200 status) or
    `parse` (a 200 whose body was not the expected shape). `status` is the HTTP status when there was one. `summary` is short and sanitized: a transport/parse error is its class name only; an HTTP
    error adds the provider's own `error.type` / `error.code` / `error.message` when the body is JSON (truncated, credentials redacted). Request bodies, headers and model text are never included.
    Model-output validation failures are a different layer (`StructuredOutputError`). The reservation stays counted in every case, exactly as before."""

    def __init__(self, category: str, status: int | None, summary: str):
        self.category, self.status, self.summary = category, status, summary
        super().__init__(f"model request failed ({category}{f' HTTP {status}' if status is not None else ''}: {summary}); the reservation stays counted")


_SECRETS = re.compile(r"Bearer\s+\S+|\bsk-[A-Za-z0-9_-]{8,}")


def _clean(text: object, key: str | None, limit: int = 160) -> str:
    t = " ".join(str(text).split())
    t = t.replace(key, "[redacted]") if key else t
    return _SECRETS.sub("[redacted]", t)[:limit]


def _http_summary(response: httpx.Response, key: str | None) -> str:
    """The provider's own error fields when the body is a JSON object, else just the reason phrase. Never the raw body."""
    try:
        err = response.json().get("error")
    except Exception:
        err = None
    if isinstance(err, dict):
        parts = [f"{k}={_clean(err[k], key)}" for k in ("type", "code", "message") if isinstance(err.get(k), (str, int)) and err.get(k) != ""]
        if parts:
            return "; ".join(parts)[:240]
    elif isinstance(err, str) and err:
        return f"message={_clean(err, key)}"
    return _clean(response.reason_phrase or "no error detail", key)


class MetaClient:
    mode = "live"

    def __init__(self, config: ModelConfig, api_key: str, gate: RequestGate, *, transport: httpx.BaseTransport | None = None, timeout: float = 90.0, _network_ok: bool = False,
                 reasoning_effort: str | None = DEFAULT_REASONING_EFFORT):
        if transport is None and not _network_ok:
            raise Halt("MetaClient has no transport and live access was not unlocked; use MetaClient.live(...)")
        self.config, self.model, self.gate = config, config.model, gate
        if reasoning_effort is not None and reasoning_effort not in REASONING_EFFORTS:
            raise ValueError(f"reasoning_effort must be one of {REASONING_EFFORTS} (or None to omit it)")
        self.reasoning_effort = reasoning_effort
        self._key = api_key
        self._client = httpx.Client(transport=transport, timeout=timeout, follow_redirects=False)
        self._index = gate.request_count()

    @classmethod
    def live(cls, config: ModelConfig, ledger: Ledger, run_id: str, *, allow_model_calls: bool, run_cap_usd: float, per_request_cap_usd: float = 0.05, max_requests: int = 16) -> "MetaClient":
        key = preflight(config, allow_model_calls)
        gate = RequestGate(ledger, run_id, run_cap=run_cap_usd, per_request_cap=per_request_cap_usd, max_requests=max_requests, input_overhead_tokens=INPUT_OVERHEAD_TOKENS)
        return cls(config, key, gate, _network_ok=True)

    def body(self, request: LLMRequest) -> dict:
        body = {"model": self.model, "messages": request.messages, "max_completion_tokens": request.max_tokens}
        if self.reasoning_effort:
            body["reasoning_effort"] = self.reasoning_effort
        if request.response_schema is not None:
            body["response_format"] = {"type": "json_schema", "json_schema": {"name": request.purpose.replace("-", "_")[:60] or "output", "strict": True, "schema": request.response_schema}}
        return body

    def complete(self, request: LLMRequest) -> LLMResponse:
        body = self.body(request)
        index = self._index + 1
        self._index = index
        try:
            self.gate.reserve(index, body)                         # raises GateRefused BEFORE anything is sent
        except GateRefused as exc:
            raise Halt(f"spend gate refused the request: {exc}") from exc
        record: dict = {"http_status": None}
        try:
            r = self._client.post(self.config.base_url.rstrip("/") + "/chat/completions", json=body, headers={"Authorization": f"Bearer {self._key}", "Content-Type": "application/json"})
        except httpx.TimeoutException as exc:
            raise ProviderError("transport", None, f"timeout ({type(exc).__name__})") from None
        except httpx.HTTPError as exc:
            raise ProviderError("transport", None, type(exc).__name__) from None
        record["http_status"] = r.status_code
        if r.status_code != 200:
            raise ProviderError("http", r.status_code, _http_summary(r, self._key)) from None
        try:
            data = r.json()
            choice = data["choices"][0]
            text = choice["message"]["content"] or ""
            usage = data.get("usage") or {}
            record["usage"] = usage
            finish = choice.get("finish_reason")
            finish = finish[:32] if isinstance(finish, str) else None
            details = usage.get("completion_tokens_details")
            reasoning = details.get("reasoning_tokens") if isinstance(details, dict) else None
            reasoning = reasoning if isinstance(reasoning, int) else None
        except (ValueError, KeyError, IndexError, TypeError, AttributeError) as exc:
            self.gate.settle(index, record)                        # a 200 was received: settle (no usable usage keeps the full reservation, as before)
            raise ProviderError("parse", 200, f"unexpected response shape ({type(exc).__name__})") from None
        self.gate.settle(index, record)
        return LLMResponse(text=text, mode=self.mode, model=self.model, usage={k: usage.get(k) for k in ("prompt_tokens", "completion_tokens")}, cost_usd=cost_of(usage), request_sha256=request_sha256(request), finish_reason=finish, reasoning_tokens=reasoning)
