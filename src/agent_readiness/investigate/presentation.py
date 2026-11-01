"""Read-only, allowlisted presentation facts; never export trace payloads."""
import json
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
    if run.has_artifact('dev-provider'):
        return {'provider': 'dev_fixture', 'presentation': 'recorded'}
    if run.mode in ('mock', 'scripted'):
        return {'provider': 'scripted', 'presentation': 'recorded'}
    records = [run.artifact('trials/' + p.stem) for p in sorted((run.dir/'artifacts/trials').glob('*.json'))]
    proven = bool(records)
    for record in records:
        events = events_for(run, record)
        requests = {e.get('index'): e for e in events if e.get('kind') == 'model_http_request'}
        if any(urlsplit(e.get('url', '')).hostname in ('localhost', '127.0.0.1', '::1') for e in requests.values()):
            return {'provider': 'dev_fixture', 'presentation': 'recorded'}
        real = any(e.get('kind') == 'model_http_response' and e.get('http_status') == 200
                   and urlsplit(requests.get(e.get('index'), {}).get('url', '')).scheme == 'https' for e in events)
        proven &= real and record.get('trial', {}).get('mode') == 'live'
    return {'provider': 'real_model' if proven and run.mode == 'live' else 'unknown', 'presentation': 'recorded'}


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
