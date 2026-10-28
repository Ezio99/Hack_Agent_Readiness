"""Domain-extensible task and environment contracts. This module must not import any concrete environment (tests enforce it).

Concepts
- Environment: a versioned website (environment_id, data_version) that can be served in controlled *variants* (website design factors).
- TaskTemplate: builds deterministic TaskInstances for an environment from named fixtures. A template owns an answer model (public
  schema), an independent oracle (private truth computed from the environment's data, never served) and a grader.
- TaskSpec: the public, frozen task record shown to an agent/scanner: objective, answer schema, limits, start path, outcome type and the
  evidence requirements. It never contains the truth.
- TaskInstance: spec + private truth + the callables needed to grade. Truth stays server/evaluator side.
- Grade/EvaluationRecord: independent verdict (answer correctness), with evidence tracked separately: ``passed`` is answer correctness
  only; ``evidence_backed`` additionally requires that the required evidence pages were actually observed.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Mapping, Protocol

from pydantic import BaseModel, ValidationError

CONTRACT_VERSION = "suite-contract-v1"
OUTCOME_TYPES = ("unique", "set", "any_valid")   # one correct answer / a complete eligible set / any single eligible choice


@dataclass(frozen=True)
class Limits:
    max_steps: int = 12
    timeout_seconds: int = 240
    max_model_requests: int = 12


@dataclass(frozen=True)
class EvidenceRequirement:
    """Evidence the agent must have been shown for the answer to count as evidence-backed.

    kinds: ``visited_path`` (exact URL path observed), ``visited_prefix`` (path prefix observed), ``observed_text`` (the text ``value`` appeared in an observation,
    optionally restricted to ``path``) and ``observed_text_any`` (any of the ``|``-separated alternatives appeared). Text kinds check what the model-visible page view
    actually contained - stronger than "the URL was visited", though still not proof that the model read or understood it (screenshot-only content is not covered)."""
    kind: str
    value: str
    why: str
    path: str | None = None


@dataclass(frozen=True)
class Observation:
    """One page view the agent was given: the URL path (no query) and the text of the model-visible view (None when unavailable)."""
    path: str
    text: str | None = None


@dataclass(frozen=True)
class Variant:
    """A controlled website configuration. ``factors`` maps factor name -> level; the id is stable and recorded in every result."""
    environment_id: str
    factors: tuple[tuple[str, str], ...]

    @property
    def variant_id(self) -> str:
        return f"{self.environment_id}/" + "+".join(f"{k}-{v}" for k, v in self.factors)

    def factor(self, name: str) -> str:
        return dict(self.factors)[name]


@dataclass(frozen=True)
class TaskSpec:
    task_id: str
    template_id: str
    version: str
    environment_id: str
    data_version: str
    objective: str
    answer_schema: Mapping[str, Any]
    start_path: str
    outcome_type: str
    evidence_policy: str                      # public, human-readable description of the evidence expected (the concrete pages are private)
    limits: Limits
    evaluator_id: str
    evaluator_version: str
    parameters: Mapping[str, Any] = field(default_factory=dict)   # public, non-sensitive fixture parameters (e.g. a stated budget)

    def public(self) -> dict:
        """What an agent or a public API may see: no truth, no oracle, no concrete evidence pages."""
        return {"task_id": self.task_id, "objective": self.objective, "answer_schema": dict(self.answer_schema), "start_path": self.start_path,
                "limits": asdict(self.limits), "outcome_type": self.outcome_type, "evidence_policy": self.evidence_policy}

    def record(self) -> dict:
        """The full, versioned record stored with results."""
        d = asdict(self)
        d["contract_version"] = CONTRACT_VERSION
        return d


@dataclass(frozen=True)
class Grade:
    passed: bool
    reasons: tuple[str, ...]
    details: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TaskInstance:
    spec: TaskSpec
    truth: Mapping[str, Any]                                # PRIVATE: produced by the oracle, never served or sent to an agent
    answer_model: type[BaseModel]
    grader: Callable[["TaskInstance", BaseModel], Grade]
    evidence: tuple[EvidenceRequirement, ...] = ()          # PRIVATE: concrete pages that must have been observed (may reveal the answer)


@dataclass(frozen=True)
class EvaluationRecord:
    task_id: str
    template_id: str
    task_version: str
    environment_id: str
    data_version: str
    variant_id: str
    evaluator_id: str
    evaluator_version: str
    contract_version: str
    answer_valid: bool
    passed: bool
    evidence_satisfied: bool
    evidence_backed: bool
    missing_evidence: tuple[str, ...]
    reasons: tuple[str, ...]
    details: Mapping[str, Any]

    def as_dict(self) -> dict:
        return asdict(self)


class Environment(Protocol):
    environment_id: str
    data_version: str

    def variants(self) -> list[Variant]: ...
    def default_variant(self) -> Variant: ...
    def create_app(self, variant: Variant): ...


class TaskTemplate(Protocol):
    template_id: str
    version: str
    environment_id: str
    def fixtures(self) -> list[str]: ...
    def build(self, fixture_id: str) -> TaskInstance: ...


ENVIRONMENTS: dict[str, Environment] = {}
TEMPLATES: dict[str, TaskTemplate] = {}


def register_environment(env: Environment) -> Environment:
    ENVIRONMENTS[env.environment_id] = env
    return env


def register_template(template: TaskTemplate) -> TaskTemplate:
    TEMPLATES[template.template_id] = template
    return template


def all_instances(environment_id: str | None = None) -> list[TaskInstance]:
    return [t.build(f) for t in TEMPLATES.values() if environment_id in (None, t.environment_id) for f in t.fixtures()]


def _as_observations(observed) -> list[Observation] | None:
    if observed is None:
        return None
    return [o if isinstance(o, Observation) else Observation(str(o).split("?", 1)[0], None) for o in observed]


def evidence_gaps(instance: TaskInstance, observed) -> list[str]:
    """Required evidence not present among the observations (paths without query; text kinds need the observation text)."""
    obs = [Observation(o.path.split("?", 1)[0], o.text) for o in (_as_observations(observed) or [])]
    missing = []
    for req in instance.evidence:
        scope = [o for o in obs if req.path is None or o.path == req.path]
        if req.kind == "visited_path":
            hit = any(o.path == req.value for o in obs)
        elif req.kind == "visited_prefix":
            hit = any(o.path.startswith(req.value) for o in obs)
        elif req.kind == "observed_text":
            hit = any(o.text is not None and req.value in o.text for o in scope)
        elif req.kind == "observed_text_any":
            hit = any(o.text is not None and any(alt in o.text for alt in req.value.split("|")) for o in scope)
        else:
            raise ValueError(f"unknown evidence kind {req.kind!r}")
        if not hit:
            missing.append(f"{req.kind}:{req.value}" + (f" on {req.path}" if req.path else "") + f" ({req.why})")
    return missing


def evaluate(instance: TaskInstance, raw_answer: object, variant: Variant, observed=None) -> EvaluationRecord:
    """Independent evaluation. The agent's own claims are never consulted: only the answer payload, the observations (URL paths and model-visible page text; plain path strings are accepted and can only satisfy path-based evidence) and private truth."""
    spec = instance.spec
    base = dict(task_id=spec.task_id, template_id=spec.template_id, task_version=spec.version, environment_id=spec.environment_id,
                data_version=spec.data_version, variant_id=variant.variant_id, evaluator_id=spec.evaluator_id,
                evaluator_version=spec.evaluator_version, contract_version=CONTRACT_VERSION)
    try:
        answer = instance.answer_model.model_validate(raw_answer)
    except ValidationError as exc:
        return EvaluationRecord(**base, answer_valid=False, passed=False, evidence_satisfied=False, evidence_backed=False,
                                missing_evidence=(),
                                reasons=("Malformed answer: does not match the task's answer schema",), details={"validation_errors": [
                                    {"loc": [str(p) for p in e["loc"]], "type": e["type"]} for e in exc.errors(include_input=False)[:10]]})
    grade = instance.grader(instance, answer)
    gaps = evidence_gaps(instance, observed) if observed is not None else []
    satisfied = observed is not None and not gaps
    return EvaluationRecord(**base, answer_valid=True, passed=grade.passed, evidence_satisfied=satisfied, evidence_backed=grade.passed and satisfied,
                            missing_evidence=tuple(gaps), reasons=grade.reasons, details=dict(grade.details))


def canonical_hash(obj: Any) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()
