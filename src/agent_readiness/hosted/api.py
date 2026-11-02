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
import time
from pathlib import Path
from typing import Literal, Protocol

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict

from . import insights as insight_rules, paired, telemetry
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


DERIVED = 'derived'                 # disposable caches derived from run evidence; never authoritative, safe to delete (rebuilt on demand)
EXPORT_CACHE_VERSION = 'export-v3'  # v3: + model_provenance derived from the trial records; v2: spend.ceiling_usd is the ENFORCED ledger ceiling; older caches are no longer read
EVALUATION_ARMS = ('placebo', 'patched')   # the evaluation's own trials (Original, Modified); a fork's `baseline` trials are imported history
AGENT_PROFILE = 'suite-v2-compat2'         # the frozen profile new hosted evaluations run with (ironbark_runner.validate_manifest enforces the same name)


def _code_id(*files: Path) -> str:
    h = hashlib.sha256()
    for f in files:
        h.update(Path(f).read_bytes())
    return h.hexdigest()[:16]


def provenance_view(root: Path, run_id: str) -> dict:
    """Model and grader provenance of a finished repetition, derived read-only from its trial records and request traces (agent_readiness.provenance),
    cached under derived/model-provenance/ keyed by the deriving code."""
    from .. import provenance as P
    cached = derived_path(root, 'model-provenance', f'{run_id}.{_code_id(Path(P.__file__))}.json')
    if cached.is_file():
        try:
            return json.loads(cached.read_text())
        except ValueError:
            pass
    view = P.model_provenance(root / run_id, arms=EVALUATION_ARMS)
    view['arm_labels'] = {'placebo': 'Original', 'patched': 'Modified', 'baseline': 'historical baseline (imported; used only by the frozen comparison rule)'}
    ironbark_runner.write(cached, view)
    return view


def derived_path(root: Path, namespace: str, name: str) -> Path:
    if not re.fullmatch(r'[a-z0-9-]+', namespace) or not re.fullmatch(r'[A-Za-z0-9._-]+', name) or '..' in name:
        raise ValueError('invalid derived cache name')
    d = root / DERIVED / namespace
    d.mkdir(parents=True, exist_ok=True)
    return d / name


def verified_export(root: Path, run_id: str) -> dict:
    """The sanitized public export of a finished repetition, regenerated from the run and cached in the versioned derived namespace."""
    cached = derived_path(root, 'public-export', f'{run_id}.{EXPORT_CACHE_VERSION}.json')
    if cached.is_file():
        try:
            return json.loads(cached.read_text())
        except ValueError:
            pass
    data = exporter.public_demo(exporter.export_run(root / run_id))
    if not data['run']['complete'] or data['evaluation']['state'] != 'evaluated':
        raise ValueError('evaluation is incomplete')
    data['model_provenance'] = provenance_view(root, run_id)
    ironbark_runner.write(cached, data)
    return data


GRADING_V2_LABEL = ('Post-hoc rescore with grader v2 (accepts correct answers that add consistent detail). Not pre-registered: the official grades '
                    'and verdicts of this evaluation are grader v1.')


def grading_v2(root: Path, run_id: str) -> dict:
    """Labelled grader_v2 view of a finished repetition, derived read-only from its stored answers and cached under derived/grader-v2/ with the
    grading code's derivation id in the name (never inside the run; disposable and rebuildable). Shown only when the rescore reproduces every
    stored v1 grade and verdict; otherwise it is withheld, never approximated."""
    from ..grading import rescore as _r
    cached = derived_path(root, 'grader-v2', f'{run_id}.{_r.derivation_id()}.json')
    if cached.is_file():
        try:
            return json.loads(cached.read_text())
        except ValueError:
            pass
    doc = _r.rescore_run(root / run_id)
    view = {'label': GRADING_V2_LABEL, 'grader': doc['graders']['v2'], 'derivation_id': _r.derivation_id(), 'faithful': doc['faithful'], 'tasks': [], 'assessment': None}
    if doc['faithful']:
        aliases = {tid: i + 1 for i, tid in enumerate(sorted({r['task_id'] for r in doc['trials']}))}
        for r in doc['trials']:
            if r['arm'] in ('placebo', 'patched') and not r['void'] and r['v2']:
                v = r['v2']
                view['tasks'].append({'arm': 'Original' if r['arm'] == 'placebo' else 'Modified', 'task': aliases[r['task_id']],
                                      'outcome': 'evidence_supported_pass' if v['evidence_backed'] else 'strict_pass' if v['passed'] else 'not_passed', 'reasons': v['reasons']})
        comps = doc['comparisons']
        frozen = next(iter((comps.get('frozen') or {}).values()), None)
        view['assessment'] = {'frozen_rule': frozen and frozen['v2_post_hoc']['verdict'], 'exploratory': (comps.get('exploratory') or {}).get('v2_post_hoc')}
    ironbark_runner.write(cached, view)
    return view


