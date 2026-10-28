"""Evidence-linked diagnostic findings for one scan, plus controlled comparison between two scans.

Rules are deliberately conservative. Every finding carries a category (website | agent_reasoning | agent_tool_interface | infrastructure | security | task_outcome |
undetermined) and a confidence: ``observed`` (a directly measured fact), ``inferred`` (follows from measured facts by a stated rule) or ``hypothesis`` (a possible cause
or fix that has NOT been validated). A recommendation is only attached to a finding that supports it, always labelled an unvalidated hypothesis, and names the controlled
rescan that would test it. Nothing here claims that a design change helps; one mock or single run cannot establish an effect."""
from __future__ import annotations

import re
from typing import Any

HYPOTHESIS = "hypothesis_unvalidated"
INFRA_STATUSES = {"infrastructure_error": "the harness or provider failed", "timeout": "the wall-clock limit was reached", "request_limit": "the model-request limit was reached",
                  "estimated_cost_limit": "the estimated-cost limit was reached", "diagnostic_fidelity_violation": "the fidelity guard blocked a request (the request did not match the frozen configuration)",
                  "cancelled": "the scan was cancelled", "model_output_error": "the model output could not be used"}


def _finding(fid, category, title, summary, confidence, evidence=None, recommendation=None, validate_with=None):
    f = {"id": fid, "category": category, "title": title, "summary": summary, "confidence": confidence, "evidence": evidence or []}
    if recommendation:
        f["recommendation"] = {"text": recommendation, "status": HYPOTHESIS, "validate_with": validate_with}
    return f


def _last_result_in_history(request_event: dict) -> str | None:
    for message in request_event.get("messages", []):
        if message.get("role") != "user":
            continue
        content = message.get("content")
        for part in (content if isinstance(content, list) else [{"text": content}]):
            text = (part or {}).get("text") or ""
            if "<agent_history>" in text and "</agent_history>" in text:
                block = text[text.index("<agent_history>"): text.index("</agent_history>")].split("<step>")[-1]
                marker = block.rfind("\nResult\n")
                return block[marker + 8:].strip() if marker >= 0 else None
    return None


def visibility_gap_steps(events: list[dict]) -> list[int]:
    """Steps whose tool output carried links (href=...) that the model's NEXT request did not show (only a count line survived in its history)."""
    results = [e["result"]["result"] for e in events if e["kind"] == "step_result"]
    requests = [e for e in events if e["kind"] == "model_request"]
    gaps = []
    for i, res in enumerate(results):
        tool = "\n".join((r.get("extracted_content") or "") for r in res)
        if 'href="' in tool and i + 1 < len(requests):
            seen = _last_result_in_history(requests[i + 1])
            if seen is not None and "href" not in seen:
                gaps.append(i + 1)
    return gaps


def _runs(steps: list[int]) -> list[list[int]]:
    out: list[list[int]] = []
    for s in steps:
        if out and s == out[-1][-1] + 1:
            out[-1].append(s)
        else:
            out.append([s])
    return out


def repeated_actions(journey: list[dict]) -> list[list[int]]:
    """Runs of >= 3 consecutive steps with the identical action name and parameters."""
    sig = [(j["step"], str(j["actions"][:1])) for j in journey if j["actions"]]
    runs, cur = [], []
    for step, s in sig:
        if cur and s == cur[-1][1]:
            cur.append((step, s))
        else:
            if len(cur) >= 3:
                runs.append([c[0] for c in cur])
            cur = [(step, s)]
    if len(cur) >= 3:
        runs.append([c[0] for c in cur])
    return runs


def reference_path_length(instance, variant) -> int | None:
    try:
        from .mock import scripted_plan
        return len(scripted_plan(instance, variant)[0])
    except Exception:
        return None


