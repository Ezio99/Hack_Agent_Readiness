"""Hosted evaluation API.

The public request body is ``{"repetitions": 1 | 3 | 5}`` and nothing else: no
URL, task, model, browser command or spending field exists. The executor is
installed by the deployment (``hosted.serve``): the Stage B engine
(``hosted/stageb.py``), which evaluates the owner-ARMED frozen suite (selected
server-side) with the lifecycle runner. Without an executor, or without an
armed evaluation, the API refuses to start before reserving budget. Historical
jobs of the retired paired Ironbark engine stay viewable read-only.

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

from . import insights as insight_rules, paired, stageb, telemetry
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
            if (b'agent_readiness.hosted.paired' in cmd or b'agent_readiness.lifecycle.jobs' in cmd) and job_id.encode() in cmd:
                try:
                    os.killpg(int(pid), signal.SIGKILL)
                except (ProcessLookupError, PermissionError):
                    pass
        job = admission.get(job_id)
        admission.transition(job_id, job['state'], 'interrupted')
        if stageb.is_job(root / 'stageb', job_id):         # a Stage B evaluation: interrupted for good (never re-run; its launch number is used)
            from ..lifecycle import jobs as LJ
            try:
                LJ.update_job(root / 'stageb', job_id, state='interrupted', error='the service restarted while this evaluation was running; it is never re-run')
            except (OSError, ValueError):
                pass
            recovered.append(job_id)
            continue
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
            'hosted budget exhausted': 'The budget for new evaluations has been used up. Completed evaluations remain available.',
            'global hosted cap reached': 'The service-wide spending cap does not cover another run.'}
BUDGET_EXHAUSTED = 'The A$20 evaluation budget has been used. Completed evaluations, their results and traces remain available.'

# One launch flow (2026-11): any valid evaluation access code (sent once per launch as a Bearer header from the page's memory; never stored, logged or
# returned) launches the same evaluation. A per-click Idempotency-Key makes a double-click or retry return the run it already started.
IDEMPOTENCY = re.compile(r'[A-Za-z0-9_-]{16,64}')


def create_app(root: Path, admission: Admission, *, client_key: bytes, executor: Executor | None = None, trusted_proxies=(), static_dir: Path | None = None,
               operator_token: bytes | None = None, public_start: bool = True, unavailable_reason: str | None = None, mode: str | None = None,
               lifecycle=None, judge_token: bytes | None = None) -> FastAPI:
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
    # M9: the judge access code is a SEPARATE secret that authorises exactly one thing: POST /api/ironbark/jobs (launching the evaluation the owner
    # armed). It is never accepted anywhere else (not by the lifecycle routes, which only know the operator check), never returned, never logged.
    if judge_token is not None and (len(judge_token) < 24 or (operator_token is not None and hmac.compare_digest(judge_token, operator_token))):
        judge_token = None                                # too short, or identical to the operator token: judge access stays off

    def enabled():
        return executor is not None and getattr(executor, 'available', False) is True

    sb_root = root / 'stageb'
    stage_b = getattr(executor, 'engine', None) == stageb.ENGINE

    def is_sb(job_id: str) -> bool:
        return stageb.is_job(sb_root, job_id)

    def current_tasks():
        if stage_b:
            try:
                return executor.configuration()['tasks']
            except Exception:
                return []
        return tasks

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
            if is_sb(job_id):
                if lifecycle is None:
                    raise RuntimeError('the lifecycle service is required to project a Stage B evaluation')
                # M9: the run completed (the worker verified every planned trial ran). Publication is a separate, fail-closed check: a report that
                # does not pass the leak audit is withheld (reported as such by the status route), but no longer turns the run into "failed".
                try:
                    lifecycle.evaluation(job_id)
                except Exception as exc:
                    if getattr(exc, 'code', None) == 'not_ready':
                        raise                                           # no results at all: an execution failure, not a publication one
                    print(f'hosted service: evaluation {job_id} completed; its report is not published ({getattr(exc, "code", None) or type(exc).__name__})', flush=True)
            else:
                job = paired.load_job(root, job_id)
                for rep in job['reps']:
                    verified_export(root, rep['run_id'])   # complete only if every repetition is exportable
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
            if is_sb(job_id):                                   # actual-cost settlement: only a verified, fully settled ledger releases capacity
                from . import settlement
                settlement.settle_automatic(admission, root, job_id)

    def bearer(request: Request) -> bytes | None:
        given = request.headers.get('authorization', '')
        return given[7:].strip().encode() if given.startswith('Bearer ') else None

    launch_db_path = root / 'launch-requests.sqlite'
    launch_lock = threading.Lock()
    code_failures: dict[str, list[float]] = {}

    def launch_db():
        import sqlite3
        db = sqlite3.connect(launch_db_path, timeout=10, isolation_level=None)
        db.execute('CREATE TABLE IF NOT EXISTS launch_requests (key_hash TEXT PRIMARY KEY, job_id TEXT NOT NULL, at REAL NOT NULL)')
        return db

    def is_operator(request: Request) -> bool:
        given = bearer(request)
        return bool(operator_token) and given is not None and hmac.compare_digest(given, operator_token)

    def is_judge(request: Request) -> bool:
        """Launch-only: consulted by `start` alone."""
        given = bearer(request)
        return bool(judge_token) and given is not None and hmac.compare_digest(given, judge_token)

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
        if is_sb(job_id):
            try:
                st = stageb.job_status(sb_root, job_id, 'running', recovery_required=False)
                finished = sum(t['state'] in ('completed', 'failed') for r in st['reps'] for t in r['tasks'])
                total = sum(len(r['tasks']) for r in st['reps']) or None
                per_trial = 50                                                    # M7: mean 52 s of agent time per trial
                return {'state': 'busy', 'job': job_id, 'started_at': st['started_at'], 'repetitions': st['repetitions'], 'finished_runs': finished,
                        'total_runs': total, 'estimated_remaining_seconds': max(60, per_trial * ((total or 0) - finished)) if total else None}
            except (OSError, ValueError, KeyError):
                return {'state': 'busy', 'job': job_id, 'started_at': None, 'finished_runs': 0, 'total_runs': None, 'estimated_remaining_seconds': None}
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

    LAUNCH_DETAIL = {
        'service_unavailable': 'The evaluation service is unavailable; recorded evaluations remain available.',
        'not_armed': 'No live evaluation is open at the moment.',
        'arming_mode_mismatch': "The authorised evaluation does not match this service's mode.",
        'arming_invalid': 'The authorised evaluation no longer verifies; the owner must authorise again.',
        'launches_exhausted': 'All live runs available for this demonstration have been used.',
        'arming_total_exhausted': "The authorisation's total reservation has been used.",
        'budget_exhausted': 'The A$20 evaluation budget has been used. Completed evaluations, their results and traces remain available.',
    }

    def launch_state(cfg: dict, active: list) -> dict:
        """Whether a NEW launch is authorised now, from the same server-side facts the launch path enforces (StageBExecutor.admit and the
        hosted admission): the service is enabled, an arming of this mode verifies, it has a launch left, and an armed option's reservation
        fits both the arming's remaining total and the hosted ceiling (`arming.summary`). Display only: every launch is still checked by
        `admit`. `authorized` excludes a running evaluation (the single slot, reported separately); `ready` = authorised and the slot is free."""
        reason = None
        ev = cfg.get('evaluation') or {}
        if not enabled():
            reason = 'service_unavailable'
        elif not cfg.get('armed'):
            reason = cfg.get('reason') or 'not_armed'
        elif ev.get('launches') is not None and ev['launches'].get('left', 0) <= 0:      # the shared budget's evaluation has no launch count
            reason = 'launches_exhausted'
        elif not any(o.get('available') for o in ev.get('options') or []):
            reason = 'budget_exhausted' if any(o.get('fits_hosted_ceiling') is False for o in ev.get('options') or []) else 'arming_total_exhausted'
        authorized = reason is None
        return {'authorized': authorized, 'ready': authorized and not active, 'reason': reason,
                'detail': None if authorized else LAUNCH_DETAIL.get(reason, 'No launch is authorised.'),
                'launches_left': (ev.get('launches') or {}).get('left') if ev else None,
                'covers': ((ev.get('options') or [{}])[0].get('covered')) if ev else None}

    programme_cache: dict = {}

    def programme_block() -> dict | None:
        """The A$50 programme (legacy scope) for display: recorded actual costs (the programme ledger shipped with this release, matched by job
        identity) + verified legacy hosted costs not yet recorded + held exposure + the hosted ceiling's available amount. Cached for 30 s."""
        path = Path(os.environ.get('AR_PROGRAMME_LEDGER') or '/app/budget/programme-ledger.json')
        if not path.is_file():
            path = Path(__file__).resolve().parents[3] / 'collaboration' / 'budget' / 'programme-ledger.json'
        if not path.is_file():
            return None
        now = time.monotonic()
        if programme_cache.get('at', -1e9) > now - 30:
            return programme_cache['value']
        try:
            from . import programme as PG, settlement as ST
            doc = json.loads(path.read_text())
            v = PG.view_from_audit(doc, ST.audit(admission, root))
            entries = doc.get('entries') or []
            value = {'spent_usd': v['spend_to_date_usd'], 'spent_aud': v['spend_to_date_aud'], 'recorded_usd': v['known_usd'],
                     'not_recorded': [{'job': m['job'], 'usd': m['usd']} for m in v['not_in_ledger']], 'held_usd': v['unverified_exposure_usd'],
                     'ceiling_available_usd': v['hosted_available_usd'], 'worst_case_usd': v['worst_case_usd'], 'worst_case_aud': v['worst_case_aud'],
                     'limit_aud': v['limit_aud'], 'rate_aud_per_usd': v['rate_aud_per_usd'], 'within_limit': v['within_limit'], 'ledger_entries': len(entries),
                     'ledger_problems': len(v['problems']), 'basis': 'actual verified costs (programme ledger, then verified hosted runs not yet recorded); a reservation is never spend'}
        except Exception as exc:                                                      # display only; never breaks the config route
            value = {'error': type(exc).__name__}
        programme_cache.update(at=now, value=value)
        return value

    def spending_view(totals: dict, ev: dict | None) -> dict:
        """Three separate things, never mixed: the hosted CEILING (a safety cap for programme/legacy jobs), each separately allocated BUDGET
        (A$, its own jobs and allocations only), and the A$50 PROGRAMME (actual expenditure). Top-level keys keep their earlier meaning: the
        ceiling's scope."""
        out = {k: totals[f'{k}_microusd'] / 1e6 for k in ('ceiling', 'settled', 'outstanding', 'committed', 'available', 'released')}
        out |= {'settled_jobs': totals['settled_jobs'], 'unsettled_jobs': totals['unsettled_jobs'], 'scope': 'programme (legacy) jobs under the hosted ceiling',
                'basis': 'calculated from provider-reported usage in each job\'s durable request ledger; not a bill'}
        gcap = totals.get('global_cap_microusd')
        out['global'] = None if gcap is None else {'cap_usd': gcap / 1e6, 'committed_usd': totals['all_committed_microusd'] / 1e6,
                                                   'available_usd': totals['global_available_microusd'] / 1e6}
        out['budgets'] = [{'id': b['budget'], 'limit_aud': b['limit_micro_aud'] / 1e6, 'rate_aud_per_usd': b['rate_num'] / b['rate_den'],
                           'spent_aud': b['spent_micro_aud'] / 1e6, 'outstanding_aud': b['outstanding_micro_aud'] / 1e6,
                           'available_aud': b['available_micro_aud'] / 1e6, 'spent_usd': b['spent_microusd'] / 1e6, 'outstanding_usd': b['outstanding_microusd'] / 1e6,
                           'available_usd': b['available_microusd'] / 1e6, 'jobs': b['jobs'], 'settled_jobs': b['settled_jobs'], 'allocations': b['allocations'],
                           'open_allocations': b['open_allocations']} for b in totals.get('budgets') or []]
        out['charged_to'] = admission.charge_scope()                                  # the shared budget while one is open (None = the hosted ceiling)
        out['programme'] = programme_block()
        return out

    @app.get('/api/ironbark/config')
    def config():
        totals = admission.totals()
        active = admission.active()
        from ..agent import ModelConfig
        if stage_b:
            cfg = executor.configuration()
            ev = cfg.get('evaluation') or {}
            left = (ev.get('launches') or {}).get('left', 0) if ev.get('launches') is not None else ((ev.get('capacity') or {}).get('launches_affordable') or 0)
            launch = launch_state(cfg, active)
            return {'engine': stageb.ENGINE, 'worker': worker_state(), 'repetition_duration': {'seconds': 75 * max(1, len(cfg['tasks']) * 2), 'basis': 'paid runs: mean agent time plus browser start per trial', 'samples': 0},
                    'service': {'state': 'operational' if enabled() else 'unavailable', 'reason': None if enabled() else (unavailable_reason or 'disabled')},
                    'launch': launch,
                    'available': launch['authorized'], 'mode': getattr(executor, 'mode', None) if enabled() else None, 'access': 'public' if public_start else 'operator',
                    'judge_access': bool(judge_token) and not public_start,
                    'reason': None if launch['authorized'] else launch['reason'],
                    'repetitions': cfg['repetitions'], 'model': (ev.get('agent') or {}).get('model') or ModelConfig().model, 'agent_profile': (ev.get('agent') or {}).get('profile') or AGENT_PROFILE,
                    'agent_settings': ev.get('agent'), 'tasks': cfg['tasks'], 'evaluation': ev or None, 'remaining_repetitions': left,
                    'ceiling': {'ceiling_usd': totals['ceiling_microusd'] / 1e6, 'reserved_usd': totals['reserved_microusd'] / 1e6},
                    'spending': spending_view(totals, ev),
                    'active': active[0] if active else None}
        return {'worker': worker_state(), 'repetition_duration': repetition_seconds(), 'available': enabled(), 'mode': getattr(executor, 'mode', None) if enabled() else None, 'access': 'public' if public_start else 'operator',
                'reason': None if enabled() else (unavailable_reason or 'disabled'),
                'repetitions': list(paired.REPETITIONS), 'model': ModelConfig().model, 'agent_profile': AGENT_PROFILE, 'agent_settings': agent_settings(),
                'tasks': tasks, 'remaining_repetitions': max(0, (totals['ceiling_microusd'] - totals['reserved_microusd']) // totals['per_repetition_microusd']),
                'active': active[0] if active and active[0].startswith('eval-') else None}

    @app.get('/api/ironbark/jobs')
    def recent():
        out = []
        for j in admission.recent(30):
            if is_sb(j['id']):
                try:
                    st = status(j['id'])
                except Exception:
                    continue
                out.append({'id': j['id'], 'engine': stageb.ENGINE, 'state': j['state'], 'execution_state': st['execution']['state'],
                            'runs_per_repetition': (st.get('tasks_planned') or 0) // max(1, st['repetitions'] or 1) or None,
                            'report_state': st['report_status']['state'], 'repetitions': st['repetitions'], 'mode': st['mode'], 'created_at': st['created_at'],
                            'finished_at': st.get('finished_at'), 'completed_repetitions': sum(r['state'] == 'completed' for r in st['reps']),
                            'summary': st['summary'] if j['state'] in TERMINAL else None, 'arm_display': st.get('arm_display'),
                            'cost_usd': (lambda x: x['settled_microusd'] / 1e6 if x else None)(admission.settlement(j['id'])),
                            'reserved_usd': j['reserved_microusd'] / 1e6, 'budget': admission.job_budget(j['id'])})
                continue
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
        who = client_identity(request)
        operator = is_operator(request)
        judge = not operator and is_judge(request)
        if not public_start and not (operator or judge):
            # invalid codes only: a valid code is never refused by this limiter
            now = time.time()
            recent = [t for t in code_failures.get(who, []) if t > now - 600]
            if bearer(request) is not None:
                code_failures[who] = recent + [now]
            if len(recent) >= 10:
                raise HTTPException(429, 'Too many attempts with an invalid access code; please try again in a few minutes')
            raise HTTPException(403, 'Starting a live evaluation needs a valid access code' if judge_token else 'New evaluations are not open to the public yet')
        # the operator is one client; each code holder is identified by address, so the per-client rate limit applies to each separately
        client = hmac.new(client_key, b'operator', hashlib.sha256).hexdigest() if operator else who
        job_id = 'eval-' + secrets.token_hex(16)
        if not stage_b:                                    # the paired Ironbark engine is retired; only the Stage B executor can launch
            raise HTTPException(503, 'Evaluations are currently unavailable')
        key = request.headers.get('idempotency-key')
        if key is not None and not IDEMPOTENCY.fullmatch(key):
            raise HTTPException(422, 'Invalid Idempotency-Key')
        # a double-click or a retry of the same launch returns the job it already started (keyed per caller; never a second reservation)
        key_hash = hashlib.sha256(f'{client}:{key}'.encode()).hexdigest() if key else None
        from ..lifecycle.arming import ArmingRefused
        with launch_lock:
            if key_hash:
                with launch_db() as db:
                    row = db.execute('SELECT job_id FROM launch_requests WHERE key_hash=?', (key_hash,)).fetchone()
                if row:
                    held = admission.get(row[0])
                    return {'id': row[0], 'state': held['state'] if held else 'unknown', 'repetitions': body.repetitions, 'duplicate': True}
            try:
                # ONE flow for every valid code: the shared budget's evaluation while it is open (no launch count), else the owner's arming
                path = executor.launch_path() if hasattr(executor, 'launch_path') else 'arming'
                out = executor.admit(job_id, client, body.repetitions, **({'charge': 'budget'} if path == 'budget' else {}))
            except Refused as exc:
                msg = str(exc)
                if msg == 'evaluation capacity is occupied':      # not a refusal of the code or the budget: one evaluation runs at a time
                    active = admission.active()
                    raise HTTPException(409, f"An evaluation is already running{' (' + active[0][:13] + ')' if active else ''}. "
                                             'You can watch it live; start yours when it finishes.') from exc
                raise HTTPException(429, BUDGET_EXHAUSTED if msg.startswith('budget ') else FRIENDLY.get(msg, msg)) from exc
            except ArmingRefused as exc:
                raise HTTPException(exc.status, exc.detail) from exc
            except ValueError as exc:
                raise HTTPException(503, 'Unable to start evaluation') from exc
            if key_hash:
                with launch_db() as db:
                    db.execute('INSERT OR IGNORE INTO launch_requests VALUES (?,?,?)', (key_hash, job_id, time.time()))
        try:
            with inflight_lock:
                inflight.add(job_id)
            threading.Thread(target=work, args=(job_id,), daemon=True, name=job_id).start()
        except Exception as exc:
            with inflight_lock:
                inflight.discard(job_id)
            admission.transition(job_id, 'reserved', 'failed')
            raise HTTPException(503, 'Unable to start evaluation') from exc
        return out

    def report_publication(job_id: str, held_state: str) -> dict:
        """Whether a Stage B job's readiness report may be published: the lifecycle service's own build + leak audit (cached once it passes)."""
        if held_state in ('reserved', 'running'):
            return {'state': 'pending'}
        if lifecycle is None:
            return {'state': 'unavailable', 'detail': 'the lifecycle service is not configured'}
        try:
            lifecycle.evaluation(job_id)
            return {'state': 'available'}
        except Exception as exc:
            code = getattr(exc, 'code', None)
            if code == 'withheld':
                return {'state': 'withheld', 'detail': 'the report did not pass the publication leak audit and is withheld (fail-closed)'}
            return {'state': 'unavailable', 'detail': getattr(exc, 'detail', None) or 'the report could not be built'}

    def accounting(job_id: str, held: dict) -> dict:
        """Where the run's cost is accounted and what it costs: its reservation until settled, then its verified actual cost (never cached)."""
        st = admission.settlement(job_id)
        return {'reserved_usd': held['reserved_microusd'] / 1e6, 'cost_usd': st['settled_microusd'] / 1e6 if st else None, 'settled': st is not None,
                'budget': admission.job_budget(job_id)}

    @app.get('/api/ironbark/jobs/{job_id}')
    def status(job_id: str):
        held = checked_job(job_id)
        if is_sb(job_id):
            return {**sb_status(job_id, held), 'accounting': accounting(job_id, held)}
        return legacy_status(job_id, held)

    def sb_status(job_id: str, held: dict):
        if job_id in cache and 'status' in cache[job_id]:
            return cache[job_id]['status']
        with inflight_lock:
            recovery_required = held['state'] in ('reserved', 'running') and job_id not in inflight
        if is_sb(job_id):
            v2, grades = None, None
            publication = report_publication(job_id, held['state'])
            if publication['state'] == 'available':
                try:
                    ev = lifecycle.evaluation(job_id)
                    ts = ev['dimensions']['task_success']['variants']
                    names = [v['name'] for v in ev['manifest']['variants']] or list(ts)
                    lab = {names[0]: 'Original', names[1]: 'Modified'} if len(names) == 2 else {}
                    # the report's grades per agent run, so the workspace grid reads like the report: correct (v2, else v1) and exact match (v1)
                    grades = {(lab[t['variant']], t['task']): {'correct': bool((t['grades']['v2'] or t['grades']['v1'])['passed']),
                                                               'exact_match': bool(t['grades']['v1']['passed'])}
                              for t in ev['trials'] if t['variant'] in lab}
                    v2 = {'label': GRADING_V2_LABEL, 'repetitions': None,
                          **{lab[v]: {'completed': x['trials'], 'evidence_supported_passes': x['v2_evidence_backed'], 'strict_passes': x['v2_passed']} for v, x in ts.items() if v in lab}}
                except Exception:
                    v2 = None
            out = stageb.job_status(sb_root, job_id, held['state'], recovery_required=recovery_required, v2=v2, publication=publication, grades=grades)
            if held['state'] in TERMINAL:
                cache.setdefault(job_id, {})['status'] = out
            return out

    def legacy_status(job_id: str, held: dict):
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
        if is_sb(job_id):
            name = stageb.trial_name(sb_root, job_id, index, arm, task) if arm in ARM_KEYS else None
            if name is None:
                raise HTTPException(404, 'Trial not found')
            return None, None, name, stageb.attempt_dir(sb_root, job_id, name)
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
        if is_sb(job_id):
            st = stageb.job_status(sb_root, job_id, checked_job(job_id)['state'], recovery_required=False)
            row = next((t for r in st['reps'] if r['index'] == index for t in r['tasks'] if t['arm'].lower() == arm and t['task'] == task), None)
            base = {'repetition': index, 'arm': arm, 'task': task, 'state': row['state'] if row else 'pending', 'mode': st['mode'], 'trial': task_id,
                    'question': next((t['question'] for t in current_tasks() if t['task'] == task), None)}
            if attempt is None:
                return {**base, 'steps': [], 'current': None, 'errors': []}
            return {**base, **stageb.timeline(sb_root, job_id, attempt)}
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
        if is_sb(job_id):
            return stageb.live(sb_root, job_id, held['state'], current_tasks())
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
        if is_sb(job_id):
            raise HTTPException(409, 'Stage B evaluations report their diagnostics in the readiness report')
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
        if is_sb(job_id):
            try:
                return lifecycle.evaluation(job_id)                   # the audited public evaluation document (same as the report)
            except Exception as exc:
                raise HTTPException(409, 'Sanitized results are unavailable') from exc
        try:
            rep = paired.load_job(root, job_id)['reps'][index - 1]
            if index < 1 or rep['state'] != 'completed':
                raise ValueError('repetition incomplete')
            return verified_export(root, rep['run_id'])
        except Exception as exc:
            raise HTTPException(409, 'Sanitized results are unavailable') from exc

    if lifecycle is not None:
        from ..lifecycle.api import register
        register(app, lifecycle, is_operator=is_operator)

    if static_dir is not None:
        from fastapi.staticfiles import StaticFiles
        app.mount('/', StaticFiles(directory=str(static_dir), html=True), name='studio')
    return app
