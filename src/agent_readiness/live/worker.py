"""Background worker: `python -m agent_readiness.live.worker LIVE_ROOT JOB_ID`. Runs ONE job through the existing investigation pipeline in its own process, so cancellation and timeouts are a
signal away and a crashed browser cannot take the API down. It holds no credential (the manager scrubs the environment) and in M0 executes MOCK mode only. Progress is not reported over a side
channel: the pipeline writes durable stage state into the run directory and the API reads that."""
from __future__ import annotations

import json
import os
import signal
import sys
import threading
import time
from pathlib import Path

TERMINAL = ("completed", "failed", "cancelled", "timed_out")


def job_path(root: Path, job_id: str) -> Path:
    return root / f"{job_id}.job.json"


def read(root: Path, job_id: str) -> dict:
    return json.loads(job_path(root, job_id).read_text())


def update(root: Path, job_id: str, **fields) -> dict:
    """Atomic write; a terminal state is never overwritten by a later one (so a cancel is not turned into a failure by the dying worker)."""
    p = job_path(root, job_id)
    job = json.loads(p.read_text())
    if job.get("state") in TERMINAL and fields.get("state") != job["state"]:
        return job
    job.update(fields)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(job, indent=2))
    os.replace(tmp, p)
    return job


def execute(root: Path, job_id: str) -> None:
    from ..investigate import flow
    from . import mock_investigator
    from .targets import TARGETS
    job = read(root, job_id)
    if job["mode"] != "mock":
        update(root, job_id, state="failed", error="Live model execution is not enabled in this build (M0 runs mock mode only).", finished_at=time.time())
        return
    target = TARGETS[job["target_id"]]
    run, pipe, ctx = flow.build(root, job_id, target.id, mode="mock", options={"snapshot": target.snapshot(), "n_tasks": job.get("n_tasks", 4), "goal": job["goal"]})
    ctx.options["investigator_llm"] = mock_investigator.make(run)
    res = pipe.run(ctx)
    if res.status == "done":
        update(root, job_id, state="completed", finished_at=time.time())
    else:
        update(root, job_id, state="failed", error=f"pipeline stopped: {res.status}" + (f" at {res.stage}" if res.stage else "") + (f": {res.error}" if res.error else ""), finished_at=time.time())


def start_watchdog(root: Path, job_id: str, seconds: float) -> threading.Timer:
    """The worker enforces its OWN deadline, so a job cannot outlive its limit if the API process that spawned it restarted (the API's timer would be gone)."""
    def expire():
        update(root, job_id, state="timed_out", error=f"The evaluation exceeded its {int(seconds)}s limit and was stopped.", finished_at=time.time())
        try:
            os.killpg(os.getpgid(0), signal.SIGKILL)                  # the worker, its browser and any children
        finally:
            os._exit(124)
    t = threading.Timer(seconds, expire)
    t.daemon = True
    t.start()
    return t


def main(argv: list[str]) -> int:
    root, job_id = Path(argv[1]), argv[2]

    def on_term(signum, frame):
        update(root, job_id, state="cancelled", error="Cancelled.", finished_at=time.time())
        os._exit(143)
    signal.signal(signal.SIGTERM, on_term)
    update(root, job_id, state="running", started_at=time.time(), pid=os.getpid())
    for name in ("META_MODEL_API_KEY", "META_API_KEY"):                  # defence in depth: the manager already scrubbed the environment; M0 must never be able to authenticate
        os.environ.pop(name, None)
    start_watchdog(root, job_id, read(root, job_id).get("timeout_seconds", 900))
    try:
        execute(root, job_id)
    except BaseException as exc:                                   # a worker never dies silently: the failure is recorded for the API
        update(root, job_id, state="failed", error=f"{type(exc).__name__}: {str(exc)[:300]}", finished_at=time.time())
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
