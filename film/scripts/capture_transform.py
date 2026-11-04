"""Capture the material for Act 3 (the transformation). Zero cost, read-only.

  * Before (`polishedoriginal`) and After (`modifiedpolished`) frozen snapshots, served through the product's read-only mirror and rendered at
    2x in the agents' font environment (scripts/agent-fonts.sh), at the agents' 1265 px layout:
      - Before course page for FEATURED (a course the hero agent never reached): the "Course details" facts, each with its box;
      - After /courses: every card's box and, for every card, its fact rows (label, value, box);
      - the dead-end address on both versions (Before: not found; After: redirected to the course page);
      - After course page JSON-LD (the structured data, verbatim).
  * The recorded screenshot of the dead end itself (Before run eval-ea13944e, task 1, step 9: the agent guessed the address), from the public
    report API. That run's report is where the three recommendations came from (see modified_polished.py).

Writes public/captures/transform/** (gitignored) and data/transform.json (committed).
    PYTHONPATH=src python film/scripts/capture_transform.py
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import urllib.request
from pathlib import Path

FILM = Path(__file__).resolve().parents[1]
OUT = FILM / "public" / "captures" / "transform"
API = "https://209-38-84-72.sslip.io"
BEFORE_EVAL = "eval-ea13944e8ba5c08e8893426b2f8b1c8f"
FEATURED = "/courses/mindful-meditation"
DEAD_END = "/courses/introduction-to-python"
HERO_MATCHES = ["Wheel-thrown pottery", "Beginners yoga", "Mindful meditation", "Home electrical basics"]

FACTS_JS = """() => { const dts = [...document.querySelectorAll('dl.facts dt')];
  return dts.map(dt => { const dd = dt.nextElementSibling; const a = dt.getBoundingClientRect(), b = dd.getBoundingClientRect();
    return { label: dt.textContent.trim(), value: dd.textContent.trim(), box: { x: a.x, y: a.y + scrollY, width: b.right - a.x, height: Math.max(a.bottom, b.bottom) - a.y } }; }); }"""
CARDS_JS = """() => [...document.querySelectorAll('article.card')].map(card => { const r = card.getBoundingClientRect();
  return { name: card.querySelector('h2').textContent.trim(), box: { x: r.x, y: r.y + scrollY, width: r.width, height: r.height },
    facts: [...card.querySelectorAll('dl.card-facts > div')].map(d => { const q = d.getBoundingClientRect();
      return { label: d.querySelector('dt').textContent.trim(), value: d.querySelector('dd').textContent.trim(), box: { x: q.x, y: q.y + scrollY, width: q.width, height: q.height } }; }) }; })"""


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


async def main() -> None:
    from playwright.async_api import async_playwright

    from agent_readiness.investigate.sitemodel.server import Mirror
    from agent_readiness.scanner.serve import serve_app
    from agent_readiness.sites.larkspur import render
    OUT.mkdir(parents=True, exist_ok=True)
    conf = FILM / ".fonts" / "fonts.conf"
    if not conf.exists():
        raise SystemExit("run film/scripts/agent-fonts.sh first")
    files, data = {}, {}

    async def shot(page, name, full=False):
        png = await page.screenshot(full_page=full)
        (OUT / name).write_bytes(png)
        files[name] = sha(png)
        return f"captures/transform/{name}"

    async with async_playwright() as p:
        b = await p.chromium.launch(env={**os.environ, "FONTCONFIG_FILE": str(conf)})
        for variant, label in (("polishedoriginal", "before"), ("modifiedpolished", "after")):
            snap = render.snapshot(variant)
            async with serve_app(Mirror(snap)) as base:
                ctx = await b.new_context(viewport={"width": 1265, "height": 960}, device_scale_factor=2)
                page = await ctx.new_page()
                v = data.setdefault(label, {"snapshot_sha256": snap.sha256})
                await page.goto(base + FEATURED); await page.wait_for_load_state("networkidle")
                v["featured"] = {"path": FEATURED, "image": await shot(page, f"{label}-featured-page.png", full=True),
                                 "facts": await page.evaluate(FACTS_JS) if label == "before" else None,
                                 "height": await page.evaluate("document.documentElement.scrollHeight")}
                if label == "after":
                    lds = await page.eval_on_selector_all('script[type="application/ld+json"]', "els => els.map(e => e.textContent)")
                    v["featured"]["json_ld"] = [json.loads(x) for x in lds]
                await page.goto(base + "/courses"); await page.wait_for_load_state("networkidle")
                v["courses"] = {"image": await shot(page, f"{label}-courses-full.png", full=True), "cards": await page.evaluate(CARDS_JS),
                                "height": await page.evaluate("document.documentElement.scrollHeight")}
                resp = await page.goto(base + DEAD_END); await page.wait_for_load_state("networkidle")
                v["dead_end"] = {"requested": DEAD_END, "status": resp.status if resp else None,
                                 "final_path": "/" + page.url.split("/", 3)[3] if page.url.count("/") >= 3 else page.url,
                                 "image": await shot(page, f"{label}-dead-end.png")}
                await ctx.close()
        await b.close()

    # the recorded dead end (Before run, task 1)
    ev = json.loads(urllib.request.urlopen(f"{API}/api/lifecycle/evaluations/{BEFORE_EVAL}", timeout=60).read())
    trial = next(t for t in ev["trials"] if t["task"] == 1)
    tl = json.loads(urllib.request.urlopen(f"{API}/api/lifecycle/evaluations/{BEFORE_EVAL}/trials/{trial['id']}", timeout=60).read())
    step = next(s for s in tl["steps"] if s["path"] == DEAD_END)
    png = urllib.request.urlopen(f"{API}/api/lifecycle/evaluations/{BEFORE_EVAL}/trials/{trial['id']}/screenshots/{step['screenshot']}", timeout=60).read()
    (OUT / "recorded-dead-end.png").write_bytes(png)
    files["recorded-dead-end.png"] = sha(png)
    prev = next(s for s in tl["steps"] if s["step"] == step["step"] - 1)
    data["recorded_dead_end"] = {"evaluation": BEFORE_EVAL, "task": 1, "step": step["step"], "path": step["path"], "memory": step["memory"],
                                 "previous_action": [a["name"] + " " + str(a.get("target")) for a in prev["actions"]],
                                 "image": "captures/transform/recorded-dead-end.png"}
    data["hero_matches"] = HERO_MATCHES
    data["files"] = files
    (FILM / "data" / "transform.json").write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n")
    a = data["after"]
    print("before facts", [(f["label"], f["value"]) for f in data["before"]["featured"]["facts"]])
    print("after cards", len(a["courses"]["cards"]), "facts/card", {len(c["facts"]) for c in a["courses"]["cards"]}, "height", a["courses"]["height"], "before height", data["before"]["courses"]["height"])
    print("dead end", data["before"]["dead_end"]["status"], data["before"]["dead_end"]["final_path"], "->", a["dead_end"]["status"], a["dead_end"]["final_path"])
    print("recorded", data["recorded_dead_end"]["step"], data["recorded_dead_end"]["memory"][:120], data["recorded_dead_end"]["previous_action"])
    print("json-ld", [x.get("@type") for x in a["featured"]["json_ld"]])


if __name__ == "__main__":
    asyncio.run(main())
