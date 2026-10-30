"""L1a (offline): three-batch taskgen with isolated failures, the enforceable baseline stage cap, restart behaviour and manifest-versus-execution consistency. No network, no key, no browser."""
import asyncio
import json
import shutil

import pytest

from agent_readiness.investigate import allocation as alloc
from agent_readiness.investigate import flow, zoo
from agent_readiness.investigate.llm import LLMResponse, ScriptedClient, StructuredOutputError, request_sha256
from agent_readiness.investigate.llm.meta import ProviderError
from agent_readiness.investigate.pipeline import Context
from agent_readiness.investigate.run import InvestigationRun
from agent_readiness.investigate.taskgen import propose
from agent_readiness.investigate.taskgen.stage import taskgen_stage
from agent_readiness.capture import GateRefused
from agent_readiness.ledger import Halt, Ledger
from agent_readiness.spend_gate import RequestGate

from .test_investigate_taskgen import GOOD_TASKS, make_run, proposals_json

GOOD = proposals_json(GOOD_TASKS)
OTHER = proposals_json(GOOD_TASKS[1:])


def stage(run, llm, **opts):
    return taskgen_stage(Context(run, llm=llm, options={"n_tasks": 4, **opts}))


class Seq:
    """A client that plays a list of outcomes: a string = a response, an Exception = raised. Counts requests."""
    mode, model = "live", "muse-spark-1.3"

    def __init__(self, plan):
        self.plan, self.calls, self.violation = list(plan), [], None

    def complete(self, request):
        self.calls.append(request)
        out = self.plan[len(self.calls) - 1]
        if isinstance(out, Exception):
            raise out
        return LLMResponse(text=out, mode="live", model=self.model, usage={"prompt_tokens": 1000, "completion_tokens": 900}, cost_usd=0.01, request_sha256=request_sha256(request))


# ------------------------------------------------------------------------------------------------------------ partial batch failures
def test_a_batch_validation_failure_does_not_discard_the_successful_batches(tmp_path):
    run = make_run(tmp_path)
    llm = Seq([GOOD, "not json at all", OTHER])
    res = stage(run, llm)
    assert res["accepted"] >= 4 and len(llm.calls) == 3                                                       # one request per batch, no retry of the invalid one
    rep = run.artifact("taskgen-report")
    assert [c["status"] for c in rep["model_calls"]] == ["ok", "invalid", "ok"] and rep["model_calls"][1]["diagnostics"]["kind"] == "not_json"
    assert rep["rule_topup"] == 0 and [a["source"] for a in rep["accepted"]].count("model") >= 4
    for i in range(3):
        assert (run.dir / "private" / f"taskgen-batch-{i}.json").exists()


def test_all_batches_invalid_falls_back_to_rules_and_the_acceptance_gate_is_unchanged(tmp_path):
    run = make_run(tmp_path)
    res = stage(run, Seq(["x", "y", "z"]))
    assert res["by_source"]["rule"] >= 4 and res["by_source"]["model"] == 0


def test_a_provider_error_stops_further_requests_but_keeps_accepted_work(tmp_path):
    run = make_run(tmp_path)
    llm = Seq([GOOD, ProviderError("http", 429, "rate_limit"), GOOD])
    res = stage(run, llm)
    assert len(llm.calls) == 2 and res["accepted"] >= 4                                                        # batch 3 was never requested
    calls = run.artifact("taskgen-report")["model_calls"]
    assert [c["status"] for c in calls] == ["ok", "provider_error"] and "429" in calls[1]["error"]


