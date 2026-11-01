"""Fixed-target hosted job API. No live executor is configured by this module.

An executor must be installed by the deployment after its network isolation is
verified. The default fails closed before reserving budget or spawning work.
"""
from __future__ import annotations

import hashlib
import hmac
import re
import secrets
import threading
from pathlib import Path
from typing import Protocol

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, ConfigDict

from .admission import Admission, Refused
from ..investigate import export as exporter


class Executor(Protocol):
    def run(self, job_id: str) -> None: ...


class StartRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')


def create_app(root: Path, admission: Admission, *, client_key: bytes, executor: Executor | None = None) -> FastAPI:
    if len(client_key) < 32:
        raise ValueError('client identity key must be at least 32 bytes')
    root = Path(root)
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    def checked_job(job_id: str):
        if not re.fullmatch(r'paired-[0-9a-f]{32}', job_id):
            raise HTTPException(404, 'Evaluation not found')
        job = admission.get(job_id)
        if not job:
            raise HTTPException(404, 'Evaluation not found')
        return job

    def work(job_id: str):
        try:
            admission.transition(job_id, 'reserved', 'running')
            executor.run(job_id)
            # Do not mark complete unless the existing exporter accepts the run.
            public = exporter.public_demo(exporter.export_run(root / job_id))
            if not public['run']['complete'] or public['evaluation']['state'] != 'evaluated':
                raise ValueError('evaluation is incomplete')
            admission.transition(job_id, 'running', 'completed')
        except Exception:
            job = admission.get(job_id)
            if job and job['state'] in ('reserved', 'running'):
                admission.transition(job_id, job['state'], 'failed')

    @app.post('/api/ironbark/jobs', status_code=202)
    def start(body: StartRequest, request: Request):
        if executor is None:
            raise HTTPException(503, 'Evaluations are currently unavailable')
        # Never trust forwarded headers: the deployment must supply a verified peer.
        peer = request.client.host if request.client else ''
        if not peer:
            raise HTTPException(403, 'Client identity unavailable')
        client = hmac.new(client_key, peer.encode(), hashlib.sha256).hexdigest()
        job_id = 'paired-' + secrets.token_hex(16)
        try:
            admission.reserve(job_id, client)
        except Refused as exc:
            raise HTTPException(429, str(exc)) from exc
        try:
            threading.Thread(target=work, args=(job_id,), daemon=True).start()
        except Exception as exc:
            admission.transition(job_id, 'reserved', 'failed')
            raise HTTPException(503, 'Unable to start evaluation') from exc
        return {'id': job_id, 'state': 'reserved'}

    @app.get('/api/ironbark/jobs/{job_id}')
    def status(job_id: str):
        job = checked_job(job_id)
        # No raw traces or private run state are exposed.
        return {'id': job_id, 'state': job['state']}

    @app.get('/api/ironbark/jobs/{job_id}/export')
    def export(job_id: str):
        if checked_job(job_id)['state'] != 'completed':
            raise HTTPException(409, 'Evaluation results are not available')
        try:
            data = exporter.public_demo(exporter.export_run(root / job_id))
            if not data['run']['complete'] or data['evaluation']['state'] != 'evaluated':
                raise ValueError('evaluation incomplete')
            return data
        except Exception as exc:
            raise HTTPException(503, 'Sanitized results are unavailable') from exc

    return app
