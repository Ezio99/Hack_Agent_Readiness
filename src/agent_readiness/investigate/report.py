"""investigation-report-v1: one report that keeps observation / hypothesis / supported finding / proposed fix / measured effect apart (plan D6)."""
from __future__ import annotations

from .models import now
from .run import InvestigationRun

SCHEMA = "investigation-report-v1"
NOTICES = {
    "scripted": "SCRIPTED: model and agent behaviour in this run was written by a test fixture; it demonstrates the pipeline, not model capability.",
    "mock": "MOCK: scripted agent over a mirror; not agent behaviour.",
    "recorded": "RECORDED: replay of a previous live transcript; not a new model run.",
    "live": "LIVE: produced by a real model call under the spend gate.",
}


def build_report(run: InvestigationRun) -> dict:
    ev = run.evidence
    modes = sorted({x.provenance.mode for coll in (ev.observations, ev.hypotheses, ev.findings, ev.proposals, ev.effects) for x in coll.values()} | {run.mode})
    verifiable = [h for h in ev.hypotheses.values() if h.tier == "verifiable"]
    novel = [h for h in ev.hypotheses.values() if h.tier == "novel"]
    return {
        "schema": SCHEMA, "run_id": run.state["id"], "target": run.state["target"], "mode": run.mode, "created_at": now(), "outcome": ev.outcome(),
        "notices": [NOTICES[m] for m in modes],
        "observations": [o.model_dump() for o in ev.observations.values()],
        "hypotheses": {
            "verifiable": [{**h.model_dump(), "label": f"hypothesis — {h.status}"} for h in verifiable],
            "novel": [{**h.model_dump(), "label": "NOVEL HYPOTHESIS — UNVERIFIED (not a finding)"} for h in novel],
        },
        "findings": [f.model_dump() for f in ev.findings.values()],
        "proposals": [{**p.model_dump(), "label": p.label, "auto_applicable": p.auto_applicable} for p in ev.proposals.values()],
        "effects": {"measured": [e.model_dump() for e in ev.effects.values() if e.measured],
                    "not_measured_pipeline_checks": [e.model_dump() for e in ev.effects.values() if not e.measured]},
        "statement": ("Findings are website properties verified by deterministic checks. Novel hypotheses are unverified and can only back EXPERIMENTAL proposals. "
                      "A measured effect shows a change moved metrics on the measured tasks; it does not verify a hypothesis' mechanism."),
    }
