"""Investigator incident repair (offline): the single-`action` recovery crash, request accounting that survives parse failures, terminal status, and the recovery fork (provenance, approvals, spending,
holdout protocol). No network, no key, no browser. Response SHAPES mirror the L1a incident without any private content."""
import hashlib
import json
import shutil

import httpx
import pytest

from agent_readiness.agent import ModelConfig
from agent_readiness.compat import recover
from agent_readiness.investigate import flow, zoo
from agent_readiness.investigate import fork as forkmod
from agent_readiness.investigate.export import export_run
from agent_readiness.investigate.inspect.stage import run_inspect
from agent_readiness.investigate.investigator import loop
from agent_readiness.investigate.investigator.loop import Step, investigate, terminal_status
from agent_readiness.investigate.investigator.stage import investigate_stage, manifest, report_stage
from agent_readiness.investigate.investigator.tools import Workspace
from agent_readiness.investigate.llm import LLMResponse, ScriptedClient, complete_structured, LLMRequest
from agent_readiness.investigate.llm.meta import MetaClient, ProviderError
from agent_readiness.investigate.pipeline import Context, Pipeline, Stage
from agent_readiness.investigate.run import InvestigationRun
from agent_readiness.investigate.trials.trace import trace_stage
from agent_readiness.ledger import Halt
from agent_readiness.spend_gate import RequestGate

from .test_investigate_investigator import hyp, scripted_model, step, ws_for

FINISH = step("finish", hyps=[])
PROSE = "Investigating where agents struggle and cataloguing the available evidence"          # one prose line, as the live model wrote
SHAPE = PROSE + json.dumps(FINISH)                                                          # prose line immediately followed by the JSON object (the incident's shape)


# ------------------------------------------------------------------------------------------------------------ 1. the recovery crash
def test_prose_prefixed_single_action_step_is_recovered_not_a_crash():
    r = recover(SHAPE, Step)
    assert r["status"] == "recovered" and r["validated"] is True and r["raw_protocol_compliant"] is False
    assert r["actions"] == [["tool"]]                                                                  # exactly the recovered action's non-null fields (finish carries only its tool name)
    assert r["normalized"] == json.dumps(FINISH) and r["prefix_chars"] == len(PROSE)


def test_recovered_action_fields_are_exact_for_a_step_with_arguments():
    r = recover(PROSE + json.dumps(step("check_claim", claim_kind="info_absent_on_template", label="price")), Step)
    assert r["status"] == "recovered" and r["actions"] == [["claim_kind", "label", "tool"]]


def test_complete_structured_accepts_the_incident_shape_end_to_end():
    parsed, resp, attempts = complete_structured(ScriptedClient([SHAPE]), LLMRequest(messages=[{"role": "user", "content": "x"}], purpose="investigate"), Step, retries=1)
    assert parsed.action.tool == "finish" and attempts == 1


def test_browser_agent_recovery_behaviour_is_unchanged():
    from tests.test_compat_parser import CAPTURED, OBJECT
    from agent_readiness.probe import build_agent_output_schema
    r = recover(CAPTURED, build_agent_output_schema()[1])
    assert r["status"] == "recovered" and r["actions"] == [["click"]] and r["normalized"] == OBJECT


def test_a_list_valued_action_and_a_model_without_action_are_both_still_handled():
    from pydantic import BaseModel
    from typing import Optional

    class Plain(BaseModel):
        a: int
    assert recover("ok then {\"a\": 1}", Plain)["actions"] is None
    assert recover("{\"a\": 1}", Plain)["status"] == "not_needed"


