"""Lifecycle routes of the product API (M8), mounted on the hosted app by `hosted.api.create_app(..., lifecycle=service)`.

  GET  /api/lifecycle/overview                                       steps, what is available, what is disabled and why
  GET  /api/lifecycle/sites, /api/lifecycle/sites/{site}             registered website contexts (business context, personas, variants)
  GET  /api/lifecycle/generations, /api/lifecycle/generations/{id}   Stage A generation and validation runs
  GET  /api/lifecycle/suites, /api/lifecycle/suites/{sha}            suites with their review packet and approval / freeze state
  POST /api/lifecycle/suites/{sha}/decision                          refused (403): web approval needs an authenticated owner (not configured)
  GET  /api/lifecycle/frozen                                         frozen suites a launch may name (server store only)
  GET  /api/lifecycle/evaluations, /api/lifecycle/evaluations/{id}   evaluation summaries; the full public evaluation document
  GET  /api/lifecycle/evaluations/{id}/trials/{trial}                one trial's public timeline
  GET  /api/lifecycle/evaluations/{id}/trials/{trial}/screenshots/{name}
  POST /api/lifecycle/evaluations                                    launch: {"frozen_suite": ref, "variants": [a, b], "mode": "rehearsal" | "paid"}
                                                                     operator-only; rehearsal only (paid is refused before anything is reserved)
  GET  /api/lifecycle/jobs/{id}                                      progress of a launched evaluation (live steps redacted for rehearsals)

Every request body forbids unknown fields; there is no task, URL, model, limit or spending field."""
from __future__ import annotations

import threading
from typing import Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field

from .service import LifecycleService, NotFound, Refused


class LaunchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    frozen_suite: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]{0,80}@v\d{1,4}$")
    variants: list[str] = Field(min_length=2, max_length=2)
    mode: Literal["rehearsal", "paid"] = "rehearsal"


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

    @app.get("/api/lifecycle/frozen")
    def frozen():
        return service.frozen_suites()

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

    @app.post("/api/lifecycle/evaluations", status_code=202)
    def launch(body: LaunchRequest, request: Request):
        def start(job_id: str):
            threading.Thread(target=service.work, args=(job_id,), daemon=True, name=job_id).start()
        return call(service.launch, frozen_suite=body.frozen_suite, variants=body.variants, mode=body.mode, operator=is_operator(request), start=start)

    @app.get("/api/lifecycle/jobs/{job_id}")
    def job(job_id: str):
        return call(service.job, job_id)
