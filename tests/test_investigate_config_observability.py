"""L1a preparation (offline): sanitized call logs for successful requests as well as failures, explicit reasoning effort / completion caps / reservation bounds in the L1a stage manifests, and the
investigator cap. Nothing here makes a network call; the values mirror the L0 attempt-3 measurements (see collaboration/reports/016j-l1a-config-proposal.md)."""
import json

import httpx
import pytest

from agent_readiness.agent import ModelConfig
from agent_readiness.investigate import flow, l0
from agent_readiness.investigate.investigator.loop import STEP_MAX_TOKENS, SYSTEM, Step, investigate
from agent_readiness.investigate.investigator.stage import manifest as investigate_manifest
from agent_readiness.investigate.llm import LLMRequest, LLMResponse, RecordedClient, RecordingClient, ScriptedClient
from agent_readiness.investigate.llm.meta import DEFAULT_REASONING_EFFORT, INPUT_OVERHEAD_TOKENS, MetaClient
from agent_readiness.investigate.pipeline import Context
from agent_readiness.investigate.taskgen import propose
from agent_readiness.ledger import Ledger
from agent_readiness.spend_gate import RequestGate

from .test_investigate_investigator import hyp, scripted_model, step, ws_for
from .test_investigate_l0 import GOOD
from .test_investigate_taskgen import make_run

REQ = LLMRequest(messages=[{"role": "user", "content": "PRIVATE-PROMPT"}], purpose="investigate", max_tokens=4096)


class Fake:
    mode, model = "live", "muse-spark-1.3"

    def __init__(self, resp):
        self.resp = resp

    def complete(self, request):
        return self.resp


def test_call_log_records_sanitized_facts_for_successes_without_text_or_prompts(tmp_path):
    resp = LLMResponse(text='{"a": "PRIVATE-MODEL-TEXT"}', mode="live", model="muse-spark-1.3", usage={"prompt_tokens": 441, "completion_tokens": 1434}, cost_usd=0.006646, finish_reason="stop", reasoning_tokens=1031)
    rc = RecordingClient(Fake(resp), tmp_path / "private" / "t.jsonl", calls_path=tmp_path / "calls" / "x.jsonl")
    rc.complete(REQ)
    raw = (tmp_path / "calls" / "x.jsonl").read_text()
    (row,) = [json.loads(l) for l in raw.splitlines()]
    assert row["outcome"] == "response" and row["finish_reason"] == "stop" and row["reasoning_tokens"] == 1031 and row["completion_tokens"] == 1434 and row["prompt_tokens"] == 441
    assert row["max_completion_tokens"] == 4096 and row["cap_used_pct"] == 35.0 and row["content_chars"] == len(resp.text) and row["cost_usd"] == 0.006646
    assert "PRIVATE" not in raw and "text" not in row and "messages" not in row                      # the sanitized log never holds prompts or model text
    private = json.loads((tmp_path / "private" / "t.jsonl").read_text())
    assert private["finish_reason"] == "stop" and private["reasoning_tokens"] == 1031 and "PRIVATE-MODEL-TEXT" in private["text"]       # the PRIVATE transcript keeps the full record


def test_call_log_records_a_length_stop_and_a_classified_provider_error(tmp_path):
    cut = LLMResponse(text="", mode="live", model="m", usage={"prompt_tokens": 105, "completion_tokens": 200}, cost_usd=0.000981, finish_reason="length", reasoning_tokens=200)
    small = LLMRequest(messages=[{"role": "user", "content": "x"}], purpose="probe", max_tokens=200)
    RecordingClient(Fake(cut), tmp_path / "p.jsonl", calls_path=tmp_path / "c.jsonl").complete(small)
    row = json.loads((tmp_path / "c.jsonl").read_text())
    assert row["finish_reason"] == "length" and row["cap_used_pct"] == 100.0 and row["content_chars"] == 0                  # the exhausted-by-reasoning signature is visible in the log
    led = Ledger(tmp_path / "spend", ceiling=1.0)
    client = MetaClient(ModelConfig(), "sk-test-SECRET", RequestGate(led, "r"), transport=httpx.MockTransport(lambda r: httpx.Response(429, json={"error": {"type": "rate_limit", "message": "slow down"}})))
    rc = RecordingClient(client, tmp_path / "p2.jsonl", calls_path=tmp_path / "c2.jsonl")
    with pytest.raises(RuntimeError):
        rc.complete(small)
    err = json.loads((tmp_path / "c2.jsonl").read_text())
    assert err["outcome"] == "provider_error" and err["error_category"] == "http" and err["http_status"] == 429 and "rate_limit" in err["error_summary"] and "SECRET" not in json.dumps(err)
    assert not (tmp_path / "p2.jsonl").exists()                                                                         # no response, no transcript entry


