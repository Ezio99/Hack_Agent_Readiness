"""The `polished` Larkspur variant (Polished v1): a human-centred visual redesign of the same college, built on Improved's information architecture.

What changes against `improved` (presentation only; the facts in `data.py` are unchanged, so every frozen task keeps its expected answer):
  1. A distinct Larkspur identity: violet and sage on warm paper, serif display headings, a larkspur logo and original SVG illustrations (hero,
     one per subject, one per campus). Images are decorative (`alt=""`); every fact is real text.
  2. Layout and hierarchy: a utility bar, a branded header, a hero with a course finder, subject tiles, campus cards, "filling fast" courses, an
     enrolment explainer and a full footer; listings use a filter panel beside a card grid; course pages lead with a key-facts panel and an
     enrolment call to action.
  3. Cards keep every deciding fact as a labelled list (Course fee, Duration, Level, Class day, Campus, Seats left, Materials) and add a seats badge.
  4. Responsive: the grid, filter panel, header and comparison table adapt from 360 px to wide screens; no script (the capture removes scripts).

Kept from `improved` because it serves visitors and agents alike: the GET filter (every submission captured), browse pages by campus, class day,
level and subject, the comparison table, schema.org JSON-LD and every redirect. `original`, `modified` and `improved` are not touched; this module
only reads their shared helpers. Deterministic output."""
from __future__ import annotations

from functools import lru_cache
from html import escape as e

from ...investigate.inspect.crawl import Limits, MappingFetcher, capture_html, crawl
from ...investigate.sitemodel.snapshot import Resource, Snapshot
from . import art
from . import data as D
from .improved import CAMPUSES, DAY_OPTIONS, LEVELS, _course_ld, _ld, matching, query, redirects, slugify

NAV = [("/courses", "All courses"), ("/courses/compare", "Compare courses"), ("/courses/campus", "Campuses"), ("/enrolment-policy", "Enrolment and refunds"),
       ("/about", "About")]

