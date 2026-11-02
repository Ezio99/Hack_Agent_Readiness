"""Immutable lifecycle records (M1). Every record is a frozen pydantic model that forbids unknown fields; its identity is the canonical SHA-256 of its
JSON form (`content_hash`). Public records never contain expected answers: those live only in `PrivateOutcome`, referenced by hash.

Stage A:  TaskRecord, PrivateOutcome, SuiteRecord, Approval, FrozenSuite      (inputs limited to boundary.STAGE_A_INPUT_KINDS)
Stage B:  EvaluationManifest (references a FrozenSuite by hash), RunResult   (outcomes; never visible to Stage A)
"""
from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ..suite.core import canonical_hash
from .boundary import STAGE_A_INPUT_KINDS, STAGE_B_INPUT_KINDS

SCHEMA = "suites-records-v1"
WORDING_CATEGORIES = ("natural_verifiable", "natural_underspecified", "natural_judgment", "assisted_restatement")
VERIFIABILITY = ("deterministic", "rubric", "human_review")
CONDITIONS = ("natural", "assisted")
ANSWER_KEYS = {"expected", "expected_answer", "answer", "answers", "truth", "solution", "correct_answer"}
SHA = re.compile(r"^[0-9a-f]{64}$")


class Record(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    def content(self) -> dict:
        return self.model_dump(mode="json")


def content_hash(record: Record) -> str:
    return canonical_hash(record.content())


def _sha(v: str) -> str:
    if not SHA.match(v or ""):
        raise ValueError("expected a 64-character lowercase hex SHA-256")
    return v


def _no_answer_keys(obj: Any, where: str) -> None:
    if isinstance(obj, dict):
        bad = sorted(k for k in obj if str(k).lower() in ANSWER_KEYS)
        if bad:
            raise ValueError(f"{where} may not carry answer fields ({', '.join(bad)}); expected outcomes belong in PrivateOutcome")
        for v in obj.values():
            _no_answer_keys(v, where)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            _no_answer_keys(v, where)


# ------------------------------------------------------------------------------------------------------------------------------- provenance
class InputRef(Record):
    kind: str
    name: str = Field(min_length=1, max_length=200)
    sha256: str

    @field_validator("sha256")
    @classmethod
    def check_sha(cls, v):
        return _sha(v)


class Provenance(Record):
    created_at: str = Field(min_length=10)                          # ISO 8601, supplied by the caller (records are deterministic given their inputs)
    created_by: str = Field(min_length=1, max_length=60)            # a role ("owner", "system", "llm-generator"), never a personal identifier or credential
    tool: str = Field(min_length=1)
    tool_version: str = Field(min_length=1)
    config_fingerprint: str | None = None
    inputs: tuple[InputRef, ...] = ()
    notes: str = ""

    def require_kinds(self, allowed: tuple[str, ...], stage: str) -> None:
        bad = [i.kind for i in self.inputs if i.kind not in allowed]
        if bad:
            raise ValueError(f"{stage} records may not take inputs of kind {sorted(set(bad))} (allowed: {', '.join(allowed)})")


# ------------------------------------------------------------------------------------------------------------------------------- tasks
class Wording(Record):
    customer: str = Field(min_length=1, max_length=600)              # the customer's own words, preserved verbatim
    executed: str | None = Field(default=None, max_length=1200)       # what the agent is given; None when the task is not executed deterministically
    category: Literal[WORDING_CATEGORIES]
    interpretation_decisions: tuple[str, ...] = ()                     # e.g. "field implied by a value unique to the class-day domain"
    assumptions: tuple[str, ...] = ()                                   # any value or constraint NOT stated by the customer
    unresolved: tuple[str, ...] = ()                                    # what an underspecified request leaves open (preserved, never invented)

    @model_validator(mode="after")
    def _category_rules(self):
        c = self.category
        if c in ("natural_verifiable", "natural_judgment"):
            if self.executed != self.customer:
                raise ValueError(f"{c}: the executed wording must be the customer wording, unchanged")
            if self.assumptions or self.unresolved:
                raise ValueError(f"{c}: no assumptions or unresolved values allowed")
        elif c == "natural_underspecified":
            if not self.unresolved:
                raise ValueError("natural_underspecified: list what the request leaves unresolved")
            if self.executed is not None:
                raise ValueError("natural_underspecified: not executed until a clarification is recorded (then it becomes assisted_restatement)")
        elif c == "assisted_restatement":
            if not self.executed or self.executed == self.customer:
                raise ValueError("assisted_restatement: the executed wording must be an explicit restatement, different from the customer wording")
        return self

    @property
    def condition(self) -> str | None:
        return {"natural_verifiable": "natural", "natural_judgment": "natural", "assisted_restatement": "assisted"}.get(self.category)


class Limits(Record):
    max_steps: int = Field(gt=0, le=64)
    max_model_requests: int = Field(gt=0, le=64)
    timeout_seconds: int = Field(gt=0, le=3600)


class TaskSpec(Record):
    kind: str = Field(min_length=1)                                     # page_fact | item_set | extremum | ... (criterion language)
    criterion: dict                                                      # PUBLIC structured specification: labels, operators, thresholds; never the answer
    verifiability: Literal[VERIFIABILITY]
    evidence_paths: tuple[str, ...] = ()                                 # pages that hold or lead to the answer (paths only; evidence TEXTS are private)

    @field_validator("criterion")
    @classmethod
    def _criterion(cls, v):
        _no_answer_keys(v, "a task specification")
        return v


class Validation(Record):
    evaluator: str
    evaluator_version: str
    config_fingerprint: str
    passed: bool
    reasons: tuple[str, ...] = ()


class PrivateOutcome(Record):
    """The independently derived expected outcome. PRIVATE: stored separately, never in a public view, never shown to an agent."""
    spec_sha256: str
    expected: Any
    evidence_texts: tuple[tuple[str | None, str], ...] = ()
    oracle: str = Field(min_length=1)
    derived_from_snapshot: str

    @field_validator("spec_sha256", "derived_from_snapshot")
    @classmethod
    def check_sha(cls, v):
        return _sha(v)


class TaskRecord(Record):
    task_id: str = Field(pattern=r"^[A-Za-z0-9._-]{1,80}$")
    site: str = Field(min_length=1)
    persona: str | None = None
    journey: str | None = None
    capability: str = Field(min_length=1)
    wording: Wording
    spec: TaskSpec
    limits: Limits
    private_sha256: str | None                                          # the PrivateOutcome hash; None only for rubric / human-review tasks
    validation: Validation
    provenance: Provenance

    @field_validator("private_sha256")
    @classmethod
    def check_sha(cls, v):
        return v if v is None else _sha(v)

    @model_validator(mode="after")
    def _consistency(self):
        self.provenance.require_kinds(STAGE_A_INPUT_KINDS, "Stage A")
        c, ver = self.wording.category, self.spec.verifiability
        allowed = {"natural_verifiable": ("deterministic",), "assisted_restatement": ("deterministic",), "natural_judgment": ("rubric", "human_review"),
                   "natural_underspecified": ("human_review",)}[c]
        if ver not in allowed:
            raise ValueError(f"wording category {c} requires verifiability in {allowed}, not {ver}")
        if ver == "deterministic" and not self.private_sha256:
            raise ValueError("a deterministic task needs a private expected outcome")
        return self

    @property
    def condition(self) -> str | None:
        return self.wording.condition


# ------------------------------------------------------------------------------------------------------------------------------- suites
class SuiteRecord(Record):
    suite_name: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]{0,63}$")
    version: int = Field(ge=1)
    site: str
    stage: Literal["A"] = "A"
    task_sha256s: tuple[str, ...] = Field(min_length=1)
    selection_rule: str = Field(min_length=1)
    coverage: dict = Field(default_factory=dict)
    gaps: tuple[str, ...] = ()
    agent_evidence_consulted: Literal[False] = False                    # Stage A never sees agent outcomes
    provenance: Provenance

    @model_validator(mode="after")
    def _rules(self):
        for t in self.task_sha256s:
            _sha(t)
        if len(set(self.task_sha256s)) != len(self.task_sha256s):
            raise ValueError("a suite lists each task once")
        self.provenance.require_kinds(STAGE_A_INPUT_KINDS, "Stage A")
        _no_answer_keys(self.coverage, "suite coverage")
        return self