def analyze(record: dict, events: list[dict], instance, variant) -> dict:
    ev, out, journey = record["evaluation"], record["outcome"], record["journey"]
    spec, findings = instance.spec, []
    n = lambda: f"F{len(findings) + 1}"
    mode = record["scan"]["mode"]
    # 1. outcome (always)
    if ev["passed"] and ev["evidence_backed"]:
        findings.append(_finding(n(), "task_outcome", "Independent evaluator: PASS with required evidence shown", "The submitted answer matched the independent oracle, and the information the task depends on appeared in pages shown to the agent.", "observed"))
    elif ev["passed"]:
        findings.append(_finding(n(), "task_outcome", "Correct answer, but required information was not shown to the agent",
                                 "The answer matches the oracle, yet the pages shown to the agent lacked required facts: " + "; ".join(ev["missing_evidence"][:4]) + ". The agent may have guessed or relied on knowledge outside the observed pages, so this pass is not evidence that the site communicates the information.",
                                 "observed", [{"note": m} for m in ev["missing_evidence"][:6]]))
    elif not ev["answer_valid"]:
        findings.append(_finding(n(), "task_outcome", "No valid answer was submitted", "; ".join(ev["reasons"]) or "The run ended without an answer in the required format.", "observed"))
    else:
        findings.append(_finding(n(), "task_outcome", "Independent evaluator: FAIL", "; ".join(ev["reasons"]), "observed", [{"note": r} for r in ev["reasons"]]))
    # 2. infrastructure / limits / security
    status = out["run_status"]
    if status in INFRA_STATUSES and status != "model_output_error":
        findings.append(_finding(n(), "infrastructure", f"Run ended early: {status}", f"{INFRA_STATUSES[status]}. This is not attributed to the website.", "observed", [{"note": e} for e in out["errors"][:3]]))
    elif status == "model_output_error":
        findings.append(_finding(n(), "agent_tool_interface", "The model's output could not be parsed", "The response did not match the required format. Format compliance is a model/harness matter, not a website property.", "observed"))
    blocked = [j["step"] for j in journey for x in j["executed"] if "blocked by security policy" in (x["error"] or "")]
    if blocked:
        findings.append(_finding(n(), "security", "Navigation outside the allowed origin was blocked", "The agent tried to open a page outside the environment under test; the browser's origin allowlist refused it before any request left the machine.", "observed", [{"step": s} for s in blocked]))
    # 3. agent-tool interface: visibility gap and repeated calls
    gaps = visibility_gap_steps(events)
    for run in [r for r in _runs(gaps) if len(r) >= 3]:
        findings.append(_finding(n(), "agent_tool_interface", f"Tool output was not visible to the model (steps {run[0]}–{run[-1]})",
                                 f"A tool returned page links to the harness in {len(run)} consecutive steps, but the model's next request showed only a count line, so the same call was repeated. This is an agent/tool-interface defect, not evidence about the website.",
                                 "observed", [{"step": s} for s in run]))
    for run in repeated_actions(journey):
        if not set(run) <= set(gaps):
            findings.append(_finding(n(), "agent_reasoning", f"Repeated the same action without progress (steps {run[0]}–{run[-1]})", f"The identical action was issued {len(run)} times in a row; the page did not change in a way that advanced the task.", "inferred", [{"step": s} for s in run]))
    # 4. wrong answer: where does the evidence say the problem lies?
    text_gaps = [m for m in ev["missing_evidence"] if m.startswith("observed_text")]
    if not ev["passed"] and ev["answer_valid"] and status not in INFRA_STATUSES:
        if ev["evidence_satisfied"]:
            findings.append(_finding(n(), "agent_reasoning", "The required facts were shown, but the answer is wrong", "Every required fact appeared in pages shown to the agent, so the error arose after viewing the information (extraction, reasoning or arithmetic), not from missing information.", "inferred"))
            if variant.factor("specs") == "fragmented" and re.search(r"\bRAM\b|battery|every criterion", " ".join(ev["reasons"]), re.I):
                findings.append(_finding(n(), "website", "Possible contribution of fragmented specifications (hypothesis)",
                                         "In this variant specification facts are written as prose rather than a labelled table, and the wrong fields are specification-like. One run cannot show the presentation caused the error.", "hypothesis", [{"note": "; ".join(ev["reasons"][:3])}],
                                         "Present the same specifications as a labelled table.", {"factor": "specs", "from": "fragmented", "to": "structured", "task": spec.task_id}))
        else:
            findings.append(_finding(n(), "undetermined", "The agent did not see information the task needs", "Required evidence never appeared in a page the agent was shown: " + "; ".join(ev["missing_evidence"][:3]) + ". This could reflect agent navigation strategy or how discoverable the information is on the site; one scan cannot distinguish them.", "observed",
                                     [{"note": m} for m in ev["missing_evidence"][:6]]))
    # 5. website-attributable observations (facts first, then hypotheses)
    detail_views = [j["step"] for j in journey if j["path"].startswith("/p/")]
    stock_task = "in stock" in spec.objective.lower()
    if stock_task and variant.factor("availability") == "detail" and detail_views:
        findings.append(_finding(n(), "website", "Stock status was only available on product pages in this variant",
                                 f"This task depends on stock. Listing and search pages in this variant show no stock cue, and the scan opened {len(set(detail_views))} product page(s) to learn availability. Whether that was avoidable effort for the agent is a hypothesis, not a measured effect.", "observed",
                                 [{"step": s, "path": next(j["path"] for j in journey if j["step"] == s)} for s in detail_views[:6]],
                                 "Show an In stock / Out of stock cue (and an in-stock filter) on listing cards. Task 007 found more requests and cost per run in the detail-only arm on a synthetic store, an exploratory result that does not transfer to other sites.",
                                 {"factor": "availability", "from": "detail", "to": "listing", "task": spec.task_id}))
    ref = reference_path_length(instance, variant)
    metrics = {"page_views": len(journey), "reference_page_views": ref, "reference_note": "reference = the scripted navigator's path; other valid paths exist, so exceeding it is not by itself a defect",
               "extra_page_views_vs_reference": (len(journey) - 1 - ref) if ref is not None else None, "visibility_gap_steps": gaps}
    return {"findings": findings, "metrics": metrics, "mode_notice": ("MOCK scan: the agent's decisions were scripted. These findings demonstrate the diagnostic mechanism and pipeline; they are not evidence about any model or website." if mode == "mock" else
            "Single live scan: findings are observations from one run, not validated effects."), "attribution_note": "Categories separate website, agent-reasoning, agent-tool-interface, infrastructure and security causes. 'observed' = measured fact; 'inferred' = follows by a stated rule; 'hypothesis' = unvalidated."}