# ------------------------------------------------------------------------------------------------------------ 2. accounting survives failures
def test_a_paid_request_stays_visible_when_parsing_fails_after_it(tmp_path, monkeypatch):
    ws = ws_for(tmp_path)
    seen = []

    def crash_after_paid_request(llm, request, output_model, *, retries=1):
        seen.append(llm.complete(request))                                    # the request is sent and answered ...
        raise AttributeError("'tuple' object has no attribute 'model_dump'")  # ... then recovery crashes (the incident)
    monkeypatch.setattr(loop, "complete_structured", crash_after_paid_request)

    class Paid:
        mode, model = "live", "muse-spark-1.3"

        def complete(self, request):
            return LLMResponse(text="x", mode="live", model="m", usage={"prompt_tokens": 1278, "completion_tokens": 124}, cost_usd=0.002125, finish_reason="stop", reasoning_tokens=7)
    res = investigate(ws, Paid(), max_calls=3)
    assert res["model_requests"] == 1 and res["cost_usd"] == 0.002125 and res["prompt_tokens"] == 1278 and res["completion_tokens"] == 124 and res["reasoning_tokens"] == 7
    assert res["finish_reasons"] == {"stop": 1} and res["tool_calls"] == 0 and res["finished"] is False                      # nothing invented: no tool call, not finished
    assert res["status"] == "incomplete_due_to_infrastructure_error" and res["error"] == "AttributeError" and "aborted after 1 model request" in res["incomplete"]


def test_unusable_output_counts_every_paid_attempt_including_the_retry(tmp_path):
    ws = ws_for(tmp_path)
    res = investigate(ws, ScriptedClient(["not json at all", "still nothing"]), max_calls=3)
    assert res["model_requests"] == 2 and res["status"] == "incomplete_unusable_model_output" and res["finished"] is False


def test_confirmed_responses_uncertain_sends_and_gate_refusals_are_told_apart(tmp_path):
    class Boom:
        mode, model = "live", "m"

        def __init__(self, exc):
            self.exc = exc

        def complete(self, request):
            raise self.exc
    cases = [(ProviderError("http", 429, "rate_limit"), 1, 0, "response_received"), (ProviderError("parse", 200, "shape"), 1, 0, "response_received"),
             (ProviderError("transport", None, "ConnectError"), 0, 1, "uncertain"), (RuntimeError("provider down"), 0, 1, "uncertain")]
    for i, (exc, confirmed, uncertain, send) in enumerate(cases):
        res = investigate(ws_for(tmp_path, name=f"c{i}"), Boom(exc), max_calls=2)
        assert (res["requests_confirmed"], res["requests_uncertain"], res["model_requests"]) == (confirmed, uncertain, 1)       # model_requests = conservative upper bound (confirmed + uncertain)
        assert res["provider_errors"][0]["send_status"] == send and res["status"] == "incomplete_due_to_infrastructure_error"
        assert ("uncertain send status" in res["incomplete"]) == bool(uncertain)                                              # the message never claims an uncertain request was sent
    res2 = investigate(ws_for(tmp_path, name="b"), Boom(Halt("spend gate refused the request")), max_calls=2)
    assert res2["model_requests"] == 0 and res2["requests_confirmed"] == res2["requests_uncertain"] == 0 and res2["refused_before_send"] == 1


def _live_client(run, handler, ceiling=2.05, cap=0.40):
    gate = RequestGate(run.ledger(ceiling), f"{run.state['id']}-investigate", run_cap=cap, per_request_cap=0.05, max_requests=26)
    return MetaClient(ModelConfig(), "sk-test-SECRET", gate, transport=httpx.MockTransport(handler))


def _ok(text, prompt=1278, completion=124):
    return lambda r: httpx.Response(200, json={"choices": [{"message": {"content": text}, "finish_reason": "stop"}], "usage": {"prompt_tokens": prompt, "completion_tokens": completion, "completion_tokens_details": {"reasoning_tokens": 7}}})


