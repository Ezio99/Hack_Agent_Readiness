"""Baseline summary and the two PRE-REGISTERED Experiment-2 rules. Both are fixed here (and hashed into every manifest) before any trial runs; neither assumes a candidate website change helps.

  exp2-eligibility-v1  Which candidate variants deserve a controlled test? Decided from the BASELINE ONLY, from the investigation-partition tasks sensitive to each variant.
  exp2-compare-v1      Did a tested variant change agent behaviour? Variant vs a CONTEMPORANEOUS control arm, with negative controls, a drift check and a holdout guard.
Holdout tasks never influence eligibility; they only confirm or withdraw a comparison."""
from __future__ import annotations

from statistics import mean

from ..investigate.evaluate import design
from ..investigate.trials.stage import VOID_STATUSES
from ..suite.core import canonical_hash

ELIGIBILITY = {"id": "exp2-eligibility-v1", "min_tasks": 3, "troubled_ratio": 1.5, "min_troubled": 2, "min_troubled_fraction": 0.35, "max_void_fraction": 0.25,
               "need": "requests a task would need = pages_needed + 2 (navigate, read each page once, answer)",
               "troubled": "a task is troubled when it is not passed evidence-backed in the mean over its non-void baseline trials (< 1), OR its mean requests >= troubled_ratio x need",
               "eligible": "a variant is eligible for a controlled test when, over its sensitive INVESTIGATION tasks with usable trials (>= min_tasks), at least min_troubled tasks and min_troubled_fraction of them are troubled",
               "not_eligible": "otherwise: the baseline shows no friction of the kind the variant addresses, so it is NOT tested (a null baseline is a result)",
               "uninterpretable": "when more than max_void_fraction of the sensitive trials are void"}
COMPARE = {"id": "exp2-compare-v1", "min_pairs": 6, "alpha": 0.10, "pass_delta_floor": 0.15, "request_reduction_floor": 0.25, "primary": "evidence_backed_pass_rate", "secondary": "model_requests",
           "improvement": design.RULE["improvement"], "regression": design.RULE["regression"], "holdout_guard": design.RULE["holdout_guard"], "otherwise": "inconclusive",
           "void_policy": design.RULE["void_policy"], "control": "the control arm is run CONTEMPORANEOUSLY (same period, same agent and model, same tasks); the baseline is only a secondary reference",
           "drift": "if the contemporaneous control's mean requests differ from the baseline's by more than drift_tolerance (relative) on the shared tasks, no improvement is claimed",
           "drift_tolerance": 0.25, "negative_controls": "tasks NOT sensitive to the variant must not move: relative change in mean requests within neg_tolerance and no loss of evidence-backed pass; otherwise `uninterpretable`",
           "neg_tolerance": 0.25, "min_negative_controls": 3, "causal_scope": "this site, these tasks, this agent profile and model; an association measured under control, never a general claim"}
RULES_SHA256 = canonical_hash({"eligibility": ELIGIBILITY, "compare": COMPARE})


def row(rec: dict, task: dict) -> dict:
    void = rec["outcome"]["run_status"] in VOID_STATUSES
    return {"task_id": rec["task_id"], "repeat": rec["repeat"], "partition": task["partition"], "family": task["family"], "difficulty": task["difficulty"], "void": void,
            "passed": bool(rec["evaluation"]["passed"]), "evidence_backed": bool(rec["evaluation"]["evidence_backed"]), "model_requests": rec["metrics"]["model_requests"], "page_views": rec["metrics"]["page_views"],
            "cost_usd": rec["metrics"]["calculated_cost_usd"], "status": rec["outcome"]["run_status"], "pages_needed": task["pages_needed"], "primary": "x"}


def _mean_ok(rows: list[dict]) -> float:
    return mean(1.0 if r["evidence_backed"] else 0.0 for r in rows)


def eligibility(rows: list[dict], plan: dict) -> dict:
    """rows: `row()` records of the control baseline. Returns, per variant, the decision and the numbers behind it."""
    tasks = {t["task_id"]: t for t in plan["tasks"]}
    out = {}
    for v in ("discoverability", "availability", "cost", "compatibility"):
        sens = [t for t in tasks.values() if v in t["sensitive_to"] and t["partition"] == "investigation"]
        trials = [r for r in rows if r["task_id"] in {t["task_id"] for t in sens}]
        void = sum(r["void"] for r in trials)
        per_task = []
        for t in sens:
            ok = [r for r in trials if r["task_id"] == t["task_id"] and not r["void"]]
            if ok:
                ratio = mean(r["model_requests"] for r in ok) / (t["pages_needed"] + 2)
                per_task.append({"task_id": t["task_id"], "pass_rate": round(_mean_ok(ok), 3), "request_ratio": round(ratio, 3), "troubled": _mean_ok(ok) < 1 or ratio >= ELIGIBILITY["troubled_ratio"]})
        troubled = sum(p["troubled"] for p in per_task)
        if trials and void / len(trials) > ELIGIBILITY["max_void_fraction"]:
            decision = "uninterpretable"
        elif len(per_task) < ELIGIBILITY["min_tasks"]:
            decision = "not_eligible_too_few_tasks"
        elif troubled >= ELIGIBILITY["min_troubled"] and troubled / len(per_task) >= ELIGIBILITY["min_troubled_fraction"]:
            decision = "eligible"
        else:
            decision = "not_eligible_no_friction_observed"
        out[v] = {"decision": decision, "tasks_with_data": len(per_task), "troubled": troubled, "void_trials": void, "sensitive_investigation_tasks": len(sens), "per_task": per_task}
    return out


