"""Controlled Ironbark before/after experiment (EXP-C driver): the EXP-B machinery applied to the registered Ironbark target.

Nothing new is invented here. It forks a finished live Ironbark run (frozen tasks, real-model baseline trials, completed investigator) with `--carry-investigation` semantics, records ONE owner-selected,
labelled, EXPERIMENTAL proposal (show three fields on the listing cards), builds the retest plan (every frozen task is an affected task; one unmodified repeat per task; counterbalanced order) and
presents the two approval manifests (`apply_fix`, then `post_trials`) exactly as the existing pipeline does. The free plan prints hashes and spends nothing; a paid run needs `--approve-hash` of the
`post_trials` manifest AND `--allow-model-calls`, and every number it may spend is in that manifest.

The intervention, hypothesis, prediction, plan and caps below are the PRE-REGISTERED inputs; changing any of them changes the manifest hash."""
from __future__ import annotations

import json
import math
from pathlib import Path

from ..investigate import allocation as alloc
from ..investigate.fork import fork
from ..investigate.run import InvestigationRun

SOURCE = Path("scanner-data/live/live-2d58a80e14")          # real-model Ironbark run: 4 frozen tasks, 4 baseline trials, completed investigator, snapshot d2824b21...
OWNER = "project owner (Ironbark before/after experiment)"
LABELS = ["refundable deposit", "minimum hire", "delivery and collection"]
HYPOTHESIS = ("Agents asked to compare the refundable deposit, minimum hire period and delivery requirements across the hire machines use nearly their whole step budget opening each machine's detail page, because "
              "those three fields appear only on the detail pages. Showing the same three facts on the listing cards would let the comparison be made from the listing pages. (Unverified; owner-selected.)")
PREDICTION = ("With the three fields shown on the listing cards, the agent answers each of the four frozen comparison tasks with at most 75% of the model requests it needs on the unmodified site and without "
              "losing any evidence-backed pass; the effect is larger than the run-to-run difference between the unmodified repeat and the historical baseline.")
CITES = ["obs-8d20d6d5d9"]                                   # the /hire listing observation of the carried investigation: the three fields are on the item pages and not in the listing items
CAPS = {"placebo_arm": 0.80, "patched_arm": 0.80}            # per-arm caps (US$, calculated): the 4 baseline trials cost 0.17-0.20 each, so one repeat per task is about 0.74; a patched trial costs 0.03-0.20 (the cap covers four failures)


def ledger_ceiling(imported_usd: float) -> float:
    """Imported spend + the two arm caps, rounded UP to the next 5 cents: the hard ceiling on the shared ledger."""
    return round(math.ceil((imported_usd + sum(CAPS.values())) * 20) / 20, 2)


def ensure_fork(source: Path, root: Path, run_id: str) -> InvestigationRun:
    d = Path(root) / run_id
    if not (d / "run.json").exists():
        fork(Path(source), Path(root), run_id, carry_investigation=True)
    return InvestigationRun(d)


def ensure_proposal(run: InvestigationRun):
    """The single owner-selected proposal (idempotent: an existing one from this module is reused, never duplicated)."""
    from ..investigate.owner import add_owner_proposal
    for p in run.evidence.proposals.values():
        if p.provenance.source == f"owner:{OWNER}" and p.change.get("owner_selected"):
            return p
    return add_owner_proposal(run, owner=OWNER, claim_kind="info_absent_on_template", params={"labels": LABELS}, hypothesis=HYPOTHESIS, prediction=PREDICTION, cites=CITES)


def build_plan(run: InvestigationRun) -> dict:
    from ..investigate.taskgen import freeze as freezer
    ids = sorted(t["task_id"] for t in freezer.load(run)[0]["tasks"])
    return {"placebo_tasks": ids, "affected": ids, "same_shape_controls": [], "detail_controls": [], "caps_usd": dict(CAPS)}


def drive(source: Path, root: Path, run_id: str, *, cfg, snapshot, approve: frozenset[str] = frozenset(), allow_model_calls: bool = False) -> dict:
    """Run the pipeline of the fork until it needs an approval it does not have; return where it stopped. When a pending manifest's hash is in `approve` (and, for the spending stage,
    `allow_model_calls` is set), record that exact approval and continue. Anything else stops with a plain report; the free steps (fork, proposal, apply_fix) spend nothing."""
    from ..investigate import flow
    from ..ledger import Halt
    run = ensure_fork(source, root, run_id)
    prop = ensure_proposal(run)
    plan = build_plan(run)
    imported = json.loads((run.dir / "fork.json").read_text())["source_ledger"]["committed_usd"]
    opts = {"model_config": cfg, "snapshot": snapshot, "fix": [prop.id], "post_plan": plan, "repeats": 1, "total_cap_usd": ledger_ceiling(imported),
            "allow_model_calls": bool(approve and allow_model_calls)}
    if opts["allow_model_calls"]:
        from ..env import load_repo_env
        load_repo_env()
    out: dict = {"fork": str(run.dir), "proposal_id": prop.id, "proposal_label": prop.label, "ledger_ceiling_usd": opts["total_cap_usd"], "imported_spend_usd": imported, "approved": []}
    run, pipe, ctx = flow.build(Path(root), run_id, run.state["target"], mode="live", options=opts)
    for _ in range(6):
        try:
            res = pipe.run(ctx)
        except Halt as exc:
            return {**out, "status": "refused", "reason": str(exc)}
        if res.status != "awaiting_approval":
            return {**out, "status": res.status, "stage": res.stage, "error": getattr(res, "error", None)}
        manifest = run.artifact(f"manifests/{res.stage}-{res.manifest_sha256[:16]}")
        spends = res.stage == "post_trials"
        if res.manifest_sha256 in approve and (allow_model_calls or not spends):
            run.approve(res.stage, res.manifest_sha256, f"OPERATOR approval of exactly this {res.stage} manifest for the Ironbark before/after experiment ({run_id})")
            out["approved"].append(res.stage)
            continue
        return {**out, "status": "awaiting_approval", "stage": res.stage, "manifest_sha256": res.manifest_sha256, "manifest": manifest}
    return {**out, "status": "stopped", "reason": "too many approval rounds"}
