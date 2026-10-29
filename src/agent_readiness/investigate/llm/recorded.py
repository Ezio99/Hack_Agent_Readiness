from __future__ import annotations

import json
import os
from pathlib import Path

from .client import LLMClient, LLMRequest, LLMResponse, request_sha256


class RecordingClient:
    """Wraps a client and appends every exchange to a private JSONL transcript (for later replay). The transcript holds prompts and model text: keep it out of Git
    unless it has been reviewed and approved; the recorded request hash lets `RecordedClient` replay it offline."""

    def __init__(self, inner: LLMClient, path: Path):
        self.inner, self.path = inner, Path(path)
        self.mode, self.model = inner.mode, inner.model

    def complete(self, request: LLMRequest) -> LLMResponse:
        resp = self.inner.complete(request)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a") as f:
            f.write(json.dumps({"request_sha256": request_sha256(request), "purpose": request.purpose, "mode": resp.mode, "model": resp.model, "usage": resp.usage,
                                "cost_usd": resp.cost_usd, "text": resp.text, "messages": request.messages}) + "\n")
            f.flush()
            os.fsync(f.fileno())
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
        return LLMResponse(text=e["text"], mode=self.mode, model=e["model"], usage=e.get("usage") or {}, cost_usd=0.0, request_sha256=h)
