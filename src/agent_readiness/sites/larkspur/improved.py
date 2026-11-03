"""The `improved` Larkspur variant: every sensible, actionable recommendation from the Larkspur evaluations, applied to the same course records.

What changes against `original` (each item is a recommendation the product made, or a dead end seen in agent traces):
  1. Every course card states ALL the deciding facts: fee, duration, level, class day, campus, seats left and materials (listing-fact gaps).
  2. Browse pages that link from the catalogue: by campus, class day (and weekend / weekday), level and subject, plus one comparison table.
  3. A working catalogue filter: a plain GET form on /courses (level, campus, class day). Every form submission is a real, captured page, and the
     query strings agents type by hand (any order, any subset, lower case) redirect to the canonical result page.
  4. schema.org JSON-LD on every course page (Course + Offer + CourseInstance) and an ItemList on /courses, with the values the page shows.
  5. No dead ends: /courses/ and /courses/<slug>/ redirect; course URLs that follow the course NAME (e.g. /courses/introduction-to-python) and the
     URLs that returned 404 in recorded agent runs redirect to the real course page; /course and /course/<slug> redirect too.
  6. Breadcrumbs and "more like this" links on each course page.

The facts (`data.py`) are unchanged, so every frozen task keeps its expected answer. The jailed mirror serves only captured resources, so all the
extra routes are captured into the snapshot: crawled links through the pipeline's own crawler, and form results and redirects fetched through the
same offline fetcher and capture step (a crawler cannot discover a form submission or an unlinked redirect). Deterministic output."""
from __future__ import annotations

import json
import re
from functools import lru_cache
from html import escape as e
from itertools import combinations, permutations

from ...investigate.inspect.crawl import Limits, MappingFetcher, capture_html, crawl
from ...investigate.sitemodel.snapshot import Resource, Snapshot
from . import data as D

NAV = [("/courses", "All courses"), ("/courses/compare", "Compare courses"), ("/courses/campus", "Campuses"), ("/enrolment-policy", "Enrolment and refunds"),
       ("/about", "About")]
CSS = """body{font:16px/1.5 system-ui,sans-serif;margin:0;color:#1d2433;background:#fbfaf7}header,main,footer{max-width:1040px;margin:0 auto;padding:16px}
nav a{margin-right:16px}.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:16px;list-style:none;padding:0}
.card{background:#fff;border:1px solid #ddd;border-radius:8px;padding:14px}.pill{font-size:12px;background:#eef;padding:2px 8px;border-radius:10px}
.card-facts{font-size:14px;color:#33405a}dl.facts{display:grid;grid-template-columns:max-content 1fr;gap:6px 16px}dt{font-weight:600}
table{border-collapse:collapse}td,th{border:1px solid #ccc;padding:6px;text-align:left}form.filter{display:flex;flex-wrap:wrap;gap:12px;align-items:end;
background:#fff;border:1px solid #ddd;border-radius:8px;padding:12px}form.filter label{display:flex;flex-direction:column;font-size:14px}
.browse{display:flex;flex-wrap:wrap;gap:6px 20px;font-size:14px}nav.crumbs a{margin-right:4px}.crumbs{font-size:14px;margin-top:8px}"""

LEVELS = ("Beginner", "Intermediate", "Advanced")
CAMPUSES = ("Northside", "Riverside")
WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday")
WEEKEND = ("Saturday", "Sunday")
DAY_OPTIONS = ("Weekend", "Weekdays", *WEEKDAYS, *WEEKEND)          # form values; "Weekend" = Saturday or Sunday
# Course URLs that returned 404 in recorded agent runs (the product's dead-end findings), redirected to the course the visitor meant.
OBSERVED_404 = {"yoga-for-beginners": "beginners-yoga", "building-web-pages": "web-pages-from-scratch", "python": "intro-to-python",
                "intro-python": "intro-to-python", "meditation": "mindful-meditation", "pottery": "wheel-thrown-pottery"}
FILTER_KEYS = ("level", "campus", "day")


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def _day_matches(course: D.Course, day: str) -> bool:
    return (not day or course.day == day or (day == "Weekend" and course.day in WEEKEND) or (day == "Weekdays" and course.day in WEEKDAYS))


def matching(level: str = "", campus: str = "", day: str = "", category: str = "") -> list[D.Course]:
    return [c for c in D.COURSES if (not level or c.level == level) and (not campus or c.campus == campus) and _day_matches(c, day)
            and (not category or c.category == category)]


