"""Durable run directory, write-once artifacts, approvals, and the stage machine's gates (plan §5, D12)."""
import json

import pytest

from agent_readiness.investigate.pipeline import Context, Pipeline, Stage
from agent_readiness.investigate.run import ArtifactExists, InvestigationRun, NeedsApproval


def make_run(tmp_path, mode="scripted", stages=("a", "b", "c")):
    return InvestigationRun.create(tmp_path, "run1", target="site", mode=mode, stages=stages, config={"k": 1})


def test_create_validates_id_and_refuses_duplicates(tmp_path):
    make_run(tmp_path)
    with pytest.raises(FileExistsError):
        make_run(tmp_path)
    for bad in ("../x", "a/b", "", "-x", "a" * 80):
        with pytest.raises(ValueError):
            InvestigationRun.create(tmp_path, bad, target="t", mode="mock", stages=("a",))
    with pytest.raises(FileNotFoundError):
        InvestigationRun(tmp_path / "nope")


def test_artifacts_are_write_once(tmp_path):
    run = make_run(tmp_path)
    run.write_artifact("tasks", {"a": 1})
    assert run.write_artifact("tasks", {"a": 1})                       # identical re-write is a no-op
    with pytest.raises(ArtifactExists):
        run.write_artifact("tasks", {"a": 2})
    assert run.artifact("tasks") == {"a": 1} and run.has_artifact("tasks") and not run.has_artifact("other")
    for bad in ("../escape", "a/../../b"):
        with pytest.raises(ValueError):
            run.write_artifact(bad, {})


def test_approval_binds_to_the_exact_manifest_hash(tmp_path):
    run = make_run(tmp_path)
    m = {"stage": "a", "cap_usd": 1.0}
    with pytest.raises(NeedsApproval) as ei:
        run.require_approval("a", m)
    h = ei.value.manifest_sha256
    assert h == run.manifest_sha256(m) and run.has_artifact(f"manifests/a-{h[:16]}")
    with pytest.raises(ValueError):
        run.approve("a", h, "  ")
    run.approve("a", h, "owner approves cap 1.0")
    assert run.require_approval("a", m) == h
    with pytest.raises(NeedsApproval):
        run.require_approval("a", {**m, "cap_usd": 2.0})              # a changed manifest needs a new approval
    with pytest.raises(KeyError):
        run.approve("zzz", h, "n")


def test_ledger_is_the_existing_usd_ledger(tmp_path):
    led = make_run(tmp_path).ledger(0.10)
    led.reserve("x", 0.05)
    with pytest.raises(Exception):
        led.reserve("y", 0.08)
    assert led.committed() == 0.05


def test_stages_run_in_order_skip_done_and_resume(tmp_path):
    run, seen = make_run(tmp_path), []
    pipe = Pipeline([Stage(n, (lambda n: lambda ctx: seen.append(n))(n)) for n in ("a", "b", "c")])
    assert pipe.run(Context(run), until="b").status == "done" and seen == ["a", "b"]
    assert pipe.run(Context(run)).status == "done" and seen == ["a", "b", "c"]
    pipe.run(Context(run))
    assert seen == ["a", "b", "c"] and run.status("c") == "done"


def test_failed_spending_stage_is_not_rerun_but_a_free_stage_is_recorded(tmp_path):
    run = make_run(tmp_path, stages=("a", "b"))
    calls = []

    def boom(ctx):
        calls.append(1)
        raise RuntimeError("provider exploded")
    pipe = Pipeline([Stage("a", lambda c: None), Stage("b", boom, spends=True)])
    r = pipe.run(Context(run))
    assert r.status == "failed" and r.stage == "b" and "provider exploded" in r.error and run.state["stages"]["b"]["status"] == "failed"
    r2 = pipe.run(Context(run))
    assert r2.status == "failed" and calls == [1]                                              # never silently retried (a retry could bill again)


def test_live_spending_stage_waits_for_approval_and_does_not_run(tmp_path):
    run = make_run(tmp_path, mode="live", stages=("a", "b"))
    ran = []
    stage = Stage("b", lambda c: ran.append("b"), spends=True, manifest=lambda c: {"cap": 1.5})
    pipe = Pipeline([Stage("a", lambda c: None), stage])
    r = pipe.run(Context(run))
    assert r.status == "awaiting_approval" and r.stage == "b" and not ran and run.status("b") == "awaiting_approval"
    run.approve("b", "0" * 64, "wrong hash")
    assert pipe.run(Context(run)).status == "awaiting_approval" and not ran
    run.approve("b", r.manifest_sha256, "owner approves")
    assert pipe.run(Context(run)).status == "done" and ran == ["b"]


def test_non_live_spending_stage_needs_no_approval_but_a_gate_always_does(tmp_path):
    run = make_run(tmp_path, mode="mock", stages=("a", "g"))
    ran = []
    pipe = Pipeline([Stage("a", lambda c: ran.append("a"), spends=True), Stage("g", lambda c: ran.append("g"), manifest=lambda c: {"apply": "p1"}, gate=True)])
    r = pipe.run(Context(run))
    assert ran == ["a"] and r.status == "awaiting_approval" and r.stage == "g"
    run.approve("g", r.manifest_sha256, "apply proposal p1")
    assert pipe.run(Context(run)).status == "done" and ran == ["a", "g"]


def test_stage_without_manifest_cannot_be_gated(tmp_path):
    run = make_run(tmp_path, mode="live", stages=("a",))
    with pytest.raises(ValueError):
        Pipeline([Stage("a", lambda c: None, spends=True)]).run(Context(run))


def test_duplicate_stage_names_rejected():
    with pytest.raises(ValueError):
        Pipeline([Stage("a", lambda c: None), Stage("a", lambda c: None)])


def test_state_file_is_json_and_records_summaries(tmp_path):
    run = make_run(tmp_path, stages=("a",))
    Pipeline([Stage("a", lambda c: {"n": 3})]).run(Context(run))
    s = json.loads((run.dir / "run.json").read_text())
    assert s["schema"] == "investigation-run-v1" and s["stages"]["a"]["summary"] == {"n": 3} and s["config_sha256"]
