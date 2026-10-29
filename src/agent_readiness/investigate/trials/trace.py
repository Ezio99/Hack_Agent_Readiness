"""Trace analysis stage: attribute every baseline trial (deterministic, free) and turn the results into neutral evidence Observations the investigator can cite.

Void trials (provider/budget/infrastructure) are listed but never counted as website evidence. Holdout trials are attributed too (for the final report) but their Observations are
flagged `holdout` and are NOT added to the evidence store the investigator reads."""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from statistics import median

from ..inspect.stage import load_snapshot  # noqa: F401
from ..models import Observation, Provenance
from ..pipeline import Context
from ..taskgen import freeze as freezer
from .attribution import attribute


def load_observations(run, trial: dict) -> list[dict]:
    p = run.dir / trial["trial_dir"] / "observations.json"
    return json.loads(p.read_text()) if p.exists() else []


def analyze(run) -> dict:
    """Attribute all baseline trials. Returns {trial_id: attribution + task info}; writes the write-once artifact `attribution`."""
    manifest, private = freezer.load(run)
    profile = run.artifact("site-profile")
    kinds = {t["task_id"]: t for t in manifest["tasks"]}
    out = {}
    for path in sorted((run.dir / "artifacts" / "trials").glob("baseline-*.json")):
        trial = run.artifact(f"trials/{path.stem}")
        tid = trial["task_id"]
        a = attribute(trial, load_observations(run, trial), private[tid], profile)
        out[trial["trial_id"]] = {**a, "task_id": tid, "partition": trial["partition"], "kind": kinds[tid]["kind"], "question": kinds[tid]["question"], "repeat": trial["repeat"],
                                  "passed": trial["evaluation"]["passed"], "evidence_backed": trial["evaluation"]["evidence_backed"], "mode": trial["trial"]["mode"]}
    run.write_artifact("attribution", out)
    return out


def observations(att: dict, *, mode: str) -> list[Observation]:
    """Neutral facts from INVESTIGATION-partition trials only (plus an aggregate that mixes no per-holdout detail)."""
    prov = Provenance(mode=mode, source="rule:trace-analysis")
    inv = {k: v for k, v in att.items() if v["partition"] == "investigation"}
    obs = []
    for tid, a in sorted(inv.items()):
        s = a["signals"]
        obs.append(Observation(kind="trial_summary", summary=(f"Trial {tid} ({a['kind']}): {'passed' if a['passed'] else 'failed'}; attribution {a['primary']} ({a['why']}); {s['page_views']} page views against a minimum of about {s['min_page_views']}; "
                                                              f"{s['model_requests']} model requests; evidence pages visited {len(s['evidence_pages_visited'])} of {len(s['evidence_pages_visited']) + len(s['evidence_pages_unvisited'])}."),
                               data={"trial_id": tid, "task_id": a["task_id"], "primary": a["primary"], "void": a["void"], "signals": s, "passed": a["passed"], "evidence_backed": a["evidence_backed"]}, refs=[f"trial:{tid}"], provenance=prov))
    valid = [a for a in inv.values() if not a["void"]]
    if valid:
        c = Counter(a["primary"] for a in valid)
        extra = [a["signals"]["extra_page_views"] for a in valid]
        obs.append(Observation(kind="trial_aggregate", summary=(f"{len(valid)} non-void investigation trials: " + ", ".join(f"{k} {v}" for k, v in sorted(c.items())) + f"; median extra page views over the minimum {median(extra)}; "
                                                               f"{sum(not a['passed'] for a in valid)} failed."),
                               data={"counts": dict(c), "median_extra_page_views": median(extra), "void_excluded": len(inv) - len(valid)}, refs=[f"trial:{t}" for t in sorted(inv)][:8], provenance=prov))
    by_task = defaultdict(list)
    for a in valid:
        by_task[a["kind"]].append(a)
    for kind, rows in sorted(by_task.items()):
        obs.append(Observation(kind="kind_summary", summary=f"Tasks of kind {kind}: {sum(r['passed'] for r in rows)} of {len(rows)} passed; median extra page views {median(r['signals']['extra_page_views'] for r in rows)}.",
                               data={"kind": kind, "n": len(rows), "passed": sum(r["passed"] for r in rows)}, refs=[f"trial:{r['task_id']}" for r in rows][:6], provenance=prov))
    return obs


def trace_stage(ctx: Context) -> dict:
    run = ctx.run
    att = analyze(run)
    obs = observations(att, mode=run.mode)
    for o in obs:
        run.evidence.add_observation(o)
    return {"trials": len(att), "void": sum(a["void"] for a in att.values()), "observations": len(obs), "by_class": dict(Counter(a["primary"] for a in att.values()))}
