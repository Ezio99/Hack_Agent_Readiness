"""Render the Larkspur site from `data.py`. Variants: `original` (course cards show name, category and summary only; the fee, duration, level and seats
are on each course page) and `modified` (the same cards also state fee, duration, level and seats left: a listing-information change; nothing else
differs). `improved` applies every actionable recommendation from the Larkspur evaluations (see `improved.py`); `original` and `modified` are
unchanged, byte for byte, because recorded evaluations refer to their snapshot hashes. Plain, semantic HTML with one stylesheet; deterministic output."""
from __future__ import annotations

from functools import lru_cache
from html import escape as e

from ...investigate.inspect.crawl import Limits, MappingFetcher, crawl
from ...investigate.sitemodel.snapshot import Snapshot
from . import data as D

VARIANTS = ("original", "modified", "improved")
NAV = [("/courses", "Courses"), ("/enrolment-policy", "Enrolment and refunds"), ("/about", "About")]
CSS = """body{font:16px/1.5 system-ui,sans-serif;margin:0;color:#1d2433;background:#fbfaf7}header,main,footer{max-width:980px;margin:0 auto;padding:16px}
nav a{margin-right:16px}.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:16px;list-style:none;padding:0}
.card{background:#fff;border:1px solid #ddd;border-radius:8px;padding:14px}.pill{font-size:12px;background:#eef;padding:2px 8px;border-radius:10px}
dl.facts{display:grid;grid-template-columns:max-content 1fr;gap:6px 16px}dt{font-weight:600}table{border-collapse:collapse}td,th{border:1px solid #ccc;padding:6px}"""


def _page(title: str, body: str, current: str = "") -> str:
    nav = "".join(f'<a href="{href}"{" aria-current=\"page\"" if href == current else ""}>{e(label)}</a>' for href, label in NAV)
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><title>{e(title)} | {e(D.COLLEGE["name"])}</title>'
            f'<meta name="viewport" content="width=device-width, initial-scale=1"><link rel="stylesheet" href="/assets/site.css"></head><body>'
            f'<header><a href="/"><strong>{e(D.COLLEGE["name"])}</strong></a><nav aria-label="Main">{nav}</nav></header><main id="main">{body}</main>'
            f'<footer><p>{e(D.COLLEGE["phone"])} · {e(D.COLLEGE["email"])}</p></footer></body></html>')


def _card(c: D.Course, modified: bool) -> str:
    extra = (f'<p class="card-facts">Course fee {D.money(c.fee)} · Duration {D.weeks(c.weeks)} · Level {e(c.level)} · Seats left {c.seats_left}</p>' if modified else "")
    return (f'<li><article class="card"><span class="pill">{e(c.category)}</span><h2><a href="/courses/{c.slug}">{e(c.name)}</a></h2>'
            f'<p>{e(c.summary)}</p>{extra}</article></li>')


def pages(variant: str = "original") -> dict[str, str]:
    if variant not in VARIANTS:
        raise ValueError(f"unknown Larkspur variant {variant!r}")
    if variant == "improved":
        from . import improved
        return improved.pages()
    mod = variant == "modified"
    out = {"/": _page("Short courses", f'<h1>{e(D.COLLEGE["tagline"])}</h1><p>{len(D.COURSES)} courses this term across {len(D.CATEGORIES)} subject areas, '
                                       f'taught at our Northside and Riverside campuses.</p><p><a href="/courses">Browse all courses</a></p>'
                                       f'<h2>Subject areas</h2><ul>{"".join(f"<li>{e(cat)}</li>" for cat in D.CATEGORIES)}</ul>')}
    out["/courses"] = _page("All courses", f'<h1>All courses</h1><p>Every short course running this term.</p><ul class="cards">{"".join(_card(c, mod) for c in D.COURSES)}</ul>', "/courses")
    for c in D.COURSES:
        out[f"/courses/{c.slug}"] = _page(c.name, (
            f'<p><a href="/courses">All courses</a></p><h1>{e(c.name)}</h1><p>{e(c.summary)}</p>'
            f'<dl class="facts"><dt>Course fee</dt><dd>{D.money(c.fee)}</dd><dt>Duration</dt><dd>{D.weeks(c.weeks)}</dd><dt>Level</dt><dd>{e(c.level)}</dd>'
            f'<dt>Class day</dt><dd>{e(c.day)}</dd><dt>Seats left</dt><dd>{c.seats_left}</dd><dt>Campus</dt><dd>{e(c.campus)}</dd><dt>Materials</dt><dd>{e(c.materials)}</dd></dl>'
            f'<p>Concession card holders receive {D.CONCESSION} % off the course fee. See <a href="/enrolment-policy">enrolment and refunds</a>.</p>'), "/courses")
    rows = "".join(f"<tr><td>{e(w)}</td><td>{e(r)}</td></tr>" for w, r in D.REFUNDS)
    out["/enrolment-policy"] = _page("Enrolment and refunds", (
        f'<h1>Enrolment and refunds</h1><p>Enrol online or at either campus office. Places are confirmed when the full fee is paid.</p>'
        f'<h2>Refunds</h2><table><caption>Refunds and withdrawals</caption><thead><tr><th scope="col">When you withdraw</th><th scope="col">Refund</th></tr></thead><tbody>{rows}</tbody></table>'
        f'<h2>Concessions</h2><p>Concession card holders receive {D.CONCESSION} % off the course fee.</p>'), "/enrolment-policy")
    out["/about"] = _page("About", f'<h1>About {e(D.COLLEGE["name"])}</h1><p>A not-for-profit adult education centre in {e(D.COLLEGE["suburb"])}.</p>', "/about")
    return out


LIMITS = Limits(max_pages=60, max_depth=4, max_query_variants=2, max_assets=5, max_asset_bytes=50_000, max_total_asset_bytes=100_000)


@lru_cache(maxsize=None)
def snapshot(variant: str = "original") -> Snapshot:
    """Crawl the rendered variant with the pipeline's own crawler (offline), exactly as any other site is captured."""
    if variant == "improved":
        from . import improved
        return improved.snapshot()
    mapping = {path: html for path, html in pages(variant).items()}
    mapping["/assets/site.css"] = (200, "text/css", CSS.encode())
    return crawl(MappingFetcher(mapping), LIMITS)
