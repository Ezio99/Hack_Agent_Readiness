"""Capture the verification run for Act 4 and the product footage for Act 5. Read-only and zero cost: GET requests to the public report API, and
page loads of the deployed product in headless Chromium (no access code is entered; nothing is launched; no model is called).

  * The paired evaluation eval-1cf64d5e (Before and After in ONE job, same tasks, agent and limits): per-variant totals and per-task results
    (correct = post-hoc grader v2, the product's "Correct"; exact match = official grader v1, kept separately), and the hero task (task 2)
    traces of both versions with every recorded screenshot.
  * Product pages at 2x: the Live report for this run (overview and task 2), and the Workspace.

Writes public/captures/paired/** (gitignored) and data/paired.json (committed).
    python film/scripts/capture_paired.py
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import urllib.request
from pathlib import Path

FILM = Path(__file__).resolve().parents[1]
OUT = FILM / "public" / "captures" / "paired"
BASE = "https://209-38-84-72.sslip.io"
EVAL = "eval-1cf64d5eae90bcaeab531b4886140c14"
AUDIENCE = {"polishedoriginal": "Before", "modifiedpolished": "After"}
HERO = 2


def get(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=60) as r:
        return r.read()


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def record() -> dict:
    ev = json.loads(get(f"{BASE}/api/lifecycle/evaluations/{EVAL}"))
    variants = [v["name"] for v in ev["manifest"]["variants"]]
    assert set(variants) == set(AUDIENCE), variants
    out = {"evaluation": EVAL, "title": ev["title"], "mode": ev["mode"], "started_at": ev["started_at"], "finished_at": ev["finished_at"],
           "agent": ev["agent"], "frozen_suite_sha256": ev["frozen_suite"]["sha256"],
           "snapshots": {AUDIENCE[v["name"]]: v["snapshot_sha256"] for v in ev["manifest"]["variants"]},
           "limit": max(t["limits"]["max_model_requests"] for t in ev["tasks"]),
           "tasks": [{"n": t["n"], "customer_wording": t["customer_wording"]} for t in ev["tasks"]],
           "cost_basis": ev["cost"]["basis"], "settled_total_usd": ev["cost"]["settled_spend"]["settled_usd"], "versions": {}}
    for v in variants:
        ts = sorted((t for t in ev["trials"] if t["variant"] == v), key=lambda t: t["task"])
        out["versions"][AUDIENCE[v]] = {
            "correct": sum(t["grades"]["v2"]["passed"] for t in ts), "exact_match": sum(t["grades"]["v1"]["passed"] for t in ts),
            "requests": sum(t["metrics"]["model_requests"] for t in ts), "seconds": round(sum(t["metrics"]["elapsed_seconds"] for t in ts), 2),
            "cost_usd": ev["cost"]["by_variant"][v], "course_pages_opened": sum(t["navigation"]["item_pages_opened"] for t in ts),
            "tasks": [{"n": t["task"], "correct": t["grades"]["v2"]["passed"], "exact_match": t["grades"]["v1"]["passed"],
                       "requests": t["metrics"]["model_requests"], "seconds": t["metrics"]["elapsed_seconds"],
                       "course_pages_opened": t["navigation"]["item_pages_opened"], "answer": t["answer"], "trial": t["id"]} for t in ts]}
    # the hero task, both versions: every recorded step and screenshot
    OUT.mkdir(parents=True, exist_ok=True)
    out["hero"] = {}
    for v in variants:
        t = next(t for t in ev["trials"] if t["variant"] == v and t["task"] == HERO)
        tl = json.loads(get(f"{BASE}/api/lifecycle/evaluations/{EVAL}/trials/{t['id']}"))
        steps = []
        for s in tl["steps"]:
            png = get(f"{BASE}/api/lifecycle/evaluations/{EVAL}/trials/{t['id']}/screenshots/{s['screenshot']}")
            name = f"{AUDIENCE[v].lower()}-t{HERO}-{s['screenshot']}"
            (OUT / name).write_bytes(png)
            steps.append({"step": s["step"], "path": s["path"], "memory": s["memory"], "done": s["done"],
                          "actions": [{"name": a["name"], "target": a.get("target")} for a in s["actions"]],
                          "screenshot": f"captures/paired/{name}", "sha256": sha(png)})
        out["hero"][AUDIENCE[v]] = {"task": HERO, "answer": t["answer"], "correct": t["grades"]["v2"]["passed"],
                                    "requests": t["metrics"]["model_requests"], "seconds": t["metrics"]["elapsed_seconds"],
                                    "course_pages_opened": t["navigation"]["item_pages_opened"], "steps": steps}
    return out


async def product(meta: dict) -> None:
    from playwright.async_api import async_playwright
    pages = {"report": f"#/reports/{EVAL}", "report-t2": f"#/reports/{EVAL}/tasks/{HERO}", "live": "#/reports/latest", "workspace": "#/run"}
    meta["product"] = {}
    async with async_playwright() as p:
        b = await p.chromium.launch()
        ctx = await b.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=2)
        page = await ctx.new_page()
        for name, route in pages.items():
            await page.goto(f"{BASE}/{route}")
            await page.wait_for_load_state("networkidle")
            await page.wait_for_timeout(3000)
            png = await page.screenshot(full_page=True)
            (OUT / f"product-{name}.png").write_bytes(png)
            boxes = await page.evaluate("""() => { const out = {}; const pick = (k, el) => { if (!el) return; const r = el.getBoundingClientRect();
                out[k] = { x: r.x, y: r.y + scrollY, width: r.width, height: r.height }; };
              pick('title', document.querySelector('h1')); pick('sides', document.querySelector('.lc-sides'));
              pick('pairbars', document.querySelector('.lc-pair, .lc-bars, [class*=pair]'));
              document.querySelectorAll('section').forEach((s, i) => pick('section' + i, s)); return out; }""")
            # internal identifiers that must not appear on screen (e.g. the budget pool id): boxes to cover in the film
            redact = await page.evaluate(r"""() => { const out = []; const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
              while (w.nextNode()) { const n = w.currentNode, m = n.textContent.match(/ar-a20-[\w-]+/); if (!m) continue;
                const r = document.createRange(); r.setStart(n, m.index); r.setEnd(n, m.index + m[0].length); const b = r.getBoundingClientRect();
                out.push({ x: b.x, y: b.y + scrollY, width: b.width, height: b.height, reason: 'internal budget identifier' }); } return out; }""")
            meta["product"][name] = {"route": route, "redact": redact, "image": f"captures/paired/product-{name}.png", "sha256": sha(png),
                                     "height": await page.evaluate("document.documentElement.scrollHeight"), "boxes": boxes,
                                     "text": (await page.evaluate("document.querySelector('main')?.innerText || ''"))[:4000]}
        await b.close()


def main() -> None:
    meta = record()
    asyncio.run(product(meta))
    (FILM / "data" / "paired.json").write_text(json.dumps(meta, indent=1, ensure_ascii=False) + "\n")
    for k, v in meta["versions"].items():
        print(k, {x: v[x] for x in ("correct", "exact_match", "requests", "seconds", "cost_usd", "course_pages_opened")})
    print({k: len(v["steps"]) for k, v in meta["hero"].items()}, {k: list(v["boxes"]) for k, v in meta["product"].items()})


if __name__ == "__main__":
    main()
