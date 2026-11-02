import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from agent_readiness.hosted import paired
from agent_readiness.hosted.admission import Admission
from agent_readiness.hosted.api import create_app, recover

CAP = 1600000


def setup(tmp_path, executor=None, ceiling=CAP * 6, **kw):
    budget = Admission(tmp_path / 'budget.sqlite', ceiling_microusd=ceiling, job_cap_microusd=CAP)
    return TestClient(create_app(tmp_path, budget, client_key=b'k' * 32, executor=executor, **kw)), budget


def wait(budget, job_id, states=('completed', 'failed', 'timed_out'), seconds=5):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline and budget.get(job_id)['state'] not in states:
        time.sleep(.02)
    return budget.get(job_id)['state']


class Raising:
    available, mode = True, 'rehearsal'
    def __init__(self, exc):
        self.exc = exc
    def run(self, job_id):
        raise self.exc


def test_disabled_and_rejects_every_custom_field(tmp_path):
    client, budget = setup(tmp_path)
    assert client.get('/api/ironbark/config').json()['available'] is False
    assert client.post('/api/ironbark/jobs', json={}).status_code == 503
    for body in ({'url': 'http://example.com'}, {'repetitions': 2}, {'repetitions': 1, 'model': 'x'}, {'repetitions': 1, 'caps': 9}, {'tasks': []}):
        assert client.post('/api/ironbark/jobs', json=body).status_code == 422, body
    assert budget.active() == []


def test_failed_executor_keeps_reservation_and_blocks_export(tmp_path):
    client, budget = setup(tmp_path, Raising(RuntimeError('test only')))
    res = client.post('/api/ironbark/jobs', json={'repetitions': 3})
    assert res.status_code == 202
    job_id = res.json()['id']
    assert wait(budget, job_id) == 'failed'
    assert budget.get(job_id)['reserved_microusd'] == 3 * CAP
    assert client.get(f'/api/ironbark/jobs/{job_id}/repetitions/1/export').status_code == 409
    assert client.get('/api/ironbark/jobs/../../private').status_code in (404, 405)
    assert client.get('/api/ironbark/jobs/paired-' + 'a' * 32).status_code == 404


def test_timed_out_worker_keeps_reservation(tmp_path):
    client, budget = setup(tmp_path, Raising(TimeoutError('fixture timeout')))
    job_id = client.post('/api/ironbark/jobs', json={}).json()['id']
    assert wait(budget, job_id) == 'timed_out'
    assert budget.get(job_id)['reserved_microusd'] == CAP


def test_budget_ceiling_and_rate_limit(tmp_path):
    client, budget = setup(tmp_path, Raising(RuntimeError('x')), ceiling=CAP * 4)
    assert client.post('/api/ironbark/jobs', json={'repetitions': 5}).status_code == 429     # 5 x 1.60 exceeds the ceiling
    job_id = client.post('/api/ironbark/jobs', json={'repetitions': 3}).json()['id']
    wait(budget, job_id)
    assert client.post('/api/ironbark/jobs', json={'repetitions': 1}).status_code == 429     # same client within the interval
    assert client.get('/api/ironbark/config').json()['remaining_repetitions'] == 1


def test_trusted_proxy_only_may_assert_the_client(tmp_path):
    client, budget = setup(tmp_path, Raising(RuntimeError('x')), trusted_proxies=['127.0.0.1'])
    client = TestClient(client.app, client=('127.0.0.1', 5000))
    assert client.post('/api/ironbark/jobs', json={}).status_code == 403                    # proxy without a forwarded client
    a = client.post('/api/ironbark/jobs', json={}, headers={'X-Forwarded-For': '9.9.9.9, 203.0.113.5'})
    assert a.status_code == 202
    wait(budget, a.json()['id'])
    b = client.post('/api/ironbark/jobs', json={}, headers={'X-Forwarded-For': '203.0.113.6'})
    assert b.status_code == 202                                                             # a different client is not rate-limited
    (tmp_path / 'u').mkdir()
    untrusted, _ = setup(tmp_path / 'u', Raising(RuntimeError('x')))
    first = untrusted.post('/api/ironbark/jobs', json={}, headers={'X-Forwarded-For': '1.1.1.1'})
    time.sleep(.2)
    assert untrusted.post('/api/ironbark/jobs', json={}, headers={'X-Forwarded-For': '2.2.2.2'}).status_code == 429  # spoofed header ignored


