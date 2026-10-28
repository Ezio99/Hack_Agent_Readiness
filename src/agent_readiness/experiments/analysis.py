"""Pre-registered analysis: per-run table, controlled contrasts, effect sizes, bootstrap intervals, within-task permutation tests, placebo/control checks, evidence tiers.
Descriptive first: with 3 runs per cell nothing here is a significance gate, and a non-detection is never reported as equivalence."""
from __future__ import annotations

import json
import random
import statistics
from pathlib import Path

from . import design
from .driver import MOCK_BANNER

METRICS = {"success": "proportion", "partial_accuracy": "mean", "model_requests": "count", "page_loads": "count", "actions": "count", "revisits": "count",
           "elapsed_seconds": "seconds", "calculated_cost_usd": "usd"}
PRIMARY = ("success", "model_requests")
SUCCESS_SIGNAL_PP = 0.25                 # |difference in success rate| that counts as a directional signal
EFFORT_SIGNAL_RATIO = 1.5                # median-requests ratio >= 1.5 (or <= 1/1.5)
PERMUTATIONS, BOOTSTRAPS = 20000, 5000
TIERS = ("observed_directional_signal", "supported_exploratory_effect", "inconclusive_no_detected_effect")

# contrast id -> (title, tasks, baseline variant, comparison variant, causal?, stage)
CONTRASTS = {
    "S1": ("Stage 1 sensitivity: V0 vs V3 (BOTH factors change; no factor attribution)", ["T1", "T2", "T3", "T4"], "V0", "V3", False, 1),
    "C1": ("Availability: listing (V0) vs detail-only (V1), specs structured", ["T1", "T3"], "V0", "V1", True, 2),
    "C2": ("Specifications: structured (V0) vs fragmented (V2), availability listing", ["T2", "T3"], "V0", "V2", True, 2),
    "C2b": ("Specifications (secondary): structured (V0) vs fragmented (V2) on T1", ["T1"], "V0", "V2", True, 2),
    "C0": ("PLACEBO: availability V0 vs V1 on T2 (availability is irrelevant to T2)", ["T2"], "V0", "V1", False, 2),
}


def load_rows(path: Path) -> list[dict]:
    return [json.loads(l) for l in Path(path).read_text().splitlines() if l.strip()] if Path(path).exists() else []


def _values(rows, task, variant, metric):
    return [float(r[metric]) for r in rows if r["task_code"] == task and r["variant_code"] == variant and r.get("run_status") != "interrupted" and metric in r]


def _stat(strata: dict[str, tuple[list[float], list[float]]]) -> float:
    """Pooled stratified difference of means (comparison - baseline), weighted by stratum size."""
    num = den = 0.0
    for a, b in strata.values():
        if a and b:
            n = len(a) + len(b)
            num += n * (statistics.fmean(b) - statistics.fmean(a))
            den += n
    return num / den if den else float("nan")


def permutation_p(strata, seed: int) -> float:
    rng = random.Random(seed)
    obs = abs(_stat(strata))
    if obs != obs:
        return float("nan")
    hits = 0
    for _ in range(PERMUTATIONS):
        perm = {}
        for k, (a, b) in strata.items():
            pool = a + b
            rng.shuffle(pool)
            perm[k] = (pool[:len(a)], pool[len(a):])
        hits += abs(_stat(perm)) >= obs - 1e-12
    return round(hits / PERMUTATIONS, 4)


def bootstrap_ci(strata, seed: int) -> list[float] | None:
    if not all(a and b for a, b in strata.values()) or min(min(len(a), len(b)) for a, b in strata.values()) < 2:
        return None                      # n<2 per arm: a resampling interval would be degenerate and misleading
    rng = random.Random(seed)
    vals = sorted(_stat({k: ([rng.choice(a) for _ in a], [rng.choice(b) for _ in b]) for k, (a, b) in strata.items()}) for _ in range(BOOTSTRAPS))
    return [round(vals[int(0.025 * BOOTSTRAPS)], 4), round(vals[int(0.975 * BOOTSTRAPS) - 1], 4)]


