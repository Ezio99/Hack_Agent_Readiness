"""Owner-selected EXPLORATORY proposals (Task 016, EXP-B). The owner may choose a change that the pipeline has not verified (e.g. a verified-supported but unpromoted pattern). It is recorded as an
owner-authored NOVEL hypothesis (unverified, with a falsifiable prediction, citing existing observations) plus a proposal that carries a validated patch from the existing template set, and it is
labelled `EXPERIMENTAL - OWNER-SELECTED change; not an investigator-verified finding` everywhere. It is never a finding, never promoted, and still needs the exact-manifest `apply_fix` approval
before the patch touches the local mirror. Offline and free: no model call."""
from __future__ import annotations

from .inspect.stage import load_snapshot
from .models import Hypothesis, Proposal, Provenance
from .recommend import templates
from .run import InvestigationRun


def add_owner_proposal(run: InvestigationRun, *, owner: str, claim_kind: str, params: dict, hypothesis: str, prediction: str, cites: list[str]) -> Proposal:
    if not owner.strip():
        raise ValueError("an owner-selected proposal needs the owner's name or role")
    if not cites:
        raise ValueError("cite at least one existing observation id")
    ev = run.evidence
    missing = [c for c in cites if c not in ev.observations]
    if missing:
        raise ValueError(f"unknown observation ids {missing}")
    patch, info = templates.build(claim_kind, params, run.artifact("site-profile"), load_snapshot(run))
    if patch is None:
        raise ValueError(f"no safe patch for this selection: {info.get('reason')}")
    prov = Provenance(mode=run.mode, source=f"owner:{owner.strip()}")
    h = ev.add_hypothesis(Hypothesis(tier="novel", statement=hypothesis, prediction=prediction, citations=list(cites), provenance=prov))
    return ev.add_proposal(Proposal(basis="unverified_hypothesis", source_id=h.id, change={**patch, "static_recheck": info["recheck"], "patch_sha256": info["patch_sha256"], "owner_selected": True, "exploratory": True},
                                    expected_effect=prediction, risks=["Owner-selected exploratory change: the underlying hypothesis is unverified", "A verified pattern removed from the page is not an effect on agents",
                                                                       "Adds text to the page, so layouts get busier"], provenance=prov))