CSS = """:root{--ink:#221d3a;--ink2:#4a4466;--muted:#615b7a;--line:#e6e0d4;--paper:#fffdf9;--cream:#f7f3ea;--violet:#5a43a6;--violet-d:#3a2a78;
--violet-l:#ece6fb;--sage:#7fa383;--sage-d:#3f6647;--gold:#e7a93c;--ok:#1f6e46;--ok-bg:#e3f2e8;--warn:#8a4b00;--warn-bg:#fdf0d8;--bad:#9c2a2a;--bad-bg:#fbe4e2;
--r:18px;--shadow:0 1px 2px rgba(34,29,58,.06),0 10px 30px rgba(34,29,58,.08);--serif:"Iowan Old Style","Palatino Linotype",Palatino,"Book Antiqua",Georgia,serif}
*{box-sizing:border-box}html{scroll-behavior:smooth}
body{margin:0;background:var(--cream);color:var(--ink);font:16px/1.6 system-ui,-apple-system,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif;-webkit-font-smoothing:antialiased}
img{max-width:100%;height:auto;display:block}a{color:var(--violet-d);text-underline-offset:3px}a:hover{color:var(--violet)}
h1,h2,h3{font-family:var(--serif);font-weight:700;line-height:1.12;letter-spacing:-.01em;margin:0 0 .6rem;color:var(--ink)}
h1{font-size:clamp(2.1rem,5vw,3.4rem)}h2{font-size:clamp(1.45rem,2.8vw,2rem)}h3{font-size:1.2rem}p{margin:0 0 1rem}
.wrap{max-width:1200px;margin:0 auto;padding:0 1.25rem}
.skip{position:absolute;left:-9999px}.skip:focus{left:1rem;top:1rem;background:#fff;padding:.6rem 1rem;z-index:50;border-radius:10px}
:focus-visible{outline:3px solid var(--gold);outline-offset:2px;border-radius:6px}
/* header */
.utility{background:var(--violet-d);color:#e4defa;font-size:.85rem}.utility .wrap{display:flex;justify-content:space-between;gap:.5rem 1.5rem;flex-wrap:wrap;padding-top:.45rem;padding-bottom:.45rem}
.utility a{color:#fff;font-weight:600;text-decoration:none}
header.site{background:var(--paper);border-bottom:1px solid var(--line);position:relative;z-index:5}
header.site .wrap{display:flex;align-items:center;justify-content:space-between;gap:1rem;padding-top:.85rem;padding-bottom:.85rem;flex-wrap:wrap}
.brand{display:flex;align-items:center;gap:.8rem;text-decoration:none;color:var(--ink)}.brand img{width:48px;height:48px}
.brand b{display:block;font-family:var(--serif);font-size:1.32rem;line-height:1.05}.brand small{display:block;font-size:.72rem;letter-spacing:.16em;text-transform:uppercase;color:var(--muted)}
nav.main{display:flex;gap:.25rem;flex-wrap:wrap}nav.main a{display:block;padding:.5rem .72rem;border-radius:999px;text-decoration:none;color:var(--ink);font-weight:600;font-size:.95rem}
nav.main a:hover{background:var(--violet-l);color:var(--violet-d)}nav.main a[aria-current="page"]{background:var(--violet-d);color:#fff}
/* buttons */
.btn{display:inline-block;padding:.85rem 1.4rem;border-radius:999px;font-weight:700;text-decoration:none;background:var(--violet-d);color:#fff;border:2px solid var(--violet-d);font-size:1rem;cursor:pointer;font-family:inherit}
.btn:hover{background:var(--violet);border-color:var(--violet);color:#fff}.btn.ghost{background:transparent;color:var(--violet-d)}.btn.ghost:hover{background:var(--violet-l)}
/* hero */
.hero{background:linear-gradient(180deg,var(--paper),var(--cream));border-bottom:1px solid var(--line)}
.hero .wrap{display:grid;grid-template-columns:1.05fr .95fr;gap:2.5rem;align-items:center;padding-top:3.2rem;padding-bottom:3.2rem}
.eyebrow{display:inline-block;font-size:.78rem;font-weight:700;letter-spacing:.16em;text-transform:uppercase;color:var(--violet);margin-bottom:.8rem}
.lede{font-size:1.15rem;color:var(--ink2);max-width:36rem}.actions{display:flex;gap:.75rem;flex-wrap:wrap;margin:1.4rem 0 0}
.hero-art img{border-radius:28px;box-shadow:var(--shadow);width:100%}
.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:1rem;margin:2.2rem 0 0;padding:0;list-style:none}
.stats li{background:#fff;border:1px solid var(--line);border-radius:14px;padding:.8rem 1rem}.stats b{display:block;font-family:var(--serif);font-size:1.6rem;color:var(--violet-d);line-height:1.1}
.stats span{font-size:.85rem;color:var(--muted)}
/* sections */
.section{padding:3rem 0}.section.alt{background:var(--paper);border-top:1px solid var(--line);border-bottom:1px solid var(--line)}
.section-head{display:flex;justify-content:space-between;align-items:end;gap:1rem;flex-wrap:wrap;margin-bottom:1.4rem}.section-head p{color:var(--muted);margin:0;max-width:40rem}
.tiles{display:grid;grid-template-columns:repeat(5,1fr);gap:1rem;list-style:none;margin:0;padding:0}
.tile{display:block;background:#fff;border:1px solid var(--line);border-radius:var(--r);overflow:hidden;text-decoration:none;color:var(--ink);box-shadow:var(--shadow);transition:transform .15s}
.tile:hover{transform:translateY(-3px);color:var(--ink)}.tile span{display:block;padding:.75rem 1rem;font-weight:700}.tile small{display:block;color:var(--muted);font-weight:500}
.campuses{display:grid;grid-template-columns:1fr 1fr;gap:1.25rem;list-style:none;margin:0;padding:0}
.campus{background:#fff;border:1px solid var(--line);border-radius:var(--r);overflow:hidden;box-shadow:var(--shadow)}.campus img{width:100%}.campus div{padding:1rem 1.25rem}
.steps{display:grid;grid-template-columns:repeat(3,1fr);gap:1.25rem;list-style:none;margin:0;padding:0;counter-reset:step}
.steps li{background:#fff;border:1px solid var(--line);border-radius:var(--r);padding:1.25rem 1.25rem 1rem;position:relative}
.steps li::before{counter-increment:step;content:counter(step);display:grid;place-items:center;width:2.2rem;height:2.2rem;border-radius:50%;background:var(--violet-l);color:var(--violet-d);font-weight:800;margin-bottom:.6rem}
/* finder form */
form.filter{background:#fff;border:1px solid var(--line);border-radius:var(--r);padding:1.1rem;box-shadow:var(--shadow);display:grid;gap:.85rem}
.hero form.filter{grid-template-columns:repeat(3,1fr) auto;align-items:end;margin-top:1.6rem}
form.filter label{display:flex;flex-direction:column;gap:.3rem;font-size:.82rem;font-weight:700;color:var(--ink2);letter-spacing:.02em}
form.filter select{font:inherit;font-weight:500;font-size:1rem;padding:.6rem .7rem;border:1px solid #cfc7b8;border-radius:10px;background:var(--paper);color:var(--ink)}
form.filter .btn{padding:.7rem 1.2rem}
/* listing */
.page-head{background:var(--paper);border-bottom:1px solid var(--line)}.page-head .wrap{padding-top:1.6rem;padding-bottom:1.8rem}.page-head p{color:var(--ink2);max-width:46rem;margin:0}
.crumbs{font-size:.88rem;margin-bottom:.9rem;color:var(--muted)}.crumbs a{color:var(--muted)}
.layout{display:grid;grid-template-columns:280px 1fr;gap:2rem;align-items:start;padding-top:2rem;padding-bottom:3rem}
.panel{position:sticky;top:1rem;display:grid;gap:1.25rem}.panel h2{font-size:1.1rem;margin:0}
.browse h2{font-size:1.3rem}.browse{background:#fff;border:1px solid var(--line);border-radius:var(--r);padding:1rem 1.1rem}.browse h3{font-family:inherit;font-size:.78rem;letter-spacing:.14em;text-transform:uppercase;color:var(--muted);margin:.9rem 0 .4rem}
.browse h3:first-of-type{margin-top:.3rem}.browse p{display:flex;flex-wrap:wrap;gap:.35rem;margin:0}
.chip{display:inline-block;padding:.25rem .7rem;border-radius:999px;background:var(--cream);border:1px solid var(--line);font-size:.86rem;text-decoration:none;color:var(--ink)}
.chip:hover{background:var(--violet-l);border-color:var(--violet-l);color:var(--violet-d)}
.result{font-weight:700;color:var(--ink2);margin:0 0 1rem}
.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:1.25rem;list-style:none;margin:0;padding:0}
.card{background:#fff;border:1px solid var(--line);border-radius:var(--r);overflow:hidden;box-shadow:var(--shadow);display:flex;flex-direction:column;height:100%}
.card-media{position:relative;aspect-ratio:320/150;overflow:hidden}.card-media img{width:100%;height:100%;object-fit:cover}
.badge{position:absolute;left:.75rem;top:.75rem;font-size:.75rem;font-weight:800;padding:.2rem .65rem;border-radius:999px;background:var(--ok-bg);color:var(--ok)}
.badge.low{background:var(--warn-bg);color:var(--warn)}.badge.full{background:var(--bad-bg);color:var(--bad)}
.card-body{padding:1rem 1.1rem 1.15rem;display:flex;flex-direction:column;gap:.5rem;flex:1}
.subject{font-size:.74rem;font-weight:800;letter-spacing:.14em;text-transform:uppercase;color:var(--violet);margin:0}
.card h2{font-size:1.28rem;margin:0}.card h2 a{color:var(--ink);text-decoration:none}.card h2 a:hover{color:var(--violet)}
.card .summary{color:var(--ink2);font-size:.95rem;margin:0}
dl.card-facts{display:grid;grid-template-columns:1fr 1fr;gap:.45rem .9rem;margin:.35rem 0 0;padding:.8rem 0 0;border-top:1px solid var(--line);font-size:.88rem}
dl.card-facts div{min-width:0}dl.card-facts dt{font-size:.7rem;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:var(--muted)}dl.card-facts dd{margin:0;font-weight:600}
.empty{background:#fff;border:1px dashed #cfc7b8;border-radius:var(--r);padding:2rem;text-align:center}
/* course page */
.course-hero{background:var(--paper);border-bottom:1px solid var(--line)}.course-hero .wrap{display:grid;grid-template-columns:1.2fr .8fr;gap:2rem;align-items:center;padding-top:1.6rem;padding-bottom:2rem}
.course-hero img{border-radius:var(--r);box-shadow:var(--shadow);width:100%}
.course{display:grid;grid-template-columns:1fr 360px;gap:2rem;align-items:start;padding-top:2rem;padding-bottom:3rem}
.keyfacts{background:#fff;border:1px solid var(--line);border-radius:var(--r);padding:1.25rem 1.35rem;box-shadow:var(--shadow);position:sticky;top:1rem}
.keyfacts h2{font-size:1.15rem}dl.facts{display:grid;grid-template-columns:max-content 1fr;gap:.55rem 1.2rem;margin:0 0 1.1rem}dl.facts dt{font-weight:700;color:var(--ink2)}dl.facts dd{margin:0}
.note{background:var(--violet-l);border-radius:14px;padding:1rem 1.15rem;color:var(--violet-d)}
.prose{background:#fff;border:1px solid var(--line);border-radius:var(--r);padding:1.5rem}.prose h2{font-size:1.35rem}
.related{margin-top:2rem}
/* tables */
.table-wrap{overflow-x:auto;background:#fff;border:1px solid var(--line);border-radius:var(--r);box-shadow:var(--shadow)}
table{border-collapse:collapse;width:100%;font-size:.94rem}caption{text-align:left;padding:1rem 1.1rem;font-weight:700;color:var(--ink2)}
th,td{padding:.7rem 1rem;text-align:left;border-top:1px solid var(--line);vertical-align:top}thead th{background:var(--cream);font-size:.78rem;letter-spacing:.06em;text-transform:uppercase;color:var(--muted);white-space:nowrap}
tbody tr:nth-child(even){background:#fcfaf5}tbody th a{font-weight:700;color:var(--ink)}
.index{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:1rem;list-style:none;margin:0;padding:0}
.index a{display:block;background:#fff;border:1px solid var(--line);border-radius:14px;padding:1rem 1.1rem;text-decoration:none;color:var(--ink);font-weight:700;box-shadow:var(--shadow)}
.index a:hover{border-color:var(--violet);color:var(--violet-d)}.index small{display:block;font-weight:500;color:var(--muted)}
/* footer */
footer.site{background:var(--ink);color:#d8d3ea;padding:2.6rem 0 1.4rem;margin-top:0}footer.site a{color:#fff}
footer.site .cols{display:grid;grid-template-columns:1.4fr 1fr 1fr;gap:2rem}footer.site h2{color:#fff;font-size:1.05rem}footer.site ul{list-style:none;padding:0;margin:0;display:grid;gap:.35rem}
footer.site .fine{border-top:1px solid #3b3557;margin-top:2rem;padding-top:1rem;font-size:.82rem;color:#a9a3c2}
/* responsive */
@media (max-width:1000px){.tiles{grid-template-columns:repeat(3,1fr)}.layout{grid-template-columns:1fr}.panel{position:static}.course{grid-template-columns:1fr}.keyfacts{position:static}}
@media (max-width:820px){.hero .wrap,.course-hero .wrap{grid-template-columns:1fr}.hero form.filter{grid-template-columns:1fr 1fr}.stats{grid-template-columns:1fr 1fr}
.campuses,.steps,footer.site .cols{grid-template-columns:1fr}nav.main{overflow-x:auto;flex-wrap:nowrap;width:100%;padding-bottom:.2rem}nav.main a{white-space:nowrap}}
@media (max-width:520px){.tiles{grid-template-columns:1fr 1fr}.hero form.filter{grid-template-columns:1fr}dl.card-facts{grid-template-columns:1fr 1fr}h1{font-size:2rem}}
@media (prefers-reduced-motion:reduce){html{scroll-behavior:auto}.tile{transition:none}}"""


