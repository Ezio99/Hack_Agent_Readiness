#!/usr/bin/env python3
"""Fresh-browser smoke test of the PRODUCTION build served under a GitHub-Pages-style sub-path (local only; uses the repo's Playwright/Chromium).

    npm run build                                   # in dashboard/
    python3 scripts/smoke_dist.py                   # public build WITHOUT replay data (the default, publishable configuration)
    python3 scripts/smoke_dist.py --with-local-replays   # copies the Git-ignored local export into a TEMPORARY copy of dist/ (never into the repo)

Each scenario uses a new browser context (no cache, cookies or storage). Exit status 1 on any failure."""
import functools
import http.server
import re
import shutil
import sys
import tempfile
import threading
from pathlib import Path

from playwright.sync_api import sync_playwright

DASH = Path(__file__).resolve().parents[1]
DIST = DASH / "dist"
LOCAL_REPLAYS = DASH / "public" / "replays"
PREFIX = "/Hack_Agent_Readiness/"          # GitHub Pages project-site base path


def serve(root: Path):
    """Serve `root` under PREFIX only (anything outside PREFIX is a 404), like a Pages project site."""
    class H(http.server.SimpleHTTPRequestHandler):
        def translate_path(self, path):
            path = path.split("?", 1)[0].split("#", 1)[0]
            return str(root / path[len(PREFIX):]) if path.startswith(PREFIX) else str(root / "__outside__")
        def log_message(self, *a): pass
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}{PREFIX}"


def run(with_replays: bool) -> list[str]:
    failures: list[str] = []
    tmp = Path(tempfile.mkdtemp(prefix="dist-smoke-"))
    site = tmp / "site"
    shutil.copytree(DIST, site)
    shutil.rmtree(site / "replays", ignore_errors=True)   # the scenario decides whether replay data exists (the repo's dist/ is never modified)
    if with_replays:
        shutil.copytree(LOCAL_REPLAYS, site / "replays")
    srv, base = serve(site)
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            def fresh():
                ctx = browser.new_context(viewport={"width": 1280, "height": 900})
                page = ctx.new_page()
                errors, failed = [], []
                page.on("pageerror", lambda e: errors.append(str(e)))
                page.on("requestfailed", lambda r: failed.append(r.url))
                page.on("response", lambda r: failed.append(f"{r.status} {r.url}") if r.status >= 400 else None)
                return ctx, page, errors, failed
            def check(cond, msg):
                if not cond:
                    failures.append(msg)
            # 1. landing page, navigation, refresh on a deep hash route
            ctx, page, errors, failed = fresh()
            page.goto(base)
            page.wait_for_selector("h1")
            check("Recorded experiment data" in page.content(), "overview lacks the recorded-data banner")
            check("29 / 30" in page.inner_text("main"), "overview headline missing")
            for tab, marker in (("Scope comparison", "Compare by scope"), ("Evidence & method", "Evidence and method"), ("Recorded replay", "Recorded replay")):
                page.get_by_role("link", name=tab).click()
                page.wait_for_selector(f"h1:has-text('{marker}')")
            page.goto(base + "#/scopes"); page.reload(); page.wait_for_selector("h1:has-text('Compare by scope')")
            check(page.url.endswith("#/scopes"), "refresh did not preserve the hash route")
            page.goto(base + "#/evidence"); page.reload(); page.wait_for_selector("h1:has-text('Evidence and method')")
            page.get_by_role("link", name="Scope comparison").click(); page.get_by_label("Fern (rank 3)").check()
            check("verification shortfall 2" in page.inner_text("main"), "Fern scope does not show run 27's verification shortfall")
            # 2. replay behaviour
            page.goto(base + "#/replay")
            if with_replays:
                page.wait_for_selector("text=Step 1 of 12", timeout=10000)
                body = page.inner_text("main")
                check("Recorded experiment replay — not live inference" in body, "replay label missing")
                page.get_by_label(re.compile("^Step 4:")).click()
                check("Agent–tool interface gap at this step" in page.inner_text("main"), "run 27 visibility gap not shown")
                check("not reported — not meaningful" in body, "run 27 residual not marked not meaningful")
                check("finish" not in body.lower().split("response format")[1][:200] if "response format" in body.lower() else True, "finish reason leaked into UI")
            else:
                page.wait_for_selector("text=Replay data is not included in this build", timeout=10000)
                check("Nothing is faked" in page.inner_text("main"), "no-data fallback wording missing")
            # only the optional replay manifest may 404 in the no-data build
            unexpected = [u for u in failed if not (not with_replays and u.endswith("replays/manifest.json"))]
            check(not errors, f"page errors: {errors}")
            check(not unexpected, f"unexpected failed requests: {unexpected}")
            ctx.close()
            # 3. every request stays under the base path (no absolute-root asset URLs)
            ctx, page, errors, failed = fresh()
            urls = []
            page.on("request", lambda r: urls.append(r.url))
            page.goto(base); page.wait_for_selector("h1")
            outside = [u for u in urls if u.startswith("http://127.0.0.1") and PREFIX not in u]
            check(not outside, f"requests outside the base path: {outside}")
            ctx.close(); browser.close()
    finally:
        srv.shutdown(); shutil.rmtree(tmp, ignore_errors=True)
    return failures


if __name__ == "__main__":
    if not DIST.exists():
        sys.exit("dist/ not found: run `npm run build` in dashboard/ first")
    with_replays = "--with-local-replays" in sys.argv
    if with_replays and not LOCAL_REPLAYS.exists():
        sys.exit("no local replay export found; run export_replay.py first")
    result = run(with_replays)
    print(f"smoke ({'with local replays in a temp copy' if with_replays else 'public build without replay data'}):", "PASSED" if not result else "FAILED")
    for r in result:
        print(" -", r)
    sys.exit(1 if result else 0)
