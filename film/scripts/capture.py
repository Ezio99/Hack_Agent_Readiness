"""Capture the film's source material. Zero cost and read-only: nothing is written to production, no model is called.

  1. Website: the frozen "Before" Larkspur snapshot (`polishedoriginal`, the exact pages the agents browsed), served through the same read-only
     mirror the jailed browser uses and rendered in headless Chromium at the agents' viewport (1280x960) with device scale factor 2, in the agents' font environment (scripts/agent-fonts.sh).
  2. Evidence: the recorded hero-task trials (task 2, "Beginner courses on Saturday or Sunday") of the two live 4 Nov 2026 evaluations, from the
     public report API: the agent's own screenshots (unchanged bytes) and step records (path, notes, actions).
  3. Fonts: the product's OFL fonts (Newsreader, Geist, Geist Mono) with their licences.

Writes film/public/captures/** (gitignored, regenerable) and film/data/evidence.json (committed: numbers, quotes and SHA-256 of every file).

    PYTHONPATH=src python film/scripts/capture.py [--api https://209-38-84-72.sslip.io]
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import shutil
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FILM = ROOT / "film"
CAP = FILM / "public" / "captures"
BEFORE_EVAL = "eval-ea13944e8ba5c08e8893426b2f8b1c8f"   # Before, live 4 Nov 2026 (AEDT)
AFTER_EVAL = "eval-5cf934b372942da74f5157c5fca39fd6"    # After, live 4 Nov 2026 (AEDT)
HERO_TASK = 2
SITE_PAGES = [("/", "home"), ("/courses", "courses"), ("/courses/watercolour-foundations", "course-watercolour")]
# Click targets the agent actually used (Before, task 2: step 1 clicks "Browse all courses", step 2 clicks "Watercolour foundations"), and the cards.
BOXES = {"/": [("home.browse_all", 'a:text-is("Browse all courses")')],
         "/courses": [("courses.watercolour_link", 'a:text-is("Watercolour foundations")'), ("courses.cards", "article.card")]}
AUDIENCE = {"polishedoriginal": "Before", "modifiedpolished": "After"}


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def get(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=60) as r:
        return r.read()


async def capture_site() -> dict:
    from playwright.async_api import async_playwright

    from agent_readiness.investigate.sitemodel.server import Mirror
    from agent_readiness.scanner.serve import serve_app
    from agent_readiness.sites.larkspur import render

    out_dir = CAP / "site"
    out_dir.mkdir(parents=True, exist_ok=True)
    snap = render.snapshot("polishedoriginal")
    files = {}
    async with async_playwright() as p:
        conf = FILM / ".fonts" / "fonts.conf"
        if not conf.exists():
            raise SystemExit("run film/scripts/agent-fonts.sh first (the agents' font environment)")
        b = await p.chromium.launch(env={**os.environ, "FONTCONFIG_FILE": str(conf)})
        async with serve_app(Mirror(snap)) as base:
            ctx = await b.new_context(viewport={"width": 1265, "height": 960}, device_scale_factor=2)
            page = await ctx.new_page()
            boxes = {}
            for path, name in SITE_PAGES:
                await page.goto(base + path)
                await page.wait_for_load_state("networkidle")
                for key, sel in BOXES.get(path, []):
                    els = await page.query_selector_all(sel)
                    boxes[key] = [await el.bounding_box() for el in els]
                for kind, full in (("view", False), ("full", True)):
                    png = await page.screenshot(full_page=full)
                    f = out_dir / f"before-{name}-{kind}.png"
                    f.write_bytes(png)
                    files[f.name] = {"path": path, "full_page": full, "sha256": sha(png)}
            await ctx.close()
        await b.close()
    return {"version": "Before", "snapshot_sha256": snap.sha256, "viewport": [1265, 960], "note": "1265 = the agents' 1280 px window minus its 15 px scrollbar, so layouts match the recorded screenshots", "device_scale_factor": 2, "files": files,
            "boxes": boxes, "boxes_note": "CSS px at scroll 0 in the 1265 px layout = the agents' screenshot coordinates"}


def capture_trial(api: str, eval_id: str) -> dict:
    ev = json.loads(get(f"{api}/api/lifecycle/evaluations/{eval_id}"))
    trial = next(t for t in ev["trials"] if t["task"] == HERO_TASK)
    task = next(t for t in ev["tasks"] if t["n"] == HERO_TASK)
    version = AUDIENCE[trial["variant"]]
    tl = json.loads(get(f"{api}/api/lifecycle/evaluations/{eval_id}/trials/{trial['id']}"))
    out_dir = CAP / "evidence" / f"{version.lower()}-t{HERO_TASK}"
    out_dir.mkdir(parents=True, exist_ok=True)
    steps = []
    for s in tl["steps"]:
        png = get(f"{api}/api/lifecycle/evaluations/{eval_id}/trials/{trial['id']}/screenshots/{s['screenshot']}")
        (out_dir / s["screenshot"]).write_bytes(png)
        steps.append({"step": s["step"], "path": s["path"], "memory": s["memory"], "goal": s["goal"],
                      "actions": [{"name": a["name"], "target": a.get("target")} for a in s["actions"]],
                      "done": s["done"], "screenshot": f"captures/evidence/{version.lower()}-t{HERO_TASK}/{s['screenshot']}", "sha256": sha(png)})
    m = trial["metrics"]
    return {"evaluation": eval_id, "site_domain": ev["site"]["domain"], "version": version, "mode": ev["mode"], "started_at": ev["started_at"], "agent": ev["agent"],
            "task": {"n": HERO_TASK, "customer_wording": task["customer_wording"], "max_model_requests": task["limits"]["max_model_requests"]},
            "answer": trial["answer"], "correct_v2": trial["grades"]["v2"]["passed"], "official_v1": trial["grades"]["v1"]["passed"],
            "metrics": {"model_requests": m["model_requests"], "steps": m["steps"], "elapsed_seconds": m["elapsed_seconds"],
                        "course_pages_opened": trial["navigation"]["item_pages_opened"]},
            "steps": steps}


def copy_fonts() -> None:
    src = ROOT / "dashboard" / "src" / "site" / "fonts"
    dst = FILM / "public" / "fonts"
    dst.mkdir(parents=True, exist_ok=True)
    for f in src.iterdir():
        shutil.copy2(f, dst / f.name)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default="https://209-38-84-72.sslip.io")
    a = ap.parse_args()
    copy_fonts()
    site = asyncio.run(capture_site())
    evidence = {"note": "Generated by film/scripts/capture.py from the frozen snapshot and the public report API. Do not edit by hand.",
                "site": site, "hero": {"before": capture_trial(a.api, BEFORE_EVAL), "after": capture_trial(a.api, AFTER_EVAL)}}
    (FILM / "data").mkdir(exist_ok=True)
    (FILM / "data" / "evidence.json").write_text(json.dumps(evidence, indent=1, ensure_ascii=False) + "\n")
    print("site files", len(site["files"]), "| before steps", len(evidence["hero"]["before"]["steps"]), "| after steps", len(evidence["hero"]["after"]["steps"]))


if __name__ == "__main__":
    main()