def baseline_summary(records: list[dict], plan: dict) -> dict:
    tasks = {t["task_id"]: t for t in plan["tasks"]}
    rows = [row(r, tasks[r["task_id"]]) for r in records if r["task_id"] in tasks]
    ok = [r for r in rows if not r["void"]]

    def agg(rs):
        u = [r for r in rs if not r["void"]]
        return {"trials": len(rs), "void": len(rs) - len(u), "evidence_backed_pass_rate": round(_mean_ok(u), 3) if u else None, "mean_requests": round(mean(r["model_requests"] for r in u), 2) if u else None,
                "cost_usd": round(sum(r["cost_usd"] or 0 for r in rs), 4)}
    by = lambda key: {k: agg([r for r in rows if r[key] == k]) for k in sorted({r[key] for r in rows})}
    return {"rules": {"eligibility": ELIGIBILITY, "compare": COMPARE, "rules_sha256": RULES_SHA256}, "trials": len(rows), "void": len(rows) - len(ok), "overall": agg(rows), "by_family": by("family"), "by_difficulty": by("difficulty"),
            "by_partition": by("partition"), "eligibility": eligibility(rows, plan), "cost_basis": "calculated at published prices; not a bill", "rows": rows}


def compare_variant(variant: str, control_rows: list[dict], variant_rows: list[dict], baseline_rows: list[dict], plan: dict) -> dict:
    """Pre-registered comparison for ONE tested variant. `control_rows` = the contemporaneous control arm on the same tasks; `baseline_rows` = the earlier baseline (secondary reference, drift check)."""
    tasks = {t["task_id"]: t for t in plan["tasks"]}
    part = {tid: t["partition"] for tid, t in tasks.items()}
    affected = {tid for tid, t in tasks.items() if variant in t["sensitive_to"]}
    group = lambda rows, ids: {tid: [r for r in rows if r["task_id"] == tid] for tid in ids if any(r["task_id"] == tid for r in rows)}
    main = design.compare(group(control_rows, affected), group(variant_rows, affected), part, COMPARE)
    neg_ids = {tid for tid in tasks if tid not in affected} & {r["task_id"] for r in variant_rows}
    neg = design.compare(group(control_rows, neg_ids), group(variant_rows, neg_ids), part, {**COMPARE, "min_pairs": 1})
    drift = None
    shared = {r["task_id"] for r in control_rows} & {r["task_id"] for r in baseline_rows}
    if shared:
        a = mean(r["model_requests"] for r in control_rows if r["task_id"] in shared and not r["void"])
        b = mean(r["model_requests"] for r in baseline_rows if r["task_id"] in shared and not r["void"])
        drift = round((a - b) / b, 3) if b else None
    verdict, reasons = main["verdict"], [main.get("reason", "")]
    if neg["pairs"] < COMPARE["min_negative_controls"]:
        verdict, reasons = "uninterpretable", [f"only {neg['pairs']} negative-control pairs (minimum {COMPARE['min_negative_controls']})"]
    else:
        moved = [r for r in neg["rows"] if abs(r["patched_requests"] - r["base_requests"]) / max(r["base_requests"], 1) > COMPARE["neg_tolerance"] or r["patched_pass"] < r["base_pass"]]
        if len(moved) > len(neg["rows"]) / 3:
            verdict, reasons = "uninterpretable", [f"{len(moved)} of {neg['pairs']} negative controls moved beyond tolerance"]
    if verdict == "improvement" and drift is not None and abs(drift) > COMPARE["drift_tolerance"]:
        verdict, reasons = "inconclusive_conflicting_comparisons", [f"the contemporaneous control drifted {drift:+.0%} from the baseline: no improvement is claimed"]
    return {"rule": COMPARE["id"], "rules_sha256": RULES_SHA256, "variant": variant, "verdict": verdict, "reasons": reasons, "control_drift": drift, "primary": main, "negative_controls": {k: neg[k] for k in ("pairs", "rows")}}
