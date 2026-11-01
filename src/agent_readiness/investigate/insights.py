"""Owner insights: a derived, model-free view of a finished run for a website owner, kept strictly apart from the strict VERIFIED path.

Nothing here is verified, promoted or patched. It reads only what the run already recorded (trials, attribution, the captured site profile, the frozen tasks, the investigator's hypotheses and their checker results)
and returns four things:
  * `site_properties`   measured facts about the captured site (e.g. a field is on every item page but on no listing card). Shown on their own: a property is not by itself a usability problem.
  * `task_effort`       what each agent trial measurably cost (requests, steps vs the limit, page views vs the minimum) and how it was graded, with the STRICT grade labelled as strict name matching next to a loose
                        `names mentioned` comparison, so an answer that is right in substance but worded differently is not described as 'the agent failed to find it'.
  * `possible_causes`   hypotheses, never conclusions: the investigator's claims grouped without repetition and labelled with their checker status (supported below promotion / unverifiable with the checker's own
                        reason / open-ended), plus one rule-based cause that appears only when a measured site property and measured friction on tasks that need that field coincide.
  * `suggestions`       text only, UNVALIDATED, emitted only where relevant trial friction exists, with the expected benefit stated as a hypothesis. No patch is built or applied here.
"""
from __future__ import annotations

import json
from pathlib import Path

from .run import InvestigationRun
from .taskgen import freeze as freezer
from .taskgen.criteria import norm_answer

FRICTION_EXTRA_VIEWS = 2              # the same threshold the strict path uses to call extra page views a cost
MAX_TEXT = 320


def _squash(s: str) -> str:
    return norm_answer(s).replace(" ", "")


def _labels(criterion: dict) -> list[str]:
    c = criterion or {}
    if c.get("kind") == "item_set":
        return [x["label"] for x in c.get("conditions") or [] if x.get("label")]
    return [c["label"]] if c.get("label") else []


def _answer_strings(answer) -> list[str]:
    if isinstance(answer, dict):
        v = answer.get("answers") if "answers" in answer else answer.get("answer")
        return [str(x) for x in v] if isinstance(v, list) else ([str(v)] if v is not None else [])
    return []


def _trials(run: InvestigationRun) -> dict[str, dict]:
    out = {}
    for f in sorted((run.dir / "artifacts" / "trials").glob("*.json")):
        d = json.loads(f.read_text())
        out[d["task_id"]] = d
    return out


def _task_effort(task: dict, private: dict, trial: dict, att: dict) -> dict:
    ev, m, sig = trial["evaluation"], trial["metrics"], att["signals"]
    truth = private["truth"] if isinstance(private["truth"], list) else [private["truth"]]
    answers = _answer_strings(trial["outcome"].get("answer"))
    blob = _squash(" ".join(answers))
    mentioned = sum(_squash(t) in blob for t in truth) if blob else 0
    d = ev.get("details") or {}
    if "recall" in d:
        strict = f"strict name match: recall {d['recall']}, precision {d['precision']} ({d.get('missing', 0)} expected name(s) not matched exactly, {d.get('extra', 0)} answer item(s) not matched)"
    else:
        strict = "strict answer match: " + ("matched" if ev["passed"] else "not matched")
    row = {"task_id": task["task_id"], "question": task["question"], "source": task["source"], "partition": task["partition"], "trial_id": trial["trial_id"],
           "passed": bool(ev["passed"]), "evidence_backed": ev.get("evidence_backed"), "requests": m["model_requests"], "steps_used": m.get("steps"), "step_limit": m["limits"]["max_steps"],
           "page_views": m["page_views"], "minimum_page_views": sig["min_page_views"], "extra_page_views": sig["extra_page_views"], "attribution": att["primary"], "strict_grade": strict,
           "names_mentioned_in_answer": f"{mentioned} of {len(truth)}" if blob else "no answer", "calculated_cost_usd": m.get("calculated_cost_usd"),
           "friction": sig["extra_page_views"] >= FRICTION_EXTRA_VIEWS or (not ev["passed"] and m.get("steps") is not None and m["steps"] >= m["limits"]["max_steps"] - 1)}
    notes = []
    if not ev["passed"] and truth and mentioned == len(truth):
        notes.append("Graded as failed by strict matching, but the answer text mentions every expected name: this shows a wording or format mismatch, not that the agent failed to find the answer.")
    elif not ev["passed"] and mentioned:
        notes.append(f"The answer text mentions {mentioned} of the {len(truth)} expected names; the strict grade is not a measure of how much the agent understood.")
    if row["steps_used"] is not None and row["steps_used"] >= row["step_limit"] - 1 and not ev["passed"]:
        notes.append("The agent used essentially its whole step budget.")
    row["notes"] = notes
    return row


