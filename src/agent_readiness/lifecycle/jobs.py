"""Lifecycle evaluation jobs launched from the product (M8): one worker subprocess per job, the hosted executor's process model (new session,
parent-death signal, hard timeout, process-group kill), the hosted admission's single evaluation slot and durable ceiling.

    python -m agent_readiness.lifecycle.jobs RUNS_ROOT STORE_ROOT JOB_ID PARENT_PID ADMISSION_DB      (started by LifecycleExecutor only)

Modes:
  rehearsal   the Stage B runner end to end (prepare -> execute -> report) on the approved, frozen suite's manifest: real Chromium in the network
              jail, the loopback dev provider standing in for the model (NOT a model), every non-loopback socket refused in the worker. Reserves
              US$0 against the hosted ceiling (it still holds the single evaluation slot).
  paid        NOT launchable from the product in this release (`PAID_WEB_LAUNCH = False`; the API refuses it before anything is reserved). The
              coordination a paid run would use is implemented and tested: `admit_paid` verifies the owner's write-once PaidAuthorization against
              the store (exact frozen suite with a real owner approval, exact manifest, trial count, cap, pinned agent), refuses a used experiment
              ledger, and reserves the manifest's worst case against the hosted ceiling before the runner's own per-request reserve-before-send
              gate and per-experiment ledger take over. Nothing in this module sends a model request."""
from __future__ import annotations

import json
import os
import re
import secrets
import signal
import subprocess
import sys
import time
from decimal import Decimal
from pathlib import Path

JOB_ID = re.compile(r"lc-[0-9a-f]{32}")
MODES = ("rehearsal", "paid")
PAID_WEB_LAUNCH = False
TIMEOUT_SECONDS = 3 * 3600
TERMINAL = ("completed", "failed", "timed_out", "interrupted")


def new_id() -> str:
    return "lc-" + secrets.token_hex(16)


def _write(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=1, sort_keys=True))
    os.replace(tmp, path)


def job_path(runs_root: Path, job_id: str) -> Path:
    if not JOB_ID.fullmatch(job_id):
        raise ValueError("invalid job id")
    return Path(runs_root) / "jobs" / f"{job_id}.json"


def new_job(runs_root: Path, job_id: str, *, manifest_sha: str, mode: str, request: dict, label: str) -> dict:
    if mode not in MODES:
        raise ValueError("unsupported mode")
    job = {"id": job_id, "mode": mode, "manifest_sha256": manifest_sha, "request": request, "label": label, "state": "reserved",
           "created_at": time.time(), "started_at": None, "finished_at": None, "runs": {}, "planned": None, "stopped": None, "error": None}
    _write(job_path(runs_root, job_id), job)
    return job


def load_job(runs_root: Path, job_id: str) -> dict:
    job = json.loads(job_path(runs_root, job_id).read_text())
    if job.get("id") != job_id:
        raise ValueError("job identity mismatch")
    return job


def update_job(runs_root: Path, job_id: str, **fields) -> dict:
    job = load_job(runs_root, job_id)
    job.update(fields)
    _write(job_path(runs_root, job_id), job)
    return job


# ------------------------------------------------------------------------------------------------------------------------------- paid coordination
def admit_paid(admission, store, manifest_sha: str, authorization_path: Path, *, job_id: str, client: str, ledger_root: Path | None = None) -> dict:
    """Coordinate the two durable spend systems for ONE paid lifecycle run (never called by the product in this release; tested with fixtures):
      1. the owner's PaidAuthorization must verify against the store and this manifest (evalruns.authorization.verify; nothing relaxed);
      2. the experiment's fixed ledger must be unused (a used ledger means trials may have been attempted: never re-run, never reset);
      3. the manifest's worst-case reservation is reserved against the hosted admission ceiling, atomically with the single evaluation slot.
    The runner then enforces reserve-before-send per request, the per-trial cap, the scope cap and the trial count from the experiment ledger."""
    from ..evalruns import authorization as AU
    from ..evalruns import runner as RN
    auth = AU.load(authorization_path)
    manifest = store.get("manifest", manifest_sha)
    planned = sum(1 for _ in _planned_trials(store, manifest))
    problems = AU.verify(auth, store, manifest_sha, planned_trials=planned)
    if problems:
        raise PermissionError("authorisation mismatch; nothing reserved: " + "; ".join(problems))
    ledger = Path(ledger_root) / auth.experiment_id if ledger_root else AU.ledger_dir(auth.experiment_id)
    if (ledger / "ledger.jsonl").exists() and (ledger / "ledger.jsonl").stat().st_size > 0:
        raise PermissionError("the experiment ledger has entries: a paid experiment id is used once; trials that ever reserved are never re-run")
    worst = Decimal(str(manifest.budget["worst_case_reservation_usd"])) * 1_000_000
    admission.reserve_amount(job_id, client, int(worst.to_integral_value(rounding="ROUND_CEILING")))
    return {"authorization_sha256": auth.sha256, "experiment_id": auth.experiment_id, "planned_trials": planned, "reserved_microusd": int(worst.to_integral_value(rounding="ROUND_CEILING")),
            "per_request_cap_usd": manifest.budget["per_request_cap_usd"], "cap_usd": auth.cap_usd, "runner": RN.SCHEMA}


def _planned_trials(store, manifest):
    from ..evalruns.manifest import suite_tasks
    _, _, tasks = suite_tasks(store, manifest.frozen_suite_sha256)
    det = [t for t in tasks if t.spec.verifiability == "deterministic" and t.condition in manifest.conditions]
    for _ in range(manifest.repetitions):
        for _t in det:
            for _v in manifest.variants:
                yield 1


