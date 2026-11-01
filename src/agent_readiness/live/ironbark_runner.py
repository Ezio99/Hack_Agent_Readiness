"""Local-only operator for the existing Ironbark paired experiment.

Run with ``python -m agent_readiness.live.ironbark_runner`` from the repository root.
No model calls occur during preparation. A paid run requires the exact displayed hash.
"""
from __future__ import annotations

import json
import math
import os
import secrets
import signal
import subprocess
import sys
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from ..agent import ModelConfig
from ..investigate import export as exporter
from ..investigate.run import InvestigationRun
from ..suite.core import canonical_hash
from . import abtest
from .targets import TARGETS

ROOT = Path('scanner-data/ironbark-operator')
SOURCE = abtest.SOURCE
ORIGINAL = 'd2824b210ed9e9d85dac527eb0b4eeb519540a70a7c59ff8690c204ff677538f'
MODIFIED = '40c5d886963c925a7b99ff721d7971d5ebacbc52d0237d9549febe301d74f1ed'
TASKS_HASH = '1c0f546ef0b0588cdc6a81ab7abb6d0e70bbe9d01487b4f9856ccd8ed979dd95'
RULE_HASH = '56c6667a3183416da81a81157d7b615392b7f85ce6b33e9704d9ed5b5981a482'
TIMEOUT = 1800


def write(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(obj, indent=2))
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)


def caps_checked(caps):
    if not isinstance(caps, dict) or set(caps) != {'placebo_arm', 'patched_arm'}:
        raise ValueError('Both arm caps are required')
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or not 0 < v <= 1 for v in caps.values()):
        raise ValueError('Each cap must be greater than zero and at most US$1.00')
    return caps


def driver(root, job_id, caps, approve=frozenset(), paid=False):
    return abtest.drive(SOURCE, root, job_id, cfg=ModelConfig(), snapshot=TARGETS['ironbark'].snapshot(),
                        approve=approve, allow_model_calls=paid, scroll_sensitivity=True, caps=caps)


def validate_manifest(m, caps):
    ids = m.get('task_ids', [])
    arms = m.get('arms', [])
    order = m.get('execution_order', [])
    c = m.get('caps_usd', {})
    if (m.get('stage') != 'post_trials' or len(ids) != 4 or len(set(ids)) != 4 or len(arms) != 1
        or set(arms[0].get('task_ids', [])) != set(ids) or arms[0].get('excluded')
        or arms[0].get('patched_snapshot_sha256') != MODIFIED
        or m.get('placebo', {}).get('snapshot_sha256') != ORIGINAL
        or set(order) != {f'{arm}:{task}:r1' for arm in ('placebo', 'patched') for task in ids} or len(order) != 8
        or m.get('tasks_manifest_sha256') != TASKS_HASH or m.get('evaluation_rule_sha256') != RULE_HASH
        or m.get('agent_profile') != 'suite-v2-compat2' or m.get('model') != ModelConfig().model
        or m.get('endpoint') != ModelConfig().base_url or m.get('repeats') != 1
        or c.get('placebo_arm') != caps['placebo_arm'] or c.get('patched_arm') != caps['patched_arm']
        or not c.get('combined_cap_fits_ceiling')):
        raise ValueError('Paired manifest does not match the approved suite, snapshots, profile, limits or caps')


def prepare(root, caps):
    caps_checked(caps)
    job_id = 'paired-' + uuid.uuid4().hex
    out = driver(root, job_id, caps)
    if out.get('status') != 'awaiting_approval' or out.get('stage') != 'apply_fix':
        raise ValueError('Could not prepare the local snapshot')
    out = driver(root, job_id, caps, frozenset({out['manifest_sha256']}))
    if out.get('status') != 'awaiting_approval' or out.get('stage') != 'post_trials':
        raise ValueError('Could not prepare the paired manifest')
    manifest = out['manifest']
    validate_manifest(manifest, caps)
    run = InvestigationRun(root / job_id)
    tasks = run.artifact('tasks-manifest')['tasks']
    job = {'id': job_id, 'state': 'awaiting_approval', 'created_at': time.time(), 'caps': caps,
           'manifest_sha256': out['manifest_sha256'], 'manifest': manifest,
           'tasks': [{k: t.get(k) for k in ('task_id', 'question', 'start_path', 'limits')} for t in tasks],
           'timeout_seconds': TIMEOUT}
    write(root / (job_id + '.json'), job)
    return job


