"""Task 013: root cause and fix for the `find_elements` visibility gap (Browser Use 0.11.13), checked offline with real Chromium + the real Browser Use agent and a scripted model.
Scripted success is a mechanism check only; it says nothing about live model reliability."""
import asyncio
import json
import tempfile

import pytest

from agent_readiness.agent import VISIBILITY_FIX_ACTIONS, apply_tool_result_visibility, profile
from agent_readiness.environments.electronics.variants import make_variant
from agent_readiness.scanner.execute import execute_scan
from agent_readiness.suite import registry

registry.load_all()
T1 = "t1-anc-headphones-under-250-all"
V0 = make_variant("listing", "structured")


def test_profiles_v1_unchanged_and_v2_is_a_new_versioned_configuration():
    v1, v2 = profile("suite-v1-compat1"), profile("suite-v2-compat1")
    assert "tool_result_visibility" not in v1 and v2["tool_result_visibility"] == "read-state-v1"
    assert {k: v for k, v in v2.items() if k not in ("id", "tool_result_visibility")} == {k: v for k, v in v1.items() if k != "id"}      # only the tool-visibility switch differs
    assert v2["output_parser"] == v1["output_parser"] == "muse-prose-prefix-json-v1"


def test_library_root_cause_is_present_in_the_pinned_browser_use():
    """Documents the defect so a library upgrade that fixes it (or changes it) is noticed: results carry a count line as long_term_memory and no one-time flag."""
    import inspect
    from browser_use.tools import service
    src = inspect.getsource(service)
    for name in ("search_page", "find_elements"):
        body = src.split(f"async def {name}(", 1)[1].split("@self.registry.action", 1)[0]
        assert "long_term_memory=memory" in body and "include_extracted_content_only_once" not in body
    from browser_use.agent.message_manager import service as mm
    mm_src = inspect.getsource(mm)
    assert "if action_result.long_term_memory:" in mm_src and "elif action_result.extracted_content and not action_result.include_extracted_content_only_once" in mm_src


def test_patch_sets_the_one_time_flag_only_on_the_two_affected_tools():
    from browser_use import Tools
    from browser_use.agent.views import ActionResult
    tools = Tools()
    originals = {n: tools.registry.registry.actions[n].function for n in tools.registry.registry.actions}
    assert apply_tool_result_visibility(tools) == list(VISIBILITY_FIX_ACTIONS)
    for n, f in tools.registry.registry.actions.items():
        assert (f.function is not originals[n]) == (n in VISIBILITY_FIX_ACTIONS)

    async def fake(**kw):
        return ActionResult(extracted_content="Found 2 elements: href=/p/x", long_term_memory="Found 2 elements.")
    tools.registry.registry.actions["find_elements"].function = fake
    apply_tool_result_visibility(tools)
    r = asyncio.run(tools.registry.registry.actions["find_elements"].function())
    assert r.include_extracted_content_only_once is True and r.long_term_memory == "Found 2 elements." and "href" in r.extracted_content


@pytest.mark.browser
def test_reference_agent_v1_reproduces_the_live_failure_and_v2_fixes_it():
    def run(profile_id):
        return asyncio.run(execute_scan(T1, V0, provider="mock", mock_behavior="element_reader", output=tempfile.mkdtemp(), profile_id=profile_id))
    v1, v2 = run("suite-v1-compat1"), run("suite-v2-compat1")
    # v1: tool output never reaches the model -> repeated find_elements, wrong (SKU-blind) answer, tool-interface finding, SKU evidence missing
    cats1 = [f["category"] for f in v1["diagnostics"]["findings"]]
    assert not v1["evaluation"]["passed"] and "agent_tool_interface" in cats1 and v1["metrics"]["model_requests"] >= 8
    assert any(m.startswith("observed_text:HP-") for m in v1["evaluation"]["missing_evidence"])
    assert any(f["title"] == "Required information was not among the agent's observations" for f in v1["diagnostics"]["findings"])
    # v2: the elements are shown once in <read_state>, the scripted agent uses them, correct and evidence-backed, no tool gap
    cats2 = [f["category"] for f in v2["diagnostics"]["findings"]]
    assert v2["evaluation"]["passed"] and v2["evaluation"]["evidence_backed"] and "agent_tool_interface" not in cats2
    assert v2["metrics"]["model_requests"] < v1["metrics"]["model_requests"] and v2["scan"]["profile"] == "suite-v2-compat1"
    assert v2["scan"]["profile_hash"] != v1["scan"]["profile_hash"]
    # trace evidence: the request after find_elements contains the full output in a read_state block only for v2
    def next_request_text(rec):
        import pathlib
        ev = [json.loads(l) for l in (pathlib.Path(rec["artifact_path"]) / "trace.jsonl").read_text().splitlines()]
        reqs = [e for e in ev if e["kind"] == "model_request"]
        return json.dumps(reqs[2]["messages"])           # request 3 follows the first find_elements
    assert "<read_state_0>" in next_request_text(v2) and 'href=' in next_request_text(v2)
    assert "<read_state_0>" not in next_request_text(v1)
