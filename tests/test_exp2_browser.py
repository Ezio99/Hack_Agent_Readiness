"""Experiment-2 integration through real Chromium (needs loopback sockets and the installed browser; no credentials, no network, no spend). The scripted agent is NOT model behaviour: these tests only show
that the Ironbark snapshot renders from the read-only mirror and that tasks run through the unchanged trial runner and are graded independently."""
import asyncio

import pytest
from playwright.async_api import async_playwright

from agent_readiness.exp2 import flow, instances, pool as P, snapshot as S, study, tasks as T
from agent_readiness.investigate.sitemodel.server import Mirror
from agent_readiness.investigate.trials.runner import run_trial
from agent_readiness.scanner.serve import serve_app

pytestmark = pytest.mark.browser


@pytest.mark.parametrize("variant,path,needle", [("control", "/", "Hire the right equipment"), ("control", "/hire/electric-demolition-hammer-15kg", "Electric demolition hammer 15 kg"),
                                                 ("control", "/hire/electric-demolition-hammer-15kg/availability", "Booked"), ("cost", "/hire/wet-tile-saw-250mm", "Your hire cost"),
                                                 ("discoverability", "/jobs/break-up-concrete", "Break up concrete")])
async def test_mirror_serves_the_snapshot_with_working_css_and_images(variant, path, needle):
    snap = S.snapshot(variant)
    async with serve_app(Mirror(snap)) as base, async_playwright() as p:
        b = await p.chromium.launch()
        page = await b.new_page(viewport={"width": 1280, "height": 900})
        problems = []
        page.on("console", lambda m: m.type == "error" and problems.append(m.text))
        page.on("requestfailed", lambda r: problems.append("failed " + r.url))
        page.on("response", lambda r: r.status >= 400 and problems.append(f"{r.status} {r.url}"))
        await page.goto(base + path)
        await page.wait_for_load_state("networkidle")
        assert needle in await page.inner_text("body")
        assert await page.evaluate("getComputedStyle(document.body).backgroundColor") == "rgb(246, 243, 236)", "the stylesheet was served and applied"
        imgs = await page.evaluate("[...document.images].map(i => [i.src, i.naturalWidth])")
        assert imgs and all(w > 0 for _, w in imgs), f"images did not load: {imgs}"
        assert problems == [], problems
        await b.close()


def _instance(c: T.Candidate, snap, part="investigation"):
    return instances.instance(study.public_task(c, part), instances.private_record(c), snap.sha256[:12])


def _pick(pool):
    want = [("total_cost", "single"), ("availability", "category_weekend"), ("availability", "next_free"), ("compatibility", "fits_yesno"), ("kit_vs_items", "choice_own_gear"), ("discovery", "need")]
    return [next(c for c in pool.accepted if (c.family, c.sub) == w) for w in want]


async def _run_all(tmp_path, cands, behavior):
    snap = S.snapshot("control")
    out = []
    for i, c in enumerate(cands):
        out.append(await run_trial(_instance(c, snap), snap, provider="mock", mock_behavior=behavior, output=tmp_path / f"{behavior}-{i}"))
    return out


def test_every_answer_kind_runs_through_the_unchanged_runner_and_is_graded_independently(tmp_path):
    pool, _ = P.build_pool()
    cands = _pick(pool)
    assert {c.kind for c in cands} >= {"money", "products", "date", "yesno", "choice", "product"}
    good = asyncio.run(_run_all(tmp_path, cands, "correct"))
    for c, rec in zip(cands, good):
        ev = rec["evaluation"]
        assert rec["outcome"]["run_status"] == "completed" and ev["passed"] and ev["evidence_backed"], (c.kind, c.question, rec["outcome"], ev)
        paths = [e["path"] for e in rec["mirror"]["log"]]
        assert set(c.evidence) <= set(paths) and rec["mirror"]["blocked"] == [] and rec["trial"]["mode"] == "mock"
    lazy = asyncio.run(_run_all(tmp_path, cands[:1], "lazy"))
    assert lazy[0]["evaluation"]["passed"] and not lazy[0]["evaluation"]["evidence_backed"], "a correct answer without visiting the evidence pages is not evidence-backed"
    wrong = asyncio.run(_run_all(tmp_path, cands[:2], "wrong"))
    assert all(not r["evaluation"]["passed"] for r in wrong)


def test_the_driver_runs_the_pilot_in_mock_mode_then_waits_at_the_owner_checkpoint(tmp_path):
    run, pipe, ctx = flow.build(tmp_path, "mock", mode="mock", options={"quotas": {f: 1 for f in T.FAMILIES}, "pilot_trials": 2, "repeat_tasks": 1})
    r = pipe.run(ctx)
    assert (r.status, r.stage) == ("awaiting_approval", "pilot_review")
    assert run.status("baseline_pilot") == "done" and len([p for p in (run.dir / "artifacts" / "trials").glob("baseline-*.json")]) == 2
    for p in (run.dir / "artifacts" / "trials").glob("baseline-*.json"):
        rec = run.artifact(f"trials/{p.stem}")
        assert rec["trial"]["mode"] == "mock" and rec["trial"]["snapshot_sha256"] == S.snapshot("control").sha256 and rec["evaluation"]["evidence_backed"]
    assert run.ledger(20.0).entries() == [], "mock mode never reserves or spends"
    run.approve("pilot_review", r.manifest_sha256, "test")
    assert pipe.run(ctx, until="pilot_review").status == "done" and run.has_artifact("main-plan")