# ------------------------------------------------------------------------------------------------------------------------------- building blocks
def _page(title: str, body: str, current: str = "", head: str = "") -> str:
    nav = "".join(f'<a href="{href}"{" aria-current=\"page\"" if href == current else ""}>{e(label)}</a>' for href, label in NAV)
    foot_courses = "".join(f'<li><a href="/courses/category/{slugify(c)}">{e(c)}</a></li>' for c in D.CATEGORIES)
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><title>{e(title)} | {e(D.COLLEGE["name"])}</title>'
            f'<meta name="viewport" content="width=device-width, initial-scale=1"><meta name="description" content="{e(D.COLLEGE["tagline"])} in {e(D.COLLEGE["suburb"])}.">'
            f'<link rel="icon" href="/assets/img/logo.svg"><link rel="stylesheet" href="/assets/site.css">{head}</head><body>'
            f'<a class="skip" href="#main">Skip to content</a>'
            f'<div class="utility"><div class="wrap"><span>Term enrolments are open · concession card holders save {D.CONCESSION} %</span>'
            f'<span>Call <a href="tel:{e(D.COLLEGE["phone"].replace(" ", ""))}">{e(D.COLLEGE["phone"])}</a></span></div></div>'
            f'<header class="site"><div class="wrap"><a class="brand" href="/"><img src="/assets/img/logo.svg" alt="" width="48" height="48">'
            f'<span><b>{e(D.COLLEGE["name"])}</b><small>{e(D.COLLEGE["suburb"])} · since 1987</small></span></a>'
            f'<nav class="main" aria-label="Main">{nav}</nav></div></header>'
            f'<main id="main">{body}</main>'
            f'<footer class="site"><div class="wrap"><div class="cols"><div><h2>{e(D.COLLEGE["name"])}</h2><p>A not-for-profit adult education centre in '
            f'{e(D.COLLEGE["suburb"])}. {e(D.COLLEGE["tagline"])}.</p><p>{e(D.COLLEGE["phone"])} · <a href="mailto:{e(D.COLLEGE["email"])}">{e(D.COLLEGE["email"])}</a></p></div>'
            f'<div><h2>Subjects</h2><ul>{foot_courses}</ul></div>'
            f'<div><h2>Plan your study</h2><ul><li><a href="/courses">All courses</a></li><li><a href="/courses/compare">Compare courses</a></li>'
            f'<li><a href="/courses/campus">Campuses</a></li><li><a href="/enrolment-policy">Enrolment and refunds</a></li><li><a href="/about">About the college</a></li></ul></div></div>'
            f'<p class="fine">Larkspur Community College is a fictional college created for this demonstration.</p></div></footer></body></html>')


