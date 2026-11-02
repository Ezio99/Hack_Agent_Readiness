"""Public Stage A views (lifecycle M8): task generation and validation runs, and suites with their review, approval and freeze state.

generation(dir)        a Stage A generation run directory (as the M6 driver writes it: experiment.json, evaluation.public.json, coverage.json,
                       gap-report.json, feedback-r*.json, optional re-evaluation-post-fix/): settings, per-round requests and costs, every
                       proposal with its admission category, gate results and rejection reasons, the feedback sent to the next round (it never
                       contains answers), coverage and the gap report. Withheld: the owner's authorisation text, ledger lines, raw model
                       responses, local paths, and the wording of any proposal rejected for revealing its answer.
suite(store, sha)      the review packet (approval.review_packet: public only) plus the suite's state: proposed | approved | rejected | frozen,
                       with the exact hashes of every approval and frozen suite and the owner-terminal command that decides it.
Stage A views never read Stage B outcomes (suites/boundary.py forbids it for the Stage A modules; this module only reads Stage A records)."""
from __future__ import annotations

import json
from pathlib import Path

from ..suites.stage_a import approval as AP
from ..suites.store import WriteOnceStore

SCHEMA = "lifecycle-stage-a-v1"
LEAK_REASON = ("reveal", "leak", "answer is", "contains the answer", "names the answer")


def _read(d: Path, name: str):
    p = d / name
    return json.loads(p.read_text()) if p.exists() else None


def generation(d: Path, *, generation_id: str | None = None) -> dict:
    d = Path(d)
    exp = _read(d, "experiment.json") or {}
    props = _read(d, "evaluation.public.json") or []
    fixed = _read(d / "re-evaluation-post-fix", "evaluation.public.json")
    settings = exp.get("settings") or {}
    out_props = []
    for p in props:
        w = p.get("wording") or {}
        reasons = list(p.get("rejection_reasons") or [])
        leaked = any(any(k in r.lower() for k in LEAK_REASON) for r in reasons)
        gates = p.get("hard_gates") or {}
        out_props.append({"id": p.get("candidate_id"), "round": (p.get("provenance") or {}).get("round"), "persona": p.get("persona"), "journey": p.get("journey"),
                          "capability": p.get("capability"), "kind": p.get("kind"), "admission": p.get("admission"), "category": w.get("category"),
                          "customer_wording": None if leaked else w.get("customer"), "withheld": "rejected for revealing its answer" if leaked else None,
                          "executed_wording": None if leaked else w.get("executed"), "assumptions": list(w.get("assumptions") or []),
                          "unresolved": list(w.get("unresolved") or []), "rejection_reasons": reasons,
                          "gates": {k: bool((v or {}).get("pass")) for k, v in gates.items()},
                          "nl_traces": [{"component": t.get("component"), "decision": t.get("decision"), "status": t.get("status")} for t in ((p.get("nl") or {}).get("traces") or [])],
                          "soft": p.get("soft"), "near_duplicate": p.get("near_duplicate")})
    rounds = []
    for r in exp.get("rounds") or []:
        rounds.append({"round": r.get("round"), "sent": r.get("sent"), "model": r.get("response_model"), "latency_seconds": r.get("latency_seconds"),
                       "prompt_tokens": (r.get("usage") or {}).get("prompt_tokens"), "completion_tokens": (r.get("usage") or {}).get("completion_tokens"),
                       "reasoning_tokens": r.get("reasoning_tokens"), "cost_usd": r.get("cost_usd"), "candidates": len(r.get("candidates") or []),
                       "admissions": r.get("admissions"), "targets_met": r.get("targets_met"), "gaps_after": r.get("gaps_after"), "stop": r.get("stop")})
    feedback = []
    for f in sorted(d.glob("feedback-r*.json")):
        fb = json.loads(f.read_text())
        feedback.append({"for_round": int(f.stem.split("-r")[-1]), "coverage_gaps": fb.get("coverage_gaps"), "missing_capabilities": fb.get("missing_capabilities"),
                         "rejection_categories": fb.get("rejection_categories") or fb.get("rejections"), "avoid_signatures": len(fb.get("avoid_signatures") or []),
                         "note": "feedback carries rejection categories, uncovered cells, missing capabilities and signatures to avoid; never answers"})
    cost = exp.get("cost") or {}
    from collections import Counter
    return {"schema": SCHEMA, "kind": "generation", "id": generation_id or d.name, "site": settings.get("site"), "created_at": exp.get("created_at"),
            "mode": "paid" if any(r.get("response_mode") == "live" for r in exp.get("rounds") or []) else "rehearsal",
            "generator": {k: settings.get(k) for k in ("model", "reasoning_effort", "max_completion_tokens", "prompt_version", "schema_version", "proposals_per_round", "max_rounds")},
            "limits": {k: settings.get(k) for k in ("max_requests", "cap_usd", "per_request_cap_usd")},
            "stop_reason": exp.get("stop_reason"), "suite_sha256": exp.get("suite_sha256"), "suite_name": settings.get("suite_name"),
            "cost": {"requests": cost.get("requests"), "calculated_usd": cost.get("settled_calculated_usd"), "unsettled": len(cost.get("unsettled") or []),
                     "basis": "calculated from provider-reported usage at published prices; not a bill"},
            "rounds": rounds, "proposals": out_props,
            "admissions": dict(Counter(p["admission"] for p in out_props)),
            "post_fix_reevaluation": None if fixed is None else {"admissions": dict(Counter(p.get("admission") for p in fixed)),
                                                                 "note": "offline re-evaluation (zero cost) of the same recorded proposals after the 'at least N' lexicon fix"},
            "feedback": feedback, "coverage": _read(d, "coverage.json"), "gap_report": _read(d, "gap-report.json")}


