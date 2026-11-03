"""The `polished` Larkspur variant (Polished v1): a human-centred redesign, registered as a new immutable re-evaluation target.

Original, Modified and Improved are pinned byte for byte (recorded evaluations refer to their hashes). Polished keeps every fact, so every frozen
task keeps its expected answer; its routes (filter results, browse pages, redirects, images) work through the same mirror the jailed browser uses."""
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
from agent_readiness.sites.larkspur import polished as P
from agent_readiness.sites.larkspur import render

ORIGINAL = "2f9fd2ce09a044547ceb728acb9b85108931d81ca6b01374198144f509fed2eb"
MODIFIED = "edb9a5d2884a0e85fff8f9dfc6ed0e8a4bed41f9616e82678fc466864befe69f"
IMPROVED = "87e715d59c2376f82b23f33007496edf193812eb574a65a8629109bbe35e63b5"
POLISHED = "1053ce1884a9cf718fc631c2f7c144168b9562705727b23ef2f4fae0964f9bbb"
STORE = Path(__file__).resolve().parents[1] / "scanner-data" / "hosted-copy-fs" / "data" / "hosted" / "lifecycle" / "store"


def _fetch(snap, paths):
    m = Mirror(snap)

    async def go():
        out = {}
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=m), base_url="http://t", follow_redirects=True) as c:
            for p in paths:
                r = await c.get(p)
                out[p] = (r.status_code, r.url.raw_path.decode(), r.text, r.headers.get("content-type", ""))
        return out
    return asyncio.run(go()), m


def test_every_earlier_version_is_unchanged_and_polished_is_pinned():
    assert render.snapshot("original").sha256 == ORIGINAL
    assert render.snapshot("modified").sha256 == MODIFIED
    assert render.snapshot("improved").sha256 == IMPROVED
    assert render.snapshot("polished").sha256 == POLISHED
    P.snapshot.cache_clear()
    assert P.snapshot().sha256 == POLISHED                              # deterministic


def test_polished_is_a_registered_release_not_part_of_the_generation_pair():
    site = get("larkspur")
    assert site.variants == ("original", "modified")
    assert site.releases == ("improved", "polished") and site.registered == ("original", "modified", "improved", "polished")
    view = LS.site_view("larkspur")
    assert [v["name"] for v in view["variants"]] == ["original", "modified", "improved", "polished"]
    assert all(v["description"] for v in view["variants"])


def test_every_card_states_every_deciding_fact_as_a_labelled_value():
    status, _, html, _ = _fetch(render.snapshot("polished"), ["/courses"])[0]["/courses"]
    assert status == 200
    cards = BeautifulSoup(html, "html.parser").select("article.card")
    assert len(cards) == len(D.COURSES)
    for c, card in zip(D.COURSES, cards):
        facts = {dt.get_text(strip=True): dt.find_next_sibling("dd").get_text(strip=True) for dt in card.select("dl.card-facts dt")}
        assert facts == {"Course fee": f"${c.fee}", "Duration": D.weeks(c.weeks), "Level": c.level, "Class day": c.day, "Campus": c.campus,
                         "Seats left": str(c.seats_left), "Materials": c.materials}, c.slug


def test_course_pages_state_the_facts_and_structured_data_agrees():
    snap = render.snapshot("polished")
    for c in D.COURSES:
        soup = BeautifulSoup(snap.get(f"/courses/{c.slug}").text(), "html.parser")
        facts = {dt.get_text(strip=True): dt.find_next_sibling("dd").get_text(strip=True) for dt in soup.select("dl.facts dt")}
        assert facts["Course fee"] == f"${c.fee}" and facts["Seats left"] == str(c.seats_left) and facts["Class day"] == c.day
        assert len(soup.select("dl")) == 1                               # no other course's facts on a course page
        ld = json.loads(soup.find("script", attrs={"type": "application/ld+json"}).string)
        assert ld["name"] == c.name and ld["offers"]["price"] == c.fee and ld["offers"]["inventoryLevel"]["value"] == c.seats_left


def test_images_and_stylesheet_are_captured_and_decorative():
    snap = render.snapshot("polished")
    got, m = _fetch(snap, ["/assets/site.css", "/assets/img/hero.svg", "/assets/img/logo.svg", *[f"/assets/img/subject-{c.lower()}.svg" for c in D.CATEGORIES]])
    assert all(s == 200 for s, *_ in got.values()) and m.blocked == []
    for r in snap.pages():
        for img in BeautifulSoup(r.text(), "html.parser").find_all("img"):
            assert img.get("alt") == "" and snap.get(img["src"]) is not None, (r.path, img)


def test_filters_browse_pages_and_redirects_keep_working():
    paths = ["/courses?level=Beginner&campus=&day=Weekend", "/courses?campus=northside&level=intermediate", "/courses/day/weekend",
             "/courses/introduction-to-python", "/courses/", "/courses?day=Friday"]
    got, m = _fetch(render.snapshot("polished"), paths)
    names = lambda html: [a.get_text() for a in BeautifulSoup(html, "html.parser").select("article.card h2 a")]
    assert names(got[paths[0]][2]) == [c.name for c in I.matching("Beginner", "", "Weekend")]
    assert names(got[paths[1]][2]) == [c.name for c in I.matching("Intermediate", "Northside")]
    assert names(got[paths[2]][2]) == [c.name for c in I.matching(day="Weekend")]
    assert got[paths[3]][:2] == (200, "/courses/intro-to-python") and got[paths[4]][:2] == (200, "/courses")
    assert "No courses match" in got[paths[5]][2]
    assert m.blocked == []


def test_every_link_resolves_inside_the_snapshot():
    snap = render.snapshot("polished")
    for r in snap.pages():
        for a in BeautifulSoup(r.text(), "html.parser").find_all("a", href=True):
            if a["href"].startswith(("tel:", "mailto:", "#")):
                continue
            target = snap.get(a["href"])
            assert target is not None and (target.is_html or target.location), (r.path, a["href"])


def test_every_page_is_reachable_and_the_page_audit_is_clean():
    from agent_readiness.diagnostics import structural as SD
    from agent_readiness.investigate.inspect.profile import build_profile
    prof = build_profile(render.snapshot("polished"))
    assert prof["unreachable"] == []
    assert SD.observe(prof, site="larkspur", version="polished") == []


@pytest.mark.skipif(not (STORE / "objects").is_dir(), reason="needs the local copy of the production lifecycle store")
def test_every_frozen_task_stays_valid_with_its_answer_on_polished():
    from agent_readiness.evalruns import manifest as MF
    from agent_readiness.evalruns import runner as RN
    from agent_readiness.investigate.inspect.profile import build_profile
    from agent_readiness.suites.store import WriteOnceStore
    st = WriteOnceStore(STORE)
    prof = build_profile(render.snapshot("polished"))
    for ref in ("larkspur-core@v3", "larkspur-core@v2"):
        sha = json.loads((STORE / "refs" / "frozen_suite" / f"{ref}.json").read_text())["sha256"]
        _, _, tasks = MF.suite_tasks(st, sha)
        for t in tasks:
            p, why = RN.validity(t, st.get("private_outcome", t.private_sha256).expected, prof, "/")
            assert p is not None, (ref, t.task_id, why)


def test_the_module_never_rewrites_the_shared_records():
    assert all(re.fullmatch(r"[a-z0-9-]+", c.slug) for c in D.COURSES)
    assert get("larkspur").oracle().label == "larkspur data.COURSES"
