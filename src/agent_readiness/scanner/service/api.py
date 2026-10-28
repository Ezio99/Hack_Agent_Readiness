"""HTTP API of the protected scanner. Authenticated with short-lived bearer tokens obtained by redeeming a server-verified invitation code.

Public:   GET /api/health, GET /api/registry, POST /api/session (redeem)
Private:  GET /api/session, POST /api/scans, GET /api/scans, GET /api/scans/{id}, GET /api/compare   (owner only; other users' scan ids look like 404)
Admin:    POST /api/admin/kill (X-Admin-Token)
Only pre-registered tasks and environment variants can be scanned; there is no field that accepts a URL, prompt, origin or agent instruction."""
from __future__ import annotations

import hmac
import time
from collections import defaultdict, deque

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from starlette.types import ASGIApp, Receive, Scope, Send

from ...suite import core, registry
from ..diagnostics import compare as compare_scans
from ..execute import execute_scan
from ..mock import BEHAVIORS
from . import views
from .config import ScannerConfig
from .manager import PER_SCAN_LIVE_RESERVATION_USD, ScanManager
from .store import ScanRefused, Store


class Redeem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str = Field(min_length=4, max_length=40)


class NewScan(BaseModel):
    model_config = ConfigDict(extra="forbid")        # no url, prompt, origin, instruction or tool fields can be supplied
    task_id: str = Field(max_length=100)
    variant_id: str = Field(max_length=100)
    mode: str = Field(default="mock", max_length=10)
    mock_behavior: str | None = Field(default=None, max_length=20)


