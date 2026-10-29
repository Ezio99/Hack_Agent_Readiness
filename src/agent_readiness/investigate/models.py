"""evidence-v1: the five kinds of record an investigation produces, kept strictly apart (plan D6).

    Observation  a deterministic fact (probe / snapshot / trace metric)
    Hypothesis   a CLAIM, never a fact. tier `verifiable` (closed claim grammar, has a registered verifier) or `novel` (open-ended, UNVERIFIED, needs a falsifiable prediction)
    Finding      created ONLY by `EvidenceStore.promote` (code, not the model) from a verifiable hypothesis that a verifier supported, with enough independent support
    Proposal     a proposed change; `basis` says whether it rests on a verified finding or on an unverified hypothesis (the latter is always labelled EXPERIMENTAL)
    Effect       a measured result; only `mode == "live"` counts as measured

Ids are content-derived, so replaying the same events reproduces the same ids."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

SCHEMA = "evidence-v1"
Mode = Literal["scripted", "mock", "recorded", "live"]
Tier = Literal["verifiable", "novel"]
HypothesisStatus = Literal["unverified", "supported", "refuted", "unverifiable"]
Attribution = Literal["website", "tool_interface", "agent", "task_invalid", "infrastructure", "provider_or_budget", "undetermined"]
WEBSITE_ATTRIBUTIONS = ("website", "tool_interface")          # only these may become a website finding
# The closed grammar (plan D8). Verifiers are registered in a later milestone; a `verifiable` hypothesis must use one of these names.
CLAIM_KINDS = ("info_absent_on_template", "info_only_after_k_hops", "control_unlabeled", "observation_missing_dom_content", "repeated_navigation",
               "inconsistent_content_across_pages", "error_response_on_path", "step_overhead_vs_minimum")
MIN_INDEPENDENT_SUPPORT = 2


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def content_id(prefix: str, core: Any) -> str:
    return f"{prefix}-{hashlib.sha256(json.dumps(core, sort_keys=True, separators=(',', ':'), default=str).encode()).hexdigest()[:10]}"


class Provenance(BaseModel):
    mode: Mode
    source: str                      # e.g. "rule:snapshot", "llm:muse-spark-1.3", "owner"
    created_at: str = Field(default_factory=now)


class Observation(BaseModel):
    id: str = ""
    kind: str
    summary: str
    data: dict = Field(default_factory=dict)
    refs: list[str] = Field(default_factory=list)            # e.g. "page:/p/1", "trial:t1#step3"
    provenance: Provenance

    @model_validator(mode="after")
    def _id(self):
        self.id = self.id or content_id("obs", [self.kind, self.summary, self.data, self.refs])
        return self


class Verification(BaseModel):
    verifier: str
    result: Literal["supported", "refuted", "unverifiable"]
    evidence: list[str] = Field(default_factory=list)
    provenance: Provenance


class Hypothesis(BaseModel):
    id: str = ""
    tier: Tier
    statement: str
    claim_kind: str | None = None                            # required for `verifiable`
    params: dict = Field(default_factory=dict)
    prediction: str | None = None                            # required for `novel`: "if X changed, metric Y on tasks Z would move in direction D"
    citations: list[str] = Field(default_factory=list)       # observation ids this rests on (must exist)
    status: HypothesisStatus = "unverified"
    verification: Verification | None = None
    provenance: Provenance

    @model_validator(mode="after")
    def _check(self):
        if not self.citations:
            raise ValueError("a hypothesis must cite at least one observation")
        if self.tier == "verifiable":
            if self.claim_kind not in CLAIM_KINDS:
                raise ValueError(f"a verifiable hypothesis must use one of the grammar's claim kinds {CLAIM_KINDS}")
        else:
            if self.claim_kind is not None:
                raise ValueError("a novel hypothesis is free-form and has no claim_kind")
            if not (self.prediction or "").strip():
                raise ValueError("a novel hypothesis needs a falsifiable prediction")
        self.id = self.id or content_id("hyp", [self.tier, self.statement, self.claim_kind, self.params, self.prediction])
        return self


class Finding(BaseModel):
    id: str = ""
    hypothesis_id: str
    statement: str
    attribution: Attribution
    support: list[str]                                       # independent trial / task refs (or a structural proof marker)
    structural_proof: bool = False
    provenance: Provenance

    @model_validator(mode="after")
    def _id(self):
        self.id = self.id or content_id("fnd", [self.hypothesis_id, self.attribution, sorted(self.support)])
        return self


class Proposal(BaseModel):
    id: str = ""
    basis: Literal["verified_finding", "unverified_hypothesis"]
    source_id: str                                           # Finding id or Hypothesis id
    change: dict                                             # a patch spec ({"ops": [...]}) or {"manual": "text"} (not auto-applicable)
    expected_effect: str
    risks: list[str] = Field(default_factory=list)
    status: Literal["proposed", "approved", "applied", "measured"] = "proposed"
    validation: Literal["unvalidated"] = "unvalidated"       # a proposal is never "validated"; only an Effect says something was measured
    approvals: list[dict] = Field(default_factory=list)
    provenance: Provenance

    @property
    def auto_applicable(self) -> bool:
        return "manual" not in self.change

    @property
    def label(self) -> str:
        return ("VERIFIED-FINDING PROPOSAL (unvalidated until measured)" if self.basis == "verified_finding"
                else "EXPERIMENTAL — based on an unverified hypothesis, not a verified finding")

    @model_validator(mode="after")
    def _id(self):
        self.id = self.id or content_id("prp", [self.basis, self.source_id, self.change])
        return self


class Effect(BaseModel):
    id: str = ""
    proposal_id: str
    verdict: Literal["improvement", "regression", "inconclusive"]
    metrics: dict = Field(default_factory=dict)
    n_pairs: int = 0
    note: str = ""
    provenance: Provenance

    @property
    def measured(self) -> bool:
        return self.provenance.mode == "live"

    @model_validator(mode="after")
    def _id(self):
        self.id = self.id or content_id("eff", [self.proposal_id, self.verdict, self.metrics, self.n_pairs, self.provenance.mode])
        return self
