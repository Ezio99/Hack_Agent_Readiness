"""Hosted batches of the existing Ironbark paired experiment.

A hosted evaluation is ``eval-<hex>``: 1, 3 or 5 *repetitions*, each a fresh
``paired-<hex>`` fork run through the unchanged local driver
(``ironbark_runner.prepare`` + ``run_worker`` -> ``abtest.drive``): four frozen
tasks on Original and on Modified, freshly graded and compared.

:class:`WorkerExecutor` runs in the API process. It launches one worker
subprocess per evaluation from the long-lived job thread (so the worker's
parent-death signal is tied to that thread), enforces a hard timeout and kills
the worker's process group on timeout. :func:`run_job` runs inside the worker.

Modes:

* ``live``: Meta Muse Spark through the existing approval-gated driver and
  spend ledger. Chromium must run in the network jail.
* ``rehearsal``: the same pipeline, jailed Chromium and real browser-use agent,
  but the scripted mock model; the worker refuses every non-loopback socket,
  so no provider can be contacted. Results are labelled as scripted (``fixture-evidence``,
  so the exporter never measures an effect), and the control-integrity check compares
  every key except model/mode, which a scripted trial cannot share with the real baseline.
"""
from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
import uuid
from decimal import Decimal
from pathlib import Path

from .admission import Admission
from ..live import ironbark_runner
from ..suite.core import canonical_hash

REPETITIONS = (1, 3, 5)
MODES = ('live', 'rehearsal')
ARM_CAPS = {'placebo_arm': 0.80, 'patched_arm': 0.80}      # the reviewed local proposal; one repetition reserves US$1.65 (caps + one request bound)
REP_TIMEOUT = ironbark_runner.TIMEOUT


def caps_microusd(caps: dict) -> int:
    """Combined arm caps of one repetition: what the manifest and the spend gate enforce on reserved amounts."""
    total = sum(Decimal(str(v)) for v in ironbark_runner.caps_checked(caps).values()) * 1_000_000
    if total != total.to_integral_value():
        raise ValueError('arm caps must be whole microdollars')
    return int(total)


def per_repetition_microusd(caps: dict) -> int:
    """Hosted reservation per repetition: the combined caps plus one per-request bound, because the
    spend gate lets at most one request settle above its (estimated) reservation before it closes."""
    from ..spend_gate import PER_REQUEST_CAP_USD
    return caps_microusd(caps) + int(Decimal(str(PER_REQUEST_CAP_USD)) * 1_000_000)


def job_path(root: Path, job_id: str) -> Path:
    return Path(root) / (job_id + '.job.json')


def new_job(root: Path, job_id: str, repetitions: int, mode: str) -> dict:
    if repetitions not in REPETITIONS or mode not in MODES:
        raise ValueError('unsupported evaluation request')
    job = {'id': job_id, 'mode': mode, 'repetitions': repetitions, 'created_at': time.time(), 'started_at': None, 'finished_at': None,
           'reps': [{'index': i + 1, 'run_id': 'paired-' + uuid.uuid4().hex, 'state': 'pending'} for i in range(repetitions)]}
    ironbark_runner.write(job_path(root, job_id), job)
    return job


def load_job(root: Path, job_id: str) -> dict:
    job = json.loads(job_path(root, job_id).read_text())
    if job.get('id') != job_id:
        raise ValueError('job identity mismatch')
    return job


# --- inside the worker subprocess ---------------------------------------------------------------------------

def _loopback_only_sockets():
    """Rehearsal: refuse any IP connection that is not loopback, at the socket layer."""
    import ipaddress
    import socket
    real = socket.socket

    def check(address):
        host = address[0] if isinstance(address, tuple) else None
        if host is not None and not ipaddress.ip_address(host).is_loopback:
            raise PermissionError('rehearsal mode: non-loopback network access refused')

    class Guarded(real):
        def connect(self, address):
            check(address)
            return super().connect(address)

        def connect_ex(self, address):
            check(address)
            return super().connect_ex(address)
    socket.socket = Guarded
    import socket as _s
    _orig_gai = _s.getaddrinfo

    def gai(host, *a, **k):
        if host not in (None, 'localhost', '127.0.0.1', '::1'):
            raise PermissionError('rehearsal mode: name resolution refused')
        return _orig_gai(host, *a, **k)
    _s.getaddrinfo = gai


def _rehearsal_patches():
    from ..investigate.trials import stage
    _loopback_only_sockets()
    stage.preflight = lambda cfg, allow: None                 # no key is read
    real = stage.run_trial

    def scripted(*args, **kwargs):
        kwargs.update(provider='mock', api_key=None)
        return real(*args, **kwargs)
    stage.run_trial = scripted
    # A scripted trial can never match the real-model baseline's model/mode. For rehearsal only, compare
    # every OTHER control key (profile, hashes, schemas, snapshot, limits); stored records are unchanged.
    from ..investigate.evaluate import stage as evaluation
    strict = evaluation._check_control

    def control(run, st, rec):
        base = run.artifact(f"trials/baseline-{st['task']['task_id']}-r1")['trial']
        view = {**rec, 'trial': {**rec.get('trial', {}), 'model': base.get('model'), 'mode': base.get('mode')}}
        return strict(run, st, view)
    evaluation._check_control = control


def _load_key_file():
    path = os.environ.pop('META_MODEL_API_KEY_FILE', None)
    if path and not os.environ.get('META_MODEL_API_KEY'):
        value = Path(path).read_text().strip()
        if value:
            os.environ['META_MODEL_API_KEY'] = value          # set after exec: not in /proc/<pid>/environ


