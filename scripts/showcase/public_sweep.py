"""Read-only sweep of every public route on the live site (or a local build via --local), desktop 1440x900 and mobile 390x844: fails on
internal terms in visible text, console/page errors, non-GET requests, broken images, horizontal overflow or empty pages.
    uv run python scripts/showcase/public_sweep.py https://209-38-84-72.sslip.io/
Update P/B/A (paired, Before, After run ids) when the featured runs change."""
import re, sys
from playwright.sync_api import sync_playwright
base = sys.argv[1]
P, B, A = "eval-1cf64d5eae90bcaeab531b4886140c14", "eval-ea13944e8ba5c08e8893426b2f8b1c8f", "eval-5cf934b372942da74f5157c5fca39fd6"
PUBLIC = ["#/", "#/how", "#/showcase", "#/lifecycle", "#/lifecycle/review", "#/lifecycle/compare", "#/run", f"#/run/{P}", "#/reports/latest", f"#/reports/{P}",
          f"#/reports/{P}/tasks/1", f"#/reports/{P}/tasks/2", f"#/reports/{B}", f"#/reports/{A}", f"#/reports/{B}/tasks/1"]
BAD = re.compile(r"Ironbark|Original vs|Improved|Earlier|Archive|[Pp]olished|owner|persona|career_switcher|budget_learner|Not covered by this task set|listing_field|agent_done|profile suite|larkspur-core|official grader|recorded rule|programme|ceiling|operators")
fails = []
with sync_playwright() as pw:
    b = pw.chromium.launch()
    for w, h, tag in ((1440, 900, "desktop"), (390, 844, "mobile")):
        for r in PUBLIC:
            c = b.new_context(viewport={"width": w, "height": h}); pg = c.new_page(); errs, writes = [], []
            pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None); pg.on("pageerror", lambda e: errs.append(str(e)))
            pg.on("request", lambda q: writes.append(q.method) if q.method not in ("GET", "HEAD") else None)
            pg.goto(base + r); pg.wait_for_timeout(4000)
            pg.evaluate("document.querySelectorAll('details').forEach(d => d.open = true)"); pg.wait_for_timeout(300)
            if r.startswith("#/run/"):
                for t in ("Agent runs", "Readiness report"):
                    tab = pg.get_by_role("tab", name=t)
                    if tab.count(): tab.click(); pg.wait_for_timeout(2500)
                pg.evaluate("document.querySelectorAll('details').forEach(d => d.open = true)")
            txt = pg.inner_text("body")
            hits = sorted(set(BAD.findall(txt)))
            broken = pg.eval_on_selector_all("img", "els => els.filter(i => i.complete && i.getAttribute('loading') !== 'lazy' && i.naturalWidth === 0).length")
            sw = pg.evaluate("document.documentElement.scrollWidth")
            bad = hits or errs or writes or broken or sw > w + 1 or len(txt) < 300
            if bad: fails.append((tag, r))
            print(f"{tag:7} {r:56} {'BAD' if bad else 'ok '} chars {len(txt):5} hits {hits} broken {broken} sw {sw} errs {errs[:1]} writes {writes[:1]}")
            c.close()
    b.close()
print("FAILS", fails)
