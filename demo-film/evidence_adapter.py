"""Read-only adapter for explicitly selected public investigation-dashboard-v1 reports.

Only reviewed public report fields are projected; never serialize the source report.
This is a narrow single-trial-per-arm adapter, not a general experiment evaluator.
"""
import hashlib
import json
import re
from pathlib import Path


class EvidenceError(ValueError):
    pass


def local_path(root, name):
    path = (root / name).resolve()
    if not path.is_relative_to(root.parent.resolve()):
        raise EvidenceError('Paths must stay inside this repository')
    return path


def project(report, selection, featured, source_sha):
    if report.get('schema') != 'investigation-dashboard-v1' or report.get('audience') != 'public-demo':
        raise EvidenceError('Only already-sanitized public investigation reports are supported')
    if report.get('evidence_origin') != {'provider': 'real_model', 'presentation': 'recorded'}:
        raise EvidenceError('This adapter requires authoritative recorded real-model provenance')
    run = report['run']
    if run['id'] != selection['run_id'] or not run.get('complete'):
        raise EvidenceError('Selected run does not match a complete report')
    if selection['original_arm'] != 'placebo' or selection['modified_arm'] != 'patched':
        raise EvidenceError('This adapter compares contemporary placebo vs patched only')
    proposal_id = selection['proposal_id']
    proposal = next((p for p in report['proposals'] if p['id'] == proposal_id), None)
    verdict = next((v for v in report['evaluation']['results'] if v['proposal_id'] == proposal_id), None)
    if not proposal or not verdict:
        raise EvidenceError('Selected proposal/result unavailable')
    rows = []
    for i, task in enumerate(report['tasks']):
        row = {'id': task['task_id'], 'question': task['question'], 'ref': f'/tasks/{i}'}
        for label, arm in [('original', 'placebo'), ('modified', 'patched')]:
            trials = task.get(arm, {}).get(proposal_id, [])
            if len(trials) > 1:
                raise EvidenceError('Repeated trials require an explicitly reviewed adapter extension')
            trial = trials[0] if trials else None
            valid = trial and not trial.get('void', True) and trial.get('run_status') == 'completed'
            row[label] = {
                'strict': trial.get('passed') if valid else None,
                'supported': trial.get('evidence_backed') if valid else None,
                'requests': trial.get('model_requests') if valid else None,
                'ref': f'/tasks/{i}/{arm}/{proposal_id}/0' if trial else None,
            }
            for key in ('strict', 'supported'):
                if row[label][key] is not None and type(row[label][key]) is not bool:
                    raise EvidenceError('Outcome must be boolean or unavailable')
            requests = row[label]['requests']
            if requests is not None and (type(requests) is not int or requests < 0):
                raise EvidenceError('Requests must be nonnegative integers or unavailable')
        rows.append(row)
    if not rows or len({r['id'] for r in rows}) != len(rows):
        raise EvidenceError('Tasks must be nonempty and unique')

    def total(arm, field):
        values = [r[arm][field] for r in rows]
        return None if any(v is None for v in values) else sum(values)

    original = {k: total('original', k) for k in ('strict', 'supported', 'requests')}
    modified = {k: total('modified', k) for k in ('strict', 'supported', 'requests')}
    before, after = original['requests'], modified['requests']
    if before is None or after is None or before == 0:
        change = 'Request change unavailable'
    elif after < before:
        change = f'{(before-after)/before:.0%} fewer in this recorded run'
    elif after > before:
        change = f'{(after-before)/before:.0%} more in this recorded run'
    else:
        change = 'No request change in this recorded run'
    selected = next((r for r in rows if r['id'] == featured['task_id']), None)
    if not selected:
        raise EvidenceError('Featured task does not exist in selected report')
    story = report.get('storyboard', {})
    events = []
    if story.get('task_id') == selected['id'] and story.get('arm') == featured['arm']:
        indices = []
        for ref in featured.get('event_refs', []):
            match = re.fullmatch(r'/storyboard/steps/(\d+)', ref)
            if not match or int(match[1]) >= len(story.get('steps', [])):
                raise EvidenceError('Selected event reference does not exist')
            index = int(match[1])
            indices.append(index)
            step = story['steps'][index]
            events.append({k: step.get(k) for k in ('event', 'category', 'text', 'ok')} | {'ref': ref})
        if indices != sorted(set(indices)):
            raise EvidenceError('Select unique event references in archived order')
    focus = next((e for e in events if e['ref'] == featured.get('focus_ref')), None)
    if events and featured.get('focus_ref') and not focus:
        raise EvidenceError('Focus must be part of selected event sequence')
    qualification = ('Exploratory comparison · Improvement not established'
                     if verdict['verdict'] == 'inconclusive'
                     else 'Recorded comparison · See stored verdicts')
    return {
        'schema': 'film-evidence-v1', 'source_sha256': source_sha,
        'run_id': run['id'], 'label': report.get('demo_case', {}).get('label', 'Recorded evaluation'),
        'provenance': report['evidence_origin'], 'task_count': len(rows), 'rows': rows,
        'original': original, 'modified': modified, 'request_change_label': change,
        'verdicts': {'frozen': verdict['verdict'], 'exploratory': report['evaluation'].get('exploratory', {}).get('verdict')},
        'qualification': qualification,
        'uncertainty': {'frozen_reason': verdict.get('reason'),
                        'rule_id': report['evaluation'].get('rule', {}).get('id'),
                        'causal_scope': report['evaluation'].get('rule', {}).get('causal_scope'),
                        'story_note': story.get('note'),
                        'demo_note': report.get('demo_case', {}).get('note')},
        'proposal': {'id': proposal_id, 'label': proposal['label'], 'owner_selected': proposal.get('owner_selected'),
                     'validation': proposal.get('validation'), 'basis': proposal.get('basis'),
                     'ref': f"/proposals/{report['proposals'].index(proposal)}"},
        'featured': {'task_id': selected['id'], 'question': selected['question'], 'arm': featured['arm'],
                     'events': events, 'event_count': len(events), 'focus': focus,
                     'availability': 'available' if events else 'No public event sequence available for this task/arm'},
    }


