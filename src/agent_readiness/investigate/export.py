"""Sanitized, read-only export of one investigation run for the dashboard (`investigation-dashboard-v1`, Task 016 M7).

Whitelist, never copy: every field below is picked by name from the run's public records. Never exported: `private/` (criteria, truth, accepted drafts, transcripts), the agent's answers,
journeys, mirror logs, trial directories, tool logs, model transcripts, absolute paths, credentials. The export tolerates incomplete runs (any stage missing, no report, no evaluation) and says
what is missing instead of failing. It reads files only: no model, network, browser or approval gate is touched."""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

from .flow import STAGES as FLOW_STAGES
from .models import now
from .evaluate import exploratory
from .report import NOTICES
from .run import InvestigationRun
from .trials.stage import VOID_STATUSES

SCHEMA = "investigation-dashboard-v1"
MODES = ("scripted", "mock", "recorded", "live")
FORBIDDEN_KEYS = {"truth", "criteria", "criterion", "expected", "expected_answer", "answer", "answers", "transcript", "journey", "tool_log", "api_key", "authorization", "evidence_texts", "evidence_paths"}
SECRET = re.compile(r"META_MODEL_API_KEY|\bsk-[A-Za-z0-9]{16,}|Bearer\s+[A-Za-z0-9._-]{16,}|/home/[a-z]|/Users/[A-Za-z]|/tmp/")


class ExportError(ValueError):
    pass


def _artifact(run: InvestigationRun, name: str):
    try:
        return run.artifact(name) if run.has_artifact(name) else None
    except (OSError, ValueError):
        return None                                  # unreadable or truncated artifact: treat as missing, the export reports it


def _pick(d: dict | None, keys) -> dict:
    d = d or {}
    return {k: d.get(k) for k in keys}


def _stage_summary(s: dict) -> dict:
    keep = {k: v for k, v in (s.get("summary") or {}).items() if isinstance(v, (str, int, float, bool)) or v is None}
    return {"status": s.get("status", "pending"), "updated_at": s.get("updated_at"), "skipped": bool(keep.get("skipped")), "reason": keep.get("reason"),
            "manifest_sha256": s.get("manifest_sha256"), "summary": {k: v for k, v in keep.items() if k not in ("skipped", "reason")}}


def _trial_row(t: dict, partition: str | None = None) -> dict:
    status = (t.get("outcome") or {}).get("run_status")
    ev, m = t.get("evaluation") or {}, t.get("metrics") or {}
    void = status in VOID_STATUSES
    return {"trial_id": t.get("trial_id"), "repeat": t.get("repeat"), "run_status": status, "void": void, "passed": None if void else bool(ev.get("passed")),
            "evidence_backed": None if void else bool(ev.get("evidence_backed")), "model_requests": m.get("model_requests"), "page_views": m.get("page_views"),
            "mode": (t.get("trial") or {}).get("mode")}


def _trials(run: InvestigationRun) -> tuple[dict, dict, dict]:
    """(baseline by task id, patched by proposal id then task id, unmodified repeats ("placebo") by proposal id then task id). Rebuilt from the per-trial records, so failures and void trials are all present."""
    base: dict[str, list] = {}
    patched: dict[str, dict[str, list]] = {}
    placebo: dict[str, dict[str, list]] = {}
    for path in sorted((run.dir / "artifacts" / "trials").glob("*.json")):
        t = _artifact(run, f"trials/{path.stem}")
        if not t or "task_id" not in t:
            continue
        row = _trial_row(t)
        if path.stem.startswith("baseline-"):
            base.setdefault(t["task_id"], []).append(row)
        elif path.stem.startswith(("patched-", "placebo-")):
            pid = "-".join(path.stem.split("-")[1:3])          # artifact name is patched-|placebo-<proposal id>-<task id>-r<n>; a proposal id is prp-<10 hex>
            (patched if path.stem.startswith("patched-") else placebo).setdefault(pid, {}).setdefault(t["task_id"], []).append(row)
    return base, patched, placebo


def _resolve_support(refs: list[str], trial_ids: set[str], task_ids: set[str]) -> list[dict]:
    out = []
    for r in refs:
        body = r.split(":", 1)[-1].split("#", 1)[0]
        out.append({"ref": r, "resolved": body in trial_ids or body in task_ids})
    return out


EXPLORATORY_KEYS = ("rules_id", "rules_sha256", "label", "verdict", "reasons", "tasks", "missing_or_void", "noise_estimate_requests", "controls_within_tolerance", "affected")


def _exploratory(run: InvestigationRun, e: dict) -> dict | None:
    """The separate EXP-B analysis (never the frozen verdict). Whitelisted: numeric per-arm rows, the verdict with its reasons, the task roles and the rules summary only when the stored hash matches the code."""
    x = e.get("exploratory")
    if not x:
        return None
    plan = _artifact(run, "post-plan") or {}
    rules_ok = x.get("rules_sha256") == exploratory.RULES_SHA256
    rules = {k: exploratory.RULES[k] for k in ("id", "label", "primary_comparison", "secondary_comparison", "effect_floor", "support", "noise_estimate", "same_shape_control_tolerance_requests",
                                                "detail_control_tolerance_requests", "controls", "drift", "conflict", "verdicts", "claims")} if rules_ok else None
    return {**_pick(x, EXPLORATORY_KEYS), "plan": _pick(plan, ("placebo_tasks", "affected", "same_shape_controls", "detail_controls")), "rules": rules, "rules_match_code": rules_ok}


