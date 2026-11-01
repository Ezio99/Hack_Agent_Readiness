import json
import subprocess
import sys
import time
from pathlib import Path

import pytest

from agent_readiness.live import ironbark_runner as r
from agent_readiness.suite.core import canonical_hash


@pytest.fixture
def job(tmp_path):
    ids = ['a', 'b', 'c', 'd']
    caps = {'placebo_arm': 0.4, 'patched_arm': 0.5}
    m = {'stage': 'post_trials', 'task_ids': ids, 'arms': [{'task_ids': ids, 'excluded': [], 'patched_snapshot_sha256': r.MODIFIED}],
         'placebo': {'snapshot_sha256': r.ORIGINAL}, 'execution_order': [f'{a}:{i}:r1' for i in ids for a in ('placebo', 'patched')],
         'agent_profile': 'suite-v2-compat2', 'model': r.ModelConfig().model, 'endpoint': r.ModelConfig().base_url, 'repeats': 1,
         'caps_usd': {**caps, 'combined_cap_fits_ceiling': True}, 'tasks_manifest_sha256': r.TASKS_HASH, 'evaluation_rule_sha256': r.RULE_HASH}
    j = {'id': 'paired-' + 'a'*32, 'state': 'awaiting_approval', 'tasks': [{'task_id': i} for i in ids], 'caps': caps,
         'manifest': m, 'manifest_sha256': canonical_hash(m)}
    r.write(tmp_path / (j['id'] + '.json'), j)
    return j


def test_caps_and_manifest_fail_closed(job):
    r.validate_manifest(job['manifest'], job['caps'])
    for value in (0, -1, 1.01, float('nan'), True):
        with pytest.raises(ValueError):
            r.caps_checked({'placebo_arm': value, 'patched_arm': .5})
    for key, value in [('agent_profile', 'other'), ('model', 'other'), ('repeats', 2)]:
        with pytest.raises(ValueError):
            r.validate_manifest({**job['manifest'], key: value}, job['caps'])
    with pytest.raises(ValueError):
        r.validate_manifest({**job['manifest'], 'execution_order': ['one']}, job['caps'])


def test_paid_start_requires_exact_hash_and_budget_before_spawn(tmp_path, job, monkeypatch):
    manager = r.Manager(tmp_path)
    monkeypatch.setattr(subprocess, 'Popen', lambda *a, **k: pytest.fail('must not spawn'))
    for digest, amount in [('wrong', .9), (job['manifest_sha256'], .8), (job['manifest_sha256'], float('nan'))]:
        with pytest.raises(ValueError):
            manager.start(job['id'], digest, amount)
    assert manager.get(job['id'])['state'] == 'awaiting_approval'


def test_eight_completed_trials_and_partial_voids_are_reported(tmp_path, job):
    run = tmp_path / job['id']
    for arm in ('placebo', 'patched'):
        for t in job['tasks']:
            p = run / 'artifacts' / 'trials' / f"{arm}-prp-123-{t['task_id']}-r1.json"
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps({'outcome': {'run_status': 'completed'}, 'evaluation': {'passed': True, 'evidence_backed': True}, 'metrics': {'model_requests': 2}}))
    result = r.Manager(tmp_path).get(job['id'])
    assert len(result['progress']) == 8
    assert all(x['state'] == 'completed' for x in result['progress'])
    assert result['summary']['Original'] == {'completed': 4, 'strict_passes': 4, 'evidence_supported_passes': 4, 'agent_requests': 8, 'incomplete': 0}
    p.write_text(json.dumps({'outcome': {'run_status': 'infrastructure_error'}, 'evaluation': {'passed': True, 'evidence_backed': True}, 'metrics': {'model_requests': 1}}))
    x = r.Manager(tmp_path).get(job['id'])
    assert x['summary']['Modified']['completed'] == 3 and x['summary']['Modified']['strict_passes'] == 3
    assert any(a['state'] == 'failed' and a['strict_pass'] is None for a in x['progress'])


def test_worker_refuses_changed_manifest_without_calling_driver(tmp_path, job, monkeypatch):
    job['state'] = 'running'
    job['manifest']['model'] = 'other'
    r.write(tmp_path / (job['id'] + '.json'), job)
    monkeypatch.setattr(r, 'driver', lambda *a, **k: pytest.fail('no paid calls'))
    with pytest.raises(ValueError):
        r.run_worker(tmp_path, job['id'])