def compare(a: dict, b: dict) -> dict:
    """Descriptive comparison of two private scan results of the same task (e.g. a baseline and a rescan with one factor changed)."""
    ta, tb = a["task"]["task_id"], b["task"]["task_id"]
    if ta != tb:
        raise ValueError("scans must be of the same task")
    fa, fb = a["variant"]["factors"], b["variant"]["factors"]
    changed = {k: [fa[k], fb[k]] for k in fa if fa[k] != fb.get(k)}
    ea, eb = a["evaluation"], b["evaluation"]
    metric = lambda path: [a["metrics"][path], b["metrics"][path]]
    delta = lambda k: round(b["metrics"][k] - a["metrics"][k], 6)
    caveats = ["Each side is a single scan; agent behaviour varies from run to run, so a difference here is not a validated effect of the changed factor."]
    if "mock" in (a["scan"]["mode"], b["scan"]["mode"]):
        caveats.append("At least one scan is a MOCK: scripted behaviour, not model evidence.")
    if len(changed) != 1:
        caveats.append("The scans differ in " + (f"{len(changed)} factors" if changed else "no factor") + "; a controlled comparison changes exactly one.")
    return {"task_id": ta, "baseline": {"variant": a["variant"]["id"], "mode": a["scan"]["mode"]}, "rescan": {"variant": b["variant"]["id"], "mode": b["scan"]["mode"]}, "factors_changed": changed,
            "outcome": {"passed": [ea["passed"], eb["passed"]], "evidence_backed": [ea["evidence_backed"], eb["evidence_backed"]]},
            "metrics": {k: {"baseline": a["metrics"][k], "rescan": b["metrics"][k], "delta": delta(k)} for k in ("model_requests", "page_views", "elapsed_seconds", "calculated_cost_usd")},
            "controlled": len(changed) == 1, "caveats": caveats}