def summarize_v2(reps: list[dict]) -> dict | None:
    """Per-arm grader_v2 totals over repetitions that have a faithful v2 view; None when none has."""
    views = [r['grading_v2'] for r in reps if (r.get('grading_v2') or {}).get('faithful')]
    if not views:
        return None
    out = {}
    for arm in ('Original', 'Modified'):
        rows = [t for v in views for t in v['tasks'] if t['arm'] == arm]
        out[arm] = {'completed': len(rows), 'evidence_supported_passes': sum(t['outcome'] == 'evidence_supported_pass' for t in rows),
                    'strict_passes': sum(t['outcome'] in ('evidence_supported_pass', 'strict_pass') for t in rows)}
    return {'label': GRADING_V2_LABEL, 'repetitions': len(views), **out}


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


ARM_KEYS = {'original': 'placebo', 'modified': 'patched'}
FRIENDLY = {'evaluation capacity is occupied': 'Another evaluation is already running. You can watch it live and start a new one when it finishes.',
            'rate limit exceeded': 'You started an evaluation a moment ago. Please wait a couple of minutes before starting another.',
            'hosted budget exhausted': 'The budget for new evaluations has been used up. Completed evaluations remain available.'}


def create_app(root: Path, admission: Admission, *, client_key: bytes, executor: Executor | None = None, trusted_proxies=(), static_dir: Path | None = None,
               operator_token: bytes | None = None, public_start: bool = True, unavailable_reason: str | None = None, mode: str | None = None) -> FastAPI:
    if len(client_key) < 32:
        raise ValueError('client identity key must be at least 32 bytes')
    root = Path(root)
    proxies = {ipaddress.ip_address(p) for p in trusted_proxies}
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    inflight: set[str] = set()
    inflight_lock = threading.Lock()
    tasks = public_tasks()
    cache: dict[str, dict] = {}                           # terminal-job derived views (immutable once terminal)
    if not public_start and not operator_token:
        executor = None                                   # operator-only access without a token: nobody can start
        unavailable_reason = unavailable_reason or 'missing_operator_token'

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
            cache.get('_', {}).pop('durations', None)          # refresh the measured duration estimate
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

    def is_operator(request: Request) -> bool:
        given = request.headers.get('authorization', '')
        return bool(operator_token) and given.startswith('Bearer ') and hmac.compare_digest(given[7:].strip().encode(), operator_token)

    @app.get('/api/health')
    def health():
        return {'status': 'ok', 'mode': mode, 'evaluations': 'enabled' if enabled() else 'disabled', 'reason': None if enabled() else (unavailable_reason or 'disabled'),
                'access': 'public' if public_start else 'operator', 'active': bool(admission.active())}

    FALLBACK_REPETITION_SECONDS = {'live': 560, 'rehearsal': 150}   # live: first genuine hosted run took 9 min 18 s

    def repetition_seconds():
        """Typical wall time of one paired repetition, measured from completed evaluations of this deployment."""
        key = 'durations'
        if key not in cache.get('_', {}):
            samples = []
            for j in admission.recent(50):
                if j['state'] != 'completed':
                    continue
                try:
                    data = paired.load_job(root, j['id'])
                    if data.get('started_at') and data.get('finished_at') and data.get('repetitions'):
                        samples.append((data['finished_at'] - data['started_at']) / data['repetitions'])
                except (OSError, ValueError):
                    continue
            cache.setdefault('_', {})[key] = samples
        samples = cache['_'][key]
        current_mode = getattr(executor, 'mode', None) or mode or 'live'
        if samples:
            return {'seconds': round(sum(samples) / len(samples)), 'basis': 'measured', 'samples': len(samples)}
        return {'seconds': FALLBACK_REPETITION_SECONDS.get(current_mode, 560), 'basis': 'first genuine run' if current_mode == 'live' else 'default', 'samples': 0}

    def worker_state():
        active = admission.active()
        if not enabled():
            return {'state': 'unavailable', 'job': None}
        if not active:
            return {'state': 'idle', 'job': None}
        job_id = active[0]
        try:
            data = paired.load_job(root, job_id)
        except (OSError, ValueError):
            return {'state': 'busy', 'job': job_id, 'started_at': None, 'finished_runs': 0, 'total_runs': None, 'estimated_remaining_seconds': None}
        reps = [repetition_status(root, r) for r in data['reps']]
        finished = sum(t['state'] in ('completed', 'failed') for r in reps for t in r['tasks'])
        total = 8 * data['repetitions']
        estimate = repetition_seconds()['seconds'] * data['repetitions']
        started = data.get('started_at')
        remaining = max(60, round(estimate - (time.time() - started))) if started else estimate
        return {'state': 'busy', 'job': job_id, 'started_at': started, 'repetitions': data['repetitions'], 'finished_runs': finished, 'total_runs': total,
                'estimated_remaining_seconds': remaining}

    def agent_settings():
        """The frozen profile new evaluations run with, read from the profile file (not restated here)."""
        try:
            from ..agent import profile
            from ..suite.core import canonical_hash
            p = profile(AGENT_PROFILE)
            return {'profile': AGENT_PROFILE, 'profile_file_sha256': canonical_hash(p), 'reasoning_effort': p.get('reasoning_effort'), 'max_completion_tokens': p.get('max_completion_tokens')}
        except Exception:
            return None

    @app.get('/api/ironbark/config')
    def config():
        totals = admission.totals()
        active = admission.active()
        from ..agent import ModelConfig
        return {'worker': worker_state(), 'repetition_duration': repetition_seconds(), 'available': enabled(), 'mode': getattr(executor, 'mode', None) if enabled() else None, 'access': 'public' if public_start else 'operator',
                'reason': None if enabled() else (unavailable_reason or 'disabled'),
                'repetitions': list(paired.REPETITIONS), 'model': ModelConfig().model, 'agent_profile': AGENT_PROFILE, 'agent_settings': agent_settings(),
                'tasks': tasks, 'remaining_repetitions': max(0, (totals['ceiling_microusd'] - totals['reserved_microusd']) // totals['per_repetition_microusd']),
                'active': active[0] if active else None}

    @app.get('/api/ironbark/jobs')
    def recent():
        out = []
        for j in admission.recent(30):
            try:
                data = paired.load_job(root, j['id'])
            except (OSError, ValueError):
                continue
            summary = None
            if j['state'] in TERMINAL:
                summary = status(j['id'])['summary']
            out.append({'id': j['id'], 'state': j['state'], 'repetitions': data['repetitions'], 'mode': data['mode'], 'created_at': data['created_at'],
                        'finished_at': data.get('finished_at'), 'completed_repetitions': sum(r['state'] == 'completed' for r in data['reps']), 'summary': summary})
        return out

    @app.post('/api/ironbark/jobs', status_code=202)
    def start(body: StartRequest, request: Request):
        if not enabled():
            raise HTTPException(503, 'Evaluations are currently unavailable')
        operator = is_operator(request)
        if not public_start and not operator:
            raise HTTPException(403, 'New evaluations are not open to the public yet')
        client = hmac.new(client_key, b'operator', hashlib.sha256).hexdigest() if operator else client_identity(request)
        job_id = 'eval-' + secrets.token_hex(16)
        try:
            admission.reserve(job_id, client, units=body.repetitions)
        except Refused as exc:
            raise HTTPException(429, FRIENDLY.get(str(exc), str(exc))) from exc
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
        if job_id in cache and 'status' in cache[job_id]:
            return cache[job_id]['status']
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
                        continue
                    try:
                        out['grading_v2'] = grading_v2(root, rep['run_id'])
                    except Exception:
                        out['grading_v2'] = None              # the official v1 results never depend on the rescore
                    try:
                        out['provenance'] = provenance_view(root, rep['run_id'])
                    except Exception:
                        out['provenance'] = None
        out = {'id': job_id, 'state': held['state'], 'recovery_required': recovery_required, 'mode': job['mode'], 'repetitions': job['repetitions'],
               'created_at': job['created_at'], 'started_at': job.get('started_at'), 'finished_at': job.get('finished_at'),
               'reps': reps, 'summary': summarize(reps), 'summary_v2': summarize_v2(reps)}
        if held['state'] in TERMINAL:
            cache.setdefault(job_id, {})['status'] = out
        return out

    def trial_location(job_id: str, index: int, arm: str, task: int):
        checked_job(job_id)
        if arm not in ARM_KEYS or task not in (1, 2, 3, 4):
            raise HTTPException(404, 'Trial not found')
        try:
            rep = paired.load_job(root, job_id)['reps'][index - 1]
            if index < 1:
                raise IndexError
            operator = json.loads((root / (rep['run_id'] + '.json')).read_text())
            task_id = sorted(t['task_id'] for t in operator['tasks'])[task - 1]
        except (OSError, ValueError, IndexError, KeyError):
            raise HTTPException(404, 'Trial not found') from None
        return rep, operator, task_id, telemetry.attempt_dir(root / rep['run_id'], ARM_KEYS[arm], task_id)

    @app.get('/api/ironbark/jobs/{job_id}/repetitions/{index}/trials/{arm}/{task}')
    def trial(job_id: str, index: int, arm: str, task: int):
        rep, operator, task_id, attempt = trial_location(job_id, index, arm, task)
        state = next((r['state'] for r in ironbark_runner.progress(root, operator) if r['task_id'] == task_id and r['arm'].lower() == arm), 'pending')
        base = {'repetition': index, 'arm': arm, 'task': task, 'state': state, 'mode': paired.load_job(root, job_id)['mode'],
                'question': next((t['question'] for t in tasks if t['task'] == task), None)}
        if attempt is None:
            return {**base, 'steps': [], 'current': None, 'errors': []}
        return {**base, **telemetry.timeline(attempt)}

    @app.get('/api/ironbark/jobs/{job_id}/repetitions/{index}/trials/{arm}/{task}/screenshots/{name}')
    def screenshot(job_id: str, index: int, arm: str, task: int, name: str):
        if not telemetry.SCREENSHOT.fullmatch(name):
            raise HTTPException(404, 'Screenshot not found')
        attempt = trial_location(job_id, index, arm, task)[3]
        if attempt is None or not (attempt / name).is_file():
            raise HTTPException(404, 'Screenshot not found')
        return FileResponse(attempt / name, media_type='image/png', headers={'Cache-Control': 'public, max-age=86400, immutable'})

    @app.get('/api/ironbark/jobs/{job_id}/live')
    def live(job_id: str):
        """The trial the agent is executing right now (or the most recently finished one)."""
        held = checked_job(job_id)
        try:
            job = paired.load_job(root, job_id)
        except (OSError, ValueError):
            return {'active': False, 'trial': None}
        latest = None
        for rep in job['reps']:
            try:
                operator = json.loads((root / (rep['run_id'] + '.json')).read_text())
            except (OSError, ValueError):
                continue
            order = sorted(t['task_id'] for t in operator['tasks'])
            for row in ironbark_runner.progress(root, operator):
                arm = row['arm'].lower()
                attempt = telemetry.attempt_dir(root / rep['run_id'], ARM_KEYS[arm], row['task_id'])
                if attempt is None:
                    continue
                stamp = (attempt / 'trace.jsonl').stat().st_mtime
                if latest is None or stamp > latest[0]:
                    latest = (stamp, rep['index'], arm, order.index(row['task_id']) + 1, row['state'], attempt)
        if latest is None:
            return {'active': held['state'] in ('reserved', 'running'), 'trial': None}
        _, index, arm, task, state, attempt = latest
        return {'active': held['state'] in ('reserved', 'running'),
                'trial': {'repetition': index, 'arm': arm, 'task': task, 'state': state, 'question': next((t['question'] for t in tasks if t['task'] == task), None),
                          **telemetry.timeline(attempt)}}

    @app.get('/api/ironbark/jobs/{job_id}/insights')
    def job_insights(job_id: str):
        held = checked_job(job_id)
        if job_id in cache and 'insights' in cache[job_id]:
            return cache[job_id]['insights']
        try:
            job = paired.load_job(root, job_id)
        except (OSError, ValueError):
            raise HTTPException(404, 'Evaluation not found') from None
        result = {**insight_rules.build(insight_rules.collect(root, job['reps'])), 'mode': job['mode'], 'final': held['state'] in TERMINAL}
        if held['state'] in TERMINAL:
            cache.setdefault(job_id, {})['insights'] = result
        return result

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