def test_the_incident_response_shape_now_completes_and_the_meter_matches_the_ledger(tmp_path):
    run = ws_for(tmp_path).run
    out = investigate_stage(Context(run, options={"investigator_llm": _live_client(run, _ok(SHAPE)), "max_calls": 3}))
    inv = run.artifact("investigation")
    assert out["status"] == "completed" and inv["finished"] and inv["model_requests"] == 1 and inv["accounting"]["reconciled"] is True
    assert inv["accounting"]["ledger_requests_reserved"] == 1 and inv["accounting"]["ledger_settled_usd"] == inv["cost_usd"] > 0


def test_a_failed_parse_after_a_paid_request_is_reconciled_with_the_ledger(tmp_path):
    run = ws_for(tmp_path).run
    investigate_stage(Context(run, options={"investigator_llm": _live_client(run, _ok("garbage, no json")), "max_calls": 3}))
    inv = run.artifact("investigation")
    assert inv["status"] == "incomplete_unusable_model_output" and inv["model_requests"] == 2 and inv["cost_usd"] > 0
    acc = inv["accounting"]
    assert acc["ledger_requests_reserved"] == 2 == acc["metered_requests"] and acc["reconciled"] is True and acc["ledger_settled_usd"] == inv["cost_usd"] and acc["ledger_unsettled_reserved_usd"] == 0


def test_a_mismatch_between_meter_and_ledger_is_flagged(tmp_path):
    run = ws_for(tmp_path).run
    led = run.ledger(2.05)
    led.reserve(f"{run.state['id']}-investigate:req01", 0.02)
    led.reserve(f"{run.state['id']}-investigate:req02", 0.02)                                   # the ledger holds two requests; the scripted investigator metered one
    investigate_stage(Context(run, options={"investigator_llm": ScriptedClient([json.dumps(FINISH)]), "max_calls": 3}))
    acc = run.artifact("investigation")["accounting"]
    assert acc["reconciled"] is False and "NOT reconciled" in acc["note"] and acc["checks"]["request_count_matches"] is False


def test_counts_and_costs_can_match_while_a_reservation_is_unsettled_and_that_is_not_reconciled(tmp_path):
    """Negative case: the meter saw 1 request and US$0, the ledger holds 1 reservation and US$0 settled - but the reservation was never settled (a transport error leaves it counted at its full bound)."""
    run = ws_for(tmp_path).run

    def refuse_connection(request):
        raise httpx.ConnectError("no route")
    investigate_stage(Context(run, options={"investigator_llm": _live_client(run, refuse_connection), "max_calls": 3}))
    inv = run.artifact("investigation")
    acc = inv["accounting"]
    assert acc["ledger_requests_reserved"] == acc["metered_requests"] == 1 and acc["ledger_settled_usd"] == acc["metered_cost_usd"] == 0.0                      # counts and costs match ...
    assert acc["ledger_unsettled_reservations"] == 1 and acc["ledger_unsettled_reserved_usd"] > 0 and acc["checks"]["all_reservations_settled"] is False         # ... but a reservation is outstanding
    assert acc["reconciled"] is False and acc["requests_uncertain"] == 1 and acc["requests_confirmed"] == 0 and "uncertain send status" in acc["note"]
    assert inv["status"] == "incomplete_due_to_infrastructure_error"


def test_an_http_error_is_a_confirmed_response_but_also_leaves_an_unsettled_reservation(tmp_path):
    run = ws_for(tmp_path).run
    investigate_stage(Context(run, options={"investigator_llm": _live_client(run, lambda r: httpx.Response(429, json={"error": {"type": "rate_limit"}})), "max_calls": 3}))
    acc = run.artifact("investigation")["accounting"]
    assert acc["requests_confirmed"] == 1 and acc["requests_uncertain"] == 0 and acc["reconciled"] is False and acc["ledger_unsettled_reservations"] == 1


