"""Lifecycle evaluation jobs launched from the product (M8): one worker subprocess per job, the hosted executor's process model (new session,
parent-death signal, hard timeout, process-group kill), the hosted admission's single evaluation slot and durable ceiling.

    python -m agent_readiness.lifecycle.jobs RUNS_ROOT STORE_ROOT JOB_ID PARENT_PID ADMISSION_DB      (started by LifecycleExecutor only)

Modes:
  rehearsal   the Stage B runner end to end (prepare -> execute -> report) on the approved, frozen suite's manifest: real Chromium in the network
              jail, the loopback dev provider standing in for the model (NOT a model), every non-loopback socket refused in the worker. Reserves
              US$0 against the hosted ceiling (it still holds the single evaluation slot).
  paid        (M8 follow-up) an owner-authorised experiment (lifecycle.paid), launched by the operator: the API checks and claims it and reserves
              its worst case against the hosted ceiling; this worker re-checks everything (`paid.check(for_job=...)`, the reservation equals the
              worst case), loads the provider key from its secret file, and runs the unchanged Stage B runner WITH the authorisation, which
              verifies it once more and enforces reserve-before-send, the per-trial and experiment caps and ledger-counted trials (no retries).
              Only the agent process reaches the provider; the browser stays in the jail. Enabled only in live mode with AR_LIFECYCLE_PAID=enabled."""
from __future__ import annotations

import json
import os
import re
import secrets
import signal
import subprocess
import sys
import time
from pathlib import Path

JOB_ID = re.compile(r"eval-[0-9a-f]{32}")              # hosted evaluation ids (the workspace URLs #/run/eval-<32 hex>)
MODES = ("rehearsal", "paid")
TIMEOUT_SECONDS = 3 * 3600
TERMINAL = ("completed", "failed", "timed_out", "interrupted")


def new_id() -> str:
    return "eval-" + secrets.token_hex(16)


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


# ------------------------------------------------------------------------------------------------------------------------------- executor
class LifecycleExecutor:
    """Launches the worker for one job and waits for it (call from the job's own thread)."""

    def __init__(self, runs_root: Path, store_root: Path, admission, *, command=None, timeout: int = TIMEOUT_SECONDS, mode: str = "rehearsal"):
        self.runs_root, self.store_root, self.admission = Path(runs_root), Path(store_root), admission
        self.mode = mode                                                      # the hosted service mode: paid launches need "live"
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
    roots. Hiding more never weakens the declared boundary; the extra paths are recorded on the job. (The jail self-test checks that no entry of a
    hidden directory appears in the browser's listing of it, so a hidden directory must not contain an entry named like itself, e.g. runs/runs.)"""
    from ..evalruns import manifest as MF
    from ..evalruns import authorization as AU
    extra = [str(Path(store_root).resolve()), str(Path(runs_root).resolve()), str(Path(AU.STAGE_B).resolve())]
    pol = os.environ.get("AGENT_READINESS_BROWSER_JAIL")
    if pol and Path(pol).is_file():
        extra = list(json.loads(Path(pol).read_text()).get("hide") or []) + extra
    declared = MF.JAIL_POLICY
    MF.JAIL_POLICY = {**declared, "hide": list(dict.fromkeys(list(declared["hide"]) + extra))}

    def restore():                                          # the declared policy (hashed into every manifest's agent) is restored after execution
        MF.JAIL_POLICY = declared
    return extra, restore


def run_job(runs_root: Path, store_root: Path, job_id: str, admission) -> dict:
    from ..evalruns import runner as RN
    from ..suites.store import WriteOnceStore
    job = load_job(runs_root, job_id)
    held = admission.get(job_id)
    if not held or held["state"] != "running":
        raise PermissionError("the job does not hold a running admission")
    from ..hosted import paired
    from . import arming as AR
    store = WriteOnceStore(store_root)
    claim = AR.check_launch(store, job)                                     # independent re-check: claim names this job; arming, manifest, (paid) authorisation, unused ledger
    if held["reserved_microusd"] != (claim["reservation_microusd"] if job["mode"] == "paid" else 0):
        raise PermissionError("the hosted reservation does not equal the armed launch's reservation")
    auth_path = None
    if job["mode"] == "rehearsal":
        paired._loopback_only_sockets()                                     # no provider can be contacted from this process
    elif job["mode"] == "paid":
        auth_path = Path(claim["authorization"])
        paired._load_key_file()                                             # the provider key, read from its secret file after exec; never logged
    else:
        raise PermissionError("unknown job mode")
    mode = job["mode"]
    runs = RN.prepare(store, job["manifest_sha256"], Path(runs_root) / "evalruns", mode=mode, label=job_id[3:13])     # not "runs": see harden_jail
    manifest = store.get("manifest", job["manifest_sha256"])
    update_job(runs_root, job_id, runs={c: str(r.dir.relative_to(Path(runs_root))) for c, r in runs.items()},
               planned=sum(len(RN.steps(r, manifest)) for r in runs.values()), state="running")
    hidden, restore = harden_jail(runs_root, store_root)
    update_job(runs_root, job_id, runtime_jail_hides=hidden)
    stopped = []
    try:
        for c, r in runs.items():
            out = RN.execute(r, store, authorization=auth_path)             # paid: the runner verifies the authorisation again and enforces its ledger
            if out.get("stopped"):
                stopped.append(f"{c}: {out['stopped']}")
    finally:
        restore()
    at = time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime())
    doc = RN.report(store, job["manifest_sha256"], runs, created_at=at)
    pub = RN.public_report(doc)
    _write(Path(runs_root) / "reports" / f"{job_id}.public.json", pub)
    audit = RN.audit_public(store, job["manifest_sha256"], runs, [Path(runs_root) / "reports" / f"{job_id}.public.json"])
    # M9: the job's state is its EXECUTION outcome (every planned trial ran, nothing stopped the run). Whether its report may be PUBLISHED is a
    # separate, fail-closed check: the same lifecycle projection audit the service applies before serving, recorded here. A withheld report stays
    # withheld (the service re-checks on every build); it no longer turns a completed run into a terminal "failed".
    publication = _publication_check(store, runs_root, job_id, runner_audit_clean=audit["clean"])
    state = "completed" if not stopped else "failed"
    return update_job(runs_root, job_id, state=state, finished_at=time.time(), stopped="; ".join(stopped) or None,
                      run_results=[r["sha256"] for r in doc["run_results"]], audit_clean=audit["clean"], publication_check=publication,
                      error=None if state == "completed" else "the run stopped early: " + "; ".join(stopped))


def _publication_check(store, runs_root: Path, job_id: str, *, runner_audit_clean: bool) -> dict:
    """Run the service's own publication policy (lifecycle.service.project_and_audit) on the finished job; counts only, never the problem text."""
    from .service import project_and_audit
    out = {"policy": "lifecycle.service.project_and_audit (lifecycle.audit.check_evaluation)", "runner_public_report_clean": bool(runner_audit_clean)}
    try:
        _, problems = project_and_audit(store, runs_root, load_job(runs_root, job_id))
        out.update(report_audit_clean=not problems, report_problems=len(problems))
    except Exception as exc:                                                     # the report cannot be built: not publishable, execution unaffected
        out.update(report_audit_clean=False, report_problems=None, report_error=type(exc).__name__)
    out["publishable"] = bool(out["report_audit_clean"] and runner_audit_clean)
    return out


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
