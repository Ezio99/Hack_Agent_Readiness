"""Coverage matrix (persona x journey x capability), diversity and the provisional suite targets (proposal §3.4, decision 3).

Targets are PROVISIONAL defaults frozen into each suite record; they are reported, never used to lower an acceptance threshold. Gap texts name
personas, journeys and capabilities only: never answers, entities that are answers, or agent results."""
from __future__ import annotations

from itertools import combinations

CAPABILITIES = ("lookup", "single_condition_filter", "multi_condition_filter", "extremum", "ranked_subset", "either_of", "policy_rubric")
TARGETS = {"min_tasks_per_persona": 2, "journey_min_weight": 0.10, "min_tasks_per_weighted_journey": 1, "min_capabilities": 4,
           "min_multi_condition_share": 0.30, "max_pair_similarity": 0.6, "deterministic_tasks": (8, 12), "max_rubric_tasks": 2,
           "natural_share_aspiration": 0.70}


def capability(crit: dict | None, verifiability: str | None) -> str | None:
    if verifiability == "rubric":
        return "policy_rubric"
    if not crit:
        return None
    k = crit.get("kind")
    if k == "page_fact":
        return "lookup"
    if k == "item_set":
        return "multi_condition_filter" if len(crit["conditions"]) > 1 else "single_condition_filter"
    return k if k in CAPABILITIES else None


def multi_condition(crit: dict | None) -> bool:
    if not crit:
        return False
    n = len(crit.get("conditions", [])) + (1 if crit.get("kind") == "either_of" else 0)
    return n > 1


def signature(crit: dict | None) -> set:
    if not crit:
        return set()
    out = {(c["label"], c["op"], str(c["value"]).lower()) for c in crit.get("conditions", [])}
    if crit.get("kind") in ("extremum", "ranked_subset"):
        out.add((crit["label"], crit["direction"]))
    if crit.get("kind") == "either_of":
        out.add((crit["label"], "one_of", "|".join(sorted(v.lower() for v in crit["values"]))))
    if crit.get("kind") == "page_fact":
        out.add((crit["page"], crit["label"]))
    return out


def similarity(a: dict | None, b: dict | None) -> float:
    sa, sb = signature(a), signature(b)
    return len(sa & sb) / max(1, len(sa | sb))


def journey_consistent(journey: dict | None, attributes: set[str], verifiability: str | None) -> bool:
    """A declared journey counts towards coverage only if the task touches one of its attributes (the policies journey: a rubric task)."""
    if journey is None:
        return False
    if not journey["attributes"]:
        return verifiability == "rubric"
    return bool(set(journey["attributes"]) & attributes)


