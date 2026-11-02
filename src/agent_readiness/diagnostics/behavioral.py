"""Behavioral observations from recorded trials (the standard trial record: journey, mirror log, metrics, evaluation). Every observation names the
trials and step numbers it comes from. `evidence_origin` says what produced the behaviour: real_model, dev_fixture or scripted. Fixture behaviour
checks the pipeline; it is not evidence about agents.

Rules (per trial, aggregated per rule x task x version):
  revisit                  a page returned to twice or more after leaving it (consecutive steps on one page, e.g. scrolling, are one visit)
  loop                     oscillation between two pages (A, B, A, B)
  retry                    the same action repeated on consecutive steps
  dead-end                 an HTTP error or blocked request, or an action that failed
  unnecessary-navigation   3+ distinct pages that neither hold the answer nor lead to it (outside the task's evidence pages, start page and listing)
  budget-exhaustion        the trial used (nearly) all its model requests, or stopped on a limit
  unsupported-answer       a correct answer the agent was never shown (not evidence-backed)
  incorrect-answer         a completed trial whose answer was graded wrong"""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

from .model import Evidence, Finding, stable_id

BROWSER_AUTO = re.compile(r"^/(favicon\.ico|apple-touch-icon[^/]*\.png|robots\.txt)$")      # fetched by the browser itself, not by the agent

SEVERITY = {"incorrect-answer": "high", "budget-exhaustion": "high", "unsupported-answer": "medium", "loop": "medium", "dead-end": "medium",
            "unnecessary-navigation": "low", "revisit": "low", "retry": "low"}
IMPACT = {"incorrect-answer": "the task was not completed correctly", "budget-exhaustion": "the agent ran out of its request budget, or nearly did",
          "unsupported-answer": "the answer was correct but not grounded in anything the agent was shown", "loop": "steps spent moving back and forth",
          "dead-end": "steps spent on errors or failed actions", "unnecessary-navigation": "steps spent on pages that do not hold the answer",
          "revisit": "the same page was shown repeatedly", "retry": "an action was repeated"}
ADVICE = {"incorrect-answer": "Compare the agent's answer with the pages it saw (trial steps cited) to see where the needed information was missing or misread.",
          "budget-exhaustion": "Find which pages consumed the budget (steps cited) and whether the needed facts could be reached in fewer steps.",
          "unsupported-answer": "Check whether the answer is reachable within the agent's view (e.g. below the fold of a long page) before trusting such passes.",
          "loop": "Inspect the two pages in the loop: the agent may be failing to find a link or fact it expects on one of them.",
          "dead-end": "Fix or remove the failing link or control (status and step cited).",
          "unnecessary-navigation": "Check the pages visited off the evidence path: navigation labels may be misleading the agent.",
          "revisit": "Check why the agent returned to this page: it may be a listing it must consult repeatedly to compare items.",
          "retry": "Inspect the repeated action: the target may not respond as the agent expects."}


