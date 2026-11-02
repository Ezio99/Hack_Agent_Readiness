"""Post-hoc rescore: reproduces stored v1 grades and verdicts exactly, applies v2 separately, never writes into the run, and detects tampering.

Offline: a scripted zoo run (frozen tasks, snapshot, approved fix, baseline + patched trials) whose stored flags are produced by grader_v1 itself
from answers that are correct but verbose (v1 rejects them; v2 accepts them)."""
import json
import os
import shutil

from agent_readiness.grading import rescore
from agent_readiness.investigate.evaluate import stage as ev
from agent_readiness.investigate.pipeline import Context, Pipeline, Stage
from agent_readiness.investigate.recommend import stage as rec
from agent_readiness.investigate.taskgen import criteria as C
from agent_readiness.investigate.taskgen import freeze as freezer
from agent_readiness.investigate.trials import stage as trials_stage

from .test_investigate_fix_eval import with_finding


def verbose_correct(priv):
    """A correct answer with harmless extra wording (no numbers, no other candidate)."""
    if priv["style"] == "set":
        return [f"{name} (listed)" for name in priv["truth"]]
    return f"{priv['truth']} - confirmed on its own page after checking every listed item carefully"


def write_trial(run, task, priv, prefix, answer, visited):
    tid = f"{task['task_id']}-r1"
    profile = run.artifact("site-profile")
    d = run.dir / "trial-data" / f"{prefix}-{tid}" / "x"
    d.mkdir(parents=True)
    (d / "observations.json").write_text(json.dumps([{"path": p, "text": profile["pages"][p]["text"] if p in profile["pages"] else ""} for p in visited]))
    comp = rescore._compiled(priv)
    passed = C.grade(comp, answer)[0]                                                # stored flags are exactly what grader_v1 says
    key = "answers" if priv["style"] == "set" else "answer"
    run.write_artifact(f"trials/{prefix}-{tid}", {
        "trial": {"label": prefix, "mode": "mock"}, "task": {}, "task_id": task["task_id"], "partition": task["partition"], "repeat": 1, "trial_id": tid, "trial_dir": str(d.relative_to(run.dir)),
        "outcome": {"run_status": "completed", "stop_reason": "x", "errors": [], "answer": {key: answer}},
        "evaluation": {"passed": passed, "evidence_backed": passed, "evidence_satisfied": True, "answer_valid": True, "missing_evidence": [], "reasons": [], "details": {}},
        "metrics": {"model_requests": len(visited) + 1, "steps": len(visited), "page_views": len(visited), "limits": {"max_steps": task["limits"]["max_steps"]}},
        "journey": [{"step": i + 1, "path": p, "query": "", "actions": [{"name": "navigate", "params": {"url": p}}], "executed": [{"result": "ok", "error": None}]} for i, p in enumerate(visited)],
        "mirror": {"log": [{"method": "GET", "path": p, "status": 200} for p in visited], "blocked": []}})


def evaluated_run(tmp_path):
    run = with_finding(tmp_path, name="rescore")                                     # baseline trials: the agent ran out of budget (no answer)
    rec.recommend_stage(Context(run))
    pid = next(p.id for p in run.evidence.proposals.values() if p.basis == "verified_finding")
    ctx = Context(run, options={"fix": pid})
    run.write_artifact("arm-config", trials_stage.arm_config(Context(run)))
    st = Stage("apply_fix", rec.apply_fix_stage, gate=True, manifest=rec.apply_manifest)
    r = Pipeline([st]).run(ctx)
    run.approve("apply_fix", r.manifest_sha256, "owner approves")
    Pipeline([st]).run(ctx)
    m, private = freezer.load(run)
    for t in m["tasks"]:
        p = private[t["task_id"]]
        write_trial(run, t, p, f"patched-{pid}", verbose_correct(p), ["/"] + p["evidence_paths"])
    ev.evaluate_stage(ctx)
    return run, pid


def fingerprint(d):
    return sorted((str(p.relative_to(d)), p.stat().st_size, p.read_bytes()) for p in d.rglob("*") if p.is_file())


