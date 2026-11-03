"""The `improved` Larkspur variant (final showcase): every actionable recommendation applied, served through the real snapshot mirror.

Original and Modified are pinned byte for byte (recorded evaluations refer to their hashes). The improved snapshot keeps every fact, so every
frozen task keeps its expected answer; its new routes (browse pages, filter form results, hand-typed query strings, redirects for dead ends)
work through the same mirror the jailed browser uses."""
import asyncio
import json
import re
from pathlib import Path

import httpx
import pytest
from bs4 import BeautifulSoup

from agent_readiness.framework.site import get
from agent_readiness.investigate.sitemodel.server import Mirror
from agent_readiness.lifecycle import sites as LS
from agent_readiness.sites.larkspur import data as D
from agent_readiness.sites.larkspur import improved as I
from agent_readiness.sites.larkspur import render

ORIGINAL = "2f9fd2ce09a044547ceb728acb9b85108931d81ca6b01374198144f509fed2eb"
MODIFIED = "edb9a5d2884a0e85fff8f9dfc6ed0e8a4bed41f9616e82678fc466864befe69f"
STORE = Path(__file__).resolve().parents[1] / "scanner-data" / "research" / "stage-a" / "store"


def _fetch(snap, paths):
    m = Mirror(snap)

    async def go():
        out = {}
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=m), base_url="http://t", follow_redirects=True) as c:
            for p in paths:
                r = await c.get(p)
                out[p] = (r.status_code, r.url.raw_path.decode(), r.text)
        return out
    return asyncio.run(go()), m


def test_original_and_modified_are_unchanged_byte_for_byte():
    assert render.snapshot("original").sha256 == ORIGINAL
    assert render.snapshot("modified").sha256 == MODIFIED


def test_improved_is_a_registered_release_not_part_of_the_generation_pair():
    site = get("larkspur")
    assert site.variants == ("original", "modified")                 # tasks are generated and validated on this pair (recorded datasets re-derive)
    assert site.releases[0] == "improved" and site.registered[:3] == ("original", "modified", "improved")     # later releases follow (polished)
    a = render.snapshot("improved").sha256
    I.snapshot.cache_clear()
    assert I.snapshot().sha256 == a and a not in (ORIGINAL, MODIFIED)
    view = LS.site_view("larkspur")
    assert [v["name"] for v in view["variants"]][:3] == ["original", "modified", "improved"]
    assert all(v["description"] for v in view["variants"])


def test_every_card_on_the_catalogue_states_every_deciding_fact():
    status, _, html = _fetch(render.snapshot("improved"), ["/courses"])[0]["/courses"]
    assert status == 200
    soup = BeautifulSoup(html, "html.parser")
    cards = soup.select("article.card")
    assert len(cards) == len(D.COURSES)
    for c, card in zip(D.COURSES, cards):
        text = card.get_text(" ", strip=True)
        for fact in (f"Course fee ${c.fee}", f"Duration {D.weeks(c.weeks)}", f"Level {c.level}", f"Class day {c.day}", f"Campus {c.campus}",
                     f"Seats left {c.seats_left}", f"Materials {c.materials}"):
            assert fact in text, (c.slug, fact)


def test_structured_data_states_the_same_values_the_pages_show():
    snap = render.snapshot("improved")
    for c in D.COURSES:
        soup = BeautifulSoup(snap.get(f"/courses/{c.slug}").text(), "html.parser")
        ld = json.loads(soup.find("script", attrs={"type": "application/ld+json"}).string)
        assert ld["@type"] == "Course" and ld["name"] == c.name and ld["educationalLevel"] == c.level
        assert ld["offers"]["price"] == c.fee and ld["offers"]["inventoryLevel"]["value"] == c.seats_left
        inst = ld["hasCourseInstance"]
        assert inst["location"]["name"] == f"{c.campus} campus" and inst["courseSchedule"]["byDay"].endswith(c.day) and inst["courseSchedule"]["repeatCount"] == c.weeks
    items = json.loads(BeautifulSoup(snap.get("/courses").text(), "html.parser").find("script", attrs={"type": "application/ld+json"}).string)
    assert items["@type"] == "ItemList" and [i["item"]["name"] for i in items["itemListElement"]] == [c.name for c in D.COURSES]


