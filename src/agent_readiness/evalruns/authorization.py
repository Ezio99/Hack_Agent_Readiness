"""Paid Stage B authorisation guard (lifecycle M6/M7). `runner.execute` refuses paid mode unless a write-once authorisation record matches.

A `PaidAuthorization` binds the owner's paid permission to:
  experiment_id            names the FIXED durable ledger (scanner-data/research/stage-b/ledgers/<experiment_id>/), so a restart can never reset
                           the spend or the trial count
  frozen_suite_sha256      the exact frozen suite; its approval must be a real owner approval (decided at an interactive terminal; never a
                           'synthetic-' fixture suite or a synthetic-labelled approval)
  manifest_sha256          the exact evaluation manifest (frozen suite, variants and snapshots, agent configuration, repetitions, seed, plan, budget)
  max_trials, cap_usd      the planned trials may not exceed max_trials, the manifest's hard cap must EQUAL cap_usd and its worst-case reservation
                           must be within it (never relaxed: a design over the cap is refused)
`verify` also checks that the manifest's agent configuration is the pinned one (model, endpoint, reasoning effort, completion cap, profile hash).
The record itself is written once (exclusive create, read-only) and identified by its content hash; any edit is a different authorisation."""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ..suite.core import canonical_hash
from ..suites.store import WriteOnceStore

ROOT = Path(__file__).resolve().parents[3]
STAGE_B = ROOT / "scanner-data" / "research" / "stage-b"
EXPERIMENT_ID = re.compile(r"^[a-z0-9][a-z0-9-]{2,60}$")


class PaidAuthorization(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    experiment_id: str = Field(pattern=EXPERIMENT_ID.pattern)
    frozen_suite_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    max_trials: int = Field(gt=0, le=64)
    cap_usd: float = Field(gt=0, le=50)
    granted_by: Literal["owner"] = "owner"
    instruction: str = Field(min_length=20)                    # the owner's own words, verbatim
    recorded_at: str = Field(min_length=10)
    recorded_by: str = Field(min_length=1)                     # who wrote this record down (e.g. "agent, from the owner's instruction")

    @property
    def sha256(self) -> str:
        return canonical_hash(self.model_dump(mode="json"))


def ledger_dir(experiment_id: str) -> Path:
    if not EXPERIMENT_ID.match(experiment_id):
        raise ValueError("invalid experiment id")
    return STAGE_B / "ledgers" / experiment_id


def write(auth: PaidAuthorization, directory: Path | None = None) -> Path:
    d = Path(directory or STAGE_B / "authorizations")
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{auth.experiment_id}.json"
    with open(path, "x") as f:                                  # write-once: an experiment id is authorised once
        f.write(json.dumps(auth.model_dump(mode="json"), indent=1, sort_keys=True))
    os.chmod(path, 0o444)
    return path


def load(path: Path) -> PaidAuthorization:
    return PaidAuthorization.model_validate(json.loads(Path(path).read_text()))


def verify(auth: PaidAuthorization, store: WriteOnceStore, manifest_sha: str, *, planned_trials: int) -> list[str]:
    """Every mismatch (empty list = authorised). Never relaxes anything: a mismatch means no paid request is sent."""
    from .manifest import agent_config
    problems = []
    if manifest_sha != auth.manifest_sha256:
        problems.append(f"manifest {manifest_sha[:12]} is not the authorised manifest {auth.manifest_sha256[:12]}")
    try:
        m = store.get("manifest", manifest_sha)
    except Exception as exc:
        return problems + [f"manifest not readable from the store ({type(exc).__name__})"]
    if m.frozen_suite_sha256 != auth.frozen_suite_sha256:
        problems.append("the manifest's frozen suite is not the authorised frozen suite")
    try:
        frozen = store.get("frozen_suite", m.frozen_suite_sha256)
        approval = store.get("approval", frozen.approval_sha256)
        suite = store.get("suite", frozen.suite_sha256)
    except Exception as exc:
        return problems + [f"frozen suite, approval or suite not readable ({type(exc).__name__})"]
    if approval.decision != "approved" or approval.suite_sha256 != frozen.suite_sha256:
        problems.append("the frozen suite has no approval of exactly its hash")
    if suite.suite_name.startswith("synthetic-") or "SYNTHETIC" in approval.notes:
        problems.append("a synthetic fixture suite or a synthetic approval can never authorise paid execution")
    if planned_trials > auth.max_trials:
        problems.append(f"{planned_trials} planned trials exceed the authorised {auth.max_trials}")
    b = m.budget
    if abs(b["hard_cap_usd"] - auth.cap_usd) > 1e-9:
        problems.append(f"the manifest's hard cap US${b['hard_cap_usd']} is not the authorised cap US${auth.cap_usd}")
    if b["worst_case_reservation_usd"] > auth.cap_usd + 1e-9:
        problems.append(f"worst-case reservation US${b['worst_case_reservation_usd']} exceeds the authorised cap US${auth.cap_usd}; a revised design is needed")
    pinned = agent_config(m.agent.profile)
    for k in ("model", "endpoint", "reasoning_effort", "max_completion_tokens", "profile", "profile_sha256"):
        if getattr(pinned, k) != getattr(m.agent, k):
            problems.append(f"agent {k} differs from the pinned configuration")
    return problems
