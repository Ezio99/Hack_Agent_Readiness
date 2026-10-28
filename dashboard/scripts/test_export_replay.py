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
