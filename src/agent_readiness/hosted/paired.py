"""Hosted evaluation records and helpers shared with the Stage B engine (M8 follow-up).

The original paired Ironbark engine (``WorkerExecutor`` -> ``ironbark_runner.prepare`` + ``run_worker`` -> ``abtest.drive``) is RETIRED: the hosted
service now runs ``hosted/stageb.py`` (the lifecycle Stage B runner on an owner-armed frozen suite). What remains here:

* the record format of historical ``eval-<hex>`` jobs (``job_path``, ``load_job``, ``new_job``), read by the API's history views;
* ``per_repetition_microusd(ARM_CAPS)``: the unit of the PERSISTED admission policy row, kept byte-identical so the previous image (rollback) still
  opens the same admission database; Stage B launches reserve exact amounts instead (``Admission.reserve_amount``);
* ``_loopback_only_sockets`` (zero-cost rehearsal workers refuse every non-loopback connection) and ``_load_key_file`` (paid workers read the
  provider key from its secret file after exec), both used by ``lifecycle/jobs.py``.
"""
from __future__ import annotations

import json
import os
import subprocess
import time
import uuid
from decimal import Decimal
from pathlib import Path

from .admission import Admission
from ..live import ironbark_runner

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


def _load_key_file():
    path = os.environ.pop('META_MODEL_API_KEY_FILE', None)
    if path and not os.environ.get('META_MODEL_API_KEY'):
        value = Path(path).read_text().strip()
        if value:
            os.environ['META_MODEL_API_KEY'] = value          # set after exec: not in /proc/<pid>/environ
