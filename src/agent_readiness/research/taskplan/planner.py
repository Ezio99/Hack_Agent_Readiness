"""The LLM task planner: a versioned prompt over the SYNTHETIC business context and the VERIFIED catalogue view, a structured-output request, and
per-item parsing. Clients: a fixture (offline; not model output) or Meta Muse Spark behind an explicit approval with a research-local ledger."""
from __future__ import annotations

import json
from pathlib import Path

from ...investigate.llm.client import LLMRequest, request_sha256
from . import context as C
from .schema import json_schema, parse_item

PROMPT_VERSION = "taskplan-v1"
SYSTEM = ("You plan evaluation tasks for a browsing agent on a website. You propose task INTENTS for realistic customers. "
          "Rules: use ONLY the attributes listed in the catalogue, with operators equals/contains/less_than/at_most/greater_than/at_least and values in the "
          "listed domains; never state or hint at the answer in the scenario; do not invent facts, services or attributes the catalogue does not list; "
          "an open question (task_type 'open', answer_form 'explanation') is allowed only for policies. Return JSON matching the schema.")


def build_request(catalogue_view: dict, n: int, *, max_tokens: int = 6000) -> LLMRequest:
    personas = [{k: p[k] for k in ("id", "name", "needs", "constraints")} for p in C.CONTEXT["personas"]]
    journeys = [{k: j[k] for k in ("id", "name", "weight")} for j in C.CONTEXT["journeys"]]
    user = (f"Business context ({C.LABEL}):\n{json.dumps({'business': C.CONTEXT['business'], 'goals': C.CONTEXT['goals'], 'personas': personas, 'journeys': journeys}, indent=1)}\n\n"
            f"Verified catalogue of {catalogue_view['label']} (the only facts you may use; the agent starts at {catalogue_view['start_path']} and the items are listed on "
            f"{catalogue_view['listing']}):\n{json.dumps({'attributes': catalogue_view['attributes'], 'items': catalogue_view['items']}, indent=1)}\n\n"
            f"Propose {n} diverse tasks: cover every persona and as many journeys as possible, weighted by the illustrative priorities. Each task: intent_id, persona (id), "
            f"journey (id), scenario (what the customer asks the agent to find out, in their own words), task_type, entity and attribute (lookup only), constraints, ranking (best only), "
            f"answer_form, rationale.")
    return LLMRequest(messages=[{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}], purpose="research-taskplan", max_tokens=max_tokens,
                      response_schema=json_schema())


def parse_batch(text: str) -> tuple[list[dict], str | None]:
    """[{index, raw, proposal, stripped, errors}], batch_error. A malformed item is rejected alone; the rest of the batch is kept."""
    try:
        doc = json.loads(text)
    except (TypeError, ValueError) as exc:
        return [], f"response is not JSON: {type(exc).__name__}"
    items = doc.get("tasks") if isinstance(doc, dict) else None
    if not isinstance(items, list):
        return [], "response has no 'tasks' list"
    out = []
    for i, raw in enumerate(items):
        p, stripped, errors = parse_item(raw)
        out.append({"index": i, "raw": raw, "proposal": p, "stripped_answer_fields": stripped, "schema_errors": errors})
    return out, None


FIXTURE = Path(__file__).with_name("fixtures") / "larkspur-fixture-v1.json"


def fixture_client():
    """A deterministic stand-in. Its proposals were WRITTEN BY THE DEVELOPER to exercise every validation path (valid, multi-constraint, hallucinated
    attributes, out-of-domain values, unsupported shapes, answer leaks, duplicates, malformed items). It is NOT model output."""
    from ...investigate.llm.scripted import ScriptedClient
    return ScriptedClient([FIXTURE.read_text()])


def meta_client(ledger_dir: Path, *, approval_note: str, run_cap_usd: float, max_requests: int):
    """Muse Spark with a research-local ledger and the reserve-before-send gate. Refuses without an explicit owner approval note."""
    if not approval_note.strip():
        raise PermissionError("a paid planner request needs the owner's explicit approval (pass --approval-note)")
    from ...agent import ModelConfig
    from ...investigate.llm.meta import MetaClient
    from ...ledger import Ledger
    return MetaClient.live(ModelConfig(), Ledger(Path(ledger_dir), run_cap_usd), "research-taskplan", allow_model_calls=True, run_cap_usd=run_cap_usd,
                           per_request_cap_usd=run_cap_usd, max_requests=max_requests)


def request_record(request: LLMRequest) -> dict:
    return {"prompt_version": PROMPT_VERSION, "request_sha256": request_sha256(request), "max_tokens": request.max_tokens, "purpose": request.purpose}