def test_only_this_stages_exact_request_ids_are_reconciled(tmp_path):
    run = ws_for(tmp_path).run
    led = run.ledger(2.05)
    rid = run.state["id"]
    for other in (f"{rid}-investigate:req99x", f"{rid}-investigate:reqabc", f"{rid}-investigate:req01-copy:req01", f"{rid}-investigate:req"):
        led.reserve(other, 0.03)                                                                                # share the prefix but are not this stage's request ids
    out = investigate_stage(Context(run, options={"investigator_llm": _live_client(run, _ok(SHAPE)), "max_calls": 3}))
    acc = run.artifact("investigation")["accounting"]
    assert acc["ledger_requests_reserved"] == 1 and acc["reconciled"] is True and out["status"] == "completed"       # the four look-alikes are ignored
    from agent_readiness.investigate.taskgen.stage import _reserved_requests
    led.reserve(f"{rid}-taskgen:req01", 0.03)
    led.reserve(f"{rid}-taskgen:req01x", 0.03)
    led.reserve(f"{rid}-taskgen:req", 0.03)
    assert _reserved_requests(run) == 1


# ------------------------------------------------------------------------------------------------------------ 3. terminal status
def _report(run, inv):
    run.write_artifact("investigation", inv)
    return report_stage(Context(run), final=True), run.artifact("report-final")


@pytest.mark.parametrize("inv,status,outcome", [
    ({"skipped": False, "finished": True, "incomplete": None}, "completed", "no_supported_issue"),
    ({"skipped": False, "finished": False, "incomplete": "aborted after 1 model request(s): AttributeError: x", "status": "incomplete_due_to_infrastructure_error"}, "incomplete_due_to_infrastructure_error", "incomplete_due_to_infrastructure_error"),
    ({"skipped": False, "finished": False, "incomplete": "unusable model output: x", "status": "incomplete_unusable_model_output"}, "incomplete_unusable_model_output", "incomplete_unusable_model_output"),
    ({"skipped": False, "finished": False, "incomplete": "tool budget exhausted without a finish action", "status": "incomplete_no_finish"}, "incomplete_no_finish", "incomplete_no_finish"),
    ({"skipped": True, "reason": "no investigator model configured for this run"}, "not_run", "not_investigated")])
def test_terminal_status_separates_a_valid_negative_from_an_incomplete_investigation(tmp_path, inv, status, outcome):
    run = ws_for(tmp_path).run
    out, rep = _report(run, inv)
    assert rep["investigation_status"] == status and rep["outcome"] == outcome == out["outcome"]
    assert ("outcome_note" in rep) == (status != "completed")
    if status != "completed":
        assert "false negative" in rep["outcome_note"]


def test_partial_findings_are_kept_even_when_the_investigation_did_not_complete(tmp_path):
    ws = ws_for(tmp_path)
    from agent_readiness.investigate.models import Hypothesis, Provenance
    obs = next(iter(ws.run.evidence.observations))
    h = ws.run.evidence.add_hypothesis(Hypothesis(tier="novel", statement="s", prediction="p", citations=[obs], provenance=Provenance(mode="scripted", source="t")))
    from agent_readiness.investigate.models import Proposal
    ws.run.evidence.add_proposal(Proposal(basis="unverified_hypothesis", source_id=h.id, change={"manual": "x"}, expected_effect="e", provenance=Provenance(mode="scripted", source="t")))
    out, rep = _report(ws.run, {"skipped": False, "finished": False, "incomplete": "aborted after 2 model request(s): X: y", "status": "incomplete_due_to_infrastructure_error"})
    assert rep["outcome"] == "experimental_only" and rep["investigation_status"] == "incomplete_due_to_infrastructure_error"             # a real (if partial) result is not overwritten


def test_terminal_status_function_and_export(tmp_path):
    assert terminal_status({"finished": True}) == "completed" and terminal_status({"incomplete": "aborted after 0 model request(s): E"}) == "incomplete_due_to_infrastructure_error"
    assert terminal_status({"incomplete": "unusable model output: bad"}) == "incomplete_unusable_model_output" and terminal_status({"incomplete": "no finish action"}) == "incomplete_no_finish"
    run = ws_for(tmp_path).run
    _report(run, {"skipped": False, "finished": False, "incomplete": "aborted after 1 model request(s): E", "status": "incomplete_due_to_infrastructure_error"})
    d = export_run(run.dir)
    assert d["run"]["outcome"] == "incomplete_due_to_infrastructure_error" and d["run"]["investigation_status"] == "incomplete_due_to_infrastructure_error"


