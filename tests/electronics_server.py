"""Test helper: serve an electronics-v1 variant on an ephemeral loopback port in a background thread."""
import socket
import threading
import time
from contextlib import contextmanager

import uvicorn

from agent_readiness.environments.electronics.app import create_app


@contextmanager
def serve(variant):
    sock = socket.create_server(("127.0.0.1", 0))
    server = uvicorn.Server(uvicorn.Config(create_app(variant), log_level="error", access_log=False, lifespan="off"))
    thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
    thread.start()
    deadline = time.time() + 10
    while not server.started and time.time() < deadline:
        time.sleep(0.02)
    try:
        yield f"http://127.0.0.1:{sock.getsockname()[1]}"
    finally:
        server.should_exit = True
        thread.join(10)
        sock.close()