# ------------------------------------------------------------------------------------------------------------------------------- building blocks
def _ld(obj) -> str:
    return '<script type="application/ld+json">' + json.dumps(obj, separators=(",", ":"), sort_keys=True).replace("</", "<\\/") + "</script>"


def _course_ld(c: D.Course) -> dict:
    return {"@context": "https://schema.org", "@type": "Course", "name": c.name, "description": c.summary, "url": f"/courses/{c.slug}", "about": c.category,
            "educationalLevel": c.level, "timeRequired": f"P{c.weeks}W",
            "provider": {"@type": "EducationalOrganization", "name": D.COLLEGE["name"]},
            "offers": {"@type": "Offer", "price": c.fee, "priceCurrency": "AUD", "category": "Course fee",
                       "availability": "https://schema.org/InStock" if c.seats_left else "https://schema.org/SoldOut",
                       "inventoryLevel": {"@type": "QuantitativeValue", "value": c.seats_left, "unitText": "seats left"},
                       "description": f"Materials: {c.materials}"},
            "hasCourseInstance": {"@type": "CourseInstance", "courseMode": "onsite", "location": {"@type": "Place", "name": f"{c.campus} campus"},
                                  "courseSchedule": {"@type": "Schedule", "byDay": f"https://schema.org/{c.day}", "repeatFrequency": "P1W", "repeatCount": c.weeks}}}


def _page(title: str, body: str, current: str = "", head: str = "") -> str:
    nav = "".join(f'<a href="{href}"{" aria-current=\"page\"" if href == current else ""}>{e(label)}</a>' for href, label in NAV)
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><title>{e(title)} | {e(D.COLLEGE["name"])}</title>'
            f'<meta name="viewport" content="width=device-width, initial-scale=1"><link rel="stylesheet" href="/assets/site.css">{head}</head><body>'
            f'<header><a href="/"><strong>{e(D.COLLEGE["name"])}</strong></a><nav aria-label="Main">{nav}</nav></header><main id="main">{body}</main>'
            f'<footer><p>{e(D.COLLEGE["phone"])} · {e(D.COLLEGE["email"])}</p></footer></body></html>')


def _facts_line(c: D.Course) -> str:
    return (f'Course fee {D.money(c.fee)} · Duration {D.weeks(c.weeks)} · Level {e(c.level)} · Class day {e(c.day)} · Campus {e(c.campus)} · '
            f'Seats left {c.seats_left} · Materials {e(c.materials)}')


def _card(c: D.Course) -> str:
    return (f'<li><article class="card"><span class="pill">{e(c.category)}</span><h2><a href="/courses/{c.slug}">{e(c.name)}</a></h2>'
            f'<p>{e(c.summary)}</p><p class="card-facts">{_facts_line(c)}</p></article></li>')


def _cards(courses: list[D.Course]) -> str:
    if not courses:
        return '<p role="status">No courses match. <a href="/courses">Show all courses</a>.</p>'
    return f'<p role="status">{len(courses)} course{"" if len(courses) == 1 else "s"} found.</p><ul class="cards">{"".join(_card(c) for c in courses)}</ul>'


def _browse() -> str:
    def group(label, items):
        return f'<p class="browse"><strong>{e(label)}:</strong> ' + " ".join(f'<a href="{h}">{e(t)}</a>' for h, t in items) + "</p>"
    return ('<section aria-labelledby="browse"><h2 id="browse">Browse courses</h2>'
            + group("Campus", [(f"/courses/campus/{slugify(c)}", c) for c in CAMPUSES])
            + group("Class day", [(f"/courses/day/{slugify(d)}", d) for d in DAY_OPTIONS])
            + group("Level", [(f"/courses/level/{slugify(l)}", l) for l in LEVELS])
            + group("Subject", [(f"/courses/category/{slugify(c)}", c) for c in D.CATEGORIES])
            + '<p><a href="/courses/compare">Compare every course in one table</a></p></section>')


