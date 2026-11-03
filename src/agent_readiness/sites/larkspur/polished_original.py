"""The `polishedoriginal` Larkspur variant (shown to the audience as "Before"): the ORIGINAL site, visually redesigned, with Original's functionality
and agent-readiness limitations unchanged.

Built from `render.py`'s Original pages, NOT from `improved.py`: the same 18 pages and links, the same facts in the same places.
  - Course cards show subject, name and a one-line summary only; fee, duration, level, class day, seats left, campus and materials are on each
    course page (exactly as in Original).
  - No filter, browse pages, comparison table, structured data or redirects; no page or fact that Original lacks.
  - What changes is presentation only: the polished Larkspur identity (violet and sage, serif display type, logo and original SVG illustrations
    from `art.py`, the stylesheet of the polished redesign), layout, hierarchy and responsiveness.
Deterministic output; images are decorative (`alt=""`)."""
from __future__ import annotations

from functools import lru_cache
from html import escape as e

from ...investigate.inspect.crawl import Limits, MappingFetcher, crawl
from ...investigate.sitemodel.snapshot import Resource, Snapshot
from . import art
from . import data as D
from .polished import CSS as POLISHED_CSS

NAV = [("/courses", "Courses"), ("/enrolment-policy", "Enrolment and refunds"), ("/about", "About")]      # Original's navigation
CSS = POLISHED_CSS + """
.tiles.static .tile{cursor:default}.tiles.static .tile:hover{transform:none}
.cards.plain .card-body{padding-bottom:1.3rem}.course-lede{max-width:40rem}
.intro-band{display:grid;grid-template-columns:1fr 1fr;gap:1.25rem}.intro-band>div{background:#fff;border:1px solid var(--line);border-radius:var(--r);padding:1.25rem}
@media (max-width:820px){.intro-band{grid-template-columns:1fr}}"""


def _page(title: str, body: str, current: str = "") -> str:
    nav = "".join(f'<a href="{href}"{" aria-current=\"page\"" if href == current else ""}>{e(label)}</a>' for href, label in NAV)
    subjects = "".join(f"<li>{e(c)}</li>" for c in D.CATEGORIES)
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><title>{e(title)} | {e(D.COLLEGE["name"])}</title>'
            f'<meta name="viewport" content="width=device-width, initial-scale=1"><link rel="icon" href="/assets/img/logo.svg">'
            f'<link rel="stylesheet" href="/assets/site.css"></head><body><a class="skip" href="#main">Skip to content</a>'
            f'<div class="utility"><div class="wrap"><span>{e(D.COLLEGE["tagline"])}</span><span>{e(D.COLLEGE["phone"])} · {e(D.COLLEGE["email"])}</span></div></div>'
            f'<header class="site"><div class="wrap"><a class="brand" href="/"><img src="/assets/img/logo.svg" alt="" width="48" height="48">'
            f'<span><b>{e(D.COLLEGE["name"])}</b><small>{e(D.COLLEGE["suburb"])}</small></span></a><nav class="main" aria-label="Main">{nav}</nav></div></header>'
            f'<main id="main">{body}</main>'
            f'<footer class="site"><div class="wrap"><div class="cols"><div><h2>{e(D.COLLEGE["name"])}</h2><p>{e(D.COLLEGE["phone"])} · {e(D.COLLEGE["email"])}</p></div>'
            f'<div><h2>Subject areas</h2><ul>{subjects}</ul></div><div><h2>Visit</h2><ul><li><a href="/courses">Courses</a></li>'
            f'<li><a href="/enrolment-policy">Enrolment and refunds</a></li><li><a href="/about">About</a></li></ul></div></div>'
            f'<p class="fine">Larkspur Community College is a fictional college created for this demonstration.</p></div></footer></body></html>')


def _head(title: str, intro: str, crumbs: str = "") -> str:
    return f'<section class="page-head"><div class="wrap">{crumbs}<h1>{e(title)}</h1><p>{intro}</p></div></section>'


def _card(c: D.Course) -> str:
    """Original's card content (subject, name, summary), restyled. No course facts, exactly as in Original."""
    return (f'<li><article class="card"><div class="card-media"><img src="/assets/img/subject-{c.category.lower()}.svg" alt="" width="320" height="232" loading="lazy"></div>'
            f'<div class="card-body"><p class="subject">{e(c.category)}</p><h2><a href="/courses/{c.slug}">{e(c.name)}</a></h2><p class="summary">{e(c.summary)}</p></div></article></li>')


