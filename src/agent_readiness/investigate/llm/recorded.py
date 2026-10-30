from __future__ import annotations

import json
import os
from pathlib import Path

from .client import LLMClient, LLMRequest, LLMResponse, request_sha256


class RecordingClient:
    """Wraps a client and appends every exchange to a private JSONL transcript (for later replay). The transcript holds prompts and model text: keep it out of Git
    unless it has been reviewed and approved; the recorded request hash lets `RecordedClient` replay it offline."""

    def __init__(self, inner: LLMClient, path: Path, calls_path: Path | None = None):
        self.inner, self.path = inner, Path(path)
        self.calls_path = Path(calls_path) if calls_path else None          # SANITIZED per-call log (no prompts, no model text): safe to keep with the run's public artifacts
        self.mode, self.model = inner.mode, inner.model

    @staticmethod
    def _append(path: Path, row: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a") as f:
            f.write(json.dumps(row) + "\n")
            f.flush()
            os.fsync(f.fileno())

    def _log_call(self, request: LLMRequest, row: dict) -> None:
        if self.calls_path:
            self._append(self.calls_path, {"purpose": request.purpose, "request_sha256": request_sha256(request)[:16], "max_completion_tokens": request.max_tokens, **row})

    def complete(self, request: LLMRequest) -> LLMResponse:
        try:
            resp = self.inner.complete(request)
        except Exception as exc:
            if hasattr(exc, "category"):                                    # a classified provider error: status and sanitized summary only
                self._log_call(request, {"outcome": "provider_error", "error_category": exc.category, "http_status": getattr(exc, "status", None), "error_summary": getattr(exc, "summary", None)})
            raise
        u = resp.usage or {}
        done = u.get("completion_tokens")
        self._append(self.path, {"request_sha256": request_sha256(request), "purpose": request.purpose, "mode": resp.mode, "model": resp.model, "usage": resp.usage, "cost_usd": resp.cost_usd,
                                 "finish_reason": resp.finish_reason, "reasoning_tokens": resp.reasoning_tokens, "text": resp.text, "messages": request.messages})
        self._log_call(request, {"outcome": "response", "finish_reason": resp.finish_reason, "prompt_tokens": u.get("prompt_tokens"), "completion_tokens": done, "reasoning_tokens": resp.reasoning_tokens,
                                 "cap_used_pct": round(100 * done / request.max_tokens, 1) if isinstance(done, int) and request.max_tokens else None,
                                 "content_chars": len(resp.text) if isinstance(resp.text, str) else None, "cost_usd": resp.cost_usd, "mode": resp.mode})
        return resp


class RecordedClient:
    """Replays a transcript offline, keyed by request hash. An unknown request is an error (a replay must not silently drift). Responses are marked `recorded`."""
    mode = "recorded"

    def __init__(self, path: Path):
        self.entries: dict[str, list[dict]] = {}
        for line in Path(path).read_text().splitlines():
            e = json.loads(line)
            self.entries.setdefault(e["request_sha256"], []).append(e)
        self.model = next((e[0]["model"] for e in self.entries.values()), "recorded")
        self._used: dict[str, int] = {}

    def complete(self, request: LLMRequest) -> LLMResponse:
        h = request_sha256(request)
        if h not in self.entries:
            raise KeyError(f"no recorded response for request {h[:12]} ({request.purpose}); the prompt differs from the recorded run")
        i = self._used.get(h, 0)
        self._used[h] = i + 1
        e = self.entries[h][min(i, len(self.entries[h]) - 1)]
        return LLMResponse(text=e["text"], mode=self.mode, model=e["model"], usage=e.get("usage") or {}, cost_usd=0.0, request_sha256=h, finish_reason=e.get("finish_reason"), reasoning_tokens=e.get("reasoning_tokens"))