def test_worker_uses_confirmed_manifest(tmp_path, job, monkeypatch):
    job['state'] = 'running'
    r.write(tmp_path / (job['id'] + '.json'), job)
    calls = []
    monkeypatch.setattr(r, 'driver', lambda *a, **kw: calls.append(kw) or {'status': 'done'})
    r.run_worker(tmp_path, job['id'])
    assert calls == [{'approve': frozenset({job['manifest_sha256']}), 'paid': True}]
    assert json.loads((tmp_path / (job['id'] + '.result.json')).read_text())['status'] == 'done'


def test_cancellation_and_timeout_preserve_terminal_state(tmp_path, job):
    manager = r.Manager(tmp_path, timeout=.1)
    job['state'] = 'running'
    r.write(tmp_path / (job['id'] + '.json'), job)
    p = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'], start_new_session=True)
    manager.active, manager.process = job['id'], p
    manager.cancel(job['id'])
    manager._monitor(job['id'], p)
    assert manager.get(job['id'])['state'] == 'cancelled'
    job['state'] = 'running'
    r.write(tmp_path / (job['id'] + '.json'), job)
    p = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'], start_new_session=True)
    manager.active, manager.process = job['id'], p
    manager._monitor(job['id'], p)
    assert manager.get(job['id'])['state'] == 'timed_out'


def test_export_passes_through_existing_clean_check(tmp_path, job, monkeypatch):
    manager = r.Manager(tmp_path)
    monkeypatch.setattr(r.exporter, 'export_run', lambda _: {'truth': 'secret'})
    with pytest.raises(r.exporter.ExportError):
        manager.export(job['id'])


def test_full_paired_driver_with_recorded_trial_fixtures(tmp_path, monkeypatch):
    """Exercise the real paired stage and assessments; archived trial records stand in for model/browser calls."""
    import shutil
    from agent_readiness.investigate.trials import stage as trials
    source = Path('scanner-data/live/live-ab-ironbark-s1')
    if not (source / 'run.json').exists() or not r.SOURCE.exists():
        pytest.skip('local historical fixture not installed')
    job = r.prepare(tmp_path, {'placebo_arm': .8, 'patched_arm': .8})
    calls = []
    async def recorded(inst, snap, *, output, label, **kwargs):
        path = next((source / 'artifacts' / 'trials').glob(f'{label}-*-{inst.spec.task_id}-r1.json'))
        rec = json.loads(path.read_text())
        calls.append((label, inst.spec.task_id, snap.sha256))
        dest = Path(output) / 'fixture'
        shutil.copytree(source / rec['trial_dir'], dest)
        rec['artifact_path'] = str(dest)
        return rec
    monkeypatch.setattr(trials, 'preflight', lambda *_: 'fixture-only')
    monkeypatch.setattr(trials, 'run_trial', recorded)
    job['state'] = 'running'
    r.write(tmp_path / (job['id'] + '.json'), job)
    r.run_worker(tmp_path, job['id'])
    result = json.loads((tmp_path / (job['id'] + '.result.json')).read_text())
    assert result['status'] == 'done'
    assert len(calls) == 8 and len(set((arm, task) for arm, task, _ in calls)) == 8
    assert all(snap == (r.ORIGINAL if arm == 'placebo' else r.MODIFIED) for arm, _, snap in calls)
    view = r.Manager(tmp_path).get(job['id'])
    assert all(row['state'] == 'completed' for row in view['progress'])
    exported = r.Manager(tmp_path).export(job['id'])
    assert exported['evaluation']['state'] == 'evaluated'
    assert exported['trials']['placebo'] == exported['trials']['patched'] == 4


def test_prepare_refuses_to_reuse_existing_run(tmp_path, monkeypatch):
    class Fixed:
        hex = 'a' * 32
    monkeypatch.setattr(r.uuid, 'uuid4', lambda: Fixed())
    existing = tmp_path / ('paired-' + 'a' * 32)
    existing.mkdir()
    (existing / 'run.json').write_text('existing')
    monkeypatch.setattr(r, 'driver', lambda *a, **kw: pytest.fail('must not resume an existing run'))
    with pytest.raises(FileExistsError):
        r.prepare(tmp_path, {'placebo_arm': .8, 'patched_arm': .8})
    assert (existing / 'run.json').read_text() == 'existing'
