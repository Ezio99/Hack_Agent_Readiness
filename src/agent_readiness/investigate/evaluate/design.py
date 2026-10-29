"""Pre-registered before/after evaluation: the rule is frozen into the tasks manifest at freeze time (before any trial), and the statistics are exact and conservative.

Unit of analysis = the frozen task (paired: same task, same agent profile, same snapshot-except-the-patch). Per task per arm: evidence-backed pass rate and mean model requests over the
non-void repeats; a pair with any void trial in either arm is excluded and listed. Paired sign-flip permutation test on per-task differences (exact enumeration up to 2^14, otherwise a seeded
Monte-Carlo with 20,000 flips). Verdict: improvement / regression / inconclusive. With few tasks and one repeat, `inconclusive` is the expected honest answer."""
from __future__ import annotations

import itertools
import random
from statistics import mean

RULE = {"id": "paired-signflip-v1", "min_pairs": 4, "alpha": 0.10, "pass_delta_floor": 0.25, "request_reduction_floor": 0.25, "primary": "evidence_backed_pass_rate", "secondary": "model_requests",
        "improvement": "mean pass delta >= +floor and p <= alpha, OR pass delta >= 0 and mean model requests fall by >= floor (relative) with p <= alpha on the request differences",
        "regression": "mean pass delta <= -floor and p <= alpha, OR pass delta <= 0 and mean model requests rise by >= floor (relative) with p <= alpha",
        "otherwise": "inconclusive", "void_policy": "a pair with any void trial in either arm is excluded and listed", "causal_scope": "measured on these frozen tasks, this agent profile and model, this snapshot and patch only"}


def sign_flip_p(diffs: list[float], *, seed: int = 0, exact_up_to: int = 14, samples: int = 20000) -> float:
    d = [x for x in diffs]
    n = len(d)
    if n == 0 or all(x == 0 for x in d):
        return 1.0
    obs = abs(sum(d))
    if n <= exact_up_to:
        hits = sum(1 for signs in itertools.product((1, -1), repeat=n) if abs(sum(s * x for s, x in zip(signs, d))) >= obs - 1e-12)
        return round(hits / 2 ** n, 6)
    rng = random.Random(seed)
    hits = sum(1 for _ in range(samples) if abs(sum(rng.choice((1, -1)) * x for x in d)) >= obs - 1e-12)
    return round((hits + 1) / (samples + 1), 6)


def arm_stats(trials: list[dict]) -> dict | None:
    """trials: attribution-annotated trial dicts of ONE task in ONE arm. None when any is void."""
    if not trials or any(t["void"] for t in trials):
        return None
    return {"pass": mean(1.0 if (t["passed"] and t["evidence_backed"]) else 0.0 for t in trials), "requests": mean(t["model_requests"] for t in trials), "n": len(trials)}


def compare(base: dict[str, list[dict]], patched: dict[str, list[dict]], partitions: dict[str, str], rule: dict) -> dict:
    rows, excluded = [], []
    for tid in sorted(base):
        b, p = arm_stats(base[tid]), arm_stats(patched.get(tid, []))
        if b is None or p is None:
            excluded.append({"task_id": tid, "reason": "void or missing trial in one arm" if tid in patched else "task not run in the patched arm"})
            continue
        rows.append({"task_id": tid, "partition": partitions[tid], "base_pass": b["pass"], "patched_pass": p["pass"], "base_requests": b["requests"], "patched_requests": p["requests"]})
    out = {"rule": rule["id"], "pairs": len(rows), "excluded": excluded, "rows": rows}
    if len(rows) < rule["min_pairs"]:
        return {**out, "verdict": "inconclusive", "reason": f"only {len(rows)} usable pairs (minimum {rule['min_pairs']})", "pass_delta": None, "request_change": None, "p_pass": None, "p_requests": None}
    dp = [r["patched_pass"] - r["base_pass"] for r in rows]
    dr = [r["patched_requests"] - r["base_requests"] for r in rows]
    mp, mb = mean(dp), mean(r["base_requests"] for r in rows)
    rel = mean(dr) / mb if mb else 0.0
    p_pass, p_req = sign_flip_p(dp), sign_flip_p(dr)
    a, f, rf = rule["alpha"], rule["pass_delta_floor"], rule["request_reduction_floor"]
    if (mp >= f and p_pass <= a) or (mp >= 0 and rel <= -rf and p_req <= a):
        verdict, why = "improvement", "meets the pre-registered improvement rule"
    elif (mp <= -f and p_pass <= a) or (mp <= 0 and rel >= rf and p_req <= a):
        verdict, why = "regression", "meets the pre-registered regression rule"
    else:
        verdict, why = "inconclusive", "neither the improvement nor the regression rule is met"
    sub = {}
    for part in ("investigation", "holdout"):
        sel = [r for r in rows if r["partition"] == part]
        if sel:
            sub[part] = {"pairs": len(sel), "pass_delta": round(mean(r["patched_pass"] - r["base_pass"] for r in sel), 4), "mean_request_change": round(mean(r["patched_requests"] - r["base_requests"] for r in sel), 3)}
    consistent = None
    if "holdout" in sub and "investigation" in sub:
        sgn = lambda x: (x > 0) - (x < 0)
        consistent = sgn(sub["holdout"]["pass_delta"]) == sgn(sub["investigation"]["pass_delta"]) or sub["holdout"]["pass_delta"] == 0
    return {**out, "verdict": verdict, "reason": why, "pass_delta": round(mp, 4), "request_change": round(rel, 4), "mean_request_difference": round(mean(dr), 3), "p_pass": p_pass, "p_requests": p_req, "by_partition": sub, "holdout_consistent": consistent}
