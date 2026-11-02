"""taskplan-schema-v3 (lifecycle M2b): the v1 proposal schema plus an either/or constraint (operator `one_of` with 2-4 `values` on one text
attribute). A 'best' task may carry constraints (ranked within a filter). taskplan-schema-v1/v2 and `schema.parse_item` are unchanged; every
v1-valid proposal parses to the same fields here. The LLM still proposes INTENTS only: answer-like fields are stripped before validation."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from .schema import ANSWER_LIKE, OPERATORS, Ranking, _strict

SCHEMA_V3 = "taskplan-schema-v3"
OPERATORS_V3 = OPERATORS + ("one_of",)


class ConstraintV3(BaseModel):
    model_config = ConfigDict(extra="forbid")
    attribute: str = Field(min_length=1, max_length=40)
    operator: Literal[OPERATORS_V3]
    value: str | None = Field(default=None, min_length=1, max_length=60)
    values: list[str] | None = Field(default=None, max_length=4)

    @model_validator(mode="after")
    def _shape(self):
        if self.operator == "one_of":
            if not self.values or len(self.values) < 2 or self.value not in (None, ""):
                raise ValueError("one_of needs 2-4 `values` and no `value`")
            if len({v.strip().casefold() for v in self.values}) != len(self.values) or any(not v.strip() or len(v) > 60 for v in self.values):
                raise ValueError("one_of values must be distinct, non-empty and at most 60 characters")
        elif not self.value or self.values:
            raise ValueError(f"{self.operator} needs a single `value` and no `values`")
        return self


class ProposalV3(BaseModel):
    model_config = ConfigDict(extra="forbid")
    intent_id: str = Field(min_length=1, max_length=40)
    persona: str = Field(min_length=1, max_length=40)
    journey: str = Field(min_length=1, max_length=40)
    scenario: str = Field(min_length=10, max_length=400)
    task_type: Literal["lookup", "filter", "best", "open"]
    entity: str | None = Field(default=None, max_length=80)
    attribute: str | None = Field(default=None, max_length=40)
    constraints: list[ConstraintV3] = Field(default_factory=list, max_length=3)
    ranking: Ranking | None = None
    answer_form: Literal["single", "list", "explanation"]
    rationale: str = Field(default="", max_length=300)


def parse_item_v3(raw) -> tuple[ProposalV3 | None, dict, list[str]]:
    if not isinstance(raw, dict):
        return None, {}, ["not an object"]
    stripped = {k: raw[k] for k in raw if k.lower() in ANSWER_LIKE}
    clean = {k: v for k, v in raw.items() if k.lower() not in ANSWER_LIKE}
    if isinstance(clean.get("constraints"), list):                    # strict-mode wire format: absent optionals arrive as null
        clean["constraints"] = [{k: v for k, v in c.items() if not (k in ("value", "values") and v is None)} if isinstance(c, dict) else c for c in clean["constraints"]]
    try:
        return ProposalV3.model_validate(clean), stripped, []
    except ValidationError as exc:
        return None, stripped, [f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors()][:6]


def json_schema_v3() -> dict:
    s = ProposalV3.model_json_schema()
    doc = {"type": "object", "additionalProperties": False, "required": ["tasks"], "properties": {"tasks": {"type": "array", "items": s}}, "$defs": s.pop("$defs", {})}
    return _strict(doc)