def test_concurrent_starts_and_restart_recovery_preserve_capacity(tmp_path):
    import threading
    entered, release = threading.Event(), threading.Event()
    class Blocked:
        available, mode = True, 'rehearsal'
        def run(self, job_id):
            entered.set()
            release.wait(5)
            raise RuntimeError('fixture stopped')
    client, budget = setup(tmp_path, Blocked())
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(lambda _: client.post('/api/ironbark/jobs', json={}), range(2)))
        assert sorted(r.status_code for r in responses) == [202, 429]
        assert entered.wait(2)
        job_id = next(r.json()['id'] for r in responses if r.status_code == 202)
        assert client.get('/api/ironbark/config').json()['active'] == job_id
        restarted, _ = setup(tmp_path)
        assert restarted.get('/api/ironbark/jobs/' + job_id).json()['recovery_required'] is True
        assert recover(tmp_path, budget) == [job_id]                                       # what a restarted service does first
        assert budget.get(job_id)['state'] == 'interrupted' and budget.get(job_id)['reserved_microusd'] == CAP
        assert paired.load_job(tmp_path, job_id)['reps'][0]['state'] == 'incomplete'
        assert budget.active() == []
    finally:
        release.set()


def _fixture_executor(tmp_path, budget, fail_rep=0):
    worker = Path(__file__).parent / 'support' / 'hosted_fixture_worker.py'
    return paired.WorkerExecutor(tmp_path, budget, mode='rehearsal', command=lambda root, job_id, db, mode: [sys.executable, str(worker), str(root), job_id, str(db), str(fail_rep)])


def test_three_repetitions_of_eight_freshly_graded_fixture_trials(tmp_path):
    from agent_readiness.live import ironbark_runner
    if not ironbark_runner.SOURCE.exists():
        pytest.skip('local historical source unavailable')
    budget = Admission(tmp_path / 'budget.sqlite', ceiling_microusd=CAP * 6, job_cap_microusd=CAP)
    client = TestClient(create_app(tmp_path, budget, client_key=b'k' * 32, executor=_fixture_executor(tmp_path, budget)))
    response = client.post('/api/ironbark/jobs', json={'repetitions': 3})
    assert response.status_code == 202
    job_id = response.json()['id']
    assert wait(budget, job_id, seconds=300) == 'completed'
    assert int((tmp_path / (job_id + '.grades')).read_text()) == 24
    status = client.get('/api/ironbark/jobs/' + job_id).json()
    assert [r['state'] for r in status['reps']] == ['completed'] * 3
    assert all(len(r['tasks']) == 8 and all(t['state'] == 'completed' for t in r['tasks']) for r in status['reps'])
    assert status['summary']['Original']['completed'] == status['summary']['Modified']['completed'] == 12
    assert status['summary']['Original']['requests_total'] == 24
    assert all(r['assessment']['evidence_origin'] == 'scripted' for r in status['reps'])
    run_ids = {r['run_id'] for r in paired.load_job(tmp_path, job_id)['reps']}
    assert len(run_ids) == 3 and not any(rid in json.dumps(status) for rid in run_ids)          # private run ids never leave
    data = client.get(f'/api/ironbark/jobs/{job_id}/repetitions/2/export').json()
    assert data['evidence_origin']['provider'] == 'scripted' and data['trials']['patched'] == data['trials']['placebo'] == 4
    assert not any(e['measured'] for e in data['effects'])
    assert 'fixture incorrect' not in json.dumps(data)
    assert client.get('/api/ironbark/jobs').json()[0]['id'] == job_id


def test_failed_repetition_fails_the_job_but_keeps_finished_ones_viewable(tmp_path):
    from agent_readiness.live import ironbark_runner
    if not ironbark_runner.SOURCE.exists():
        pytest.skip('local historical source unavailable')
    budget = Admission(tmp_path / 'budget.sqlite', ceiling_microusd=CAP * 6, job_cap_microusd=CAP)
    client = TestClient(create_app(tmp_path, budget, client_key=b'k' * 32, executor=_fixture_executor(tmp_path, budget, fail_rep=2)))
    job_id = client.post('/api/ironbark/jobs', json={'repetitions': 3}).json()['id']
    assert wait(budget, job_id, seconds=300) == 'failed'
    status = client.get('/api/ironbark/jobs/' + job_id).json()
    assert [r['state'] for r in status['reps']] == ['completed', 'failed', 'incomplete']
    assert client.get(f'/api/ironbark/jobs/{job_id}/repetitions/1/export').status_code == 200
    assert client.get(f'/api/ironbark/jobs/{job_id}/repetitions/2/export').status_code == 409
    assert budget.get(job_id)['reserved_microusd'] == 3 * CAP
