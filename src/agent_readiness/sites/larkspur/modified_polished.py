"""The `modifiedpolished` Larkspur variant (shown to the audience as "After"): the "Before" site (`polished_original.py`, the original college site
visually redesigned) with the agent-readiness recommendations of ITS OWN live evaluation applied, and the same visual design.

Evidence: live evaluation eval-ea13944e8ba5c08e8893426b2f8b1c8f (larkspur-core@v3, Before evaluated alone, 2026-11-04): 0/3 correct, 36 model
requests, 311 s, US$0.52. Agents opened course pages one by one because the cards state no facts, and ran out of requests. The report's
recommendations, applied here (nothing else changes; no filter, browse pages or comparison table are added):
  1. State every deciding fact on each course card, as labelled values (listing-fact-gap): course fee, seats left, class day and duration (the
     report links each to tasks 1-3), level (task 2's agent opened pages "to check level and meeting days"), campus and materials (page audit).
  2. Fix the dead end the agent hit: /courses/introduction-to-python returned 404 (it guessed the URL from the course name); every course URL
     that follows the course NAME now redirects to the course page.
  3. Describe each course with schema.org JSON-LD (no-structured-data), using the values the page shows, and list the courses on /courses.
Deterministic output; the facts in `data.py` are unchanged, so every frozen task keeps its expected answer."""
from __future__ import annotations

import json
import re
from functools import lru_cache
from html import escape as e

from ...investigate.inspect.crawl import Limits, MappingFetcher, crawl
from ...investigate.sitemodel.snapshot import Resource, Snapshot
from . import art
from . import data as D
from . import polished_original as B

CSS = B.CSS + """
dl.card-facts{display:grid;grid-template-columns:1fr 1fr;gap:.45rem .9rem;margin:.35rem 0 0;padding:.8rem 0 0;border-top:1px solid var(--line);font-size:.88rem}"""


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def _ld(obj) -> str:
    return '<script type="application/ld+json">' + json.dumps(obj, separators=(",", ":"), sort_keys=True).replace("</", "<\\/") + "</script>"


def _course_ld(c: D.Course) -> dict:
    return {"@context": "https://schema.org", "@type": "Course", "name": c.name, "description": c.summary, "url": f"/courses/{c.slug}", "about": c.category,
            "educationalLevel": c.level, "timeRequired": f"P{c.weeks}W", "provider": {"@type": "EducationalOrganization", "name": D.COLLEGE["name"]},
            "offers": {"@type": "Offer", "price": c.fee, "priceCurrency": "AUD", "availability": "https://schema.org/InStock" if c.seats_left else "https://schema.org/SoldOut",
                       "inventoryLevel": {"@type": "QuantitativeValue", "value": c.seats_left, "unitText": "seats left"}, "description": f"Materials: {c.materials}"},
            "hasCourseInstance": {"@type": "CourseInstance", "courseMode": "onsite", "location": {"@type": "Place", "name": f"{c.campus} campus"},
                                  "courseSchedule": {"@type": "Schedule", "byDay": f"https://schema.org/{c.day}", "repeatFrequency": "P1W", "repeatCount": c.weeks}}}


def _facts_dl(c: D.Course) -> str:
    rows = (("Course fee", D.money(c.fee)), ("Duration", D.weeks(c.weeks)), ("Level", c.level), ("Class day", c.day), ("Campus", c.campus),
            ("Seats left", str(c.seats_left)), ("Materials", c.materials))
    return '<dl class="card-facts">' + "".join(f"<div><dt>{k}</dt><dd>{e(v)}</dd></div>" for k, v in rows) + "</dl>"


def _card(c: D.Course) -> str:
    return (f'<li><article class="card"><div class="card-media"><img src="/assets/img/subject-{c.category.lower()}.svg" alt="" width="320" height="232" loading="lazy"></div>'
            f'<div class="card-body"><p class="subject">{e(c.category)}</p><h2><a href="/courses/{c.slug}">{e(c.name)}</a></h2><p class="summary">{e(c.summary)}</p>'
            f'{_facts_dl(c)}</div></article></li>')


def _with_head(html: str, head: str) -> str:
    return html.replace("</head>", head + "</head>", 1)


def pages() -> dict[str, str]:
    out = B.pages()
    items = _ld({"@context": "https://schema.org", "@type": "ItemList", "numberOfItems": len(D.COURSES),
                 "itemListElement": [{"@type": "ListItem", "position": i, "item": {k: v for k, v in _course_ld(c).items() if k != "@context"}}
                                     for i, c in enumerate(D.COURSES, 1)]})
    out["/courses"] = _with_head(B._page("All courses", B._head("All courses", "Every short course running this term, with its fee, duration, level, class day, campus, "
                                                                  "seats left and materials.")
                                         + f'<div class="wrap section"><ul class="cards">{"".join(_card(c) for c in D.COURSES)}</ul></div>', "/courses"), items)
    for c in D.COURSES:
        out[f"/courses/{c.slug}"] = _with_head(out[f"/courses/{c.slug}"], _ld(_course_ld(c)))
    return out


def redirects() -> dict[str, str]:
    """Course URLs that follow the course name (the observed dead end /courses/introduction-to-python is one) -> the course page."""
    return {f"/courses/{slugify(c.name)}": f"/courses/{c.slug}" for c in D.COURSES if slugify(c.name) != c.slug}


LIMITS = Limits(max_pages=60, max_depth=4, max_query_variants=2, max_assets=12, max_asset_bytes=60_000, max_total_asset_bytes=300_000)


@lru_cache(maxsize=1)
def snapshot() -> Snapshot:
    """Crawl with the pipeline's own crawler (offline); add the redirects (unlinked, so a crawler cannot find them) and any skipped image."""
    assets = {"/assets/site.css": CSS.encode(), **art.assets()}
    mapping: dict = dict(pages())
    mapping.update({p: (200, "text/css" if p.endswith(".css") else "image/svg+xml", b) for p, b in assets.items()})
    reds = redirects()
    mapping.update({p: ("redirect", t) for p, t in reds.items()})
    snap = crawl(MappingFetcher(mapping), LIMITS)
    res = dict(snap.resources)
    for path, body in sorted(assets.items()):
        if path not in res:
            res[path] = Resource(path, 200, "text/css" if path.endswith(".css") else "image/svg+xml", body)
    for path, target in sorted(reds.items()):
        if path not in res:
            res[path] = Resource(path, 301, "", b"", target)
    missing = sorted(set(reds.values()) - {p for p, r in res.items() if r.is_html})
    if missing:
        raise AssertionError(f"modifiedpolished Larkspur redirects to pages that are not captured: {missing}")
    return Snapshot(res, snap.meta)