def pages() -> dict[str, str]:
    n = len(D.COURSES)
    tiles = "".join(f'<li><div class="tile"><img src="/assets/img/subject-{c.lower()}.svg" alt="" width="320" height="232"><span>{e(c)}</span></div></li>' for c in D.CATEGORIES)
    out = {"/": _page("Short courses", (
        f'<section class="hero"><div class="wrap"><div><span class="eyebrow">{e(D.COLLEGE["suburb"])}</span><h1>{e(D.COLLEGE["tagline"])}</h1>'
        f'<p class="lede">{n} courses this term across {len(D.CATEGORIES)} subject areas, taught at our Northside and Riverside campuses.</p>'
        f'<div class="actions"><a class="btn" href="/courses">Browse all courses</a></div></div>'
        f'<div class="hero-art"><img src="/assets/img/hero.svg" alt="" width="640" height="480"></div></div></section>'
        f'<section class="section"><div class="wrap"><div class="section-head"><div><span class="eyebrow">Subjects</span><h2>Subject areas</h2></div></div>'
        f'<ul class="tiles static">{tiles}</ul></div></section>'))}
    out["/courses"] = _page("All courses", _head("All courses", "Every short course running this term.")
                            + f'<div class="wrap section"><ul class="cards plain">{"".join(_card(c) for c in D.COURSES)}</ul></div>', "/courses")
    for c in D.COURSES:
        facts = (f'<dl class="facts"><dt>Course fee</dt><dd>{D.money(c.fee)}</dd><dt>Duration</dt><dd>{D.weeks(c.weeks)}</dd><dt>Level</dt><dd>{e(c.level)}</dd>'
                 f'<dt>Class day</dt><dd>{e(c.day)}</dd><dt>Seats left</dt><dd>{c.seats_left}</dd><dt>Campus</dt><dd>{e(c.campus)}</dd><dt>Materials</dt><dd>{e(c.materials)}</dd></dl>')
        out[f"/courses/{c.slug}"] = _page(c.name, (
            f'<section class="course-hero"><div class="wrap"><div><p class="crumbs"><a href="/courses">All courses</a></p><span class="eyebrow">{e(c.category)}</span>'
            f'<h1>{e(c.name)}</h1><p class="lede course-lede">{e(c.summary)}</p></div>'
            f'<img src="/assets/img/subject-{c.category.lower()}.svg" alt="" width="320" height="232"></div></section>'
            f'<div class="wrap course"><div><section class="prose"><h2>Course details</h2>{facts}</section></div>'
            f'<aside class="keyfacts" aria-label="Concessions"><p class="note">Concession card holders receive {D.CONCESSION} % off the course fee. See '
            f'<a href="/enrolment-policy">enrolment and refunds</a>.</p></aside></div>'), "/courses")
    rows = "".join(f"<tr><td>{e(w)}</td><td>{e(r)}</td></tr>" for w, r in D.REFUNDS)
    out["/enrolment-policy"] = _page("Enrolment and refunds", _head("Enrolment and refunds", "Enrol online or at either campus office. Places are confirmed when the full fee is paid.")
                                     + f'<div class="wrap section"><div class="prose"><h2>Refunds</h2><div class="table-wrap"><table><caption>Refunds and withdrawals</caption>'
                                       f'<thead><tr><th scope="col">When you withdraw</th><th scope="col">Refund</th></tr></thead><tbody>{rows}</tbody></table></div>'
                                       f'<h2 style="margin-top:1.5rem">Concessions</h2><p>Concession card holders receive {D.CONCESSION} % off the course fee.</p></div></div>',
                                     "/enrolment-policy")
    out["/about"] = _page("About", _head(f"About {D.COLLEGE['name']}", f"A not-for-profit adult education centre in {e(D.COLLEGE['suburb'])}.")
                          + '<div class="wrap section"><ul class="campuses"><li class="campus"><img src="/assets/img/campus-northside.svg" alt="" width="480" height="260"></li>'
                            '<li class="campus"><img src="/assets/img/campus-riverside.svg" alt="" width="480" height="260"></li></ul></div>', "/about")
    return out


LIMITS = Limits(max_pages=60, max_depth=4, max_query_variants=2, max_assets=12, max_asset_bytes=60_000, max_total_asset_bytes=300_000)


@lru_cache(maxsize=1)
def snapshot() -> Snapshot:
    """Crawl the rendered site with the pipeline's own crawler (offline), then add any image the crawler's asset limit skipped."""
    assets = {"/assets/site.css": CSS.encode(), **art.assets()}
    mapping: dict = dict(pages())
    mapping.update({p: (200, "text/css" if p.endswith(".css") else "image/svg+xml", b) for p, b in assets.items()})
    snap = crawl(MappingFetcher(mapping), LIMITS)
    res = dict(snap.resources)
    for path, body in sorted(assets.items()):
        if path not in res:
            res[path] = Resource(path, 200, "text/css" if path.endswith(".css") else "image/svg+xml", body)
    return Snapshot(res, snap.meta)
