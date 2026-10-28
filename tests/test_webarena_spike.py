"""WebArena Verified integration spike (credential-free). Needs the optional `webarena-verified` package (skipped otherwise, e.g. in CI).
The WebArena Magento site is NOT used: a tiny local stub storefront stands in so the PIPELINE (Browser Use agent -> HAR -> official evaluator) is exercised.
A pass here proves wiring, not anything about the real site or live-model behaviour."""
import asyncio
import json
import tempfile
from pathlib import Path

import pytest

pytest.importorskip("webarena_verified")
from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from agent_readiness.scanner import mock
from agent_readiness.scanner.serve import serve_app
from agent_readiness.webarena.adapter import WAAnswer, WebArenaShopping, available
from agent_readiness.webarena.runner import run_task

pytestmark = pytest.mark.browser
SLUG = "/portable-ssd-2tb-external-hard-drive-mobile-solid-state-drive-portable-hard-drive-for-pc-laptop-and-mac-data-storage-and-transfer-2tb-silver.html"
OK = {"task_type": "NAVIGATE", "status": "SUCCESS", "retrieved_data": None, "error_details": None}


def stub_app():
    app = FastAPI()
    links = "".join(f'<li><a href="/p{i}.html">Other drive {i}</a></li>' for i in range(8))

    @app.get("/", response_class=HTMLResponse)
    async def home():
        return f'<html><body><h1>Stub One Stop Market</h1><ul>{links}<li><a href="{SLUG}">Portable SSD 2TB</a></li></ul></body></html>'

    @app.get("/{path:path}", response_class=HTMLResponse)
    async def page(path: str):
        return f"<html><body><h1>{path}</h1><p>Product page</p></body></html>"
    return app


def factory(script):
    def make(task, base_url):
        state = {"n": 0}

        def handler(request):
            import httpx
            state["n"] += 1
            body = json.loads(request.content)
            text = json.dumps(body["messages"])
            action = script(state["n"], text, base_url)
            return mock._reply(state["n"], action)
        return handler
    return make


def go_direct(n, text, base):
    return {"navigate": {"url": base + SLUG, "new_tab": False}} if n == 1 else {"done": {"data": OK, "success": True}}


def go_wrong(n, text, base):
    return {"navigate": {"url": base + "/p3.html", "new_tab": False}} if n == 1 else {"done": {"data": OK, "success": True}}


def make_reader():
    """Scripted model that uses link targets only if they are actually shown to it (same idea as the synthetic-suite element_reader)."""
    st = {"stage": "home"}

    def script(n, text, base):
        if st["stage"] == "home":
            st["stage"] = "ask"
            return {"navigate": {"url": base + "/", "new_tab": False}}
        if st["stage"] == "ask":
            st["stage"] = "asked"
            return {"find_elements": {"selector": "a", "attributes": ["href"], "include_text": True, "max_results": 20}}
        if st["stage"] == "asked":
            if "<read_state_" in text and SLUG in text.split("<read_state_", 1)[1]:
                st["stage"] = "follow"
                return {"navigate": {"url": base + SLUG, "new_tab": False}}
            if n >= 8:
                st["stage"] = "follow"
                return {"done": {"data": {"task_type": "NAVIGATE", "status": "NOT_FOUND_ERROR", "retrieved_data": None, "error_details": "could not see link targets"}, "success": False}}
            return {"find_elements": {"selector": "a", "attributes": ["href"], "include_text": True, "max_results": 20}}
        return {"done": {"data": OK, "success": True}}
    return script


def run(script, profile_id="suite-v2-compat1", task_id=286):
    async def main():
        async with serve_app(stub_app()) as base:
            shop = WebArenaShopping(base)
            return await run_task(shop, shop.task(task_id), output=Path(tempfile.mkdtemp()), handler_factory=factory(script), profile_id=profile_id)
    return asyncio.run(main())