def test_dead_ends_seen_in_agent_runs_now_redirect_to_the_right_page():
    got, m = _fetch(render.snapshot("improved"), ["/courses/", "/courses/introduction-to-python", "/courses/yoga-for-beginners", "/courses/building-web-pages",
                                                   "/courses/intro-to-python/", "/course/beginners-yoga", "/courses/campus/"])
    assert {p: (s, u) for p, (s, u, _) in got.items()} == {
        "/courses/": (200, "/courses"), "/courses/introduction-to-python": (200, "/courses/intro-to-python"),
        "/courses/yoga-for-beginners": (200, "/courses/beginners-yoga"), "/courses/building-web-pages": (200, "/courses/web-pages-from-scratch"),
        "/courses/intro-to-python/": (200, "/courses/intro-to-python"), "/course/beginners-yoga": (200, "/courses/beginners-yoga"),
        "/courses/campus/": (200, "/courses/campus")}
    assert m.blocked == []
    # the same paths are dead ends on the Original site (unchanged)
    orig, _ = _fetch(render.snapshot("original"), ["/courses/", "/courses/introduction-to-python"])
    assert {s for s, _, _ in orig.values()} == {404}


def test_browse_pages_and_hand_typed_filters_return_exactly_the_matching_courses():
    paths = ["/courses/campus/northside", "/courses/day/weekend", "/courses/level/intermediate", "/courses/category/arts",
             "/courses?level=Intermediate&campus=Northside", "/courses?campus=northside&level=intermediate", "/courses?day=Saturday",
             "/courses?level=Beginner&campus=&day=Weekend", "/courses?day=Friday"]
    got, _ = _fetch(render.snapshot("improved"), paths)
    names = lambda html: [a.get_text() for a in BeautifulSoup(html, "html.parser").select("article.card h2 a")]
    want = {"/courses/campus/northside": I.matching(campus="Northside"), "/courses/day/weekend": I.matching(day="Weekend"),
            "/courses/level/intermediate": I.matching(level="Intermediate"), "/courses/category/arts": I.matching(category="Arts"),
            "/courses?level=Intermediate&campus=Northside": I.matching("Intermediate", "Northside"),
            "/courses?campus=northside&level=intermediate": I.matching("Intermediate", "Northside"),
            "/courses?day=Saturday": I.matching(day="Saturday"), "/courses?level=Beginner&campus=&day=Weekend": I.matching("Beginner", "", "Weekend"),
            "/courses?day=Friday": []}
    for p in paths:
        assert got[p][0] == 200, p
        assert names(got[p][2]) == [c.name for c in want[p]], p
    assert {c.name for c in I.matching(day="Weekend", level="Beginner")} == {"Wheel-thrown pottery", "Beginners yoga", "Mindful meditation", "Home electrical basics"}
    assert "No courses match" in got["/courses?day=Friday"][2]


def test_every_form_submission_and_redirect_is_captured_and_stays_inside_the_site():
    snap = render.snapshot("improved")
    for lv in ("", *I.LEVELS):
        for cp in ("", *I.CAMPUSES):
            for dy in ("", *I.DAY_OPTIONS):
                assert snap.get(f"/courses?{I.query(lv, cp, dy)}").is_html
    reds = [r for r in snap.resources.values() if r.location]
    assert len(reds) == len(I.redirects()) and all(r.location.startswith("/") and not r.location.startswith("//") for r in reds)
    assert all(snap.get(r.location).is_html for r in reds)


def test_every_page_link_resolves_inside_the_improved_snapshot():
    snap = render.snapshot("improved")
    for r in snap.pages():
        for a in BeautifulSoup(r.text(), "html.parser").find_all("a", href=True):
            target = snap.get(a["href"])
            assert target is not None and (target.is_html or target.location), (r.path, a["href"])


def test_the_oracle_and_its_facts_are_unchanged():
    o = get("larkspur").oracle()
    assert o.label == "larkspur data.COURSES"
    assert all(re.fullmatch(r"[a-z0-9-]+", c.slug) for c in D.COURSES)


