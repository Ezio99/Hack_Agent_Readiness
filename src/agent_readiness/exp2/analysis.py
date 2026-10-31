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
               "troubled": "a task is troubled when its supported-pass rate (correct AND evidence sufficient) is below 1 over its non-void baseline trials, OR its mean requests >= troubled_ratio x need; the two causes are reported separately",
               "eligible": "a variant is eligible for a controlled test when, over its sensitive INVESTIGATION tasks with usable trials (>= min_tasks), at least min_troubled tasks and min_troubled_fraction of them are troubled",
               "not_eligible": "otherwise: the baseline shows no friction of the kind the variant addresses, so it is NOT tested (a null baseline is a result)",
               "uninterpretable": "when more than max_void_fraction of the sensitive trials are void"}
COMPARE = {"id": "exp2-compare-v1", "min_pairs": 6, "alpha": 0.10, "pass_delta_floor": 0.15, "request_reduction_floor": 0.25, "primary": "supported_pass_rate", "secondary": "model_requests",
           "min_repeats_affected": 2, "min_repeats_negative": 1, "evidence_asymmetry_tolerance": 0.15,
           "repeats": "every affected task needs at least min_repeats_affected non-void trials in BOTH arms and every negative control at least min_repeats_negative; a task below that is excluded and listed",
           "evidence": "evidence sufficiency is page-agnostic and identical in every arm; if the share of correct answers WITHOUT sufficient evidence differs between the arms by more than evidence_asymmetry_tolerance, no improvement is claimed",
           "improvement": design.RULE["improvement"], "regression": design.RULE["regression"], "holdout_guard": design.RULE["holdout_guard"], "otherwise": "inconclusive",
           "void_policy": design.RULE["void_policy"], "control": "the control arm is run CONTEMPORANEOUSLY (same period, same agent and model, same tasks); the baseline is only a secondary reference",
           "drift": "if the contemporaneous control's mean requests differ from the baseline's by more than drift_tolerance (relative) on the shared tasks, no improvement is claimed",
           "drift_tolerance": 0.25, "negative_controls": "tasks NOT sensitive to the variant must not move: relative change in mean requests within neg_tolerance and no loss of evidence-backed pass; otherwise `uninterpretable`",
           "neg_tolerance": 0.25, "min_negative_controls": 3, "causal_scope": "this site, these tasks, this agent profile and model; an association measured under control, never a general claim"}
RULES_SHA256 = canonical_hash({"eligibility": ELIGIBILITY, "compare": COMPARE})


def row(rec: dict, task: dict, ev: dict | None = None) -> dict:
    """One trial, with the THREE measurements kept apart.
      correct              the answer matched the independently derived truth                      (field `passed`)
      evidence_sufficient  the model was shown the facts the answer depends on, on ANY page        (field `evidence_backed`; see evidence.py; `ev` is its assessment)
      efficiency           requests / page views / distinct pages against what the task needs      (fields `request_ratio`, `page_views`, `distinct_pages`)
    `supported` = correct AND evidence_sufficient is the primary outcome (a correct answer the model could not have derived from what it was shown does not count)."""
    void = rec["outcome"]["run_status"] in VOID_STATUSES
    suff = bool(ev and ev.get("sufficient"))
    need = task["pages_needed"] + 2
    return {"task_id": rec["task_id"], "repeat": rec["repeat"], "partition": task["partition"], "family": task["family"], "difficulty": task["difficulty"], "void": void,
            "passed": bool(rec["evaluation"]["passed"]), "evidence_backed": suff, "supported": bool(rec["evaluation"]["passed"]) and suff, "evidence_missing": (ev or {}).get("missing", []),
            "model_requests": rec["metrics"]["model_requests"], "page_views": rec["metrics"]["page_views"], "distinct_pages": len({j.get("path") for j in rec.get("journey", [])}), "request_ratio": round(rec["metrics"]["model_requests"] / need, 3),
            "cost_usd": rec["metrics"]["calculated_cost_usd"], "status": rec["outcome"]["run_status"], "pages_needed": task["pages_needed"], "primary": "x"}


def _mean_ok(rows: list[dict]) -> float:
    """Supported-pass rate: correct AND evidence sufficient."""
    return mean(1.0 if r["passed"] and r["evidence_backed"] else 0.0 for r in rows)


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


def baseline_summary(records: list[dict], plan: dict, evidence: dict[str, dict] | None = None) -> dict:
    """`evidence` = {trial name -> assessment} (flow.annotate); a trial without an assessment counts as NOT sufficient."""
    tasks = {t["task_id"]: t for t in plan["tasks"]}
    rows = [row(r, tasks[r["task_id"]], (evidence or {}).get(r["trial_id"] if "trial_id" in r else "")) for r in records if r["task_id"] in tasks]
    ok = [r for r in rows if not r["void"]]

    def agg(rs):
        u = [r for r in rs if not r["void"]]
        c = [r for r in u if r["passed"]]
        return {"trials": len(rs), "void": len(rs) - len(u), "correct_rate": round(mean(1.0 if r["passed"] else 0.0 for r in u), 3) if u else None,
                "evidence_sufficiency_rate_among_correct": round(mean(1.0 if r["evidence_backed"] else 0.0 for r in c), 3) if c else None,
                "supported_pass_rate": round(_mean_ok(u), 3) if u else None, "mean_requests": round(mean(r["model_requests"] for r in u), 2) if u else None,
                "mean_request_ratio": round(mean(r["request_ratio"] for r in u), 2) if u else None, "mean_page_views": round(mean(r["page_views"] for r in u), 2) if u else None,
                "mean_distinct_pages": round(mean(r["distinct_pages"] for r in u), 2) if u else None, "cost_usd": round(sum(r["cost_usd"] or 0 for r in rs), 4)}
    by = lambda key: {k: agg([r for r in rows if r[key] == k]) for k in sorted({r[key] for r in rows})}
    return {"rules": {"eligibility": ELIGIBILITY, "compare": COMPARE, "rules_sha256": RULES_SHA256}, "trials": len(rows), "void": len(rows) - len(ok), "overall": agg(rows), "by_family": by("family"), "by_difficulty": by("difficulty"),
            "by_partition": by("partition"), "eligibility": eligibility(rows, plan), "cost_basis": "calculated at published prices; not a bill", "rows": rows}


