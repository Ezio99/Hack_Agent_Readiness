"""An ephemeral local storefront owned and cleaned up by one experiment."""
import asyncio
from contextlib import asynccontextmanager
import socket
import uvicorn
from .storefront import app


@asynccontextmanager
async def local_storefront():
    sock = socket.create_server(("127.0.0.1", 0))
    sock.setblocking(False)
    url = f"http://127.0.0.1:{sock.getsockname()[1]}/"
    server = uvicorn.Server(uvicorn.Config(app, log_level="error", access_log=False, lifespan="off"))
    task = asyncio.create_task(server.serve(sockets=[sock]))
    try:
        async with asyncio.timeout(10):
            while not server.started:
                if task.done():
                    await task
                    raise RuntimeError("Storefront stopped before startup")
                await asyncio.sleep(0.01)
        yield url
    finally:
        server.should_exit = True
        try:
            await asyncio.wait_for(task, 10)
        finally:
            sock.close()
