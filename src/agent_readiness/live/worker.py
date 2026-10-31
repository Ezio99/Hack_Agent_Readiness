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

TERMINAL = ("completed", "failed", "cancelled", "timed_out", "awaiting_approval", "stopped")      # no further transition by a dying worker; awaiting_approval/stopped never occupy the job slot


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


def sanitize_goal(goal: str) -> str:
    return " ".join("".join(ch for ch in goal if ch.isprintable()).split())[:300]


def stop_kind(error: str) -> str:
    return "budget" if any(w in error.lower() for w in ("budget", "spend gate", "ceiling", " cap", "estimated_cost_limit", "bound violation", "cost limit")) else "error"


def execute(root: Path, job_id: str) -> None:
    job = read(root, job_id)
    if job["mode"] == "live":
        return execute_live(root, job_id, job)
    from ..investigate import flow
    from . import mock_investigator
    from .targets import TARGETS
    if job["mode"] != "mock":
        update(root, job_id, state="failed", error="Unknown evaluation mode.", finished_at=time.time())
        return
    target = TARGETS[job["target_id"]]
    run, pipe, ctx = flow.build(root, job_id, target.id, mode="mock", options={"snapshot": target.snapshot(), "n_tasks": job.get("n_tasks", 4), "goal": job["goal"]})
    ctx.options["investigator_llm"] = mock_investigator.make(run)
    res = pipe.run(ctx)
    if res.status == "done":
        update(root, job_id, state="completed", finished_at=time.time())
    else:
        update(root, job_id, state="failed", error=f"pipeline stopped: {res.status}" + (f" at {res.stage}" if res.stage else "") + (f": {res.error}" if res.error else ""), finished_at=time.time())


def execute_live(root: Path, job_id: str, job: dict) -> None:
    """A user-approved live evaluation: the real model drives task generation, browsing and investigation through the unchanged pipeline. Every paid stage still presents its manifest; the worker
    records the approval ONLY through `grant.Approver` (this job's grant: scope, caps, budget, model), and the ledger ceiling equals the budget. Anything outside the grant stops the run safely."""
    from ..agent import ModelConfig
    from ..investigate import flow
    from . import grant as G
    from .targets import TARGETS
    g = job.get("grant")
    from .jobs import under_test_with_real_endpoint
    if g and under_test_with_real_endpoint(g.get("endpoint", "")):
        update(root, job_id, state="stopped", error="Not started: a test process may not reach a real model endpoint.", stop={"kind": "scope", "stage": None, "reason": "test process, real endpoint"}, finished_at=time.time())
        return
    try:
        approver = G.Approver(g, job_id=job_id, owner=job["owner"], run_id=job_id)
        target = TARGETS[job["target_id"]]
        snap = target.snapshot()
        if snap.sha256 != g["snapshot_sha256"] or g["goal"] != job["goal"] or g["target_id"] != job["target_id"]:
            raise G.GrantRefused("the job no longer matches the grant (site capture, goal or target changed)", "integrity")
    except G.GrantRefused as exc:
        update(root, job_id, state="stopped", error=f"Not started: {exc.reason}", stop={"kind": exc.kind, "stage": None, "reason": exc.reason}, finished_at=time.time())
        return
    smoke = job.get("until") == "taskgen"                                           # operator smoke test: nothing after task generation + freeze may run
    if smoke and list(g["stages"]) != list(G.SMOKE_STAGES):
        update(root, job_id, state="stopped", error="Not started: a smoke job's grant must cover task generation only.", stop={"kind": "scope", "stage": None, "reason": "smoke grant too broad"}, finished_at=time.time())
        return
    budget = g["budget_usd"]
    cfg = ModelConfig(model=g["model"], base_url=g["endpoint"])
    opts = {"snapshot": snap, "n_tasks": job.get("n_tasks", 4), "goals": {"focus": sanitize_goal(job["goal"])}, "focus": sanitize_goal(job["goal"]), "rule_topup": False, "model_config": cfg, "allow_model_calls": True,
            "total_cap_usd": budget, "repeats": 1}
    run, pipe, ctx = flow.build(root, job_id, target.id, mode="live", options=opts)
    run.write_artifact("live-grant", g)                                        # the authorization, kept with the run it covers

    def finish(state: str, **fields) -> None:
        if smoke:
            from . import smoke as S
            try:
                run.write_artifact("smoke-report", S.build_report(run, job, cap_usd=budget, state=state))
            except Exception:                                                        # the report must never mask the real outcome
                pass
        update(root, job_id, state=state, finished_at=time.time(), **fields)
    for _ in range(len(G.LIVE_STAGES) + 2):
        res = pipe.run(ctx, until="freeze" if smoke else None)
        if res.status == "done":
            finish("completed")
            return
        if res.status == "failed":
            err = res.error or "pipeline failed"
            finish("stopped" if stop_kind(err) == "budget" else "failed", error=f"Stopped at {res.stage}: {err}"[:400], stop={"kind": stop_kind(err), "stage": res.stage, "reason": err[:300]})
            return
        manifest = run.artifact(f"manifests/{res.stage}-{res.manifest_sha256[:16]}")
        try:
            approver.decide(run, res.stage, res.manifest_sha256, manifest, run.ledger(budget).committed())
        except G.GrantRefused as exc:
            finish("awaiting_approval", error=f"Stopped before {res.stage}: {exc.reason}. Nothing further was spent; a person must approve this stage.",
                   stop={"kind": exc.kind, "stage": res.stage, "reason": exc.reason, "manifest_sha256": res.manifest_sha256})
            return
    finish("failed", error="The pipeline kept asking for approvals beyond the expected stages; stopped.")


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


def neutralize_dotenv() -> None:
    """Browser Use calls `dotenv.load_dotenv()` when imported and finds the repository `.env` (the operator's model key). A worker must hold exactly the credential the manager gave it (none for a
    mock job): make that call inert before anything imports it."""
    import dotenv
    dotenv.load_dotenv = lambda *args, **kwargs: False


def main(argv: list[str]) -> int:
    neutralize_dotenv()
    root, job_id = Path(argv[1]), argv[2]

    def on_term(signum, frame):
        update(root, job_id, state="cancelled", error="Cancelled.", finished_at=time.time())
        os._exit(143)
    signal.signal(signal.SIGTERM, on_term)
    update(root, job_id, state="running", started_at=time.time(), pid=os.getpid())
    if read(root, job_id)["mode"] != "live":
        for name in ("META_MODEL_API_KEY", "META_API_KEY"):               # defence in depth: the manager already scrubbed the environment; a mock job must never be able to authenticate
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