# ------------------------------------------------------------------------------------------------------------ 4-6. recovery fork
def _tree(root):
    return hashlib.sha256(b"".join(p.relative_to(root).as_posix().encode() + p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file())).hexdigest()


@pytest.fixture
def source(tmp_path):
    """A 'live' run with frozen tasks, baseline trials, a spending history, approvals and a FAILED investigation, as after the L1a incident."""
    src = ws_for(tmp_path, name="seed").run
    live = InvestigationRun.create(tmp_path, "src-live", target="site-1", mode="live", stages=flow.STAGES)
    for d in ("artifacts", "private", "snapshot", "trial-data"):
        shutil.copytree(src.dir / d, live.dir / d, dirs_exist_ok=True)
    shutil.copy2(src.dir / "evidence.jsonl", live.dir / "evidence.jsonl")
    for stage in ("inspect", "taskgen", "freeze", "baseline_trials", "trace"):
        live.set_status(stage, "done")
    led = live.ledger(2.05)
    led.reserve("src-live-taskgen:req01", 0.03); led.settle("src-live-taskgen:req01", 0.012)
    led.reserve("baseline-gen-aaaa-r1:req01", 0.04); led.settle("baseline-gen-aaaa-r1:req01", 0.02)
    led.reserve("src-live-investigate:req01", 0.019); led.settle("src-live-investigate:req01", 0.002125)
    live.approve("taskgen", "a" * 64, "approved")
    live.approve("investigate", "c" * 64, "approved the original investigate manifest")
    live.write_artifact("investigation", {"skipped": False, "finished": False, "incomplete": "aborted after 0 model request(s): AttributeError", "status": "incomplete_due_to_infrastructure_error", "model_requests": 1, "cost_usd": 0.002125})
    live.write_private("investigator-transcript", [{"role": "user", "content": "PRIVATE-INVESTIGATOR-PROMPT"}])
    return live


def test_fork_imports_only_paid_evidence_and_history_and_leaves_the_source_untouched(tmp_path, source):
    before = _tree(source.dir)
    new = InvestigationRun(forkmod.fork(source.dir, tmp_path, "fork-1"))
    assert _tree(source.dir) == before                                                                        # the original run (and its failed history) is only read
    prov = forkmod.load_fork(new)
    assert prov["source_run"] == "src-live" and prov["paid_stages_rerun" if False else "source_run"]
    assert new.mode == "live" and [new.status(s) for s in ("inspect", "taskgen", "freeze", "baseline_trials", "trace", "investigate")] == ["pending", "done", "done", "done", "pending", "pending"]
    assert not (new.dir / "approvals.jsonl").exists() and new.approvals() == []                                # approvals are NOT inherited
    for absent in ("evidence.jsonl", "artifacts/investigation.json", "private/investigator-transcript.json", "artifacts/report.json"):
        assert not (new.dir / absent).exists(), absent
    assert (new.dir / "artifacts" / "tasks-manifest.json").read_bytes() == (source.dir / "artifacts" / "tasks-manifest.json").read_bytes()
    assert (new.dir / "spend" / "ledger.jsonl").read_bytes() == (source.dir / "spend" / "ledger.jsonl").read_bytes()
    assert prov["source_ledger"]["settled_usd"] == round(0.012 + 0.02 + 0.002125, 6) and prov["source_ledger"]["outstanding_reserved_usd"] == 0
    assert prov["source_approvals_not_inherited"] == [{"stage": "taskgen", "manifest_sha256": "a" * 64}, {"stage": "investigate", "manifest_sha256": "c" * 64}]
    assert prov["source_investigation"]["status"] == "incomplete_due_to_infrastructure_error" and "PRIVATE" not in json.dumps(prov)