def test_a_spend_gate_halt_is_critical_but_completed_batches_survive_and_a_restart_does_not_respend_them(tmp_path):
    run = make_run(tmp_path)
    llm = Seq([GOOD, Halt("spend gate refused the request: run cap"), GOOD])
    with pytest.raises(Halt):
        stage(run, llm)
    assert len(llm.calls) == 2 and (run.dir / "private" / "taskgen-batch-0.json").exists() and not (run.dir / "private" / "taskgen-batch-1.json").exists()
    assert not run.has_artifact("taskgen-report")                                                              # no half-finished report
    again = Seq([GOOD, OTHER])                                                                               # restart (an owner decision): batch 0 is NOT requested again
    res = stage(run, again)
    assert len(again.calls) == 2 and [c.messages[1]["content"] for c in again.calls] == [r.messages[1]["content"] for r in propose.batch_requests(run.artifact("site-profile"))[1:]]
    assert res["accepted"] >= 4 and [c["status"] for c in run.artifact("taskgen-report")["model_calls"]] == ["ok", "ok", "ok"]


def test_a_spend_gate_bound_violation_stops_the_stage_after_persisting_the_batch(tmp_path):
    run = make_run(tmp_path)

    class Violating(Seq):
        def complete(self, request):
            r = super().complete(request)
            self.violation = "actual calculated cost exceeded the reserved upper bound"
            return r
    llm = Violating([GOOD, GOOD, GOOD])
    with pytest.raises(Halt, match="bound violation"):
        stage(run, llm)
    assert len(llm.calls) == 1 and (run.dir / "private" / "taskgen-batch-0.json").exists()


def test_an_unexpected_critical_error_propagates_and_never_becomes_a_rule_fallback(tmp_path):
    run = make_run(tmp_path)
    with pytest.raises(RuntimeError, match="exhausted"):
        stage(run, ScriptedClient([GOOD]))                                                                      # the second request raises: critical, not a silent top-up
    assert not run.has_artifact("taskgen-report")


# ------------------------------------------------------------------------------------------------------------ spending enforcement
def _body(cap=100):
    return {"model": "m", "max_completion_tokens": cap, "messages": [{"role": "user", "content": "hi"}]}


def test_stage_cap_spans_all_trial_gates_is_durable_across_restarts_and_ignores_other_stages(tmp_path):
    led = Ledger(tmp_path, ceiling=2.05)
    scope = frozenset(f"baseline-t{i}-r1" for i in range(4))
    led.reserve("lg-taskgen:req01", 0.15)                                                                      # another stage: not counted against the baseline cap
    bound = 0.4
    mk = lambda i: RequestGate(led, f"baseline-t{i}-r1", per_request_cap=0.5, run_cap=0.5, scope_run_ids=scope, scope_cap=1.40)
    for i in range(3):
        led.reserve(f"baseline-t{i}-r1:req01", bound)                                                          # three trials already reserved 1.20 (as an earlier process would have)
    fresh = mk(3)                                                                                              # a NEW gate instance (restart) sees the durable ledger
    assert fresh.scope_committed() == 1.2
    body = _body(cap=int(0.3 / 4.25e-6))                                                                       # ~US$0.30 upper bound: 1.20 + 0.30 > 1.40
    with pytest.raises(GateRefused, match="stage cap"):
        fresh.reserve(1, body)
    small = _body(cap=int(0.1 / 4.25e-6))                                                                      # ~US$0.10 fits: 1.20 + 0.10 <= 1.40
    assert fresh.reserve(1, small)["upper_bound_usd"] <= 0.2


def test_stage_cap_counts_the_settled_cost_not_the_reservation_once_known(tmp_path):
    led = Ledger(tmp_path, ceiling=2.05)
    scope = frozenset({"baseline-a-r1", "baseline-b-r1"})
    g = RequestGate(led, "baseline-a-r1", per_request_cap=0.5, run_cap=0.5, scope_run_ids=scope, scope_cap=1.40)
    g.reserve(1, _body(cap=int(0.3 / 4.25e-6)))
    assert g.scope_committed() > 0.29
    g.settle(1, {"http_status": 200, "usage": {"prompt_tokens": 100, "completion_tokens": 100}})
    assert g.scope_committed() < 0.001


