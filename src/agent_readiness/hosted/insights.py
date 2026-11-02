"""Evidence-derived friction insights for a hosted evaluation.

Deterministic rules over the public telemetry projection (``telemetry.timeline``) of
every finished Original/Modified trial. Each finding states what was OBSERVED (counts,
with the number of agent runs behind it). Each suggestion is a separate, explicitly
unmeasured proposal; the only measured comparison is the Original vs Modified grading
already reported by the evaluation. No model call is made here.
"""
from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

from . import telemetry

DETAIL = re.compile(r'^/hire/(?!sort/)[a-z0-9-]+$')
LISTING = re.compile(r'^/(hire|equipment|kits|accessories)(/sort/[a-z-]+)?$')
POLICY = re.compile(r'^/hire-terms$')
ARMS = {'placebo': 'Original', 'patched': 'Modified'}


def trial_features(steps: list[dict], max_steps: int | None) -> dict:
    paths = [s['path'] for s in steps if s.get('path')]
    visits = Counter(paths)
    names = [a['name'] for s in steps for a in s.get('actions', [])]
    done = any(s.get('done') for s in steps)
    return {'steps': len(steps), 'distinct_pages': len(visits),
            'detail_views': sum(1 for p in paths if DETAIL.match(p)),
            'listing_returns': max(0, sum(1 for p in paths if LISTING.match(p)) - 1),
            'policy_views': sum(1 for p in paths if POLICY.match(p)),
            'revisits': sum(n - 1 for n in visits.values() if n > 1),
            'element_searches': sum(n in ('Find elements', 'Search page', 'Extract', 'Find text') for n in names),
            'scrolls': names.count('Scroll'), 'errors': sum(1 for s in steps if s.get('error')),
            'answered': done, 'step_limit': bool(max_steps and len(steps) >= max_steps and not done)}


def collect(root: Path, reps: list[dict]) -> dict[str, list[dict]]:
    """Features of every finished paired trial, by arm label."""
    import json
    from ..live import ironbark_runner
    out = {'Original': [], 'Modified': []}
    for rep in reps:
        try:
            operator = json.loads((root / (rep['run_id'] + '.json')).read_text())
        except (OSError, ValueError):
            continue
        limits = {t['task_id']: (t.get('limits') or {}).get('max_steps') for t in operator['tasks']}
        order = sorted(t['task_id'] for t in operator['tasks'])
        finished = {(r['arm'], r['task_id']) for r in ironbark_runner.progress(root, operator) if r['state'] == 'completed'}
        for arm, label in ARMS.items():
            for task_id in order:
                if (label, task_id) not in finished:
                    continue
                d = telemetry.attempt_dir(root / rep['run_id'], arm, task_id)
                if d is None:
                    continue
                f = trial_features(telemetry.timeline(d)['steps'], limits.get(task_id))
                out[label].append({**f, 'task': order.index(task_id) + 1, 'repetition': rep['index']})
    return out


def _mean(rows, key):
    return round(sum(r[key] for r in rows) / len(rows), 1) if rows else None


def build(features: dict[str, list[dict]]) -> dict:
    o, m = features['Original'], features['Modified']
    stats = {arm: {k: _mean(rows, k) for k in ('steps', 'detail_views', 'listing_returns', 'revisits', 'element_searches', 'scrolls', 'policy_views')}
             | {'runs': len(rows), 'step_limit_runs': sum(r['step_limit'] for r in rows), 'error_runs': sum(r['errors'] > 0 for r in rows)}
             for arm, rows in features.items()}
    findings, suggestions = [], []
    if not o:
        return {'state': 'insufficient', 'runs': {'Original': len(o), 'Modified': len(m)}, 'stats': stats, 'findings': [], 'suggestions': []}
    so, sm = stats['Original'], stats['Modified']

    def add(id_, severity, title, observed):
        findings.append({'id': id_, 'severity': severity, 'title': title, 'observed': observed})
    if so['detail_views'] and so['detail_views'] >= 1.5:
        add('detail-dependency', 'high', 'Comparison facts are only on item detail pages',
            f"On Original, agents opened {so['detail_views']} item detail pages per task on average ({so['runs']} runs)"
            + (f"; on Modified, {sm['detail_views']} ({sm['runs']} runs)." if m else '.'))
        suggestions.append({'for': 'detail-dependency', 'text': 'Show the attributes agents compare (deposit, minimum hire, delivery) on listing cards or in a comparison table.',
                            'status': 'tested in this evaluation' if m else 'not measured'})
    if so['listing_returns'] and so['listing_returns'] >= 1:
        add('navigation-loops', 'medium', 'Agents loop between listing and detail pages',
            f"On Original, agents returned to a listing page {so['listing_returns']} times per task and revisited pages {so['revisits']} times per task.")
        suggestions.append({'for': 'navigation-loops', 'text': 'Offer sortable or filterable listings by the attributes in question (e.g. sort by deposit), so one page answers the comparison.',
                            'status': 'not measured'})
    if so['element_searches'] and so['element_searches'] >= 1:
        add('link-enumeration', 'medium', 'Agents enumerate links to discover items',
            f"On Original, agents used element search/extraction {so['element_searches']} times per task to find item links.")
        suggestions.append({'for': 'link-enumeration', 'text': 'Expose the full item list with stable, descriptive links (or structured data) on a single listing page.',
                            'status': 'not measured'})
    if so['policy_views'] and so['policy_views'] >= .5:
        add('policy-detour', 'low', 'Agents look for terms on a separate policy page',
            f"Agents visited the hire-terms page {so['policy_views']} times per task on Original.")
        suggestions.append({'for': 'policy-detour', 'text': 'State per-item terms (deposit, minimum hire) where items are listed instead of only in general terms.', 'status': 'not measured'})
    limited = so['step_limit_runs'] + (sm['step_limit_runs'] if m else 0)
    if limited:
        add('step-budget', 'high', 'Agents ran out of steps',
            f"{so['step_limit_runs']} of {so['runs']} Original runs" + (f" and {sm['step_limit_runs']} of {sm['runs']} Modified runs" if m else '')
            + ' used every allowed step without answering.')
    errored = so['error_runs'] + (sm['error_runs'] if m else 0)
    if errored:
        add('action-errors', 'medium', 'Browser actions failed', f"{errored} runs contained at least one failed browser action.")
    if m and so['steps'] and sm['steps'] is not None:
        change = round(100 * (so['steps'] - sm['steps']) / so['steps'])
        add('modified-effect', 'info', 'Observed difference on the Modified site',
            f"Agents took {so['steps']} steps per task on Original and {sm['steps']} on Modified ({abs(change)}% {'fewer' if change >= 0 else 'more'}). "
            'Observed only; see the comparison rules for whether it meets the pre-registered criteria.')
    return {'state': 'ok', 'runs': {'Original': len(o), 'Modified': len(m)}, 'stats': stats, 'findings': findings, 'suggestions': suggestions,
            'method': 'Deterministic rules over the agent telemetry of finished runs (pages, actions, errors). Suggestions are proposals, not measured outcomes.'}
