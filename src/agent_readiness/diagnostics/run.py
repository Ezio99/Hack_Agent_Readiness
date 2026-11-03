"""Diagnostic pipeline over an evidence bundle (a site's versions, their frozen snapshots, the frozen tasks and the recorded trials).

Two read-only adapters, no site-specific logic:
  from_framework_run(dir)   a Phase 3 zero-cost run (framework/evaluate.py): versions = the site definition's variants
  from_recorded_fork(dir)   a recorded paired run (e.g. a hosted Ironbark repetition): original = the fork's snapshot (trials `placebo-*`),
                            modified = its patched snapshot (trials `patched-*`), plus the run's recorded comparison verdicts

    python -m agent_readiness.diagnostics.run DIR [--out FILE]"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from ..investigate.inspect.profile import build_profile
from ..investigate.run import InvestigationRun
from ..investigate.sitemodel.snapshot import Snapshot
from ..investigate.taskgen import freeze as freezer
from . import behavioral, hypotheses, structural

SCHEMA = "diagnostics-report-v2"   # v2 (M8): hypotheses-2 (either_of / ranked_subset labels); every finding carries `basis` (observed | hypothesis)


def _trials(run: InvestigationRun, prefix: str) -> dict:
    return {p.stem: run.artifact(f"trials/{p.stem}") for p in sorted((run.dir / "artifacts" / "trials").glob(f"{prefix}-*.json"))}


def from_framework_run(run_dir: Path) -> dict:
    from ..framework.site import get
    from ..investigate.evaluate.stage import still_valid
    run = InvestigationRun(Path(run_dir))
    site = get(run.state["config"]["site"])
    _, private = freezer.load(run)
    versions = []
    names = [v for v in (run.state["config"].get("variants") or site.variants) if v in site.registered] or list(site.variants)   # the run's own pair
    for v in names:
        snap = site.snapshot(v)
        priv = private if v == names[0] else {**private, **still_valid(run, snap)[2]}
        versions.append({"name": v, "snapshot": snap, "private": priv, "trials": _trials(run, v)})
    return {"site": site.id, "source": str(run.dir), "origin": "dev_fixture" if run.has_artifact("dev-provider") else "scripted", "versions": versions, "comparison": None,
            "alias": {t: str(i + 1) for i, t in enumerate(sorted(private))}}


def from_recorded_fork(run_dir: Path) -> dict:
    from ..investigate.evaluate.stage import still_valid
    from ..investigate.presentation import origin
    run = InvestigationRun(Path(run_dir))
    _, private = freezer.load(run)
    pids = sorted(p.name for p in (run.dir / "patched").iterdir())
    if len(pids) != 1:
        raise ValueError("a recorded fork with exactly one applied change is required")
    base, mod = Snapshot.load(run.dir / "snapshot"), Snapshot.load(run.dir / "patched" / pids[0])
    ev = run.artifact("evaluation") if run.has_artifact("evaluation") else {}
    res = (ev.get("results") or {}).get(pids[0]) or {}
    comparison = {"frozen": res.get("verdict"), "frozen_rule_id": (ev.get("rule") or {}).get("id"), "exploratory": (ev.get("exploratory") or {}).get("verdict"),
                  "exploratory_rule_id": (ev.get("exploratory") or {}).get("rules_id")} if ev else None
    alias = {t: str(i + 1) for i, t in enumerate(sorted(private))}
    return {"site": run.state.get("target") or "recorded", "source": str(run.dir), "origin": origin(run)["provider"],
            "versions": [{"name": "original", "snapshot": base, "private": private, "trials": _trials(run, "placebo")},
                         {"name": "modified", "snapshot": mod, "private": {**private, **still_valid(run, mod)[2]}, "trials": _trials(run, "patched")}],
            "comparison": comparison, "alias": alias}


def _evalrun_v2(run_dir: Path) -> dict:
    """Stage B lifecycle runs (M8): `rescore_run` cannot key the M2b kinds (ranked_subset, either_of), so v2 was silently missing and every v1
    format rejection read as an incorrect answer. The lifecycle runner's own row grader (same `rescore._trial_rows`, keys from `build_key_any`) is
    used instead, again only when it reproduces every stored v1 grade."""
    try:
        from ..evalruns.runner import condition_results
        res = condition_results(InvestigationRun(run_dir))
        if not res["rescore_faithful"]:
            return {}
        return {r["trial"]: {"passed": r["v2_passed"], "evidence_backed": r["v2_evidence_backed"], "reasons": r["v2_reasons"]} for r in res["rows"] if r["v2_passed"] is not None}
    except Exception:
        return {}


def diagnose(bundle: dict) -> dict:
    site, origin = bundle["site"], bundle["origin"]
    versions = []
    for v in bundle["versions"]:
        versions.append({**v, "sha256": v["snapshot"].sha256, "profile": build_profile(v["snapshot"])})
    try:                                                                                  # post-hoc grader v2 per trial, only when the rescore reproduces v1 exactly
        from ..grading.rescore import rescore_run
        rs = rescore_run(Path(bundle["source"]))
        v2 = {r["trial"]: r["v2"] for r in rs["trials"] if r["v2"]} if rs["faithful"] else {}
    except Exception:
        v2 = _evalrun_v2(Path(bundle["source"]))
    st = {v["name"]: structural.observe(v["profile"], site=site, version=v["name"]) for v in versions}
    bh = {v["name"]: behavioral.observe(v["trials"], v["private"], site=site, version=v["name"], version_sha=v["sha256"], origin=origin, tasks_alias=bundle.get("alias"), v2=v2)
          for v in versions}
    hy = hypotheses.link(site=site, versions=versions, structural=st, behavioral=bh, comparison=bundle.get("comparison"), origin=origin, tasks_alias=bundle.get("alias"))
    findings = [f for v in versions for f in st[v["name"]]] + [f for v in versions for f in bh[v["name"]]] + hy
    changes = {v["name"]: structural.compare(st[versions[0]["name"]], st[v["name"]]) for v in versions[1:]}
    return {"schema": SCHEMA, "rules": {"hypotheses": hypotheses.RULES_VERSION, "behavioral": behavioral.RULES_VERSION}, "site": site, "source": bundle["source"], "evidence_origin": origin, "versions": {v["name"]: v["sha256"] for v in versions},
            "comparison": bundle.get("comparison"), "structural_changes": changes,
            "summary": {"by_layer_status": dict(Counter(f"{f.layer}:{f.status}" for f in findings)), "findings": len(findings)},
            "findings": [f.as_dict() for f in findings]}


def to_markdown(rep: dict) -> str:
    lines = [f"# Diagnostics: {rep['site']} ({rep['evidence_origin']} behaviour)", "", f"Versions: " + ", ".join(f"{k} `{v[:12]}`" for k, v in rep["versions"].items()), ""]
    for name, ch in rep["structural_changes"].items():
        lines.append(f"Structural change in **{name}**: resolved {len(ch['resolved'])} ({'; '.join(ch['titles'][i] for i in ch['resolved'])}), introduced {len(ch['introduced'])}.")
    for layer in ("hypothesis", "behavioral", "structural"):
        fs = [f for f in rep["findings"] if f["layer"] == layer]
        lines += ["", f"## {layer.capitalize()} ({len(fs)})", "", "| id | status | severity | version | finding | recommendation |", "|---|---|---|---|---|---|"]
        for f in fs:
            lines.append(f"| `{f['id']}` | {f['status']} | {f['severity']} | {f['version']} | {f['title']} | {f['recommendation']} |")
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="agent_readiness.diagnostics.run")
    ap.add_argument("run", type=Path)
    ap.add_argument("--recorded", action="store_true", help="the directory is a recorded paired fork (placebo/patched trials)")
    ap.add_argument("--out", type=Path, help="write the JSON report here (and a .md beside it)")
    a = ap.parse_args(argv)
    rep = diagnose(from_recorded_fork(a.run) if a.recorded else from_framework_run(a.run))
    if a.out:
        a.out.write_text(json.dumps(rep, indent=1) + "\n")
        a.out.with_suffix(".md").write_text(to_markdown(rep))
    print(json.dumps(rep["summary"]), json.dumps({k: {x: len(v[x]) for x in ("resolved", "introduced")} for k, v in rep["structural_changes"].items()}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
