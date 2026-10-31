"""The scripted M0 investigator. It is a TEST DOUBLE standing in for the LLM investigator of M1: it lists the trials, picks the listing field that the deterministic inspector profile shows to be
missing from listing items, asks the deterministic verifier to check the claim, and reports it. The finding it ends with is verified by the same code as a real model's would be; what is scripted
is only the choice of what to look at. Every result carries mode=scripted/mock and is labelled so in the export and the UI."""
from __future__ import annotations

import json

from ..investigate.llm import ScriptedClient

NULLS = dict(evidence_id=None, trial_id=None, task_id=None, step=None, path=None, css=None, text=None, claim_kind=None, label=None, scope=None, k=None)


def _step(tool, thought, hyps=None, **kw):
    return {"thought": thought, "action": {**NULLS, "tool": tool, **kw}, "hypotheses": hyps}


def _label(profile: dict) -> str | None:
    best = None
    for listing in profile.get("listings", []):
        for name, f in listing.get("fields", {}).items():
            if f["detail_pages"] >= 2 and f["in_listing_item"] <= f["detail_pages"] * 0.5 and (best is None or f["detail_pages"] > best[0]):
                best = (f["detail_pages"], name)
    return best[1] if best else None


def make(run) -> ScriptedClient:
    state = {"i": 0}

    def respond(request):
        last = {}
        m = request.messages[-1]
        if m["role"] == "user" and m["content"].startswith('{"tool_result"'):
            last = json.loads(m["content"]).get("tool_result", {})
        state["i"] += 1
        if state["i"] == 1:
            return json.dumps(_step("list_trials", "MOCK: start from the trials"))
        label = _label(run.artifact("site-profile"))
        if state["i"] == 2 and label:
            return json.dumps(_step("check_claim", f"MOCK: check whether '{label}' is missing from listing items", claim_kind="info_absent_on_template", label=label))
        obs = next((o.id for o in run.evidence.observations.values() if o.kind == "listing_detail_fields"), None)
        hyps = []
        if label and obs and last.get("result") == "supported":
            hyps = [{"statement": f"The field '{label}' is only on the item pages, not in the listing items, so an agent must open each item to compare it.", "claim_kind": "info_absent_on_template", "label": label,
                     "scope": None, "k": None, "prediction": None, "citations": [obs], "proposed_change": None},
                    {"statement": f"Agents comparing items lose steps because '{label}' is not visible on the listing cards.", "claim_kind": None, "label": None, "scope": None, "k": None,
                     "prediction": f"If each listing card showed '{label}', page views per comparison task would drop.", "citations": [obs], "proposed_change": f"Show '{label}' on every listing card."}]
        return json.dumps(_step("finish", "MOCK: report the verified pattern", hyps=hyps))
    return ScriptedClient(respond)