def test_rescore_reproduces_v1_applies_v2_separately_and_never_writes_into_the_run(tmp_path):
    run, pid = evaluated_run(tmp_path)
    before = fingerprint(run.dir)
    doc = rescore.rescore_run(run.dir)
    assert fingerprint(run.dir) == before                                            # read-only
    assert doc["faithful"] and all(r["v1_reproduced"] for r in doc["trials"]) and not doc["key_errors"]
    frozen = doc["comparisons"]["frozen"][pid]
    assert frozen["v1_reproduced"] and frozen["stored_v1"] == frozen["recomputed_v1"]
    patched = [r for r in doc["trials"] if r["arm"] == "patched"]
    assert patched and all(not r["v1"]["passed"] for r in patched)                   # v1 rejected every verbose answer...
    assert all(r["v2"]["passed"] and r["v2"]["evidence_backed"] for r in patched)    # ...v2 accepts them
    assert all(r["v2"]["reasons"] == ["matches_truth_with_consistent_detail"] for r in patched)
    assert frozen["v2_post_hoc"]["pass_delta"] == 1.0 and frozen["stored_v1"]["pass_delta"] == 0.0
    assert doc["label"].startswith("POST-HOC RESCORE") and doc["graders"]["v1"]["version"] == "1" and doc["graders"]["v2"]["version"] == "2"
    assert len(doc["changed"]) == len(patched)


def test_public_summary_carries_no_answers_or_expected_values(tmp_path):
    run, _ = evaluated_run(tmp_path)
    doc = rescore.rescore_run(run.dir)
    pub = json.dumps(rescore.public_summary(doc))
    _, private = freezer.load(run)
    for p in private.values():
        for value in ([p["truth"]] if isinstance(p["truth"], str) else p["truth"]):
            assert value not in pub
    assert "listed)" not in pub and "confirmed on its own page" not in pub and '"answer"' not in pub


def test_a_tampered_stored_grade_makes_the_rescore_unfaithful(tmp_path):
    run, _ = evaluated_run(tmp_path)
    copy = tmp_path / "tampered"
    shutil.copytree(run.dir, copy)
    target = next((copy / "artifacts" / "trials").glob("patched-*.json"))
    rec_ = json.loads(target.read_text())
    rec_["evaluation"]["passed"] = not rec_["evaluation"]["passed"]
    os.chmod(target, 0o600)
    target.write_text(json.dumps(rec_))
    doc = rescore.rescore_run(copy)
    assert not doc["faithful"] and any(not r["v1_reproduced"] for r in doc["trials"])


def test_cli_writes_private_and_public_documents_outside_the_run(tmp_path):
    run, _ = evaluated_run(tmp_path)
    out = tmp_path / "out"
    assert rescore.main([str(run.dir), "--out", str(out)]) == 0
    names = sorted(p.name for p in out.iterdir())
    assert names == [f"{run.dir.name}.grader-v2.json", f"{run.dir.name}.grader-v2.public.json"]
    assert not any(p.name.endswith("grader-v2.json") for p in run.dir.rglob("*"))


def test_hosted_view_is_labelled_cached_beside_the_run_and_withheld_when_unfaithful(tmp_path):
    from agent_readiness.hosted import api
    run, _ = evaluated_run(tmp_path)
    before = fingerprint(run.dir)
    view = api.grading_v2(run.dir.parent, run.dir.name)
    caches = list((run.dir.parent / "derived" / "grader-v2").glob(f"{run.dir.name}.*.json"))
    assert fingerprint(run.dir) == before and len(caches) == 1 and rescore.derivation_id() in caches[0].name
    caches[0].unlink()                                                                # disposable: rebuilt identically on demand
    assert api.grading_v2(run.dir.parent, run.dir.name) == view
    assert view["faithful"] and "Not pre-registered" in view["label"] and view["grader"]["version"] == "2"
    assert view["tasks"] and all(t["arm"] == "Modified" and t["outcome"] == "evidence_supported_pass" for t in view["tasks"])   # this run has no placebo arm
    s = api.summarize_v2([{"grading_v2": view}])
    assert s["Modified"]["evidence_supported_passes"] == s["Modified"]["completed"] == len(view["tasks"]) and s["Original"]["completed"] == 0
    assert api.summarize_v2([{"grading_v2": {**view, "faithful": False}}, {"grading_v2": None}]) is None
    copy = tmp_path / "tampered-root"
    shutil.copytree(run.dir, copy / run.dir.name)
    target = next((copy / run.dir.name / "artifacts" / "trials").glob("patched-*.json"))
    rec_ = json.loads(target.read_text()); rec_["evaluation"]["passed"] = True
    os.chmod(target, 0o600); target.write_text(json.dumps(rec_))
    bad = api.grading_v2(copy, run.dir.name)
    assert bad["faithful"] is False and bad["tasks"] == [] and bad["assessment"] is None