class Approval(Record):
    suite_sha256: str
    decision: Literal["approved", "rejected"]
    approver_role: Literal["owner"] = "owner"                         # decision 7: human approval, initially the owner
    approved_at: str = Field(min_length=10)
    notes: str = ""

    @field_validator("suite_sha256")
    @classmethod
    def check_sha(cls, v):
        return _sha(v)


class FrozenSuite(Record):
    suite_sha256: str
    approval_sha256: str
    frozen_at: str = Field(min_length=10)

    @field_validator("suite_sha256", "approval_sha256")
    @classmethod
    def check_sha(cls, v):
        return _sha(v)


# ------------------------------------------------------------------------------------------------------------------------------- Stage B
def min_p_sign_flip(n_pairs: int) -> float:
    """Smallest two-sided p-value an exact sign-flip test over n task pairs can produce: 2 / 2^n (necessary, not sufficient, for a confirmatory design)."""
    return 2 / 2 ** n_pairs if n_pairs > 0 else 1.0


class StatisticalPlan(Record):
    designation: Literal["confirmatory", "exploratory"]
    primary_outcome: str = Field(min_length=1)
    comparison_rule: str = Field(min_length=1)                          # e.g. "paired-exact-sign-flip"
    alpha: float = Field(default=0.05, gt=0, lt=1)
    unit_of_analysis: Literal["task"] = "task"                          # repetitions are clustered within tasks: aggregated per task and variant
    clustering: str = "repetitions aggregated per task and variant; tasks are the unit of analysis"
    n_tasks: int = Field(gt=0)
    repetitions: int = Field(gt=0)
    analysis: str = Field(min_length=1)
    stopping_rule: str = Field(min_length=1)
    feasibility: dict | None = None                                      # {min_achievable_p, minimum_detectable_effect | power, assumptions, feasible}

    @model_validator(mode="after")
    def _confirmatory(self):
        if self.designation == "confirmatory":
            f = self.feasibility or {}
            if not f.get("feasible") or f.get("min_achievable_p") is None or not ({"minimum_detectable_effect", "power"} & set(f)):
                raise ValueError("a confirmatory plan needs a feasibility assessment (min_achievable_p and a minimum detectable effect or power) marked feasible")
            if f["min_achievable_p"] > self.alpha:
                raise ValueError(f"infeasible: the smallest achievable p ({f['min_achievable_p']}) exceeds alpha ({self.alpha}); run as exploratory")
            if self.comparison_rule == "paired-exact-sign-flip" and abs(f["min_achievable_p"] - min_p_sign_flip(self.n_tasks)) > 1e-12:
                raise ValueError("min_achievable_p does not match the exact sign-flip test for n_tasks")
        return self