def _form(level: str = "", campus: str = "", day: str = "") -> str:
    def select(name, label, options, chosen, any_label):
        opts = f'<option value=""{" selected" if not chosen else ""}>{e(any_label)}</option>' + "".join(
            f'<option value="{e(o)}"{" selected" if o == chosen else ""}>{e(o)}</option>' for o in options)
        return f'<label>{e(label)}<select name="{name}">{opts}</select></label>'
    return ('<form class="filter" method="get" action="/courses" role="search" aria-label="Filter courses">'
            + select("level", "Level", LEVELS, level, "Any level") + select("campus", "Campus", CAMPUSES, campus, "Any campus")
            + select("day", "Class day", DAY_OPTIONS, day, "Any day") + '<button type="submit">Show courses</button></form>')


def _itemlist(courses: list[D.Course]) -> str:
    return _ld({"@context": "https://schema.org", "@type": "ItemList", "numberOfItems": len(courses),
                "itemListElement": [{"@type": "ListItem", "position": i, "item": {k: v for k, v in _course_ld(c).items() if k != "@context"}}
                                    for i, c in enumerate(courses, 1)]})


def _listing(title: str, intro: str, courses: list[D.Course], *, form: tuple[str, str, str] | None = None, crumbs: str = "", current: str = "") -> str:
    body = (crumbs + f"<h1>{e(title)}</h1><p>{intro}</p>" + (_form(*form) if form is not None else "") + _cards(courses) + _browse())
    return _page(title, body, current, head=_itemlist(courses))


def _crumbs(*links: tuple[str, str]) -> str:
    return '<nav class="crumbs" aria-label="Breadcrumb"><a href="/">Home</a> › ' + " › ".join(f'<a href="{h}">{e(t)}</a>' for h, t in links) + "</nav>"


def query(level: str = "", campus: str = "", day: str = "") -> str:
    """The exact query string a browser sends when the filter form is submitted (field order, empty values kept)."""
    return f"level={level}&campus={campus}&day={day}"


