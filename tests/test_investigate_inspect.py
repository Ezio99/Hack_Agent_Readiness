"""Generic page model + bounded crawler (plan D2/M2): facts only, no domain assumptions, hard boundaries."""
import httpx
import pytest

from agent_readiness.investigate.inspect.crawl import Crawler, HttpFetcher, Limits, MappingFetcher, capture_html, crawl
from agent_readiness.investigate.inspect.pagemodel import accessible_name, parse_page
from bs4 import BeautifulSoup


def pg(body, title="T"):
    return f'<!doctype html><html lang="en"><head><title>{title}</title></head><body>{body}</body></html>'


def test_accessible_names_follow_the_usual_sources():
    html = ('<main><button aria-label="Close"></button><button><svg><title>Menu</title></svg></button><button><svg></svg></button><a href="/x"><img src="a.png" alt="Home"></a>'
            '<a href="/y"></a><label for="q">Query</label><input id="q" name="q"><input name="z" placeholder="Zip"><input type="submit" value="Go"><span id="l">Name field</span>'
            '<input aria-labelledby="l" name="n"><div role="button">Do it</div></main>')
    rec = parse_page("/", pg(html))
    by = {(c["tag"], c["locator"]): c for c in rec["controls"]}
    names = [(c["tag"], c["name"], c["name_source"]) for c in rec["controls"]]
    assert ("button", "Close", "aria-label") in names and ("button", "Menu", "content") in names and ("button", None, None) in names
    assert ("a", "Home", "img-alt") in names and ("a", None, None) in names
    assert ("input", "Query", "label") in names and ("input", "Zip", "placeholder") in names and ("input", "Go", "value") in names and ("input", "Name field", "aria-labelledby") in names
    assert ("div", "Do it", "content") in names and by


def test_page_model_is_domain_neutral_and_extracts_structure():
    html = ('<header><nav><a href="/">Home</a><a href="/docs">Docs</a></nav></header><main><h1>API reference</h1><h2>Limits</h2>'
            '<dl><dt>Rate limit</dt><dd>60 per minute</dd><dt>Burst</dt><dd>10</dd></dl><table><tr><th>Plan</th><td>Free</td></tr></table><p>Region: eu-west</p>'
            '<form action="/search" method="get"><input name="q"><button>Find</button></form><img src="/a.png"><p style="display:none">secret hidden words</p>'
            '<script type="application/ld+json">{"@type":"Article","name":"X"}</script></main><footer>(c)</footer>')
    r = parse_page("/ref", pg(html, "Ref"))
    assert r["title"] == "Ref" and r["lang"] == "en" and [h["text"] for h in r["headings"]] == ["API reference", "Limits"]
    assert {"nav", "header", "main", "footer"} <= set(r["landmarks"])
    facts = {(f["label"], f["value"], f["how"]) for f in r["facts"]}
    assert ("rate limit", "60 per minute", "dl") in facts and ("plan", "Free", "table") in facts and ("region", "eu-west", "text") in facts
    assert "secret hidden" not in r["text"] and r["images"] == [{"src": "/a.png", "alt": None}]
    assert r["forms"][0]["action"] == "/search" and r["forms"][0]["fields"][0]["accessible_name"] is None and r["structured_data"][0]["name"] == "X"
    assert [l["href"] for l in r["nav_links"]] == ["/", "/docs"]


def test_item_groups_are_found_structurally_without_prices():
    items = "".join(f'<li class="row"><a href="/talks/{i}">Talk {i}</a><span>Room: R{i}</span></li>' for i in range(4))
    r = parse_page("/talks", pg(f"<main><ul>{items}</ul><nav><a href=\"/a\">a</a><a href=\"/b\">b</a><a href=\"/c\">c</a></nav></main>"))
    assert len(r["item_groups"]) == 1 and len(r["item_groups"][0]["items"]) == 4
    assert r["item_groups"][0]["items"][0]["facts"][0]["label"] == "room"


def site(extra=None):
    f = {"/": pg('<a href="/a">a</a><a href="/b?x=1">b1</a><a href="/b?x=2">b2</a><a href="/b?x=3">b3</a><a href="https://elsewhere.invalid/z">off</a><a href="/secret/s">s</a><a href="/doc.pdf">pdf</a>'),
         "/a": pg('<a href="/a/deep">deeper</a>'), "/a/deep": pg('<a href="/a/deep/deeper">more</a>'), "/a/deep/deeper": pg("end"),
         "/b?x=1": pg("1"), "/b?x=2": pg("2"), "/b?x=3": pg("3"), "/secret/s": pg("hidden by robots"),
         "/robots.txt": (200, "text/plain", "User-agent: *\nDisallow: /secret/\n")}
    f.update(extra or {})
    return MappingFetcher(f)