def progress(root, job):
    d = root / job['id']
    rows = []
    for arm in ('placebo', 'patched'):
        for task in job['tasks']:
            pattern = f"{arm}-*-{task['task_id']}-r1"
            files = list((d / 'artifacts' / 'trials').glob(pattern + '.json'))
            quarantined = list((d / 'artifacts' / 'trials-quarantine').glob(pattern + '.json'))
            running = list((d / 'trial-data').glob(pattern))
            row = {'arm': 'Original' if arm == 'placebo' else 'Modified', 'task_id': task['task_id'], 'state': 'pending'}
            if files:
                try:
                    t = json.loads(files[0].read_text())
                    status = t['outcome']['run_status']
                    from ..investigate.trials.stage import VOID_STATUSES
                    row.update(state='failed' if status in VOID_STATUSES else 'completed', outcome=status,
                               strict_pass=t.get('evaluation', {}).get('passed'), evidence_supported=t.get('evaluation', {}).get('evidence_backed'),
                               requests=t.get('metrics', {}).get('model_requests'))
                    if status in VOID_STATUSES:
                        row.update(strict_pass=None, evidence_supported=None)
                except (OSError, ValueError, KeyError):
                    row['state'] = 'failed'
            elif quarantined:
                row['state'] = 'failed'
            elif running:
                row['state'] = 'running' if job['state'] == 'running' else 'incomplete'
            rows.append(row)
    return rows


def run_worker(root, job_id):
    path = root / (job_id + '.json')
    job = json.loads(path.read_text())
    caps_checked(job['caps'])
    validate_manifest(job['manifest'], job['caps'])
    if canonical_hash(job['manifest']) != job['manifest_sha256'] or job['state'] != 'running':
        raise ValueError('Approval or manifest mismatch')
    out = driver(root, job_id, job['caps'], approve=frozenset({job['manifest_sha256']}), paid=True)
    write(root / (job_id + '.result.json'), {'status': out.get('status'), 'stage': out.get('stage')})


