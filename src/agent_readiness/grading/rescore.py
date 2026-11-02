"""Post-hoc rescore of a recorded investigation run with grader_v2.

Reads a run READ-ONLY (frozen manifest + private criteria verified by `freeze.load`, site profile, trial artifacts, evaluation, approved
post-plan, patched mirrors) and returns a separate, labelled document. Nothing is written into the run: the recorded grades and the
pre-registered verdicts stay the official results of that run.

Faithfulness checks (any failure is reported and the document is marked not faithful):
  * grader_v1 is re-applied to every stored answer and must reproduce every stored `passed` flag;
  * the frozen comparison (`design.compare` with the run's pre-registered rule) and the exploratory rule are recomputed from the stored v1
    flags and must reproduce the stored verdicts.
Only then are the same rules applied to the v2 flags. v2 statistics are labelled post hoc: the rules were pre-registered for v1 grades.

    python -m agent_readiness.grading.rescore RUN_DIR [RUN_DIR ...] --out DIR
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

from ..investigate.evaluate import design, exploratory
from ..investigate.run import InvestigationRun
from ..investigate.taskgen import criteria as C
from ..investigate.taskgen import freeze as freezer
from ..investigate.trials.attribution import attribute
from ..investigate.trials.stage import VOID_STATUSES
from ..investigate.trials.trace import load_observations
from ..suite.core import canonical_hash
from . import v2
from .key import build_key

SCHEMA = "grader-rescore-v1"
LABEL = ("POST-HOC RESCORE: grader_v2 applied to answers recorded earlier. Not pre-registered. The official results of this run are its grader_v1 "
         "grades and verdicts, reproduced here unchanged; v2 statistics apply the same rules to v2 grades and must not be read as the original verdicts.")


def _answer(trial: dict, style: str):
    ans = (trial.get("outcome") or {}).get("answer")
    if not isinstance(ans, dict):
        return None
    return ans.get("answers" if style == "set" else "answer")


def _compiled(priv: dict) -> C.Compiled:
    return C.Compiled(priv["kind"], priv["style"], priv["truth"], priv["evidence_paths"], [tuple(t) for t in priv["evidence_texts"]], detail=priv["detail"], distractors=priv.get("distractors", []))


def _trial_rows(run: InvestigationRun, private: dict, keys: dict) -> dict[str, dict]:
    rows = {}
    for path in sorted((run.dir / "artifacts" / "trials").glob("*.json")):
        t = run.artifact(f"trials/{path.stem}")
        tid, ev, status = t["task_id"], t["evaluation"], t["outcome"]["run_status"]
        priv = private[tid]
        ans = _answer(t, priv["style"])
        void = status in VOID_STATUSES
        v1_re = bool(ev.get("answer_valid")) and C.grade(_compiled(priv), ans)[0]
        row = {"trial": path.stem, "arm": path.stem.split("-")[0], "task_id": tid, "run_status": status, "void": void, "answer": ans,
               "v1": {"passed": ev["passed"], "evidence_backed": ev["evidence_backed"]}, "v1_reproduced": v1_re == ev["passed"],
               "evidence_satisfied": ev.get("evidence_satisfied"), "v2": None}
        if tid in keys:
            g = v2.grade(keys[tid], ans if ev.get("answer_valid") else None)
            row["v2"] = {"passed": g.passed, "evidence_backed": bool(g.passed and ev.get("evidence_satisfied")), "reasons": g.reasons, "review": g.review}
        row["changed"] = row["v2"] is not None and not void and (row["v2"]["passed"], row["v2"]["evidence_backed"]) != (ev["passed"], ev["evidence_backed"])
        rows[path.stem] = row
    return rows


def _collect(run, prefix: str, private: dict, profile: dict, rows: dict, which: str) -> dict[str, list[dict]]:
    """`evaluate.stage._collect` with the pass flags taken from `which` ('v1' = as stored, 'v2' = rescored)."""
    by: dict[str, list[dict]] = defaultdict(list)
    for path in sorted((run.dir / "artifacts" / "trials").glob(f"{prefix}-*.json")):
        t = run.artifact(f"trials/{path.stem}")
        a = attribute(t, load_observations(run, t), private[t["task_id"]], profile)
        r = rows[path.stem]
        flags = r["v1"] if which == "v1" else (r["v2"] or {"passed": False, "evidence_backed": False})
        by[t["task_id"]].append({"void": a["void"], "passed": flags["passed"], "evidence_backed": flags["evidence_backed"], "model_requests": t["metrics"]["model_requests"],
                                 "primary": a["primary"], "page_views": t["metrics"]["page_views"]})
    return by


STAT_KEYS = ("verdict", "reason", "pairs", "pass_delta", "request_change", "p_pass", "p_requests")


def _comparisons(run: InvestigationRun, manifest: dict, private: dict, profile: dict, rows: dict) -> dict:
    if not run.has_artifact("evaluation") or not run.artifact("evaluation").get("evaluated"):
        return {"state": "not_evaluated"}
    from ..investigate.evaluate.stage import still_valid
    from ..investigate.sitemodel.snapshot import Snapshot
    stored = run.artifact("evaluation")
    rule = manifest.get("evaluation_rule") or design.RULE
    parts = {t["task_id"]: t["partition"] for t in manifest["tasks"]}
    out = {"state": "evaluated", "rule": rule["id"], "frozen": {}, "exploratory": None, "reproduced": True}
    base = {w: _collect(run, "baseline", private, profile, rows, w) for w in ("v1", "v2")}
    pids = list((stored.get("results") or {}).keys())
    patched_by_pid = {}
    for pid in pids:
        _, _, priv_new = still_valid(run, Snapshot.load(run.dir / "patched" / pid))
        merged = {**private, **priv_new}
        patched = {w: _collect(run, f"patched-{pid}", merged, profile, rows, w) for w in ("v1", "v2")}
        patched_by_pid[pid] = (merged, patched)
        res = {w: design.compare(base[w], patched[w], parts, rule) for w in ("v1", "v2")}
        st = stored["results"][pid]
        ok = all(res["v1"].get(k) == st.get(k) for k in ("verdict", "pairs", "p_pass", "p_requests", "pass_delta", "request_change"))
        out["reproduced"] &= ok
        out["frozen"][pid] = {"stored_v1": {k: st.get(k) for k in STAT_KEYS}, "recomputed_v1": {k: res["v1"].get(k) for k in STAT_KEYS}, "v1_reproduced": ok,
                              "v2_post_hoc": {k: res["v2"].get(k) for k in STAT_KEYS}}
    if stored.get("exploratory") and run.has_artifact("post-plan") and len(pids) == 1:
        pid = pids[0]
        plan = run.artifact("post-plan")
        merged, patched = patched_by_pid[pid]
        res = {w: exploratory.analyze(plan, base[w], _collect(run, f"placebo-{pid}", private, profile, rows, w), patched[w]) for w in ("v1", "v2")}
        ok = res["v1"]["verdict"] == stored["exploratory"]["verdict"]
        out["reproduced"] &= ok
        out["exploratory"] = {"rules_id": exploratory.ID, "stored_v1": stored["exploratory"]["verdict"], "recomputed_v1": res["v1"]["verdict"], "v1_reproduced": ok,
                              "v2_post_hoc": res["v2"]["verdict"], "v2_reasons": res["v2"].get("reasons")}
    return out


def _tally(rows: dict) -> dict:
    out = {}
    for arm in sorted({r["arm"] for r in rows.values()}):
        rs = [r for r in rows.values() if r["arm"] == arm and not r["void"]]
        out[arm] = {"trials": len(rs), "void": sum(r["void"] for r in rows.values() if r["arm"] == arm),
                    "v1_passed": sum(r["v1"]["passed"] for r in rs), "v1_evidence_backed": sum(r["v1"]["evidence_backed"] for r in rs),
                    "v2_passed": sum(bool(r["v2"] and r["v2"]["passed"]) for r in rs), "v2_evidence_backed": sum(bool(r["v2"] and r["v2"]["evidence_backed"]) for r in rs)}
    return out


def rescore_run(run_dir: Path) -> dict:
    run = InvestigationRun(Path(run_dir))
    manifest, private = freezer.load(run)
    profile = run.artifact("site-profile")
    keys, key_errors = {}, {}
    for tid, priv in sorted(private.items()):
        try:
            keys[tid] = build_key(tid, priv, profile)
        except v2.KeyError_ as exc:
            key_errors[tid] = str(exc)
    rows = _trial_rows(run, private, keys)
    comps = _comparisons(run, manifest, private, profile, rows)
    faithful = all(r["v1_reproduced"] for r in rows.values()) and comps.get("reproduced", True)
    return {"schema": SCHEMA, "label": LABEL, "run": run.state.get("id") or run.dir.name, "faithful": faithful,
            "graders": {"v1": v2.GRADER_V1, "v2": {"id": v2.GRADER_ID, "version": v2.GRADER_VERSION, "implementation": "agent_readiness.grading.v2", "code_sha256": v2.code_sha256()}},
            "inputs": {"criteria_sha256": manifest["criteria_sha256"], "snapshot_sha256": manifest["snapshot_sha256"], "tasks": len(manifest["tasks"]),
                       "evaluation_sha256": canonical_hash(run.artifact("evaluation")) if run.has_artifact("evaluation") else None},
            "key_errors": key_errors, "tally": _tally(rows), "comparisons": comps,
            "changed": [{k: r[k] for k in ("trial", "arm", "task_id", "v1", "v2")} for r in rows.values() if r["changed"]],
            "trials": list(rows.values())}


def public_summary(doc: dict, task_alias: dict[str, int] | None = None) -> dict:
    """Shareable view: no answers, no expected values, no private criteria; task ids may be aliased to their public numbers."""
    alias = (lambda t: task_alias.get(t, t)) if task_alias else (lambda t: t)
    return {"schema": SCHEMA + "-public", "label": doc["label"], "run": doc["run"], "faithful": doc["faithful"], "graders": doc["graders"],
            "inputs": {k: doc["inputs"][k] for k in ("criteria_sha256", "snapshot_sha256", "tasks", "evaluation_sha256")}, "key_errors": sorted(doc["key_errors"]),
            "tally": doc["tally"], "comparisons": doc["comparisons"],
            "changed": [{"trial_arm": c["arm"], "task": alias(c["task_id"]), "v1": c["v1"], "v2": {k: c["v2"][k] for k in ("passed", "evidence_backed", "reasons")}} for c in doc["changed"]],
            "v2_reason_counts": _reason_counts(doc)}


def _reason_counts(doc: dict) -> dict:
    counts: dict[str, int] = defaultdict(int)
    for r in doc["trials"]:
        if r["v2"] and not r["void"]:
            for reason in r["v2"]["reasons"]:
                counts[reason] += 1
    return dict(sorted(counts.items()))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="agent_readiness.grading.rescore", description=__doc__.split("\n\n")[0])
    ap.add_argument("runs", nargs="+", type=Path)
    ap.add_argument("--out", type=Path, required=True, help="directory for <run>.grader-v2.json (private: contains answers) and <run>.grader-v2.public.json")
    a = ap.parse_args(argv)
    a.out.mkdir(parents=True, exist_ok=True)
    bad = 0
    for d in a.runs:
        doc = rescore_run(d)
        (a.out / f"{doc['run']}.grader-v2.json").write_text(json.dumps(doc, indent=1, sort_keys=True))
        (a.out / f"{doc['run']}.grader-v2.public.json").write_text(json.dumps(public_summary(doc), indent=1, sort_keys=True))
        bad += not doc["faithful"]
        print(doc["run"], "faithful" if doc["faithful"] else "NOT FAITHFUL", json.dumps(doc["tally"]), f"changed={len(doc['changed'])}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
