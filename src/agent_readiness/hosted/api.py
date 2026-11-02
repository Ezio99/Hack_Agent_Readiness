"""Fixed-target hosted evaluation API (Ironbark only).

The public request body is ``{"repetitions": 1 | 3 | 5}`` and nothing else: no
URL, task, model, browser command or spending field exists. The executor is
installed by the deployment (``hosted.serve``); without one the API refuses to
start evaluations before reserving budget.

Public responses contain only job states, per-task progress, aggregate
metrics and the existing sanitized ``public_demo`` export.
"""
from __future__ import annotations

import hashlib
import hmac
import ipaddress
import json
import os
import re
import secrets
import signal
import subprocess
import threading
from pathlib import Path
from typing import Literal, Protocol

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, ConfigDict

from . import paired
from .admission import Admission, Refused
from ..investigate import export as exporter
from ..live import ironbark_runner

JOB_ID = re.compile(r'eval-[0-9a-f]{32}')
TERMINAL = ('completed', 'failed', 'timed_out', 'interrupted')


class Executor(Protocol):
    available: bool
    mode: str
    def run(self, job_id: str) -> None: ...


class StartRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    repetitions: Literal[1, 3, 5] = 1


def public_tasks() -> list[dict]:
    """The four frozen public prompts, read from the source run (already published in the Tasks stage)."""
    try:
        from ..investigate.run import InvestigationRun
        tasks = InvestigationRun(ironbark_runner.SOURCE).artifact('tasks-manifest')['tasks']
        return [{'task': i + 1, 'question': t['question'], 'limits': t.get('limits')} for i, t in enumerate(sorted(tasks, key=lambda t: t['task_id']))]
    except Exception:
        return []


def _outcome(row: dict) -> str:
    if row['state'] != 'completed':
        return row['state']
    if row.get('evidence_supported'):
        return 'evidence_supported_pass'
    return 'strict_pass' if row.get('strict_pass') else 'not_passed'


def repetition_status(root: Path, rep: dict) -> dict:
    out = {'index': rep['index'], 'state': rep['state'], 'tasks': [], 'assessment': None}
    try:
        operator = json.loads((root / (rep['run_id'] + '.json')).read_text())
        if operator.get('id') != rep['run_id']:
            raise ValueError('run identity mismatch')
        aliases = {t['task_id']: i + 1 for i, t in enumerate(sorted(operator['tasks'], key=lambda t: t['task_id']))}
        for row in ironbark_runner.progress(root, operator):
            out['tasks'].append({'arm': row['arm'], 'task': aliases[row['task_id']], 'state': row['state'], 'outcome': _outcome(row),
                                 **{k: row.get(k) for k in ('requests', 'page_views', 'steps', 'elapsed_seconds')}})
    except (OSError, ValueError, KeyError, TypeError):
        pass  # before preparation or during an interrupted write: unavailable, never invented
    return out


def summarize(reps: list[dict]) -> dict:
    """Descriptive per-arm totals across finished trials; not a causal estimate."""
    out = {}
    for arm in ('Original', 'Modified'):
        rows = [t for r in reps for t in r['tasks'] if t['arm'] == arm]
        done = [t for t in rows if t['state'] == 'completed']
        mean = lambda k: round(sum(t[k] for t in done if t.get(k) is not None) / len(done), 2) if done and all(t.get(k) is not None for t in done) else None
        out[arm] = {'planned': 4 * len(reps), 'completed': len(done), 'failed': sum(t['state'] == 'failed' for t in rows),
                    'evidence_supported_passes': sum(t['outcome'] == 'evidence_supported_pass' for t in done),
                    'strict_passes': sum(t['outcome'] in ('evidence_supported_pass', 'strict_pass') for t in done),
                    'requests_total': sum(t.get('requests') or 0 for t in done),
                    'requests_mean': mean('requests'), 'page_views_mean': mean('page_views'), 'steps_mean': mean('steps'), 'elapsed_mean': mean('elapsed_seconds')}
    return out


