"""Experiment-2 study design: a balanced baseline over task families and difficulty levels, an investigation/holdout partition, a repeat plan, a fixed trial order and the hashed phase
manifests the owner approves. Deterministic: the same inputs always give the same plan and hashes. Nothing in this module spends money."""
from __future__ import annotations

import hashlib
from collections import Counter, defaultdict

from ..suite.core import canonical_hash
from . import costs
from .answers import answer_schema
from .tasks import FAMILIES, Candidate

# Target number of distinct tasks per family in the baseline, and how many of them must be "hard" where the family has hard tasks. Informed by the pool: lookup tasks are cheap negative controls;
# discovery, availability, cost and compatibility families are the ones a candidate website change could affect and so need at least 6 tasks each (see the comparison rules).
QUOTAS = {"lookup": 4, "discovery": 6, "availability": 7, "kit_vs_items": 5, "total_cost": 6, "delivery_deposit": 3, "compatibility": 4, "planning": 5}
HOLDOUT_FRACTION = 1 / 3
REPEAT_TASKS = 8                       # tasks that get a second baseline trial (early variance estimate), spread over families and both partitions; the variant test's contemporaneous control (K = 2) is the main noise estimate
PILOT_TRIALS = 8
# The eight trials ACTUALLY RUN in pilot 1 (run exp2-pilot-1, manifest 29df5a28..., 2026-10-31), in execution order. A revised plan keeps them first and unchanged: only the not-yet-run trials may change.
EXECUTED_PILOT = tuple({"task_id": t, "repeat": 1} for t in ("ib-d9260f2d9a", "ib-39484fe9c0", "ib-e3d8f94923", "ib-004e62ff61", "ib-729f03a2cf", "ib-d60a326ffd", "ib-22a62928c8", "ib-7ac16db8c4"))
MIN_AFFECTED = 6                       # a variant needs at least this many sensitive baseline tasks to be testable
N_AFFECTED, N_NEG = 6, 3               # tasks per variant test: affected (3 investigation + 3 holdout where available) and negative controls
K_AFFECTED, K_NEG = 2, 1               # trials per task PER ARM: affected tasks twice (the comparison rule needs K >= 2 in both arms), negative controls once


def h(*p) -> str:
    return hashlib.sha256("|".join(map(str, p)).encode()).hexdigest()


