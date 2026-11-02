"""Hosted service entry point: ``python -m agent_readiness.hosted.serve``.

Configuration (environment; nothing is accepted from requests):

* ``AR_HOSTED_MODE``: ``disabled`` (default), ``rehearsal`` (jailed browser, scripted
  model, no provider) or ``live`` (Meta Muse Spark; requires owner authorization).
* ``AR_HOSTED_ACCESS``: ``operator`` (default: only a holder of the operator token can
  start evaluations; everyone can watch) or ``public`` (anyone, subject to admission).
* ``AR_HOSTED_CEILING_USD``: global hosted spending ceiling, required unless disabled.
  Every evaluation reserves US$1.65 per repetition against it, permanently.
* ``AR_OPERATOR_TOKEN_FILE`` (default ``/run/secrets/operator_token``),
  ``META_MODEL_API_KEY_FILE`` (provider key, read only by the worker; live only).
* ``AR_HOSTED_DATA`` (default ``/data/hosted``; live/disabled use ``live/``, rehearsal ``rehearsal/``,
  each with its own admission database), ``AR_HOSTED_ROOT`` (explicit override), ``AR_STATIC_DIR`` (dashboard build),
  ``AR_TRUSTED_PROXIES`` (comma-separated reverse-proxy addresses allowed to set
  X-Forwarded-For), ``AR_HOSTED_MIN_INTERVAL`` (seconds per client, default 120),
  ``AR_HOST``/``AR_PORT``.
* ``AGENT_READINESS_BROWSER_JAIL``: jail policy JSON (required unless disabled).
* Engine (M8 follow-up): evaluations run the lifecycle Stage B runner (``hosted/stageb.py``) on the frozen suite the owner ARMED at a terminal
  (``python -m agent_readiness.lifecycle.arming arm``; live mode needs a paid arming, rehearsal mode a rehearsal arming). ``AR_LIFECYCLE_STORE``
  (default ``<AR_HOSTED_DATA>/lifecycle/store``; required to enable evaluations) holds the owner-approved frozen suites; ``AR_STAGE_B_ROOT``
  (default ``<AR_HOSTED_DATA>/lifecycle/stage-b``) holds armings, launch claims, per-launch authorisations and ledgers; ``AR_LIFECYCLE_DATASETS``
  the sanitized datasets. The retired paired Ironbark engine is never constructed; its historical jobs stay viewable. Web approval is disabled.

Startup never crash-loops on an evaluation problem: if any precondition fails the
site and past results stay up, evaluations are disabled, ``/api/health`` reports a
reason code and the log states the cause. Only an unusable data directory exits.
"""
from __future__ import annotations

import fcntl
import os
import secrets
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path

from . import jail, paired
from .admission import Admission
from .api import create_app, recover
from ..live import ironbark_runner


class Unavailable(Exception):
    def __init__(self, code: str, detail: str):
        super().__init__(detail)
        self.code = code


def log(message: str):
    print(f'hosted service: {message}', flush=True)


def _client_key(root: Path) -> bytes:
    path = root / 'client.key'
    if not path.exists():
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'wb') as f:
            f.write(secrets.token_bytes(32))
    return path.read_bytes()


def _secret(path: str | None, name: str, *, min_length: int) -> bytes:
    if not path:
        raise Unavailable(f'missing_{name}', f'{name} file is not configured')
    try:
        value = Path(path).read_bytes().strip()
    except OSError as exc:
        raise Unavailable(f'missing_{name}', f'{name} file {path} is not readable ({exc.strerror})') from None
    if len(value) < min_length:
        raise Unavailable(f'missing_{name}', f'{name} file {path} is empty or too short')
    return value


def check_source(source: Path | None = None):
    """Every file of the private source run must be readable by this user (fork copies it)."""
    source = Path(source or ironbark_runner.SOURCE)
    if not (source / 'run.json').is_file():
        raise Unavailable('source_run_missing', f'source run {source} is missing')
    unreadable = [str(p.relative_to(source)) for p in source.rglob('*') if p.is_file() and not os.access(p, os.R_OK)]
    unreadable += [str(p.relative_to(source)) for p in source.rglob('*') if p.is_dir() and not os.access(p, os.R_OK | os.X_OK)]
    if unreadable:
        raise Unavailable('source_run_unreadable', f'{len(unreadable)} source-run paths are not readable by uid {os.getuid()}, e.g. {unreadable[0]}')


