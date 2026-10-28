"""Task 006 Stage 2 driver: schedule, persistence, halts, approvals and no-repeat guarantees (offline, fake runs)."""
import copy
import json
from pathlib import Path
import pytest
from agent_readiness import pilot
from agent_readiness.pilot import PilotError

ZERO_RECORD = dict(status="completed", stop_reason="agent_done", evaluation={"passed": True}, model_request_count=2,
                   protocol_compliance={"raw_protocol_compliant": 2}, elapsed_seconds=10.0,
                   estimated_cost={"cumulative_estimated_sent_usd": 0.06}, metrics={"cost": {"calculated_actual_usd": 0.03},
                   "tokens": {"prompt": 1, "completion": 1}, "navigation": {}, "strategy": {}},
                   profile_hash="p", configuration_hash="c", browser_version="Chrome/1", inventory_hash="i",
                   model={"model": "muse-spark-1.3"}, provenance={"code_hash": "h", "git_commit": "abc", "packages": {}})


class Fake:
    def __init__(self, tmp, mutate=None, raise_on=None):
        self.calls, self.mutate, self.raise_on, self.tmp = [], mutate or {}, raise_on, tmp
        self.state_seen = []

    async def __call__(self, **kwargs):
        index = len(self.calls) + 1
        self.calls.append(kwargs)
        if self.raise_on == index:
            raise RuntimeError("boom")
        record = copy.deepcopy(ZERO_RECORD)
        record["run_id"] = f"run-{index:02d}"
        record["storefront_variant"] = kwargs["storefront_variant"]
        for key, value in self.mutate.get(index, {}).items():
            record[key] = value
        return Path(self.tmp) / f"run-{index:02d}", record


def live(tmp, fake, **kw):
    state = pilot.load(tmp)
    return pilot.drive(tmp, fake, mode="live", allow_model_calls=True, approved_schedule_sha256=state["schedule_sha256"], **kw)


async def test_schedule_is_the_preregistered_24_run_counterbalanced_design():
    entries = pilot.build_schedule()
    assert len(entries) == 24 and [e["position"] for e in entries] == list(range(1, 25))
    assert [(e["seed"], e["arm"]) for e in entries[:4]] == [(2, "A"), (2, "B"), (2, "B"), (2, "A")]
    patterns = {}
    for e in entries:
        patterns.setdefault(e["seed"], "")
        patterns[e["seed"]] += e["arm"]
    assert list(patterns.items()) == [(2, "ABBA"), (9, "BAAB"), (7, "BAAB"), (5, "ABBA"), (14, "ABBA"), (13, "BAAB")]
    cells = {(e["seed"], e["arm"], e["repetition"]) for e in entries}
    assert len(cells) == 24 and sum(e["arm"] == "A" for e in entries) == 12
    first = [patterns[s][0] for s in patterns]
    assert first.count("A") == first.count("B") == 3
    assert {e["storefront_variant"] for e in entries if e["arm"] == "A"} == {"baseline-detail-v1"}
    assert {e["storefront_variant"] for e in entries if e["arm"] == "B"} == {"link-info-placement-b-v1"}
    assert pilot.FROZEN | {} == {"profile_id": "natural-shopping-v3-compat1", "provider": "meta", "model": "muse-spark-1.3",
        "kind": "discovery", "max_steps": 6, "max_model_requests": 6, "timeout_seconds": 120, "max_estimated_cost_usd": 0.04,
        "max_cumulative_estimated_cost_usd": 0.25, "expect_schema_sha256": "c80ef8b813abef0b2afd79c83a6f31e857c0101ea8730952ee78d61e65f9a194"}
    assert pilot.LIMITS == {"pilot_estimated_cap_usd": 6.0, "review_halt_actual_usd": 2.0, "max_consecutive_model_output_errors": 2}
    assert pilot.schedule_sha256() == pilot.schedule_sha256()


async def test_plan_is_idempotent_and_refuses_a_different_schedule_or_mode(tmp_path):
    first = pilot.plan(tmp_path)
    assert pilot.plan(tmp_path) == first
    with pytest.raises(PilotError):
        pilot.plan(tmp_path, "smoke")


async def test_live_execution_needs_the_flag_and_the_exact_schedule_hash_and_calls_nothing_otherwise(tmp_path):
    pilot.plan(tmp_path)
    fake = Fake(tmp_path)
    for kwargs in ({}, {"allow_model_calls": True}, {"allow_model_calls": True, "approved_schedule_sha256": "0" * 64},
                   {"approved_schedule_sha256": pilot.load(tmp_path)["schedule_sha256"]}):
        with pytest.raises(PilotError):
            await pilot.drive(tmp_path, fake, mode="live", **kwargs)
    assert fake.calls == []
    with pytest.raises(PilotError):
        await pilot.drive(tmp_path, fake, mode="smoke")   # a live state is never run as a rehearsal, or vice versa
    assert fake.calls == []


