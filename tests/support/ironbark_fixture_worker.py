"""Test-only worker: no sockets, and fixture outputs enter before the real grader."""
import asyncio
import socket
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from agent_readiness.investigate.trials import runner, stage
from agent_readiness.live import ironbark_runner
from agent_readiness.suite import core

root, job_id, fail = Path(sys.argv[1]), sys.argv[2], sys.argv[3] == 'fail'
# Enforced at the socket constructor, including any unexpected provider or browser code.
real_socket = socket.socket
def no_socket(*args, **kwargs):
    family = args[0] if args else kwargs.get('family', socket.AF_INET)
    if family != socket.AF_UNIX:
        raise AssertionError('network disabled for fixture preflight')
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
    return {'status': 'completed', 'stop_reason': 'fixture', 'answer': answer,
            'errors': [], 'model_request_count': 1, 'steps': 1, 'usage': []}
runner.attempt = fake_attempt
original = core.evaluate
calls = []
def grade(*args, **kwargs):
    calls.append(1)
    if fail:
        raise RuntimeError('fixture grading failure')
    result = original(*args, **kwargs)
    assert result.answer_valid, 'fixture must exercise the task grader, not only schema validation'
    return result
core.evaluate = grade
try:
    ironbark_runner.run_worker(root, job_id)
finally:
    (root / (job_id + '.grades')).write_text(str(len(calls)))
