"""Snapshot determinism and the read-only mirror."""
import asyncio

import httpx
import pytest

from agent_readiness.investigate import zoo
from agent_readiness.investigate.inspect.crawl import Limits, MappingFetcher, crawl
from agent_readiness.investigate.sitemodel.server import Mirror
from agent_readiness.investigate.sitemodel.snapshot import Resource, Snapshot
from agent_readiness.scanner.serve import serve_app


def test_snapshot_hash_is_deterministic_and_origin_independent():
    rel = {"/": "<html><body><a href='/a'>a</a></body></html>", "/a": "<html><body>a</body></html>"}

    class Other(MappingFetcher):
        origin = "http://another-origin.invalid"
    absolute = {"/": "<html><body><a href='http://another-origin.invalid/a'>a</a></body></html>", "/a": rel["/a"]}
    a, b, c = crawl(MappingFetcher(rel)), crawl(MappingFetcher(rel)), crawl(Other(absolute))
    assert a.sha256 == b.sha256 == c.sha256                                         # same content => same hash, whatever the crawled origin
    changed = crawl(MappingFetcher({**rel, "/a": "<html><body>A</body></html>"}))
    assert changed.sha256 != a.sha256


def test_zoo_snapshots_are_reproducible():
    for sid in zoo.ids():
        assert crawl(MappingFetcher(zoo.files(sid)), Limits()).sha256 == zoo.snapshot(sid).sha256


def test_save_load_round_trip_and_tamper_detection(tmp_path):
    snap = zoo.snapshot("site-1")
    snap.save(tmp_path / "s")
    again = Snapshot.load(tmp_path / "s")
    assert again.sha256 == snap.sha256 and again.get("/workshops").body == snap.get("/workshops").body
    blob = next((tmp_path / "s" / "blobs").iterdir())
    blob.write_bytes(b"tampered")
    with pytest.raises(ValueError):
        Snapshot.load(tmp_path / "s")


def client_for(mirror):
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=mirror), base_url="http://mirror.test")


def test_mirror_is_read_only_and_serves_exactly_the_snapshot():
    snap = zoo.snapshot("site-1")
    m = Mirror(snap)

    async def go():
        async with client_for(m) as c:
            ok = await c.get("/workshops")
            head = await c.head("/workshops")
            missing = await c.get("/nope")
            q = await c.get("/workshops?x=1")                                      # no query fallback: only captured keys exist
            post = await c.post("/workshops", content=b"a=1")
            put = await c.put("/contact")
            return ok, head, missing, q, post, put
    ok, head, missing, q, post, put = asyncio.run(go())
    assert ok.status_code == 200 and ok.content == snap.get("/workshops").body and "text/html" in ok.headers["content-type"]
    assert head.status_code == 200 and head.content == b"" and missing.status_code == 404 and q.status_code == 404
    assert post.status_code == 405 and put.status_code == 405 and m.blocked == [{"method": "POST", "path": "/workshops"}, {"method": "PUT", "path": "/contact"}]
    assert ok.headers["cache-control"] == "no-store" and "default-src 'self'" in ok.headers["content-security-policy"] and "form-action 'self'" in ok.headers["content-security-policy"]
    assert [l["status"] for l in m.log] == [200, 200, 404, 404]


def test_mirror_serves_redirects_and_does_not_mutate_the_snapshot():
    snap = Snapshot({"/old": Resource("/old", 302, "", b"", "/new"), "/new": Resource("/new", 200, "text/html", b"<html>new</html>")})
    before = snap.sha256
    m = Mirror(snap)

    async def go():
        async with client_for(m) as c:
            return await c.get("/old", follow_redirects=False)
    r = asyncio.run(go())
    assert r.status_code == 302 and r.headers["location"] == "/new" and snap.sha256 == before


def test_mirror_over_a_real_loopback_socket():
    snap = zoo.snapshot("site-3")

    async def go():
        async with serve_app(Mirror(snap)) as base:
            async with httpx.AsyncClient() as c:
                return base, await c.get(base + "/recipes"), await c.post(base + "/recipes", content=b"x")
    base, ok, post = asyncio.run(go())
    assert base.startswith("http://127.0.0.1:") and ok.status_code == 200 and b"Lentil Soup" in ok.content and post.status_code == 405


@pytest.mark.browser
def test_real_chromium_can_browse_the_mirror_and_pages_cannot_reach_other_origins():
    from playwright.async_api import async_playwright
    snap = zoo.snapshot("site-2")
    m = Mirror(snap)

    async def go():
        async with serve_app(m) as base, async_playwright() as p:
            b = await p.chromium.launch()
            page = await b.new_page()
            await page.goto(base + "/")
            await page.locator("nav a").nth(2).click()                          # the third (icon-only) navigation link
            where, h1 = page.url.replace(base, ""), await page.locator("h1").inner_text()
            await b.close()
            return where, h1
    where, h1 = asyncio.run(go())
    assert (where, h1) == ("/rooms", "Rooms") and [l["status"] for l in m.log] == [200, 200] and m.blocked == []