class Kill(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool


class BodyLimit:
    """Reject request bodies larger than the limit before the application sees them (by declared length and by bytes actually received)."""
    def __init__(self, app: ASGIApp, limit: int):
        self.app, self.limit = app, limit

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        declared = dict(scope["headers"]).get(b"content-length")
        if declared and int(declared) > self.limit:
            return await JSONResponse({"code": "body_too_large", "message": "Request body too large."}, status_code=413)(scope, receive, send)
        total = 0

        async def limited():
            nonlocal total
            message = await receive()
            total += len(message.get("body", b""))
            if total > self.limit:
                raise HTTPException(413, "Request body too large.")
            return message
        return await self.app(scope, limited, send)


def create_scanner_app(config: ScannerConfig, runner=execute_scan, store: Store | None = None, manager: ScanManager | None = None) -> FastAPI:
    registry.load_all()
    store = store or Store(config)
    store.recover_interrupted()
    manager = manager or ScanManager(store, config, runner)
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None, title="Agent Readiness scanner")
    app.state.store, app.state.manager, app.state.config = store, manager, config
    hits: dict[str, deque] = defaultdict(deque)

    app.add_middleware(BodyLimit, limit=config.max_body_bytes)
    if config.cors_origins:
        app.add_middleware(CORSMiddleware, allow_origins=list(config.cors_origins), allow_credentials=False, allow_methods=["GET", "POST"],
                           allow_headers=["Authorization", "Content-Type", "Idempotency-Key", "X-Admin-Token"], max_age=600)

    @app.middleware("http")
    async def guard(request: Request, call_next):
        client = request.client.host if request.client else "unknown"
        q = hits[client]
        now = time.monotonic()
        while q and q[0] < now - 60:
            q.popleft()
        if len(q) >= config.rate_limit_per_minute:
            return JSONResponse({"code": "rate_limited", "message": "Too many requests."}, status_code=429, headers={"Retry-After": "60"})
        q.append(now)
        try:
            response = await call_next(request)
        except HTTPException as exc:
            response = JSONResponse({"code": "http_error", "message": exc.detail}, status_code=exc.status_code)
        response.headers.update({"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff", "Referrer-Policy": "no-referrer"})
        return response

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException):
        return JSONResponse({"code": "http_error", "message": exc.detail}, status_code=exc.status_code)

    def client_of(request: Request) -> str:
        return request.client.host if request.client else "unknown"

    def current_session(authorization: str | None = Header(default=None)) -> dict:
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(401, "Authentication required.")
        session = store.session_for(authorization[7:].strip())
        if session is None:
            raise HTTPException(401, "The session is invalid or has expired.")
        return session

    @app.get("/api/health")
    async def health():
        return {"status": "ok", "kill_switch": manager.killed()}

    @app.get("/api/registry")
    async def registry_endpoint():
        return views.registry_view(config, manager.killed())

    @app.post("/api/session")
    async def redeem(body: Redeem, request: Request):
        client = client_of(request)
        if store.failed_attempts(client) >= config.code_attempts_per_10_min:
            raise HTTPException(429, "Too many failed attempts; try again later.")
        got = store.redeem(body.code)
        if got is None:
            store.record_failed_attempt(client)
            raise HTTPException(401, "Invalid, expired or already used code.")
        token, info = got
        return {"token": token, "expires_at": info["expires_at"], "scan_quota": info["scan_quota"], "scans_used": 0}

    @app.get("/api/session")
    async def session_info(session: dict = Depends(current_session)):
        return {"expires_at": session["expires_at"], "scan_quota": session["scan_quota"], "scans_used": session["scans_used"], "live_available": config.live_available}

    @app.post("/api/scans", status_code=202)
    async def create_scan(body: NewScan, session: dict = Depends(current_session), idempotency_key: str | None = Header(default=None, max_length=64)):
        if manager.killed():
            raise HTTPException(503, "Scanning is paused by the operator.")
        variants = {v.variant_id: v for env in core.ENVIRONMENTS.values() for v in env.variants()}
        task_ids = {i.spec.task_id: i for i in core.all_instances()}
        if body.task_id not in task_ids or body.variant_id not in variants:
            raise HTTPException(422, "Unknown task or variant: only registered tasks and environment variants can be scanned.")
        if variants[body.variant_id].environment_id != task_ids[body.task_id].spec.environment_id:
            raise HTTPException(422, "That variant does not belong to the task's environment.")
        if body.mode not in ("mock", "live"):
            raise HTTPException(422, "mode must be mock or live.")
        if body.mode == "live" and not config.live_available:
            raise HTTPException(403, "Live inference is not enabled on this server.")
        if body.mock_behavior is not None and (body.mode != "mock" or body.mock_behavior not in BEHAVIORS or (not config.allow_mock_behaviors and body.mock_behavior != "correct")):
            raise HTTPException(422, "Invalid mock scenario.")
        try:
            scan_id = store.reserve_scan(session, body.task_id, body.variant_id, body.mode, body.mock_behavior, PER_SCAN_LIVE_RESERVATION_USD if body.mode == "live" else 0.0,
                                         config.live_budget_usd, idempotency_key)
        except ScanRefused as exc:
            raise HTTPException(exc.status, exc.message)
        scan = store.get_scan(scan_id)
        if scan["status"] == "queued":
            manager.submit(scan_id, body.task_id, variants[body.variant_id], body.mode, body.mock_behavior)
        return {"scan_id": scan_id, "status": scan["status"]}

    def owned(scan_id: str, session: dict) -> dict:
        scan = store.get_scan(scan_id)
        if scan is None or scan["invitation_id"] != session["invitation_id"]:
            raise HTTPException(404, "Scan not found.")        # identical response for unknown and foreign ids
        return scan

    @app.get("/api/scans")
    async def list_scans(session: dict = Depends(current_session)):
        return {"scans": [views.summary(s) for s in store.scans_of(session["invitation_id"])]}

    @app.get("/api/scans/{scan_id}")
    async def get_scan(scan_id: str, session: dict = Depends(current_session)):
        scan = owned(scan_id, session)
        return views.public_result(scan, manager.private_result(scan_id) if scan["status"] == "complete" else None)

    @app.get("/api/compare")
    async def compare(baseline: str, rescan: str, session: dict = Depends(current_session)):
        a, b = owned(baseline, session), owned(rescan, session)
        pa, pb = manager.private_result(baseline), manager.private_result(rescan)
        if a["status"] != "complete" or b["status"] != "complete" or pa is None or pb is None:
            raise HTTPException(409, "Both scans must be complete.")
        try:
            return compare_scans(pa, pb)
        except ValueError as exc:
            raise HTTPException(422, str(exc))

    @app.post("/api/admin/kill")
    async def kill(body: Kill, x_admin_token: str | None = Header(default=None)):
        if not config.admin_token or not x_admin_token or not hmac.compare_digest(x_admin_token, config.admin_token):
            raise HTTPException(403, "Forbidden.")
        if body.enabled:
            config.kill_switch_path.write_text("on")
            cancelled = manager.cancel_all()
            return {"kill_switch": True, "cancelled_running": cancelled}
        config.kill_switch_path.unlink(missing_ok=True)
        return {"kill_switch": False}

    return app
