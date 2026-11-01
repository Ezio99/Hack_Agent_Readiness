import time
from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient

from agent_readiness.hosted.admission import Admission
from agent_readiness.hosted.api import create_app


def setup(tmp_path, executor=None):
    budget = Admission(tmp_path / 'budget.sqlite', ceiling_microusd=3200000, job_cap_microusd=1600000)
    return TestClient(create_app(tmp_path, budget, client_key=b'k'*32, executor=executor)), budget


def test_disabled_and_rejects_extra_fields(tmp_path):
    client, budget = setup(tmp_path)
    assert client.post('/api/ironbark/jobs', json={}).status_code == 503
    assert client.post('/api/ironbark/jobs', json={'url': 'http://example.com'}).status_code == 422
    assert budget.get('absent') is None


def test_failed_executor_keeps_reservation_and_blocks_export(tmp_path):
    class Fail:
        def run(self, job_id):
            raise RuntimeError('test only')
    client, budget = setup(tmp_path, Fail())
    res = client.post('/api/ironbark/jobs', json={})
    assert res.status_code == 202
    job_id = res.json()['id']
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline and budget.get(job_id)['state'] not in ('failed', 'completed'):
        time.sleep(.01)
    assert budget.get(job_id)['state'] == 'failed'
    assert budget.get(job_id)['reserved_microusd'] == 1600000
    assert client.get('/api/ironbark/jobs/' + job_id + '/export').status_code == 409
    assert client.get('/api/ironbark/jobs/../../private').status_code in (404, 405)


def test_concurrent_starts_and_restart_preserve_capacity(tmp_path):
    import threading
    entered, release = threading.Event(), threading.Event()
    class Blocked:
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
        restarted, _ = setup(tmp_path)
        assert restarted.get('/api/ironbark/jobs/' + job_id).json()['state'] == 'running'
        assert budget.get(job_id)['reserved_microusd'] == 1600000
    finally:
        release.set()


def test_fixed_api_with_eight_freshly_graded_fixture_trials(tmp_path):
    import json
    import subprocess
    import sys
    from pathlib import Path
    import pytest
    from agent_readiness.live import ironbark_runner
    if not ironbark_runner.SOURCE.exists():
        pytest.skip('local historical source unavailable')
    fixture_worker = Path(__file__).parent / 'support' / 'ironbark_fixture_worker.py'
    class FixtureExecutor:
        def run(self, job_id):
            job = ironbark_runner.prepare(tmp_path, {'placebo_arm': .8, 'patched_arm': .8}, job_id=job_id)
            job['state'] = 'running'
            ironbark_runner.write(tmp_path / (job_id + '.json'), job)
            subprocess.run([sys.executable, str(fixture_worker), str(tmp_path), job_id, 'ok'], check=True, timeout=120)
    client, budget = setup(tmp_path, FixtureExecutor())
    response = client.post('/api/ironbark/jobs', json={})
    assert response.status_code == 202
    job_id = response.json()['id']
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline and budget.get(job_id)['state'] not in ('completed', 'failed'):
        time.sleep(.1)
    assert budget.get(job_id)['state'] == 'completed'
    assert int((tmp_path / (job_id + '.grades')).read_text()) == 8
    result = client.get('/api/ironbark/jobs/' + job_id + '/export')
    assert result.status_code == 200
    data = result.json()
    assert data['evidence_origin']['provider'] == 'scripted'
    assert data['trials']['patched'] == data['trials']['placebo'] == 4
    assert not any(e['measured'] for e in data['effects'])
    assert 'fixture incorrect' not in json.dumps(data)