def _trial_findings(name: str, t: dict, priv: dict | None, v2: dict | None = None) -> list[tuple[str, list[Evidence], dict]]:
    out = []
    journey = t.get("journey") or []
    paths = [s.get("path") for s in journey if s.get("path")]
    ev, metrics, outcome = t.get("evaluation") or {}, t.get("metrics") or {}, t.get("outcome") or {}
    seq = [p for i, p in enumerate(paths) if i == 0 or p != paths[i - 1]]                 # visits: maximal runs of consecutive steps on one page
    for p, n in Counter(seq).items():
        if n >= 3:
            out.append(("revisit", [Evidence("trial", name, f"{p} visited {n} times (returned {n - 1} times)")], {"page": p, "visits": n}))
    for i in range(len(seq) - 3):
        if seq[i] == seq[i + 2] and seq[i + 1] == seq[i + 3] and seq[i] != seq[i + 1]:
            out.append(("loop", [Evidence("trial", name, f"{seq[i]} <-> {seq[i + 1]}")], {"pages": [seq[i], seq[i + 1]]}))
            break
    acts = [json.dumps(s.get("actions"), sort_keys=True) for s in journey]
    rep = [journey[i]["step"] for i in range(1, len(acts)) if acts[i] == acts[i - 1] and '"scroll' not in acts[i]]
    if rep:
        out.append(("retry", [Evidence("step", f"{name}#{s}") for s in rep[:5]], {"steps": rep}))
    bad = [(m.get("path"), m.get("status")) for m in ((t.get("mirror") or {}).get("log") or []) if (m.get("status") or 200) >= 400 and not BROWSER_AUTO.match(m.get("path") or "")]
    blocked = (t.get("mirror") or {}).get("blocked") or []
    errs = [s["step"] for s in journey for x in (s.get("executed") or []) if x.get("error")]
    if bad or blocked or errs:
        out.append(("dead-end", [Evidence("trial", name, f"http errors {bad[:3]}; blocked {len(blocked)}; failed actions at steps {errs[:5]}")], {"http": bad[:10], "failed_steps": errs}))
    if priv is not None:
        useful = set(priv.get("evidence_paths") or []) | {(t.get("task") or {}).get("start_path", "/"), "/"}
        off = sorted({p for p in paths if p not in useful})
        if len(off) >= 3:
            out.append(("unnecessary-navigation", [Evidence("trial", name, f"{len(off)} pages off the evidence path: {off[:5]}")], {"pages": off}))
    lim = (metrics.get("limits") or {}).get("max_model_requests")
    if (lim and (metrics.get("model_requests") or 0) >= lim - 1) or "limit" in str(outcome.get("stop_reason") or ""):
        out.append(("budget-exhaustion", [Evidence("trial", name, f"{metrics.get('model_requests')} of {lim} model requests; stop {outcome.get('stop_reason')}")], {"requests": metrics.get("model_requests"), "limit": lim}))
    if ev.get("passed") and not ev.get("evidence_backed"):
        miss = ev.get("missing_evidence") or []                          # the requirement texts are the expected answers: count them, never quote them
        out.append(("unsupported-answer", [Evidence("trial", name, f"{len(miss)} required evidence item(s) were not shown to the agent "
                                                                     f"({sum(m.startswith('observed_text:') for m in miss)} answer text, {sum(m.startswith('visited_path:') for m in miss)} page visit)")], {"missing": len(miss)}))
    if outcome.get("run_status") == "completed" and not ev.get("passed"):
        note = " (post-hoc grader v2: correct; the answer adds consistent detail)" if (v2 or {}).get("passed") else ""
        out.append(("incorrect-answer", [Evidence("trial", name, "graded not passed by the official grader v1" + note)], {"v2_passed": (v2 or {}).get("passed")}))
    return out


def observe(trials: dict[str, dict], private: dict, *, site: str, version: str, version_sha: str, origin: str, tasks_alias: dict[str, str] | None = None,
            v2: dict[str, dict] | None = None) -> list[Finding]:
    """trials: {artifact name: trial record} of ONE version. Aggregates per rule x task."""
    agg: dict[tuple[str, str], dict] = {}
    for name, t in sorted(trials.items()):
        tid = t["task_id"]
        for rule, evs, detail in _trial_findings(name, t, private.get(tid), (v2 or {}).get(name)):
            a = agg.setdefault((rule, tid), {"evidence": [], "trials": set(), "details": []})
            a["evidence"] += evs
            a["trials"].add(name)
            a["details"].append(detail)
    total = Counter(t["task_id"] for t in trials.values())
    out = []
    for (rule, tid), a in sorted(agg.items()):
        label = (tasks_alias or {}).get(tid, tid)
        out.append(Finding(stable_id("B", rule, site, version, tid), "behavioral", rule, f"{rule.replace('-', ' ')} on task {label} ({len(a['trials'])}/{total[tid]} trials)",
                           site, version, version_sha, SEVERITY[rule], IMPACT[rule], "observed", a["evidence"][:12], ADVICE[rule],
                           "Re-run the task after a change and compare this observation's frequency across versions.", tasks=[tid], evidence_origin=origin,
                           detail={"trials": sorted(a["trials"]), "occurrences": a["details"][:12]}))
    return out


def item_page_visits(trial: dict, item_pages: set[str]) -> int:
    return len({s.get("path") for s in trial.get("journey") or [] if s.get("path") in item_pages})
