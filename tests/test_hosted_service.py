"""Hosted service: startup preflight degrades cleanly, operator-only access, telemetry and insights projections."""
import json
import os
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from agent_readiness.hosted import api, insights, jail, paired, serve, telemetry
from agent_readiness.hosted.admission import Admission

CAP = paired.per_repetition_microusd(paired.ARM_CAPS)


@pytest.fixture
def env(tmp_path, monkeypatch):
    source = tmp_path / 'source'
    (source / 'private').mkdir(parents=True)
    (source / 'run.json').write_text('{}')
    (source / 'private' / 'criteria.json').write_text('{}')
    monkeypatch.setattr(serve.ironbark_runner, 'SOURCE', source)
    monkeypatch.setattr(jail, 'selftest', lambda: {'ok': True})
    monkeypatch.setattr(jail, '_REQUIRED', False)
    policy = tmp_path / 'jail.json'
    policy.write_text(json.dumps({'hide': [str(tmp_path / 'hidden')], 'dir': '/tmp/arj-test'}))
    token, key = tmp_path / 'operator', tmp_path / 'key'
    token.write_text('t' * 32)
    key.write_text('provider-key-value')
    for k, v in {'AR_HOSTED_ROOT': str(tmp_path / 'data'), 'AR_HOSTED_MODE': 'live', 'AR_HOSTED_CEILING_USD': '10', 'AR_OPERATOR_TOKEN_FILE': str(token),
                 'META_MODEL_API_KEY_FILE': str(key), jail.ENV: str(policy), 'AR_HOSTED_ACCESS': 'operator'}.items():
        monkeypatch.setenv(k, v)
    monkeypatch.delenv('AR_STATIC_DIR', raising=False)
    yield {'source': source, 'token': token, 'key': key, 'root': tmp_path / 'data'}


def health(app):
    return TestClient(app).get('/api/health').json()


def built(capsys):
    app = serve.build()
    app.state.lock.close()                                   # release the data-directory lock between builds
    return app, capsys.readouterr().out


def test_all_preconditions_enable_operator_only_evaluations(env, capsys):
    app, out = built(capsys)
    assert health(app) == {'status': 'ok', 'mode': 'live', 'evaluations': 'enabled', 'reason': None, 'access': 'operator', 'active': False}
    assert 'provider-key-value' not in out and 't' * 32 not in out
    client = TestClient(app)
    assert client.get('/api/ironbark/config').json()['access'] == 'operator'
    assert client.post('/api/ironbark/jobs', json={}).status_code == 403
    assert client.post('/api/ironbark/jobs', json={}, headers={'Authorization': 'Bearer wrong'}).status_code == 403


@pytest.mark.parametrize('breakage,reason', [
    (lambda e: e['key'].write_text(''), 'missing_provider_key'),
    (lambda e: e['key'].unlink(), 'missing_provider_key'),
    (lambda e: e['token'].write_text('short'), 'missing_operator_token'),
    (lambda e: (e['source'] / 'run.json').unlink(), 'source_run_missing'),
    (lambda e: (e['source'] / 'private' / 'criteria.json').chmod(0), 'source_run_unreadable'),
    (lambda e: os.environ.update(AR_HOSTED_CEILING_USD=''), 'ceiling_not_configured'),
    (lambda e: os.environ.update(AR_HOSTED_CEILING_USD='1.00'), 'ceiling_invalid'),          # below one repetition
    (lambda e: setattr(jail, 'selftest', lambda: {'ok': False, 'reason': 'jailed browser did not start'}), 'isolation_check_failed'),
    (lambda e: os.environ.update({jail.ENV: '/nonexistent.json'}), 'isolation_policy_invalid'),
])
def test_failed_preconditions_keep_the_site_up_with_evaluations_disabled(env, capsys, breakage, reason):
    if os.getuid() == 0 and reason == 'source_run_unreadable':
        pytest.skip('root can read anything')
    breakage(env)
    try:
        app, out = built(capsys)
    finally:
        (env['source'] / 'private' / 'criteria.json').chmod(0o600) if (env['source'] / 'private' / 'criteria.json').exists() else None
    h = health(app)
    assert h['evaluations'] == 'disabled' and h['reason'] == reason, (h, out)
    assert f'[{reason}]' in out
    assert TestClient(app).post('/api/ironbark/jobs', json={}, headers={'Authorization': 'Bearer ' + 't' * 32}).status_code == 503