def _badge(c: D.Course) -> str:
    if c.seats_left == 0:
        return '<span class="badge full">Fully booked</span>'
    if c.seats_left <= 3:
        return f'<span class="badge low">Only {c.seats_left} left</span>'
    return '<span class="badge">Places available</span>'


def _facts_dl(c: D.Course) -> str:
    rows = (("Course fee", D.money(c.fee)), ("Duration", D.weeks(c.weeks)), ("Level", c.level), ("Class day", c.day), ("Campus", c.campus),
            ("Seats left", str(c.seats_left)), ("Materials", c.materials))
    return '<dl class="card-facts">' + "".join(f"<div><dt>{k}</dt><dd>{e(v)}</dd></div>" for k, v in rows) + "</dl>"


def _card(c: D.Course) -> str:
    return (f'<li><article class="card"><div class="card-media"><img src="/assets/img/subject-{c.category.lower()}.svg" alt="" width="320" height="232" loading="lazy">'
            f'{_badge(c)}</div><div class="card-body"><p class="subject">{e(c.category)}</p><h2><a href="/courses/{c.slug}">{e(c.name)}</a></h2>'
            f'<p class="summary">{e(c.summary)}</p>{_facts_dl(c)}</div></article></li>')


def _cards(courses: list[D.Course]) -> str:
    if not courses:
        return '<div class="empty"><p role="status" class="result">No courses match.</p><p><a class="btn ghost" href="/courses">Show all courses</a></p></div>'
    return f'<p role="status" class="result">{len(courses)} course{"" if len(courses) == 1 else "s"} found.</p><ul class="cards">{"".join(_card(c) for c in courses)}</ul>'