# ------------------------------------------------------------------------------------------------------------------------------- pages
def pages() -> dict[str, str]:
    n = len(D.COURSES)
    out = {"/": _page("Short courses", (
        f'<h1>{e(D.COLLEGE["tagline"])}</h1><p>{n} courses this term across {len(D.CATEGORIES)} subject areas, taught at our Northside and Riverside '
        f'campuses. Every course lists its fee, duration, level, class day, campus, seats left and materials up front.</p>'
        f'<p><a href="/courses">Browse all courses</a> · <a href="/courses/compare">Compare every course in one table</a></p>'
        + _form() + _browse()), head=_ld({"@context": "https://schema.org", "@type": "EducationalOrganization", "name": D.COLLEGE["name"],
                                         "telephone": D.COLLEGE["phone"], "email": D.COLLEGE["email"]}))}
    out["/courses"] = _listing("All courses", f"Every short course running this term ({n}). Filter by level, campus or class day, or browse below.",
                               D.COURSES, form=("", "", ""), current="/courses")
    for lv in ("", *LEVELS):
        for cp in ("", *CAMPUSES):
            for dy in ("", *DAY_OPTIONS):
                chosen = [x for x in (lv, cp and f"{cp} campus", dy and ("Weekdays" if dy == "Weekdays" else dy)) if x]
                title = "Courses: " + " · ".join(chosen) if chosen else "All courses"
                out[f"/courses?{query(lv, cp, dy)}"] = _listing(title, "Filtered from all courses. Change the filters or browse below.",
                                                                matching(lv, cp, dy), form=(lv, cp, dy), crumbs=_crumbs(("/courses", "All courses")))
    # browse pages (crawlable, linked from every listing)
    out["/courses/campus"] = _page("Campuses", _crumbs(("/courses", "All courses")) + "<h1>Campuses</h1><ul>" + "".join(
        f'<li><a href="/courses/campus/{slugify(c)}">{e(c)} campus</a> ({len(matching(campus=c))} courses)</li>' for c in CAMPUSES) + "</ul>", "/courses/campus")
    out["/courses/day"] = _page("Class days", _crumbs(("/courses", "All courses")) + "<h1>Class days</h1><ul>" + "".join(
        f'<li><a href="/courses/day/{slugify(d)}">{e(d)}</a> ({len(matching(day=d))} courses)</li>' for d in DAY_OPTIONS) + "</ul>")
    out["/courses/level"] = _page("Levels", _crumbs(("/courses", "All courses")) + "<h1>Levels</h1><ul>" + "".join(
        f'<li><a href="/courses/level/{slugify(l)}">{e(l)}</a> ({len(matching(level=l))} courses)</li>' for l in LEVELS) + "</ul>")
    out["/courses/category"] = _page("Subjects", _crumbs(("/courses", "All courses")) + "<h1>Subjects</h1><ul>" + "".join(
        f'<li><a href="/courses/category/{slugify(c)}">{e(c)}</a> ({len(matching(category=c))} courses)</li>' for c in D.CATEGORIES) + "</ul>")
    up = lambda h, t: _crumbs(("/courses", "All courses"), (h, t))
    for c in CAMPUSES:
        out[f"/courses/campus/{slugify(c)}"] = _listing(f"Courses at {c} campus", f"All courses taught at our {e(c)} campus.", matching(campus=c),
                                                        crumbs=up("/courses/campus", "Campuses"))
    for d in DAY_OPTIONS:
        what = {"Weekend": "on Saturday or Sunday", "Weekdays": "Monday to Friday"}.get(d, f"on {d}")
        out[f"/courses/day/{slugify(d)}"] = _listing(f"{d} courses", f"Courses with classes {e(what)}.", matching(day=d), crumbs=up("/courses/day", "Class days"))
    for lv in LEVELS:
        out[f"/courses/level/{slugify(lv)}"] = _listing(f"{lv} courses", f"All {e(lv.lower())} courses.", matching(level=lv), crumbs=up("/courses/level", "Levels"))
    for cat in D.CATEGORIES:
        out[f"/courses/category/{slugify(cat)}"] = _listing(f"{cat} courses", f"All {e(cat)} courses.", matching(category=cat),
                                                            crumbs=up("/courses/category", "Subjects"))
    head = "".join(f'<th scope="col">{h}</th>' for h in ("Course", "Subject", "Course fee", "Duration", "Level", "Class day", "Campus", "Seats left", "Materials"))
    rows = "".join(f'<tr><th scope="row"><a href="/courses/{c.slug}">{e(c.name)}</a></th><td>{e(c.category)}</td><td>{D.money(c.fee)}</td>'
                   f'<td>{D.weeks(c.weeks)}</td><td>{e(c.level)}</td><td>{e(c.day)}</td><td>{e(c.campus)}</td><td>{c.seats_left}</td><td>{e(c.materials)}</td></tr>'
                   for c in sorted(D.COURSES, key=lambda c: (c.fee, c.name)))
    out["/courses/compare"] = _page("Compare courses", _crumbs(("/courses", "All courses")) + (
        f'<h1>Compare courses</h1><p>All {n} courses, cheapest first.</p><table><caption>Every course this term</caption><thead><tr>{head}</tr></thead>'
        f'<tbody>{rows}</tbody></table>'), "/courses/compare")
    for c in D.COURSES:
        cat = f"/courses/category/{slugify(c.category)}"
        more = (f'<h2>More like this</h2><p class="browse"><a href="{cat}">More {e(c.category)} courses</a> <a href="/courses/campus/{slugify(c.campus)}">More at '
                f'{e(c.campus)} campus</a> <a href="/courses/day/{slugify(c.day)}">More {e(c.day)} courses</a> <a href="/courses/level/{slugify(c.level)}">More '
                f'{e(c.level)} courses</a></p>')
        out[f"/courses/{c.slug}"] = _page(c.name, (
            _crumbs(("/courses", "All courses"), (cat, c.category)) + f'<h1>{e(c.name)}</h1><p>{e(c.summary)}</p>'
            f'<dl class="facts"><dt>Course fee</dt><dd>{D.money(c.fee)}</dd><dt>Duration</dt><dd>{D.weeks(c.weeks)}</dd><dt>Level</dt><dd>{e(c.level)}</dd>'
            f'<dt>Class day</dt><dd>{e(c.day)}</dd><dt>Seats left</dt><dd>{c.seats_left}</dd><dt>Campus</dt><dd>{e(c.campus)}</dd><dt>Materials</dt><dd>{e(c.materials)}</dd></dl>'
            f'<p>Concession card holders receive {D.CONCESSION} % off the course fee. See <a href="/enrolment-policy">enrolment and refunds</a>.</p>' + more),
            "/courses", head=_ld(_course_ld(c)))
    rows = "".join(f"<tr><td>{e(w)}</td><td>{e(r)}</td></tr>" for w, r in D.REFUNDS)
    out["/enrolment-policy"] = _page("Enrolment and refunds", (
        f'<h1>Enrolment and refunds</h1><p>Enrol online or at either campus office. Places are confirmed when the full fee is paid.</p>'
        f'<h2>Refunds</h2><table><caption>Refunds and withdrawals</caption><thead><tr><th scope="col">When you withdraw</th><th scope="col">Refund</th></tr></thead><tbody>{rows}</tbody></table>'
        f'<h2>Concessions</h2><p>Concession card holders receive {D.CONCESSION} % off the course fee.</p>'), "/enrolment-policy")
    out["/about"] = _page("About", f'<h1>About {e(D.COLLEGE["name"])}</h1><p>A not-for-profit adult education centre in {e(D.COLLEGE["suburb"])}, with '
                                   f'campuses at Northside and Riverside. <a href="/courses/campus">Courses by campus</a>.</p>', "/about")
    return out


