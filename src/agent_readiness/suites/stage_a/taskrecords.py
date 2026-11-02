"""Stage A: map taskeval-2 records one-to-one onto the M1 lifecycle records (`suites.records`): `Wording`, `TaskSpec`, `TaskRecord`, `PrivateOutcome`.

Public `TaskSpec.evidence_paths` lists only pages the criterion itself names (the listing, or the looked-up page): the full evidence pages of set
and ranking tasks identify answer items, so they live in the private outcome, together with the expected answer, evidence texts, distractors
and the per-page details Stage B needs to rebuild a frozen task instance."""
from __future__ import annotations

from ...investigate.taskgen import freeze as freezer
from ...suite.core import canonical_hash
from ..records import InputRef, Limits, PrivateOutcome, Provenance, TaskRecord, TaskSpec, Validation, Wording, content_hash

UNEXECUTED_LIMITS = Limits(max_steps=8, max_model_requests=8, timeout_seconds=240)        # recorded for non-deterministic tasks; never used to score


def task_id(record: dict) -> str:
    """Stable id: the frozen-manifest id of the criterion plus the condition, or a wording hash for unexecuted tasks."""
    acc = record.get("_accepted")
    cond = record["wording"]["condition"]
    if acc is not None and record["verifiability"] == "deterministic":
        return f"{freezer.task_id(acc.fingerprint)}-{'n' if cond == 'natural' else 'a'}"
    return "cand-" + canonical_hash([record["wording"]["customer"], record["wording"]["category"]])[:10]


def public_evidence_paths(crit: dict | None) -> tuple[str, ...]:
    if not crit:
        return ()
    return tuple(p for p in (crit.get("listing"), crit.get("page")) if p)


def private_record(record: dict) -> dict:
    """The freeze-format private criterion (criteria, truth, evidence, distractors) for a deterministic task."""
    a = record["_accepted"]
    c = a.compiled
    return {"criterion": a.criterion, "kind": c.kind, "style": c.style, "truth": c.truth, "evidence_paths": list(c.evidence_paths),
            "evidence_texts": [list(t) for t in c.evidence_texts], "detail": c.detail, "min_hops": max(a.hops.values(), default=0), "distractors": list(c.distractors)}


def build(record: dict, *, site: str, snapshot_sha256: str, oracle_label: str, created_at: str, inputs: tuple[InputRef, ...], tool_version: str) -> tuple[TaskRecord, PrivateOutcome | None]:
    """(TaskRecord, PrivateOutcome or None) for one admitted taskeval-2 record (admission natural | assisted | preserved_unexecuted | rubric | human_review)."""
    if record["admission"] == "rejected":
        raise ValueError("rejected candidates do not become task records")
    w = record["wording"]
    wording = Wording(customer=w["customer"], executed=w["executed"], category=w["category"], interpretation_decisions=tuple(w["interpretation_decisions"]),
                      assumptions=tuple(w["assumptions"]), unresolved=tuple(w["unresolved"]))
    crit = record["specification"] or {}
    spec = TaskSpec(kind=crit.get("kind") or record.get("kind") or "open", criterion=crit, verifiability=record["verifiability"],
                    evidence_paths=public_evidence_paths(record["specification"]))
    priv = None
    if record["verifiability"] == "deterministic":
        p = private_record(record)
        priv = PrivateOutcome(spec_sha256=content_hash(spec), expected=p, evidence_texts=tuple((t[0], t[1]) for t in p["evidence_texts"]), oracle=oracle_label,
                              derived_from_snapshot=snapshot_sha256)
        lim = freezer._limits(record["_accepted"].hops)
        limits = Limits(max_steps=lim.max_steps, max_model_requests=lim.max_model_requests, timeout_seconds=lim.timeout_seconds)
    else:
        limits = UNEXECUTED_LIMITS
    gates = record["hard_gates"]
    reasons = tuple([f"admission: {record['admission']}", f"category: {w['category']}"] + [f"{k}: {'pass' if g['pass'] else 'fail'}" for k, g in gates.items()]
                    + ([f"nl verdict: {record['nl']['verdict']}"] if record.get("nl") else []))
    ev = record["evaluator"]
    task = TaskRecord(task_id=task_id(record), site=site, persona=record["persona"], journey=record["journey"], capability=record["capability"] or "open",
                      wording=wording, spec=spec, limits=limits, private_sha256=content_hash(priv) if priv else None,
                      validation=Validation(evaluator="taskeval", evaluator_version=ev["version"], config_fingerprint=ev["config_fingerprint"], passed=True, reasons=reasons),
                      provenance=Provenance(created_at=created_at, created_by="system", tool="agent_readiness.taskeval.v2", tool_version=tool_version,
                                            config_fingerprint=ev["config_fingerprint"], inputs=inputs,
                                            notes=f"candidate {record['candidate_id']}" + (f" (assisted derivative of {record['derived_from']})" if record.get("derived_from") else "")))
    return task, priv