def test_changed_ceiling_is_refused_but_history_stays_viewable(env, capsys):
    built(capsys)
    os.environ['AR_HOSTED_CEILING_USD'] = '20'
    app, out = built(capsys)
    assert health(app)['reason'] == 'budget_policy_mismatch'
    assert TestClient(app).get('/api/ironbark/jobs').status_code == 200


def test_public_access_and_operator_bearer(env, capsys, monkeypatch):
    monkeypatch.setenv('AR_HOSTED_MODE', 'rehearsal')
    app, _ = built(capsys)
    started = []
    class Exec:
        available, mode = True, 'rehearsal'
        def run(self, job_id):
            started.append(job_id)
            raise RuntimeError('stop')
    budget = Admission.open_existing(env['root'] / 'admission.sqlite')
    gated = TestClient(api.create_app(env['root'], budget, client_key=b'k' * 32, executor=Exec(), public_start=False, operator_token=b't' * 32))
    assert gated.post('/api/ironbark/jobs', json={}).status_code == 403
    assert gated.post('/api/ironbark/jobs', json={}, headers={'Authorization': 'Bearer ' + 't' * 32}).status_code == 202
    nobody = TestClient(api.create_app(env['root'] / 'x', budget, client_key=b'k' * 32, executor=Exec(), public_start=False, operator_token=None))
    assert nobody.get('/api/health').json()['reason'] == 'missing_operator_token'


def test_reservation_covers_caps_plus_one_request_bound():
    from agent_readiness.spend_gate import PER_REQUEST_CAP_USD
    assert paired.caps_microusd(paired.ARM_CAPS) == 1_600_000
    assert CAP == 1_600_000 + int(PER_REQUEST_CAP_USD * 1_000_000)


def test_executor_refuses_an_admission_policy_with_a_different_reservation(tmp_path):
    with pytest.raises(ValueError, match='does not match'):
        paired.WorkerExecutor(tmp_path, Admission(tmp_path / 'a.db', ceiling_microusd=10_000_000, job_cap_microusd=1_600_000), mode='rehearsal')


# --- telemetry -------------------------------------------------------------------------------------------------

def write_trace(d: Path, events):
    d.mkdir(parents=True, exist_ok=True)
    (d / 'trace.jsonl').write_text('\n'.join(json.dumps(e) for e in events) + '\n{"partial": ')
    (d / 'step-001.png').write_bytes(b'\x89PNG fake')


EVENTS = [
    {'kind': 'model_http_request', 'messages': ['SECRET PROMPT'], 'url': 'https://api.meta.ai/v1'},
    {'kind': 'observation', 'step': 1, 'url': 'http://127.0.0.1:40111/hire', 'title': '127.0.0.1:40111/hire', 'dom': 'DOM-DUMP', 'screenshot': 'step-001.png'},
    {'kind': 'step_result', 'result': {'model_output': {'evaluation_previous_goal': 'Opened http://127.0.0.1:40111/', 'memory': 'm', 'next_goal': 'Open the lift',
        'thinking': 'PRIVATE-THINKING', 'action': [{'click': {'index': 4}}, {'navigate': {'url': 'https://evil.example/x'}}]},
        'result': [{'is_done': False, 'extracted_content': 'EXTRACTED'}, {'error': 'net::ERR_INTERNET_DISCONNECTED at https://evil.example/x'}],
        'state': {'url': 'http://127.0.0.1:40111/hire', 'screenshot_path': '/tmp/browser_use/step_1.png',
                  'interacted_element': [{'ax_name': 'Electric scissor lift', 'attributes': {'href': '/hire/lift'}}, None]}, 'metadata': {'step_number': 1}}},
    {'kind': 'model_http_response', 'http_status': 429},
    {'kind': 'observation', 'step': 2, 'url': 'http://127.0.0.1:40111/hire/lift', 'title': 'Lift', 'dom': 'x', 'screenshot': '../../private/criteria.json'},
]


def test_timeline_projects_only_allowlisted_sanitized_fields(tmp_path):
    t = telemetry.timeline(write_trace(tmp_path / 'a', EVENTS) or tmp_path / 'a')
    text = json.dumps(t)
    for leaked in ('SECRET PROMPT', 'DOM-DUMP', 'PRIVATE-THINKING', 'EXTRACTED', '127.0.0.1', '/tmp/', 'evil.example', 'criteria'):
        assert leaked not in text, leaked
    step = t['steps'][0]
    assert step['path'] == '/hire' and step['title'] is None and step['screenshot'] == 'step-001.png'
    assert step['actions'] == [{'name': 'Click', 'target': '“Electric scissor lift” · /hire/lift'}, {'name': 'Navigate', 'target': 'external navigation (blocked)'}]
    assert step['error'].startswith('net::ERR_INTERNET_DISCONNECTED')
    assert t['current'] == {'step': 2, 'path': '/hire/lift', 'title': 'Lift', 'screenshot': None}
    assert t['errors'] == ['model provider returned HTTP 429']