async def test_frozen_configuration_drift_after_planning_blocks_live_execution(tmp_path, monkeypatch):
    pilot.plan(tmp_path)
    monkeypatch.setitem(pilot.FROZEN, "max_steps", 7)
    fake = Fake(tmp_path)
    with pytest.raises(PilotError):
        await live(tmp_path, fake)
    assert fake.calls == []


async def test_tampered_state_is_detected(tmp_path):
    state = pilot.plan(tmp_path)
    state["entries"][3]["seed"] = 99
    pilot.save(tmp_path, state)
    with pytest.raises(PilotError):
        await live(tmp_path, Fake(tmp_path))
    state = pilot.plan(tmp_path.joinpath("x"))
    state["limits"]["pilot_estimated_cap_usd"] = 100
    pilot.save(tmp_path / "x", state)
    with pytest.raises(PilotError, match="altered"):
        await live(tmp_path / "x", Fake(tmp_path))


async def test_full_live_schedule_runs_in_order_with_frozen_kwargs_and_is_never_repeated(tmp_path):
    pilot.plan(tmp_path)
    fake = Fake(tmp_path)
    state = await live(tmp_path, fake)
    assert len(fake.calls) == 24 and state["halt"] is None and all(e["status"] == "done" for e in state["entries"])
    assert [(c["seed"], c["storefront_variant"]) for c in fake.calls] == [(e["seed"], e["storefront_variant"]) for e in pilot.build_schedule()]
    for call in fake.calls:
        assert (call["mode"], call["kind"], call["max_steps"], call["max_model_requests"], call["timeout_seconds"]) == ("live", "discovery", 6, 6, 120)
        assert (call["profile_id"], call["max_estimated_cost_usd"], call["max_cumulative_estimated_cost_usd"], call["allow_model_calls"]) == (
            "natural-shopping-v3-compat1", 0.04, 0.25, True)
        assert call["expect_schema_sha256"] == pilot.FROZEN["expect_schema_sha256"]
    first = state["entries"][0]["result"]
    assert first["run_id"] == "run-01" and first["run_status"] == "completed" and first["stop_reason"] == "agent_done" and first["evaluator_passed"] is True
    again = Fake(tmp_path)
    await live(tmp_path, again)
    assert again.calls == []                                   # completed runs are never repeated
    assert not list(Path(tmp_path).glob("*.tmp"))
    assert [a["event"] for a in pilot.load(tmp_path)["audit"]].count("run_started") == 24


async def test_state_is_persisted_as_running_before_each_run_and_max_runs_limits_execution(tmp_path):
    pilot.plan(tmp_path)
    seen = []

    async def spy(**kwargs):
        state = pilot.load(tmp_path)
        seen.append([e["status"] for e in state["entries"]][:3])
        return await fake(**kwargs)
    fake = Fake(tmp_path)
    await live(tmp_path, spy, max_runs=2)
    assert seen == [["running", "pending", "pending"], ["done", "running", "pending"]] and len(fake.calls) == 2
    await live(tmp_path, fake, max_runs=1)
    assert len(fake.calls) == 3


@pytest.mark.parametrize("status,kind", [("diagnostic_fidelity_violation", "fidelity_violation"), ("estimated_cost_limit", "cost_cap_block"),
                                         ("infrastructure_error", "infrastructure_failure"), ("setup_error", "setup_failure")])
async def test_failure_statuses_halt_the_pilot_and_nothing_continues_without_approval(tmp_path, status, kind):
    pilot.plan(tmp_path)
    fake = Fake(tmp_path, mutate={2: {"status": status, "stop_reason": "x"}})
    state = await live(tmp_path, fake)
    assert len(fake.calls) == 2 and state["halt"]["kind"] == kind and not state["halt"]["resolved"]
    with pytest.raises(PilotError, match="halted"):
        await live(tmp_path, fake)
    assert len(fake.calls) == 2
    with pytest.raises(PilotError, match="approval note"):
        pilot.resume(tmp_path, "  ")
    pilot.resume(tmp_path, "reviewed; continue")
    state = await live(tmp_path, fake, max_runs=1)
    assert len(fake.calls) == 3 and state["entries"][1]["status"] == "done" and state["entries"][2]["status"] == "done"
    assert [e["status"] for e in state["entries"]].count("done") == 3        # the halted run was not repeated
    assert any(a["event"] == "resume_approved" and a["note"] == "reviewed; continue" for a in state["audit"])


async def test_version_drift_halts(tmp_path):
    pilot.plan(tmp_path)
    fake = Fake(tmp_path, mutate={3: {"browser_version": "Chrome/2"}})
    state = await live(tmp_path, fake)
    assert len(fake.calls) == 3 and state["halt"]["kind"] == "version_drift" and "browser_version" in state["halt"]["detail"]


