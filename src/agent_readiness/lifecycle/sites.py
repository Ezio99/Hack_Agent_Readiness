"""Server-side website contexts for the product lifecycle (M8). The client selects a context by id; it never supplies a URL, catalogue, snapshot,
business context, persona, task, model setting or spending limit.

Onboarding a website (step 1 of the lifecycle) means: a frozen, content-hashed snapshot per variant, an independent oracle built from the site's
own source records, and a business context with customer personas and journeys. Only CONTROLLED sites have an oracle, so only they can be
evaluated deterministically. Both registered contexts are SYNTHETIC (illustrative assumptions for fictional businesses; labelled as such).
Onboarding a new website from a URL is not available in the web product (no crawl happens on request) and is shown as unavailable."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from ..framework.site import get

VARIANT_TEXT = {
    "larkspur": {"original": "Course cards show name, category and summary only; fee, duration, level and seats left are on each course page.",
                 "modified": "The same cards also state course fee, duration, level and seats left (one listing-information change).",
                 "improved": "Every recommendation applied: each card states fee, duration, level, class day, campus, seats left and materials; browse "
                             "pages by campus, day, level and subject; a working catalogue filter; a comparison table; schema.org course data; and "
                             "redirects for every dead end agents hit.",
                 "polished": "Earlier trial A (superseded): a visual redesign built on the Improved site, so it already had every agent-readiness "
                             "improvement (filter, browse pages, comparison table, structured data, redirects and every fact on every card).",
                 "polished2": "Earlier trial B (superseded): trial A plus the changes its live evaluation justified: every result list names all "
                              "matching courses before the first card, and listing pages use a compact header and slimmer card images.",
                 "polishedoriginal": "Before: the original college website, visually redesigned for people. Course cards show a name, subject and summary; "
                                     "every fee, class day, level, seat count and campus is on the course's own page.",
                 "modifiedpolished": "After: the same redesigned website with Agent Readiness's recommendations applied: every course card states its fee, "
                                     "duration, level, class day, campus, seats left and materials; course URLs that follow the course name lead to the "
                                     "course; and every course is described with schema.org structured data."},
    "ironbark": {"original": "The control hire site: deposit, minimum hire and delivery are stated on item pages only.",
                 "modified": "Listing cards also show refundable deposit, minimum hire and delivery (the owner-selected change used by the hosted evaluation)."},
}
HOSTED_NOTE = {"ironbark": "The hosted Ironbark evaluation (4 fixed tasks, paired Original/Modified) remains available in the evaluation workspace."}


def context_for(site_id: str) -> dict | None:
    if site_id == "larkspur":
        from ..research.taskplan.context import CONTEXT
        return json.loads(json.dumps(CONTEXT))
    if site_id == "ironbark":
        from ..evalruns.rehearse import FIXTURES
        return json.loads((Path(FIXTURES) / "ironbark-stage-a-v1.json").read_text())["context"]
    return None


@lru_cache(maxsize=8)
def _snapshot_sha(site_id: str, variant: str) -> str:
    return get(site_id).snapshot(variant).sha256


def site_view(site_id: str, *, with_hashes: bool = True) -> dict:
    s = get(site_id)
    if not s.controlled:
        raise KeyError(site_id)
    try:
        ctx = context_for(site_id)
    except (OSError, ValueError):
        ctx = None                                    # shown as "no business context onboarded"; never invented
    return {"id": s.id, "label": s.label, "domain": s.domain, "controlled": s.controlled, "oracle": True, "start_path": s.start_path,
            "listings": list(s.listings), "noun": list(s.noun) if s.noun else None,
            "variants": [{"name": v, "label": v.capitalize(), "description": VARIANT_TEXT.get(site_id, {}).get(v),
                          **({"snapshot_sha256": _snapshot_sha(site_id, v)} if with_hashes else {})} for v in s.registered],
            "context": ctx, "context_label": (ctx or {}).get("label"), "note": HOSTED_NOTE.get(site_id),
            "source": "frozen snapshots rendered from the site's own source data (no crawl on request)"}


def registered() -> list[str]:
    return ["larkspur", "ironbark"]


def onboarding() -> dict:
    return {"available": False, "reason": "uncontrolled_site_not_supported",
            "detail": "Evaluating a new website needs a frozen snapshot and an independent oracle from the site's own records, so that every task has a "
                      "verifiable answer. Onboarding from a URL is not available in the web product; choose a registered website context."}
