"""Deterministic suite selection (selection-1). Uses ONLY evaluator records (never agent performance).

Rule: from candidates that pass every hard gate and are not near-duplicates of an already chosen task, pick greedily up to k tasks, each step taking
the candidate with the highest
    3 x (new personas) + 2 x (new journeys) + 1 x (new attributes) + 3 x (first multi-condition task, while none is chosen) + quality
ties broken by candidate_id ascending. If no multi-condition task was chosen and one is available, the last pick is replaced by the best such task.
The executed wording is the restated question for every selected task (it passes the acceptance gate; the customer wording is kept separately)."""
from __future__ import annotations

RULE_ID = "selection-1"


def _multi(r) -> bool:
    return bool(r["specification"]) and len(r["specification"].get("conditions", [])) > 1


def select(records: list[dict], k: int = 4) -> tuple[list[dict], list[dict]]:
    pool = sorted([r for r in records if r["hard_pass"]], key=lambda r: r["candidate_id"])
    chosen, log = [], []
    while len(chosen) < k and pool:
        personas = {r["persona"] for r in chosen}
        journeys = {r["journey"] for r in chosen}
        attrs = set().union(*(set(r["attributes"]) for r in chosen)) if chosen else set()
        has_multi = any(_multi(r) for r in chosen)

        def score(r):
            return (3 * (r["persona"] not in personas) + 2 * (r["journey"] not in journeys) + len(set(r["attributes"]) - attrs)
                    + (3 if _multi(r) and not has_multi else 0) + (r["quality"] or 0))
        eligible = [r for r in pool if not any(_sim(r, c) >= 0.6 for c in chosen)]
        if not eligible:
            break
        best = max(eligible, key=lambda r: (score(r), [-ord(ch) for ch in r["candidate_id"]]))
        log.append({"step": len(chosen) + 1, "picked": best["candidate_id"], "score": round(score(best), 3)})
        chosen.append(best)
        pool.remove(best)
    if chosen and not any(_multi(r) for r in chosen):
        multi = sorted([r for r in pool if _multi(r)], key=lambda r: (-(r["quality"] or 0), r["candidate_id"]))
        if multi:
            log.append({"step": "multi-condition requirement", "replaced": chosen[-1]["candidate_id"], "with": multi[0]["candidate_id"]})
            chosen[-1] = multi[0]
    for r in chosen:
        r["wordings"]["executed"] = "restated_question"
    return chosen, log


def _sim(a, b) -> float:
    from .evaluator import _signature
    sa, sb = _signature(a["specification"]), _signature(b["specification"])
    return len(sa & sb) / max(1, len(sa | sb))
