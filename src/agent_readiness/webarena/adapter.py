"""Load WebArena Verified tasks and evaluate them with the official evaluator (private ground truth stays inside the official package)."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

SITE_PLACEHOLDER = "__SHOPPING__"


def available() -> bool:
    try:
        import webarena_verified  # noqa: F401
        return True
    except ImportError:
        return False


class WAAnswer(BaseModel):
    """The official WebArena Verified final-response contract (FinalAgentResponse): used as the Browser Use `done` data schema."""
    model_config = ConfigDict(extra="forbid")
    task_type: Literal["RETRIEVE", "MUTATE", "NAVIGATE"]
    status: Literal["SUCCESS", "ACTION_NOT_ALLOWED_ERROR", "PERMISSION_DENIED_ERROR", "NOT_FOUND_ERROR", "DATA_VALIDATION_ERROR", "UNKNOWN_ERROR"]
    retrieved_data: list[Any] | None = None
    error_details: str | None = None


@dataclass(frozen=True)
class WATask:
    task_id: int
    template_id: int
    intent: str                   # the public instruction
    start_urls: tuple[str, ...]   # rendered against the configured base URL
    task_type: str                # retrieve | navigate | mutate (from the task's expected response)
    sites: tuple[str, ...]
    network_evaluators: int       # number of NetworkEventEvaluator entries (state-changing checks)

    def prompt(self) -> str:
        return (f"{self.intent}\n\nStart at {self.start_urls[0]}"
                + (f" (other tabs/pages to consider: {', '.join(self.start_urls[1:])})" if len(self.start_urls) > 1 else "")
                + "\nWhen finished call done with data = {\"task_type\": \"RETRIEVE\"|\"MUTATE\"|\"NAVIGATE\", \"status\": \"SUCCESS\" (or an error status), "
                  "\"retrieved_data\": [..] or null, \"error_details\": null or a short reason}. Use null retrieved_data for MUTATE and NAVIGATE.")


class WebArenaShopping:
    """Thin wrapper over the official `WebArenaVerified` API configured with one shopping base URL."""

    def __init__(self, base_url: str):
        from webarena_verified.api.webarena_verified import WebArenaVerified
        from webarena_verified.types.config import WebArenaVerifiedConfig
        self.base_url = base_url.rstrip("/")
        cfg = WebArenaVerifiedConfig.model_validate({"environments": {SITE_PLACEHOLDER: {"urls": [self.base_url], "active_url_idx": 0}}})
        self.wa = WebArenaVerified(config=cfg)

    def task(self, task_id: int) -> WATask:
        t = self.wa.get_task(task_id)
        raw = t.model_dump() if hasattr(t, "model_dump") else dict(t)
        evals = raw["eval"]
        ar = next(e for e in evals if e["evaluator"] == "AgentResponseEvaluator")
        return WATask(task_id=task_id, template_id=raw["intent_template_id"], intent=raw["intent"],
                      start_urls=tuple(u.replace(SITE_PLACEHOLDER, self.base_url) for u in raw["start_urls"]),
                      task_type=str(ar["expected"]["task_type"]).lower(), sites=tuple(str(s.value if hasattr(s, "value") else s) for s in raw["sites"]),
                      network_evaluators=sum(1 for e in evals if e["evaluator"] == "NetworkEventEvaluator"))

    def evaluate(self, task_id: int, answer: Any, har: Path | list[dict]) -> dict:
        """Official evaluation of (agent response, network HAR). Returns a compact, serialisable verdict."""
        res = self.wa.evaluate_task(task_id=task_id, agent_response=answer, network_trace=har)
        return {"passed": str(getattr(res.status, "value", res.status)) == "success", "score": res.score, "error": res.error_msg,
                "evaluators": [{"name": e.evaluator_name, "status": str(getattr(e.status, "value", e.status)), "assertions": [a.assertion_name for a in (e.assertions or []) if str(getattr(a.status, "value", a.status)) != "success"]}
                               for e in res.evaluators_results],
                "evaluator_version": res.webarena_verified_version, "evaluator_checksum": res.webarena_verified_evaluator_checksum, "data_checksum": res.webarena_verified_data_checksum}