def select(pool: list[Candidate], quotas: dict[str, int] = QUOTAS, seed: int = 0) -> list[Candidate]:
    """Quota selection per family, spreading difficulty and templates: within a family, candidates are ordered by a seeded hash and taken round-robin over (template, difficulty) cells."""
    chosen: list[Candidate] = []
    for fam in FAMILIES:
        cells: dict[tuple, list[Candidate]] = defaultdict(list)
        for c in sorted((c for c in pool if c.family == fam), key=lambda c: h(seed, c.fingerprint)):
            cells[(c.sub, c.difficulty)].append(c)
        order = sorted(cells, key=lambda k: h(seed, fam, *k))
        cap = max(2, -(-quotas.get(fam, 0) // max(1, len({k[0] for k in cells}))))       # at most ceil(quota / templates) tasks per template, so a family is not one question asked ten ways
        taken, per_template = [], Counter()
        while len(taken) < quotas.get(fam, 0) and any(cells.values()):
            progressed = False
            for k in order:
                if cells[k] and len(taken) < quotas[fam] and per_template[k[0]] < cap:
                    taken.append(cells[k].pop(0)); per_template[k[0]] += 1; progressed = True
            if not progressed:
                break
        chosen += taken
    return chosen


def partition(tasks: list[Candidate], seed: int = 0) -> dict[str, str]:
    """Stratified by family: within each family tasks are ordered by a seeded hash and every third becomes a holdout task (at least one holdout per family with >= 3 tasks)."""
    out: dict[str, str] = {}
    for fam in FAMILIES:
        ts = sorted((t for t in tasks if t.family == fam), key=lambda t: h(seed, "part", t.fingerprint))
        k = 0 if len(ts) < 3 else max(1, round(len(ts) * HOLDOUT_FRACTION))
        for i, t in enumerate(ts):
            out[t.task_id] = "holdout" if i < k else "investigation"
    return out


def repeat_set(tasks: list[Candidate], part: dict[str, str], n: int = REPEAT_TASKS, seed: int = 0) -> list[str]:
    """Tasks that get a second baseline trial: round-robin over (family, partition) cells so both partitions and every family are represented; lookup negative controls are included once."""
    cells: dict[tuple, list[Candidate]] = defaultdict(list)
    for t in sorted(tasks, key=lambda t: h(seed, "rep", t.fingerprint)):
        cells[(t.family, part[t.task_id])].append(t)
    keys = sorted(cells, key=lambda k: h(seed, "repcell", *k))
    out: list[str] = []
    while len(out) < n and any(cells.values()):
        for k in keys:
            if cells[k] and len(out) < n:
                out.append(cells[k].pop(0).task_id)
    return out


def trial_order(tasks: list[Candidate], repeats: list[str], seed: int = 0) -> list[dict]:
    """Fixed order: repeat 1 of every task interleaved by family so any prefix (the pilot) covers many families, then repeat 2 for the repeat set. Recorded in the manifest and enforced."""
    by_fam = {f: sorted((t for t in tasks if t.family == f), key=lambda t: h(seed, "ord", t.fingerprint)) for f in FAMILIES}
    order, rnd = [], 0
    while any(by_fam.values()):
        for f in sorted(FAMILIES, key=lambda f: h(seed, "fam", rnd, f)):
            if by_fam[f]:
                t = by_fam[f].pop(0); order.append({"task_id": t.task_id, "repeat": 1})
        rnd += 1
    rep = sorted(repeats, key=lambda i: h(seed, "r2", i))
    return order + [{"task_id": i, "repeat": 2} for i in rep]


def public_task(t: Candidate, part: str) -> dict:
    """What the manifest (and any investigator) may see: the question, where to start and the answer shape. NEVER the truth, the expected answer text or the evidence pages."""
    return {"task_id": t.task_id, "family": t.family, "template": t.sub, "difficulty": t.difficulty, "partition": part, "question": t.full_question, "start_path": t.start_path, "answer_kind": t.kind,
            "answer_schema": answer_schema(t.kind), "pages_needed": t.pages_needed, "limits": {"max_model_requests": costs.step_limit(t.pages_needed), "max_steps": costs.step_limit(t.pages_needed), "timeout_seconds": 600}, "sensitive_to": list(t.sensitive_to)}


def _spread(ts: list[dict], n: int, seed, salt) -> list[dict]:
    """n tasks, round-robin over families, each family ordered by a seeded hash."""
    by: dict[str, list[dict]] = defaultdict(list)
    for t in sorted(ts, key=lambda t: h(seed, salt, t["task_id"])):
        by[t["family"]].append(t)
    out = []
    while len(out) < n and any(by.values()):
        for f in sorted(by, key=lambda f: h(seed, salt, f)):
            if by[f] and len(out) < n:
                out.append(by[f].pop(0))
    return out


def variant_test_plan(plan: dict, variant: str, seed: int = 0) -> dict:
    """The controlled test of ONE variant, sized to the pre-registered rule `exp2-compare-v1`: N_AFFECTED affected tasks (half holdout where possible), K_AFFECTED = 2 trials per task in EACH arm
    (variant and a CONTEMPORANEOUS control), N_NEG negative-control tasks with K_NEG = 1 per arm. The arms alternate which goes first, per task, to spread time drift. Planned only; never run
    without the owner's approval of its exact manifest, and only for a variant that `exp2-eligibility-v1` found eligible."""
    tasks = plan["tasks"]
    aff = [t for t in tasks if variant in t["sensitive_to"]]
    hold = _spread([t for t in aff if t["partition"] == "holdout"], N_AFFECTED // 2, seed, "vh")
    inv = _spread([t for t in aff if t["partition"] == "investigation"], N_AFFECTED - len(hold), seed, "vi")
    chosen = inv + hold
    if len(chosen) < N_AFFECTED:                                                       # top up from whichever partition has more
        rest = [t for t in aff if t not in chosen]
        chosen += _spread(rest, N_AFFECTED - len(chosen), seed, "vx")
    neg = _spread([t for t in tasks if variant not in t["sensitive_to"] and t["difficulty"] != "hard"], N_NEG, seed, "vn")
    trials = []
    for t, k in [(t, K_AFFECTED) for t in chosen] + [(t, K_NEG) for t in neg]:
        first = "control" if int(h(seed, "arm", variant, t["task_id"]), 16) % 2 == 0 else "variant"
        second = "variant" if first == "control" else "control"
        for r in range(1, k + 1):
            trials += [{"task_id": t["task_id"], "arm": first if r % 2 else second, "repeat": r}, {"task_id": t["task_id"], "arm": second if r % 2 else first, "repeat": r}]
    pages = {t["task_id"]: t["pages_needed"] for t in tasks}
    cost = costs.phase_cost([pages[x["task_id"]] for x in trials])
    return {"variant": variant, "affected": [t["task_id"] for t in chosen], "affected_by_partition": dict(Counter(t["partition"] for t in chosen)), "negative_controls": [t["task_id"] for t in neg],
            "repeats": {"affected_per_arm": K_AFFECTED, "negative_per_arm": K_NEG}, "trials": trials, "trial_count": len(trials), "cost": cost.__dict__,
            "meets_rule": len(chosen) >= MIN_AFFECTED and len(neg) >= 3, "rule": "exp2-compare-v1"}


def build_plan(pool: list[Candidate], *, seed: int = 0, quotas: dict[str, int] = QUOTAS, pilot_trials: int = PILOT_TRIALS, repeat_tasks: int = REPEAT_TASKS, executed: tuple = ()) -> dict:
    """`executed` = trials that have already been run (the pilot): they stay first, in that order, and the pilot phase is exactly them; the remaining trials follow in the standard order."""
    tasks = select(pool, quotas, seed)
    part = partition(tasks, seed)
    reps = repeat_set(tasks, part, repeat_tasks, seed)
    order = trial_order(tasks, reps, seed)
    by_id = {t.task_id: t for t in tasks}
    if executed:
        done = [dict(x) for x in executed]
        if (gone := [x["task_id"] for x in done if x["task_id"] not in by_id]):
            raise ValueError(f"executed trials are no longer in the task selection: {gone}")
        order, pilot_trials = done + [o for o in order if o not in done], len(done)
    pages = [by_id[o["task_id"]].pages_needed for o in order]
    pilot, main = order[:pilot_trials], order[pilot_trials:]
    pc, mc = costs.phase_cost(pages[:pilot_trials]), costs.phase_cost(pages[pilot_trials:])
    pv = {"schema": "exp2-study-plan-v1", "tasks": [public_task(t, part[t.task_id]) for t in sorted(tasks, key=lambda t: t.task_id)]}
    variant_tests = {v: variant_test_plan(pv, v, seed) for v in ("discoverability", "availability", "cost", "compatibility")}
    alloc = costs.allocation(pc, mc, variant_min_cost=min(v["cost"]["p50_usd"] for v in variant_tests.values()), variant_max_cost=max(v["cost"]["p50_usd"] for v in variant_tests.values()))
    warnings = [f"only {n} tasks are sensitive to the {v} variant (the comparison rule needs at least {MIN_AFFECTED})" for v, n in {v: sum(v in t.sensitive_to for t in tasks) for v in ("discoverability", "availability", "cost", "compatibility")}.items() if n < MIN_AFFECTED]
    plan = {"schema": "exp2-study-plan-v1", "seed": seed, "tasks": [public_task(t, part[t.task_id]) for t in sorted(tasks, key=lambda t: t.task_id)], "trial_order": order, "trial_order_sha256": canonical_hash(order),
            "phases": {"baseline_pilot": {"trials": pilot, "cost": pc.__dict__}, "baseline_main": {"trials": main, "cost": mc.__dict__}},
            "counts": {"tasks": len(tasks), "trials": len(order), "investigation": sum(v == "investigation" for v in part.values()), "holdout": sum(v == "holdout" for v in part.values()),
                       "by_family": dict(Counter(t.family for t in tasks)), "by_difficulty": dict(Counter(t.difficulty for t in tasks)), "by_kind": dict(Counter(t.kind for t in tasks)),
                       "sensitive_to": {v: sum(v in t.sensitive_to for t in tasks) for v in ("discoverability", "availability", "cost", "compatibility")}, "negative_control_tasks": sum(not t.sensitive_to for t in tasks)},
            "variant_tests": variant_tests, "allocation": alloc, "warnings": warnings, "cost_basis": "calculated at published prices; assumptions in exp2/costs.py; not a bill"}
    plan["plan_sha256"] = canonical_hash({k: v for k, v in plan.items() if k != "plan_sha256"})
    return plan