def _eligible_groups(rows: list[dict], ids, min_n: int) -> dict:
    out = {}
    for tid in ids:
        rs = [r for r in rows if r["task_id"] == tid]
        if rs:
            out[tid] = rs
    return out


def _share_unsupported(rows: list[dict]) -> float | None:
    c = [r for r in rows if r["passed"] and not r["void"]]
    return round(mean(0.0 if r["evidence_backed"] else 1.0 for r in c), 3) if c else None


def compare_variant(variant: str, control_rows: list[dict], variant_rows: list[dict], baseline_rows: list[dict], plan: dict) -> dict:
    """Pre-registered comparison for ONE tested variant. `control_rows` = the contemporaneous control arm on the same tasks; `baseline_rows` = the earlier baseline (secondary reference, drift check).
    Affected tasks need >= min_repeats_affected non-void trials in both arms (K >= 2), negative controls >= min_repeats_negative; tasks below that are excluded and listed."""
    tasks = {t["task_id"]: t for t in plan["tasks"]}
    part = {tid: t["partition"] for tid, t in tasks.items()}
    affected = {tid for tid, t in tasks.items() if variant in t["sensitive_to"]}
    neg_ids = ({tid for tid in tasks if tid not in affected} & {r["task_id"] for r in variant_rows}) | set()
    n_ok = lambda rows, tid: sum(1 for r in rows if r["task_id"] == tid and not r["void"])
    short = []

    def keep(ids, k):
        ok = set()
        for tid in ids:
            if n_ok(control_rows, tid) >= k and n_ok(variant_rows, tid) >= k:
                ok.add(tid)
            elif any(r["task_id"] == tid for r in variant_rows + control_rows):
                short.append({"task_id": tid, "reason": f"fewer than {k} non-void trials in an arm"})
        return ok
    aff_ok, neg_ok = keep(affected, COMPARE["min_repeats_affected"]), keep(neg_ids, COMPARE["min_repeats_negative"])
    group = lambda rows, ids: {tid: [r for r in rows if r["task_id"] == tid] for tid in ids}
    main = design.compare(group(control_rows, aff_ok), group(variant_rows, aff_ok), part, COMPARE)
    neg = design.compare(group(control_rows, neg_ok), group(variant_rows, neg_ok), part, {**COMPARE, "min_pairs": 1})
    drift = None
    shared = {r["task_id"] for r in control_rows} & {r["task_id"] for r in baseline_rows}
    if shared:
        a = mean(r["model_requests"] for r in control_rows if r["task_id"] in shared and not r["void"])
        b = mean(r["model_requests"] for r in baseline_rows if r["task_id"] in shared and not r["void"])
        drift = round((a - b) / b, 3) if b else None
    audit = {"control_unsupported_share": _share_unsupported([r for r in control_rows if r["task_id"] in aff_ok]), "variant_unsupported_share": _share_unsupported([r for r in variant_rows if r["task_id"] in aff_ok])}
    verdict, reasons = main["verdict"], [main.get("reason", "")]
    if neg["pairs"] < COMPARE["min_negative_controls"]:
        verdict, reasons = "uninterpretable", [f"only {neg['pairs']} negative-control pairs (minimum {COMPARE['min_negative_controls']})"]
    else:
        moved = [r for r in neg["rows"] if abs(r["patched_requests"] - r["base_requests"]) / max(r["base_requests"], 1) > COMPARE["neg_tolerance"] or r["patched_pass"] < r["base_pass"]]
        if len(moved) > len(neg["rows"]) / 3:
            verdict, reasons = "uninterpretable", [f"{len(moved)} of {neg['pairs']} negative controls moved beyond tolerance"]
    if verdict == "improvement" and drift is not None and abs(drift) > COMPARE["drift_tolerance"]:
        verdict, reasons = "inconclusive_conflicting_comparisons", [f"the contemporaneous control drifted {drift:+.0%} from the baseline: no improvement is claimed"]
    if verdict == "improvement" and None not in audit.values() and abs(audit["control_unsupported_share"] - audit["variant_unsupported_share"]) > COMPARE["evidence_asymmetry_tolerance"]:
        verdict, reasons = "inconclusive_evidence_asymmetry", ["the share of correct answers without sufficient evidence differs between the arms: the comparison is not like for like"]
    return {"rule": COMPARE["id"], "rules_sha256": RULES_SHA256, "variant": variant, "verdict": verdict, "reasons": reasons, "control_drift": drift, "evidence_audit": audit, "excluded_for_repeats": short,
            "primary": main, "negative_controls": {k: neg[k] for k in ("pairs", "rows")}}
