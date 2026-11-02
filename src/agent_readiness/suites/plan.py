"""Statistical plan helper (lifecycle M4; proposal §4.2, owner decision 6). Pure Python, deterministic from its seed.

Design: paired (variant A vs variant B) over the SAME frozen tasks. Repetitions are clustered within tasks: per task and variant the outcome is the
mean pass rate over its repetitions, the per-task difference d_i = mean_B - mean_A is the unit of analysis, and the test is the EXACT two-sided
sign-flip (randomisation) test of sum(d_i) over tasks. Natural and assisted wording conditions are analysed separately and never pooled.

Feasibility (required before a study may be confirmatory):
  min_achievable_p   2 / 2^n for n task pairs (all differences non-zero and the same sign); must be <= alpha (n >= 6 at alpha 0.05). Necessary,
                     not sufficient.
  power / MDE        Monte Carlo under STATED assumptions: per-task baseline pass probabilities vary between tasks (normal on the logit scale with
                     `between_task_sd`), the effect is a shift of `effect` in pass probability at the baseline mean (applied on the logit scale),
                     each repetition is Bernoulli. Power = share of simulated studies with p <= alpha; the minimum detectable effect is the
                     smallest effect on a grid reaching `power_target`.
A confirmatory designation is refused unless feasible; an underpowered study may run only as EXPLORATORY, with no confirmatory claims."""
from __future__ import annotations

import math
import random
from fractions import Fraction

from .records import StatisticalPlan, min_p_sign_flip

VERSION = "plan-1"
TEST = "paired-exact-sign-flip"
EFFECT_GRID = tuple(round(0.05 * k, 2) for k in range(1, 11))     # 0.05 .. 0.50


class InfeasibleError(ValueError):
    """A confirmatory designation was requested for a design whose feasibility assessment fails."""


def sign_flip_p(diffs: list[float], *, scale: int | None = None) -> float:
    """Exact two-sided p of the sign-flip test on sum(d): P(|S| >= |S_obs|) over all 2^n sign assignments. Differences are rationals with a
    common denominator (repetition counts), so the null distribution is computed exactly by dynamic programming over integers."""
    fr = [Fraction(d).limit_denominator(10_000) for d in diffs]
    den = scale or math.lcm(*[f.denominator for f in fr]) if fr else 1
    ints = [abs(int(f * den)) for f in fr]
    obs = abs(sum(int(f * den) for f in fr))
    counts = {0: 1}
    for v in ints:
        nxt: dict[int, int] = {}
        for s, c in counts.items():
            for t in (s + v, s - v):
                nxt[t] = nxt.get(t, 0) + c
        counts = nxt
    total = 2 ** len(ints)
    return sum(c for s, c in counts.items() if abs(s) >= obs) / total if ints else 1.0


def _logit(p: float) -> float:
    p = min(max(p, 1e-6), 1 - 1e-6)
    return math.log(p / (1 - p))


def _expit(x: float) -> float:
    return 1 / (1 + math.exp(-x))


def power(n_tasks: int, repetitions: int, effect: float, *, alpha: float = 0.05, baseline: float = 0.5, between_task_sd: float = 1.0, sims: int = 2000,
          seed: int = 0) -> float:
    if baseline + effect >= 1 or baseline + effect <= 0:
        return float("nan")
    rng = random.Random(seed)
    shift = _logit(baseline + effect) - _logit(baseline)
    hits = 0
    for _ in range(sims):
        diffs = []
        for _ in range(n_tasks):
            lo = rng.gauss(_logit(baseline), between_task_sd)
            pa, pb = _expit(lo), _expit(lo + shift)
            a = sum(rng.random() < pa for _ in range(repetitions)) / repetitions
            b = sum(rng.random() < pb for _ in range(repetitions)) / repetitions
            diffs.append(b - a)
        if sign_flip_p(diffs, scale=repetitions) <= alpha:
            hits += 1
    return hits / sims


def feasibility(n_tasks: int, repetitions: int, *, alpha: float = 0.05, effect: float = 0.25, baseline: float = 0.5, between_task_sd: float = 1.0,
                power_target: float = 0.8, sims: int = 2000, seed: int = 0) -> dict:
    min_p = min_p_sign_flip(n_tasks)
    pw = power(n_tasks, repetitions, effect, alpha=alpha, baseline=baseline, between_task_sd=between_task_sd, sims=sims, seed=seed) if min_p <= alpha else 0.0
    mde = None
    if min_p <= alpha:
        for e in EFFECT_GRID:
            if baseline + e < 1 and power(n_tasks, repetitions, e, alpha=alpha, baseline=baseline, between_task_sd=between_task_sd, sims=sims, seed=seed) >= power_target:
                mde = e
                break
    feasible = min_p <= alpha and pw >= power_target
    reasons = []
    if min_p > alpha:
        reasons.append(f"with {n_tasks} task pairs the smallest achievable p is {min_p:.4g} > alpha {alpha} (need >= {math.ceil(math.log2(2 / alpha))} tasks)")
    elif pw < power_target:
        reasons.append(f"power {pw:.2f} < target {power_target} for an effect of {effect} at baseline {baseline}")
    return {"version": VERSION, "test": TEST, "n_tasks": n_tasks, "repetitions": repetitions, "alpha": alpha, "min_achievable_p": min_p, "power": round(pw, 3),
            "power_target": power_target, "minimum_detectable_effect": mde, "feasible": feasible, "reasons": reasons,
            "assumptions": {"effect_on_pass_probability": effect, "baseline_pass_probability": baseline, "between_task_sd_logit": between_task_sd,
                            "repetitions_bernoulli": True, "statement": "assumptions, not estimates: change them and the assessment changes"},
            "method": {"sims": sims, "seed": seed, "unit_of_analysis": "task (repetitions aggregated per task and variant)", "two_sided": True}}


