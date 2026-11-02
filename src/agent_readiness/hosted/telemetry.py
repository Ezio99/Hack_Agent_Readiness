"""Public projection of a trial's live telemetry (allowlist only).

Reads the trial's own ``trace.jsonl`` (appended while the agent runs) and returns,
per step: the site-relative page path and title, the step screenshot name, the
model's stated evaluation / memory / next goal, the executed actions (allowlisted
names with a short target), errors and the final answer. Never returned: DOM
dumps, model inputs or raw responses, request bodies, local file paths, loopback
ports, thinking text, usage records or anything under ``private/``.

Every value is truncated; any URL is reduced to a path on the mirror, and a
non-mirror URL is reported only as blocked external navigation.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urlsplit

SCREENSHOT = re.compile(r'step-(\d{3})\.png')
LOOPBACK_URL = re.compile(r'(?:https?://)?(?:127\.0\.0\.1|localhost|\[::1\])(?::\d+)?')
CONTROL = re.compile(r'[\x00-\x08\x0b-\x1f\x7f]')
OTHER_URL = re.compile(r'\b[a-zA-Z][a-zA-Z0-9+.-]*://[^\s"\'<>]+')
ACTIONS = {'navigate': 'Navigate', 'click': 'Click', 'scroll': 'Scroll', 'extract': 'Extract', 'find_elements': 'Find elements',
           'search_page': 'Search page', 'go_back': 'Go back', 'done': 'Answer', 'input_text': 'Type', 'input': 'Type', 'send_keys': 'Keys',
           'select_dropdown': 'Select', 'dropdown_options': 'Read options', 'wait': 'Wait', 'switch_tab': 'Switch tab', 'close_tab': 'Close tab',
           'scroll_to_text': 'Scroll to text', 'find_text': 'Find text', 'read_state': 'Read state'}


def text(value, limit: int = 240) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    value = CONTROL.sub(' ', OTHER_URL.sub('[external URL]', LOOPBACK_URL.sub('', value))).strip()
    return value if len(value) <= limit else value[:limit - 1].rstrip() + '…'


def path_of(url) -> str | None:
    if not isinstance(url, str) or not url:
        return None
    if url.startswith('/') and not url.startswith('//'):
        return text(url, 120)
    parts = urlsplit(url)
    if parts.scheme in ('http', 'https') and parts.hostname in ('127.0.0.1', 'localhost'):
        p = (parts.path or '/') + (('?' + parts.query) if parts.query else '')
        return text(p, 120)
    if parts.scheme in ('about', 'chrome-error', 'data') or url.startswith('about:'):
        return None
    return 'external navigation (blocked)'


def _target(name: str, params, element) -> str | None:
    params = params if isinstance(params, dict) else {}
    if name in ('navigate',):
        return path_of(params.get('url'))
    if name == 'click' and isinstance(element, dict):
        label = text(element.get('ax_name') or element.get('node_value'), 80)
        href = (element.get('attributes') or {}).get('href')
        href = path_of(href) if isinstance(href, str) and href.startswith(('/', 'http')) else None
        return ' · '.join(x for x in (label and f'“{label}”', href) if x) or None
    if name == 'scroll':
        down = params.get('down', True)
        pages = params.get('pages') or params.get('num_pages')
        return f"{'down' if down else 'up'}{f' {pages} page(s)' if isinstance(pages, (int, float)) else ''}"
    if name in ('extract', 'search_page', 'find_text', 'scroll_to_text'):
        return text(params.get('query') or params.get('text') or params.get('pattern'), 100)
    if name == 'find_elements':
        return text(params.get('selector'), 60)
    if name == 'done':
        data = params.get('data') if isinstance(params.get('data'), dict) else {}
        answer = data.get('answer', data.get('answers'))
        if isinstance(answer, list):
            answer = '; '.join(str(a) for a in answer[:12])
        return text(answer if isinstance(answer, str) else None, 300)
    return None


def _title(value) -> str | None:
    """Page title; a title that is only the (loopback) address carries no information."""
    if isinstance(value, str) and LOOPBACK_URL.match(value.strip()):
        return None
    return text(value, 120)


def read_events(trace: Path) -> list[dict]:
    events = []
    try:
        lines = trace.read_text(errors='replace').splitlines()
    except OSError:
        return events
    for line in lines:
        try:
            events.append(json.loads(line))
        except ValueError:
            continue                                       # a line being appended right now
    return events


def timeline(attempt_dir: Path) -> dict:
    """Project one trial attempt directory into public steps."""
    events = read_events(attempt_dir / 'trace.jsonl')
    steps: list[dict] = []
    pages: dict[int, dict] = {}
    errors: list[str] = []
    for e in events:
        kind = e.get('kind')
        if kind == 'observation' and isinstance(e.get('step'), int):
            shot = e.get('screenshot')
            pages[e['step']] = {'path': path_of(e.get('url')), 'title': _title(e.get('title')),
                                'screenshot': shot if isinstance(shot, str) and SCREENSHOT.fullmatch(shot) and (attempt_dir / shot).is_file() else None}
        elif kind == 'step_result':
            result = e.get('result') or {}
            output = result.get('model_output') or {}
            number = (result.get('metadata') or {}).get('step_number') or len(steps) + 1
            elements = (result.get('state') or {}).get('interacted_element') or []
            actions = []
            for i, action in enumerate(output.get('action') or []):
                if not isinstance(action, dict) or not action:
                    continue
                name = next(iter(action))
                element = elements[i] if i < len(elements) else None
                actions.append({'name': ACTIONS.get(name, 'Other action'), 'target': _target(name, action[name], element) if name in ACTIONS else None})
            outcomes = [r for r in (result.get('result') or []) if isinstance(r, dict)]
            error = next((text(r.get('error'), 160) for r in outcomes if r.get('error')), None)
            done = any(r.get('is_done') for r in outcomes)
            page = pages.get(number) or {}
            state = result.get('state') or {}
            steps.append({'step': number, 'path': page.get('path') or path_of(state.get('url')), 'title': page.get('title') or _title(state.get('title')),
                          'screenshot': page.get('screenshot'), 'assessment': text(output.get('evaluation_previous_goal'), 220),
                          'memory': text(output.get('memory'), 260), 'goal': text(output.get('next_goal'), 220), 'actions': actions,
                          'error': error, 'done': done})
        elif kind == 'model_http_response' and isinstance(e.get('http_status'), int) and e['http_status'] != 200:
            errors.append(f"model provider returned HTTP {e['http_status']}")
        elif kind in ('model_request_limit', 'estimated_cost_limit', 'fidelity_violation'):
            errors.append({'model_request_limit': 'request limit reached', 'estimated_cost_limit': 'spend limit reached',
                           'fidelity_violation': 'request blocked by the fidelity guard'}[kind])
    # The page the agent is looking at now (an observation without a step result yet).
    pending = max(pages) if pages and (not steps or max(pages) > steps[-1]['step']) else None
    current = {'step': pending, **pages[pending]} if pending else None
    return {'steps': steps, 'current': current, 'errors': errors[:5]}


def attempt_dir(run_dir: Path, arm: str, task_id: str) -> Path | None:
    """Latest attempt directory of the paired trial (`arm` is placebo|patched)."""
    if arm not in ('placebo', 'patched') or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', task_id):
        return None
    candidates = sorted(Path(run_dir, 'trial-data').glob(f'{arm}-*-{task_id}-r1/*/trace.jsonl'))
    return candidates[-1].parent if candidates else None
