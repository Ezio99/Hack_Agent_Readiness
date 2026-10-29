"""Deterministic mock model provider (no network, no credentials). It plays a *scripted agent behaviour* through the real Browser Use agent, real
Chromium, the real environment, the real fidelity guard and the real evaluator - only the model's decisions are replaced. Every result produced this way
is labelled ``mock`` and says nothing about how Meta Muse Spark would perform.

Behaviours (a server-side allow-list; the default is ``correct``):
  correct         navigate the pages a scripted solver needs, then submit the correct answer
  lazy            submit the correct answer after viewing only the home page (correct but not evidence-backed)
  wrong           do the navigation, then submit a plausible but wrong answer
  loop            repeat the same find_elements call (reproduces the agent-tool visibility gap), then submit a wrong answer
  stuck           make no progress until the step budget is exhausted
  escape          first try to navigate outside the allowed origin (must be blocked), then behave like ``correct``
  provider_error  the provider fails (HTTP 500) on the first request
  element_reader  a faithful model: asks find_elements for link targets on the listing, then USES them if (and only if) the next request actually shows them; otherwise it
                  keeps asking (as the live model did) and finally answers with what it could see (product names as SKUs). Reproduces the live T1 failure mode."""
from __future__ import annotations

import json
from typing import Any

import httpx
from fastapi.testclient import TestClient
from openai import DefaultAsyncHttpxClient

BEHAVIORS = ("correct", "lazy", "wrong", "loop", "stuck", "escape", "provider_error", "element_reader")
MOCK_USAGE = {"prompt_tokens": 9500, "completion_tokens": 300, "total_tokens": 9800, "completion_tokens_details": {"reasoning_tokens": 120}}


def corrupt(answer: Any) -> Any:
    """Add one to the first integer found: schema-valid but wrong."""
    done = False

    def walk(x):
        nonlocal done
        if isinstance(x, bool):
            return x
        if isinstance(x, int) and not done:
            done = True
            return x + 1
        if isinstance(x, dict):
            return {k: walk(v) for k, v in x.items()}
        if isinstance(x, list):
            return [walk(v) for v in x]
        return x
    return walk(json.loads(json.dumps(answer)))


def scripted_plan(instance, variant) -> tuple[list[str], dict]:
    """(page paths a scripted solver visits, correct answer) computed in-process against the same environment/variant the browser will use."""
    from ..environments.electronics.scripted import solve
    from ..suite import core
    env = core.ENVIRONMENTS[instance.spec.environment_id]
    client = TestClient(env.create_app(variant), base_url="http://shop.local")
    paths: list[str] = []

    def fetch(path):
        paths.append(path)
        r = client.get(path)
        r.raise_for_status()
        return r.text
    answer = solve(instance.spec.template_id, dict(instance.spec.parameters), instance.spec.outcome_type, fetch)
    deduped = [p for i, p in enumerate(paths) if i == 0 or p != paths[i - 1]]
    return deduped, answer


def _reply(n: int, action: dict | list) -> httpx.Response:
    actions = action if isinstance(action, list) else [action]
    out = {"evaluation_previous_goal": "mock", "memory": "", "next_goal": "mock step", "thinking": "mock agent (scripted behaviour, not a model)",
           "current_plan_item": 0, "plan_update": None, "action": actions}
    return httpx.Response(200, headers={"x-request-id": f"mock-{n}"}, json={
        "id": f"mock-{n}", "object": "chat.completion", "created": 0, "model": "mock-scripted-agent",
        "choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": json.dumps(out)}}], "usage": MOCK_USAGE})


def make_handler(instance, variant, base_url: str, behavior: str):
    if behavior not in BEHAVIORS:
        raise ValueError(f"unknown mock behavior {behavior!r}")
    paths, answer = scripted_plan(instance, variant)
    wrong = corrupt(answer)
    nav = lambda path: {"navigate": {"url": base_url + path, "new_tab": False}}
    script: list[dict] = []
    if behavior in ("correct", "wrong", "escape"):
        script = [nav(p) for p in paths]
        if behavior == "escape":     # first try to leave the allowed origin
            script.insert(0, {"navigate": {"url": "https://example.com/", "new_tab": False}})
    elif behavior == "lazy":
        script = [nav("/")]
    elif behavior == "loop":
        script = [nav("/c/headphones")] + [{"find_elements": {"selector": "a", "attributes": ["href"], "include_text": True, "max_results": 20}}] * 7
    reader = {"stage": "start"}
    final = {"done": {"data": answer if behavior in ("correct", "lazy", "escape") else wrong, "success": True}}
    state = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        state["n"] += 1
        n = state["n"]
        if behavior == "provider_error":
            return httpx.Response(500, json={"error": {"message": "mock provider failure", "type": "server_error"}})
        text = json.dumps(body["messages"]).lower()
        if behavior == "element_reader":
            return _element_reader(n, body, text, paths, nav, answer, reader)
        if "this is your last step" in text or n > len(script):
            if behavior == "stuck" and "this is your last step" not in text:
                return _reply(n, {"wait": {"seconds": 1}})
            return _reply(n, final)
        return _reply(n, script[n - 1])
    return handler


def attach_mock(llm, handler):
    """Route an already-constructed Browser Use ChatOpenAI client through the mock transport (same technique the tests use)."""
    llm.http_client = DefaultAsyncHttpxClient(transport=httpx.MockTransport(handler))
    sdk = llm.get_client()
    sdk._platform = "Linux"        # avoid the SDK's platform probe
    llm.get_client = lambda: sdk
    return llm


def _element_reader(n, body, text, paths, nav, answer, reader):
    """Scripted 'reads the tool output if it can see it' behaviour (see module docstring)."""
    listing = next((p for p in paths if p.startswith("/c/")), paths[min(1, len(paths) - 1)])
    last = "this is your last step" in text
    if n == 1:
        return _reply(n, nav(listing))
    if reader["stage"] == "start":
        reader["stage"] = "asked"
        return _reply(n, {"find_elements": {"selector": "a", "attributes": ["href"], "include_text": True, "max_results": 20}})
    visible = "<read_state_" in text and "/p/" in text.split("<read_state_", 1)[1]
    if reader["stage"] == "asked" and visible:
        reader["stage"] = "following"
        reader["queue"] = [p for p in paths if p.startswith("/p/") or p.startswith("/help/")]
    if reader["stage"] == "following":
        if reader.get("queue") and not last:
            return _reply(n, nav(reader["queue"].pop(0)))
        return _reply(n, {"done": {"data": answer, "success": True}})
    if last or n >= 11:                                  # never saw the elements: answers with what was visible (names in the sku field)
        return _reply(n, {"done": {"data": _names_as_skus(answer), "success": True}})
    return _reply(n, {"find_elements": {"selector": "a", "attributes": ["href"], "include_text": True, "max_results": 20}})


def _names_as_skus(answer):
    if isinstance(answer, dict) and isinstance(answer.get("products"), list):
        return {"products": [{**p, "sku": "(name only)"} for p in answer["products"]]}
    return answer
