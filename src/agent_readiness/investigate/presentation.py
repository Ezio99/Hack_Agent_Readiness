"""Read-only, allowlisted presentation facts; never export trace payloads."""
import json
import ipaddress
from urllib.parse import urlsplit


def events_for(run, record):
    rel = record.get('trial_dir')
    if not isinstance(rel, str):
        return []
    path = (run.dir / rel / 'trace.jsonl').resolve()
    if not path.is_relative_to(run.dir.resolve()) or not path.is_file():
        return []
    try:
        return [json.loads(line) for line in path.read_text().splitlines()]
    except (ValueError, OSError):
        return []


def origin(run):
    def result(provider):
        return {'provider': provider, 'presentation': 'recorded'}
    if run.has_artifact('fixture-evidence'):
        return result('scripted')
    if run.has_artifact('dev-provider'):
        return result('dev_fixture')
    if run.mode in ('mock', 'scripted'):
        return result('scripted')
    records = [run.artifact('trials/' + p.stem) for p in sorted((run.dir/'artifacts/trials').glob('*.json'))]
    proven = bool(records)
    # An assessment cannot be verified from a surviving subset of its trials.
    if run.has_artifact('evaluation'):
        try:
            evaluation = run.artifact('evaluation')
            tasks = run.artifact('tasks-manifest')['tasks']
            trial_dir = run.dir / 'artifacts' / 'trials'
            plan = run.artifact('post-plan') if run.has_artifact('post-plan') else {}
            if not evaluation.get('evaluated') or not evaluation.get('results'):
                proven = False
            for pid, assessment in evaluation.get('results', {}).items():
                excluded = {e['task_id'] for e in assessment.get('excluded', [])}
                ids = {t['task_id'] for t in tasks} - excluded
                proven &= bool(ids) and all(list(trial_dir.glob(f'baseline-{t}-r*.json')) and list(trial_dir.glob(f'patched-{pid}-{t}-r*.json')) for t in ids)
                proven &= all(list(trial_dir.glob(f'placebo-{pid}-{t}-r*.json')) for t in plan.get('placebo_tasks', []))
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            proven = False
    for record in records:
        events = events_for(run, record)
        requests = {e.get('index'): e for e in events if e.get('kind') == 'model_http_request'}
        def endpoint(value):
            try:
                return urlsplit(value if isinstance(value, str) else '')
            except ValueError:
                return urlsplit('')
        def local(host):
            if not host or host == 'localhost' or host.endswith('.localhost'):
                return True
            try:
                return not ipaddress.ip_address(host).is_global
            except ValueError:
                return False
        if any(local(endpoint(e.get('url')).hostname) for e in requests.values() if endpoint(e.get('url')).hostname):
            return result('dev_fixture')
        real = any(e.get('kind') == 'model_http_response' and e.get('http_status') == 200
                   and endpoint(requests.get(e.get('index'), {}).get('url')).scheme == 'https'
                   and not local(endpoint(requests.get(e.get('index'), {}).get('url')).hostname) for e in events)
        mirror = record.get('mirror')
        log = mirror.get('log') if isinstance(mirror, dict) else None
        browser = isinstance(log, list) and any(isinstance(e, dict) and e.get('method') == 'GET' and e.get('status') == 200 for e in log)
        proven &= real and browser and record.get('trial', {}).get('mode') == 'live'
    return result('real_model' if proven and run.mode == 'live' else 'unknown')


ACTIONS = {'click': 'Clicked a page element', 'navigate': 'Navigated within the captured site',
           'scroll': 'Scrolled', 'go_back': 'Went back', 'search_page': 'Searched page text',
           'find_elements': 'Located page elements', 'done': 'Submitted a structured response (content withheld)'}


def storyboard(run):
    paths = sorted((run.dir/'artifacts/trials').glob('patched-*.json'))
    if not paths:
        return None
    record = run.artifact('trials/' + paths[0].stem)
    events = events_for(run, record)
    items, observed = [], set()
    for event in events:
        kind = event.get('kind')
        if kind == 'observation':
            dom = event.get('dom', '').lower()
            visible = [label for label in ('refundable deposit', 'minimum hire', 'delivery and collection') if label in dom and label not in observed]
            if visible:
                items.append({'event': event['sequence'], 'category': 'page observation', 'text': 'Captured view included field labels: ' + ', '.join(visible), 'ok': True})
                observed.update(visible)
        elif kind == 'scroll_index_fallback':
            items.append({'event': event['sequence'], 'category': 'browser tool',
                          'text': 'Missing scroll index used a page scroll instead.',
                          'ok': not bool(event.get('result', {}).get('error') or event.get('result', {}).get('exception'))})
        elif kind == 'step_result':
            result = event.get('result') or {}
            actions = (result.get('model_output') or {}).get('action', [])
            # Only actions with an execution result, never the entire proposed batch.
            for action, outcome in zip(actions, result.get('result', [])):
                name = next(iter(action), '')
                if name in ACTIONS:
                    items.append({'event': event['sequence'], 'category': 'agent action', 'text': ACTIONS[name], 'ok': not bool(outcome.get('error'))})
    ev = record.get('evaluation', {})
    return {'task_id': record['task_id'], 'arm': 'patched', 'steps': items[:12],
            'strict_pass': bool(ev.get('passed')), 'evidence_supported': bool(ev.get('passed') and ev.get('evidence_backed')),
            'note': 'Selected recorded execution events, in order. Content and response payloads withheld; field presence is an observation, not a causal diagnosis.'} if items else None
