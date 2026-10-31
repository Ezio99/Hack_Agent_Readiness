"""HTTP routes of the live evaluation product, mounted on the protected scanner app (same invitation sessions, rate limit, body limit, kill switch and CORS rules).
    GET  /api/live/targets            registered demo websites (no URL field exists anywhere)
    POST /api/live/jobs               start a bounded evaluation {target_id, goal}                          -> 202 job view
    GET  /api/live/jobs               this session's evaluations
    GET  /api/live/jobs/{id}          status polled by the UI: stages, progress, trials, trace events, recorded spend
    POST /api/live/jobs/{id}/cancel
    GET  /api/live/jobs/{id}/export   the sanitized `investigation-dashboard-v1` report of the run (replay: no model call, no execution)"""
from __future__ import annotations

import asyncio
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from .jobs import JobError, JobManager
from .targets import listing


class NewJob(BaseModel):
    model_config = ConfigDict(extra="forbid")                      # no url, no prompt, no key, no command
    target_id: str = Field(max_length=60)
    goal: str = Field(max_length=400)
    mode: Literal["mock", "live"] = "mock"
    confirm_budget_usd: float | None = Field(default=None, ge=0, le=100)   # live only: the user's explicit confirmation of the maximum spend; must equal the server's cap


def add_live_routes(app: FastAPI, jobs: JobManager, current_session) -> None:
    async def run(fn, *a):
        try:
            return await asyncio.to_thread(fn, *a)
        except JobError as e:
            raise HTTPException(e.status, e.message)

    @app.get("/api/live/targets")
    async def live_targets(session: dict = Depends(current_session)):
        live = jobs.live.available()
        return {"targets": listing() if not live else [t for t in listing() if t["id"] == "ironbark"] + [t for t in listing() if t["id"] != "ironbark"], "modes": {"mock": True, "live": live},
                "live": {"cap_usd": jobs.live.cap_usd, "model": jobs.live.model, "targets": ["ironbark"], "dev_provider": jobs.live.dev_provider} if live else None}

    @app.post("/api/live/jobs", status_code=202)
    async def live_start(body: NewJob, session: dict = Depends(current_session)):
        return await run(jobs.create, session["id"], body.target_id, body.goal, body.mode, body.confirm_budget_usd)

    @app.get("/api/live/jobs")
    async def live_list(session: dict = Depends(current_session)):
        return {"jobs": await run(jobs.list, session["id"])}

    @app.get("/api/live/jobs/{job_id}")
    async def live_get(job_id: str, session: dict = Depends(current_session)):
        return await run(jobs.get, job_id, session["id"])

    @app.post("/api/live/jobs/{job_id}/cancel")
    async def live_cancel(job_id: str, session: dict = Depends(current_session)):
        return await run(jobs.cancel, job_id, session["id"])

    @app.get("/api/live/jobs/{job_id}/export")
    async def live_export(job_id: str, session: dict = Depends(current_session)):
        return await run(jobs.export, job_id, session["id"])
