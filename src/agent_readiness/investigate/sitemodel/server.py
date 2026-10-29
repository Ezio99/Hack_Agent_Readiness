"""Read-only local mirror of a `Snapshot` (ASGI). GET/HEAD only; anything else is refused with 405 and recorded in `blocked` (a form POST is captured, never forwarded anywhere).
Serves exactly the captured resources: no directory listing, no query fallback, no proxying. A restrictive Content-Security-Policy keeps pages from reaching other origins. Serve it
with `scanner.serve.serve_app` (loopback only) for real-browser trials; tests drive it in-process through `httpx.ASGITransport`."""
from __future__ import annotations

from .snapshot import Snapshot

CSP = "default-src 'self' 'unsafe-inline' data:; frame-ancestors 'none'; form-action 'self'; base-uri 'none'"


class Mirror:
    def __init__(self, snapshot: Snapshot):
        self.snapshot = snapshot
        self.log: list[dict] = []          # {"method", "path", "status"} — the page-view record for trial metrics
        self.blocked: list[dict] = []

    async def _send(self, send, status: int, headers: list, body: bytes) -> None:
        await send({"type": "http.response.start", "status": status, "headers": [(k.encode(), v.encode()) for k, v in headers]})
        await send({"type": "http.response.body", "body": body})

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return
        method = scope["method"]
        path = scope["path"] or "/"
        key = path + (f"?{scope['query_string'].decode('latin-1')}" if scope.get("query_string") else "")
        base = [("cache-control", "no-store"), ("x-content-type-options", "nosniff"), ("content-security-policy", CSP)]
        if method not in ("GET", "HEAD"):
            self.blocked.append({"method": method, "path": path})
            return await self._send(send, 405, base + [("allow", "GET, HEAD"), ("content-type", "text/plain")], b"read-only mirror")
        r = self.snapshot.get(key)
        if r is None:
            self.log.append({"method": method, "path": key, "status": 404})
            return await self._send(send, 404, base + [("content-type", "text/html; charset=utf-8")], b"<!doctype html><title>Not found</title><h1>Not found</h1>")
        self.log.append({"method": method, "path": key, "status": r.status})
        if r.location:
            return await self._send(send, r.status, base + [("location", r.location)], b"")
        await self._send(send, r.status, base + [("content-type", r.content_type or "application/octet-stream"), ("content-length", str(len(r.body)))], b"" if method == "HEAD" else r.body)
