"""Managed demo targets: registered storefronts served on loopback whose configuration an OPERATOR can change (the stand-in for 'the site owner applies the recommended change').
The audit API only accepts a registered target id — never a URL — and never learns, uses or exposes the target's internal configuration; recommendations come solely from what
the probe observes on the served pages. Initial state is operator configuration (server side)."""
from __future__ import annotations

import asyncio
import socket
import threading
from dataclasses import dataclass

import uvicorn

from ..environments.electronics.catalog import ENVIRONMENT_ID
from ..environments.electronics.variants import make_variant
from ..suite import core, registry

CHANGES = {"availability-on-listing-cards": ("availability", "listing"), "sku-on-listing-cards": ("sku", "listing"), "in-stock-filter": ("stockfilter", "on")}      # library change ids -> operator action
DEFAULT_INITIAL = {"availability": "detail", "specs": "structured", "sku": "listing"}


class _Switch:
    """ASGI indirection so the served app can be replaced while the server keeps its port."""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        await self.app(scope, receive, send)


@dataclass
class ManagedTarget:
    id: str
    description: str
    factors: dict
    applied: list
    base_url: str = ""
    _switch: _Switch | None = None
    _server: uvicorn.Server | None = None
    _thread: threading.Thread | None = None

    def _app(self):
        registry.load_all()
        return core.ENVIRONMENTS[ENVIRONMENT_ID].create_app(make_variant(self.factors["availability"], self.factors["specs"], self.factors["sku"], self.factors.get("stockfilter", "on")))

    def start(self) -> None:
        self._switch = _Switch(self._app())
        sock = socket.create_server(("127.0.0.1", 0))
        self.base_url = f"http://127.0.0.1:{sock.getsockname()[1]}"
        self._server = uvicorn.Server(uvicorn.Config(self._switch, log_level="error", access_log=False, lifespan="off"))
        self._thread = threading.Thread(target=lambda: asyncio.run(self._server.serve(sockets=[sock])), daemon=True, name=f"target-{self.id}")
        self._thread.start()
        for _ in range(500):
            if self._server.started:
                return
            threading.Event().wait(0.01)
        raise RuntimeError("target server did not start")

    def stop(self) -> None:
        if self._server:
            self._server.should_exit = True
        if self._thread:
            self._thread.join(10)

    def apply(self, change_id: str) -> dict:
        if change_id not in CHANGES:
            raise KeyError(change_id)
        factor, level = CHANGES[change_id]
        self.factors = {**self.factors, factor: level}
        if self._switch is not None:
            self._switch.app = self._app()
        if change_id not in self.applied:
            self.applied.append(change_id)
        return {"target_id": self.id, "applied": list(self.applied)}

    def current_variant(self):
        return make_variant(self.factors["availability"], self.factors["specs"], self.factors["sku"], self.factors.get("stockfilter", "on"))


class TargetRegistry:
    def __init__(self, targets: list[ManagedTarget] | None = None):
        self.targets = {t.id: t for t in (targets or [])}

    @classmethod
    def demo(cls, initial: dict | None = None) -> "TargetRegistry":
        return cls([ManagedTarget("demo-shop", "Managed demo electronics storefront (electronics-v1)", dict(initial or DEFAULT_INITIAL), [])])

    def start(self):
        for t in self.targets.values():
            t.start()
        return self

    def stop(self):
        for t in self.targets.values():
            t.stop()

    def get(self, target_id: str) -> ManagedTarget | None:
        return self.targets.get(target_id)

    def listing(self) -> list[dict]:
        return [{"id": t.id, "description": t.description, "managed": True} for t in self.targets.values()]