def test_crawl_respects_origin_robots_depth_query_cap_and_types():
    fetcher = site()
    snap = crawl(fetcher, Limits(max_depth=2, max_query_variants=2))
    paths = set(snap.resources)
    assert "/secret/s" not in paths and snap.meta["skipped"]["/secret/s"] == "robots.txt"
    assert not any("elsewhere" in r for r in fetcher.requests) and "/doc.pdf" not in fetcher.requests
    assert "/a/deep" in paths and "/a/deep/deeper" not in paths                      # depth 3 > max_depth 2
    assert sum(p.startswith("/b?") for p in paths) == 2 and any(v == "query_variant_cap" for v in snap.meta["skipped"].values())


def test_crawl_page_cap_and_redirects():
    f = {"/": pg("".join(f'<a href="/p{i}">p</a>' for i in range(20))), "/r": ("redirect", "/p1"), **{f"/p{i}": pg(str(i)) for i in range(20)}}
    snap = crawl(MappingFetcher(f), Limits(max_pages=5))
    assert len(snap.pages()) == 5
    f2 = {"/": pg('<a href="/old">old</a><a href="/away">away</a>'), "/old": ("redirect", "/new"), "/new": pg("new"), "/away": ("redirect", "https://elsewhere.invalid/x")}
    s2 = crawl(MappingFetcher(f2))
    assert s2.get("/old").location == "/new" and s2.get("/new").is_html and s2.get("/away") is None and s2.meta["skipped"]["/away"] == "redirect_off_origin"


def test_capture_removes_scripts_handlers_and_records_fidelity():
    html = pg('<main><p>Hi</p><button onclick="steal()">x</button><iframe src="https://e.invalid"></iframe><base href="https://e.invalid/"><meta http-equiv="refresh" content="0;url=https://e.invalid">'
              '<script>fetch("https://e.invalid")</script><script type="application/ld+json">{"a":1}</script></main>')
    body, c = capture_html(html, "/")
    text = body.decode()
    assert "<script>" not in text and "onclick" not in text and "iframe" not in text and "<base" not in text and "refresh" not in text and "ld+json" in text
    assert c == {"scripts": 1, "iframes": 1, "handlers": 1}
    spa = MappingFetcher({"/": '<html><body><div id="app"></div><script>render()</script></body></html>'})
    snap = crawl(spa)
    assert snap.meta["fidelity"]["level"] == "low" and snap.meta["fidelity"]["js_dependent_pages"] == ["/"]


def test_http_fetcher_enforces_origin_and_public_hosts():
    seen = []

    def handler(request):
        seen.append(str(request.url))
        if request.url.path == "/away":
            return httpx.Response(302, headers={"location": "https://elsewhere.invalid/x"})
        if request.url.path == "/big":
            return httpx.Response(200, headers={"content-type": "text/html"}, content=b"x" * 3_000_000)
        return httpx.Response(200, headers={"content-type": "text/html"}, content=b"<html><body>ok</body></html>")
    client = httpx.Client(transport=httpx.MockTransport(handler))
    f = HttpFetcher("http://127.0.0.1:9", allow_private_hosts=True, client=client)
    assert f.get("http://127.0.0.1:9/ok").status == 200
    assert len(f.get("http://127.0.0.1:9/big").body) <= 1_000_000
    assert f.get("http://127.0.0.1:9/away").location == "https://elsewhere.invalid/x"
    with pytest.raises(ValueError):
        f.get("http://elsewhere.invalid/")
    with pytest.raises(ValueError):
        HttpFetcher("http://127.0.0.1:9")                                          # loopback refused unless explicitly allowed (SSRF rule reused from the probe)
    with pytest.raises(ValueError):
        HttpFetcher("http://user:pw@example.com/")
    with pytest.raises(ValueError):
        HttpFetcher("ftp://example.com/")
    snap = Crawler(f).run()
    assert snap.get("/") is not None and all(u.startswith("http://127.0.0.1:9") for u in seen)


def test_delay_between_requests_is_applied():
    slept = []
    Crawler(site(), Limits(max_pages=3, delay_seconds=0.5), sleep=slept.append).run()
    assert slept and set(slept) == {0.5}