def redirects() -> dict[str, str]:
    """Every redirect the improved site serves: {path: target}. Targets are captured pages."""
    out = {"/courses/": "/courses", "/course": "/courses", "/course/": "/courses", "/catalogue": "/courses", "/courses/all": "/courses"}
    for c in D.COURSES:
        out[f"/courses/{c.slug}/"] = f"/courses/{c.slug}"
        out[f"/course/{c.slug}"] = f"/courses/{c.slug}"
        if slugify(c.name) != c.slug:
            out[f"/courses/{slugify(c.name)}"] = f"/courses/{c.slug}"
    out.update({f"/courses/{alias}": f"/courses/{slug}" for alias, slug in OBSERVED_404.items()})
    for sub in ("campus", "day", "level", "category"):
        out[f"/courses/{sub}/"] = f"/courses/{sub}"
    # hand-typed filter URLs: any subset of level/campus/day in any order, original or lower case -> the canonical form result
    values = {"level": LEVELS, "campus": CAMPUSES, "day": DAY_OPTIONS}
    for k in range(1, 4):
        for keys in combinations(FILTER_KEYS, k):
            for combo in _product([values[key] for key in keys]):
                chosen = dict(zip(keys, combo))
                target = f"/courses?{query(chosen.get('level', ''), chosen.get('campus', ''), chosen.get('day', ''))}"
                for order in permutations(keys):
                    for case in (str, str.lower):
                        q = "&".join(f"{key}={case(chosen[key])}" for key in order)
                        if f"/courses?{q}" != target:
                            out[f"/courses?{q}"] = target
    return out


def _product(lists):
    if not lists:
        yield ()
        return
    for head in lists[0]:
        for rest in _product(lists[1:]):
            yield (head, *rest)


LIMITS = Limits(max_pages=120, max_depth=4, max_query_variants=2, max_assets=5, max_asset_bytes=50_000, max_total_asset_bytes=100_000)


@lru_cache(maxsize=1)
def snapshot() -> Snapshot:
    """Crawl the rendered site with the pipeline's own crawler, then capture what a crawler cannot discover (form results and redirects) through the
    same offline fetcher and capture step. Any redirect must land on a captured page (checked)."""
    rendered = pages()
    mapping: dict = {path: html for path, html in rendered.items()}
    mapping["/assets/site.css"] = (200, "text/css", CSS.encode())
    reds = redirects()
    mapping.update({p: ("redirect", t) for p, t in reds.items()})
    snap = crawl(MappingFetcher(mapping), LIMITS)
    res = dict(snap.resources)
    fetcher = MappingFetcher(mapping)
    for path in sorted(set(rendered) - set(res)):
        r = fetcher.get(fetcher.origin + path)
        body, _ = capture_html(r.body.decode("utf-8"), path)
        res[path] = Resource(path, 200, "text/html; charset=utf-8", body)
    for path, target in sorted(reds.items()):
        if path not in res:
            res[path] = Resource(path, 301, "", b"", target)
    missing = sorted({t for t in reds.values()} - {p for p, r in res.items() if r.is_html})
    if missing:
        raise AssertionError(f"improved Larkspur redirects to pages that are not captured: {missing[:5]}")
    return Snapshot(res, {**snap.meta, "pages": sum(1 for r in res.values() if r.is_html), "captured_beyond_crawl": {
        "form_results_and_unlinked_pages": len(set(rendered) - set(snap.resources)), "redirects": sum(1 for r in res.values() if r.location)}})