def _site_properties(profile: dict, wanted: set[str]) -> list[dict]:
    """For each field the tasks needed: on how many item pages, shown on how many cards of the largest listing that carries it (captured site, measured by code)."""
    out = []
    for label in sorted(wanted):
        best = None
        for l in profile.get("listings", []):
            f = next((v for k, v in l["fields"].items() if norm_answer(k) == norm_answer(label)), None)
            if f and f["detail_pages"] >= 2 and (best is None or f["of"] > best[1]["of"]):
                best = (l, f)
        if best:
            l, f = best
            out.append({"field": label, "listing": l["listing"], "item_pages_with_field": f["detail_pages"], "listing_items": f["of"], "shown_on_listing_items": f["in_listing_item"],
                        "absent_from_cards": f["in_listing_item"] <= f["of"] * 0.5, "evidence": "site profile (captured copy), measured by code"})
    return out


def _group_hypotheses(run: InvestigationRun, inv: dict) -> list[dict]:
    rows = {r["hypothesis_id"]: r for r in inv.get("verification", [])}
    groups: dict[tuple, dict] = {}
    findings = {f.hypothesis_id for f in run.evidence.findings.values()}
    for h in run.evidence.hypotheses.values():
        if h.id in findings:
            continue                                                                  # promoted claims live in the strict findings, not here
        v = rows.get(h.id)
        if h.tier == "novel":
            status, key = "open-ended idea: not checked by any code", ("novel", h.statement[:80].lower())
        elif v and v["result"] == "supported":
            status, key = f"the checker supported it, but only {v['support']} task(s) show a cost, below the promotion rule (needs 2): not a finding", (h.claim_kind, "supported")
        elif v and v["result"] == "refuted":
            status, key = f"the checker refuted it: {v['detail'][:140]}", (h.claim_kind, "refuted")
        else:
            reason = (v or {}).get("detail") or (h.verification.result if h.verification else "not checked")
            status, key = f"could not be checked: {reason}. Treated as an unverified idea, not as a finding.", (h.claim_kind, "unverifiable", reason[:60])
        g = groups.setdefault(key, {"claim_kind": h.claim_kind, "status": status, "statements": [], "fields": [], "refs": [], "source": "the investigator (model)"})
        g["statements"].append(h.statement)
        lab = h.params.get("label")
        if lab and lab not in g["fields"]:
            g["fields"].append(lab)
        for r in [h.id, *h.citations[:3]]:
            if r not in g["refs"]:
                g["refs"].append(r)
    out = []
    for g in groups.values():
        text = g["statements"][0] if len(g["statements"]) == 1 else f"{g['statements'][0]} (the investigator made {len(g['statements'])} similar claims, one per field)"
        out.append({"text": text[:MAX_TEXT + 80], "fields": g["fields"], "claim_kind": g["claim_kind"], "status": g["status"], "refs": g["refs"][:8], "source": g["source"], "label": "POSSIBLE CAUSE (hypothesis, not established)"})
    return out