def test_a_bound_violation_survives_a_restart(tmp_path):
    led = Ledger(tmp_path, ceiling=2.05)
    g = RequestGate(led, "r", per_request_cap=0.5, run_cap=0.5)
    g.reserve(1, _body(10))
    g.settle(1, {"http_status": 200, "usage": {"prompt_tokens": 100000, "completion_tokens": 10}})             # actual far above the reservation
    assert g.violation
    revived = RequestGate(led, "r", per_request_cap=0.5, run_cap=0.5)                                          # new process, same durable ledger
    assert revived.violation
    with pytest.raises(GateRefused, match="bound violation"):
        revived.reserve(2, _body(10))
    assert RequestGate(led, "other", per_request_cap=0.5, run_cap=0.5).violation is None                        # other runs are unaffected


def test_allocation_adds_up_and_flags_a_ceiling_that_cannot_hold_it():
    a = alloc.allocation(2.05)
    assert a["stage_caps_usd"] == {"taskgen": 0.15, "baseline_trials": 1.40, "investigate": 0.40} and a["allocated_usd"] == 1.95 and a["unallocated_usd"] == 0.10 and a["allocation_fits_ceiling"]
    assert not alloc.allocation(1.75)["allocation_fits_ceiling"] and alloc.allocation(1.75)["unallocated_usd"] < 0


@pytest.mark.parametrize("sid", zoo.ids())
def test_taskgen_worst_case_fits_its_stage_and_per_request_caps_on_every_site(tmp_path, sid):
    run = make_run(tmp_path, sid, f"w-{sid}")
    m = flow.taskgen_manifest(Context(run, options={"total_cap_usd": 2.05}))
    assert max(m["per_request_reservation_usd"]) <= alloc.PER_REQUEST_CAP_USD and m["worst_case_stage_usd"] <= alloc.TASKGEN_CAP_USD
    assert m["worst_case_stage_usd"] + alloc.BASELINE_CAP_USD + alloc.INVESTIGATE_CAP_USD <= 2.05                  # all stage worst cases fit inside the ledger ceiling


# ------------------------------------------------------------------------------------------------------------ manifest == execution
def test_executed_taskgen_requests_match_the_approved_manifest(tmp_path):
    run = make_run(tmp_path, "site-5", "mc")
    ctx = Context(run, options={"n_tasks": 8, "total_cap_usd": 2.05})
    m = flow.taskgen_manifest(ctx)
    llm = Seq([GOOD, OTHER, GOOD])
    taskgen_stage(Context(run, llm=llm, options={"n_tasks": 8}))
    assert [request_sha256(r) for r in llm.calls] == m["batch_request_sha256"] and [json.dumps(r.messages, sort_keys=True) for r in llm.calls] == [json.dumps(r.messages, sort_keys=True) for r in propose.batch_requests(run.artifact("site-profile"))]
    assert len(llm.calls) == m["max_requests"] == m["batches"] and all(r.max_tokens == m["max_completion_tokens"] for r in llm.calls)
    from agent_readiness.suite.core import canonical_hash
    assert [canonical_hash(r.messages) for r in llm.calls] == m["batch_prompt_sha256"] and len({*m["batch_prompt_sha256"]}) == 3


def test_the_spend_gate_is_built_with_the_manifest_numbers(tmp_path, monkeypatch):
    seen = []

    class Stub:
        mode, model = "live", "muse-spark-1.3"
        gate = type("G", (), {"violation": None})()

        def complete(self, request):
            return LLMResponse(text="x", mode="live", model="m")
    monkeypatch.setattr(flow.MetaClient, "live", classmethod(lambda cls, cfg, ledger, run_id, **kw: (seen.append({"run_id": run_id, "ceiling": ledger.ceiling, **kw}) or Stub())))
    run, pipe, ctx = flow.build(tmp_path, "mm", "site-5", mode="live", options={"total_cap_usd": 2.05, "n_tasks": 8})
    from agent_readiness.investigate.inspect.stage import run_inspect
    run_inspect(ctx, zoo.snapshot("site-5"))
    m = flow.taskgen_manifest(ctx)
    ctx.llm.complete(propose.batch_requests(run.artifact("site-profile"))[0])
    (g,) = seen
    assert g["run_cap_usd"] == m["run_cap_usd"] and g["per_request_cap_usd"] == m["per_request_cap_usd"] and g["max_requests"] == m["max_requests"] and g["ceiling"] == m["allocation"]["ledger_ceiling_usd"] == 2.05
    ctx.options["investigator_llm"].complete(propose.batch_requests(run.artifact("site-profile"))[0])
    inv = seen[1]
    assert inv["run_cap_usd"] == alloc.INVESTIGATE_CAP_USD and inv["per_request_cap_usd"] == alloc.PER_REQUEST_CAP_USD and inv["max_requests"] == 2 * (12 + 1)