def test_official_task_loading_and_shortlist_definitions():
    assert available()
    shop = WebArenaShopping("http://localhost:7770")
    t = {i: shop.task(i) for i in (286, 124, 25, 431, 508, 528)}
    assert t[286].task_type == "navigate" and t[286].start_urls == ("http://localhost:7770",) and "least expensive ssd" in t[286].intent
    assert t[124].task_type == "retrieve" and t[124].network_evaluators == 0
    assert t[25].start_urls[0].startswith("http://localhost:7770/epson") and t[431].task_type == "mutate" and len(t[431].start_urls) == 3
    assert t[508].network_evaluators == 4 and t[528].network_evaluators == 2
    assert "__SHOPPING__" not in t[286].prompt()
    assert WAAnswer.model_json_schema()["required"] == ["task_type", "status"]


def test_official_evaluator_scores_hars_offline_without_the_site():
    shop = WebArenaShopping("http://localhost:7770")
    def ent(method, url, post=None):
        e = {"startedDateTime": "2026-10-28T00:00:00Z", "time": 1, "request": {"method": method, "url": url, "httpVersion": "HTTP/1.1", "headers": [{"name": "Accept", "value": "text/html,*/*"}], "queryString": [], "cookies": [], "headersSize": -1, "bodySize": -1},
             "response": {"status": 200, "statusText": "OK", "httpVersion": "HTTP/1.1", "headers": [], "cookies": [], "content": {"size": 0, "mimeType": "text/html", "text": ""}, "redirectURL": "", "headersSize": -1, "bodySize": -1}, "cache": {}, "timings": {"send": 0, "wait": 1, "receive": 0}}
        if post:
            e["request"]["postData"] = {"mimeType": "application/x-www-form-urlencoded", "text": post}
        return e
    ok = shop.evaluate(286, OK, [ent("GET", "http://localhost:7770" + SLUG)])
    bad = shop.evaluate(286, OK, [ent("GET", "http://localhost:7770/other.html")])
    assert ok["passed"] and not bad["passed"] and "missing_navigation_event" in str(bad["evaluators"])
    r = lambda lo, hi: {"task_type": "RETRIEVE", "status": "SUCCESS", "retrieved_data": [{"min": lo, "max": hi}]}
    assert shop.evaluate(124, r(0.01, 298.0), [ent("GET", "http://localhost:7770")])["passed"] and not shop.evaluate(124, r(0.01, 250.0), [ent("GET", "http://localhost:7770")])["passed"]
    add = lambda pid: [ent("POST", f"http://localhost:7770/checkout/cart/add/uenc/x/product/{pid}/", post=f"qty=1&item={pid}")]
    done = {"task_type": "MUTATE", "status": "SUCCESS", "retrieved_data": None}
    assert shop.evaluate(431, done, add(32202))["passed"] and not shop.evaluate(431, done, add(1))["passed"]
    assert shop.evaluate(286, OK, [ent("GET", "http://localhost:7770" + SLUG)])["evaluator_version"]


def test_end_to_end_browser_use_agent_records_a_har_the_official_evaluator_accepts():
    r = run(go_direct)
    assert r["run_status"] == "completed" and r["har_present"] and r["official_verdict"]["passed"], r
    assert r["profile"] == "suite-v2-compat1" and r["mode"] == "mock" and r["model_requests"] == 2


def test_wrong_page_is_a_task_failure_attributed_by_the_official_evaluator_not_by_us():
    r = run(go_wrong)
    assert r["run_status"] == "completed" and not r["official_verdict"]["passed"]
    assert any(e["name"] == "NetworkEventEvaluator" and e["status"] != "success" for e in r["official_verdict"]["evaluators"])


def test_tool_visibility_fix_works_in_the_webarena_runner_v2_but_not_v1():
    v2 = run(make_reader())
    assert v2["official_verdict"]["passed"] and v2["model_requests"] == 4, v2
    v1 = run(make_reader(), profile_id="suite-v1-compat1")
    assert not v1["official_verdict"]["passed"] and v1["model_requests"] > v2["model_requests"]      # v1: the model never sees the link targets
