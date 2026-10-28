"""Task 011 end-to-end MOCK execution (credential-free, no network beyond loopback): real Chromium + real Browser Use agent + real fidelity guard +
real environment + independent evaluator, with only the model's decisions scripted. Results are pipeline checks, not model evidence."""
import asyncio
import tempfile

import pytest

from agent_readiness.environments.electronics.variants import all_variants, make_variant
from agent_readiness.scanner.execute import execute_scan
from agent_readiness.suite import registry

pytestmark = pytest.mark.browser
registry.load_all()
TEMPLATE_TASKS = ["t1-anc-headphones-under-250-all", "t2-compare-air14-vs-probook15", "t3-cheapest-monitor-27in-usbc-120hz", "t4-policy-delivery-tessera-whisper"]
V = make_variant("detail", "fragmented")


def scan(task, behavior, variant=V):
    return asyncio.run(execute_scan(task, variant, provider="mock", mock_behavior=behavior, output=tempfile.mkdtemp()))


@pytest.mark.parametrize("task", TEMPLATE_TASKS)
def test_correct_mock_passes_every_template_with_evidence(task):
    r = scan(task, "correct")
    assert r["scan"]["mode"] == "mock" and r["outcome"]["run_status"] == "completed"
    assert r["evaluation"]["passed"] and r["evaluation"]["evidence_backed"], r["evaluation"]
    assert r["metrics"]["model_requests"] >= 2 and r["metrics"]["page_views"] >= 2
    assert "MOCK" in r["metrics"]["cost_basis"] and r["protocol"]["raw_protocol_noncompliant"] == 0
    assert r["diagnostics"]["findings"][0]["category"] == "task_outcome"


@pytest.mark.parametrize("variant", all_variants(), ids=lambda v: v.variant_id.split("/")[1])
def test_correct_mock_passes_in_every_variant(variant):
    r = scan("t3-cheapest-monitor-27in-usbc-120hz", "correct", variant)
    assert r["evaluation"]["passed"] and r["evaluation"]["evidence_backed"]


def test_lazy_answer_is_correct_but_not_evidence_backed():
    r = scan("t2-compare-air14-vs-probook15", "lazy")
    assert r["evaluation"]["passed"] and not r["evaluation"]["evidence_backed"]
    assert r["diagnostics"]["findings"][0]["title"].startswith("Correct answer, but required information was not shown")


def test_wrong_answer_fails_and_is_attributed_to_reasoning_not_missing_information():
    r = scan("t4-policy-delivery-tessera-whisper", "wrong")
    assert not r["evaluation"]["passed"]
    cats = {f["category"]: f for f in r["diagnostics"]["findings"]}
    assert "agent_reasoning" in cats and cats["agent_reasoning"]["confidence"] == "inferred"


def test_loop_persona_is_diagnosed_as_agent_tool_interface_not_website():
    r = scan("t1-anc-headphones-under-250-all", "loop")
    f = [x for x in r["diagnostics"]["findings"] if x["category"] == "agent_tool_interface"]
    assert f and f[0]["confidence"] == "observed" and "not evidence about the website" in f[0]["summary"]
    assert not any(x["category"] == "website" and x["confidence"] == "observed" and "visib" in x["title"].lower() for x in r["diagnostics"]["findings"])


def test_stuck_hits_the_request_limit_and_is_infrastructure_not_website():
    r = scan("t2-compare-air14-vs-probook15", "stuck")
    assert r["metrics"]["model_requests"] <= r["metrics"]["limits"]["max_model_requests"] <= 12
    assert not r["evaluation"]["passed"]


def test_origin_escape_is_blocked_by_the_browser_allowlist_and_reported():
    r = scan("t2-compare-air14-vs-probook15", "escape")
    assert any(f["category"] == "security" for f in r["diagnostics"]["findings"])
    assert not r["evaluation"]["passed"]
    assert all("example.com" not in a["params"].get("url", "") or a["params"]["url"].startswith("[external]") for j in r["journey"] for a in j["actions"])


def test_provider_failure_is_infrastructure_and_costs_nothing():
    r = scan("t3-cheapest-monitor-27in-usbc-120hz", "provider_error")
    assert r["outcome"]["run_status"] == "infrastructure_error"
    assert r["metrics"]["calculated_cost_usd"] == 0
    assert [f["category"] for f in r["diagnostics"]["findings"]][:2] == ["task_outcome", "infrastructure"]


def test_live_mode_without_key_is_refused_before_anything_runs():
    with pytest.raises(ValueError):
        asyncio.run(execute_scan("t3-cheapest-monitor-27in-usbc-120hz", V, provider="live", output=tempfile.mkdtemp()))


def test_result_contains_no_truth_or_secret_fields():
    r = scan("t3-cheapest-monitor-27in-usbc-120hz", "correct")
    blob = str(r).lower()
    assert "oracle" not in str(r["task"]).lower() and "expected" not in str(r["task"]).lower()
    assert "api_key" not in blob and "bearer" not in blob
