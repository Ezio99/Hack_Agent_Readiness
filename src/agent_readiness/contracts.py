"""Public wire contracts. Deliberately independent of inventory/evaluator imports."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class Answer(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    product_id: str = Field(min_length=1)
    price_cents: int = Field(ge=0)
    available: bool


class PublicTask(BaseModel):
    model_config = ConfigDict(frozen=True)
    task_id: str
    kind: Literal["discovery", "availability"]
    prompt: str
    permitted_actions: tuple[str, ...] = ("browse", "search", "filter", "read_detail")


class Evaluation(BaseModel):
    passed: bool
    reasons: list[str]
