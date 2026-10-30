"""EXPLORATORY retest of an owner-selected change (EXP-B): plan validation, the fixed execution order and the pre-registered decision rules.

This is NOT the frozen `paired-signflip-v1` rule and never replaces it: the frozen rule is computed and reported unchanged by `evaluate_stage`; this module adds a second, separately labelled
analysis whose rules are written into the post_trials approval manifest (and hashed) before any trial runs. Comparisons: the PRIMARY one is the contemporaneous unmodified repeat (placebo: same
frozen task, model, profile, tool interface, limits and source snapshot) against the patched trial; the imported historical baseline is a SECONDARY reference. A material conflict between the two
never produces a claim of support."""
from __future__ import annotations

from ...suite.core import canonical_hash

ID = "exploratory-listing-v1"
RULES = {
    "id": ID, "label": "EXPLORATORY - owner-selected change; separate from the frozen paired-signflip-v1 rule; never its replacement",
    "primary_comparison": "contemporaneous unmodified repeat (placebo) vs patched trial, per affected task, model requests",
    "secondary_comparison": "imported historical baseline vs patched trial (same tasks)",
    "effect_floor": 0.25,
    "support": "for EVERY affected task: patched requests <= (1 - effect_floor) x placebo requests; (placebo - patched) strictly exceeds the noise estimate; patched page views < placebo page views; "
               "no evidence-backed pass lost relative to the placebo",
    "noise_estimate": "max over the placebo tasks of |placebo requests - historical baseline requests|",
    "same_shape_control_tolerance_requests": 3, "detail_control_tolerance_requests": 1,
    "controls": "same-shape controls (have a placebo): |patched - placebo| requests <= tolerance; detail-page controls (no placebo): |patched - historical baseline| requests <= tolerance",
    "drift": "affected task: |placebo - historical| / historical > 0.25 is flagged as drift",
    "conflict": "any affected task where the two comparisons fall on opposite sides of the effect floor, or a drift flag, while the primary comparison would support H1",
    "verdicts": {"consistent_with_h1": "all support conditions hold, controls inside tolerance, no conflict",
                 "not_supported": "an affected task misses a support condition, or a pass is lost (the contemporaneous comparison governs; a supportive historical comparison alone changes nothing)",
                 "inconclusive_conflicting_comparisons": "the primary comparison would support H1 but the secondary conflicts or drift is flagged: no support is claimed",
                 "uninterpretable": "a control moved beyond tolerance, a trial is missing or void, or the control is not identical to the baseline"},
    "claims": "allowed: 'consistent with / not consistent with a reduction in browsing effort for this exploratory change on this site and these tasks'; never 'proved' or a general improvement",
}
RULES_SHA256 = canonical_hash(RULES)


def validate_plan(plan: dict, frozen_task_ids: list[str]) -> dict:
    """Normalise and validate the owner's retest plan: `placebo_tasks` (ordered), `affected` and `same_shape_controls` (a partition of the placebo tasks), `detail_controls` (patched only)."""
    need = ("placebo_tasks", "affected", "same_shape_controls", "detail_controls")
    if not isinstance(plan, dict) or any(k not in plan or not isinstance(plan[k], list) for k in need):
        raise ValueError(f"the post plan needs list fields {need}")
    out = {k: list(plan[k]) for k in need}
    every = out["placebo_tasks"] + out["detail_controls"]
    if len(set(every)) != len(every) or any(t not in frozen_task_ids for t in every):
        raise ValueError("plan tasks must be distinct frozen tasks")
    if set(out["placebo_tasks"]) != set(out["affected"]) | set(out["same_shape_controls"]) or set(out["affected"]) & set(out["same_shape_controls"]) or not out["affected"]:
        raise ValueError("placebo_tasks must be exactly the affected tasks plus the same-shape controls (disjoint, at least one affected task)")
    return out


def execution_plan(plan: dict, patched_task_ids: list[str], proposal_id: str) -> list[dict]:
    """The FIXED execution order (written into the manifest before any trial): placebo tasks in the plan's order, counterbalanced - the first placebo task runs placebo-then-patched, the second
    patched-then-placebo, and so on - then the remaining patched tasks in task-id order. Tasks the patch invalidated are not in `patched_task_ids`; an invalidated placebo task is refused."""
    for t in plan["placebo_tasks"]:
        if t not in patched_task_ids:
            raise ValueError(f"placebo task {t} is not valid on the patched mirror, so the pair cannot be run")
    steps = []
    for i, t in enumerate(plan["placebo_tasks"]):
        pair = [("placebo", t), ("patched", t)] if i % 2 == 0 else [("patched", t), ("placebo", t)]
        steps += [{"arm": a, "task_id": tid, "repeat": 1} for a, tid in pair]
    steps += [{"arm": "patched", "task_id": t, "repeat": 1} for t in sorted(patched_task_ids) if t not in plan["placebo_tasks"]]
    for s in steps:
        s["name"] = f"{s['arm']}:{s['task_id']}:r{s['repeat']}"
        s["proposal_id"] = proposal_id
    return steps


