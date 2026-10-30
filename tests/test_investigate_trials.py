"""M3 -> M4 thin path: a frozen generated task runs on the mirror through the real agent stack and is graded independently. Mock behaviours here are scripted, not model behaviour."""
import asyncio
import json

import pytest

from agent_readiness.investigate import zoo
from agent_readiness.investigate.pipeline import Context, Pipeline, Stage
from agent_readiness.investigate.taskgen import freeze as freezer
from agent_readiness.investigate.trials.runner import run_trial
from agent_readiness.investigate.trials.stage import baseline_trials_stage, manifest
from agent_readiness.ledger import Halt

from .test_investigate_taskgen import make_run, run_tasks


def frozen_run(tmp_path, mode="scripted"):
    run = make_run(tmp_path)
    assert run_tasks(run, None, n_tasks=4, feedback_round=False).status == "done"
    return run


def instance_for(run, kind):
    m = run.artifact("tasks-manifest")
    tid = next(t["task_id"] for t in m["tasks"] if t["kind"] == kind)
    return next(i for i in freezer.instances(run) if i.spec.task_id == tid)


@pytest.mark.browser
@pytest.mark.parametrize("behavior,passed,backed", [("correct", True, True), ("lazy", True, False), ("wrong", False, False)])
def test_mock_agent_runs_through_real_chromium_on_the_mirror_and_is_graded_independently(tmp_path, behavior, passed, backed):
    run = frozen_run(tmp_path)
    inst = instance_for(run, "page_fact")
    snap = zoo.snapshot("site-1")
    rec = asyncio.run(run_trial(inst, snap, provider="mock", mock_behavior=behavior, output=tmp_path / "t"))
    ev = rec["evaluation"]
    assert rec["trial"]["mode"] == "mock" and rec["outcome"]["answer"] is not None
    assert ev["passed"] is passed and ev["evidence_backed"] is backed
    paths = [e["path"] for e in rec["mirror"]["log"]]
    assert inst.spec.start_path in paths and rec["mirror"]["blocked"] == []
    if behavior == "correct":
        assert set(r.value for r in inst.evidence if r.kind == "visited_path") <= set(paths)
    assert rec["metrics"]["cost_basis"].startswith("MOCK")


@pytest.mark.browser
def test_baseline_trials_stage_runs_all_frozen_tasks_resumably_in_mock_mode(tmp_path):
    run = frozen_run(tmp_path)
    run2 = type(run)(run.dir)
    st = baseline_trials_stage(Context(run2, options={"repeats": 1}))
    tasks = run.artifact("tasks-manifest")["tasks"]
    assert st["trials"] == len(tasks) and st["void"] == 0
    for t in tasks:
        rec = run.artifact(f"trials/baseline-{t['task_id']}-r1")
        assert rec["evaluation"]["passed"] and rec["evaluation"]["evidence_backed"] and rec["partition"] == t["partition"] and rec["trial"]["mode"] == "mock"
    again = baseline_trials_stage(Context(run2, options={"repeats": 1}))
    assert again["trials"] == len(tasks)                                           # resumed from artifacts, nothing re-run


def test_live_baseline_stage_waits_for_approval_and_never_runs_without_it(tmp_path):
    run = make_run(tmp_path)
    assert run_tasks(run, None, n_tasks=4, feedback_round=False).status == "done"
    live = type(run).create(tmp_path, "live1", target="site-1", mode="live", stages=("baseline_trials",))
    # reuse the frozen artifacts of `run` for the live run directory
    import shutil
    shutil.copytree(run.dir / "artifacts", live.dir / "artifacts", dirs_exist_ok=True)
    shutil.copytree(run.dir / "private", live.dir / "private", dirs_exist_ok=True)
    shutil.copytree(run.dir / "snapshot", live.dir / "snapshot", dirs_exist_ok=True)
    stage = Stage("baseline_trials", baseline_trials_stage, spends=True, manifest=manifest)
    r = Pipeline([stage]).run(Context(live, options={"repeats": 2}))
    assert r.status == "awaiting_approval" and not list((live.dir / "artifacts").glob("trials/*"))
    m = manifest(Context(live, options={"repeats": 2}))
    blob = json.dumps(m)
    _, private = freezer.load(live)
    assert m["repeats"] == 2 and m["retries"] == 0 and not any(str(t["truth"]) in blob for t in private.values())
    live.approve("baseline_trials", r.manifest_sha256, "test approval")
    r2 = Pipeline([stage]).run(Context(live, options={"repeats": 2}))                     # approved, but no --allow-model-calls: the preflight refuses before any request
    assert r2.status == "failed" and "allow-model-calls" in r2.error
    assert not (live.dir / "spend").exists() or live.ledger(1).entries() == []
    # a different manifest (more repeats) is a different, unapproved manifest
    assert Pipeline([stage]).run(Context(live, options={"repeats": 3})).status in ("awaiting_approval", "failed")