def _evaluation(run: InvestigationRun, ev) -> dict:
    e = _artifact(run, "evaluation")
    if e is None:
        return {"state": "missing", "reason": "no evaluation artifact (the evaluate stage has not run)", "rule": None, "results": [], "exploratory": None}
    if not e.get("evaluated"):
        return {"state": "not_evaluated", "reason": e.get("reason") or "not evaluated", "rule": None, "results": [], "exploratory": None}
    measured = {x.proposal_id: x for x in ev.effects.values()}
    results = []
    for pid, r in (e.get("results") or {}).items():
        eff = measured.get(pid)
        results.append({"proposal_id": pid, **_pick(r, ("verdict", "reason", "pairs", "pass_delta", "request_change", "p_pass", "p_requests", "holdout_consistent", "by_partition", "rule_preregistered_at_freeze")),
                        "excluded": [_pick(x, ("task_id", "reason")) for x in r.get("excluded") or []], "measured": bool(eff and eff.measured), "effect_mode": eff.provenance.mode if eff else None})
    rule = e.get("rule") or {}
    return {"state": "evaluated", "reason": None, "rule": _pick(rule, ("id", "primary", "secondary", "alpha", "min_pairs", "pass_delta_floor", "request_reduction_floor", "void_policy", "causal_scope")), "results": results, "exploratory": _exploratory(run, e)}


def _spend(run: InvestigationRun) -> dict:
    """Calculated (published-price) spend from the durable ledger, by arm: never a bill. Ids are `<trial or stage>:<request>`; trial ids start with the arm label."""
    try:
        rows = [json.loads(line) for line in (run.dir / "spend" / "ledger.jsonl").read_text().splitlines() if line.strip()]
    except (OSError, ValueError):
        return {"state": "missing"}
    settled = {r["id"]: r["usd"] for r in rows if r.get("kind") == "settle"}
    open_ = {r["id"] for r in rows if r.get("kind") == "reserve"} - set(settled)
    by_arm: dict[str, float] = {}
    by_trial: dict[str, float] = {}
    for rid, usd in settled.items():
        trial = rid.split(":")[0]
        arm = trial.split("-")[0] if trial.split("-")[0] in ("baseline", "patched", "placebo") else "other"
        by_arm[arm] = by_arm.get(arm, 0) + usd
        if arm != "other":
            by_trial[trial] = by_trial.get(trial, 0) + usd
    total = sum(settled.values())
    ceiling = (run.state.get("config") or {}).get("total_cap_usd")
    r6 = lambda x: round(x, 6)
    return {"state": "ok", "basis": "calculated at published prices from the spend ledger; not a bill", "committed_usd": r6(total), "ceiling_usd": ceiling, "remaining_usd": r6(ceiling - total) if ceiling else None,
            "open_reservations": len(open_), "by_arm_usd": {k: r6(v) for k, v in sorted(by_arm.items())}, "by_trial_usd": {k: r6(v) for k, v in sorted(by_trial.items())}}