async def test_two_consecutive_model_output_errors_halt_but_one_does_not(tmp_path):
    pilot.plan(tmp_path / "a")
    fake = Fake(tmp_path, mutate={2: {"status": "model_output_error"}, 4: {"status": "model_output_error"}})
    state = await live(tmp_path / "a", fake, max_runs=5)
    assert state["halt"] is None and len(fake.calls) == 5
    pilot.plan(tmp_path / "b")
    fake = Fake(tmp_path, mutate={2: {"status": "model_output_error"}, 3: {"status": "model_output_error"}})
    state = await live(tmp_path / "b", fake)
    assert len(fake.calls) == 3 and state["halt"]["kind"] == "consecutive_model_output_errors"


async def test_review_spend_halt_needs_a_higher_explicitly_approved_threshold(tmp_path):
    pilot.plan(tmp_path)
    expensive = {"metrics": {"cost": {"calculated_actual_usd": 0.5}, "tokens": {}, "navigation": {}, "strategy": {}}}
    fake = Fake(tmp_path, mutate={i: expensive for i in range(1, 25)})
    state = await live(tmp_path, fake)
    assert len(fake.calls) == 5 and state["halt"]["kind"] == "review_spend"      # 5 x 0.5 = 2.5 > 2.00
    with pytest.raises(PilotError, match="new threshold"):
        pilot.resume(tmp_path, "ok")
    with pytest.raises(PilotError, match="new threshold"):
        pilot.resume(tmp_path, "ok", new_review_halt_usd=2.0)
    state = pilot.resume(tmp_path, "approved 4.00", new_review_halt_usd=4.0)
    assert state["limits"]["review_halt_actual_usd"] == 4.0 and state["limits_approved"]["review_halt_actual_usd"] == 2.0
    state = await live(tmp_path, fake)
    assert len(fake.calls) == 9 and state["halt"]["kind"] == "review_spend"      # 8 x 0.5 = 4.0 is not > 4.0; the 9th (4.5) is
    assert pilot.spend(state)["calculated_actual_usd"] > 4.0


async def test_pilot_wide_estimated_cap_halts_before_a_run_that_could_exceed_it(tmp_path, monkeypatch):
    monkeypatch.setitem(pilot.LIMITS, "pilot_estimated_cap_usd", 0.6)
    pilot.plan(tmp_path)
    fake = Fake(tmp_path)                       # each fake run reports 0.06 worst-case sent; next run commits 0.25
    state = await live(tmp_path, fake)
    done = len(fake.calls)
    assert state["halt"]["kind"] == "pilot_estimated_cap" and 0.06 * done + 0.25 > 0.6 >= 0.06 * (done - 1) + 0.25
    assert state["entries"][done]["status"] == "pending"


async def test_exception_in_a_run_halts_and_the_run_is_not_retried(tmp_path):
    pilot.plan(tmp_path)
    fake = Fake(tmp_path, raise_on=2)
    state = await live(tmp_path, fake)
    assert len(fake.calls) == 2 and state["halt"]["kind"] == "driver_exception"
    assert state["entries"][1]["status"] == "done" and state["entries"][1]["result"]["run_status"] == "driver_exception"
    pilot.resume(tmp_path, "inspected")
    await live(tmp_path, fake, max_runs=1)
    assert len(fake.calls) == 3


async def test_a_crashed_run_is_marked_interrupted_halts_and_is_never_repeated(tmp_path):
    state = pilot.plan(tmp_path)
    state["entries"][0]["status"] = "done"
    state["entries"][0]["result"] = pilot.summarize(copy.deepcopy(ZERO_RECORD) | {"run_id": "r1"}, tmp_path)
    state["entries"][1]["status"] = "running"            # the process died during this run
    pilot.save(tmp_path, state)
    fake = Fake(tmp_path)
    with pytest.raises(PilotError, match="halted"):
        await live(tmp_path, fake)
    assert fake.calls == []
    state = pilot.load(tmp_path)
    assert state["entries"][1]["status"] == "interrupted" and state["halt"]["kind"] == "interrupted_run"
    pilot.resume(tmp_path, "checked the artifact; spend accounted for")
    await live(tmp_path, fake, max_runs=1)
    state = pilot.load(tmp_path)
    assert fake.calls[0]["seed"] == state["entries"][2]["seed"] and state["entries"][1]["status"] == "interrupted"


async def test_smoke_rehearsal_passes_no_model_arguments_and_is_separate(tmp_path):
    pilot.plan(tmp_path, "smoke")
    fake = Fake(tmp_path)
    state = await pilot.drive(tmp_path, fake, mode="smoke", max_runs=2)
    assert all(c["mode"] == "smoke" and "allow_model_calls" not in c and "profile_id" not in c for c in fake.calls)
    assert state["mode"] == "smoke"