def report(tasks: list[dict], context: dict, targets: dict | None = None) -> dict:
    """tasks: [{persona, journey, capability, condition ('natural'|'assisted'|None), verifiability, criterion, attributes}] for the tasks of a
    suite (deterministic and rubric). Returns the matrix, measures, per-target status and the gap list."""
    t = {**TARGETS, **(targets or {})}
    journeys = {j["id"]: j for j in context["journeys"]}
    personas = [p["id"] for p in context["personas"]]
    det = [x for x in tasks if x["verifiability"] == "deterministic"]
    rub = [x for x in tasks if x["verifiability"] == "rubric"]
    matrix = {p: {j: 0 for j in journeys} for p in personas}
    inconsistent = []
    for x in tasks:
        j = journeys.get(x.get("journey"))
        if x.get("persona") in matrix and journey_consistent(j, set(x.get("attributes") or ()), x["verifiability"]):
            matrix[x["persona"]][x["journey"]] += 1
        elif x.get("journey"):
            inconsistent.append(x.get("id"))
    per_persona = {p: sum(matrix[p].values()) for p in personas}
    per_journey = {j: sum(matrix[p][j] for p in personas) for j in journeys}
    caps = {c: sum(x.get("capability") == c for x in tasks) for c in CAPABILITIES}
    pairs = [{"a": a.get("id"), "b": b.get("id"), "similarity": round(similarity(a["criterion"], b["criterion"]), 3)}
             for a, b in combinations(det, 2) if similarity(a["criterion"], b["criterion"]) > t["max_pair_similarity"]]
    multi = round(sum(multi_condition(x["criterion"]) for x in det) / len(det), 3) if det else 0.0
    natural = round(sum(x.get("condition") == "natural" for x in det) / len(det), 3) if det else 0.0
    lo, hi = t["deterministic_tasks"]
    status = {
        "tasks_per_persona": {"target": f">= {t['min_tasks_per_persona']} each", "actual": per_persona, "met": all(n >= t["min_tasks_per_persona"] for n in per_persona.values())},
        "weighted_journeys": {"target": f">= {t['min_tasks_per_weighted_journey']} for each journey with weight >= {t['journey_min_weight']}",
                              "actual": {j: per_journey[j] for j, d in journeys.items() if d["weight"] >= t["journey_min_weight"]},
                              "met": all(per_journey[j] >= t["min_tasks_per_weighted_journey"] for j, d in journeys.items() if d["weight"] >= t["journey_min_weight"])},
        "capabilities": {"target": f">= {t['min_capabilities']} distinct", "actual": sum(1 for n in caps.values() if n), "met": sum(1 for n in caps.values() if n) >= t["min_capabilities"]},
        "multi_condition_share": {"target": f">= {t['min_multi_condition_share']}", "actual": multi, "met": multi >= t["min_multi_condition_share"]},
        "near_duplicates": {"target": f"no pair above {t['max_pair_similarity']}", "actual": len(pairs), "met": not pairs},
        "deterministic_tasks": {"target": f"{lo}-{hi}", "actual": len(det), "met": lo <= len(det) <= hi},
        "rubric_tasks": {"target": f"<= {t['max_rubric_tasks']} (reported separately)", "actual": len(rub), "met": len(rub) <= t["max_rubric_tasks"]},
    }
    gaps = []
    gaps += [f"persona {p}: {n} task(s), target >= {t['min_tasks_per_persona']}" for p, n in per_persona.items() if n < t["min_tasks_per_persona"]]
    gaps += [f"journey {j} (weight {journeys[j]['weight']}): no task" for j, n in status["weighted_journeys"]["actual"].items() if n < t["min_tasks_per_weighted_journey"]]
    if not status["capabilities"]["met"]:
        gaps.append(f"capabilities: {status['capabilities']['actual']} covered, target >= {t['min_capabilities']} (missing: {', '.join(c for c, n in caps.items() if not n)})")
    if not status["multi_condition_share"]["met"]:
        gaps.append(f"multi-condition share {multi}, target >= {t['min_multi_condition_share']}")
    if pairs:
        gaps.append(f"{len(pairs)} near-duplicate pair(s) above {t['max_pair_similarity']}")
    if not status["deterministic_tasks"]["met"]:
        gaps.append(f"{len(det)} deterministic task(s), target {lo}-{hi}")
    if not status["rubric_tasks"]["met"]:
        gaps.append(f"{len(rub)} rubric task(s), at most {t['max_rubric_tasks']}")
    return {"targets": {k: (list(v) if isinstance(v, tuple) else v) for k, v in t.items()}, "matrix": matrix, "per_persona": per_persona, "per_journey": per_journey,
            "capabilities": caps, "multi_condition_share": multi, "natural_share": natural,
            "natural_share_note": f"aspirational development metric (target {t['natural_share_aspiration']}), not an admission rule",
            "deterministic": len(det), "rubric": len(rub), "near_duplicate_pairs": pairs, "journey_inconsistent": [i for i in inconsistent if i],
            "status": status, "gaps": gaps, "targets_met": not gaps}


def uncovered_cells(cov: dict, context: dict) -> list[dict]:
    """Persona x journey cells still empty, for the feedback synthesiser (weighted journeys first)."""
    weights = {j["id"]: j["weight"] for j in context["journeys"]}
    cells = [{"persona": p, "journey": j, "weight": weights[j]} for p, row in cov["matrix"].items() for j, n in row.items() if n == 0]
    return sorted(cells, key=lambda c: (-c["weight"], c["persona"], c["journey"]))
