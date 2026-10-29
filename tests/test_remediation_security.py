"""Security properties of the website audit: SSRF guards, redirect handling, response bounds, error redaction, API boundaries. Loopback test servers only; no internet."""
import asyncio

import httpx
import pytest
from fastapi import FastAPI, Response
from fastapi.responses import HTMLResponse, RedirectResponse

from agent_readiness.remediation.engine import build_report
from agent_readiness.remediation.probe import MAX_BODY_BYTES, SiteProbe, assert_public_host
from agent_readiness.scanner.serve import serve_app


@pytest.mark.parametrize("host", ["127.0.0.1", "localhost", "10.0.0.5", "192.168.1.10", "172.16.0.1", "169.254.169.254", "0.0.0.0", "[::1]"])
def test_private_and_metadata_hosts_are_refused_by_default(host):
    with pytest.raises(ValueError):
        SiteProbe(f"http://{host}/")                                                    # refused at construction, before any request


def test_credentials_in_the_url_and_non_http_schemes_are_refused():
    for url in ("http://user:pw@example.com/", "file:///etc/passwd", "ftp://example.com/", "http:///x", "javascript:alert(1)"):
        with pytest.raises(ValueError):
            SiteProbe(url, allow_private_hosts=True)


def test_public_address_check_accepts_a_public_ip_literal():
    assert_public_host("93.184.216.34")                                                 # public literal (no DNS needed)


def served(app):
    return serve_app(app)


def test_redirects_off_origin_are_not_followed_and_the_error_is_redacted():
    hits = {"other": 0}
    other = FastAPI()

    @other.get("/{p:path}")
    async def anywhere(p: str):
        hits["other"] += 1
        return HTMLResponse("<html><body>secret internal page</body></html>")

    async def go():
        async with served(other) as off_origin:
            app = FastAPI()

            @app.get("/", response_class=HTMLResponse)
            async def home():
                return f'<html><body><a href="{off_origin}/leak">elsewhere</a><a href="/jump">jump</a></body></html>'

            @app.get("/jump")
            async def jump():
                return RedirectResponse(f"{off_origin}/internal")
            async with served(app) as base:
                obs = await asyncio.to_thread(lambda: SiteProbe(base, allow_private_hosts=True).run())
                return base, obs, build_report(obs)
    base, obs, report = asyncio.run(go())
    assert hits["other"] == 0                                                           # neither the link nor the redirect reached the other origin
    assert any("left the audited origin" in e for e in obs.errors)
    assert base not in str(report["probe"]) and "127.0.0.1" not in str(report["probe"]["errors"])


def test_redirect_loops_are_bounded():
    async def go():
        app = FastAPI()

        @app.get("/")
        async def loop():
            return RedirectResponse("/")
        async with served(app) as base:
            return await asyncio.to_thread(lambda: SiteProbe(base, allow_private_hosts=True).run())
    obs = asyncio.run(go())
    assert obs.pages_fetched == 0 and any("too many redirects" in e for e in obs.errors)


def test_response_body_is_capped_and_non_html_is_skipped():
    async def go():
        app = FastAPI()

        @app.get("/", response_class=HTMLResponse)
        async def big():
            return "<html><body>" + ("x" * (3 * MAX_BODY_BYTES)) + "</body></html>"

        @app.get("/data")
        async def data():
            return Response(b"{}", media_type="application/json")
        async with served(app) as base:
            probe = SiteProbe(base, allow_private_hosts=True)
            status, html = await asyncio.to_thread(probe._get, base + "/")
            status2, html2 = await asyncio.to_thread(probe._get, base + "/data")
            return len(html), html2
    n, other = asyncio.run(go())
    assert n <= MAX_BODY_BYTES and other == ""


def test_page_and_depth_budget_bound_the_number_of_requests():
    count = {"n": 0}

    async def go():
        app = FastAPI()

        @app.get("/{path:path}", response_class=HTMLResponse)
        async def page(path: str):
            count["n"] += 1
            return "<html><body>" + "".join(f'<a href="/{path}/{i}">l{i}</a>' for i in range(20)) + "</body></html>"
        async with served(app) as base:
            await asyncio.to_thread(lambda: SiteProbe(base, allow_private_hosts=True, max_pages=10).run())
    asyncio.run(go())
    assert count["n"] <= 10 + 6                                                         # page cap (+ at most max_details extra fetches)


def test_audit_api_never_accepts_a_url_or_label_and_does_not_expose_internal_addresses(tmp_path):
    from fastapi.testclient import TestClient
    from agent_readiness.remediation.targets import TargetRegistry
    from agent_readiness.scanner.service import api as api_mod
    from agent_readiness.scanner.service.config import ScannerConfig
    targets = TargetRegistry.demo().start()
    try:
        cfg = ScannerConfig(data_dir=tmp_path, secret="s", admin_token="a", rate_limit_per_minute=1000)
        app = api_mod.create_scanner_app(cfg, targets=targets)
        c = TestClient(app)
        _, code = app.state.store.create_invitation("t")
        h = {"Authorization": "Bearer " + c.post("/api/session", json={"code": code}).json()["token"]}
        for body in ({"target_id": "http://169.254.169.254/latest/meta-data/"}, {"target_id": "demo-shop", "url": "http://169.254.169.254/"}, {"target_id": "../../etc/passwd"},
                     {"target_id": "demo-shop", "previous_audit_id": "../../../etc/passwd"}):
            assert c.post("/api/audits", headers=h, json=body).status_code in (404, 422)
        text = c.post("/api/audits", headers=h, json={"target_id": "demo-shop"}).text + c.get("/api/targets", headers=h).text
        assert "127.0.0.1" not in text and targets.get("demo-shop").base_url not in text           # internal address never leaves the service
        assert c.get("/api/audits/not-an-id", headers=h).status_code == 404
    finally:
        targets.stop()