def verified_export(root: Path, run_id: str) -> dict:
    data = exporter.public_demo(exporter.export_run(root / run_id))
    if not data['run']['complete'] or data['evaluation']['state'] != 'evaluated':
        raise ValueError('evaluation is incomplete')
    return data


def _assessment(data: dict) -> dict:
    ev = data.get('evaluation') or {}
    frozen = (ev.get('results') or [{}])[0]
    return {'frozen_rule': frozen.get('verdict'), 'exploratory': (ev.get('exploratory') or {}).get('verdict'),
            'evidence_origin': (data.get('evidence_origin') or {}).get('provider')}


def recover(root: Path, admission: Admission) -> list[str]:
    """Service start: no worker can outlive its service (parent-death signal), but verify and kill any
    survivor, then mark unfinished jobs interrupted. Reservations are kept (charges may have occurred)."""
    recovered = []
    for job_id in admission.active():
        for pid in os.listdir('/proc'):
            try:
                cmd = Path(f'/proc/{pid}/cmdline').read_bytes().split(b'\0')
            except OSError:
                continue
            if b'agent_readiness.hosted.paired' in cmd and job_id.encode() in cmd:
                try:
                    os.killpg(int(pid), signal.SIGKILL)
                except (ProcessLookupError, PermissionError):
                    pass
        job = admission.get(job_id)
        admission.transition(job_id, job['state'], 'interrupted')
        try:
            data = paired.load_job(root, job_id)
            for rep in data['reps']:
                if rep['state'] not in ('completed', 'failed'):
                    rep['state'] = 'incomplete'
            ironbark_runner.write(paired.job_path(root, job_id), data)
        except (OSError, ValueError):
            pass
        recovered.append(job_id)
    return recovered