class AgentConfig(Record):
    model: str
    endpoint: str
    reasoning_effort: str | None
    max_completion_tokens: int = Field(gt=0)
    profile: str
    profile_sha256: str
    jail_policy_sha256: str | None = None


class EvaluationManifest(Record):
    stage: Literal["B"] = "B"
    frozen_suite_sha256: str
    variants: tuple[tuple[str, str], ...] = Field(min_length=1)          # (variant name, snapshot sha256)
    conditions: tuple[Literal[CONDITIONS], ...] = ("natural",)            # conditions executed; never pooled in analysis
    oracle: str
    graders: dict                                                         # {"official": ..., "post_hoc": [...]}
    agent: AgentConfig
    repetitions: int = Field(gt=0)
    seed: int
    void_policy: str = "no retries; void trials excluded and listed"
    plan: StatisticalPlan
    budget: dict
    provenance: Provenance

    @model_validator(mode="after")
    def _rules(self):
        _sha(self.frozen_suite_sha256)
        for _, s in self.variants:
            _sha(s)
        self.provenance.require_kinds(STAGE_B_INPUT_KINDS, "Stage B")
        if self.plan.repetitions != self.repetitions:
            raise ValueError("the plan's repetitions must match the manifest")
        return self


class RunResult(Record):
    """A Stage B outcome reference (summary and evidence pointer). Never readable by Stage A."""
    manifest_sha256: str
    variant: str
    condition: Literal[CONDITIONS]
    summary: dict
    evidence_dir_sha256: str | None = None
    provenance: Provenance

    @field_validator("manifest_sha256")
    @classmethod
    def check_sha(cls, v):
        return _sha(v)


KINDS = {TaskRecord: "task", PrivateOutcome: "private_outcome", SuiteRecord: "suite", Approval: "approval", FrozenSuite: "frozen_suite",
         EvaluationManifest: "manifest", RunResult: "run_result"}
BY_KIND = {v: k for k, v in KINDS.items()}


def public_task_view(task: TaskRecord) -> dict:
    """The shareable form of a task: the record itself (it never holds the answer) plus its hash."""
    return {"sha256": content_hash(task), **task.content()}