def load(root, manifest):
    selection = manifest['evidence']
    if selection['adapter'] != 'investigation-dashboard-v1-public':
        raise EvidenceError('Unsupported adapter; add a reviewed adapter for a new report format')
    raw = local_path(root, selection['source']).read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != selection['sha256']:
        raise EvidenceError('Report SHA256 differs from explicitly selected evidence')
    return project(json.loads(raw), selection, manifest['featured'], digest)


def captures(root, manifest, evidence):
    """Use optional actual UI crops only while their report/selection bindings match."""
    config = manifest.get('captures')
    if not config:
        return {}
    metadata = json.loads(local_path(root, config['provenance']).read_text())
    if (metadata['recorded_asset_sha256'] != evidence['source_sha256']
            or metadata.get('proposal_id') != evidence['proposal']['id']):
        return {}  # No stale report imagery when switching evidence.
    result = {}
    for key, name in [('storyboard', 'recorded-storyboard.png'), ('suggestion', 'recorded-suggestion.png'),
                      ('outcomes', 'recorded-outcomes.png')]:
        if key == 'storyboard' and (metadata.get('task_id') != evidence['featured']['task_id']
                                   or metadata.get('arm') != evidence['featured']['arm']
                                   or [e['ref'] for e in evidence['featured']['events']] != metadata.get('story_event_refs')):
            continue
        if key != 'storyboard' and config['proposal_id'] != evidence['proposal']['id']:
            continue
        path = local_path(root, 'assets/' + name)
        expected = metadata['images'][name]['sha256']
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise EvidenceError('UI capture hash mismatch')
        result[key] = 'assets/' + name
    return result