def _ratio(a, b):
    ma, mb = statistics.median(a), statistics.median(b)
    return round(mb / ma, 3) if ma else None


def analyze(rows: list[dict], sched: dict, *, mechanism_review: dict | None = None, seed: int = 12) -> dict:
    stage = sched["stage"]
    planned = {(e["task_code"], e["variant_code"]): 0 for e in sched["entries"]}
    for e in sched["entries"]:
        planned[(e["task_code"], e["variant_code"])] += 1
    have = {k: sum(1 for r in rows if (r["task_code"], r["variant_code"]) == k and r.get("run_status") != "interrupted") for k in planned}
    incomplete = {f"{k[0]}/{k[1]}": f"{have[k]}/{n}" for k, n in planned.items() if have[k] < n}
    modes = sorted({r.get("mode") for r in rows})
    out = {"stage": stage, "schedule_hash": sched["schedule_hash"], "modes": modes, "banner": MOCK_BANNER if "mock" in modes else None,
           "partial_schedule": bool(incomplete), "incomplete_cells": incomplete, "runs_analysed": len(rows), "runs_planned": len(sched["entries"]),
           "runs": rows, "cells": {}, "contrasts": {}}
    for (t, v), n in sorted(planned.items()):
        cell = {m: _values(rows, t, v, m) for m in METRICS}
        cell["planned"], cell["completed"] = n, have[(t, v)]
        cell["infrastructure_errors"] = sum(1 for r in rows if (r["task_code"], r["variant_code"]) == (t, v) and r.get("run_status") == "infrastructure_error")
        out["cells"][f"{t}/{v}"] = cell
    review = mechanism_review or {}
    for cid, (title, tasks, base, comp, causal, st) in CONTRASTS.items():
        if st != stage:
            continue
        per_metric, notes = {}, []
        for m in METRICS:
            strata = {t: (_values(rows, t, base, m), _values(rows, t, comp, m)) for t in tasks}
            usable = {k: v for k, v in strata.items() if v[0] and v[1]}
            if not usable:
                per_metric[m] = {"n": {t: [len(a), len(b)] for t, (a, b) in strata.items()}, "effect": None, "note": "no complete arms"}
                continue
            eff = round(_stat(usable), 4)
            per_metric[m] = {"n": {t: [len(a), len(b)] for t, (a, b) in strata.items()}, "effect": eff, "ci95_bootstrap": bootstrap_ci(usable, seed), "permutation_p": permutation_p(usable, seed),
                             "per_task": {t: {"baseline": a, "comparison": b, "difference": round(statistics.fmean(b) - statistics.fmean(a), 4), "ratio_of_medians": _ratio(a, b)} for t, (a, b) in usable.items()}}
        succ, req = per_metric["success"], per_metric["model_requests"]
        directions = []
        if succ.get("effect") is not None:
            directions += [(-1 if v["difference"] < 0 else 1 if v["difference"] > 0 else 0) for v in succ["per_task"].values()]
        succ_signal = succ.get("effect") is not None and abs(succ["effect"]) >= SUCCESS_SIGNAL_PP
        req_ratios = [v["ratio_of_medians"] for v in req.get("per_task", {}).values() if v["ratio_of_medians"]]
        req_signal = bool(req_ratios) and all(r >= EFFORT_SIGNAL_RATIO for r in req_ratios) or bool(req_ratios) and all(r <= 1 / EFFORT_SIGNAL_RATIO for r in req_ratios)
        succ_dirs = {d for d in directions if d != 0}
        consistent = (len(succ_dirs) <= 1) and (not succ_signal or len(succ_dirs) == 1)
        signal = bool(succ_signal or req_signal)
        n_min = min((min(len(a), len(b)) for a, b in strata.values() if a or b), default=0)
        tier = "observed_directional_signal" if signal else "inconclusive_no_detected_effect"
        reasons = []
        if signal and causal and cid not in ("C0",):
            ok = consistent and review.get(cid, {}).get("supported") is True and not out["partial_schedule"]
            beyond_control = None
            if cid != "C0" and "C0" in out["contrasts"]:
                c0 = out["contrasts"]["C0"]["metrics"]["success"].get("effect")
                beyond_control = c0 is None or abs(succ.get("effect") or 0) > abs(c0)
            if ok and beyond_control is not False:
                tier = "supported_exploratory_effect"
            else:
                reasons = ["not 'supported': " + "; ".join(x for x in (
                    None if consistent else "direction not consistent across tasks", None if review.get(cid, {}).get("supported") is True else "no trace-supported website mechanism recorded (mechanism review required)",
                    "schedule incomplete" if out["partial_schedule"] else None, "not beyond placebo variability" if beyond_control is False else None) if x)]
        if not signal:
            reasons.append(f"no detected effect at n={n_min} per arm per task; smallest observable success difference per task is {1 / n_min:.2f}" if n_min else "no data")
            reasons.append("This is NOT evidence of equivalence.")
        if not causal and cid == "S1":
            reasons.append("Combined change: any difference must not be attributed to availability or specifications individually.")
        out["contrasts"][cid] = {"title": title, "tasks": tasks, "baseline": base, "comparison": comp, "causal_contrast": causal, "tier": tier, "tier_notes": reasons, "metrics": per_metric,
                                 "direction_consistent": consistent, "primary_metrics": list(PRIMARY)}
    if stage == 2:
        t4 = _values(rows, "T4", "V0", "model_requests")
        out["control_T4_V0"] = {"model_requests": t4, "note": "pure-noise reference; not an A/B test"}
    return out


