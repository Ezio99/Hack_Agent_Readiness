"""Export the recorded Larkspur evidence the static showcase pages use (Home and the Lifecycle story must render without the API).

Two sources, both zero cost:
  1. the paid live evaluation `eval-e529db2a…` as the product serves it: run the service in view-only mode on a COPY of the production data, e.g.
         AR_HOSTED_MODE=disabled AR_HOSTED_DATA=<copy>/hosted AR_PORT=8765 python -m agent_readiness.hosted.serve
     then pass --service http://127.0.0.1:8765. Only fields the public report already shows are kept (task wording, per-trial metrics, the agent's
     own answers and step notes, official grades); recorded screenshots are converted to WebP unchanged in content.
  2. previews of the Larkspur website versions (original, modified, improved), rendered from their frozen snapshots through the same read-only
     mirror the jailed browser uses, in headless Chromium.

    python scripts/showcase/export_larkspur_showcase.py --service http://127.0.0.1:8765
"""
from __future__ import annotations

import argparse
import asyncio
import io
import json
import urllib.request
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "dashboard" / "src" / "site" / "showcase"
EVAL = "eval-e529db2aafecbfddd21e5c571eb85243"
# the steps the story shows: task 1 on Original (the agent runs out of requests) and on Modified (answered from the listing)
FRAMES = {("original", 1): (2, 12, 13), ("modified", 1): (2,)}
PREVIEWS = [("original", "/courses"), ("modified", "/courses"), ("improved", "/courses"), ("improved", "/courses?level=Beginner&campus=&day=Weekend"),
            ("improved", "/courses/compare"), ("improved", "/courses/intro-to-python")]


def _get(base: str, path: str):
    with urllib.request.urlopen(base + path, timeout=30) as r:
        return r.read()


def _webp(png: bytes, width: int = 960) -> bytes:
    im = Image.open(io.BytesIO(png)).convert("RGB")
    if im.width > width:
        im = im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "WEBP", quality=80, method=6)
    return buf.getvalue()


def export_live(base: str) -> dict:
    ev = json.loads(_get(base, f"/api/lifecycle/evaluations/{EVAL}"))
    nav = ev["dimensions"]["navigation_efficiency"]["variants"]
    trials, journeys = [], {}
    for t in ev["trials"]:
        m = t["metrics"]
        trials.append({"task": t["task"], "variant": t["variant"], "passed": bool(t["grades"]["v1"]["passed"]), "correct": bool(t["grades"]["v2"]["passed"]),
                       "requests": m["model_requests"], "limit": m["request_limit"], "seconds": round(m["elapsed_seconds"], 1), "cost_usd": m["cost_usd"],
                       "dead_end": bool(t["reliability"].get("dead_end"))})
        key = (t["variant"], t["task"])
        if key in FRAMES:
            tl = json.loads(_get(base, f"/api/lifecycle/evaluations/{EVAL}/trials/{t['id']}"))
            steps = []
            for s in tl["steps"]:
                frame = None
                if s.get("step") in FRAMES[key] and s.get("screenshot"):
                    frame = f"{t['variant']}-t{t['task']}-s{s['step']}"
                    (OUT / "frames" / f"{frame}.webp").write_bytes(_webp(_get(base, f"/api/lifecycle/evaluations/{EVAL}/trials/{t['id']}/screenshots/{s['screenshot']}")))
                steps.append({"step": s.get("step"), "path": s.get("path"), "memory": s.get("memory"), "goal": s.get("goal"), "frame": frame})
            journeys[f"{t['variant']}-{t['task']}"] = {"answer": t["answer"], "steps": steps}
    return {"id": EVAL, "title": ev["title"], "started_at": ev["started_at"], "finished_at": ev["finished_at"],
            "agent": {k: ev["agent"].get(k) for k in ("model", "reasoning_effort", "max_completion_tokens", "profile")},
            "cost_usd": ev["cost"]["settled_spend"]["settled_usd"] if ev["cost"].get("settled_spend") else ev["cost"]["total_usd"],
            "tasks": [{"n": t["n"], "task_id": t["task_id"], "wording": t["customer_wording"], "capability": t.get("capability")} for t in ev["tasks"] if t.get("executed", True)],
            "totals": {v: {"requests": x["model_requests_total"], "seconds": round(x["elapsed_seconds_total"]), "cost_usd": round(x["cost_usd_total"], 6)} for v, x in nav.items()},
            "passed": {v: x["v1_passed"] for v, x in ev["dimensions"]["task_success"]["variants"].items()},
            "correct": {v: x["v2_passed"] for v, x in ev["dimensions"]["task_success"]["variants"].items()},
            "trials": trials, "journeys": journeys}


async def _previews() -> dict:
    from playwright.async_api import async_playwright

    from agent_readiness.investigate.sitemodel.server import Mirror
    from agent_readiness.scanner.serve import serve_app
    from agent_readiness.sites.larkspur import render
    out = {}
    async with async_playwright() as p:
        b = await p.chromium.launch()
        for variant in ("original", "modified", "improved"):
            snap = render.snapshot(variant)
            async with serve_app(Mirror(snap)) as base:
                page = await b.new_page(viewport={"width": 1280, "height": 960})
                for v, path in PREVIEWS:
                    if v != variant:
                        continue
                    await page.goto(base + path)
                    name = f"site-{variant}-{'courses' if path == '/courses' else path.strip('/').replace('/', '-').split('?')[0] + ('-filter' if '?' in path else '')}"
                    (OUT / "frames" / f"{name}.webp").write_bytes(_webp(await page.screenshot()))
                    out[name] = {"variant": variant, "path": path, "snapshot_sha256": snap.sha256}
                await page.close()
        await b.close()
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--service", help="base URL of a view-only service on a copy of the production data (omit to refresh only the site previews)")
    a = ap.parse_args(argv)
    (OUT / "frames").mkdir(parents=True, exist_ok=True)
    target = OUT / "larkspur.json"
    data = json.loads(target.read_text()) if target.exists() else {}
    if a.service:
        data["live"] = export_live(a.service.rstrip("/"))
    data["previews"] = asyncio.run(_previews())
    target.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n")
    print(f"wrote {target.relative_to(ROOT)} and {len(list((OUT / 'frames').glob('*.webp')))} frames")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