def test_unknown_mock_behavior_and_missing_live_key_are_refused(tmp_path):
    run = frozen_run(tmp_path)
    inst = instance_for(run, "page_fact")
    with pytest.raises(ValueError):
        asyncio.run(run_trial(inst, zoo.snapshot("site-1"), provider="live", output=tmp_path / "x"))
    with pytest.raises(ValueError):
        asyncio.run(run_trial(inst, zoo.snapshot("site-1"), provider="nope", output=tmp_path / "x"))


def test_live_flow_stops_for_approval_at_taskgen_before_any_key_or_network(tmp_path, monkeypatch):
    from agent_readiness.investigate import flow
    monkeypatch.delenv("META_MODEL_API_KEY", raising=False)
    run, pipe, ctx = flow.build(tmp_path, "live-a", "site-4", mode="live", options={"n_tasks": 6})
    r = pipe.run(ctx)
    assert r.status == "awaiting_approval" and r.stage == "taskgen" and ctx.llm._client is None
    m = run.artifact(f"manifests/taskgen-{r.manifest_sha256[:16]}")
    assert m["model"] == "muse-spark-1.3" and m["max_requests"] == 3 and m["batches"] == 3 and m["retries_per_request"] == 0 and m["feedback_round"] is False and m["run_cap_usd"] == 0.15 and len(m["batch_prompt_sha256"]) == 3
    assert not (run.dir / "spend").exists()
    run.approve("taskgen", r.manifest_sha256, "unit test approval")
    r2 = flow.build(tmp_path, "live-a", "site-4", mode="live", options={"n_tasks": 6})[1].run(flow.build(tmp_path, "live-a", "site-4", mode="live", options={"n_tasks": 6})[2])
    assert r2.status == "failed" and "allow-model-calls" in r2.error                           # approved, but the flag is missing: preflight refuses, nothing sent or reserved
    assert not (run.dir / "private" / "llm-transcript.jsonl").exists()
    with pytest.raises(Halt):
        flow.build(tmp_path, "live-a", "site-4", mode="mock")                                    # a live investigation cannot be resumed as mock (or vice versa)


@pytest.mark.browser
def test_mock_flow_runs_the_whole_chain_through_report_with_a_scripted_investigator(tmp_path):
    from agent_readiness.investigate import flow
    from agent_readiness.investigate.llm import ScriptedClient
    from .test_investigate_investigator import scripted_model, step
    inv = ScriptedClient(scripted_model([step("list_trials"), step("finish", hyps=[])]))
    run, pipe, ctx = flow.build(tmp_path, "m1", "site-4", mode="mock", options={"n_tasks": 4, "investigator_llm": inv})
    res = pipe.run(ctx)
    assert res.status == "done" and all(run.status(s) == "done" for s in flow.STAGES)
    tasks = run.artifact("tasks-manifest")["tasks"]
    assert len(tasks) == 4 and all(run.artifact(f"trials/baseline-{t['task_id']}-r1")["evaluation"]["evidence_backed"] for t in tasks)
    rep = run.artifact("report")
    assert rep["outcome"] == "no_supported_issue" and rep["investigation"]["finished"] and rep["trials"]["by_attribution"] == {"success": 4} and rep["tasks"]["generator"]["mode"] == "none"
    assert rep["mode"] == "mock" and any("MOCK" in n for n in rep["notices"])