def test_baseline_trial_gates_are_built_with_the_manifest_stage_cap_and_halt_when_it_binds(tmp_path, monkeypatch):
    from agent_readiness.investigate.trials import stage as ts
    from .test_investigate_investigator import ws_for
    src = ws_for(tmp_path, name="src").run
    live = InvestigationRun.create(tmp_path, "livebase", target="site-1", mode="live", stages=flow.STAGES)
    for d in ("artifacts", "private", "snapshot"):
        shutil.copytree(src.dir / d, live.dir / d, dirs_exist_ok=True)
    (live.dir / "trial-data").mkdir()
    for old in (live.dir / "artifacts" / "trials").glob("*"):
        old.unlink()                                                                                              # start from the frozen tasks only
    gates, refused, cur = [], {"on": None}, {"run": live}

    async def fake_trial(instance, snap, *, output, request_gate, label, **kw):
        gates.append(request_gate)
        out = cur["run"].dir / "trial-data" / f"t{len(gates)}"
        out.mkdir(parents=True, exist_ok=True)
        status = "completed"
        if refused["on"] == len(gates):
            try:
                request_gate.reserve(1, {"model": "m", "max_completion_tokens": 4096, "messages": [{"role": "user", "content": "x"}]})
            except GateRefused:
                status = "estimated_cost_limit"
        else:
            request_gate.reserve(1, {"model": "m", "max_completion_tokens": 100, "messages": [{"role": "user", "content": "x"}]})
        return {"artifact_path": str(out), "outcome": {"run_status": status}, "evaluation": {"passed": True, "evidence_backed": True}, "metrics": {"model_requests": 1, "page_views": 1}}
    monkeypatch.setattr(ts, "run_trial", fake_trial)
    monkeypatch.setattr(ts, "preflight", lambda cfg, allow: "k")
    ctx = Context(live, options={"total_cap_usd": 2.05, "allow_model_calls": True})
    m = ts.manifest(ctx)
    ts.baseline_trials_stage(ctx)
    tasks = live.artifact("tasks-manifest")["tasks"]
    assert len(gates) == len(tasks)
    expected_scope = {f"baseline-{t['task_id']}-r1" for t in tasks}
    for g in gates:
        assert g.scope_cap == m["stage_cap_usd"] == 1.40 and set(g.scope_run_ids) == expected_scope and g.run_cap == m["run_cap_usd"] and g.max_requests == m["max_requests_per_trial"] and g.per_request_cap == m["per_request_cap_usd"]
    # the cap binds: pre-commit 1.39 of the stage, then the next trial's reservation is refused -> void -> the stage halts (never a website result)
    live2 = InvestigationRun.create(tmp_path, "livebase2", target="site-1", mode="live", stages=flow.STAGES)
    for d in ("artifacts", "private", "snapshot"):
        shutil.copytree(live.dir / d, live2.dir / d, dirs_exist_ok=True)
    (live2.dir / "trial-data").mkdir()
    for old in (live2.dir / "artifacts" / "trials").glob("*"):
        old.unlink()
    (live2.dir / "artifacts" / "arm-config.json").unlink(missing_ok=True)
    ctx2 = Context(live2, options={"total_cap_usd": 2.05, "allow_model_calls": True})
    led = live2.ledger(2.05)
    first = tasks[0]["task_id"]
    led.reserve(f"baseline-{first}-r1:req09", 1.39)
    gates.clear()
    cur["run"] = live2
    refused["on"] = 1
    with pytest.raises(Halt, match="void trial"):
        ts.baseline_trials_stage(ctx2)
    assert len(gates) == 1 and led.committed() <= 2.05


