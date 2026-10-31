"""Experiment-2 integration through real Chromium (needs loopback sockets and the installed browser; no credentials, no network, no spend). The scripted agent is NOT model behaviour: these tests only show
that the Ironbark snapshot renders from the read-only mirror and that tasks run through the unchanged trial runner and are graded independently."""
import asyncio

import pytest
from playwright.async_api import async_playwright

import json
from pathlib import Path

from agent_readiness.exp2 import evidence as E, flow, instances, pool as P, snapshot as S, study, tasks as T
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
    return instances.instance(study.public_task(c, part), instances.private_record(c), snap.sha256[:12], mock=True)


def _pick(pool):
    want = [("total_cost", "single"), ("availability", "category_weekend"), ("availability", "next_free"), ("compatibility", "fits_yesno"), ("kit_vs_items", "choice_own_gear"), ("discovery", "need")]
    return [next(c for c in pool.accepted if (c.family, c.sub) == w) for w in want]


def _evidence(c, rec):
    """Evidence sufficiency from what the trial stored the model as having seen (observations.json)."""
    obs = json.loads((Path(rec["artifact_path"]) / "observations.json").read_text())
    return E.assess(c.facts, obs)


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
        assert rec["outcome"]["run_status"] == "completed" and ev["passed"], (c.kind, c.question, rec["outcome"], ev)
        paths = [e["path"] for e in rec["mirror"]["log"]]
        assert set(c.visit) <= set(paths) and rec["mirror"]["blocked"] == [] and rec["trial"]["mode"] == "mock"
        assert _evidence(c, rec)["sufficient"], (c.question, _evidence(c, rec))      # needles written from the data match the text the model is really shown
    lazy = asyncio.run(_run_all(tmp_path, cands, "lazy"))
    assert lazy[0]["evaluation"]["passed"]
    for c, r in zip(cands, lazy):
        if c.family == "discovery":
            continue                                                                  # a featured item's summary is on the home page, so a discovery answer CAN be evidenced from the start page: the rule is about what was shown, not where
        assert not _evidence(c, r)["sufficient"], f"{c.family}/{c.sub}: answering after the start page only is not evidence-sufficient, even when correct"
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


def test_evidence_is_page_agnostic_and_arm_consistent_through_the_real_model_view(tmp_path):
    """Same scripted visit (the product page only) on two arms: the cost variant's product page carries the total, so the answer is evidenced; on the control the same view lacks the terms. The rule is identical."""
    pool, _ = P.build_pool()
    c = next(c for c in pool.accepted if c.family == "total_cost" and c.sub == "single" and c.params["waiver"] and len(c.facts[0].routes) == 2)      # a task whose total the cost variant displays
    product = f"/hire/{T.PRODUCT[c.params['p']].slug}"

    async def run(variant):
        snap = S.snapshot(variant)
        cand = type(c)(**{**c.__dict__, "visit": (product,)})
        return await run_trial(_instance(cand, snap), snap, provider="mock", output=tmp_path / variant)
    ctrl, cost = asyncio.run(run("control")), asyncio.run(run("cost"))
    assert ctrl["evaluation"]["passed"] and cost["evaluation"]["passed"], "correctness is graded the same way in both arms"
    assert not _evidence(c, ctrl)["sufficient"] and _evidence(c, ctrl)["missing"] == ["cost inputs"]
    assert _evidence(c, cost)["sufficient"], "the cost variant's product page alone shows the total (an alternative route)"
    assert ctrl["metrics"]["page_views"] == cost["metrics"]["page_views"], "efficiency is reported separately from evidence and correctness"
    terms = type(c)(**{**c.__dict__, "visit": (product, "/hire-terms")})
    snap = S.snapshot("control")
    both = asyncio.run(run_trial(_instance(terms, snap), snap, provider="mock", output=tmp_path / "control2"))
    assert _evidence(c, both)["sufficient"], "on the control, product page + terms page is the other route"


def test_a_correct_availability_answer_from_the_product_page_alone_is_not_sufficient_on_the_control(tmp_path):
    pool, _ = P.build_pool()
    c = next(c for c in pool.accepted if c.family == "availability" and c.sub == "day")
    product = f"/hire/{T.PRODUCT[c.params['p']].slug}"

    async def run(variant):
        snap = S.snapshot(variant)
        cand = type(c)(**{**c.__dict__, "visit": (product,)})
        return await run_trial(_instance(cand, snap), snap, provider="mock", output=tmp_path / variant)
    ctrl, avail = asyncio.run(run("control")), asyncio.run(run("availability"))
    assert not _evidence(c, ctrl)["sufficient"], "the control's product page says only whether the item is free today"
    assert _evidence(c, avail)["sufficient"], "the availability variant's 'Dates at a glance' panel is an alternative route"
