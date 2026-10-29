"""Audit report assembly, re-audit lifecycle and measured-effect attachment.

Report sections are kept apart on purpose (acceptance criterion: do not blur them):
  website_observations   facts measured by the probe (counts, cues, filters), with evidence
  findings               conclusions derived by fixed rules from those facts (kind:attribute fingerprints)
  agent_execution        what an agent did in a recorded scan + independent verdict (optional); never converted into website findings
  discovery_candidates   trace-driven candidate patterns with no recommendation
  recommendations        PROPOSED interventions selected from the library by the findings; status `proposed`, validation `unvalidated`
  lifecycle              (re-audit only) per previous finding: resolved / persisting / indeterminate, plus new findings; "resolved" = property no longer observed, NOT "effect proven"
  measured_effects       empty unless a controlled experiment's summary is attached with provenance
No input names a variant, an experimental arm or an expected outcome."""
from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime, timezone

from . import discovery, library
from .execution import execution_evidence
from .findings import attribute_stats, derive_findings
from .probe import SiteObservations

SCHEMA = "remediation-audit-v1"
TAXONOMY = {
    "website_observations": "Facts measured on the site by the probe.", "findings": "Rule-derived conclusions about website properties, each with evidence.",
    "agent_execution": "What an agent did in a recorded scan and the independent evaluator's verdict; not a website finding.",
    "recommendations": "Proposed interventions, selected by observed findings; unvalidated until measured.",
    "lifecycle": "Whether a previously observed property is still observed after a change; resolution is not an effect measurement.",
    "measured_effects": "Controlled-experiment results (n, metrics, intervals) with provenance; empty unless supplied.",
}


def _redact(text: str, origin: str) -> str:
    return text.replace(origin, "<target>")


def _relativize(value, origin: str):
    """Evidence URLs are reported relative to the audited site: the service never discloses the address it fetched from."""
    if isinstance(value, str):
        return (value[len(origin):] or "/") if value.startswith(origin) else value.replace(origin, "<target>")
    if isinstance(value, list):
        return [_relativize(v, origin) for v in value]
    if isinstance(value, dict):
        return {k: _relativize(v, origin) for k, v in value.items()}
    return value


def _id(origin: str, findings: list[dict]) -> str:
    return hashlib.sha256(json.dumps([origin, sorted(f["fingerprint"] for f in findings), datetime.now(timezone.utc).isoformat()]).encode()).hexdigest()[:12]


def build_report(obs: SiteObservations, *, objective: str | None = None, scan: dict | None = None, previous: dict | None = None, target: str | None = None) -> dict:
    findings = derive_findings(obs)
    recs = library.select(findings, objective)
    problems = [f for f in findings if f["category"] == "website_property"]
    report = {
        "schema": SCHEMA, "audit_id": _id(obs.origin, findings), "created_at": datetime.now(timezone.utc).isoformat(), "target": target or obs.origin,
        "objective": objective, "taxonomy": TAXONOMY,
        "probe": {"pages_fetched": obs.pages_fetched, "listing_pages": len(obs.listing_pages), "product_template": obs.product_template, "limits": obs.limits, "errors": [_redact(e, obs.origin) for e in obs.errors[:5]]},
        "website_observations": {"attributes": attribute_stats(obs), "filters": [{"listing_url": f.listing_url, "controls": f.controls[:10], "attribute_filters": f.attribute_filters} for f in obs.filters if f.controls][:4]},
        "findings": findings, "recommendations": recs, "agent_execution": None, "discovery_candidates": [], "lifecycle": None, "measured_effects": {"status": "not_measured", "effects": []},
        "summary": {"problems": len(problems), "recommendations": len(recs), "problem_fingerprints": [f["fingerprint"] for f in problems]},
        "disclaimer": "Findings describe what the probe observed. Recommendations are proposals; none is claimed to improve agent outcomes until measured_effects says so.",
    }
    report = _relativize(report, obs.origin)
    report["target"] = target or obs.origin               # the id of a registered target, or (CLI, operator's own site) the audited origin
    if scan is not None:
        report["agent_execution"] = execution_evidence(scan, obs.product_template, findings, objective)
        report["discovery_candidates"] = discovery.discover(scan, obs.product_template, findings)
    if previous is not None:
        report["lifecycle"] = lifecycle(previous, report)
        by_status = {item["fingerprint"]: item["status"] for item in report["lifecycle"]["items"]}
        for r in report["recommendations"]:
            r["history"] = "previously proposed and the property is still observed" if any(by_status.get(fp) == "persisting" for fp in r["addresses"]) else "new in this audit"
    return report


