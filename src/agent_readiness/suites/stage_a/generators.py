"""Task generators for the Stage A loop. Every generator exposes `identity` (recorded in provenance), `reservation_usd(request)` (the worst-case
spend the stopping rule checks before the round) and `complete(request) -> LLMResponse`.

  RoundsFixture     pre-written batches, one per round (developer-written test data; NOT model output; zero cost)
  FeedbackFixture   a deterministic stand-in that READS the feedback slot of the request and answers from a developer-written pool with intents
                    for the uncovered cells and missing capabilities it names (exercises targeted regeneration; NOT model output; zero cost)
The paid generator (Meta Muse Spark behind the spend gate) is `research.taskplan.planner_v2.MetaGenerator`: it lives outside Stage A because it
imports the agent's model configuration, which the Stage A boundary forbids. It is never used by tests or rehearsals."""
from __future__ import annotations

import json
import re
from pathlib import Path

from ...investigate.llm.client import LLMRequest, LLMResponse, request_sha256

POOL = Path(__file__).with_name("fixtures") / "larkspur-stage-a-pool-v1.json"


class RoundsFixture:
    mode, model = "scripted", "stage-a-rounds-fixture (NOT a model)"

    def __init__(self, batches: list[list[dict]], *, reservation_per_round_usd: float = 0.0, cost_per_round_usd: float = 0.0):
        self.batches, self.reservation, self.cost = batches, reservation_per_round_usd, cost_per_round_usd
        self.calls: list[LLMRequest] = []

    @property
    def identity(self) -> dict:
        return {"kind": "fixture", "model": self.model, "note": "developer-written batches; not model output", "reservation_per_round_usd": self.reservation}

    def reservation_usd(self, request: LLMRequest) -> float:
        return self.reservation

    def complete(self, request: LLMRequest) -> LLMResponse:
        self.calls.append(request)
        i = len(self.calls) - 1
        if i >= len(self.batches):
            raise RuntimeError("RoundsFixture exhausted: the loop asked for more rounds than were scripted")
        return LLMResponse(text=json.dumps({"tasks": self.batches[i]}), mode=self.mode, model=self.model, usage={}, cost_usd=self.cost, request_sha256=request_sha256(request))


def feedback_of(request: LLMRequest) -> dict | None:
    text = request.messages[-1]["content"]
    m = re.search(r"Feedback on the previous rounds[^\n]*\n(\{.*?\n\})", text, re.S)
    return json.loads(m.group(1)) if m else None


class FeedbackFixture:
    """Round 1: the `first` intents of the pool. Later rounds: pool intents (not yet proposed) whose persona x journey cell or capability the
    feedback lists as missing, in pool order, at most `n` per round. Deterministic; NOT model output."""
    mode, model = "scripted", "stage-a-feedback-fixture (NOT a model)"

    def __init__(self, first: list[str], *, n: int = 6, pool_path: Path = POOL, capability_of: dict | None = None):
        self.pool = json.loads(Path(pool_path).read_text())["tasks"]
        self.first, self.n = first, n
        self.capability_of = capability_of or {}
        self.used: set[str] = set()
        self.calls: list[LLMRequest] = []
        self.read_feedback: list[dict | None] = []

    @property
    def identity(self) -> dict:
        return {"kind": "feedback-fixture", "model": self.model, "note": "deterministic stand-in that reads the feedback slot; developer-written pool; not model output"}

    def reservation_usd(self, request: LLMRequest) -> float:
        return 0.0

    def complete(self, request: LLMRequest) -> LLMResponse:
        self.calls.append(request)
        fb = feedback_of(request)
        self.read_feedback.append(fb)
        if fb is None:
            batch = [t for t in self.pool if t["intent_id"] in self.first]
        else:
            cells = {(c["persona"], c["journey"]) for c in fb["uncovered_cells"]}
            caps = set(fb["missing_capabilities"])
            batch = [t for t in self.pool if t["intent_id"] not in self.used and ((t["persona"], t["journey"]) in cells or self.capability_of.get(t["intent_id"]) in caps)][:self.n]
        self.used |= {t["intent_id"] for t in batch}
        return LLMResponse(text=json.dumps({"tasks": batch}), mode=self.mode, model=self.model, usage={}, cost_usd=0.0, request_sha256=request_sha256(request))