def suite_state(store: WriteOnceStore, suite_sha: str) -> dict:
    """proposed | approved | rejected | frozen, with every approval and frozen suite of exactly this hash (read from the store, tamper-checked)."""
    approvals, frozen = [], []
    for p in sorted((store.root / "objects" / "approval").glob("*.json")) if (store.root / "objects" / "approval").exists() else []:
        a = store.get("approval", p.stem)
        if a.suite_sha256 == suite_sha:
            approvals.append({"sha256": p.stem, "decision": a.decision, "role": a.approver_role, "decided_at": a.approved_at,
                              "synthetic": "SYNTHETIC" in a.notes})
    for p in sorted((store.root / "objects" / "frozen_suite").glob("*.json")) if (store.root / "objects" / "frozen_suite").exists() else []:
        f = store.get("frozen_suite", p.stem)
        if f.suite_sha256 == suite_sha:
            frozen.append({"sha256": p.stem, "approval_sha256": f.approval_sha256, "frozen_at": f.frozen_at})
    refs = []
    rd = store.root / "refs" / "frozen_suite"
    for p in sorted(rd.glob("*.json")) if rd.exists() else []:
        r = json.loads(p.read_text())
        if r["sha256"] in {f["sha256"] for f in frozen}:
            refs.append(r["name"])
    state = "frozen" if frozen else "approved" if any(a["decision"] == "approved" for a in approvals) else \
            "rejected" if any(a["decision"] == "rejected" for a in approvals) else "proposed"
    return {"state": state, "approvals": approvals, "frozen": frozen, "refs": refs}


def suite(store: WriteOnceStore, suite_sha: str) -> dict:
    packet = AP.review_packet(store, suite_sha)
    st = suite_state(store, suite_sha)
    prov = packet["provenance"]
    return {"schema": SCHEMA, "kind": "suite", **packet["suite"], "synthetic": packet["synthetic"], "state": st["state"], "approvals": st["approvals"],
            "frozen": st["frozen"], "refs": st["refs"], "created_at": prov.get("created_at"), "created_by": prov.get("created_by"),
            "inputs": [{"kind": i["kind"], "name": i["name"], "sha256": i["sha256"]} for i in prov.get("inputs") or []],
            "coverage": packet["coverage"], "counts": packet["counts"], "tasks": packet["tasks"], "checklist": packet["checklist"],
            "attestation": packet["attestation"],
            "owner_terminal_command": f"python -m agent_readiness.suites.stage_a.approval decide <STORE> {suite_sha} approved",
            "web_decision": {"available": False, "reason": "owner_authentication_not_configured",
                             "detail": "Approval from the web needs a verified owner identity, which has not been chosen or configured. Decide at an owner terminal."}}


def suites(store: WriteOnceStore) -> list[dict]:
    out = []
    d = store.root / "objects" / "suite"
    for p in sorted(d.glob("*.json")) if d.exists() else []:
        s = store.get("suite", p.stem)
        st = suite_state(store, p.stem)
        out.append({"sha256": p.stem, "name": s.suite_name, "version": s.version, "site": s.site, "tasks": len(s.task_sha256s), "state": st["state"],
                    "refs": st["refs"], "synthetic": s.suite_name.startswith(AP.SYNTHETIC_PREFIX), "created_at": s.provenance.created_at,
                    "created_by": s.provenance.created_by, "gaps": len(s.gaps)})
    return sorted(out, key=lambda x: (x["synthetic"], x["name"], -x["version"]))
