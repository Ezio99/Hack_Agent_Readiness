"""Unit tests for the replay exporter's sanitizers (synthetic inputs only; no run artifacts needed).
Run from the repository root:  .venv/bin/python -m pytest dashboard/scripts -q"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import export_replay as x  # noqa: E402


def test_scrub_removes_localhost_ports():
    assert x.scrub("Navigated to http://127.0.0.1:36285/?q=") == "Navigated to http://localhost/?q="
    assert x.scrub("title 127.0.0.1:41999/x") == "title localhost/x"
    assert x.scrub(None) is None


def test_actions_are_allow_listed_and_free_text_is_dropped():
    a = x.sanitize_action({"go_back": {"description": "Back to product list to verify all Bags"}})
    assert a == {"name": "go_back", "params": {}}
    c = x.sanitize_action({"click": {"index": 5, "description": "free text", "note": "x"}})
    assert c == {"name": "click", "params": {"index": 5}}
    n = x.sanitize_action({"navigate": {"url": "http://127.0.0.1:1234/products/abc?x=1", "new_tab": False}})
    assert n["params"] == {"url": "/products/abc?x=1", "new_tab": False}
    d = x.sanitize_action({"done": {"success": True, "data": {"product_id": "AR-1", "price_cents": 1, "available": True, "text": "free"}, "files_to_display": []}})
    assert d["params"] == {"data": {"product_id": "AR-1", "price_cents": 1, "available": True}, "success": True}
    u = x.sanitize_action({"weird_tool": {"thinking": "secret"}})
    assert u == {"name": "weird_tool", "params": {}, "params_omitted": True}


def test_history_last_result_excludes_model_written_lines_and_the_system_prompt_example():
    history = ("<agent_history>\nAgent initialized\n<step>\nMODEL GOAL TEXT\nMODEL MEMORY TEXT\nMODEL NEXT GOAL\nResult\nNavigated to http://127.0.0.1:99/\n"
               "<step>\nSECOND GOAL\nSECOND MEMORY\nSECOND NEXT\nResult\nFound 11 elements matching \"a\".\n</agent_history>")
    event = {"messages": [{"role": "system", "content": "docs <agent_history>\n<step>\nexample\nResult\nSYSTEM EXAMPLE\n</agent_history>"},
                          {"role": "user", "content": [{"type": "text", "text": history}]}]}
    assert x.history_last_result(event) == 'Found 11 elements matching "a".'
    assert "GOAL" not in x.history_last_result(event)


def test_excerpt_truncates_and_flags():
    text, cut = x.excerpt("a" * 700)
    assert cut and len(text) == x.EXCERPT_CHARS + 1 and text.endswith("…")
    assert x.excerpt("short") == ("short", False)


def test_page_kind_and_path():
    assert x.page_kind("http://h:1/") == "listing"
    assert x.page_kind("http://h:1/?brand=Fern") == "filtered listing"
    assert x.page_kind("http://h:1/products/abc") == "product detail"
    assert x.path_of("http://h:1/?brand=Fern") == "/?brand=Fern"


def test_audit_flags_forbidden_keys_ports_and_paths():
    files = {"a.json": '{"run": {"thinking": "x"}, "steps": [], "p": "http://127.0.0.1:123/ /home/u"}'}
    findings, _ = x.audit(files)
    assert any("forbidden keys" in f for f in findings) and any("localhost port" in f for f in findings) and any("local path" in f for f in findings)


# ---- audit-before-write safety and run-27 attribution --------------------------------------------------------------------------
import hashlib  # noqa: E402
import json  # noqa: E402
import pytest  # noqa: E402


def good_files():
    step = {"step": 1, "usage": {"prompt_tokens": 100, "completion_tokens": 10}, "estimated_cost_usd": 0.0001}
    run = {"id": "r", "evaluator": {"passed": True}, "verification_shortfall": None,
           "totals": {"requests": 1, "prompt_tokens": 100, "completion_tokens": 10, "estimated_cost_usd": 0.0001},
           "attribution": {"required_path_requests": 2, "tool_loop_requests": 0, "total_requests": 1, "required_path_completed": True, "residual_requests": -1}}
    run["attribution"]["residual_requests"] = 1 - 2 - 0   # consistent with total - required - tool for a successful run
    replay = json.dumps({"run": run, "steps": [step]}, sort_keys=True) + "\n"
    manifest = {"replays": [{"file": "r.json", "sha256": hashlib.sha256(replay.encode()).hexdigest(), "bytes": len(replay.encode())}]}
    return {"r.json": replay, "manifest.json": json.dumps(manifest) + "\n"}


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    monkeypatch.setattr(x, "ROOT", tmp_path)                     # audit() must not read the real .env
    monkeypatch.setattr(x, "STATE", tmp_path / "no-state.json")   # no local artifacts: model-text leak check is skipped
    monkeypatch.setattr(x, "OUT", tmp_path / "public" / "replays")
    return tmp_path


def snapshot(d):
    return {p.name: p.read_bytes() for p in sorted(d.glob("*"))} if d.exists() else None


def test_clean_export_is_audited_and_then_written(sandbox, monkeypatch):
    monkeypatch.setattr(x, "build", good_files)
    assert x.main([]) == 0                                       # audit is mandatory even without --audit
    assert set(snapshot(x.OUT)) == {"r.json", "manifest.json"}
    assert not [p for p in x.OUT.parent.iterdir() if p.name.startswith(".replays-stage-")]


@pytest.mark.parametrize("flags", [[], ["--audit"]])
def test_failed_audit_writes_nothing_when_no_export_exists(sandbox, monkeypatch, flags):
    bad = good_files()
    bad["r.json"] = json.dumps({"run": {"thinking": "x"}, "steps": []})   # forbidden key and malformed structure
    monkeypatch.setattr(x, "build", lambda: bad)
    assert x.main(flags) == 1
    assert not x.OUT.exists()                                    # not even the directory
    assert not x.OUT.parent.exists() or not [p for p in x.OUT.parent.iterdir() if p.name.startswith(".replays-stage-")]


@pytest.mark.parametrize("flags", [[], ["--audit"]])
def test_failed_audit_never_overwrites_existing_exports(sandbox, monkeypatch, flags):
    monkeypatch.setattr(x, "build", good_files)
    assert x.main([]) == 0
    before = snapshot(x.OUT)
    bad = good_files()
    bad["r.json"] = bad["r.json"].replace('"id": "r"', '"id": "r", "request_id": "abc"')   # forbidden key + manifest hash mismatch
    monkeypatch.setattr(x, "build", lambda: bad)
    assert x.main(flags) == 1
    assert snapshot(x.OUT) == before                              # byte-identical: nothing overwritten, nothing removed, nothing added


def test_failed_integrity_check_also_blocks_the_write(sandbox, monkeypatch):
    bad = good_files()
    manifest = json.loads(bad["manifest.json"])
    manifest["replays"][0]["sha256"] = "0" * 64
    bad["manifest.json"] = json.dumps(manifest)
    monkeypatch.setattr(x, "build", lambda: bad)
    assert x.main([]) == 1 and not x.OUT.exists()


def test_credential_value_blocks_the_write(sandbox, monkeypatch):
    (sandbox / ".env").write_text("META_MODEL_API_KEY=sentinel-secret-value-0123456789\n")
    bad = good_files()
    bad["r.json"] = bad["r.json"].replace('"id": "r"', '"id": "sentinel-secret-value-0123456789"')
    monkeypatch.setattr(x, "build", lambda: bad)
    assert x.main([]) == 1 and not x.OUT.exists()


def test_check_is_read_only(sandbox, monkeypatch):
    monkeypatch.setattr(x, "build", good_files)
    assert x.main(["--check"]) == 1                              # nothing on disk: reports a mismatch ...
    assert not x.OUT.exists()                                    # ... without creating anything
    assert x.main([]) == 0
    before = snapshot(x.OUT)
    changed = good_files()
    changed["r.json"] += " "
    monkeypatch.setattr(x, "build", lambda: changed)
    assert x.main(["--check"]) == 1 and snapshot(x.OUT) == before


def rec(passed, shortfall, arm="B", rank=3, requests=12, loops=7):
    return {"arm": arm, "rank": rank, "requests": requests, "passed": passed, "shortfall": shortfall, "find_elements": [{}] * loops}


def test_failed_run_residual_is_null_and_marked_not_meaningful_but_counts_are_preserved():
    a = x.attribution_for(rec(False, {"detail_visit_shortfall": 2}))
    assert a["residual_requests"] is None and a["required_path_completed"] is False
    assert a["total_requests"] == 12 and a["tool_loop_requests"] == 7 and a["required_path_requests"] == 6
    assert "not meaningful" in a["residual_note"] and "efficiency" in a["residual_note"]


def test_successful_run_keeps_a_numeric_residual_and_no_note():
    a = x.attribution_for(rec(True, None, arm="A", rank=3, requests=4, loops=0))
    assert a["residual_requests"] == 2 and a["required_path_completed"] is True and a["residual_note"] is None
    b = x.attribution_for(rec(True, None, arm="B", rank=3, requests=8, loops=0))
    assert (b["required_path_requests"], b["residual_requests"]) == (6, 2)


def test_integrity_rejects_a_failed_run_with_a_numeric_residual():
    files = good_files()
    data = json.loads(files["r.json"])
    data["run"]["evaluator"]["passed"] = False
    data["run"]["verification_shortfall"] = {"detail_visit_shortfall": 2}
    data["run"]["attribution"].update(residual_requests=-1, required_path_completed=False)
    files["r.json"] = json.dumps(data, sort_keys=True) + "\n"
    manifest = json.loads(files["manifest.json"])
    manifest["replays"][0].update(sha256=hashlib.sha256(files["r.json"].encode()).hexdigest(), bytes=len(files["r.json"].encode()))
    files["manifest.json"] = json.dumps(manifest)
    assert any("failed run must have residual null" in f for f in x.integrity(files))
