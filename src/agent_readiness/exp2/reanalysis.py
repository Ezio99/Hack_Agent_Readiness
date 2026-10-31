"""Versioned, READ-ONLY re-analysis of a finished run under the corrected evaluation rules (`exp2-evidence-v2`, `exp2-names-v2`), shown NEXT TO the original outcomes.

The original run directory is never opened for writing: trial records, observations, criteria, manifests, approvals and the ledger stay byte-identical, and the report carries a digest of the whole
directory so a reader can check that. ORIGINAL outcomes are regenerated from the stored artifacts with the frozen v1 matcher and the answer exactly as graded at the time; CORRECTED outcomes use the
current rules on the very same stored answers and the very same model-visible observations. Nothing is re-run, nothing is paid for, and no truth is written to the report."""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from statistics import mean

from ..suite.core import canonical_hash
from . import answers as A, evidence as E, evidence_v1 as E1, modelview
from .instances import private_record
from .pool import build_pool
from .study import EXECUTED_PILOT, build_plan
from .tasks import ANAME, PNAME

REPORT_SCHEMA = "exp2-reanalysis-v1"


def tree_digest(root: Path) -> dict:
    """SHA-256 over `sha256  ./relative/path` lines of every file, in byte order (the same text `find . -type f | sort | xargs sha256sum` prints)."""
    lines = []
    for p in sorted(x for x in root.rglob("*") if x.is_file()):
        lines.append(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  ./{p.relative_to(root).as_posix()}\n")
    lines.sort(key=lambda l: l.split("  ", 1)[1].rstrip("\n").encode())
    return {"files": len(lines), "sha256": hashlib.sha256("".join(lines).encode()).hexdigest()}


def _json(p: Path):
    return json.loads(p.read_text())


def _names(kind: str) -> dict:
    return ANAME if kind in ("accessory", "accessories") else PNAME if kind in ("product", "products") else {}


def _answer(rec: dict, kind: str):
    a = (rec["outcome"].get("answer") or {})
    return a.get("answers" if kind in A.SET_KINDS else "answer")


def reanalyse(run_dir: Path) -> dict:
    run_dir = Path(run_dir)
    before = tree_digest(run_dir)
    plan, priv = _json(run_dir / "artifacts" / "study-plan.json"), _json(run_dir / "private" / "criteria.json")
    tasks = {t["task_id"]: t for t in plan["tasks"]}
    report, _ = build_pool()
    cand = {c.task_id: c for c in report.accepted}
    rows = []
    for f in sorted((run_dir / "artifacts" / "trials").glob("baseline-*.json")):
        rec = _json(f)
        tid, t, p = rec["task_id"], tasks[rec["task_id"]], priv[rec["task_id"]]
        obs = _json(run_dir / rec["trial_dir"] / "observations.json")
        kind, ans = p["kind"], _answer(rec, p["kind"])
        names = _names(kind)
        ok_then = bool(rec["evaluation"]["passed"])
        ok_now = A.grade(kind, p["truth"], ans, options=tuple(p["options"]), names=names)
        v1, v2 = E1.assess(p["facts"], obs), E.assess(cand[tid].facts, obs)
        exact = isinstance(ans, str) and kind in ("product", "accessory") and A.norm_answer(ans) == A.norm_answer(p["expected_text"])
        need = t["pages_needed"] + 2
        m = rec["metrics"]
        rows.append({
            "trial": rec["trial_id"], "task_id": tid, "family": t["family"], "difficulty": t["difficulty"], "partition": t["partition"], "status": rec["outcome"]["run_status"],
            "original": {"correct": ok_then, "evidence_sufficient": v1["sufficient"], "evidence_missing": v1["missing"], "supported_pass": ok_then and v1["sufficient"], "rules": ["exp2-evidence-v1", "exp2-names-v1"]},
            "corrected": {"correct": ok_now, "evidence_sufficient": v2["sufficient"], "evidence_missing": v2["missing"], "supported_pass": ok_now and v2["sufficient"], "rules": [E.RULE_VERSION, A.NAME_RULE]},
            "changed": {"correctness": ok_then != ok_now, "evidence": v1["sufficient"] != v2["sufficient"]},
            "needs_review": ([ "correct only through unit-spacing normalisation (not the exact displayed name)" ] if ok_now and kind in ("product", "accessory") and not exact and not ok_then else [])
                            + ([ "evidence sufficient only under the v2 matcher" ] if v2["sufficient"] and not v1["sufficient"] else []),
            "model_requests": m["model_requests"], "request_limit": m["limits"]["max_model_requests"], "page_views": m["page_views"], "distinct_pages": len({j.get("path") for j in rec.get("journey", [])}),
            "request_ratio": round(m["model_requests"] / need, 2), "cost_usd": m["calculated_cost_usd"]})
    summ = lambda key: {"trials": len(rows), "correct": sum(r[key]["correct"] for r in rows), "evidence_sufficient": sum(r[key]["evidence_sufficient"] for r in rows),
                        "supported_passes": sum(r[key]["supported_pass"] for r in rows)}
    after = tree_digest(run_dir)
    revised = build_plan(report.accepted, executed=EXECUTED_PILOT)
    crit = json.loads(json.dumps({t["task_id"]: private_record(cand[t["task_id"]]) for t in revised["tasks"]}, default=str))
    return {"schema": REPORT_SCHEMA, "run_id": run_dir.name, "rules": {"original": ["exp2-evidence-v1", "exp2-names-v1"], "corrected": [E.RULE_VERSION, A.NAME_RULE]},
            "integrity": {"original_run_tree_before": before, "original_run_tree_after": after, "unchanged": before == after,
                          "original_plan_sha256": plan["plan_sha256"], "original_criteria_sha256": canonical_hash(priv), "corrected_criteria_sha256": canonical_hash(crit), "revised_plan_commit_hash": revised["plan_sha256"],
                          "model_views_sha256": modelview.views_sha256()},
            "summary": {"original": summ("original"), "corrected": summ("corrected"), "changed_trials": [r["trial"] for r in rows if r["changed"]["correctness"] or r["changed"]["evidence"]],
                        "needs_review": {r["trial"]: r["needs_review"] for r in rows if r["needs_review"]}, "mean_request_ratio": round(mean(r["request_ratio"] for r in rows), 2),
                        "cost_usd": round(sum(r["cost_usd"] for r in rows), 4), "statuses": dict(Counter(r["status"] for r in rows))},
            "trials": rows,
            "note": "Original outcomes were produced by the rules in force during the pilot and are kept as the experimental record. Corrected outcomes apply the amended rules to the same stored answers and observations; no trial was re-run. No truth is stored here."}