# ------------------------------------------------------------------------------------------------------------ crash window: request reserved/sent, result not persisted
from agent_readiness.investigate.taskgen.stage import AmbiguousBatchAttempt, recover_batch


class Killed(Seq):
    """Simulates the process dying (BaseException, not caught by the stage) during batch `at`: optionally AFTER the ledger reserved (and optionally settled) the request."""

    def __init__(self, run, plan, at=0, reserve=True, settle=False):
        super().__init__(plan)
        self.run, self.at, self.reserve, self.settle = run, at, reserve, settle

    def complete(self, request):
        if len(self.calls) == self.at:
            self.calls.append(request)
            led = self.run.ledger(2.05)
            if self.reserve:
                led.reserve(f"{self.run.state['id']}-taskgen:req{self.at + 1:02d}", 0.03)
                if self.settle:
                    led.settle(f"{self.run.state['id']}-taskgen:req{self.at + 1:02d}", 0.011)
            raise SystemExit("killed")
        return super().complete(request)


def never(request):
    raise AssertionError("an ambiguous batch must NOT be re-sent")


def test_the_attempt_marker_is_durable_before_the_request_leaves(tmp_path):
    run = make_run(tmp_path)
    seen = []

    class Spy(Seq):
        def complete(self, request):
            marker = run.dir / "private" / f"taskgen-attempt-{len(self.calls)}.json"
            seen.append(marker.exists() and json.loads(marker.read_text()))
            return super().complete(request)
    stage(run, Spy([GOOD, OTHER, GOOD]))
    assert all(m and m["request_sha256"] and "reserved_before" in m for m in seen) and len(seen) == 3                 # written before each of the three sends


@pytest.mark.parametrize("settle", [False, True])
def test_a_request_reserved_but_not_persisted_is_never_re_sent_until_the_owner_decides(tmp_path, settle):
    run = make_run(tmp_path)
    with pytest.raises(SystemExit):
        stage(run, Killed(run, [GOOD, OTHER, GOOD], at=0, settle=settle))                                       # killed after reserve (and, in one case, after the response was settled)
    assert (run.dir / "private" / "taskgen-attempt-0.json").exists() and not (run.dir / "private" / "taskgen-batch-0.json").exists()
    resend = Seq([never])
    with pytest.raises(AmbiguousBatchAttempt, match="NOT re-sent automatically") as ei:                         # restart: refuses, sends nothing
        taskgen_stage(Context(run, llm=resend, options={"n_tasks": 4}))
    assert resend.calls == [] and "recover-batch" in str(ei.value) and isinstance(ei.value, Halt)
    with pytest.raises(AmbiguousBatchAttempt):                                                                  # and again: the refusal is stable, nothing changes until the owner acts
        taskgen_stage(Context(run, llm=Seq([never]), options={"n_tasks": 4}))
    rec = recover_batch(run, 0, note="owner: abandon batch 0, accept the unknown cost")
    assert rec["status"] == "abandoned" and rec["meta"]["note"].startswith("owner") and rec["drafts"] == []
    cont = Seq([OTHER, GOOD])                                                                                 # explicit recovery: ONLY the two remaining batches are requested
    res = stage(run, cont)
    assert len(cont.calls) == 2 and res["accepted"] >= 4
    assert [c["status"] for c in run.artifact("taskgen-report")["model_calls"]] == ["abandoned", "ok", "ok"]
    assert [c.messages[1]["content"] for c in cont.calls] == [r.messages[1]["content"] for r in propose.batch_requests(run.artifact("site-profile"))[1:]]