def _form(level: str = "", campus: str = "", day: str = "", button: str = "Show courses") -> str:
    def select(name, label, options, chosen, any_label):
        opts = f'<option value=""{" selected" if not chosen else ""}>{e(any_label)}</option>' + "".join(
            f'<option value="{e(o)}"{" selected" if o == chosen else ""}>{e(o)}</option>' for o in options)
        return f'<label>{e(label)}<select name="{name}">{opts}</select></label>'
    return ('<form class="filter" method="get" action="/courses" role="search" aria-label="Filter courses">'
            + select("level", "Level", LEVELS, level, "Any level") + select("campus", "Campus", CAMPUSES, campus, "Any campus")
            + select("day", "Class day", DAY_OPTIONS, day, "Any day") + f'<button class="btn" type="submit">{e(button)}</button></form>')


def _browse() -> str:
    def group(label, items):
        return f'<h3>{e(label)}</h3><p>' + "".join(f'<a class="chip" href="{h}">{e(t)}</a>' for h, t in items) + "</p>"
    return ('<section class="browse" aria-labelledby="browse"><h2 id="browse">Browse courses</h2>'
            + group("Campus", [(f"/courses/campus/{slugify(c)}", c) for c in CAMPUSES])
            + group("Class day", [(f"/courses/day/{slugify(d)}", d) for d in DAY_OPTIONS])
            + group("Level", [(f"/courses/level/{slugify(l)}", l) for l in LEVELS])
            + group("Subject", [(f"/courses/category/{slugify(c)}", c) for c in D.CATEGORIES])
            + '<h3>Side by side</h3><p><a class="chip" href="/courses/compare">Compare every course in one table</a></p></section>')


def _itemlist(courses: list[D.Course]) -> str:
    return _ld({"@context": "https://schema.org", "@type": "ItemList", "numberOfItems": len(courses),
                "itemListElement": [{"@type": "ListItem", "position": i, "item": {k: v for k, v in _course_ld(c).items() if k != "@context"}}
                                    for i, c in enumerate(courses, 1)]})


def _crumbs(*links: tuple[str, str]) -> str:
    return '<nav class="crumbs" aria-label="Breadcrumb"><a href="/">Home</a> › ' + " › ".join(f'<a href="{h}">{e(t)}</a>' for h, t in links) + "</nav>"


def _head(title: str, intro: str, crumbs: str = "", eyebrow: str = "") -> str:
    return (f'<section class="page-head"><div class="wrap">{crumbs}{f"<span class=eyebrow>{e(eyebrow)}</span>" if eyebrow else ""}'
            f'<h1>{e(title)}</h1><p>{intro}</p></div></section>')


def _listing(title: str, intro: str, courses: list[D.Course], *, form: tuple[str, str, str] = ("", "", ""), crumbs: str = "", current: str = "") -> str:
    body = (_head(title, intro, crumbs, "Short courses") + '<div class="wrap layout"><div class="panel"><h2>Find a course</h2>' + _form(*form) + _browse()
            + '</div><div class="results">' + _cards(courses) + "</div></div>")
    return _page(title, body, current, head=_itemlist(courses))


