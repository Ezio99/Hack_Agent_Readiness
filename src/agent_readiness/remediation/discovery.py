"""Trace-driven discovery hook. Detectors read recorded agent journeys and emit CANDIDATE findings for friction patterns the recommendation library may not know yet.
A candidate carries evidence and, if it coincides with an observed website property, a link to it; it never carries a recommendation. Adding knowledge = adding a library
template for the pattern (or a new probe check), not editing the detectors."""
from __future__ import annotations

import re
from typing import Callable

from .execution import _detail_regex

Detector = Callable[[list[dict], str | None, list[dict]], list[dict]]
DETECTORS: list[Detector] = []


def detector(fn: Detector) -> Detector:
    DETECTORS.append(fn)
    return fn


@detector
def listing_detail_ping_pong(journey, product_template, findings):
    """list -> product -> list -> product ... at least three product visits that each return to the same list page."""
    rx = _detail_regex(product_template)
    if rx is None:
        return []
    steps = [(j["step"], j["path"] + ("?" + j["query"] if j.get("query") else ""), bool(rx.match(j["path"]))) for j in journey]
    returns = [steps[i + 2][0] for i in range(len(steps) - 2) if not steps[i][2] and steps[i + 1][2] and not steps[i + 2][2] and steps[i][1] == steps[i + 2][1]]
    if len(returns) < 2:
        return []
    linked = [f["fingerprint"] for f in findings if f["kind"] == "attribute_detail_only"]
    return [{"id": "candidate-list-detail-ping-pong", "category": "candidate_unexplained", "confidence": "observed_pattern", "title": "Repeated list -> product -> same list navigation",
             "summary": f"The agent returned to the same list page after {len(returns) + 1} product visits (steps {returns}). The cause is not determined from the trace alone.",
             "data": {"return_steps": returns}, "linked_website_findings": linked,
             "recommendation": None, "note": "No library recommendation exists for this pattern until a cause is established; "
                                             + ("it coincides with an observed detail-only attribute, which may explain it (hypothesis)." if linked else "no matching website property was observed.")}]


@detector
def repeated_product_page(journey, product_template, findings):
    rx = _detail_regex(product_template)
    if rx is None:
        return []
    counts: dict[str, list[int]] = {}
    for j in journey:
        if rx.match(j["path"]):
            counts.setdefault(j["path"], []).append(j["step"])
    rep = {p: s for p, s in counts.items() if len(s) >= 3}
    return [{"id": f"candidate-revisit-{re.sub(r'[^a-z0-9]+', '-', p)[:30]}", "category": "candidate_unexplained", "confidence": "observed_pattern", "title": "A product page was reopened three or more times",
             "summary": f"{p} was loaded in steps {s}.", "data": {"steps": s}, "linked_website_findings": [], "recommendation": None} for p, s in rep.items()]


def discover(scan: dict, product_template: str | None, findings: list[dict]) -> list[dict]:
    out = []
    for d in DETECTORS:
        out.extend(d(scan["journey"], product_template, findings))
    return out
