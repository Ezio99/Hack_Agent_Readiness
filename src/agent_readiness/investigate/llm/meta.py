"""Meta (OpenAI-compatible Chat Completions) client for the investigator.

Safety properties (tested offline with `httpx.MockTransport`; this module has never made a live request):
  * the network is reachable only through `MetaClient.live(...)`, which runs the shared `ledger.preflight` (explicit allow flag, verified prices, https, key present);
  * every request passes the durable `spend_gate.RequestGate` BEFORE it is sent (reserve-before-send, per-call / per-run / call-count / ledger-ceiling caps);
  * a transport error, non-200 or missing usage keeps the full reservation counted;
  * retries are never automatic here (callers decide; each retry is a new gated call); the key is never logged or placed in an exception message.
Request shape follows https://dev.meta.ai/docs/protocols/chat-completions and /structured-output; real behaviour against the hosted API is NOT yet verified (that is the L0 probe)."""
from __future__ import annotations

import httpx

from ...agent import ModelConfig
from ...capture import GateRefused
from ...ledger import Halt, Ledger, cost_of, preflight
from ...spend_gate import RequestGate
from .client import LLMRequest, LLMResponse, request_sha256


class MetaClient:
    mode = "live"

    def __init__(self, config: ModelConfig, api_key: str, gate: RequestGate, *, transport: httpx.BaseTransport | None = None, timeout: float = 90.0, _network_ok: bool = False):
        if transport is None and not _network_ok:
            raise Halt("MetaClient has no transport and live access was not unlocked; use MetaClient.live(...)")
        self.config, self.model, self.gate = config, config.model, gate
        self._key = api_key
        self._client = httpx.Client(transport=transport, timeout=timeout, follow_redirects=False)
        self._index = gate.request_count()

    @classmethod
    def live(cls, config: ModelConfig, ledger: Ledger, run_id: str, *, allow_model_calls: bool, run_cap_usd: float, per_request_cap_usd: float = 0.05, max_requests: int = 16) -> "MetaClient":
        key = preflight(config, allow_model_calls)
        gate = RequestGate(ledger, run_id, run_cap=run_cap_usd, per_request_cap=per_request_cap_usd, max_requests=max_requests)
        return cls(config, key, gate, _network_ok=True)

    def body(self, request: LLMRequest) -> dict:
        body = {"model": self.model, "messages": request.messages, "max_completion_tokens": request.max_tokens}
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
            record["http_status"] = r.status_code
            if r.status_code != 200:
                raise RuntimeError(f"provider returned HTTP {r.status_code}")
            data = r.json()
            text = data["choices"][0]["message"]["content"] or ""
            usage = data.get("usage") or {}
            record["usage"] = usage
        except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError, RuntimeError) as exc:
            if record["http_status"] == 200:
                self.gate.settle(index, record)
            raise RuntimeError(f"model request failed ({type(exc).__name__}); the reservation stays counted") from None
        self.gate.settle(index, record)
        return LLMResponse(text=text, mode=self.mode, model=self.model, usage={k: usage.get(k) for k in ("prompt_tokens", "completion_tokens")}, cost_usd=cost_of(usage), request_sha256=request_sha256(request))