def test_replay_restores_finish_reason_and_reasoning_tokens(tmp_path):
    resp = LLMResponse(text="{}", mode="live", model="m", usage={"prompt_tokens": 1, "completion_tokens": 2}, finish_reason="stop", reasoning_tokens=1)
    RecordingClient(Fake(resp), tmp_path / "t.jsonl").complete(REQ)
    back = RecordedClient(tmp_path / "t.jsonl").complete(REQ)
    assert back.finish_reason == "stop" and back.reasoning_tokens == 1 and back.mode == "recorded"


def test_l0_rows_for_successful_requests_carry_sanitized_finish_and_reasoning_fields(tmp_path):
    class Live(ScriptedClient):
        def complete(self, request):
            r = super().complete(request)
            r.finish_reason, r.reasoning_tokens, r.usage = "stop", 640, {"prompt_tokens": 100, "completion_tokens": 700}
            return r
    rep = l0.run(tmp_path, approved_sha256=l0.manifest_sha256(), allow_model_calls=False, client=Live(GOOD))
    assert rep["evaluation"]["verdict"] == "PASS"
    for row in rep["results"]:
        assert row["finish_reason"] == "stop" and row["reasoning_tokens"] == 640 and row["content_chars"] > 0 and row["max_completion_tokens"] == (1024 if row["id"] in ("P1-strict-echo", "P2-prompt-only-echo") else 4096)
        assert row["cap_used_pct"] == round(100 * 700 / row["max_completion_tokens"], 1)
    assert "Return a=3" not in json.dumps(rep) and l0.manifest_sha256() == "0ce19b499a243252ffbf4f0172f8e084cbd0119f3d7fad2ae3b90ca5b0490b86"      # observability does not change the approved L0 manifest


def test_taskgen_manifest_lists_effort_cap_and_the_enforced_reservations(tmp_path):
    run = make_run(tmp_path, "site-5", "tg")
    m = flow.taskgen_manifest(Context(run, options={"n_tasks": 8, "total_cap_usd": 2.05}))
    assert m["reasoning_effort"] == DEFAULT_REASONING_EFFORT and m["max_completion_tokens"] == propose.MAX_TOKENS == 6144 and m["input_overhead_tokens_reserved"] == INPUT_OVERHEAD_TOKENS
    assert len(m["per_request_reservation_usd"]) == m["batches"] == 3 and all(0 < b <= m["per_request_cap_usd"] for b in m["per_request_reservation_usd"])
    assert m["worst_case_stage_usd"] == round(sum(m["per_request_reservation_usd"]), 6) <= m["run_cap_usd"] == 0.15


def test_investigate_manifest_lists_effort_cap_and_reservation(tmp_path):
    ws = ws_for(tmp_path)
    m = investigate_manifest(Context(ws.run))
    assert m["reasoning_effort"] == "low" and m["max_completion_tokens"] == STEP_MAX_TOKENS == 4096 and m["input_overhead_tokens_reserved"] == INPUT_OVERHEAD_TOKENS
    assert 0 < m["first_request_reservation_usd"] <= m["per_request_cap_usd"]


def test_investigator_requests_use_the_listed_cap(tmp_path):
    ws = ws_for(tmp_path)
    seen = []
    base = ScriptedClient(scripted_model([step("finish", hyps=[])]))

    class Spy:
        mode, model = base.mode, base.model

        def complete(self, request):
            seen.append((request.max_tokens, request.purpose, request.response_schema == Step.model_json_schema()))
            return base.complete(request)
    out = investigate(ws, Spy(), max_calls=2)
    assert out["finished"] and seen and all(c == STEP_MAX_TOKENS and p == "investigate" and ok for c, p, ok in seen)
