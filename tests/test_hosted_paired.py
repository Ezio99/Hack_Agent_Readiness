import pytest

from agent_readiness.hosted import paired
from agent_readiness.hosted.admission import Admission


def test_mismatched_reservation_or_mode_fails_before_preparation(tmp_path, monkeypatch):
    from agent_readiness.live import ironbark_runner
    budget = Admission(tmp_path / 'budget.db', ceiling_microusd=8000000, job_cap_microusd=1500000)
    job_id = 'eval-' + 'a' * 32
    paired.new_job(tmp_path, job_id, 1, 'rehearsal')
    budget.reserve(job_id, 'b' * 64)
    budget.transition(job_id, 'reserved', 'running')
    monkeypatch.setattr(ironbark_runner, 'prepare', lambda *a, **k: pytest.fail('must not prepare'))
    with pytest.raises(ValueError, match='reservation'):
        paired.run_job(tmp_path, job_id, budget, mode='rehearsal')
    with pytest.raises(ValueError, match='mode'):
        paired.run_job(tmp_path, job_id, budget, mode='live')
    assert budget.get(job_id)['reserved_microusd'] == 1500000
    with pytest.raises(ValueError):
        paired.new_job(tmp_path, 'eval-' + 'b' * 32, 2, 'rehearsal')


def test_worker_refuses_without_jail_policy(tmp_path, monkeypatch):
    import os
    import subprocess
    import sys
    from agent_readiness.hosted import jail
    budget = Admission(tmp_path / 'budget.db', ceiling_microusd=8000000, job_cap_microusd=1600000)
    env = {k: v for k, v in os.environ.items() if k != jail.ENV}
    code = subprocess.run([sys.executable, '-c', 'import os,subprocess,sys; sys.exit(subprocess.run([sys.executable, "-m", "agent_readiness.hosted.paired", sys.argv[1], "eval-" + "c"*32, str(os.getpid()), sys.argv[2], "live"]).returncode)',
                           str(tmp_path), str(budget.path)], env=env, timeout=60).returncode
    assert code != 0


def test_rehearsal_control_check_relaxes_only_model_and_mode(monkeypatch):
    from agent_readiness.investigate.evaluate import stage as evaluation
    from agent_readiness.investigate.trials import stage
    from agent_readiness.ledger import Halt
    import socket
    monkeypatch.setattr(evaluation, '_check_control', evaluation._check_control)
    monkeypatch.setattr(stage, 'run_trial', stage.run_trial)
    monkeypatch.setattr(stage, 'preflight', stage.preflight)
    monkeypatch.setattr(socket, 'socket', socket.socket)
    monkeypatch.setattr(socket, 'getaddrinfo', socket.getaddrinfo)
    paired._rehearsal_patches()
    base = {'trial': {'model': 'muse-spark-1.3', 'mode': 'live', 'profile': 'p', 'profile_hash': 'h', 'schema_hashes': {'a': 1}, 'snapshot_sha256': 's'}, 'task': {'limits': {'max_steps': 14}}}
    class Run:
        def artifact(self, name):
            return base
    st = {'label': 'placebo', 'task': {'task_id': 't'}}
    scripted = {'trial': {**base['trial'], 'model': 'mock-scripted-agent', 'mode': 'mock'}, 'task': base['task']}
    monkeypatch.setattr(evaluation.scroll_successor, 'check', lambda *a: False)
    evaluation._check_control(Run(), st, scripted)                                   # model/mode differences tolerated
    for key, value in (('profile_hash', 'other'), ('snapshot_sha256', 'patched')):
        with pytest.raises(Halt):
            evaluation._check_control(Run(), st, {'trial': {**scripted['trial'], key: value}, 'task': base['task']})
    with pytest.raises(PermissionError):
        socket.create_connection(('1.1.1.1', 443), timeout=1)
