"""Zero-cost end-to-end rehearsal of the two-stage lifecycle on a controlled site (lifecycle M5).

    python -m agent_readiness.evalruns.rehearse larkspur --root DIR [--repetitions 1] [--no-regression]
    python -m agent_readiness.evalruns.rehearse ironbark --root DIR

Chain: Stage A loop (developer-written FIXTURE generator, NOT a model) -> review packet -> a SYNTHETIC approval (the suite is named 'synthetic-...';
the record says it is a test decision, not the owner's) -> freeze -> pre-registered plan (feasibility computed; confirmatory requested, exploratory
fallback recorded) -> evaluation manifest (declares the real agent configuration; nothing paid is called) -> Stage B prepare / execute (real Chromium
in the network jail, loopback dev provider) / report -> RunResult records -> public-artefact leak audit. Larkspur also runs a REGRESSION manifest of
the same frozen suite on a new snapshot ("release2": one course fee changed) to show snapshot-specific invalidation and the manifest diff.
Every output is written under --root (git-ignored data); nothing here spends money."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from ..framework.site import get
from ..research.taskplan import catalogue as K
from ..research.taskplan import context as X
from ..suites import plan as PL
from ..suites.stage_a import approval as AP
from ..suites.stage_a import generators as G
from ..suites.stage_a import loop as LP
from ..suites.stage_a import stopping as ST
from ..suites.store import WriteOnceStore
from . import manifest as MF
from . import runner as RN

FIXTURES = Path(__file__).resolve().parents[1] / "suites" / "stage_a" / "fixtures"
LARKSPUR_FIRST = ["p04", "p05", "p08", "p09", "p18", "u01", "u02", "r01", "r02", "r03"]


def larkspur_release2():
    """A new Larkspur snapshot for the regression rehearsal: the 'modified' pages with one changed fact (Mindful meditation $120 -> $265)."""
    from ..sites.larkspur import render
    pages = render.pages("modified")
    for path in ("/courses/mindful-meditation", "/courses"):
        pages[path] = pages[path].replace("Course fee $120", "Course fee $265").replace("<dd>$120</dd>", "<dd>$265</dd>")
    mapping = dict(pages)
    mapping["/assets/site.css"] = (200, "text/css", render.CSS.encode())
    return render.crawl(render.MappingFetcher(mapping), render.LIMITS)


def stage_a(site_id: str, root: Path, store: WriteOnceStore, at: str, resume: bool = False) -> tuple[dict, dict]:
    site = get(site_id)
    view = K.view(site)
    if site_id == "larkspur":
        context, gen, cfg = X.CONTEXT, G.FeedbackFixture(LARKSPUR_FIRST, n=8), LP.LoopConfig(suite_name="synthetic-larkspur-rehearsal")
    elif site_id == "ironbark":
        fx = json.loads((FIXTURES / "ironbark-stage-a-v1.json").read_text())
        context, gen = fx["context"], G.RoundsFixture([fx["tasks"]])
        cfg = LP.LoopConfig(suite_name="synthetic-ironbark-rehearsal", stop=ST.StopRule(max_rounds=1))
    else:
        raise ValueError("rehearsals exist for the controlled sites larkspur and ironbark")
    out = LP.run(site, view, context, gen, config=cfg, created_at=at, out_dir=None if resume else root / "stage-a", store=store, context_label=context.get("label", ""))
    return out, context


def rehearse(site_id: str, root: Path, *, repetitions: int = 1, seed: int = 7, regression: bool = True, at: str | None = None, resume: bool = False) -> dict:
    root = Path(root)
    if resume:                                                               # deterministic re-derivation of the same records (same timestamp), recorded trials reused
        at = json.loads((root / "stage-a" / "loop.json").read_text())["created_at"]
    else:
        at = at or datetime.now(timezone.utc).isoformat(timespec="seconds")
        root.mkdir(parents=True, exist_ok=False)
    store = WriteOnceStore(root / "store")
    site = get(site_id)
    loop, context = stage_a(site_id, root, store, at, resume)
    suite_sha = loop["suite_sha256"]
    if resume and json.loads((root / "stage-a" / "suite-proposal.json").read_text())["suite_sha256"] != suite_sha:
        raise ValueError("resume: the re-derived suite differs from the recorded proposal")
    packet = AP.review_packet(store, suite_sha)
    (root / "review-packet.md").write_text(AP.render_markdown(packet))
    approval = AP.decide(store, suite_sha, decision="approved", attestation=AP.attestation_text(suite_sha, "approved"), at=at, notes="zero-cost rehearsal")
    frozen = AP.freeze(store, suite_sha, approval, at=at)
    _, suite, tasks = MF.suite_tasks(store, frozen)
    det = [t for t in tasks if t.spec.verifiability == "deterministic"]
    primary = "natural" if any(t.condition == "natural" for t in det) else "assisted"
    n_primary = sum(t.condition == primary for t in det)
    plan = PL.make_plan(n_tasks=n_primary, repetitions=repetitions, requested="confirmatory", allow_exploratory_fallback=True, sims=1000,
                        primary_outcome=f"evidence-supported pass (official grader v1), {primary}-wording condition")
    variants = [(v, site.snapshot(v).sha256) for v in site.variants]
    m = MF.build(store, frozen, variants=variants, oracle=site.oracle().label, plan=plan, repetitions=repetitions, seed=seed, created_at=at)
    msha = store.put(m)
    result = {"site": site_id, "root": str(root), "suite_sha256": suite_sha, "approval_sha256": approval, "frozen_suite_sha256": frozen, "manifest_sha256": msha,
              "stage_a": {"stop_reason": loop["summary"]["stop_reason"], "rounds": len([r for r in loop["summary"]["rounds"] if r["sent"]]), "gaps": loop["gap_report"]["gaps"],
                          "preserved_underspecified": len(loop["gap_report"]["preserved_underspecified"]), "selected": len(loop["selected"]), "rubric": len(loop["rubric"]),
                          "natural_share": loop["coverage"]["natural_share"], "capabilities": loop["coverage"]["capabilities"]},
              "plan": {"designation": plan.designation, "feasibility": plan.feasibility}, "budget": m.budget, "evaluations": {}}
    result["evaluations"]["base"] = _evaluate(store, msha, root / "runs", "base", at, resume=resume)
    if regression and site_id == "larkspur":
        rel = larkspur_release2()
        m2, diff = MF.regression(store, msha, variants=[("modified", site.snapshot("modified").sha256), ("release2", rel.sha256)], created_at=at)
        m2sha = store.put(m2)
        result["regression"] = {"manifest_sha256": m2sha, "diff": diff}
        result["evaluations"]["regression"] = _evaluate(store, m2sha, root / "runs", "regression", at, extra={"release2": rel}, resume=resume)
    (root / "rehearsal.json").write_text(json.dumps(result, indent=1, default=str))
    return result


def _evaluate(store, msha, runs_root, label, at, extra=None, resume=False) -> dict:
    runs = RN.prepare(store, msha, runs_root, mode="rehearsal", extra_snapshots=extra, label=label, resume=resume)
    executions = {c: RN.execute(r, store, extra_snapshots=extra) for c, r in runs.items()}
    doc = RN.report(store, msha, runs, created_at=at)
    priv = runs_root / f"report-{label}.private.json"
    pub = runs_root / f"report-{label}.public.json"
    priv.write_text(json.dumps(doc, indent=1, default=str))
    pub.write_text(json.dumps(RN.public_report(doc), indent=1, default=str))
    audit = RN.audit_public(store, msha, runs, [pub])
    return {"manifest_sha256": msha, "runs": {c: r.state["id"] for c, r in runs.items()},
            "executed": {c: len(e["executed"]) for c, e in executions.items()}, "planned": {c: e["planned"] for c, e in executions.items()},
            "stopped": {c: e["stopped"] for c, e in executions.items()}, "jail_ok": all(e["jail_selftest"].get("ok") for e in executions.values()),
            "tallies": {c: d["tallies"] for c, d in doc["exploratory"].items()}, "analysis": {c: d["analysis"] for c, d in doc["exploratory"].items()},
            "invalidated": {c: d["invalidated"] for c, d in doc["exploratory"].items()}, "rescore_faithful": {c: d["rescore_faithful"] for c, d in doc["exploratory"].items()},
            "complete": {c: d["complete"] for c, d in doc["exploratory"].items()}, "preregistered": doc["preregistered"], "diagnostics": doc["diagnostics"],
            "run_results": doc["run_results"], "audit": audit, "public_report": str(pub)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="agent_readiness.evalruns.rehearse")
    ap.add_argument("site", choices=("larkspur", "ironbark"))
    ap.add_argument("--root", type=Path, required=True)
    ap.add_argument("--repetitions", type=int, default=1)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--no-regression", action="store_true")
    ap.add_argument("--resume", action="store_true", help="continue an interrupted rehearsal in --root (recorded trials are reused, never re-run)")
    a = ap.parse_args(argv)
    r = rehearse(a.site, a.root, repetitions=a.repetitions, seed=a.seed, regression=not a.no_regression, resume=a.resume)
    print(json.dumps({k: r[k] for k in ("site", "manifest_sha256", "stage_a", "plan", "evaluations")} | ({"regression": r["regression"]} if "regression" in r else {}),
                     indent=1, default=str))
    ok = all(e["audit"]["clean"] and all(e["complete"].values()) and all(e["rescore_faithful"].values()) for e in r["evaluations"].values())
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
