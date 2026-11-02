"""Test-only hosted worker: no sockets; scripted outputs enter before the real grader (see ironbark_fixture_worker)."""
import socket
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from agent_readiness.hosted import paired
from agent_readiness.hosted.admission import Admission
from agent_readiness.investigate.trials import runner, stage
from agent_readiness.suite import core

root, job_id, db, fail_rep = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3]), int(sys.argv[4])
real_socket = socket.socket
def no_socket(*args, **kwargs):
    family = args[0] if args else kwargs.get('family', socket.AF_INET)
    if family != socket.AF_UNIX:
        raise AssertionError('network disabled for fixture worker')
    return real_socket(*args, **kwargs)
socket.socket = no_socket
stage.preflight = lambda *_: 'fixture-only'

@asynccontextmanager
async def fake_server(_mirror):
    yield 'http://fixture.invalid'
runner.serve_app = fake_server
runner.create_model = lambda *a, **kw: object()
async def fake_attempt(*args, **kwargs):
    prompt = args[0].prompt
    answer = {'answer': 'fixture incorrect'} if 'highest refundable deposit' in prompt else {'answers': ['fixture incorrect']}
    return {'status': 'completed', 'stop_reason': 'fixture', 'answer': answer, 'errors': [], 'model_request_count': 2, 'steps': 3, 'usage': []}
runner.attempt = fake_attempt
calls = []
original = core.evaluate
def grade(*args, **kwargs):
    calls.append(1)
    return original(*args, **kwargs)
core.evaluate = grade

def before(rep):
    if rep['index'] == fail_rep:
        raise RuntimeError('fixture repetition failure')
try:
    paired.run_job(root, job_id, Admission.open_existing(db), mode='rehearsal', before_rep=before)
except Exception:
    raise SystemExit(1)
finally:
    (root / (job_id + '.grades')).write_text(str(len(calls)))