def run_job(root: Path, job_id: str, admission: Admission, *, mode: str, caps: dict = ARM_CAPS, before_rep=None) -> None:
    """Run every repetition of ``job_id`` sequentially. Raises if any repetition does not finish."""
    root = Path(root)
    job = load_job(root, job_id)
    held = admission.get(job_id)
    if job['mode'] != mode or not held or held['state'] != 'running':
        raise ValueError('job does not hold a running reservation for this mode')
    if per_repetition_microusd(caps) * job['repetitions'] != held['reserved_microusd']:
        raise ValueError('reservation does not match the paired arm caps')
    for rep in job['reps']:
        rep['state'] = 'preparing'
        ironbark_runner.write(job_path(root, job_id), job)
        try:
            if before_rep is not None:
                before_rep(rep)
            prepared = ironbark_runner.prepare(root, dict(caps), job_id=rep['run_id'])
            if mode == 'rehearsal':
                # Provenance: the exporter labels this run scripted; it can never be shown as model evidence.
                from ..investigate.run import InvestigationRun
                InvestigationRun(root / rep['run_id']).write_artifact('fixture-evidence', {'synthetic': True, 'kind': 'hosted-rehearsal-scripted-model'})
            manifest = prepared['manifest']
            ironbark_runner.validate_manifest(manifest, caps)
            combined = Decimal(str(manifest['caps_usd']['post_trials_combined'])) * 1_000_000
            if combined != caps_microusd(caps) or canonical_hash(manifest) != prepared['manifest_sha256']:
                raise ValueError('prepared manifest does not match the reservation')
            prepared.update(state='running', started_at=time.time(), hosted_job=job_id, hosted_mode=mode)
            ironbark_runner.write(root / (rep['run_id'] + '.json'), prepared)
            rep['state'] = 'running'
            ironbark_runner.write(job_path(root, job_id), job)
            ironbark_runner.run_worker(root, rep['run_id'])
            result = json.loads((root / (rep['run_id'] + '.result.json')).read_text())
            rows = ironbark_runner.progress(root, {**prepared, 'state': 'completed'})
            ok = result.get('status') == 'done' and len(rows) == 8 and all(r['state'] == 'completed' for r in rows)
            rep['state'] = 'completed' if ok else 'failed'
            prepared.update(state=rep['state'], finished_at=time.time())
            ironbark_runner.write(root / (rep['run_id'] + '.json'), prepared)
        except Exception:
            rep['state'] = 'failed'
            raise
        finally:
            ironbark_runner.write(job_path(root, job_id), job)
        if rep['state'] != 'completed':
            raise RuntimeError('repetition did not complete')


def worker_main(argv: list[str]) -> int:
    root, job_id, parent, db, mode = Path(argv[0]), argv[1], int(argv[2]), Path(argv[3]), argv[4]
    import ctypes
    if ctypes.CDLL(None, use_errno=True).prctl(1, signal.SIGKILL) != 0 or os.getppid() != parent:
        return 4                                             # cannot guarantee the worker dies with the service
    from . import jail
    jail.require()
    jail.policy()                                            # fails closed when the deployment has no jail policy
    if mode == 'rehearsal':
        _rehearsal_patches()
    else:
        _load_key_file()
    admission = Admission.open_existing(db)
    try:
        run_job(root, job_id, admission, mode=mode)
    except Exception as exc:
        # Never copy exception text: provider errors can contain sensitive data.
        job = load_job(root, job_id)
        job['error_type'] = type(exc).__name__
        ironbark_runner.write(job_path(root, job_id), job)
        return 1
    return 0


# --- in the API process -------------------------------------------------------------------------------------

class WorkerExecutor:
    """Launch the hosted worker for one evaluation and wait for it (call from the job's own thread)."""

    def __init__(self, root: Path, admission: Admission, *, mode: str, caps: dict = ARM_CAPS, command=None, rep_timeout: int = REP_TIMEOUT):
        if mode not in MODES:
            raise ValueError('unsupported executor mode')
        self.root, self.admission, self.mode, self.caps = Path(root), admission, mode, dict(caps)
        self.per_rep = per_repetition_microusd(self.caps)
        if admission.cap != self.per_rep:
            raise ValueError('admission policy per-repetition reservation does not match the executor caps')
        self.command = command or (lambda root, job_id, db, mode: [sys.executable, '-m', 'agent_readiness.hosted.paired', str(root), job_id, str(os.getpid()), str(db), mode])
        self.rep_timeout = rep_timeout
        self.processes: dict[str, subprocess.Popen] = {}
        self.available = True

    def run(self, job_id: str) -> None:
        job = load_job(self.root, job_id)
        job['started_at'] = time.time()
        ironbark_runner.write(job_path(self.root, job_id), job)
        import ctypes
        libc = ctypes.CDLL(None, use_errno=True)
        proc = subprocess.Popen(self.command(self.root, job_id, self.admission.path, self.mode), start_new_session=True,
                                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                preexec_fn=lambda: libc.prctl(1, signal.SIGKILL))
        self.processes[job_id] = proc
        try:
            code = proc.wait(timeout=self.rep_timeout * job['repetitions'] + 300)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            proc.wait()
            raise
        finally:
            self.processes.pop(job_id, None)
            job = load_job(self.root, job_id)
            job['finished_at'] = time.time()
            for rep in job['reps']:
                if rep['state'] in ('pending', 'preparing', 'running'):
                    rep['state'] = 'incomplete'
            ironbark_runner.write(job_path(self.root, job_id), job)
        if code != 0:
            raise RuntimeError('hosted worker failed')


if __name__ == '__main__':
    raise SystemExit(worker_main(sys.argv[1:]))
