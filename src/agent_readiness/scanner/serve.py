"""Serve a registered environment variant on an ephemeral loopback port for the duration of a scan. The target is never user-supplied."""
from __future__ import annotations

import asyncio
import socket
from contextlib import asynccontextmanager

import uvicorn


@asynccontextmanager
async def serve_app(app):
    sock = socket.create_server(("127.0.0.1", 0))
    sock.setblocking(False)
    server = uvicorn.Server(uvicorn.Config(app, log_level="error", access_log=False, lifespan="off"))
    task = asyncio.create_task(server.serve(sockets=[sock]))
    try:
        async with asyncio.timeout(10):
            while not server.started:
                if task.done():
                    await task
                    raise RuntimeError("environment server stopped before startup")
                await asyncio.sleep(0.01)
        yield f"http://127.0.0.1:{sock.getsockname()[1]}"
    finally:
        server.should_exit = True
        try:
            await asyncio.wait_for(task, 10)
        finally:
            sock.close()