def ceiling_microusd(value: str | None) -> int:
    if not value:
        raise Unavailable('ceiling_not_configured', 'AR_HOSTED_CEILING_USD is required to enable evaluations')
    try:
        micro = Decimal(value) * 1_000_000
    except InvalidOperation:
        raise Unavailable('ceiling_invalid', 'AR_HOSTED_CEILING_USD is not a number') from None
    if micro != micro.to_integral_value() or micro <= 0:
        raise Unavailable('ceiling_invalid', 'AR_HOSTED_CEILING_USD must be positive with at most 6 decimals')
    return int(micro)


def open_admission(root: Path, ceiling: str | None, per_rep: int) -> tuple[Admission, str | None]:
    db = root / 'admission.sqlite'
    interval = int(os.environ.get('AR_HOSTED_MIN_INTERVAL', '120'))
    try:
        micro = ceiling_microusd(ceiling)
        return Admission(db, ceiling_microusd=micro, job_cap_microusd=per_rep, min_interval_seconds=interval), None
    except Unavailable as exc:
        reason = exc.code
    except ValueError as exc:
        reason = 'budget_policy_mismatch' if 'durable policy' in str(exc) else 'ceiling_invalid'
        log(f'evaluations disabled: {exc}')
    if db.exists():
        return Admission.open_existing(db), reason             # history stays viewable
    import tempfile
    return Admission(Path(tempfile.mkdtemp()) / 'empty.sqlite', ceiling_microusd=per_rep, job_cap_microusd=per_rep), reason


def verify_isolation(attempts: int = 3) -> dict:
    """The first Chromium start in a fresh container can be slow (cold caches); retry before giving up.
    A failed *boundary* (escape possible) is never retried into success: only a browser that did not start is."""
    import time
    result: dict = {}
    for attempt in range(1, attempts + 1):
        result = jail.selftest(timeout=60 if attempt == 1 else 30)
        if result.get('ok') or result.get('reason') not in ('jailed browser did not start', 'TimeoutError', 'Error'):
            return result
        log(f'isolation self-test attempt {attempt} did not complete ({result.get("reason")}); retrying')
        time.sleep(3)
    return result


def lifecycle_paths(base: Path) -> dict:
    repo = Path(__file__).resolve().parents[3] / 'datasets' / 'lifecycle'
    return {'datasets': Path(os.environ.get('AR_LIFECYCLE_DATASETS') or ('/app/datasets/lifecycle' if Path('/app/datasets/lifecycle').is_dir() else repo)),
            'store': Path(os.environ.get('AR_LIFECYCLE_STORE') or base / 'lifecycle' / 'store'),
            'stage_b': Path(os.environ.get('AR_STAGE_B_ROOT') or base / 'lifecycle' / 'stage-b')}


def build_lifecycle(paths: dict, root: Path, admission: Admission, executor, client_key: bytes):
    """The lifecycle views (M8): datasets, the store and the hosted Stage B jobs under <root>/stageb. Never prevents the site from starting."""
    try:
        from ..lifecycle.service import LifecycleService
        runs = root / 'stageb'
        service = LifecycleService(datasets=paths['datasets'], store_root=paths['store'], runs_root=runs if runs.is_dir() else None, executor=executor,
                                   admission=admission, client_key=client_key, log=log)
        log(f'lifecycle: datasets={",".join(sorted(service.datasets)) or "none"} store={"yes" if service.store_root else "no"} web-approval=disabled')
        return service
    except Exception as exc:                                              # the site and the hosted evaluation stay up
        log(f'lifecycle: unavailable ({type(exc).__name__}: {str(exc)[:160]})')
        return None


def arming_state(executor) -> str:
    if executor is None:
        return 'unused'
    cfg = executor.configuration()
    ev = cfg.get('evaluation') or {}
    return f"{ev.get('arming_id')} ({ev.get('mode')}, {ev.get('suite')}, launches left {(ev.get('launches') or {}).get('left')})" if cfg['armed'] else f"none ({cfg['reason']})"


