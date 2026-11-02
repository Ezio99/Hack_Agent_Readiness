"""Structured task proposals. The LLM proposes INTENTS (what a persona wants and which verified attributes constrain it); it never supplies a trusted
expected answer. Any answer-like field it adds is stripped and recorded, and the expected outcome is derived by the oracle in verify.py."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

OPERATORS = ("equals", "contains", "less_than", "at_most", "greater_than", "at_least")
ANSWER_LIKE = ("answer", "answers", "expected", "expected_answer", "solution", "correct_answer", "truth")


class Constraint(BaseModel):
    model_config = ConfigDict(extra="forbid")
    attribute: str = Field(min_length=1, max_length=40)
    operator: Literal[OPERATORS]
    value: str = Field(min_length=1, max_length=60)


class Ranking(BaseModel):
    model_config = ConfigDict(extra="forbid")
    attribute: str = Field(min_length=1, max_length=40)
    direction: Literal["highest", "lowest"]


class Proposal(BaseModel):
    model_config = ConfigDict(extra="forbid")
    intent_id: str = Field(min_length=1, max_length=40)
    persona: str = Field(min_length=1, max_length=40)
    journey: str = Field(min_length=1, max_length=40)
    scenario: str = Field(min_length=10, max_length=400)           # the natural-language task given to the agent
    task_type: Literal["lookup", "filter", "best", "open"]           # one item's attribute | items meeting constraints | best item by a ranking | open question
    entity: str | None = Field(default=None, max_length=80)          # lookup only: the item's name
    attribute: str | None = Field(default=None, max_length=40)       # lookup only: which attribute of that item
    constraints: list[Constraint] = Field(default_factory=list, max_length=3)
    ranking: Ranking | None = None
    answer_form: Literal["single", "list", "explanation"]
    rationale: str = Field(default="", max_length=300)


def json_schema() -> dict:
    """Strict structured-output schema for the batch."""
    s = Proposal.model_json_schema()
    return {"type": "object", "additionalProperties": False, "required": ["tasks"],
            "properties": {"tasks": {"type": "array", "items": s}}, "$defs": s.pop("$defs", {})}


def parse_item(raw) -> tuple[Proposal | None, dict, list[str]]:
    """(proposal or None, stripped answer-like fields, schema errors). Answer-like fields are removed BEFORE validation and kept only as a record."""
    if not isinstance(raw, dict):
        return None, {}, ["not an object"]
    stripped = {k: raw[k] for k in raw if k.lower() in ANSWER_LIKE}
    clean = {k: v for k, v in raw.items() if k.lower() not in ANSWER_LIKE}
    try:
        return Proposal.model_validate(clean), stripped, []
    except ValidationError as exc:
        return None, stripped, [f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors()][:6]


# --------------------------------------------------------------------------------------------------- taskplan-schema-v2 (wire format only)
SCHEMA_V1, SCHEMA_V2 = "taskplan-schema-v1", "taskplan-schema-v2"
PROVEN_KEYWORDS = {"$ref", "additionalProperties", "anyOf", "description", "enum", "items", "required", "title", "type"}   # used by schemas Meta has accepted live
WIRE_ONLY_DROP = ("default", "minLength", "maxLength", "minItems", "maxItems")   # still enforced by the pydantic parser on our side


def _strict(node):
    if isinstance(node, list):
        return [_strict(x) for x in node]
    if not isinstance(node, dict):
        return node
    out = {k: _strict(v) for k, v in node.items() if k not in WIRE_ONLY_DROP}
    if "properties" in out:
        out["required"] = list(out["properties"].keys())        # Meta strict mode: every property listed; optional ones are nullable or may be empty
        out["additionalProperties"] = False
        out.setdefault("type", "object")
    return out


def json_schema_v2() -> dict:
    """taskplan-schema-v2: the v1 schema made strict-compatible for Meta. Every object lists ALL its properties in `required` with
    additionalProperties false; optional values stay representable (entity/attribute/ranking are `anyOf [..., null]`, constraints may be [] and
    rationale may be ""); only keywords already accepted live are used. Parsing and validation (`parse_item`, the pydantic model) are unchanged."""
    return _strict(json_schema())


SCHEMAS = {SCHEMA_V1: json_schema, SCHEMA_V2: json_schema_v2}