# ------------------------------------------------------------------------------------------------------------------------------- executor
class LifecycleExecutor:
    """Launches the worker for one job and waits for it (call from the job's own thread)."""

    def __init__(self, runs_root: Path, store_root: Path, admission, *, command=None, timeout: int = TIMEOUT_SECONDS):
        self.runs_root, self.store_root, self.admission = Path(runs_root), Path(store_root), admission
        self.command = command or (lambda job_id: [sys.executable, "-m", "agent_readiness.lifecycle.jobs", str(self.runs_root), str(self.store_root), job_id,
                                                   str(os.getpid()), str(admission.path)])
        self.timeout = timeout
        self.available = True

    def run(self, job_id: str) -> None:
        update_job(self.runs_root, job_id, started_at=time.time(), state="running")
        import ctypes
        libc = ctypes.CDLL(None, use_errno=True)
        proc = subprocess.Popen(self.command(job_id), start_new_session=True, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                preexec_fn=lambda: libc.prctl(1, signal.SIGKILL))
        try:
            code = proc.wait(timeout=self.timeout)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            proc.wait()
            update_job(self.runs_root, job_id, state="timed_out", finished_at=time.time(), error="the evaluation exceeded its time limit and was stopped")
            raise
        job = load_job(self.runs_root, job_id)
        if code != 0 or job.get("state") != "completed":
            update_job(self.runs_root, job_id, state="failed", finished_at=time.time(), error=job.get("error") or f"worker exited with status {code}")
            raise RuntimeError("lifecycle worker failed")


# ------------------------------------------------------------------------------------------------------------------------------- worker
def _public_error(exc: BaseException) -> str:
    text = f"{type(exc).__name__}: {exc}"
    text = re.sub(r"/[^\s'\"]+", "[path]", text)
    return text[:300]


def harden_jail(runs_root: Path, store_root: Path) -> list[str]:
    """The manifest declares the evalruns jail policy (hidden: ~/Projects, ~/.ssh, ~/.claude, /root), which on a workstation hides the checkout.
    In the product container the application, data and secret directories live elsewhere, so this worker process hides, IN ADDITION, the
    deployment jail policy's own hidden paths (AGENT_READINESS_BROWSER_JAIL: /app, /data, /run/secrets, ...) and the lifecycle store and runs
    roots. Hiding more never weakens the declared boundary; the extra paths are recorded on the job."""
    from ..evalruns import manifest as MF
    extra = [str(Path(store_root).resolve()), str(Path(runs_root).resolve())]
    pol = os.environ.get("AGENT_READINESS_BROWSER_JAIL")
    if pol and Path(pol).is_file():
        extra = list(json.loads(Path(pol).read_text()).get("hide") or []) + extra
    MF.JAIL_POLICY = {**MF.JAIL_POLICY, "hide": list(dict.fromkeys(list(MF.JAIL_POLICY["hide"]) + extra))}
    return extra


def run_job(runs_root: Path, store_root: Path, job_id: str, admission) -> dict:
    from ..evalruns import runner as RN
    from ..suites.store import WriteOnceStore
    job = load_job(runs_root, job_id)
    held = admission.get(job_id)
    if not held or held["state"] != "running":
        raise PermissionError("the job does not hold a running admission")
    if job["mode"] != "rehearsal":
        raise PermissionError("paid lifecycle execution is not launchable from the product in this release")
    if held["reserved_microusd"] != 0:
        raise PermissionError("a rehearsal reserves exactly US$0")
    from ..hosted import paired
    paired._loopback_only_sockets()                                         # no provider can be contacted from this process
    store = WriteOnceStore(store_root)
    runs = RN.prepare(store, job["manifest_sha256"], Path(runs_root) / "runs", mode="rehearsal", label=job_id[3:13])
    manifest = store.get("manifest", job["manifest_sha256"])
    update_job(runs_root, job_id, runs={c: str(r.dir.relative_to(Path(runs_root))) for c, r in runs.items()},
               planned=sum(len(RN.steps(r, manifest)) for r in runs.values()), state="running")
    hidden = harden_jail(runs_root, store_root)
    update_job(runs_root, job_id, runtime_jail_hides=hidden)
    stopped = []
    for c, r in runs.items():
        out = RN.execute(r, store)
        if out.get("stopped"):
            stopped.append(f"{c}: {out['stopped']}")
    at = time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime())
    doc = RN.report(store, job["manifest_sha256"], runs, created_at=at)
    pub = RN.public_report(doc)
    _write(Path(runs_root) / "reports" / f"{job_id}.public.json", pub)
    audit = RN.audit_public(store, job["manifest_sha256"], runs, [Path(runs_root) / "reports" / f"{job_id}.public.json"])
    state = "completed" if audit["clean"] and not stopped else "failed"
    return update_job(runs_root, job_id, state=state, finished_at=time.time(), stopped="; ".join(stopped) or None,
                      run_results=[r["sha256"] for r in doc["run_results"]], audit_clean=audit["clean"],
                      error=None if state == "completed" else ("the public leak audit failed" if not audit["clean"] else "the run stopped early: " + "; ".join(stopped)))


def worker_main(argv: list[str]) -> int:
    from ..hosted.admission import Admission
    runs_root, store_root, job_id, parent, db = Path(argv[0]), Path(argv[1]), argv[2], int(argv[3]), Path(argv[4])
    if os.getppid() != parent:
        return 3
    admission = Admission.open_existing(db)
    try:
        run_job(runs_root, store_root, job_id, admission)
        return 0
    except Exception as exc:
        try:
            update_job(runs_root, job_id, state="failed", finished_at=time.time(), error=_public_error(exc))
        except Exception:
            pass
        return 1


if __name__ == "__main__":
    raise SystemExit(worker_main(sys.argv[1:]))
