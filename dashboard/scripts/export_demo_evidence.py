"""Export the recorded Muse Spark evaluation used by the cinematic Demo and the homepage.

Reads ONLY the public, allowlisted projection that the hosted API already serves
(`/api/ironbark/...`: job status, per-trial telemetry, screenshots, insights and the
sanitized export) and writes a reviewed snapshot into `src/site/evidence/`:

  eval-9aaac35c.json   job summary, tasks, every trial's steps, insights, comparison verdicts
  frames/<sha>.webp    de-duplicated screenshots for the selected trials (WebP, same pixels size)

No model call, no write to the service. Typical use against a local read-only server
(AR_HOSTED_MODE=disabled) over a copy of the hosted data:

  python scripts/export_demo_evidence.py --api http://127.0.0.1:8765 \
      --job eval-9aaac35ca488c2bf951e01e58746604a --frames original:1 modified:1 modified:2
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import urllib.request
from pathlib import Path

from PIL import Image

STEP_FIELDS = ('step', 'path', 'goal', 'memory', 'assessment', 'actions', 'error', 'done')


def get(api: str, path: str, raw: bool = False):
    with urllib.request.urlopen(f'{api}{path}', timeout=30) as r:
        body = r.read()
    return body if raw else json.loads(body)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--api', required=True)
    ap.add_argument('--job', required=True)
    ap.add_argument('--frames', nargs='*', default=['original:1', 'modified:1'], help='arm:task trials whose screenshots are bundled')
    ap.add_argument('--out', default=str(Path(__file__).resolve().parent.parent / 'src' / 'site' / 'evidence'))
    a = ap.parse_args()
    out = Path(a.out)
    (out / 'frames').mkdir(parents=True, exist_ok=True)
    base = f'/api/ironbark/jobs/{a.job}'

    config = get(a.api, '/api/ironbark/config')
    job = get(a.api, base)
    insights = get(a.api, f'{base}/insights')
    if job['state'] != 'completed' or job['mode'] != 'live':
        raise SystemExit('only a completed live evaluation can be exported for the demo')
    rep = job['reps'][0]
    export = get(a.api, f'{base}/repetitions/{rep["index"]}/export')
    if export['evidence_origin']['provider'] != 'real_model':
        raise SystemExit('evidence origin is not real_model')
    framed = {tuple(f.split(':')) for f in a.frames}

    trials, written = [], {}
    for arm in ('original', 'modified'):
        for task in (1, 2, 3, 4):
            t = get(a.api, f'{base}/repetitions/{rep["index"]}/trials/{arm}/{task}')
            steps = []
            for s in t['steps']:
                row = {k: s.get(k) for k in STEP_FIELDS}
                row['frame'] = None
                if (arm, str(task)) in framed and s.get('screenshot'):
                    png = get(a.api, f'{base}/repetitions/{rep["index"]}/trials/{arm}/{task}/screenshots/{s["screenshot"]}', raw=True)
                    key = hashlib.sha256(png).hexdigest()[:12]
                    if key not in written:
                        img = Image.open(io.BytesIO(png)).convert('RGB')
                        buf = io.BytesIO()
                        img.save(buf, 'WEBP', quality=80, method=6)
                        (out / 'frames' / f'{key}.webp').write_bytes(buf.getvalue())
                        written[key] = img.size
                    row['frame'] = key
                steps.append(row)
            trials.append({'arm': arm, 'task': task, 'question': t.get('question'), 'state': t['state'], 'errors': t.get('errors', []), 'steps': steps})

    result = export['evaluation']['results'][0]
    data = {
        'source': {
            'job': job['id'], 'repetition': rep['index'], 'mode': job['mode'], 'evidence_origin': export['evidence_origin']['provider'],
            'model': config['model'], 'agent_profile': config['agent_profile'],
            'created_at': job['created_at'], 'started_at': job['started_at'], 'finished_at': job['finished_at'],
            'note': 'Public allowlisted projection served by the hosted API; screenshots re-encoded as WebP for the web, pixels otherwise unchanged.',
        },
        'tasks': [{'task': t['task'], 'question': t['question'], 'limits': t.get('limits')} for t in config['tasks']],
        'rows': rep['tasks'],
        'summary': job['summary'],
        'assessment': rep['assessment'],
        'frozen_rule': {k: result.get(k) for k in ('verdict', 'reason', 'pairs', 'pass_delta', 'request_change', 'p_pass', 'p_requests')}
                       | {'id': export['evaluation']['rule']['id'], 'alpha': export['evaluation']['rule']['alpha'], 'min_pairs': export['evaluation']['rule']['min_pairs']},
        'exploratory_rule': {'id': export['evaluation']['exploratory']['rules_id'], 'verdict': export['evaluation']['exploratory']['verdict']},
        'change': {k: export['proposals'][0].get(k) for k in ('label', 'owner_selected', 'exploratory', 'validation')},
        'insights': {k: insights.get(k) for k in ('runs', 'stats', 'findings', 'suggestions', 'method', 'final')},
        'trials': trials,
        'frames': {k: {'width': w, 'height': h} for k, (w, h) in written.items()},
    }
    (out / 'eval-9aaac35c.json').write_text(json.dumps(data, indent=1, ensure_ascii=False) + '\n')
    print(f'wrote {len(trials)} trials, {len(written)} frames to {out}')


if __name__ == '__main__':
    main()
