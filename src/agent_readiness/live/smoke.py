"""The report of a task-generation-only smoke test: what the model proposed, what the independent gate accepted or rejected and why, whether the accepted tasks relate to the goal, what it cost, and
whether the provider's response shapes (structured output, usage) were compatible. Built only from the run's own artifacts and ledger. No truth, expected answer or criterion is included; the
relevance check is a LEXICAL HEURISTIC that points a person at the questions, it is not a verification."""
from __future__ import annotations

import re
from collections import Counter

STOP = set("can could would should does will with that this have from what which when into your their there about across between each every than then them they also only some more most "
           "agent agents user users site website evaluate evaluation check whether find able".split())


def _stem(w: str) -> str:
    return w[:-1] if w.endswith("s") and len(w) > 4 else w


def terms(text: str) -> set[str]:
    return {_stem(w) for w in re.findall(r"[a-z]{4,}", (text or "").lower()) if w not in STOP}


def relevance(goal: str, questions: list[str]) -> dict:
    g = terms(goal)
    rows = [{"question": q, "shared_goal_terms": sorted(g & terms(q))} for q in questions]
    n = sum(bool(r["shared_goal_terms"]) for r in rows)
    return {"method": "lexical heuristic: goal words (4+ letters, light stemming) that also occur in the question; a person must read the questions and judge relevance", "goal_terms": sorted(g),
            "tasks_sharing_a_goal_term": n, "of": len(rows), "per_task": rows}


def build_report(run, job: dict, *, cap_usd: float, state: str) -> dict:
    tg = run.artifact("taskgen-report") if run.has_artifact("taskgen-report") else {"accepted": [], "rejected": [], "model_calls": [], "rule_topup": 0}
    calls = tg["model_calls"]
    led: dict[str, dict] = {}
    for e in run.ledger(cap_usd).entries():
        if "-taskgen" in e["id"]:
            led.setdefault(e["id"], {"id": e["id"], "reserved_usd": None, "settled_usd": None})
            led[e["id"]]["reserved_usd" if e["kind"] == "reserve" else "settled_usd"] = e["usd"]
    spent = round(sum((r["settled_usd"] if r["settled_usd"] is not None else r["reserved_usd"] or 0) for r in led.values()), 6)
    rej = Counter(r["reason"].split(":")[0][:80] for r in tg["rejected"])
    accepted = [{"question": a["question"], "criterion_kind": a["kind"], "source": a["source"]} for a in tg["accepted"]]
    compat = []
    for c in calls:
        u = c.get("usage") or {}
        compat.append({"batch": c["batch"], "status": c["status"], "model_reported": c.get("model"), "attempts": c.get("attempts"), "proposed": c.get("proposed"),
                       "usage_has_prompt_and_completion_tokens": u.get("prompt_tokens") is not None and u.get("completion_tokens") is not None, "prompt_tokens": u.get("prompt_tokens"),
                       "completion_tokens": u.get("completion_tokens"), "error": c.get("error"), "unusable_output": (c.get("diagnostics") or None)})
    goal = job["goal"]
    gb = tg.get("goal_binding")
    if gb:
        asm = gb["assessments"]
        rel = {"method": gb["verifier"], "relevant_tasks": gb["relevant_tasks"], "gate_accepted_tasks": gb["gate_accepted_tasks"], "needed": gb["needed"], "goal_analysis_site_grounded": gb["analysis"],
               "model_goal_analysis": gb["model_goal_analysis"], "limitations": gb["analysis"]["limitations"], "limitation_details": gb["analysis"].get("limitation_details", []), "coverage": gb["coverage"], "coverage_status": gb["coverage"]["status"], "per_task": [{k: a[k] for k in ("question", "aspects_matched", "entity_match", "goal_relevant", "why", "model_goal_link")} for a in asm],
               "tasks_sharing_a_goal_term": gb["relevant_tasks"], "of": gb["gate_accepted_tasks"]}
    else:
        rel = relevance(goal, [a["question"] for a in accepted])
    return {
        "schema": "live-smoke-report-v1", "job_id": job["id"], "job_state": state, "goal": goal, "stopped_after": "taskgen + freeze (no browser trial, investigator or recommendation ran)",
        "yield": {"requests_made": len(calls), "max_requests": 3, "batches_ok": sum(c["status"] == "ok" for c in calls), "tasks_proposed": sum(c.get("proposed") or 0 for c in calls),
                  "tasks_accepted": len(accepted), "tasks_rejected": len(tg["rejected"]), "needed": 4, "meets_minimum": (gb["coverage"]["passes"] if gb else len(accepted) >= 4), "rule_topup_tasks": tg.get("rule_topup", 0),
                  "accepted_by_source": dict(Counter(a["source"] for a in accepted))},
        "independent_verification": {"how": "each accepted task's criterion was compiled and evaluated against the captured site by the gate (code, not the model); the model supplied no answers",
                                     "rejection_reasons": dict(rej), "rejected_examples": [{"question": r["question"][:160], "reason": r["reason"][:160]} for r in tg["rejected"][:12]]},
        "accepted_tasks": accepted, "relevance_to_goal": rel, "proposal_accounting": tg.get("accounting"),
        "cost": {"calculated_usd": spent, "cap_usd": cap_usd, "basis": "calculated from provider-reported tokens at published prices; not a bill", "per_request": list(led.values()),
                 "unsettled_requests": [r["id"] for r in led.values() if r["settled_usd"] is None]},
        "provider_compatibility": compat,
    }