def test_fork_refuses_an_incomplete_source_an_existing_target_and_a_bad_id(tmp_path, source):
    bare = InvestigationRun.create(tmp_path, "bare", target="site-1", mode="live", stages=flow.STAGES)
    with pytest.raises(ValueError, match="paid prerequisites"):
        forkmod.fork(bare.dir, tmp_path, "x1")
    forkmod.fork(source.dir, tmp_path, "dup")
    with pytest.raises(FileExistsError):
        forkmod.fork(source.dir, tmp_path, "dup")
    with pytest.raises(ValueError, match="run id"):
        forkmod.fork(source.dir, tmp_path, "../escape")


def test_the_forks_investigate_manifest_shows_provenance_and_needs_a_fresh_exact_approval(tmp_path, source):
    new = InvestigationRun(forkmod.fork(source.dir, tmp_path, "fork-2"))
    for stage, fn in (("inspect", lambda c: run_inspect(c, zoo.snapshot("site-1"))), ("trace", trace_stage)):
        Pipeline([Stage(stage, fn)]).run(Context(new))                                                       # the free stages re-derive their output from the imported evidence
    src_obs, new_obs = set(InvestigationRun(source.dir).evidence.observations), set(InvestigationRun(new.dir).evidence.observations)
    assert src_obs == new_obs and new_obs                                                                      # the same observations, re-derived deterministically
    m = manifest(Context(new, options={"max_calls": 3, "total_cap_usd": 2.05}))
    assert m["forked_from"]["source_run"] == "src-live" and m["forked_from"]["paid_stages_rerun"] is False and m["forked_from"]["imported_spend_committed_usd"] == round(0.012 + 0.02 + 0.002125, 6)
    assert m["forked_from"]["tasks_manifest_sha256"] == forkmod.load_fork(new)["tasks_manifest_sha256"]
    h = new.manifest_sha256(m)
    assert not new.is_approved("investigate", h) and not new.is_approved("investigate", "c" * 64)             # neither the source's approval nor any other hash applies
    client = ScriptedClient([json.dumps(FINISH)])
    stage_ = Stage("investigate", investigate_stage, spends=True, manifest=manifest)
    ctx = Context(new, options={"investigator_llm": client, "max_calls": 3, "total_cap_usd": 2.05})
    r = Pipeline([stage_]).run(ctx)
    assert r.status == "awaiting_approval" and r.manifest_sha256 == h and client.calls == []                    # nothing is sent before an exact approval
    new.approve("investigate", "d" * 64, "approving a different hash")
    assert Pipeline([stage_]).run(ctx).status == "awaiting_approval" and client.calls == []                     # a different hash does not unlock it
    new.approve("investigate", h, "owner approved this exact fork manifest")
    assert Pipeline([stage_]).run(ctx).status == "done" and len(client.calls) == 1


def test_a_tampered_import_or_rewritten_history_halts_before_any_request(tmp_path, source):
    new = InvestigationRun(forkmod.fork(source.dir, tmp_path, "fork-3"))
    forkmod.verify_fork(new)
    for stage, fn in (("inspect", lambda c: run_inspect(c, zoo.snapshot("site-1"))), ("trace", trace_stage)):
        Pipeline([Stage(stage, fn)]).run(Context(new))
    trial = next((new.dir / "artifacts" / "trials").glob("*.json"))
    original = trial.read_text()
    trial.write_text(original.replace('"passed"', '"passed" ', 1))
    with pytest.raises(Halt, match="imported evidence changed"):
        manifest(Context(new, options={}))
    client = ScriptedClient([json.dumps(FINISH)])
    with pytest.raises(Halt):
        investigate_stage(Context(new, options={"investigator_llm": client}))
    assert client.calls == []
    trial.write_text(original)
    forkmod.verify_fork(new)                                                                                   # restored: fine again
    ledger = new.dir / "spend" / "ledger.jsonl"
    lines = ledger.read_text().splitlines()
    ledger.write_text("\n".join(lines[1:]) + "\n")                                                              # history rewritten
    with pytest.raises(Halt, match="spending history"):
        forkmod.verify_fork(new)