def build_insights(run: InvestigationRun) -> dict | None:
    """None for a run that has no frozen tasks or baseline trials (nothing measured yet)."""
    if not run.has_artifact("tasks-manifest") or not (run.dir / "artifacts" / "trials").exists() or not run.has_artifact("attribution"):
        return None
    manifest, private = freezer.load(run)
    trials, att = _trials(run), run.artifact("attribution")
    att = att.get("trials") or att
    profile = run.artifact("site-profile")
    effort = [_task_effort(t, private[t["task_id"]], trials[t["task_id"]], att[trials[t["task_id"]]["trial_id"]]) for t in sorted(manifest["tasks"], key=lambda t: t["question"])
              if t["task_id"] in trials and trials[t["task_id"]]["trial_id"] in att and not att[trials[t["task_id"]]["trial_id"]]["void"]]
    labels = {t["task_id"]: _labels(private[t["task_id"]]["criterion"]) for t in manifest["tasks"]}
    props = _site_properties(profile, {l for ls in labels.values() for l in ls})
    absent = {norm_answer(p["field"]): p for p in props if p["absent_from_cards"]}
    for row in effort:
        row["fields_needed"] = labels[row["task_id"]]
        row["needs_field_absent_from_cards"] = [l for l in labels[row["task_id"]] if norm_answer(l) in absent]
    inv = run.artifact("investigation") if run.has_artifact("investigation") else {}
    causes = _group_hypotheses(run, inv)
    friction_rows = [r for r in effort if r["friction"] and r["needs_field_absent_from_cards"]]
    suggestions, rule_cause = [], None
    if friction_rows:
        fields = sorted({l for r in friction_rows for l in r["needs_field_absent_from_cards"]})
        listing = absent[norm_answer(fields[0])]["listing"]
        tids = [r["task_id"] for r in friction_rows]
        refs = [r["trial_id"] for r in friction_rows]
        rule_cause = {"text": f"Possible cause (rule-based, untested): the cards on {listing} do not show {', '.join(fields)}, so an agent has to open item pages to read them; on {len(friction_rows)} task(s) that needed these fields the agent used "
                              f"{min(r['extra_page_views'] for r in friction_rows)}-{max(r['extra_page_views'] for r in friction_rows)} more page views than the minimum or most of its step budget. Other explanations (the agent's strategy, the step limit) are not ruled out.",
                      "fields": fields, "claim_kind": None, "status": "derived by a fixed rule from two measurements; no checker or model was involved", "refs": refs, "source": "rule", "label": "POSSIBLE CAUSE (hypothesis, not established)"}
        suggestions.append({"text": f"Consider showing {', '.join(fields)} on each listing card on {listing} (or in a comparison view), so the choice can be made without opening every item page.", "fields": fields, "tasks": tids,
                            "basis": refs + [p["listing"] for p in props if norm_answer(p["field"]) in {norm_answer(f) for f in fields}],
                            "expected_benefit": "HYPOTHESIS, not measured: fewer page views and fewer step-budget failures on tasks that compare these fields.", "risks": ["Cards become busier", "Not tested: no change was applied and nothing was re-run"],
                            "label": "SUGGESTED IMPROVEMENT (UNVALIDATED)", "source": "rule", "patch": None})
    for n in (inv.get("novel_changes", []) if any(r["friction"] for r in effort) else []):          # the investigator's own text-only proposals, labelled as such, never duplicated, and only where a trial measured friction
        h = run.evidence.hypotheses.get(n["hypothesis_id"])
        if h and not any(n["proposed_change"].strip().lower() == s["text"].strip().lower() for s in suggestions):
            suggestions.append({"text": n["proposed_change"], "fields": [], "tasks": [], "basis": [h.id, *h.citations[:3]], "expected_benefit": "HYPOTHESIS, not measured: " + (h.prediction or "none stated"), "risks": ["Based on an unverified idea"],
                                "label": "SUGGESTED IMPROVEMENT (UNVALIDATED)", "source": "the investigator (model)", "patch": None})
    if rule_cause:
        causes = [rule_cause, *causes]
    findings = list(run.evidence.findings.values())
    fork = run.dir / "fork.json"
    fk = json.loads(fork.read_text()) if fork.exists() else None
    summary = (f"{len(friction_rows)} of {len(effort)} measured task(s) showed friction on a field that the listing cards do not show." if friction_rows else
               f"No friction was observed on these {len(effort)} task(s): " + ("; ".join(f"{r['requests']} request(s), {r['extra_page_views']} extra page view(s)" for r in effort) if effort else "no usable trial") +
               ". No friction-based suggestion is made.")
    return {"schema": "owner-insights-v1", "summary": summary, "site_properties": props, "task_effort": effort, "friction_tasks": [r["task_id"] for r in effort if r["friction"]], "possible_causes": causes, "suggestions": suggestions,
            "strict_findings": len(findings), "claim_audit": inv.get("claim_audit", []),
            "provenance": {"run_id": run.state["id"], "mode": run.mode, "source_run": fk["source_run"] if fk else None, "task_sources": {s: sum(t["source"] == s for t in manifest["tasks"]) for s in sorted({t["source"] for t in manifest["tasks"]})},
                           "investigator_model": inv.get("model"), "investigation_status": inv.get("status"), "frozen_tasks": len(manifest["tasks"]),
                           "note": "Derived from recorded measurements only; no model call; nothing here is verified, promoted, patched or applied."}}