def _synthetic_job(root: Path, mode='rehearsal'):
    job_id = 'eval-' + 'd' * 32
    budget = Admission(root / 'b.db', ceiling_microusd=CAP * 4, job_cap_microusd=CAP)
    job = paired.new_job(root, job_id, 1, mode)
    run_id = job['reps'][0]['run_id']
    (root / (run_id + '.json')).write_text(json.dumps({'id': run_id, 'state': 'running', 'tasks': [{'task_id': f'gen-{i}', 'question': 'q', 'limits': {'max_steps': 14}} for i in 'abcd']}))
    write_trace(root / run_id / 'trial-data' / 'placebo-prp-1-gen-b-r1' / '20261102T000000-aaaa', EVENTS)
    budget.reserve(job_id, 'e' * 64)
    budget.transition(job_id, 'reserved', 'running')
    return job_id, budget


def test_trial_live_and_screenshot_endpoints(tmp_path):
    job_id, budget = _synthetic_job(tmp_path)
    client = TestClient(api.create_app(tmp_path, budget, client_key=b'k' * 32))
    t = client.get(f'/api/ironbark/jobs/{job_id}/repetitions/1/trials/original/2').json()
    assert t['state'] == 'running' and t['steps'][0]['goal'] == 'Open the lift' and t['mode'] == 'rehearsal'
    assert client.get(f'/api/ironbark/jobs/{job_id}/repetitions/1/trials/modified/2').json()['steps'] == []
    live = client.get(f'/api/ironbark/jobs/{job_id}/live').json()
    assert live['active'] and (live['trial']['arm'], live['trial']['task'], live['trial']['state']) == ('original', 2, 'running')
    assert live['trial']['steps'][0]['path'] == '/hire'
    png = client.get(f'/api/ironbark/jobs/{job_id}/repetitions/1/trials/original/2/screenshots/step-001.png')
    assert png.status_code == 200 and png.headers['content-type'] == 'image/png'
    for bad in ('step-1.png', '..%2Ftrace.jsonl', 'trace.jsonl', 'step-002.png'):
        assert client.get(f'/api/ironbark/jobs/{job_id}/repetitions/1/trials/original/2/screenshots/{bad}').status_code == 404, bad
    for bad in ('/repetitions/2/trials/original/1', '/repetitions/0/trials/original/1', '/repetitions/1/trials/baseline/1', '/repetitions/1/trials/original/5'):
        assert client.get(f'/api/ironbark/jobs/{job_id}{bad}').status_code in (404, 422), bad


def test_insights_separate_observations_from_suggestions():
    def run(**k):
        base = {'steps': 13, 'distinct_pages': 6, 'detail_views': 4, 'listing_returns': 3, 'policy_views': 1, 'revisits': 5, 'element_searches': 2,
                'scrolls': 0, 'errors': 0, 'answered': True, 'step_limit': False}
        return {**base, **k}
    out = insights.build({'Original': [run(), run(step_limit=True, answered=False)], 'Modified': [run(steps=5, detail_views=0, listing_returns=0), run(steps=6, detail_views=0, listing_returns=0)]})
    ids = [f['id'] for f in out['findings']]
    assert ids[:2] == ['detail-dependency', 'navigation-loops'] and 'step-budget' in ids and 'modified-effect' in ids
    assert all(s['status'] in ('not measured', 'tested in this evaluation') for s in out['suggestions'])
    assert next(s for s in out['suggestions'] if s['for'] == 'detail-dependency')['status'] == 'tested in this evaluation'
    assert insights.build({'Original': [], 'Modified': []})['state'] == 'insufficient'
    f = insights.trial_features([{'path': '/hire', 'actions': [{'name': 'Find elements'}]}, {'path': '/hire/lift', 'actions': []}, {'path': '/hire', 'actions': []},
                                 {'path': '/hire/sort/price-desc', 'actions': [{'name': 'Scroll'}]}], 4)
    assert (f['detail_views'], f['listing_returns'], f['revisits'], f['step_limit']) == (1, 2, 1, True)
