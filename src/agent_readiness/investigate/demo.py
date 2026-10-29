"""Scripted end-to-end demonstration of the M1 plumbing (NO model, NO network, NO website). It exists to prove that the durable pipeline, evidence rules, approval gates and
report work together before the real components (inspector, task generator, trials, verifiers, Meta investigator) land in later milestones.

Everything produced here carries provenance mode `scripted` and the report says so. The toy site facts and the toy verifier below are fixtures, not a product feature."""
from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel

from .llm import LLMRequest, ScriptedClient, complete_structured
from .models import Hypothesis, Observation, Proposal, Provenance, Verification
from .pipeline import STAGES, Context, Pipeline, Stage
from .report import build_report
from .run import InvestigationRun

DEMO_STAGES = ("inspect", "investigate", "recommend", "report")
SCRIPTED = Provenance(mode="scripted", source="fixture:demo")


class HypothesisDraft(BaseModel):
    tier: str
    statement: str
    claim_kind: str | None = None
    prediction: str | None = None
    citations: list[str]


class InvestigatorOutput(BaseModel):
    hypotheses: list[HypothesisDraft]


def toy_observations() -> list[Observation]:
    return [Observation(kind="listing_cards", summary="Listing cards show name and price but no availability text (6 of 6 cards).", data={"cards": 6, "with_availability": 0}, refs=["page:/list"], provenance=SCRIPTED),
            Observation(kind="detail_pages", summary="Detail pages show availability (3 of 3 sampled).", data={"pages": 3, "with_availability": 3}, refs=["page:/p/1", "page:/p/2", "page:/p/3"], provenance=SCRIPTED),
            Observation(kind="trace_pattern", summary="In 2 trials the agent opened every detail page before answering.", data={"trials": ["t1", "t2"]}, refs=["trial:t1", "trial:t2"], provenance=SCRIPTED)]


def scripted_investigator(obs_ids: list[str]) -> ScriptedClient:
    out = {"hypotheses": [
        {"tier": "verifiable", "statement": "Availability appears on detail pages but not on listing cards.", "claim_kind": "info_absent_on_template", "citations": obs_ids[:2]},
        {"tier": "novel", "statement": "Agents open every product page because the listing gives no cue about which items are worth opening.",
         "prediction": "If listing cards showed availability, model requests on list-and-filter tasks would fall.", "citations": [obs_ids[2]]}]}
    return ScriptedClient([json.dumps(out)])


def toy_verify(store, hyp) -> Verification:
    """Fixture verifier for the one claim kind the demo uses: the claim holds when the cited listing observation shows 0 availability cues and a detail observation shows > 0."""
    cited = [store.observations[c] for c in hyp.citations]
    listing = next((o for o in cited if o.kind == "listing_cards"), None)
    detail = next((o for o in cited if o.kind == "detail_pages"), None)
    ok = bool(listing and detail and listing.data["with_availability"] == 0 and detail.data["with_availability"] > 0)
    return Verification(verifier="demo:toy_info_absent_on_template", result="supported" if ok else "refuted", evidence=hyp.citations, provenance=SCRIPTED)


def _inspect(ctx: Context):
    for o in toy_observations():
        ctx.evidence.add_observation(o)
    return {"observations": len(ctx.evidence.observations)}


def _investigate(ctx: Context):
    ids = [o.id for o in toy_observations()]
    req = LLMRequest(messages=[{"role": "system", "content": "Investigate the observations. Return hypotheses."}, {"role": "user", "content": json.dumps([o.model_dump() for o in ctx.evidence.observations.values()], default=str)}],
                     purpose="investigate", response_schema=InvestigatorOutput.model_json_schema())
    parsed, _resp, attempts = complete_structured(ctx.llm, req, InvestigatorOutput)
    for d in parsed.hypotheses:
        h = ctx.evidence.add_hypothesis(Hypothesis(tier=d.tier, statement=d.statement, claim_kind=d.claim_kind, prediction=d.prediction, citations=d.citations,
                                                   provenance=Provenance(mode=ctx.llm.mode, source=f"llm:{ctx.llm.model}")))
        if h.tier == "verifiable":
            ctx.evidence.record_verification(h.id, toy_verify(ctx.evidence, h))
            if h.status == "supported":
                ctx.evidence.promote(h.id, attribution="website", support=["trial:t1", "trial:t2"])
    return {"hypotheses": len(ctx.evidence.hypotheses), "findings": len(ctx.evidence.findings), "model_calls": attempts}


def _recommend(ctx: Context):
    ev = ctx.evidence
    for f in list(ev.findings.values()):
        ev.add_proposal(Proposal(basis="verified_finding", source_id=f.id, change={"ops": [{"op": "toy_copy_field_to_listing", "field": "availability"}]},
                                 expected_effect="Fewer page views to answer availability-dependent tasks.", risks=["Wider cards"], provenance=SCRIPTED))
    for h in list(ev.hypotheses.values()):
        if h.tier == "novel":
            ev.add_proposal(Proposal(basis="unverified_hypothesis", source_id=h.id, change={"manual": "Add a one-line stock cue to listing cards and compare request counts."},
                                     expected_effect=h.prediction or "", risks=["Mechanism unverified"], provenance=SCRIPTED))
    return {"proposals": len(ev.proposals)}


def _report(ctx: Context):
    rep = build_report(ctx.run)
    ctx.run.write_artifact("report", rep)
    return {"outcome": rep["outcome"]}


def build_pipeline() -> Pipeline:
    return Pipeline([Stage("inspect", _inspect), Stage("investigate", _investigate), Stage("recommend", _recommend), Stage("report", _report)])


def run_demo(root: Path, run_id: str = "scripted-demo") -> tuple[InvestigationRun, dict]:
    run = InvestigationRun.create(root, run_id, target="scripted-toy-site", mode="scripted", stages=DEMO_STAGES, config={"demo": True})
    ids = [o.id for o in toy_observations()]
    result = build_pipeline().run(Context(run, llm=scripted_investigator(ids)))
    if result.status != "done":
        raise RuntimeError(f"demo pipeline did not finish: {result}")
    return run, run.artifact("report")


assert set(DEMO_STAGES) <= set(STAGES)