def lifecycle(previous: dict, current: dict) -> dict:
    """Compare two audit REPORTS by finding fingerprint. Uses nothing but what the two probes observed."""
    cur = {f["fingerprint"]: f for f in current["findings"]}
    items = []
    for f in previous["findings"]:
        if f["category"] != "website_property":
            continue
        fp, attr = f["fingerprint"], f["attribute"]
        if fp in cur:
            status, evidence = "persisting", cur[fp]["evidence"][:3]
        elif f["kind"] == "attribute_detail_only" and f"attribute_partial_on_cards:{attr}" in cur:
            status, evidence = "partially_resolved", cur[f"attribute_partial_on_cards:{attr}"]["evidence"][:3]
        elif (resolved_by := {"attribute_detail_only": f"attribute_on_cards:{attr}", "filter_absent": f"filter_present:{attr}"}.get(f["kind"])) in cur:
            status, evidence = "resolved", cur[resolved_by]["evidence"][:3]
        else:
            status, evidence = "indeterminate", []
        items.append({"fingerprint": fp, "attribute": attr, "status": status, "previous_summary": f["summary"],
                      "current_summary": (cur.get(fp) or cur.get(f"attribute_partial_on_cards:{attr}" if status == "partially_resolved" else resolved_by if status == "resolved" else "") or {}).get("summary", "not observed (probe coverage insufficient or attribute no longer visible anywhere)"),
                      "evidence": evidence})
    prev_fps = {f["fingerprint"] for f in previous["findings"]}
    new = [f["fingerprint"] for f in current["findings"] if f["category"] == "website_property" and f["fingerprint"] not in prev_fps]
    return {"previous_audit_id": previous["audit_id"], "items": items, "new_findings": new,
            "statement": "Resolution means the property is no longer observed by the probe. It does not show that agent outcomes improved; see measured_effects.",
            "resolved": sum(i["status"] == "resolved" for i in items), "persisting": sum(i["status"] == "persisting" for i in items)}


def report_sha256(report: dict) -> str:
    return hashlib.sha256(json.dumps(report, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def attach_measured_effects(report: dict, experiment: dict) -> dict:
    """Return a DERIVED view of `report` with a controlled experiment's summary attached. The original report is never modified and the recommendation's original
    `validation` ("unvalidated" as issued) is never rewritten: the measurement appears as `measured_validation` plus the effect record, which must reference the report's own
    audit id and a recommendation id it contains. Required keys: mode (must be 'live'), experiment_id, audit_id, recommendation_id, addresses, n_pairs, metrics, verdict (supports | not_supported | inconclusive)."""
    for key in ("experiment_id", "audit_id", "recommendation_id", "addresses", "n_pairs", "metrics", "verdict"):
        if key not in experiment:
            raise ValueError(f"experiment summary lacks {key!r}")
    if experiment.get("mode") != "live":
        raise ValueError("only LIVE experiment results are measured effects; mock / dry-run output must never be attached")
    if experiment["verdict"] not in ("supports", "not_supported", "inconclusive"):
        raise ValueError("verdict must be supports, not_supported or inconclusive")
    if experiment["audit_id"] != report["audit_id"] or experiment["recommendation_id"] not in {r["id"] for r in report["recommendations"]}:
        raise ValueError("the experiment does not reference this report's audit id and one of its recommendation ids")
    view = copy.deepcopy(report)
    view["original_report_sha256"] = report_sha256(report)
    view["measured_effects"] = {"status": "measured", "effects": [{**experiment, "provenance": "controlled experiment summary supplied by the experiment analysis; not produced by the audit"}]}
    for r in view["recommendations"]:
        if r["id"] == experiment["recommendation_id"]:
            r["measured_validation"] = f"measured_{experiment['verdict']}"
    return view