def test_the_forks_spending_history_counts_against_the_ceiling_and_new_spend_gets_a_new_gate_id(tmp_path, source):
    new = InvestigationRun(forkmod.fork(source.dir, tmp_path, "fork-4"))
    led = new.ledger(2.05)
    assert led.committed() == round(0.012 + 0.02 + 0.002125, 6) and len(led.entries()) == 6                    # paid history carried over, nothing re-spent by forking
    tight = new.ledger(0.05)
    with pytest.raises(Halt, match="budget ceiling"):
        tight.reserve("fork-4-investigate:req01", 0.019)                                                       # 0.034 already committed: the imported history is not free
    ok = RequestGate(new.ledger(2.05), "fork-4-investigate", run_cap=0.40, per_request_cap=0.05, max_requests=26)
    body = {"model": "m", "max_completion_tokens": 100, "messages": [{"role": "user", "content": "x"}]}
    ok.reserve(1, body)
    assert any(e["id"] == "fork-4-investigate:req01" for e in new.ledger(2.05).entries()) and not any(e["id"] == "fork-4-investigate:req01" for e in source.ledger(2.05).entries())
    assert RequestGate(new.ledger(2.05), "src-live-investigate", run_cap=0.40, per_request_cap=0.05, max_requests=26).request_count() == 1       # the original attempt remains visible, separately


def test_the_fork_keeps_the_holdout_protocol(tmp_path, source):
    new = InvestigationRun(forkmod.fork(source.dir, tmp_path, "fork-5"))
    for stage, fn in (("inspect", lambda c: run_inspect(c, zoo.snapshot("site-1"))), ("trace", trace_stage)):
        Pipeline([Stage(stage, fn)]).run(Context(new))
    ws = Workspace(InvestigationRun(new.dir))
    manifest_ = new.artifact("tasks-manifest")
    hold = [t for t in manifest_["tasks"] if t["partition"] == "holdout"]
    assert hold and set(ws.inv_tasks) == {t["task_id"] for t in manifest_["tasks"] if t["partition"] == "investigation"}
    assert all(a["partition"] == "investigation" for a in ws.att.values()) and not any(t["task_id"] in ws.inv_tasks for t in hold)
    first = loop.first_user_message(ws, None)
    assert not any(t["task_id"] in first or t["question"] in first for t in hold)                                # the investigator's first prompt never names a holdout task
    listed = json.dumps(ws.t_list_trials(loop.ToolCall(tool="list_trials", **{k: None for k in ("evidence_id", "trial_id", "task_id", "step", "path", "css", "text", "claim_kind", "label", "scope", "k")}))) if hasattr(ws, "t_list_trials") else ""
    assert not any(t["question"] in listed for t in hold)                                                          # the investigator's trial list never contains a holdout task


def test_fork_cli_is_offline_and_reports_what_it_did_not_import(tmp_path, source, monkeypatch, capsys):
    from agent_readiness.cli import main as cli_main
    monkeypatch.setattr("sys.argv", ["readiness", "investigate", "fork", str(source.dir), "--id", "fork-cli", "--root", str(tmp_path)])
    cli_main()
    out = capsys.readouterr().out
    assert "NOT imported: approvals" in out and (tmp_path / "fork-cli" / "fork.json").exists()
    monkeypatch.setattr("sys.argv", ["readiness", "investigate", "fork", str(source.dir), "--id", "fork-cli", "--root", str(tmp_path)])
    with pytest.raises(SystemExit, match="fork refused"):
        cli_main()