class Manager:
    def __init__(self, root=ROOT, timeout=TIMEOUT):
        self.root, self.timeout = Path(root), timeout
        self.root.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.process = None
        self.active = None

    def get(self, job_id):
        if not job_id.startswith('paired-') or len(job_id) != 39 or any(c not in '0123456789abcdef' for c in job_id[7:]):
            raise ValueError('Invalid job id')
        job = json.loads((self.root / (job_id + '.json')).read_text())
        rows = progress(self.root, job)
        summary = {}
        for arm in ('Original', 'Modified'):
            subset = [r for r in rows if r['arm'] == arm]
            summary[arm] = {'completed': sum(r['state'] == 'completed' for r in subset),
                            'strict_passes': sum(r.get('strict_pass') is True for r in subset),
                            'evidence_supported_passes': sum(r.get('evidence_supported') is True for r in subset),
                            'agent_requests': sum(r.get('requests') or 0 for r in subset),
                            'incomplete': sum(r['state'] != 'completed' for r in subset)}
        result_path = self.root / (job_id + '.result.json')
        detail = json.loads(result_path.read_text()) if result_path.exists() else None
        return {**job, 'progress': rows, 'summary': summary, 'worker_result': detail}

    def start(self, job_id, digest, amount):
        with self.lock:
            if self.active:
                raise ValueError('A job is already running')
            job = self.get(job_id)
            caps_checked(job['caps'])
            validate_manifest(job['manifest'], job['caps'])
            if (job['state'] != 'awaiting_approval' or digest != job['manifest_sha256'] or canonical_hash(job['manifest']) != digest
                or isinstance(amount, bool) or not isinstance(amount, (float, int)) or not math.isfinite(amount)
                or abs(amount - sum(job['caps'].values())) > 1e-9):
                raise ValueError('Exact manifest hash and combined spending confirmation required')
            job.pop('progress', None)
            job.pop('summary', None)
            job.pop('worker_result', None)
            job.update(state='running', started_at=time.time())
            write(self.root / (job_id + '.json'), job)
            try:
                self.process = subprocess.Popen([sys.executable, '-m', 'agent_readiness.live.ironbark_runner', '--worker', str(self.root), job_id, str(os.getpid())],
                                                start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                job.update(state='failed', finished_at=time.time(), error='Worker could not start')
                write(self.root / (job_id + '.json'), job)
                raise
            self.active = job_id
            threading.Thread(target=self._monitor, args=(job_id, self.process), daemon=True).start()

    def _monitor(self, job_id, process):
        try:
            code = process.wait(timeout=self.timeout)
            state = 'failed'
            result_path = self.root / (job_id + '.result.json')
            if code == 0 and result_path.exists():
                result = json.loads(result_path.read_text())
                rows = self.get(job_id)['progress']
                state = 'completed' if result.get('status') == 'done' and len(rows) == 8 and all(row['state'] == 'completed' for row in rows) else 'failed'
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
            state = 'timed_out'
        with self.lock:
            job = self.get(job_id)
            job.pop('progress', None)
            job.pop('summary', None)
            job.pop('worker_result', None)
            if job['state'] == 'running':
                job.update(state=state, finished_at=time.time())
                write(self.root / (job_id + '.json'), job)
            self.active = None
            self.process = None

    def cancel(self, job_id):
        with self.lock:
            if self.active != job_id or not self.process:
                raise ValueError('Job is not running')
            job = self.get(job_id)
            job.pop('progress', None)
            job.pop('summary', None)
            job.pop('worker_result', None)
            job.update(state='cancelled', finished_at=time.time())
            write(self.root / (job_id + '.json'), job)
            try:
                os.killpg(self.process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass

    def export(self, job_id):
        self.get(job_id)
        data = exporter.export_run(self.root / job_id)
        exporter.check_clean(data)
        return data


PAGE = '''<!doctype html><html><head><meta charset="utf-8"><title>Ironbark Evaluation Runner</title>
<style>body{font:16px system-ui;max-width:1050px;margin:2rem auto;padding:0 1rem;color:#152638}button,input{font:inherit;padding:.5rem}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f2f5f7;padding:1rem}section{margin:2rem 0}label{display:inline-block;margin-right:1rem}</style></head><body>
<h1>Ironbark Evaluation Runner</h1><p>Local operator app. Preparation is free. Live execution sends requests to Meta and requires your explicit confirmation. Observed differences do not establish causation.</p>
<section><h2>1. Prepare paired evaluation</h2><p>Set proposed caps in US dollars (maximum $1 per arm). This creates a separate run and prepares the frozen suite and snapshots.</p>
<label>Original cap <input id="original" type="number" min="0.01" max="1" step="0.01"></label><label>Modified cap <input id="modified" type="number" min="0.01" max="1" step="0.01"></label><button id="prepare">Prepare review</button></section>
<section><h2>2. Review configuration</h2><pre id="config">No run prepared.</pre><label>Paste exact manifest SHA-256 <input id="digest" size="64"></label><label>Confirm combined cap US$ <input id="amount" type="number" step="0.01"></label><button id="start">Approve and start paid evaluation</button></section>
<section><h2>3. Execution and results</h2><label>Existing run ID <input id="resume" size="45"></label><button id="load">Load run</button> <button id="cancel">Cancel running evaluation</button> <button id="comparison">Show assessments</button> <button id="export">Download sanitized export</button><p id="message"></p><pre id="status"></pre><pre id="assessment"></pre><p>Individual completed outcomes and request counts are shown above. Incomplete or void executions are not passes. Full comparisons and methodology are in the sanitized export.</p></section>
<script>
const token='TOKEN'; let job=null;
async function api(path, body){let r=await fetch(path,{method:body?'POST':'GET',headers:{'Content-Type':'application/json','X-Operator-Token':token},body:body?JSON.stringify(body):undefined});let x=await r.json();if(!r.ok)throw Error(x.error||'Request failed');return x}
function msg(e){document.getElementById('message').textContent=String(e)}
document.getElementById('prepare').onclick=async()=>{try{msg('Preparing; this can take a minute.');job=await api('/prepare',{placebo_arm:Number(document.getElementById('original').value),patched_arm:Number(document.getElementById('modified').value)});document.getElementById('config').textContent=JSON.stringify(job,null,2);msg('Review the complete manifest and tasks before approving.');}catch(e){msg(e)}};
document.getElementById('start').onclick=async()=>{try{if(!job)throw Error('Prepare a run first');await api('/start',{id:job.id,hash:document.getElementById('digest').value,amount:Number(document.getElementById('amount').value)});msg('Evaluation started.');}catch(e){msg(e)}};
document.getElementById('cancel').onclick=async()=>{try{await api('/cancel',{id:job.id});msg('Cancelled.');}catch(e){msg(e)}};
document.getElementById('load').onclick=async()=>{try{job=await api('/status?id='+encodeURIComponent(document.getElementById('resume').value));document.getElementById('config').textContent=JSON.stringify(job,null,2);msg('Run loaded.')}catch(e){msg(e)}};
document.getElementById('comparison').onclick=async()=>{try{let x=await api('/export?id='+encodeURIComponent(job.id));document.getElementById('assessment').textContent=JSON.stringify(x.evaluation||{state:'unavailable'},null,2)}catch(e){msg(e)}};
document.getElementById('export').onclick=async()=>{try{let x=await api('/export?id='+encodeURIComponent(job.id));let a=document.createElement('a');a.href=URL.createObjectURL(new Blob([JSON.stringify(x,null,2)],{type:'application/json'}));a.download=job.id+'-sanitized.json';a.click();URL.revokeObjectURL(a.href)}catch(e){msg(e)}};
setInterval(async()=>{if(job){try{let x=await api('/status?id='+encodeURIComponent(job.id));document.getElementById('status').textContent=JSON.stringify({state:x.state,summary:x.summary,progress:x.progress,worker_result:x.worker_result},null,2)}catch(e){msg(e)}}},2000);
</script></body></html>'''


def serve(port=8765):
    import fcntl
    from urllib.parse import urlsplit, parse_qs
    manager = Manager()
    lock_file = (manager.root / '.operator.lock').open('a')
    fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
    for path in manager.root.glob('paired-*.json'):
        if path.name.endswith('.result.json'):
            continue
        try:
            job = json.loads(path.read_text())
            if job.get('state') == 'running':
                job.update(state='interrupted', finished_at=time.time())
                write(path, job)
        except (OSError, ValueError):
            continue
    token = secrets.token_urlsafe(32)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def respond(self, code, data, content_type='application/json'):
            data = data.encode() if isinstance(data, str) else data
            self.send_response(code)
            self.send_header('Content-Type', content_type)
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(data)

        def handle_request(self):
            host = self.headers.get('Host', '')
            if host not in (f'127.0.0.1:{port}', f'localhost:{port}'):
                return self.respond(403, '{"error":"Invalid host"}')
            p = urlsplit(self.path)
            if self.command == 'GET' and p.path == '/':
                return self.respond(200, PAGE.replace('TOKEN', token), 'text/html; charset=utf-8')
            if not secrets.compare_digest(self.headers.get('X-Operator-Token', ''), token):
                return self.respond(403, '{"error":"Invalid operator token"}')
            try:
                body = {}
                if self.command == 'POST':
                    n = int(self.headers.get('Content-Length', '0'))
                    if n <= 0 or n > 4096:
                        raise ValueError('Invalid request length')
                    body = json.loads(self.rfile.read(n))
                job_id = body.get('id') or parse_qs(p.query).get('id', [''])[0]
                if self.command == 'POST' and p.path == '/prepare':
                    if manager.active:
                        raise ValueError('A job is already running')
                    result = prepare(manager.root, body)
                elif self.command == 'POST' and p.path == '/start':
                    manager.start(job_id, body.get('hash'), body.get('amount'))
                    result = {'ok': True}
                elif self.command == 'POST' and p.path == '/cancel':
                    manager.cancel(job_id)
                    result = {'ok': True}
                elif self.command == 'GET' and p.path == '/status':
                    result = manager.get(job_id)
                elif self.command == 'GET' and p.path == '/export':
                    result = manager.export(job_id)
                else:
                    return self.respond(404, '{"error":"Not found"}')
                self.respond(200, json.dumps(result))
            except (ValueError, KeyError, OSError, TypeError) as exc:
                self.respond(400, json.dumps({'error': str(exc)}))

        do_GET = handle_request
        do_POST = handle_request

    server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    print(f'Open http://127.0.0.1:{port}/', flush=True)
    try:
        server.serve_forever()
    finally:
        if manager.active:
            manager.cancel(manager.active)
        server.server_close()
        lock_file.close()


def main():
    if len(sys.argv) == 5 and sys.argv[1] == '--worker':
        # Linux: ensure an unexpectedly killed operator cannot leave a paid worker running.
        import ctypes
        libc = ctypes.CDLL(None, use_errno=True)
        if libc.prctl(1, signal.SIGKILL) != 0 or os.getppid() != int(sys.argv[4]):
            raise SystemExit('Cannot establish operator lifetime guard')
        try:
            run_worker(Path(sys.argv[2]), sys.argv[3])
        except Exception as exc:
            # Do not copy exception text: provider errors can contain sensitive data.
            write(Path(sys.argv[2]) / (sys.argv[3] + '.result.json'),
                  {'status': 'failed', 'error_type': type(exc).__name__})
            raise SystemExit(1) from None
    elif len(sys.argv) == 1:
        serve()
    else:
        raise SystemExit('Usage: python -m agent_readiness.live.ironbark_runner')


if __name__ == '__main__':
    main()