def build():
    mode = os.environ.get('AR_HOSTED_MODE', 'disabled')
    access = os.environ.get('AR_HOSTED_ACCESS', 'operator')
    if mode not in ('disabled', *paired.MODES) or access not in ('operator', 'public'):
        raise SystemExit('AR_HOSTED_MODE must be disabled|rehearsal|live and AR_HOSTED_ACCESS operator|public')
    # Rehearsal never shares the live admission database: it would consume the live ceiling and mix
    # scripted runs into the public history. `disabled` shows the live history.
    base = Path(os.environ.get('AR_HOSTED_DATA', '/data/hosted'))
    root = Path(os.environ.get('AR_HOSTED_ROOT') or base / ('rehearsal' if mode == 'rehearsal' else 'live')).resolve()
    try:
        root.mkdir(parents=True, exist_ok=True)
        probe = root / '.write-test'
        probe.write_text('ok')
        probe.unlink()
    except OSError as exc:
        raise SystemExit(f'hosted data directory {root} is not writable: {exc.strerror}')
    lock = (root / '.service.lock').open('a')
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise SystemExit('another hosted service is using this data directory')

    # The Stage B root (owner armings, launch claims, per-launch authorisations and ledgers) lives on the data volume; the worker inherits it.
    paths = lifecycle_paths(base)
    from ..lifecycle import arming
    arming.set_stage_b_root(paths['stage_b'])
    per_rep = paired.per_repetition_microusd(paired.ARM_CAPS)          # the persisted admission policy row stays as it was (rollback-compatible)
    admission, reason = open_admission(root, os.environ.get('AR_HOSTED_CEILING_USD'), per_rep)
    interrupted = recover(root, admission)
    if interrupted:
        log(f'marked {len(interrupted)} unfinished evaluation(s) interrupted; their reservations are kept')

    executor, operator_token = None, None
    if mode == 'disabled':
        reason = 'disabled'
    else:
        try:
            if reason:
                raise Unavailable(reason, 'budget admission is not configured')
            if access == 'operator':
                operator_token = _secret(os.environ.get('AR_OPERATOR_TOKEN_FILE', '/run/secrets/operator_token'), 'operator_token', min_length=24)
            if mode == 'live':
                _secret(os.environ.get('META_MODEL_API_KEY_FILE'), 'provider_key', min_length=8)   # read again by the worker; never logged
            if not (paths['store'] / 'objects').is_dir():
                raise Unavailable('lifecycle_store_missing', f"the lifecycle store {paths['store']} is missing; it holds the owner-approved frozen suites")
            jail.require()
            try:
                jail.policy()
            except Exception as exc:
                raise Unavailable('isolation_policy_invalid', str(exc)) from None
            result = verify_isolation()
            if not result.get('ok'):
                raise Unavailable('isolation_check_failed', f'browser isolation self-test failed: {result}')
            from .stageb import StageBExecutor
            executor = StageBExecutor(root, paths['store'], admission, mode=mode)        # the hosted engine: the lifecycle Stage B runner
            reason = None
        except Unavailable as exc:
            reason = exc.code
            log(f'evaluations disabled [{exc.code}]: {exc}')

    lifecycle = build_lifecycle(paths, root, admission, executor, _client_key(root))
    static = os.environ.get('AR_STATIC_DIR')
    proxies = [p for p in os.environ.get('AR_TRUSTED_PROXIES', '').split(',') if p.strip()]
    app = create_app(root, admission, client_key=_client_key(root), executor=executor, trusted_proxies=proxies,
                     static_dir=Path(static) if static else None, operator_token=operator_token,
                     public_start=(access == 'public'), unavailable_reason=reason, mode=mode, lifecycle=lifecycle)
    app.state.lock = lock
    log(f'mode={mode} access={access} evaluations={"enabled" if executor else "disabled"}'
        f'{" reason=" + reason if reason else ""} jail={"verified" if executor else "unused"} engine={"stage-b" if executor else "none"} armed={arming_state(executor)}')
    return app


def main():
    import uvicorn
    app = build()
    uvicorn.run(app, host=os.environ.get('AR_HOST', '127.0.0.1'), port=int(os.environ.get('AR_PORT', '8080')), workers=1,
                proxy_headers=False, server_header=False, date_header=False, access_log=False, timeout_graceful_shutdown=5)


if __name__ == '__main__':
    sys.exit(main())