def export_run(run_dir: Path | str) -> dict:
    run = InvestigationRun(Path(run_dir))
    state, ev = run.state, run.evidence
    missing = []

    def need(name):
        art = _artifact(run, name)
        if art is None:
            missing.append(name)
        return art
    manifest = need("tasks-manifest")
    final, interim = _artifact(run, "report-final"), _artifact(run, "report")
    report_source = "report-final" if final else "report" if interim else "evidence"
    if not final:
        missing.append("report-final")
    base, patched, placebo = _trials(run)
    trial_ids = {r["trial_id"] for rows in base.values() for r in rows} | {r["trial_id"] for arm in (patched, placebo) for by in arm.values() for rows in by.values() for r in rows}
    task_ids = {t["task_id"] for t in (manifest or {}).get("tasks", [])}
    attribution = _artifact(run, "attribution") or {}
    att_by_task: dict[str, list] = {}
    for tid, a in attribution.items():
        att_by_task.setdefault(a["task_id"], []).append({"trial_id": tid, **_pick(a, ("primary", "void", "why"))})
    for rows in base.values():
        for r in rows:
            for a in att_by_task.get(r["trial_id"].rsplit("-r", 1)[0], []):
                if a["trial_id"] == r["trial_id"]:
                    r["attribution"] = a["primary"]
                    r["why"] = a["why"]
    tasks = [{**_pick(t, ("task_id", "question", "kind", "source", "partition", "start_path")), "limits": t.get("limits"), "baseline": base.get(t["task_id"], []), "patched": {pid: by.get(t["task_id"], []) for pid, by in patched.items()},
             "placebo": {pid: by[t["task_id"]] for pid, by in placebo.items() if t["task_id"] in by}}
             for t in (manifest or {}).get("tasks", [])]
    modes = sorted({x.provenance.mode for coll in (ev.observations, ev.hypotheses, ev.findings, ev.proposals, ev.effects) for x in coll.values()} | {run.mode} | {r["mode"] for rows in base.values() for r in rows if r["mode"]},
                   key=MODES.index)
    prov = lambda x: {"mode": x.provenance.mode, "source": x.provenance.source}
    findings = []
    for f in ev.findings.values():
        h = ev.hypotheses.get(f.hypothesis_id)
        cites = h.citations if h else []
        findings.append({"id": f.id, "hypothesis_id": f.hypothesis_id, "statement": f.statement, "attribution": f.attribution, "structural_proof": f.structural_proof, "provenance": prov(f),
                         "observation_ids": [c for c in cites if c in ev.observations], "unresolved_observation_ids": [c for c in cites if c not in ev.observations],
                         "support": _resolve_support(f.support, trial_ids, task_ids)})
    promoted = {f.hypothesis_id for f in ev.findings.values()}
    inv = _artifact(run, "investigation") or {}
    rep_inv = (final or interim or {}).get("investigation") or inv
    out = {
        "schema": SCHEMA, "exported_at": now(),
        "run": {"id": state["id"], "target": state["target"], "mode": state["mode"], "created_at": state.get("created_at"), "outcome": (final or interim or {}).get("outcome") or ev.outcome(), "investigation_status": (final or interim or {}).get("investigation_status"), "report_source": report_source,
                "complete": report_source == "report-final" and all(s.get("status") == "done" for s in state["stages"].values()), "missing_artifacts": sorted(set(missing))},
        "modes": modes, "notices": [NOTICES[m] for m in modes],
        "stages": [{"name": n, **_stage_summary(s)} for n, s in sorted(state["stages"].items(), key=lambda kv: FLOW_STAGES.index(kv[0]) if kv[0] in FLOW_STAGES else len(FLOW_STAGES))],      # run.json is written with sorted keys; restore pipeline order
        "tasks": tasks,
        "trials": {"baseline": sum(len(r) for r in base.values()), "patched": sum(len(r) for by in patched.values() for r in by.values()), "placebo": sum(len(r) for by in placebo.values() for r in by.values()),
                   "void": sum(r["void"] for rows in base.values() for r in rows) + sum(r["void"] for arm in (patched, placebo) for by in arm.values() for rows in by.values() for r in rows),
                   "quarantined": len(list((run.dir / "artifacts" / "trials-quarantine").glob("*.json"))),
                   "note": "Void trials (provider, budget, infrastructure, fidelity guard) are never website results and are excluded from comparisons."},
        "observations": [{"id": o.id, "kind": o.kind, "summary": o.summary, "refs": o.refs, "provenance": prov(o)} for o in ev.observations.values()],
        "hypotheses": [{"id": h.id, "tier": h.tier, "statement": h.statement, "claim_kind": h.claim_kind, "prediction": h.prediction, "status": h.status, "observation_ids": h.citations,
                        "verification": _pick(h.verification.model_dump(), ("verifier", "result", "evidence")) if h.verification else None, "promoted": h.id in promoted, "provenance": prov(h)}
                       for h in ev.hypotheses.values()],
        "findings": findings,
        "proposals": [{"id": p.id, "basis": p.basis, "source_id": p.source_id, "label": p.label, "status": p.status, "validation": p.validation, "expected_effect": p.expected_effect, "risks": p.risks,
                       "auto_applicable": p.auto_applicable, "owner_selected": bool(p.change.get("owner_selected")), "exploratory": bool(p.change.get("exploratory")), "change": {"manual": p.change["manual"]} if "manual" in p.change else {"ops": [o.get("op") for o in p.change.get("ops", [])]}, "approved": bool(p.approvals), "provenance": prov(p)}
                      for p in ev.proposals.values()],
        "evaluation": _evaluation(run, ev), "spend": _spend(run),
        "effects": [{"id": e.id, "proposal_id": e.proposal_id, "verdict": e.verdict, "n_pairs": e.n_pairs, "note": e.note, "measured": e.measured, "mode": e.provenance.mode} for e in ev.effects.values()],
        "investigation": {**_pick(rep_inv, ("skipped", "reason", "finished", "incomplete", "tool_calls", "model_requests", "model", "mode", "cost_usd")), "rejected_hypotheses": len(rep_inv.get("rejected_hypotheses") or [])},
        "statement": (final or interim or {}).get("statement"),
    }
    check_clean(out)
    return out


def check_clean(obj, path: str = "$") -> None:
    """Fail closed: refuse an export that contains a forbidden key, a credential-like string or a local path."""
    env_key = os.environ.get("META_MODEL_API_KEY")
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k.lower() in FORBIDDEN_KEYS:
                raise ExportError(f"forbidden key {k!r} at {path}")
            check_clean(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            check_clean(v, f"{path}[{i}]")
    elif isinstance(obj, str) and (SECRET.search(obj) or (env_key and env_key in obj)):
        raise ExportError(f"credential-like string or local path at {path}")


def write_export(run_dir: Path | str, out: Path | str) -> dict:
    data = export_run(run_dir)
    Path(out).write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
    return data