def _index(title: str, intro: str, items: list[tuple[str, str, int]], current: str = "") -> str:
    lis = "".join(f'<li><a href="{h}">{e(t)}<small>{n} course{"" if n == 1 else "s"}</small></a></li>' for h, t, n in items)
    return _page(title, _head(title, intro, _crumbs(("/courses", "All courses"))) + f'<div class="wrap section"><ul class="index">{lis}</ul></div>', current)


# ------------------------------------------------------------------------------------------------------------------------------- pages
def pages() -> dict[str, str]:
    n = len(D.COURSES)
    filling = sorted((c for c in D.COURSES if 0 < c.seats_left <= 3), key=lambda c: (c.seats_left, c.name))[:3]
    tiles = "".join(f'<li><a class="tile" href="/courses/category/{slugify(c)}"><img src="/assets/img/subject-{c.lower()}.svg" alt="" width="320" height="232">'
                    f'<span>{e(c)}<small>{len(matching(category=c))} courses</small></span></a></li>' for c in D.CATEGORIES)
    campuses = "".join(f'<li class="campus"><img src="/assets/img/campus-{c.lower()}.svg" alt="" width="480" height="260"><div><h3>{e(c)} campus</h3>'
                       f'<p>{len(matching(campus=c))} courses this term.</p><a href="/courses/campus/{slugify(c)}">Courses at {e(c)}</a></div></li>' for c in CAMPUSES)
    out = {"/": _page("Short courses", (
        f'<section class="hero"><div class="wrap"><div><span class="eyebrow">Term short courses · {e(D.COLLEGE["suburb"])}</span>'
        f'<h1>{e(D.COLLEGE["tagline"])}</h1><p class="lede">{n} courses this term across {len(D.CATEGORIES)} subject areas, taught at our Northside and '
        f'Riverside campuses. Every course lists its fee, duration, level, class day, campus, seats left and materials up front.</p>'
        f'<div class="actions"><a class="btn" href="/courses">Browse all courses</a><a class="btn ghost" href="/courses/compare">Compare every course in one table</a></div>'
        + _form(button="Find courses")
        + f'<ul class="stats"><li><b>{n}</b><span>courses this term</span></li><li><b>{len(D.CATEGORIES)}</b><span>subject areas</span></li>'
          f'<li><b>2</b><span>campuses</span></li><li><b>{D.CONCESSION} %</b><span>concession discount</span></li></ul></div>'
          f'<div class="hero-art"><img src="/assets/img/hero.svg" alt="" width="640" height="480"></div></div></section>'
        + f'<section class="section"><div class="wrap"><div class="section-head"><div><span class="eyebrow">Subjects</span><h2>Find your next class</h2></div>'
          f'<p>Small groups, friendly tutors and evening or weekend times that fit around work.</p></div><ul class="tiles">{tiles}</ul></div></section>'
        + f'<section class="section alt"><div class="wrap"><div class="section-head"><div><span class="eyebrow">Filling fast</span><h2>Only a few places left</h2></div>'
          f'<p><a href="/courses">See every course</a></p></div><ul class="cards">{"".join(_card(c) for c in filling)}</ul></div></section>'
        + f'<section class="section"><div class="wrap"><div class="section-head"><div><span class="eyebrow">Campuses</span><h2>Two campuses in {e(D.COLLEGE["suburb"])}</h2></div></div>'
          f'<ul class="campuses">{campuses}</ul></div></section>'
        + f'<section class="section alt"><div class="wrap"><div class="section-head"><div><span class="eyebrow">Enrolling</span><h2>How enrolment works</h2></div>'
          f'<p><a href="/enrolment-policy">Enrolment and refunds</a></p></div><ol class="steps"><li><h3>Choose a course</h3><p>Browse by subject, campus, class day or level.</p></li>'
          f'<li><h3>Enrol online or on campus</h3><p>Places are confirmed when the full fee is paid.</p></li>'
          f'<li><h3>Come to your first class</h3><p>Concession card holders receive {D.CONCESSION} % off the course fee.</p></li></ol></div></section>'
        + f'<div class="wrap section">{_browse()}</div>'),
        head=_ld({"@context": "https://schema.org", "@type": "EducationalOrganization", "name": D.COLLEGE["name"], "telephone": D.COLLEGE["phone"],
                  "email": D.COLLEGE["email"]}))}
    out["/courses"] = _listing("All courses", f"Every short course running this term ({n}). Filter by level, campus or class day, or browse by subject.",
                               D.COURSES, current="/courses")
    for lv in ("", *LEVELS):
        for cp in ("", *CAMPUSES):
            for dy in ("", *DAY_OPTIONS):
                chosen = [x for x in (lv, cp and f"{cp} campus", dy) if x]
                title = "Courses: " + " · ".join(chosen) if chosen else "All courses"
                out[f"/courses?{query(lv, cp, dy)}"] = _listing(title, "Filtered from all courses. Change the filters or browse below.",
                                                                matching(lv, cp, dy), form=(lv, cp, dy), crumbs=_crumbs(("/courses", "All courses")))
    out["/courses/campus"] = _index("Campuses", "Choose a campus to see every course taught there.",
                                    [(f"/courses/campus/{slugify(c)}", f"{c} campus", len(matching(campus=c))) for c in CAMPUSES], "/courses/campus")
    out["/courses/day"] = _index("Class days", "Choose the day that suits you.", [(f"/courses/day/{slugify(d)}", d, len(matching(day=d))) for d in DAY_OPTIONS])
    out["/courses/level"] = _index("Levels", "From first steps to advanced skills.", [(f"/courses/level/{slugify(l)}", l, len(matching(level=l))) for l in LEVELS])
    out["/courses/category"] = _index("Subjects", "Five subject areas this term.", [(f"/courses/category/{slugify(c)}", c, len(matching(category=c))) for c in D.CATEGORIES])
    up = lambda h, t: _crumbs(("/courses", "All courses"), (h, t))
    for c in CAMPUSES:
        out[f"/courses/campus/{slugify(c)}"] = _listing(f"Courses at {c} campus", f"All courses taught at our {e(c)} campus.", matching(campus=c),
                                                        form=("", c, ""), crumbs=up("/courses/campus", "Campuses"))
    for d in DAY_OPTIONS:
        what = {"Weekend": "on Saturday or Sunday", "Weekdays": "Monday to Friday"}.get(d, f"on {d}")
        out[f"/courses/day/{slugify(d)}"] = _listing(f"{d} courses", f"Courses with classes {e(what)}.", matching(day=d), form=("", "", d),
                                                     crumbs=up("/courses/day", "Class days"))
    for lv in LEVELS:
        out[f"/courses/level/{slugify(lv)}"] = _listing(f"{lv} courses", f"All {e(lv.lower())} courses.", matching(level=lv), form=(lv, "", ""),
                                                        crumbs=up("/courses/level", "Levels"))
    for cat in D.CATEGORIES:
        out[f"/courses/category/{slugify(cat)}"] = _listing(f"{cat} courses", f"All {e(cat)} courses.", matching(category=cat), crumbs=up("/courses/category", "Subjects"))
    head = "".join(f'<th scope="col">{h}</th>' for h in ("Course", "Subject", "Course fee", "Duration", "Level", "Class day", "Campus", "Seats left", "Materials"))
    rows = "".join(f'<tr><th scope="row"><a href="/courses/{c.slug}">{e(c.name)}</a></th><td>{e(c.category)}</td><td>{D.money(c.fee)}</td>'
                   f'<td>{D.weeks(c.weeks)}</td><td>{e(c.level)}</td><td>{e(c.day)}</td><td>{e(c.campus)}</td><td>{c.seats_left}</td><td>{e(c.materials)}</td></tr>'
                   for c in sorted(D.COURSES, key=lambda c: (c.fee, c.name)))
    out["/courses/compare"] = _page("Compare courses", _head("Compare courses", f"All {n} courses side by side, cheapest first.", _crumbs(("/courses", "All courses")))
                                    + f'<div class="wrap section"><div class="table-wrap"><table><caption>Every course this term</caption><thead><tr>{head}</tr></thead>'
                                      f'<tbody>{rows}</tbody></table></div></div>', "/courses/compare")
    for c in D.COURSES:
        cat = f"/courses/category/{slugify(c.category)}"
        more = (f'<section class="related"><h2>More like this</h2><p class="browse-links"><a class="chip" href="{cat}">More {e(c.category)} courses</a> '
                f'<a class="chip" href="/courses/campus/{slugify(c.campus)}">More at {e(c.campus)} campus</a> <a class="chip" href="/courses/day/{slugify(c.day)}">More '
                f'{e(c.day)} courses</a> <a class="chip" href="/courses/level/{slugify(c.level)}">More {e(c.level)} courses</a></p></section>')
        facts = (f'<dl class="facts"><dt>Course fee</dt><dd>{D.money(c.fee)}</dd><dt>Duration</dt><dd>{D.weeks(c.weeks)}</dd><dt>Level</dt><dd>{e(c.level)}</dd>'
                 f'<dt>Class day</dt><dd>{e(c.day)}</dd><dt>Seats left</dt><dd>{c.seats_left}</dd><dt>Campus</dt><dd>{e(c.campus)}</dd><dt>Materials</dt><dd>{e(c.materials)}</dd></dl>')
        cta = ('<p><a class="btn" href="/enrolment-policy">How to enrol</a></p>' if c.seats_left else '<p class="note">This course is fully booked this term.</p>')
        out[f"/courses/{c.slug}"] = _page(c.name, (
            f'<section class="course-hero"><div class="wrap"><div>{_crumbs(("/courses", "All courses"), (cat, c.category))}<span class="eyebrow">{e(c.category)} · '
            f'{e(c.campus)} campus</span><h1>{e(c.name)}</h1><p class="lede">{e(c.summary)}</p></div>'
            f'<img src="/assets/img/subject-{c.category.lower()}.svg" alt="" width="320" height="232"></div></section>'
            f'<div class="wrap course"><div><section class="prose"><h2>About this course</h2><p>{e(c.summary)} Classes run every {e(c.day)} for {D.weeks(c.weeks)} at our '
            f'{e(c.campus)} campus.</p><p class="note">Concession card holders receive {D.CONCESSION} % off the course fee. See '
            f'<a href="/enrolment-policy">enrolment and refunds</a>.</p></section>{more}</div>'
            f'<aside class="keyfacts" aria-labelledby="kf"><h2 id="kf">Key facts</h2>{facts}{cta}</aside></div>'),
            "/courses", head=_ld(_course_ld(c)))
    rows = "".join(f"<tr><td>{e(w)}</td><td>{e(r)}</td></tr>" for w, r in D.REFUNDS)
    out["/enrolment-policy"] = _page("Enrolment and refunds", _head("Enrolment and refunds", "Enrol online or at either campus office. Places are confirmed when the full fee is paid.")
                                     + f'<div class="wrap section"><div class="prose"><h2>Refunds</h2><div class="table-wrap"><table><caption>Refunds and withdrawals</caption>'
                                       f'<thead><tr><th scope="col">When you withdraw</th><th scope="col">Refund</th></tr></thead><tbody>{rows}</tbody></table></div>'
                                       f'<h2 style="margin-top:1.5rem">Concessions</h2><p>Concession card holders receive {D.CONCESSION} % off the course fee.</p></div></div>',
                                     "/enrolment-policy")
    out["/about"] = _page("About", _head(f"About {D.COLLEGE['name']}", f"A not-for-profit adult education centre in {e(D.COLLEGE['suburb'])}, with campuses at Northside and Riverside.")
                          + f'<div class="wrap section"><h2>Our campuses</h2><ul class="campuses">{campuses}</ul><p style="margin-top:1.5rem"><a href="/courses/campus">Courses by campus</a></p></div>',
                          "/about")
    return out


