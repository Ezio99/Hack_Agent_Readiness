"""Agent-execution evidence from a recorded scan (private scan result). Kept strictly separate from website properties: these are observations of what an agent DID on the
audited site, with an independent evaluator verdict. They never become website findings by themselves; at most they are marked as corroborating an observed property
(an inference about intent, labelled `inferred`)."""
from __future__ import annotations

import re

from ..scanner.diagnostics import repeated_actions
from .library import objective_relevance


def _detail_regex(template: str | None):
    return re.compile("^" + re.escape(template).replace(r"\{\}", "[^/]+") + "$") if template else None


def execution_evidence(scan: dict, product_template: str | None, findings: list[dict], objective: str | None) -> dict:
    journey, ev, out, met = scan["journey"], scan["evaluation"], scan["outcome"], scan["metrics"]
    rx = _detail_regex(product_template)
    detail_steps = [j["step"] for j in journey if rx and rx.match(j["path"])]
    distinct = sorted({j["path"] for j in journey if rx and rx.match(j["path"])})
    items = [{"id": "outcome", "category": "task_outcome", "confidence": "observed", "title": "Independent evaluator verdict",
              "summary": ("PASS" if ev["passed"] else "FAIL") + (f"; evidence-backed: {ev['evidence_backed']}" if ev.get("evidence_backed") is not None else "") + f"; run status {out['run_status']}",
              "data": {"passed": ev["passed"], "evidence_backed": ev.get("evidence_backed"), "run_status": out["run_status"], "reasons": ev.get("reasons", [])[:4]}},
             {"id": "effort", "category": "agent_execution", "confidence": "observed", "title": "Effort spent",
              "summary": f"{met['model_requests']} model requests, {met['page_views']} page views, {met['elapsed_seconds']} s, calculated cost US${met['calculated_cost_usd']} ({scan['scan']['mode']} scan).",
              "data": {k: met[k] for k in ("model_requests", "page_views", "elapsed_seconds", "calculated_cost_usd")}},
             {"id": "product-page-visits", "category": "agent_execution", "confidence": "observed", "title": "Product pages opened",
              "summary": f"{len(distinct)} distinct product pages opened in {len(detail_steps)} steps.", "data": {"steps": detail_steps, "pages": distinct[:12]}}]
    gaps = (scan.get("diagnostics", {}).get("metrics", {}) or {}).get("visibility_gap_steps") or []
    if gaps:
        items.append({"id": "tool-visibility-gap", "category": "agent_tool_interface", "confidence": "observed", "title": "Tool output not visible to the model",
                      "summary": f"Link-bearing tool output was not shown to the model in steps {gaps}; this is not attributed to the website.", "data": {"steps": gaps}})
    for run in repeated_actions(journey):
        items.append({"id": f"repeated-action-{run[0]}", "category": "agent_execution", "confidence": "observed", "title": "Identical action repeated",
                      "summary": f"The same action was issued {len(run)} times in a row (steps {run[0]}-{run[-1]}).", "data": {"steps": run}})
    if out["run_status"] in ("infrastructure_error", "timeout", "request_limit", "estimated_cost_limit", "diagnostic_fidelity_violation", "model_output_error", "cancelled"):
        items.append({"id": "run-ended-early", "category": "infrastructure_or_limit", "confidence": "observed", "title": f"Run ended early: {out['run_status']}",
                      "summary": "Not attributed to the website.", "data": {"run_status": out["run_status"]}})
    corroborates = []
    for f in findings:
        if f["kind"] == "attribute_detail_only" and len(distinct) >= 2:
            corroborates.append({"finding": f["fingerprint"], "confidence": "inferred", "task_relevance": objective_relevance(f["attribute"], objective),
                                 "statement": (f"The agent opened {len(distinct)} product pages while the audited listing cards lack {f['attribute']}. This is consistent with per-product lookups of "
                                               f"{f['attribute']}, but the agent's intent was not observed and the opened pages may have had other purposes.")})
    return {"scan_mode": scan["scan"]["mode"], "model": scan["scan"]["model"], "profile": scan["scan"]["profile"], "task_id": scan["task"]["task_id"], "items": items, "corroborates": corroborates,
            "mode_notice": ("MOCK scan: the agent's decisions were scripted; this demonstrates the pipeline, not agent behaviour." if scan["scan"]["mode"] == "mock"
                            else "Single live scan: observations from one run, not a measured effect.")}