ANALYSIS = ("per wording condition separately (natural and assisted are never pooled): per task, the mean evidence-supported pass over its repetitions "
            "on each variant; paired difference per task; exact two-sided sign-flip test over tasks (tasks are the unit of analysis)")


def make_plan(*, n_tasks: int, repetitions: int, requested: str = "confirmatory", allow_exploratory_fallback: bool = False,
              primary_outcome: str = "evidence-supported pass (official grader v1), natural-wording condition",
              comparison_rule: str = TEST, stopping_rule: str = "all planned trials once; no retries; void trials excluded and listed; halt on a spend-gate bound violation",
              alpha: float = 0.05, **assumptions) -> StatisticalPlan:
    """A pre-registered plan. A confirmatory request on an infeasible design raises InfeasibleError, unless the caller explicitly allows an
    EXPLORATORY fallback (recorded in the plan's feasibility block)."""
    f = feasibility(n_tasks, repetitions, alpha=alpha, **assumptions)
    designation = requested
    if requested == "confirmatory" and not f["feasible"]:
        if not allow_exploratory_fallback:
            raise InfeasibleError("; ".join(f["reasons"]) or "infeasible")
        designation = "exploratory"
        f = {**f, "fallback": "confirmatory requested; infeasible; designated exploratory (no confirmatory claims)"}
    return StatisticalPlan(designation=designation, primary_outcome=primary_outcome, comparison_rule=comparison_rule, alpha=alpha, n_tasks=n_tasks,
                           repetitions=repetitions, analysis=ANALYSIS, stopping_rule=stopping_rule, feasibility=f)


def analyse(plan: StatisticalPlan, per_task: dict[str, dict[str, list[bool]]], variants: tuple[str, str]) -> dict:
    """per_task: {task_id: {variant: [pass per repetition]}} for ONE wording condition. Returns task-level means, paired differences and the exact
    sign-flip p; the label is the plan's designation (an exploratory plan never yields a confirmatory claim)."""
    a, b = variants
    rows, diffs = [], []
    for tid in sorted(per_task):
        va, vb = per_task[tid].get(a) or [], per_task[tid].get(b) or []
        if not va or not vb:
            rows.append({"task_id": tid, "excluded": "missing variant (void or invalidated)"})
            continue
        ma, mb = sum(va) / len(va), sum(vb) / len(vb)
        diffs.append(mb - ma)
        rows.append({"task_id": tid, a: round(ma, 4), b: round(mb, 4), "difference": round(mb - ma, 4), "repetitions": [len(va), len(vb)]})
    p = sign_flip_p(diffs) if diffs else None
    claim = None
    if plan.designation == "confirmatory" and p is not None and len(diffs) == plan.n_tasks:
        claim = "significant" if p <= plan.alpha else "not significant"
    return {"designation": plan.designation, "test": plan.comparison_rule, "alpha": plan.alpha, "pairs": len(diffs), "planned_pairs": plan.n_tasks,
            "mean_difference": round(sum(diffs) / len(diffs), 4) if diffs else None, "p_value": p, "confirmatory_result": claim,
            "label": "pre-registered confirmatory analysis" if plan.designation == "confirmatory" else "EXPLORATORY: no confirmatory claim may be made",
            "per_task": rows}


def preregistration_check(plan: StatisticalPlan, *, n_tasks_in_condition: int, repetitions: int) -> list[str]:
    """Problems that make a plan unusable for the manifest it is attached to (empty list = ok)."""
    out = []
    if plan.n_tasks != n_tasks_in_condition:
        out.append(f"plan n_tasks {plan.n_tasks} != {n_tasks_in_condition} tasks in the analysed condition")
    if plan.repetitions != repetitions:
        out.append("plan repetitions differ from the manifest")
    if plan.unit_of_analysis != "task":
        out.append("tasks must be the unit of analysis")
    if "never pooled" not in plan.analysis:
        out.append("the analysis must keep natural and assisted wording separate")
    if plan.designation == "confirmatory" and not (plan.feasibility or {}).get("feasible"):
        out.append("confirmatory without a feasible assessment")
    return out