LIMITS = Limits(max_pages=120, max_depth=4, max_query_variants=2, max_assets=12, max_asset_bytes=60_000, max_total_asset_bytes=300_000)


@lru_cache(maxsize=1)
def snapshot() -> Snapshot:
    """Crawl the rendered site with the pipeline's own crawler, then capture what a crawler cannot discover (form results, unlinked redirects and any
    image the crawler's asset limit skipped) through the same offline fetcher and capture step. Every redirect must land on a captured page."""
    rendered = pages()
    assets = {"/assets/site.css": CSS.encode(), **art.assets()}
    mapping: dict = {path: html for path, html in rendered.items()}
    mapping.update({p: (200, "text/css" if p.endswith(".css") else "image/svg+xml", b) for p, b in assets.items()})
    reds = redirects()
    mapping.update({p: ("redirect", t) for p, t in reds.items()})
    snap = crawl(MappingFetcher(mapping), LIMITS)
    res = dict(snap.resources)
    fetcher = MappingFetcher(mapping)
    for path in sorted(set(rendered) - set(res)):
        r = fetcher.get(fetcher.origin + path)
        body, _ = capture_html(r.body.decode("utf-8"), path)
        res[path] = Resource(path, 200, "text/html; charset=utf-8", body)
    for path, body in sorted(assets.items()):
        if path not in res:
            res[path] = Resource(path, 200, "text/css" if path.endswith(".css") else "image/svg+xml", body)
    for path, target in sorted(reds.items()):
        if path not in res:
            res[path] = Resource(path, 301, "", b"", target)
    missing = sorted({t for t in reds.values()} - {p for p, r in res.items() if r.is_html})
    if missing:
        raise AssertionError(f"polished Larkspur redirects to pages that are not captured: {missing[:5]}")
    return Snapshot(res, {**snap.meta, "pages": sum(1 for r in res.values() if r.is_html), "captured_beyond_crawl": {
        "form_results_and_unlinked_pages": len(set(rendered) - set(snap.resources)), "redirects": sum(1 for r in res.values() if r.location)}})
