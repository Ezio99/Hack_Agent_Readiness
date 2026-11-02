"""selection-2: deterministic suite selection from evaluator-v2 records ONLY (never agent performance; Stage A cannot see any).

From the admitted deterministic tasks (natural or assisted) that are not near-duplicates (criterion similarity above the target) of an already
chosen task, pick greedily up to the target maximum, each step taking the highest
    3 x (persona still below its minimum) + 2 x (fills an empty weighted journey) + 1 x (new persona x journey cell)
  + 2 x (new capability) + 2 x (multi-condition while the share is below target) + 1 x (natural wording) + quality
ties broken by candidate_id ascending. Rubric (policy) tasks: up to the rubric maximum, journey-consistent first, then by candidate_id. Underspecified
requests are never selected (they are preserved and reported in the gap report); assisted tasks are labelled and analysed separately from natural."""
from __future__ import annotations

from ...taskeval.v2 import coverage as COV

RULE_ID = "selection-2"


def select(records: list[dict], context: dict, targets: dict | None = None) -> tuple[list[dict], list[dict], list[dict]]:
    t = {**COV.TARGETS, **(targets or {})}
    weights = {j["id"]: j["weight"] for j in context["journeys"]}
    pool = sorted([r for r in records if r["admission"] in ("natural", "assisted") and r["verifiability"] == "deterministic"], key=lambda r: r["candidate_id"])
    chosen, log = [], []
    hi = t["deterministic_tasks"][1]
    while len(chosen) < hi:
        per_persona = {}
        cells, caps, journeys = set(), set(), set()
        for r in chosen:
            per_persona[r["persona"]] = per_persona.get(r["persona"], 0) + 1
            caps.add(r["capability"])
            if r["journey_consistent"]:
                cells.add((r["persona"], r["journey"]))
                journeys.add(r["journey"])
        multi_share = sum(COV.multi_condition(r["specification"]) for r in chosen) / len(chosen) if chosen else 0.0

        def score(r):
            jc = r["journey_consistent"]
            return (3 * (per_persona.get(r["persona"], 0) < t["min_tasks_per_persona"]) + 2 * (jc and r["journey"] not in journeys and weights.get(r["journey"], 0) >= t["journey_min_weight"])
                    + 1 * (jc and (r["persona"], r["journey"]) not in cells) + 2 * (r["capability"] not in caps)
                    + 2 * (COV.multi_condition(r["specification"]) and multi_share < t["min_multi_condition_share"]) + 1 * (r["admission"] == "natural") + (r.get("quality") or 0))
        eligible = [r for r in pool if r not in chosen and all(COV.similarity(r["specification"], c["specification"]) <= t["max_pair_similarity"] for c in chosen)]
        if not eligible:
            break
        best = max(eligible, key=lambda r: (round(score(r), 6), [-ord(ch) for ch in r["candidate_id"]]))
        log.append({"step": len(chosen) + 1, "picked": best["candidate_id"], "score": round(score(best), 3)})
        chosen.append(best)
    rub = sorted([r for r in records if r["admission"] == "rubric"], key=lambda r: (not r["journey_consistent"], r["candidate_id"]))[:t["max_rubric_tasks"]]
    return chosen, rub, log
