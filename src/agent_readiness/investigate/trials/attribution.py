"""Deterministic failure attribution for ONE trial (plan D7). Conservative by design: it only says what the recorded evidence supports and otherwise answers `undetermined`.

classes
  success              passed and evidence-backed
  success_unsupported  passed, but the evidence pages were not actually shown to the model (right answer, not a measured success)
  provider_or_budget   VOID - the provider/budget/cost guard stopped the run; never a website result
  infrastructure       VOID - harness failure, cancelled, fidelity-guard stop
  task_invalid         the task cannot be solved inside its own limits (required hops exceed the step limit)
  agent                the decisive text WAS shown to the model (or the answer was malformed / navigation was possible and named) and the agent still failed
  tool_interface       the decisive text is in the page but was NOT in the observation the model received
  website              a structural blocker: the only link(s) leading toward the evidence have no accessible name
  undetermined         everything else (e.g. out of budget before reaching the evidence)
Signals (efficiency, repeats, evidence shown) are returned for every class so later stages can aggregate them without re-reading traces."""
from __future__ import annotations

from collections import Counter

from ..taskgen.criteria import norm_answer

VOID_PROVIDER = ("estimated_cost_limit", "model_output_error")
VOID_INFRA = ("infrastructure_error", "diagnostic_fidelity_violation", "cancelled")
OUT_OF_BUDGET = ("timeout", "request_limit")


def _shown(observations: list[dict], text: str, path: str | None) -> list[int]:
    t = norm_answer(text)
    return [i for i, o in enumerate(observations, 1) if (path is None or o["path"] == path) and t and t in norm_answer(o.get("text") or "")]


def signals(trial: dict, observations: list[dict], private: dict, profile: dict) -> dict:
    journey = trial["journey"]
    visited = [j["path"] for j in journey]
    ev_paths = private["evidence_paths"]
    start = (trial.get("task") or {}).get("start_path") or (visited[0] if visited else "/")
    min_views = max(len(set(ev_paths) | {start}), private.get("min_hops", 0) + 1)          # lower bound: every required page plus the start page
    actions = [json_key(a) for j in journey for a in j["actions"]]
    repeats = max(Counter(actions).values(), default=0)
    shown_steps = [_shown(observations, t, p) for p, t in private["evidence_texts"]]
    return {"page_views": len(visited), "min_page_views": min_views, "extra_page_views": max(0, len(visited) - min_views), "revisited_pages": sorted(p for p, n in Counter(visited).items() if n > 1),
            "max_identical_actions": repeats, "evidence_pages_visited": [p for p in ev_paths if p in visited], "evidence_pages_unvisited": [p for p in ev_paths if p not in visited],
            "evidence_texts_shown": sum(bool(v) for v in shown_steps), "evidence_texts_total": len(shown_steps), "model_requests": trial["metrics"]["model_requests"], "steps": trial["metrics"].get("steps")}


def json_key(a: dict) -> str:
    return f"{a['name']}:{sorted((a.get('params') or {}).items())}"


def _reach(profile: dict, starts: set[str], named_only: bool) -> set[str]:
    pages, seen, q = profile["pages"], set(starts), list(starts)
    while q:
        cur = q.pop()
        for c in pages.get(cur, {"controls": []})["controls"]:
            if c["href"] in pages and c["href"] not in seen and (c["name"] or not named_only):
                seen.add(c["href"])
                q.append(c["href"])
    return seen


def attribute(trial: dict, observations: list[dict], private: dict, profile: dict) -> dict:
    ev, out = trial["evaluation"], trial["outcome"]
    status = out["run_status"]
    sig = signals(trial, observations, private, profile)
    def res(primary, why, **extra):
        return {"primary": primary, "why": why, "void": primary in ("provider_or_budget", "infrastructure"), "signals": sig, **extra}
    if status in VOID_PROVIDER:
        return res("provider_or_budget", f"run stopped by {status}")
    if status in VOID_INFRA:
        return res("infrastructure", f"run stopped by {status}")
    if ev["passed"] and ev["evidence_backed"]:
        return res("success", "correct and the evidence was shown")
    if ev["passed"]:
        return res("success_unsupported", "correct answer, but the required evidence was not shown to the model", missing_count=len(ev.get("missing_evidence", [])))
    if not ev["answer_valid"] and out.get("answer") is not None:
        return res("agent", "the final answer did not match the required answer schema")
    if private["min_hops"] + 2 > trial["metrics"]["limits"]["max_steps"]:
        return res("task_invalid", "the required navigation does not fit inside the task's own step limit")
    if sig["evidence_texts_shown"]:
        return res("agent", "the decisive text was shown to the model, yet the answer was wrong or missing")
    visited_ev = sig["evidence_pages_visited"]
    unv = sig["evidence_pages_unvisited"]
    for p in visited_ev:                                         # visited an evidence page but its text never reached the model
        page = profile["pages"].get(p)
        if page and any(norm_answer(t) in norm_answer(page["text"]) for _, t in private["evidence_texts"] if t):
            return res("tool_interface", f"{p} was loaded and contains the decisive text, but the model's observation did not", page=p)
    if unv and status not in OUT_OF_BUDGET:
        visited = {j["path"] for j in trial["journey"]}
        via_names, via_any = _reach(profile, visited, True), _reach(profile, visited, False)
        blocked = [p for p in unv if p not in via_names and p in via_any]
        if blocked and len(blocked) == len(unv):
            return res("website", "the unvisited evidence page(s) can only be reached from the visited pages through controls that have no accessible name", blocked=blocked[:3])
        if all(p in via_names for p in unv):
            return res("agent", "a path of named links toward the evidence existed from the visited pages but was not followed", unvisited=unv[:3])
    if unv and status in OUT_OF_BUDGET:
        return res("undetermined", "the run ended on its budget before reaching the evidence (agent efficiency and site structure cannot be separated from one trial)", unvisited=unv[:3])
    return res("undetermined", "no deterministic rule explains the failure")
