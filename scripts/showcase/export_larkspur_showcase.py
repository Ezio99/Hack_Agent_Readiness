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
# the featured live evaluation (Original vs Improved, the three-task judge suite) and the first live evaluation (Original vs Modified, six tasks).
# Frames: the steps the story shows (suite-local task numbers).
RUNS = {"live": ("eval-c04fdb100d6b1c877de96dabe76eb052", {("original", 2): (2, 9, 13), ("improved", 2): (1, 2), ("original", 1): (13,), ("improved", 1): (2,)}),
        "first_live": ("eval-e529db2aafecbfddd21e5c571eb85243", {("original", 1): (2, 12, 13), ("modified", 1): (2,)}),
        # Polished v1 evaluated alone (2026-11-04): task 2 is the friction trace (finder, 3 of 4 results visible, scroll, answer)
        "polished_v1": ("eval-abc5fc838a5428b6753a424e189ba1cc", {("polished", 2): (1, 2, 3, 4), ("polished", 1): (1, 2), ("polished", 3): (2,)}),
        # Polished v2 evaluated alone (2026-11-04): the same task 2 trace after the change (read options, select, submit, verify-scroll, answer)
        "polished_v2": ("eval-11ee8a1e6dad19998865db7187c8cb5e", {("polished2", 2): (1, 2, 3, 4, 5), ("polished2", 1): (1, 2), ("polished2", 3): (2,)}),
        # the corrected showcase: "Before" (Original redesigned) and "After" (its recommendations applied), each evaluated alone (2026-11-04)
        "before": ("eval-ea13944e8ba5c08e8893426b2f8b1c8f", {("polishedoriginal", 2): tuple(range(1, 12)), ("polishedoriginal", 1): (8, 9, 13),
                                                              ("polishedoriginal", 3): (12,)}),
        "after": ("eval-5cf934b372942da74f5157c5fca39fd6", {("modifiedpolished", 1): tuple(range(1, 15)), ("modifiedpolished", 2): tuple(range(1, 15)),
                                                             ("modifiedpolished", 3): tuple(range(1, 15))})}
PREVIEWS = [("original", "/courses"), ("modified", "/courses"), ("improved", "/courses"), ("improved", "/courses?level=Beginner&campus=&day=Weekend"),
            ("improved", "/courses/compare"), ("improved", "/courses/intro-to-python"), ("polished", "/courses"), ("polished", "/"),
            ("polished", "/courses/wheel-thrown-pottery"),
            ("polished", "/courses?level=Beginner&campus=&day=Weekend"), ("polished2", "/courses"), ("polished2", "/courses?level=Beginner&campus=&day=Weekend"),
            ("polishedoriginal", "/"), ("polishedoriginal", "/courses"), ("polishedoriginal", "/courses/wheel-thrown-pottery"),
            ("modifiedpolished", "/"), ("modifiedpolished", "/courses"), ("modifiedpolished", "/courses/wheel-thrown-pottery")]


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


def export_live(base: str, EVAL: str, FRAMES: dict) -> dict:
    ev = json.loads(_get(base, f"/api/lifecycle/evaluations/{EVAL}"))
    nav = ev["dimensions"]["navigation_efficiency"]["variants"]
    trials, journeys = [], {}
    for t in ev["trials"]:
        m = t["metrics"]
        trials.append({"task": t["task"], "variant": t["variant"], "passed": bool(t["grades"]["v1"]["passed"]), "correct": bool(t["grades"]["v2"]["passed"]),
                       "requests": m["model_requests"], "limit": m["request_limit"], "seconds": round(m["elapsed_seconds"], 1), "cost_usd": m["cost_usd"],
                       "dead_end": bool(t["reliability"].get("dead_end")), "path": t["navigation"]["visits"]})
        key = (t["variant"], t["task"])
        if key in FRAMES:
            tl = json.loads(_get(base, f"/api/lifecycle/evaluations/{EVAL}/trials/{t['id']}"))
            steps = []
            for s in tl["steps"]:
                frame = None
                if s.get("step") in FRAMES[key] and s.get("screenshot"):
                    frame = f"{EVAL[5:9]}-{t['variant']}-t{t['task']}-s{s['step']}"
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


async def _previews(only: set[str] | None = None) -> dict:
    from playwright.async_api import async_playwright

    from agent_readiness.investigate.sitemodel.server import Mirror
    from agent_readiness.scanner.serve import serve_app
    from agent_readiness.sites.larkspur import render
    out = {}
    async with async_playwright() as p:
        b = await p.chromium.launch()
        for variant in dict.fromkeys(v for v, _ in PREVIEWS):
            if only and variant not in only:
                continue
            snap = render.snapshot(variant)
            async with serve_app(Mirror(snap)) as base:
                page = await b.new_page(viewport={"width": 1280, "height": 960})
                for v, path in PREVIEWS:
                    if v != variant:
                        continue
                    await page.goto(base + path)
                    name = f"site-{variant}-{'courses' if path == '/courses' else 'home' if path == '/' else path.strip('/').replace('/', '-').split('?')[0] + ('-filter' if '?' in path else '')}"
                    (OUT / "frames" / f"{name}.webp").write_bytes(_webp(await page.screenshot()))
                    out[name] = {"variant": variant, "path": path, "snapshot_sha256": snap.sha256}
                await page.close()
        await b.close()
    return out


def page_audit() -> dict:
    """The product's structural page audit of each version (zero cost; the same rules the readiness report uses)."""
    from agent_readiness.diagnostics import structural as SD
    from agent_readiness.investigate.inspect.profile import build_profile
    from agent_readiness.sites.larkspur import render
    return {v: [f.title for f in SD.observe(build_profile(render.snapshot(v)), site="larkspur", version=v)] for v in ("original", "modified", "improved")}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--service", help="base URL of a view-only service on a copy of the production data, or the public site (GET only)")
    ap.add_argument("--runs", nargs="+", choices=sorted(RUNS), help="export only these runs (default: all); other runs' data and frames are kept")
    ap.add_argument("--preview-variants", nargs="+", help="render only these versions' previews; the others are kept as they are")
    a = ap.parse_args(argv)
    (OUT / "frames").mkdir(parents=True, exist_ok=True)
    target = OUT / "larkspur.json"
    data = json.loads(target.read_text()) if target.exists() else {}
    if a.service:
        for key in (a.runs or sorted(RUNS)):
            ev_id, frames = RUNS[key]
            for f in (OUT / "frames").glob(f"{ev_id[5:9]}-*-t*-s*.webp"):
                f.unlink()                                               # this run's frames are re-exported below
            data[key] = export_live(a.service.rstrip("/"), ev_id, frames)
    only = set(a.preview_variants) if a.preview_variants else None
    data["previews"] = {**({k: v for k, v in data.get("previews", {}).items() if only and v["variant"] not in only}), **asyncio.run(_previews(only))}
    data["page_audit"] = page_audit()
    target.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n")
    print(f"wrote {target.relative_to(ROOT)} and {len(list((OUT / 'frames').glob('*.webp')))} frames")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
