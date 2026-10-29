"""Durable, append-only evidence store with the invariants of plan D6/D8 enforced in code (not by prompt).

Everything is an event in `evidence.jsonl`; state is rebuilt by replaying events through the same methods, so a reloaded store is identical and cannot hold anything the
rules would have refused. The model-facing side can only `add_observation` / `add_hypothesis` / `add_proposal`; verification, promotion to a Finding and approvals are code paths."""
from __future__ import annotations

import json
import os
from pathlib import Path

from .models import (MIN_INDEPENDENT_SUPPORT, SCHEMA, WEBSITE_ATTRIBUTIONS, Effect, Finding, Hypothesis, Observation, Proposal, Provenance, Verification, now)


class EvidenceError(ValueError):
    pass


class PromotionError(EvidenceError):
    pass


class EvidenceStore:
    def __init__(self, path: Path | None = None):
        self.path = Path(path) if path else None
        self.observations: dict[str, Observation] = {}
        self.hypotheses: dict[str, Hypothesis] = {}
        self.findings: dict[str, Finding] = {}
        self.proposals: dict[str, Proposal] = {}
        self.effects: dict[str, Effect] = {}
        if self.path and self.path.exists():
            lines = self.path.read_text().splitlines()
            for i, line in enumerate(lines):
                try:
                    e = json.loads(line)
                except ValueError:
                    if i == len(lines) - 1:                      # a crash mid-append leaves a truncated LAST line only; drop it (and the partial bytes) rather than make the run unloadable
                        self.path.write_text("".join(l + "\n" for l in lines[:-1]))
                        break
                    raise
                getattr(self, "_replay_" + e["event"])(e["data"])

    # -- persistence ---------------------------------------------------------------------------------------------------
    def _append(self, event: str, data: dict) -> None:
        if not self.path:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a") as f:
            f.write(json.dumps({"schema": SCHEMA, "ts": now(), "event": event, "data": data}, sort_keys=True) + "\n")
            f.flush()
            os.fsync(f.fileno())

    # -- model-facing additions ----------------------------------------------------------------------------------------
    def add_observation(self, obs: Observation) -> Observation:
        if obs.id in self.observations:
            return self.observations[obs.id]
        self.observations[obs.id] = obs
        self._append("observation", obs.model_dump())
        return obs

    def add_hypothesis(self, hyp: Hypothesis) -> Hypothesis:
        missing = [c for c in hyp.citations if c not in self.observations]
        if missing:
            raise EvidenceError(f"hypothesis cites unknown observation ids {missing}")
        if hyp.status != "unverified" or hyp.verification is not None:
            raise EvidenceError("a hypothesis is always added unverified; verification is recorded by code")
        if hyp.id in self.hypotheses:
            return self.hypotheses[hyp.id]
        self.hypotheses[hyp.id] = hyp
        self._append("hypothesis", hyp.model_dump())
        return hyp

    def add_proposal(self, prp: Proposal) -> Proposal:
        if prp.status != "proposed" or prp.approvals:
            raise EvidenceError("a proposal is added as `proposed` with no approvals")
        if prp.basis == "verified_finding":
            if prp.source_id not in self.findings:
                raise EvidenceError("a verified-finding proposal must reference an existing Finding")
        else:
            if prp.source_id in self.findings:
                raise EvidenceError("an unverified_hypothesis proposal must reference a hypothesis id, not a Finding")
            hyp = self.hypotheses.get(prp.source_id)
            if hyp is None:
                raise EvidenceError("an unverified_hypothesis proposal must reference an existing Hypothesis")
            if hyp.status == "supported" and hyp.tier == "verifiable":
                raise EvidenceError("this hypothesis is verified-supported: promote it to a Finding and use basis=verified_finding")
        if prp.id in self.proposals:
            return self.proposals[prp.id]
        self.proposals[prp.id] = prp
        self._append("proposal", prp.model_dump())
        return prp

    # -- code-only transitions -----------------------------------------------------------------------------------------
    def record_verification(self, hypothesis_id: str, v: Verification) -> Hypothesis:
        h = self._hyp(hypothesis_id)
        if h.tier != "verifiable":
            raise EvidenceError("only a verifiable hypothesis can be verified; a novel hypothesis stays unverified")
        if h.verification is not None:
            raise EvidenceError("this hypothesis already has a verification record")
        h.verification, h.status = v, v.result
        self._append("verification", {"hypothesis_id": hypothesis_id, "verification": v.model_dump()})
        return h

    def promote(self, hypothesis_id: str, *, attribution: str, support: list[str], structural_proof: bool = False, statement: str | None = None, source: str = "code:promote") -> Finding:
        """The ONLY way to create a Finding. Requirements: verifiable tier, verifier result `supported`, website/tool_interface attribution, and >= 2 independent support refs
        (or one deterministic structural proof)."""
        h = self._hyp(hypothesis_id)
        if h.tier != "verifiable":
            raise PromotionError("a novel hypothesis can never become a finding (it can only back an EXPERIMENTAL proposal)")
        if h.status != "supported" or h.verification is None or h.verification.result != "supported":
            raise PromotionError(f"hypothesis is {h.status}; only a verifier-supported hypothesis can be promoted")
        if attribution not in WEBSITE_ATTRIBUTIONS:
            raise PromotionError(f"attribution {attribution!r} is not a website-side cause; it cannot become a website finding")
        support = sorted(set(support))
        if len(support) < MIN_INDEPENDENT_SUPPORT and not structural_proof:
            raise PromotionError(f"needs >= {MIN_INDEPENDENT_SUPPORT} independent supporting trials/tasks or a structural proof (got {len(support)})")
        f = Finding(hypothesis_id=h.id, statement=statement or h.statement, attribution=attribution, support=support, structural_proof=structural_proof,
                    provenance=Provenance(mode=h.verification.provenance.mode, source=source))
        if f.id not in self.findings:
            self.findings[f.id] = f
            self._append("finding", f.model_dump())
        return self.findings[f.id]

    def approve(self, proposal_id: str, *, manifest_sha256: str, note: str) -> Proposal:
        """Record the owner's explicit approval of THIS proposal (and the manifest hash it covers). Required before a proposal can be applied or tested."""
        p = self._prp(proposal_id)
        if not note.strip() or not manifest_sha256:
            raise EvidenceError("approval needs a note and the approved manifest hash")
        p.approvals.append({"manifest_sha256": manifest_sha256, "note": note, "at": now()})
        p.status = "approved" if p.status == "proposed" else p.status
        self._append("approval", {"proposal_id": proposal_id, "manifest_sha256": manifest_sha256, "note": note, "at": p.approvals[-1]["at"]})
        return p

    def mark_applied(self, proposal_id: str) -> Proposal:
        p = self._prp(proposal_id)
        if p.status not in ("approved", "applied") or not p.approvals:
            raise EvidenceError("a proposal cannot be applied without a recorded owner approval")
        if not p.auto_applicable:
            raise EvidenceError("a manual-change proposal is not auto-applicable")
        p.status = "applied"
        self._append("applied", {"proposal_id": proposal_id})
        return p

    def add_effect(self, e: Effect) -> Effect:
        p = self._prp(e.proposal_id)
        if p.status not in ("applied", "measured"):
            raise EvidenceError("an effect needs an applied (hence approved) proposal")
        if e.id not in self.effects:
            self.effects[e.id] = e
            if e.measured:
                p.status = "measured"
            self._append("effect", e.model_dump())
        return self.effects[e.id]

    # -- views ---------------------------------------------------------------------------------------------------------
    def outcome(self) -> str:
        """findings | experimental_only | no_supported_issue  (a novel hypothesis alone is never a supported issue)."""
        if self.findings:
            return "findings"
        if any(p.basis == "unverified_hypothesis" for p in self.proposals.values()):
            return "experimental_only"
        return "no_supported_issue"

    def _hyp(self, i: str) -> Hypothesis:
        if i not in self.hypotheses:
            raise EvidenceError(f"unknown hypothesis {i}")
        return self.hypotheses[i]

    def _prp(self, i: str) -> Proposal:
        if i not in self.proposals:
            raise EvidenceError(f"unknown proposal {i}")
        return self.proposals[i]

    # -- replay (loads events through plain state assignment; the rules already held when they were written) --------------
    def _replay_observation(self, d):
        o = Observation(**d)
        self.observations[o.id] = o

    def _replay_hypothesis(self, d):
        h = Hypothesis(**d)
        self.hypotheses[h.id] = h

    def _replay_verification(self, d):
        h = self._hyp(d["hypothesis_id"])
        h.verification = Verification(**d["verification"])
        h.status = h.verification.result

    def _replay_finding(self, d):
        f = Finding(**d)
        self.findings[f.id] = f

    def _replay_proposal(self, d):
        p = Proposal(**d)
        self.proposals[p.id] = p

    def _replay_approval(self, d):
        p = self._prp(d["proposal_id"])
        p.approvals.append({k: d[k] for k in ("manifest_sha256", "note", "at")})
        p.status = "approved" if p.status == "proposed" else p.status

    def _replay_applied(self, d):
        self._prp(d["proposal_id"]).status = "applied"

    def _replay_effect(self, d):
        e = Effect(**d)
        self.effects[e.id] = e
        if e.measured:
            self._prp(e.proposal_id).status = "measured"
