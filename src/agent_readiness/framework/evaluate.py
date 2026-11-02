"""Reusable evaluation orchestration: one interface for every `SiteDefinition`, with no site-specific branching.

    prepare(site, root)            site definition -> generated, independently validated tasks -> frozen manifest, persisted as a standard
                                   investigation run (snapshot, site profile, tasks-manifest, private criteria, provenance)
    execute(run, provider=...)     every scoring-eligible task on every site variant through the existing trial runner
                                   (`investigate.trials.runner.run_trial`: real Browser Use agent, real Chromium, the snapshot served on loopback),
                                   each model request behind the reserve-before-send `RequestGate`; trial records persisted in the standard format
    results(run)                   frozen grader_v1 grades as recorded, grader_v2 post-hoc view (`grading.rescore`, with the v1 reproduction check),
                                   per-variant totals, provenance

ZERO COST ONLY. provider='dev' is the loopback dev provider (`live.devprovider`: NOT a model; it replays a scripted agent built from the run's own
frozen tasks over real HTTP); provider='mock' is the in-process scripted agent (behaviours correct | wrong | lazy). Any non-loopback endpoint is refused.
Isolated from the hosted Ironbark path (nothing in `hosted/` imports this module).

    python -m agent_readiness.framework.evaluate SITE --root DIR [--provider dev|mock] [--behavior correct|wrong]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import socket
import sys
import threading
import uuid
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlsplit

from ..agent import ModelConfig
from ..grading import rescore
from ..investigate.evaluate.stage import still_valid
from ..investigate.inspect.stage import run_inspect
from ..investigate.pipeline import Context
from ..investigate.run import InvestigationRun
from ..investigate.taskgen import freeze as freezer
from ..investigate.trials.runner import run_trial
from ..investigate.trials.stage import VOID_STATUSES
from ..spend_gate import RequestGate
from ..suite.core import canonical_hash
from . import generate as G
from .site import SiteDefinition, get

SCHEMA = "framework-evaluation-v1"
PROVIDERS = ("dev", "mock")
DEV_KEY = "dev-provider-not-a-key-0000000000000000"
FIXTURE_LEDGER_CEILING_USD = 5.0          # dev-provider "spend" is calculated from fixture token counts (no money moves); the gate and ledger still run
PER_REQUEST_CAP_USD = 0.05
LOOPBACK = ("127.0.0.1", "localhost", "::1")


def _loopback(url: str) -> str:
    if urlsplit(url).hostname not in LOOPBACK:
        raise ValueError(f"refused: {url!r} is not a loopback endpoint; this orchestrator never calls a real model")
    return url


def prepare(site: SiteDefinition | str, root: Path, *, provider: str = "dev", run_id: str | None = None) -> InvestigationRun:
    if provider not in PROVIDERS:
        raise ValueError(f"provider must be one of {PROVIDERS}")
    site = get(site) if isinstance(site, str) else site
    ts = G.generate(site)
    manifest, private = G.freeze_eligible(ts)
    base = site.variants[0]
    run_id = run_id or f"fw-{site.id}-{uuid.uuid4().hex[:10]}"
    run = InvestigationRun.create(Path(root), run_id, target=site.id, mode="live" if provider == "dev" else "mock", stages=("inspect", "freeze", "trials"),
                                  config={"framework": SCHEMA, "site": site.id, "provider": provider, "variants": list(site.variants)})
    run_inspect(Context(run), site.snapshot(base))                       # snapshot + site profile, exactly as the investigation pipeline stores them
    run.write_private("criteria", private)
    run.write_artifact("tasks-manifest", manifest)
    if provider == "dev":
        run.write_artifact("dev-provider", {"loopback_stand_in": True})   # every report/export of this run leads with the dev-fixture notice
    run.write_artifact("framework-taskset", G.public(ts))
    run.write_artifact("framework-provenance", {
        "schema": SCHEMA, "site": {"id": site.id, "label": site.label, "domain": site.domain, "controlled": site.controlled},
        "variants": {v: site.snapshot(v).sha256 for v in site.variants}, "generated_on": base,
        "oracle": ts["oracle"], "task_generation": ts["generator"], "verifiability_counts": ts["counts"],
        "tasks_manifest_sha256": canonical_hash(manifest), "criteria_sha256": manifest["criteria_sha256"],
        "graders": {"official": rescore.v2.GRADER_V1, "post_hoc": {"id": rescore.v2.GRADER_ID, "version": rescore.v2.GRADER_VERSION, "derivation_id": rescore.derivation_id()}},
        "agent": {"provider": provider, "model": "dev provider fixture (NOT a model)" if provider == "dev" else "in-process scripted agent (NOT a model)",
                  "profile": manifest["agent_profile"]}})
    freezer.load(run)                                                     # the frozen manifest, criteria and snapshot verify against each other
    return run


class _PinnedDevProvider:
    """The dev provider, answering for exactly this run (the stock one picks the newest live-* run under its root)."""

    def __init__(self, run: InvestigationRun):
        from ..live.devprovider import DevProvider
        provider = DevProvider(run.dir.parent)
        provider.run = lambda: run
        self.provider = provider


@contextmanager
def dev_provider(run: InvestigationRun):
    import uvicorn
    from ..live.devprovider import make_app
    prov = _PinnedDevProvider(run).provider
    sock = socket.create_server(("127.0.0.1", 0))
    server = uvicorn.Server(uvicorn.Config(make_app(prov), log_level="error", lifespan="off"))
    thread = threading.Thread(target=lambda: server.run(sockets=[sock]), daemon=True)
    thread.start()
    try:
        yield prov, f"http://127.0.0.1:{sock.getsockname()[1]}/v1"
    finally:
        server.should_exit = True
        thread.join(timeout=10)


def _plan(run: InvestigationRun, site: SiteDefinition) -> tuple[list[dict], list[dict]]:
    """(steps, exclusions): every eligible task on every variant. A non-base variant uses the private record re-derived on that variant
    (same question and answer; evidence pages may legitimately move); a task whose answer changes there is excluded and listed."""
    manifest, private = freezer.load(run)
    steps, excluded = [], []
    for v in site.variants:
        snap = site.snapshot(v)
        if v == site.variants[0]:
            valid, priv = manifest["tasks"], private
        else:
            valid, out, priv = still_valid(run, snap)
            excluded += [{**e, "variant": v} for e in out]
        for t in valid:
            steps.append({"variant": v, "snap": snap, "task": t, "inst": freezer.instance(t, priv[t["task_id"]], snap.sha256)})
    return steps, excluded


def execute(run: InvestigationRun, *, behavior: str = "correct", model_url: str | None = None) -> dict:
    """Run the plan (resumable: trials already recorded are kept). provider 'dev' needs no URL (a pinned loopback dev provider is started)."""
    site = get(run.state["config"]["site"])
    provider = run.state["config"]["provider"]
    steps, excluded = _plan(run, site)
    ledger = run.ledger(FIXTURE_LEDGER_CEILING_USD) if provider == "dev" else None
    executed = []

    def go(url: str | None):
        for st in steps:
            t, v = st["task"], st["variant"]
            name = f"{v}-{t['task_id']}-r1"
            if run.has_artifact(f"trials/{name}"):
                continue
            lim = st["inst"].spec.limits
            gate = RequestGate(ledger, name, run_cap=FIXTURE_LEDGER_CEILING_USD, per_request_cap=PER_REQUEST_CAP_USD, max_requests=lim.max_model_requests) if ledger else None
            rec = asyncio.run(run_trial(st["inst"], st["snap"], provider="live" if provider == "dev" else "mock", mock_behavior=behavior, output=run.dir / "trial-data" / name,
                                        model_config=ModelConfig(base_url=_loopback(url)) if url else None, api_key=DEV_KEY if provider == "dev" else None,
                                        request_gate=gate, label=v, profile_id=run.artifact("tasks-manifest")["agent_profile"]))
            trial_dir = str(Path(rec.pop("artifact_path")).relative_to(run.dir))
            run.write_artifact(f"trials/{name}", {**rec, "task_id": t["task_id"], "partition": t["partition"], "repeat": 1, "trial_id": f"{t['task_id']}-r1",
                                                  "trial_dir": trial_dir, "arm": v, "variant": v, "variant_sha256": st["snap"].sha256})
            executed.append(name)

    if provider == "dev":
        if model_url:
            go(model_url)
        else:
            with dev_provider(run) as (_, url):
                go(url)
    else:
        go(None)
    return {"executed": executed, "planned": len(steps), "excluded": excluded}


def results(run: InvestigationRun) -> dict:
    """Recorded v1 grades, the v2 post-hoc view (with the v1 reproduction check), per-variant totals and provenance. Written once all planned trials exist."""
    site = get(run.state["config"]["site"])
    steps, excluded = _plan(run, site)
    doc = rescore.rescore_run(run.dir)
    trials = {r["trial"]: r for r in doc["trials"]}
    rows = []
    for st in steps:
        name = f"{st['variant']}-{st['task']['task_id']}-r1"
        if name not in trials:
            continue
        t, r = run.artifact(f"trials/{name}"), trials[name]
        rows.append({"variant": st["variant"], "task_id": st["task"]["task_id"], "kind": run.artifact("tasks-manifest") and next(x["kind"] for x in run.artifact("tasks-manifest")["tasks"] if x["task_id"] == st["task"]["task_id"]),
                     "status": t["outcome"]["run_status"], "void": t["outcome"]["run_status"] in VOID_STATUSES, "v1_passed": t["evaluation"]["passed"], "v1_evidence_backed": t["evaluation"]["evidence_backed"],
                     "v2_passed": (r["v2"] or {}).get("passed"), "v2_evidence_backed": (r["v2"] or {}).get("evidence_backed"), "v2_reasons": (r["v2"] or {}).get("reasons"),
                     "model_requests": t["metrics"]["model_requests"], "page_views": t["metrics"]["page_views"], "steps": t["metrics"]["steps"],
                     "evidence_files": sorted(p.name for p in (run.dir / t["trial_dir"]).iterdir()) if (run.dir / t["trial_dir"]).is_dir() else []})
    totals = {}
    for v in site.variants:
        rs = [r for r in rows if r["variant"] == v and not r["void"]]
        totals[v] = {"trials": len(rs), "void": sum(r["void"] for r in rows if r["variant"] == v), "v1_evidence_backed": sum(r["v1_evidence_backed"] for r in rs),
                     "v2_evidence_backed": sum(bool(r["v2_evidence_backed"]) for r in rs), "requests": sum(r["model_requests"] or 0 for r in rs)}
    complete = len(rows) == len(steps)
    out = {"schema": SCHEMA, "run": run.state["id"], "complete": complete, "planned": len(steps), "recorded": len(rows), "excluded": excluded,
           "rescore_faithful": doc["faithful"], "totals": totals, "trials": rows, "provenance": run.artifact("framework-provenance"),
           "notice": "Zero-cost fixture execution: the agent's replies come from a scripted stand-in (NOT a model). This proves the pipeline, not agent or website performance."}
    if complete and not run.has_artifact("framework-results"):
        run.write_artifact("framework-results", out)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="agent_readiness.framework.evaluate")
    ap.add_argument("site")
    ap.add_argument("--root", type=Path, required=True)
    ap.add_argument("--provider", choices=PROVIDERS, default="dev")
    ap.add_argument("--behavior", default="correct", help="mock provider only: correct | wrong | lazy")
    a = ap.parse_args(argv)
    run = prepare(a.site, a.root, provider=a.provider)
    ex = execute(run, behavior=a.behavior)
    res = results(run)
    print(json.dumps({"run": str(run.dir), "executed": len(ex["executed"]), "excluded": ex["excluded"], "complete": res["complete"], "rescore_faithful": res["rescore_faithful"], "totals": res["totals"]}, indent=1))
    return 0 if res["complete"] and res["rescore_faithful"] else 1


if __name__ == "__main__":
    sys.exit(main())
