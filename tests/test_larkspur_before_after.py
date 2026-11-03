"""The corrected showcase experiment: `polishedoriginal` ("Before") is the ORIGINAL Larkspur site visually redesigned, with Original's pages, links,
facts and agent-readiness limitations unchanged; `modifiedpolished` ("After") applies the Before evaluation's recommendations to that design.
Every earlier snapshot is pinned byte for byte."""
import json
from pathlib import Path

import pytest
from bs4 import BeautifulSoup

from agent_readiness.framework.site import get
from agent_readiness.sites.larkspur import data as D
from agent_readiness.sites.larkspur import render

PINNED = {"original": "2f9fd2ce09a044547ceb728acb9b85108931d81ca6b01374198144f509fed2eb", "modified": "edb9a5d2884a0e85fff8f9dfc6ed0e8a4bed41f9616e82678fc466864befe69f",
          "improved": "87e715d59c2376f82b23f33007496edf193812eb574a65a8629109bbe35e63b5", "polished": "1053ce1884a9cf718fc631c2f7c144168b9562705727b23ef2f4fae0964f9bbb",
          "polished2": "1b02ed0907330a1e17ce414ef232081922769554a322b93632f43d38ce7c6106",
          "polishedoriginal": "2ee4a7be2bd0cfb66adef68779317ea40a27b55c7330cf4ca23bdc85ec91169a",
          "modifiedpolished": "2a16c38be474b38f4634307e44a782eddadd1dba48b45d9c85dcb3059530569f"}
STORE = Path(__file__).resolve().parents[1] / "scanner-data" / "hosted-copy-fs" / "data" / "hosted" / "lifecycle" / "store"


def _links(snap, path):
    return {a["href"] for a in BeautifulSoup(snap.get(path).text(), "html.parser").find_all("a", href=True)} - {"#main"}


def test_every_snapshot_is_pinned():
    for v, sha in PINNED.items():
        assert render.snapshot(v).sha256 == sha, v
    assert {"polishedoriginal", "modifiedpolished"} <= set(get("larkspur").registered)


def test_before_has_exactly_originals_pages_links_and_no_agent_readiness_features():
    o, b = render.snapshot("original"), render.snapshot("polishedoriginal")
    assert {r.path for r in o.pages()} == {r.path for r in b.pages()}
    for r in o.pages():
        assert _links(b, r.path) <= _links(o, r.path) | {"/"}, r.path                # no page links anywhere Original does not
    assert not any(r.location for r in b.resources.values())                          # no redirects
    for r in b.pages():
        html = r.text()
        assert "application/ld+json" not in html and "<form" not in html, r.path
    cards = BeautifulSoup(b.get("/courses").text(), "html.parser").select("article.card")
    assert len(cards) == len(D.COURSES)
    for c, card in zip(D.COURSES, cards):
        text = card.get_text(" ", strip=True)
        assert text == f"{c.category} {c.name} {c.summary}", c.slug               # Original's card content only
    for c in D.COURSES:
        facts = {dt.get_text(strip=True): dt.find_next_sibling("dd").get_text(strip=True) for dt in BeautifulSoup(b.get(f"/courses/{c.slug}").text(), "html.parser").select("dl.facts dt")}
        assert facts == {"Course fee": f"${c.fee}", "Duration": D.weeks(c.weeks), "Level": c.level, "Class day": c.day, "Seats left": str(c.seats_left),
                         "Campus": c.campus, "Materials": c.materials}


def test_before_has_originals_page_audit():
    from agent_readiness.diagnostics import structural as SD
    from agent_readiness.investigate.inspect.profile import build_profile
    t = lambda v: sorted(f.title for f in SD.observe(build_profile(render.snapshot(v)), site="larkspur", version=v))
    assert t("polishedoriginal") == t("original") and len(t("original")) == 7


@pytest.mark.skipif(not (STORE / "objects").is_dir(), reason="needs the local copy of the production lifecycle store")
def test_the_frozen_v3_tasks_stay_valid_with_their_answers_on_before():
    from agent_readiness.evalruns import manifest as MF
    from agent_readiness.evalruns import runner as RN
    from agent_readiness.investigate.inspect.profile import build_profile
    from agent_readiness.suites.store import WriteOnceStore
    st = WriteOnceStore(STORE)
    sha = json.loads((STORE / "refs" / "frozen_suite" / "larkspur-core@v3.json").read_text())["sha256"]
    _, _, tasks = MF.suite_tasks(st, sha)
    for v, hops in (("polishedoriginal", 2), ("modifiedpolished", 1)):
        prof = build_profile(render.snapshot(v))
        for t in tasks:
            p, why = RN.validity(t, st.get("private_outcome", t.private_sha256).expected, prof, "/")
            assert p is not None and p["min_hops"] == hops, (v, t.task_id, why)


def test_after_is_before_plus_exactly_the_recommended_changes():
    import asyncio
    import httpx
    from agent_readiness.diagnostics import structural as SD
    from agent_readiness.investigate.inspect.profile import build_profile
    from agent_readiness.investigate.sitemodel.server import Mirror
    b, a = render.snapshot("polishedoriginal"), render.snapshot("modifiedpolished")
    assert {r.path for r in b.pages()} == {r.path for r in a.pages()}                     # no new pages: no filter, browse pages or comparison table
    assert {p: r.location for p, r in a.resources.items() if r.location} == {"/courses/introduction-to-python": "/courses/intro-to-python"}
    for c, card in zip(D.COURSES, BeautifulSoup(a.get("/courses").text(), "html.parser").select("article.card")):
        facts = {dt.get_text(strip=True): dt.find_next_sibling("dd").get_text(strip=True) for dt in card.select("dl.card-facts dt")}
        assert facts == {"Course fee": f"${c.fee}", "Duration": D.weeks(c.weeks), "Level": c.level, "Class day": c.day, "Campus": c.campus,
                         "Seats left": str(c.seats_left), "Materials": c.materials}
    for c in D.COURSES:
        ld = json.loads(BeautifulSoup(a.get(f"/courses/{c.slug}").text(), "html.parser").find("script", attrs={"type": "application/ld+json"}).string)
        assert ld["name"] == c.name and ld["offers"]["price"] == c.fee and ld["offers"]["inventoryLevel"]["value"] == c.seats_left
    assert SD.observe(build_profile(a), site="larkspur", version="modifiedpolished") == []

    async def go():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=Mirror(a)), base_url="http://t", follow_redirects=True) as c:
            r = await c.get("/courses/introduction-to-python")
            return r.status_code, r.url.raw_path.decode()
    assert asyncio.run(go()) == (200, "/courses/intro-to-python")
