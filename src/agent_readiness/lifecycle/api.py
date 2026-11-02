"""Lifecycle routes of the product API (M8), mounted on the hosted app by `hosted.api.create_app(..., lifecycle=service)`.

  GET  /api/lifecycle/overview                                       steps, what is available, what is disabled and why
  GET  /api/lifecycle/sites, /api/lifecycle/sites/{site}             registered website contexts (business context, personas, variants)
  GET  /api/lifecycle/generations, /api/lifecycle/generations/{id}   Stage A generation and validation runs
  GET  /api/lifecycle/suites, /api/lifecycle/suites/{sha}            suites with their review packet and approval / freeze state
  POST /api/lifecycle/suites/{sha}/decision                          refused (403): web approval needs an authenticated owner (not configured)
  GET  /api/lifecycle/evaluations, /api/lifecycle/evaluations/{id}   evaluation summaries; the full public evaluation document (datasets and hosted jobs)
  GET  /api/lifecycle/evaluations/{id}/trials/{trial}                one trial's public timeline
  GET  /api/lifecycle/evaluations/{id}/trials/{trial}/screenshots/{name}

Nothing here launches an evaluation: the hosted evaluation (`POST /api/ironbark/jobs {"repetitions"}`) is the product's one launch path.
Every request body forbids unknown fields; there is no task, URL, model, limit or spending field."""
from __future__ import annotations

from typing import Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field

from .service import LifecycleService, NotFound, Refused


class DecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: Literal["approved", "rejected"]
    attestation: str = Field(max_length=400)


def register(app: FastAPI, service: LifecycleService, *, is_operator) -> None:
    def call(fn, *a, **k):
        try:
            return fn(*a, **k)
        except NotFound:
            raise HTTPException(404, "Not found") from None
        except Refused as exc:
            raise HTTPException(exc.status, {"code": exc.code, "message": exc.detail}) from None

    @app.get("/api/lifecycle/overview")
    def overview():
        return service.overview()

    @app.get("/api/lifecycle/sites")
    def sites():
        return service.sites()

    @app.get("/api/lifecycle/sites/{site_id}")
    def site(site_id: str):
        return call(service.site, site_id)

    @app.get("/api/lifecycle/generations")
    def generations():
        return service.generations()

    @app.get("/api/lifecycle/generations/{gid}")
    def generation(gid: str):
        return call(service.generation, gid)

    @app.get("/api/lifecycle/suites")
    def suites():
        return service.suites()

    @app.get("/api/lifecycle/suites/{sha}")
    def suite(sha: str):
        return call(service.suite, sha)

    @app.post("/api/lifecycle/suites/{sha}/decision")
    def decide(sha: str, body: DecisionRequest, request: Request):
        return call(service.decide, sha, body.model_dump())          # always refused in this release (server-side), operator token or not

    @app.get("/api/lifecycle/evaluations")
    def evaluations():
        return service.evaluations()

    @app.get("/api/lifecycle/evaluations/{eid}")
    def evaluation(eid: str):
        return call(service.evaluation, eid)

    @app.get("/api/lifecycle/evaluations/{eid}/trials/{trial}")
    def timeline(eid: str, trial: str):
        return call(service.timeline, eid, trial)

    @app.get("/api/lifecycle/evaluations/{eid}/trials/{trial}/screenshots/{name}")
    def screenshot(eid: str, trial: str, name: str):
        path, media = call(service.screenshot, eid, trial, name)
        return FileResponse(path, media_type=media, headers={"Cache-Control": "public, max-age=86400, immutable"})
