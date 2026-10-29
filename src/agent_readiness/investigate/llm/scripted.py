from __future__ import annotations

from typing import Callable

from .client import LLMRequest, LLMResponse, request_sha256


class ScriptedClient:
    """Deterministic test double: returns pre-written responses in order (or from a callable). Output is a TEST FIXTURE, never model behaviour; mode is always `scripted`."""
    mode = "scripted"
    model = "scripted-fixture"

    def __init__(self, responses: list[str] | Callable[[LLMRequest], str]):
        self._responses, self.calls = responses, []

    def complete(self, request: LLMRequest) -> LLMResponse:
        self.calls.append(request)
        if callable(self._responses):
            text = self._responses(request)
        else:
            if len(self.calls) > len(self._responses):
                raise RuntimeError("ScriptedClient exhausted: the code made more model calls than the test scripted")
            text = self._responses[len(self.calls) - 1]
        return LLMResponse(text=text, mode=self.mode, model=self.model, request_sha256=request_sha256(request))
