"""Hosted service entry point: ``python -m agent_readiness.hosted.serve``.

Configuration (environment; nothing is accepted from requests):

* ``AR_HOSTED_MODE``: ``disabled`` (default), ``rehearsal`` (jailed browser, scripted
  model, no provider) or ``live`` (Meta Muse Spark; requires owner authorization).
* ``AR_HOSTED_CEILING_USD``: global hosted spending ceiling, required unless disabled.
  Every evaluation reserves US$1.60 per repetition against it, permanently.
* ``AR_HOSTED_ROOT`` (default ``/data/hosted``), ``AR_STATIC_DIR`` (dashboard build),
  ``AR_TRUSTED_PROXIES`` (comma-separated reverse-proxy addresses allowed to set
  X-Forwarded-For), ``AR_HOSTED_MIN_INTERVAL`` (seconds per client, default 120),
  ``AR_HOST``/``AR_PORT``.
* ``AGENT_READINESS_BROWSER_JAIL``: jail policy JSON (required unless disabled).
* ``META_MODEL_API_KEY_FILE``: provider key file, read only by the worker (live).
"""
from __future__ import annotations

import fcntl
import os
import secrets
from decimal import Decimal
from pathlib import Path

from . import jail, paired
from .admission import Admission
from .api import create_app, recover
from ..live import ironbark_runner


def _client_key(root: Path) -> bytes:
    path = root / 'client.key'
    if not path.exists():
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'wb') as f:
            f.write(secrets.token_bytes(32))
    return path.read_bytes()


def build():
    mode = os.environ.get('AR_HOSTED_MODE', 'disabled')
    if mode not in ('disabled', *paired.MODES):
        raise SystemExit('AR_HOSTED_MODE must be disabled, rehearsal or live')
    root = Path(os.environ.get('AR_HOSTED_ROOT', '/data/hosted')).resolve()
    root.mkdir(parents=True, exist_ok=True)
    lock = (root / '.service.lock').open('a')
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise SystemExit('another hosted service is using this data directory')
    per_rep = paired.per_repetition_microusd(paired.ARM_CAPS)
    ceiling = os.environ.get('AR_HOSTED_CEILING_USD')
    if mode != 'disabled' and not ceiling:
        raise SystemExit('AR_HOSTED_CEILING_USD is required to enable evaluations')
    db = root / 'admission.sqlite'
    if ceiling:
        admission = Admission(db, ceiling_microusd=int(Decimal(ceiling) * 1_000_000), job_cap_microusd=per_rep,
                              min_interval_seconds=int(os.environ.get('AR_HOSTED_MIN_INTERVAL', '120')))
    elif db.exists():
        admission = Admission.open_existing(db)              # disabled: past results stay viewable
    else:
        import tempfile
        admission = Admission(Path(tempfile.mkdtemp()) / 'empty.sqlite', ceiling_microusd=per_rep, job_cap_microusd=per_rep)
    interrupted = recover(root, admission)
    executor = None
    if mode != 'disabled':
        if not ironbark_runner.SOURCE.exists():
            raise SystemExit(f'source run {ironbark_runner.SOURCE} is missing')
        jail.require()
        jail.policy()
        probe = jail.selftest()
        if not probe.get('ok'):
            raise SystemExit(f'browser isolation self-test failed: {probe}')
        executor = paired.WorkerExecutor(root, admission, mode=mode)
    static = os.environ.get('AR_STATIC_DIR')
    proxies = [p for p in os.environ.get('AR_TRUSTED_PROXIES', '').split(',') if p.strip()]
    app = create_app(root, admission, client_key=_client_key(root), executor=executor, trusted_proxies=proxies,
                     static_dir=Path(static) if static else None)
    app.state.lock = lock
    print(f'hosted service: mode={mode} interrupted={len(interrupted)} jail={"verified" if executor else "unused"}', flush=True)
    return app


def main():
    import uvicorn
    app = build()
    uvicorn.run(app, host=os.environ.get('AR_HOST', '127.0.0.1'), port=int(os.environ.get('AR_PORT', '8080')), workers=1,
                proxy_headers=False, server_header=False, date_header=False, access_log=False)


if __name__ == '__main__':
    main()