def test_form_results_count_as_reachable_and_the_page_audit_finds_nothing_left_to_fix():
    from agent_readiness.diagnostics import structural as SD
    from agent_readiness.investigate.inspect.profile import build_profile
    prof = build_profile(render.snapshot("improved"))
    assert prof["unreachable"] == []                                     # every filter result is one form submission away
    assert prof["depth"][f"/courses?{I.query('Beginner', '', 'Weekend')}"] == 1             # the filter form is on the home page too
    st = {v: SD.observe(build_profile(render.snapshot(v)), site="larkspur", version=v) for v in ("original", "modified", "improved")}
    assert [len(st[v]) for v in st] == [7, 4, 0]
    c = SD.compare(st["original"], st["improved"])
    assert (len(c["resolved"]), len(c["introduced"]), len(c["persisting"])) == (7, 0, 0)
    audit = json.loads((Path(__file__).resolve().parents[1] / "dashboard" / "src" / "site" / "showcase" / "larkspur.json").read_text())["page_audit"]
    assert audit == {v: [f.title for f in st[v]] for v in st}            # the showcase states exactly what the product finds


def test_a_get_form_only_adds_reachability_for_pages_its_own_fields_produce():
    from agent_readiness.investigate.inspect.crawl import Limits, MappingFetcher, crawl
    from agent_readiness.investigate.inspect.profile import build_profile
    from agent_readiness.investigate.sitemodel.snapshot import Resource
    form = '<form method="get" action="/list"><select name="a"><option>x</option></select></form>'
    snap = crawl(MappingFetcher({"/": f"<html><body><main><a href='/list'>list</a>{form}</main></body></html>", "/list": "<main>list</main>"}), Limits())
    res = dict(snap.resources)
    for path in ("/list?a=x", "/list?b=y", "/other?a=x"):
        res[path] = Resource(path, 200, "text/html; charset=utf-8", b"<main>result</main>")
    prof = build_profile(type(snap)(res, snap.meta))
    assert prof["unreachable"] == ["/list?b=y", "/other?a=x"]           # only the form's own action and field names count


@pytest.mark.skipif(not (STORE / "objects").is_dir(), reason="needs the local lifecycle store")
def test_every_frozen_larkspur_task_stays_valid_with_its_answer_on_improved():
    from agent_readiness.evalruns import manifest as MF
    from agent_readiness.evalruns import runner as RN
    from agent_readiness.investigate.inspect.profile import build_profile
    from agent_readiness.suites.store import WriteOnceStore
    st = WriteOnceStore(STORE)
    sha = json.loads((STORE / "refs" / "frozen_suite" / "larkspur-core@v2.json").read_text())["sha256"]
    _, _, tasks = MF.suite_tasks(st, sha)
    profs = {v: build_profile(render.snapshot(v)) for v in ("original", "improved")}
    hops = {}
    for t in tasks:
        priv = st.get("private_outcome", t.private_sha256).expected
        for v, prof in profs.items():
            p, why = RN.validity(t, priv, prof, "/")
            assert p is not None, (t.task_id, v, why)
            hops[(t.task_id, v)] = p["min_hops"]
    # five of the six tasks are answerable from the catalogue on the improved site; the sixth is a single-course question (its own page)
    assert sorted(hops[(t.task_id, "improved")] for t in tasks) == [1, 1, 1, 1, 1, 2]
    assert all(hops[(t.task_id, "original")] == 2 for t in tasks)


@pytest.mark.browser
def test_real_chromium_filters_the_catalogue_with_the_form():
    from playwright.async_api import async_playwright

    from agent_readiness.scanner.serve import serve_app
    m = Mirror(render.snapshot("improved"))

    async def go():
        async with serve_app(m) as base, async_playwright() as p:
            b = await p.chromium.launch()
            page = await b.new_page()
            await page.goto(base + "/courses")
            await page.select_option("select[name=level]", "Beginner")
            await page.select_option("select[name=day]", "Weekend")
            await page.click("form.filter button[type=submit]")
            await page.wait_for_load_state()
            where, h1 = page.url.replace(base, ""), await page.locator("h1").inner_text()
            n = await page.locator("article.card").count()
            await page.goto(base + "/courses/introduction-to-python")
            redirected = page.url.replace(base, ""), await page.locator("h1").inner_text()
            await b.close()
            return where, h1, n, redirected
    where, h1, n, redirected = asyncio.run(go())
    assert where == "/courses?level=Beginner&campus=&day=Weekend" and h1 == "Courses: Beginner · Weekend" and n == 4
    assert redirected == ("/courses/intro-to-python", "Introduction to Python")
    assert m.blocked == [] and all(e["status"] in (200, 301) for e in m.log)