def test_a_crash_before_any_reservation_is_provably_safe_and_resumes_automatically(tmp_path):
    run = make_run(tmp_path)
    with pytest.raises(SystemExit):
        stage(run, Killed(run, [GOOD, OTHER, GOOD], at=0, reserve=False))                                       # died before the gate reserved anything: the request never left
    assert (run.dir / "private" / "taskgen-attempt-0.json").exists()
    again = Seq([GOOD, OTHER, GOOD])
    res = stage(run, again)
    assert len(again.calls) == 3 and res["accepted"] >= 4                                                      # all three batches requested, none refused as ambiguous


def test_a_crash_in_a_later_batch_keeps_the_finished_ones_and_flags_only_the_ambiguous_one(tmp_path):
    run = make_run(tmp_path)
    run.ledger(2.05).reserve(f"{run.state['id']}-taskgen:req01", 0.03)                                          # batch 0's request, reserved and answered normally
    with pytest.raises(SystemExit):
        stage(run, Killed(run, [GOOD, OTHER, GOOD], at=1, reserve=False))
    # killed in batch 1 after reserving: add that reservation as the dying process would have
    run.ledger(2.05).reserve(f"{run.state['id']}-taskgen:req02", 0.03)
    assert (run.dir / "private" / "taskgen-batch-0.json").exists() and (run.dir / "private" / "taskgen-attempt-1.json").exists()
    rest = Seq([never])
    with pytest.raises(AmbiguousBatchAttempt, match="batch 1"):
        taskgen_stage(Context(run, llm=rest, options={"n_tasks": 4}))
    assert rest.calls == []


def test_recovery_is_explicit_and_refuses_when_there_is_nothing_to_recover(tmp_path):
    run = make_run(tmp_path)
    with pytest.raises(ValueError, match="no attempt marker"):
        recover_batch(run, 0, note="x")
    stage(run, Seq([GOOD, OTHER, GOOD]))
    with pytest.raises(ValueError, match="already has a persisted result"):
        recover_batch(run, 0, note="x")
    run2 = make_run(tmp_path, name="r2")
    with pytest.raises(SystemExit):
        stage(run2, Killed(run2, [GOOD], at=0, reserve=False))
    with pytest.raises(ValueError, match="note"):
        recover_batch(run2, 0, note="  ")


def test_cli_recover_batch_requires_abandon_and_a_note_and_never_resends(tmp_path, monkeypatch, capsys):
    from agent_readiness.cli import main as cli_main
    run = make_run(tmp_path)
    with pytest.raises(SystemExit):
        stage(run, Killed(run, [GOOD], at=0))
    argv = lambda *a: monkeypatch.setattr("sys.argv", ["readiness", "investigate", "recover-batch", str(run.dir), *a])
    argv("--batch", "0", "--note", "n")                                                                         # --abandon is mandatory
    with pytest.raises(SystemExit):
        cli_main()
    argv("--batch", "0", "--abandon")                                                                           # --note is mandatory
    with pytest.raises(SystemExit):
        cli_main()
    assert not (run.dir / "private" / "taskgen-batch-0.json").exists()
    argv("--batch", "0", "--abandon", "--note", "owner decided")
    cli_main()
    assert "recorded as abandoned" in capsys.readouterr().out and json.loads((run.dir / "private" / "taskgen-batch-0.json").read_text())["status"] == "abandoned"
    argv("--batch", "0", "--abandon", "--note", "again")
    with pytest.raises(SystemExit, match="recovery refused"):
        cli_main()


def test_the_ambiguous_request_still_counts_toward_the_three_request_limit(tmp_path):
    led = Ledger(tmp_path, ceiling=2.05)
    led.reserve("r-taskgen:req01", 0.03)                                                                        # the abandoned batch's reservation stays in the durable ledger
    gate = RequestGate(led, "r-taskgen", per_request_cap=0.05, run_cap=0.15, max_requests=3)
    gate.reserve(2, _body(100))
    gate.reserve(3, _body(100))
    with pytest.raises(GateRefused, match="request-count cap"):
        gate.reserve(4, _body(100))                                                                             # a re-send of batch 0 would be a fourth request: impossible inside the approved manifest
