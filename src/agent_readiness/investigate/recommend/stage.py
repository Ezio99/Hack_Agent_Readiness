"""Stages `recommend` (free), `apply_fix` (owner approval in EVERY mode)."""
from __future__ import annotations

from ..inspect.stage import load_snapshot
from ..models import Proposal, Provenance
from ..pipeline import Context
from ..sitemodel.patch import apply_patch
from . import templates


def recommend_stage(ctx: Context) -> dict:
    run = ctx.run
    ev, profile, snap = run.evidence, run.artifact("site-profile"), load_snapshot(run)
    inv = run.artifact("investigation") if run.has_artifact("investigation") else {"novel_changes": []}
    offered, declined = [], []
    for f in list(ev.findings.values()):
        h = ev.hypotheses[f.hypothesis_id]
        patch, info = templates.build(h.claim_kind, h.params, profile, snap)
        if patch is None:
            declined.append({"finding_id": f.id, "claim_kind": h.claim_kind, **info})
            continue
        p = ev.add_proposal(Proposal(basis="verified_finding", source_id=f.id, change={**patch, "static_recheck": info["recheck"], "patch_sha256": info["patch_sha256"]},
                                     expected_effect=f"Fewer extra page views and more evidence-backed passes on tasks that depend on this pattern: {f.statement[:160]}",
                                     risks=["Adds text/links to the page, so layouts get busier", "Not measured: a verified pattern removed from the page is not yet an effect on agents"],
                                     provenance=Provenance(mode=run.mode, source="rule:template")))
        offered.append({"proposal_id": p.id, "finding_id": f.id, "claim_kind": h.claim_kind, **{k: info[k] for k in ("note", "recheck", "patch_sha256", "result_snapshot_sha256", "pages_changed", "inserted_bytes")}})
    manual = []
    for n in inv.get("novel_changes", []):
        h = ev.hypotheses.get(n["hypothesis_id"])
        if h is None or h.status != "unverified" or h.tier != "novel":
            continue
        p = ev.add_proposal(Proposal(basis="unverified_hypothesis", source_id=h.id, change={"manual": n["proposed_change"]}, expected_effect=h.prediction or "", risks=["The underlying hypothesis is unverified", "Manual change: not testable by this tool"],
                                     provenance=Provenance(mode=run.mode, source="llm:investigator")))
        manual.append({"proposal_id": p.id, "hypothesis_id": h.id})
    run.write_artifact("recommendations", {"verified_finding_proposals": offered, "not_offered": declined, "experimental_manual_proposals": manual,
                                           "note": "Every proposal is unvalidated. Resolution of a pattern is not an effect on agents; only the retest of the frozen tasks measures an effect."})
    return {"proposals": len(offered) + len(manual), "auto_applicable": len(offered), "not_offered": len(declined)}


def fix_ids(ctx: Context) -> list[str]:
    f = ctx.options.get("fix")
    return [f] if isinstance(f, str) else list(f or [])


def apply_manifest(ctx: Context) -> dict | None:
    run, ids = ctx.run, fix_ids(ctx)
    if not ids:
        return None
    snap = load_snapshot(run)
    items = []
    for pid in ids:
        p = run.evidence.proposals.get(pid)
        owner_selected = bool(p and p.basis == "unverified_hypothesis" and p.change.get("owner_selected") and p.provenance.source.startswith("owner:"))
        if p is None or not p.auto_applicable or (p.basis != "verified_finding" and not owner_selected):
            raise ValueError(f"proposal {pid} is not an auto-applicable verified-finding or owner-selected exploratory proposal")
        new, rep = apply_patch(snap, {k: v for k, v in p.change.items() if k in ("description", "ops")})
        items.append({"proposal_id": pid, "label": p.label, "exploratory_owner_selected": owner_selected, "patch_sha256": rep["patch_sha256"], "parent_snapshot_sha256": snap.sha256, "result_snapshot_sha256": rep["new_sha256"], "pages_changed": rep["pages_changed"],
                      "inserted_bytes": rep["inserted_bytes"]})
    from ..fork import provenance_summary
    forked = provenance_summary(run)
    return {**({"forked_from": forked} if forked else {}), "stage": "apply_fix", "applies_to": "the LOCAL MIRROR only (never a real site)", "proposals": items}


def apply_fix_stage(ctx: Context) -> dict:
    run = ctx.run
    m = apply_manifest(ctx)
    h = run.manifest_sha256(m)
    snap = load_snapshot(run)
    note = next(a["note"] for a in reversed(run.approvals()) if a["stage"] == "apply_fix" and a["manifest_sha256"] == h)
    for it in m["proposals"]:
        p = run.evidence.proposals[it["proposal_id"]]
        new, rep = apply_patch(snap, {k: v for k, v in p.change.items() if k in ("description", "ops")})
        assert rep["new_sha256"] == it["result_snapshot_sha256"]                    # exactly what was approved
        run.evidence.approve(p.id, manifest_sha256=h, note=note)
        new.save(run.dir / "patched" / p.id)
        run.evidence.mark_applied(p.id)
    return {"applied": [i["proposal_id"] for i in m["proposals"]]}
