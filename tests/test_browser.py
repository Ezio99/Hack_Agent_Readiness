"""Requires local sockets + installed Chromium. CI runs these without credentials."""
import json
import pytest
from agent_readiness.runner import run
from .test_benchmark import assert_no_leaks

pytestmark = pytest.mark.browser


@pytest.mark.parametrize("kind,available", [("discovery", None), ("availability", True), ("availability", False)])
async def test_real_browser_smoke_and_information_boundary(tmp_path, kind, available):
    path, record = await run(output=tmp_path, kind=kind, available=available)
    assert record["status"] == "completed", record.get("errors")
    assert record["evaluation"]["passed"]
    for name in ["initial-listing", "filtered-listing"]:
        observation = json.loads((path / f"{name}.json").read_text())
        assert_no_leaks(json.dumps(observation))
        assert observation["agent_dom"]
        assert observation["agent_screenshot"]
        assert observation["accessibility"]["nodes"]
        assert observation["dom_snapshot"]["documents"]
        for image in [observation["screenshot"], observation["agent_screenshot"]]:
            assert (path / image).read_bytes().startswith(b"\x89PNG")
    detail = json.loads((path / "detail.json").read_text())
    assert "/products/" in detail["url"]
    assert record["answer"]["product_id"] in detail["html"]
    assert record["answer"]["product_id"] in detail["agent_dom"]
    trace = [json.loads(line) for line in (path / "trace.jsonl").read_text().splitlines()]
    assert len([e for e in trace if e["kind"] == "observation"]) == 3
    assert record["action_count"] >= 4 and record["usage"] is None


async def test_smoke_applies_viewport_and_stops_at_overridden_step_limit(tmp_path):
    from PIL import Image
    viewport = {"width": 960, "height": 720}
    path, record = await run(output=tmp_path, max_steps=1, profile_overrides={"viewport": viewport})
    assert record["status"] == "step_limit" and record["steps"] == 1
    assert record["profile"]["viewport"] == viewport and record["limits"]["max_steps"] == 1
    assert record["model_request_count"] == 0
    observation = json.loads((path / "initial-listing.json").read_text())
    assert_no_leaks(json.dumps(observation))
    with Image.open(path / observation["agent_screenshot"]) as screenshot:
        assert screenshot.size == (960, 720)
    assert not (path / "filtered-listing.json").exists() and not (path / "detail.json").exists()
