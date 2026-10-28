"""The LIVE code path of execute_scan (real HTTP client, key scrubbing, real guard) against a LOCAL fake provider on loopback. No external network, no credentials."""
import asyncio
import tempfile
import threading

import httpx
import pytest
import uvicorn
from fastapi import FastAPI, Request, Response

from agent_readiness.agent import ModelConfig
from agent_readiness.environments.electronics.variants import make_variant
from agent_readiness.scanner import mock
from agent_readiness.scanner.execute import execute_scan
from agent_readiness.suite import registry

pytestmark = pytest.mark.browser
registry.load_all()
TASK = "t3-cheapest-monitor-27in-usbc-120hz"


def test_live_path_against_local_fake_provider(monkeypatch):
    monkeypatch.setenv("META_MODEL_API_KEY", "fake-key-123456789")
    seen = {"auth": set(), "n": 0}
    holder = {}
    app = FastAPI()

    @app.post("/v1/chat/completions")
    async def completions(request: Request):
        body = await request.body()
        seen["auth"].add(request.headers.get("authorization"))
        seen["n"] += 1
        r = holder["handler"](httpx.Request("POST", "http://x/", content=body))
        return Response(r.content, status_code=r.status_code, media_type="application/json")

    import socket
    s = socket.create_server(("127.0.0.1", 0)); port = s.getsockname()[1]
    srv = uvicorn.Server(uvicorn.Config(app, log_level="error", lifespan="off"))
    threading.Thread(target=lambda: srv.run(sockets=[s]), daemon=True).start()
    inst = registry.get_instance(TASK)
    variant = make_variant("listing", "structured")
    # the fake provider needs the environment's base URL for navigation; reuse the mock handler factory lazily on first call
    real_make = mock.make_handler

    async def go():
        return await execute_scan(TASK, variant, provider="live", api_key="fake-key-123456789", output=tempfile.mkdtemp(), model_config=ModelConfig(base_url=f"http://127.0.0.1:{port}/v1"))
    # navigation URLs must point at the env origin, which is chosen at run time: learn it from the task prompt
    state = {}
    def handler(request):
        import json, re
        body = json.loads(request.content)
        if "h" not in state:
            text = json.dumps(body["messages"])
            base = re.search(r"Start at (http://127\.0\.0\.1:\d+)", text) or re.search(r"(http://127\.0\.0\.1:\d+)/", text)
            state["h"] = real_make(inst, variant, base.group(1), "correct")
        return state["h"](request)
    holder["handler"] = handler
    try:
        r = asyncio.run(go())
    finally:
        srv.should_exit = True
    assert seen["auth"] == {"Bearer fake-key-123456789"} and seen["n"] >= 2
    assert r["scan"]["mode"] == "live"
    assert r["outcome"]["run_status"] == "completed", r["outcome"]
    assert r["evaluation"]["passed"] and "fake-key" not in str(r)