def _one(rows: list[dict] | None):
    """(requests, page_views, evidence-backed pass) of a single usable trial, or None (missing / void / replicated)."""
    if not rows or len(rows) != 1 or rows[0]["void"]:
        return None
    r = rows[0]
    return {"requests": r["model_requests"], "page_views": r["page_views"], "pass": bool(r["passed"] and r["evidence_backed"])}


def analyze(plan: dict, baseline: dict, placebo: dict, patched: dict) -> dict:
    """Apply RULES. Inputs: per task id, the list of attribution-annotated trial rows of the historical baseline, the unmodified repeat and the patched arm."""
    f = RULES["effect_floor"]
    tasks = {"baseline": {t: _one(baseline.get(t)) for t in plan["placebo_tasks"] + plan["detail_controls"]},
             "placebo": {t: _one(placebo.get(t)) for t in plan["placebo_tasks"]}, "patched": {t: _one(patched.get(t)) for t in plan["placebo_tasks"] + plan["detail_controls"]}}
    missing = [f"{arm}:{t}" for arm, d in tasks.items() for t, v in d.items() if v is None]
    out = {"rules_id": ID, "rules_sha256": RULES_SHA256, "label": RULES["label"], "tasks": tasks, "missing_or_void": missing}
    if missing:
        return {**out, "verdict": "uninterpretable", "reasons": [f"missing, void or replicated trials: {missing}"]}
    noise = max(abs(tasks["placebo"][t]["requests"] - tasks["baseline"][t]["requests"]) for t in plan["placebo_tasks"])
    out["noise_estimate_requests"] = noise
    reasons, controls_ok = [], True
    for t in plan["same_shape_controls"]:
        d = abs(tasks["patched"][t]["requests"] - tasks["placebo"][t]["requests"])
        if d > RULES["same_shape_control_tolerance_requests"]:
            controls_ok = False
            reasons.append(f"same-shape control {t} moved by {d} requests (tolerance {RULES['same_shape_control_tolerance_requests']})")
    for t in plan["detail_controls"]:
        d = abs(tasks["patched"][t]["requests"] - tasks["baseline"][t]["requests"])
        if d > RULES["detail_control_tolerance_requests"]:
            controls_ok = False
            reasons.append(f"detail-page control {t} moved by {d} requests (tolerance {RULES['detail_control_tolerance_requests']})")
    out["controls_within_tolerance"] = controls_ok
    if not controls_ok:
        return {**out, "verdict": "uninterpretable", "reasons": reasons}
    per, supported, conflict, drift, lost = {}, True, False, False, False
    for t in plan["affected"]:
        p, h, x = tasks["placebo"][t], tasks["baseline"][t], tasks["patched"][t]
        c_ok = x["requests"] <= (1 - f) * p["requests"]
        h_ok = x["requests"] <= (1 - f) * h["requests"]
        noise_ok = (p["requests"] - x["requests"]) > noise
        pv_ok = x["page_views"] < p["page_views"]
        pass_ok = x["pass"] >= p["pass"]
        d = h["requests"] > 0 and abs(p["requests"] - h["requests"]) / h["requests"] > 0.25
        per[t] = {"placebo_requests": p["requests"], "historical_requests": h["requests"], "patched_requests": x["requests"], "primary_meets_floor": c_ok, "secondary_meets_floor": h_ok,
                  "exceeds_noise": noise_ok, "page_views_lower": pv_ok, "pass_not_lost": pass_ok, "drift_flag": d}
        supported &= c_ok and noise_ok and pv_ok and pass_ok
        lost |= not pass_ok
        conflict |= (c_ok != h_ok)
        drift |= d
    out["affected"] = per
    if not supported:
        why = [f"{t}: " + ", ".join(k for k in ("primary_meets_floor", "exceeds_noise", "page_views_lower", "pass_not_lost") if not v[k]) for t, v in per.items() if not all(v[k] for k in ("primary_meets_floor", "exceeds_noise", "page_views_lower", "pass_not_lost"))]
        note = " (the historical comparison alone would have suggested support; the contemporaneous control governs)" if all(v["secondary_meets_floor"] for v in per.values()) else ""
        return {**out, "verdict": "not_supported", "reasons": ["missed: " + "; ".join(why) + note]}
    if conflict or drift:
        return {**out, "verdict": "inconclusive_conflicting_comparisons", "reasons": ["the contemporaneous comparison would support H1 but " + ("the historical comparison falls on the other side of the effect floor" if conflict else "the unmodified repeat drifted from the historical baseline by more than 25 %") + ": no support is claimed"]}
    return {**out, "verdict": "consistent_with_h1", "reasons": ["every affected task meets the effect floor against the contemporaneous control, exceeds the noise estimate, shows fewer page views and loses no pass; controls are inside tolerance; the historical comparison agrees"]}
