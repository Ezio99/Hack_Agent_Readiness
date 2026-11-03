"""Hosted evaluation API: the unchanged launch contract and its safeguards, now in front of the Stage B engine (M8 follow-up). The executor here is
a Stage B stand-in (its admission and job record are real; its run is replaced), so no browser or model is involved."""
import time
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from agent_readiness.hosted import stageb
from agent_readiness.hosted.admission import Admission
from agent_readiness.hosted.api import create_app, recover
from agent_readiness.lifecycle import jobs as J

CAP = 1650000                     # one launch unit in these tests (the armed reservation per repetition)


class StageB:
    """A Stage B executor whose launch reserves CAP x repetitions in the real admission and writes a real job record; `run` is the test's."""
    engine, available, mode = stageb.ENGINE, True, 'rehearsal'

    def __init__(self, run=None):
        self._run = run or (lambda job_id: None)
        self.root = None

    def configuration(self):
        return {'engine': stageb.ENGINE, 'armed': True, 'reason': None, 'tasks': [], 'repetitions': [1, 3, 5],
                'evaluation': {'launches': {'left': 9, 'max': 9, 'used': 0}, 'agent': {'model': 'muse-spark-1.3', 'profile': 'suite-v2-compat2'}, 'options': []}}

    def admit(self, job_id, client, repetitions):
        self.admission.reserve_amount(job_id, client, CAP * repetitions)
        J.new_job(self.root / 'stageb', job_id, manifest_sha='a' * 64, mode='rehearsal', request={'repetitions': repetitions}, label='test')
        J.update_job(self.root / 'stageb', job_id, repetitions=repetitions, engine=stageb.ENGINE)
        return {'id': job_id, 'state': 'reserved', 'repetitions': repetitions}

    def run(self, job_id):
        self._run(job_id)


def setup(tmp_path, executor=None, ceiling=CAP * 6, **kw):
    budget = Admission(tmp_path / 'budget.sqlite', ceiling_microusd=ceiling, job_cap_microusd=CAP)
    if executor is not None:
        executor.root, executor.admission = tmp_path, budget
    return TestClient(create_app(tmp_path, budget, client_key=b'k' * 32, executor=executor, **kw)), budget


def wait(budget, job_id, states=('completed', 'failed', 'timed_out'), seconds=5):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline and budget.get(job_id)['state'] not in states:
        time.sleep(.02)
    return budget.get(job_id)['state']


def Raising(exc):
    def run(job_id):
        raise exc
    return StageB(run)


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
    assert client.get(f'/api/ironbark/jobs/{job_id}').json()['report'] is None                                # a failed evaluation has no report
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
    assert client.get('/api/ironbark/config').json()['ceiling'] == {'ceiling_usd': CAP * 4 / 1e6, 'reserved_usd': CAP * 3 / 1e6}


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
    def blocked(job_id):
        entered.set()
        release.wait(5)
        raise RuntimeError('fixture stopped')
    client, budget = setup(tmp_path, StageB(blocked))
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(lambda _: client.post('/api/ironbark/jobs', json={}), range(2)))
        assert sorted(r.status_code for r in responses) == [202, 409]          # the second start is told an evaluation is already running (not a refusal of the caller)
        assert entered.wait(2)
        job_id = next(r.json()['id'] for r in responses if r.status_code == 202)
        assert client.get('/api/ironbark/config').json()['active'] == job_id
        restarted, _ = setup(tmp_path)
        assert restarted.get('/api/ironbark/jobs/' + job_id).json()['recovery_required'] is True
        assert recover(tmp_path, budget) == [job_id]                                       # what a restarted service does first
        assert budget.get(job_id)['state'] == 'interrupted' and budget.get(job_id)['reserved_microusd'] == CAP
        assert J.load_job(tmp_path / 'stageb', job_id)['state'] == 'interrupted'                    # never re-run
        assert budget.active() == []
    finally:
        release.set()


def test_the_retired_engine_cannot_launch(tmp_path):
    class Legacy:                                                                           # an executor without the Stage B interface
        available, mode = True, 'rehearsal'
        def run(self, job_id):
            raise AssertionError('must not run')
    client, budget = setup(tmp_path, Legacy())
    assert client.post('/api/ironbark/jobs', json={'repetitions': 1}).status_code == 503 and budget.recent() == []