def create_app(root: Path, admission: Admission, *, client_key: bytes, executor: Executor | None = None, trusted_proxies=(), static_dir: Path | None = None) -> FastAPI:
    if len(client_key) < 32:
        raise ValueError('client identity key must be at least 32 bytes')
    root = Path(root)
    proxies = {ipaddress.ip_address(p) for p in trusted_proxies}
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    inflight: set[str] = set()
    inflight_lock = threading.Lock()
    tasks = public_tasks()

    def enabled():
        return executor is not None and getattr(executor, 'available', False) is True

    @app.middleware('http')
    async def headers(request: Request, call_next):
        response = await call_next(request)
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'no-referrer'
        response.headers['Content-Security-Policy'] = "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'"
        if request.url.path.startswith('/api/'):
            response.headers['Cache-Control'] = 'no-store'
        return response

    def checked_job(job_id: str):
        if not JOB_ID.fullmatch(job_id):
            raise HTTPException(404, 'Evaluation not found')
        job = admission.get(job_id)
        if not job:
            raise HTTPException(404, 'Evaluation not found')
        return job

    def client_identity(request: Request) -> str:
        peer = request.client.host if request.client else ''
        if not peer:
            raise HTTPException(403, 'Client identity unavailable')
        try:
            addr = ipaddress.ip_address(peer)
        except ValueError:
            addr = peer                                   # opaque peer label (never a trusted proxy)
        if addr in proxies:
            # Only a configured reverse proxy may assert the client; take the address it appended.
            forwarded = [p.strip() for p in request.headers.get('x-forwarded-for', '').split(',') if p.strip()]
            try:
                addr = ipaddress.ip_address(forwarded[-1])
            except (IndexError, ValueError):
                raise HTTPException(403, 'Client identity unavailable')
        return hmac.new(client_key, str(addr).encode(), hashlib.sha256).hexdigest()

    def work(job_id: str):
        try:
            admission.transition(job_id, 'reserved', 'running')
            executor.run(job_id)
            job = paired.load_job(root, job_id)
            for rep in job['reps']:
                verified_export(root, rep['run_id'])       # complete only if every repetition is exportable
            admission.transition(job_id, 'running', 'completed')
        except (TimeoutError, subprocess.TimeoutExpired):
            job = admission.get(job_id)
            if job and job['state'] in ('reserved', 'running'):
                admission.transition(job_id, job['state'], 'timed_out' if job['state'] == 'running' else 'failed')
        except Exception:
            job = admission.get(job_id)
            if job and job['state'] in ('reserved', 'running'):
                admission.transition(job_id, job['state'], 'failed')
        finally:
            with inflight_lock:
                inflight.discard(job_id)

    @app.get('/api/ironbark/config')
    def config():
        totals = admission.totals()
        active = admission.active()
        from ..agent import ModelConfig
        return {'available': enabled(), 'mode': getattr(executor, 'mode', None) if enabled() else None,
                'repetitions': list(paired.REPETITIONS), 'model': ModelConfig().model, 'agent_profile': 'suite-v2-compat2',
                'tasks': tasks, 'remaining_repetitions': max(0, (totals['ceiling_microusd'] - totals['reserved_microusd']) // totals['per_repetition_microusd']),
                'active': active[0] if active else None}

    @app.get('/api/ironbark/jobs')
    def recent():
        out = []
        for j in admission.recent(20):
            try:
                data = paired.load_job(root, j['id'])
            except (OSError, ValueError):
                continue
            out.append({'id': j['id'], 'state': j['state'], 'repetitions': data['repetitions'], 'mode': data['mode'], 'created_at': data['created_at']})
        return out

    @app.post('/api/ironbark/jobs', status_code=202)
    def start(body: StartRequest, request: Request):
        if not enabled():
            raise HTTPException(503, 'Evaluations are currently unavailable')
        client = client_identity(request)
        job_id = 'eval-' + secrets.token_hex(16)
        try:
            admission.reserve(job_id, client, units=body.repetitions)
        except Refused as exc:
            raise HTTPException(429, str(exc)) from exc
        try:
            paired.new_job(root, job_id, body.repetitions, executor.mode)
            with inflight_lock:
                inflight.add(job_id)
            threading.Thread(target=work, args=(job_id,), daemon=True, name=job_id).start()
        except Exception as exc:
            with inflight_lock:
                inflight.discard(job_id)
            admission.transition(job_id, 'reserved', 'failed')
            raise HTTPException(503, 'Unable to start evaluation') from exc
        return {'id': job_id, 'state': 'reserved', 'repetitions': body.repetitions}

    @app.get('/api/ironbark/jobs/{job_id}')
    def status(job_id: str):
        held = checked_job(job_id)
        with inflight_lock:
            recovery_required = held['state'] in ('reserved', 'running') and job_id not in inflight
        try:
            job = paired.load_job(root, job_id)
        except (OSError, ValueError):
            job = {'reps': [], 'repetitions': None, 'mode': None, 'created_at': held['created'], 'started_at': None, 'finished_at': None}
        reps = [repetition_status(root, r) for r in job['reps']]
        if held['state'] in TERMINAL:
            for out, rep in zip(reps, job['reps']):
                if rep['state'] == 'completed':
                    try:
                        out['assessment'] = _assessment(verified_export(root, rep['run_id']))
                    except Exception:
                        out['state'] = 'unverified'
        return {'id': job_id, 'state': held['state'], 'recovery_required': recovery_required, 'mode': job['mode'], 'repetitions': job['repetitions'],
                'created_at': job['created_at'], 'started_at': job.get('started_at'), 'finished_at': job.get('finished_at'),
                'reps': reps, 'summary': summarize(reps)}

    @app.get('/api/ironbark/jobs/{job_id}/repetitions/{index}/export')
    def export(job_id: str, index: int):
        if checked_job(job_id)['state'] not in TERMINAL:
            raise HTTPException(409, 'Evaluation results are not available yet')
        try:
            rep = paired.load_job(root, job_id)['reps'][index - 1]
            if index < 1 or rep['state'] != 'completed':
                raise ValueError('repetition incomplete')
            return verified_export(root, rep['run_id'])
        except Exception as exc:
            raise HTTPException(409, 'Sanitized results are unavailable') from exc

    if static_dir is not None:
        from fastapi.staticfiles import StaticFiles
        app.mount('/', StaticFiles(directory=str(static_dir), html=True), name='studio')
    return app
