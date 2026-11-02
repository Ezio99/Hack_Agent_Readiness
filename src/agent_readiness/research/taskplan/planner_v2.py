"""Planner prompt taskplan-v2 (lifecycle M3): taskplan-v1's rules plus natural-wording guidance, the M2b task shapes (either/or via `one_of`,
'best' within a filter) and a FEEDBACK slot for targeted regeneration. Wire schema: taskplan-schema-v3. taskplan-v1 (`planner.py`) is unchanged.

The feedback slot carries only what the Stage A feedback synthesiser produces (rejection categories, wording-only examples, uncovered cells,
missing capabilities, signatures to avoid, underspecified wordings): never expected answers, agent results or variant outcomes."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from ...investigate.llm.client import LLMRequest, request_sha256
from .schema_v3 import SCHEMA_V3, json_schema_v3

PROMPT_VERSION = "taskplan-v2"
SYSTEM = ("You plan evaluation tasks for a browsing agent on a website. You propose task INTENTS for realistic customers. "
          "Rules: use ONLY the attributes listed in the catalogue, with operators equals/contains/less_than/at_most/greater_than/at_least/one_of and values in the "
          "listed domains; never state or hint at the answer in the scenario; do not invent facts, services or attributes the catalogue does not list. "
          "Write each scenario in the customer's own words. Every value a constraint uses must appear in those words (field names may be implied). "
          "If a real customer would be vague (\"a tight budget\", \"a few weeks\"), you may keep the vague wording, but then the constraint value is YOUR "
          "assumption and the task will be preserved as underspecified rather than executed: prefer stating the value. Do not add constraints the customer "
          "does not express, and express every constraint the customer does state. Either/or requests use operator one_of with 2-4 `values`; a 'best' task "
          "may carry constraints (the best item within a filtered subset). An open question (task_type 'open', answer_form 'explanation') is allowed only "
          "for policies. Return JSON matching the schema.")


def build_request(catalogue_view: dict, context: dict, n: int, *, feedback: dict | None = None, round_no: int = 1, targets: dict | None = None,
                  max_tokens: int = 6000) -> LLMRequest:
    personas = [{k: p[k] for k in ("id", "name", "needs", "constraints")} for p in context["personas"]]
    journeys = [{k: j[k] for k in ("id", "name", "weight")} for j in context["journeys"]]
    parts = [f"Business context ({context.get('label', 'unlabelled')}):\n{json.dumps({'business': context['business'], 'goals': context['goals'], 'personas': personas, 'journeys': journeys}, indent=1)}",
             f"Verified catalogue of {catalogue_view['label']} (the only facts you may use; the agent starts at {catalogue_view['start_path']} and the items are listed on "
             f"{catalogue_view['listing']}):\n{json.dumps({'attributes': catalogue_view['attributes'], 'items': catalogue_view['items']}, indent=1)}"]
    if targets:
        parts.append(f"Suite coverage targets (provisional): {json.dumps(targets, sort_keys=True)}")
    if feedback:
        parts.append(f"Round {round_no}. Feedback on the previous rounds (no answers are given; address the gaps, avoid the listed signatures):\n{json.dumps(feedback, indent=1, sort_keys=True)}")
    parts.append(f"Propose {n} diverse tasks: cover every persona and as many journeys and task shapes as possible, weighted by the illustrative priorities. Each task: intent_id, "
                 f"persona (id), journey (id), scenario (what the customer asks the agent to find out, in their own words), task_type, entity and attribute (lookup only), "
                 f"constraints, ranking (best only), answer_form, rationale.")
    return LLMRequest(messages=[{"role": "system", "content": SYSTEM}, {"role": "user", "content": "\n\n".join(parts)}], purpose="research-stage-a",
                      max_tokens=max_tokens, response_schema=json_schema_v3())


def request_record(request: LLMRequest) -> dict:
    return {"prompt_version": PROMPT_VERSION, "schema_version": SCHEMA_V3, "messages_sha256": hashlib.sha256(json.dumps(request.messages, sort_keys=True).encode()).hexdigest(),
            "request_sha256": request_sha256(request), "max_tokens": request.max_tokens, "purpose": request.purpose}


def parse_batch(text: str) -> tuple[list[dict], str | None]:
    """[{index, raw}], batch_error. Items are evaluated individually (a malformed item is rejected alone)."""
    try:
        doc = json.loads(text)
    except (TypeError, ValueError) as exc:
        return [], f"response is not JSON: {type(exc).__name__}"
    items = doc.get("tasks") if isinstance(doc, dict) else None
    if not isinstance(items, list):
        return [], "response has no 'tasks' list"
    return [{"index": i, "raw": raw} for i, raw in enumerate(items)], None


class MetaGenerator:
    """PAID. Muse Spark behind the durable reserve-before-send spend gate. Construction refuses without an explicit owner approval note.

    Enforcement lives in the gate and its fsync'd ledger (`spend_gate.RequestGate`, `ledger.Ledger`), not in this process: the request count,
    the run cap and any bound violation are re-read from the ledger, so a restart that reuses `ledger_dir` and `run_id` can never exceed them.
    Use one FIXED ledger directory per authorisation. `MetaClient.complete` sends exactly one POST per call (no retries, no redirects); a failed
    request keeps its full reservation counted. `client` may be injected (a MetaClient over a mock transport) for zero-cost rehearsals."""
    mode = "live"

    def __init__(self, ledger_dir: Path, *, approval_note: str, run_cap_usd: float, max_requests: int = 3, per_request_cap_usd: float | None = None,
                 run_id: str = "research-stage-a", client=None):
        if not approval_note.strip():
            raise PermissionError("a paid Stage A generation needs the owner's explicit approval note (and a cap)")
        from ...agent import ModelConfig
        from ...investigate.llm.meta import DEFAULT_REASONING_EFFORT, MetaClient
        from ...ledger import Ledger
        self.ledger = Ledger(Path(ledger_dir), run_cap_usd)
        self.per_request_cap = per_request_cap_usd if per_request_cap_usd is not None else run_cap_usd
        self.client = client or MetaClient.live(ModelConfig(), self.ledger, run_id, allow_model_calls=True, run_cap_usd=run_cap_usd,
                                                per_request_cap_usd=self.per_request_cap, max_requests=max_requests)
        self.model, self.reasoning_effort, self.approval_note, self.cap = self.client.model, getattr(self.client, "reasoning_effort", DEFAULT_REASONING_EFFORT), approval_note, run_cap_usd
        self.run_id, self.max_requests, self.ledger_dir = run_id, max_requests, str(ledger_dir)

    @property
    def identity(self) -> dict:
        return {"kind": "meta", "model": self.model, "reasoning_effort": self.reasoning_effort, "approval_note": self.approval_note, "run_cap_usd": self.cap,
                "per_request_cap_usd": self.per_request_cap, "max_requests": self.max_requests, "gate_run_id": self.run_id, "ledger_dir": self.ledger_dir}

    def reservation_usd(self, request: LLMRequest) -> float:
        from ...investigate.llm.meta import reservation_bound_usd
        return reservation_bound_usd(request, self.reasoning_effort)

    def complete(self, request: LLMRequest) -> LLMResponse:
        return self.client.complete(request)