def markdown(res: dict) -> str:
    L = []
    if res["banner"]:
        L += [f"> **{res['banner']}**", ""]
    if res["partial_schedule"]:
        L += [f"> **PARTIAL SCHEDULE** — {res['runs_analysed']}/{res['runs_planned']} runs; incomplete cells: {res['incomplete_cells']}. No run was retried or replaced.", ""]
    L += [f"# Task 012 Stage {res['stage']} analysis", "", f"schedule `{res['schedule_hash'][:16]}…`; modes {res['modes']}", "", "## Per-run results", "",
          "| run | task | variant | status | success | partial | evid. cov | requests | page loads | revisits | time s | cost US$ | attribution |", "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in res["runs"]:
        L.append(f"| {r['run_id']} | {r['task_code']} | {r['variant_code']} | {r['run_status']} | {'yes' if r.get('success') else 'no'} | {r.get('partial_accuracy')} | {r.get('evidence_coverage')} | {r.get('model_requests')} | {r.get('page_loads')} | {r.get('revisits')} | {r.get('elapsed_seconds')} | {r.get('calculated_cost_usd')} | {','.join(r.get('attribution', []))} |")
    for cid, c in res["contrasts"].items():
        L += ["", f"## {cid}: {c['title']}", "", f"**Evidence tier: {c['tier'].replace('_', ' ')}**"] + [f"- {n}" for n in c["tier_notes"]]
        for m in ("success", "partial_accuracy", "model_requests", "page_loads", "elapsed_seconds", "calculated_cost_usd"):
            x = c["metrics"][m]
            if x.get("effect") is None:
                L.append(f"- {m}: no complete arms")
            else:
                L.append(f"- {m}: pooled difference (comparison − baseline) {x['effect']}, bootstrap 95% CI {x['ci95_bootstrap'] if x['ci95_bootstrap'] else 'not computed (n<2 per arm)'}, permutation p {x['permutation_p']} (descriptive); per task: " +
                         "; ".join(f"{t} {v['baseline']}→{v['comparison']}" for t, v in x["per_task"].items()))
    L += ["", "Evidence tiers: observed directional signal / supported exploratory effect (replicated, consistent, beyond control variability, trace-supported mechanism) / inconclusive or no detected effect (never proof of equivalence)."]
    return "\n".join(L)
