"""Operator commands, run inside the app container (talks to the local service only).

    python -m agent_readiness.hosted.admin health
    python -m agent_readiness.hosted.admin start --repetitions 1     # needs the operator token file
    python -m agent_readiness.hosted.admin watch eval-...            # prints progress until terminal
    python -m agent_readiness.hosted.admin list
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE = f"http://127.0.0.1:{os.environ.get('AR_PORT', '8080')}"


def call(path: str, body: dict | None = None, token: bytes | None = None):
    req = urllib.request.Request(BASE + path, data=None if body is None else json.dumps(body).encode(), method='GET' if body is None else 'POST',
                                 headers={'Content-Type': 'application/json', **({'Authorization': 'Bearer ' + token.decode()} if token else {})})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read() or b'null')
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read() or b'{}')


def line(job: dict) -> str:
    done = sum(t['state'] in ('completed', 'failed') for r in job['reps'] for t in r['tasks'])
    s = job['summary']
    return (f"{job['state']:<11} {done}/{8 * (job['repetitions'] or 0)} runs | reps {[r['state'] for r in job['reps']]} | "
            f"Original {s['Original']['evidence_supported_passes']}/{s['Original']['completed']} ({s['Original']['requests_total']} req) | "
            f"Modified {s['Modified']['evidence_supported_passes']}/{s['Modified']['completed']} ({s['Modified']['requests_total']} req)")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog='agent_readiness.hosted.admin')
    sub = ap.add_subparsers(dest='cmd', required=True)
    sub.add_parser('health')
    sub.add_parser('list')
    st = sub.add_parser('start')
    st.add_argument('--repetitions', type=int, choices=(1, 3, 5), default=1)
    st.add_argument('--watch', action='store_true')
    w = sub.add_parser('watch')
    w.add_argument('job')
    a = ap.parse_args(argv)
    if a.cmd == 'health':
        code, body = call('/api/health')
        print(json.dumps(body, indent=2))
        return 0 if code == 200 and body.get('evaluations') == 'enabled' else 1
    if a.cmd == 'list':
        for j in call('/api/ironbark/jobs')[1]:
            print(j['id'], j['state'], j['mode'], f"{j['repetitions']}x", time.strftime('%Y-%m-%d %H:%M', time.localtime(j['created_at'])))
        return 0
    if a.cmd == 'start':
        token = Path(os.environ.get('AR_OPERATOR_TOKEN_FILE', '/run/secrets/operator_token')).read_bytes().strip()
        code, body = call('/api/ironbark/jobs', {'repetitions': a.repetitions}, token)
        print(json.dumps(body))
        if code != 202:
            return 1
        if not a.watch:
            return 0
        a.job = body['id']
    last = None
    while True:
        code, job = call(f'/api/ironbark/jobs/{a.job}')
        if code != 200:
            print(json.dumps(job))
            return 1
        text = line(job)
        if text != last:
            print(time.strftime('%H:%M:%S'), text, flush=True)
            last = text
        if job['state'] in ('completed', 'failed', 'timed_out', 'interrupted'):
            return 0 if job['state'] == 'completed' else 1
        time.sleep(5)


if __name__ == '__main__':
    sys.exit(main())
