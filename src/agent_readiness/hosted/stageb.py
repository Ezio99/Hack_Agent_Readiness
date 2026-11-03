"""The hosted evaluation engine (M8 follow-up): the lifecycle's Stage B runner behind the unchanged launch API `{"repetitions": 1 | 3 | 5}`.

`StageBExecutor` replaces `paired.WorkerExecutor` in the service. What a launch evaluates is decided server-side by the owner's ACTIVE ARMING
(lifecycle/arming.py: an owner-approved frozen suite, registered website variants, one exact manifest per repetition count, the model, the number
of launches and their total reservation; recorded only at an interactive terminal). A launch:

  1. checks the arming (mode must match the service: live -> paid, rehearsal -> zero-cost rehearsal) and the chosen repetitions;
  2. reserves, in the SAME hosted admission (one evaluation slot, the durable US$10 ceiling, never released), the manifest's worst case plus one
     per-request bound (rehearsal: US$0);
  3. claims the next launch number of the arming (exclusive create) and, for paid mode, writes that launch's PaidAuthorization;
  4. runs one worker subprocess (`lifecycle.jobs`, the hosted executor's process model): it re-checks the claim, arming, manifest and reservation,
     then runs `evalruns.runner` prepare -> execute (jailed Chromium; paid: the runner verifies the authorisation again and reserves every request
     in the launch's own ledger before sending; no retries) -> report -> public leak audit.
Results are the lifecycle projection (`/api/lifecycle/evaluations/<eval id>`), the same report and trace views as the preloaded M7 dataset; the
hosted progress, live and trial routes read the Stage B trial records through `job_status` / `trial_dir` / `live` below."""
from __future__ import annotations

import json
import time
from pathlib import Path

from ..investigate.trials.stage import VOID_STATUSES
from ..lifecycle import arming as AR
from ..lifecycle import jobs as J
from . import telemetry

ENGINE = "stage-b"


class StageBExecutor(J.LifecycleExecutor):
    engine = ENGINE

    def __init__(self, root: Path, store_root: Path, admission, *, mode: str, command=None, timeout: int = J.TIMEOUT_SECONDS):
        self.hosted_root = Path(root)
        runs = self.hosted_root / "stageb"
        runs.mkdir(parents=True, exist_ok=True)
        super().__init__(runs, store_root, admission, command=command, timeout=timeout, mode=mode)
        self.available = True

    # ---------------------------------------------------------------------------------------------- arming
    def store(self):
        return AR.open_store(self.store_root)

    def arming(self) -> tuple[AR.Arming | None, str | None]:
        rec = AR.active()
        if rec is None:
            return None, "not_armed"
        if rec.mode != ("paid" if self.mode == "live" else "rehearsal"):
            return None, "arming_mode_mismatch"
        if AR.verify(self.store(), rec):
            return None, "arming_invalid"
        return rec, None

    def configuration(self) -> dict:
        rec, why = self.arming()
        view = AR.summary(self.store(), rec, self.admission) if rec else None
        return {"engine": ENGINE, "armed": rec is not None, "reason": why, "evaluation": view,
                "tasks": self.tasks(rec) if rec else [], "repetitions": [o["repetitions"] for o in (view or {}).get("options", []) if o["available"]]}

    def tasks(self, rec) -> list[dict]:
        return AR.executed_tasks(self.store(), rec.frozen_suite_sha256)

    # ---------------------------------------------------------------------------------------------- launch
    def admit(self, job_id: str, client: str, repetitions: int) -> dict:
        """Steps 1-3. Raises AR.ArmingRefused or admission.Refused before anything is reserved; after the reservation, any failure leaves it
        reserved (conservative, as for hosted repetitions) and the launch number used."""
        rec, why = self.arming()
        if rec is None:
            raise AR.ArmingRefused(why or "not_armed", {"not_armed": "No evaluation is armed. The owner arms one at the server terminal.",
                                                         "arming_mode_mismatch": "The armed evaluation does not match this service's mode.",
                                                         "arming_invalid": "The armed evaluation no longer verifies; the owner must arm again."}.get(why, why), 409)
        opt = rec.option(repetitions)
        if opt is None:
            raise AR.ArmingRefused("repetitions_not_armed", f"{repetitions} repetition(s) are not armed for this evaluation.", 409)
        used = AR.claims(rec.arming_id)
        if len(used) >= rec.max_launches:
            raise AR.ArmingRefused("launches_exhausted", "All armed launches have been used. The owner must arm a new evaluation.", 409)
        if sum(c["reservation_microusd"] for c in used) + opt.reservation_microusd > rec.total_reservation_microusd:
            raise AR.ArmingRefused("arming_total_exhausted", "This launch would exceed the armed total.", 409)
        amount = opt.reservation_microusd if rec.mode == "paid" else 0
        self.admission.reserve_amount(job_id, client, amount)                           # atomic: slot + ceiling + rate limit
        at = time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime())
        try:
            claim = AR.launch(self.store(), rec, repetitions=repetitions, job_id=job_id, at=at)
        except Exception:
            self.admission.transition(job_id, "reserved", "failed")
            raise
        mode = "paid" if rec.mode == "paid" else "rehearsal"
        from ..lifecycle.sites import site_view                                       # hosted reaches the evaluation code only through the lifecycle
        try:
            where = site_view(rec.site)["label"]                                       # e.g. "Larkspur Community College" (judge-facing title)
        except Exception:
            where = rec.site
        label = f"{'Live' if mode == 'paid' else 'Rehearsal'} evaluation · {where} · {rec.variants[0][0].capitalize()} vs {rec.variants[1][0].capitalize()}"
        J.new_job(self.runs_root, job_id, manifest_sha=opt.manifest_sha256, mode=mode, label=label,
                  request={"repetitions": repetitions, "arming_id": rec.arming_id, "experiment": claim["experiment_id"], "frozen_suite": rec.frozen_suite,
                           "variants": [n for n, _ in rec.variants], "manifest_basis": "the owner-armed manifest", "reservation_usd": amount / 1e6})
        J.update_job(self.runs_root, job_id, launch=claim, engine=ENGINE, repetitions=repetitions)
        return {"id": job_id, "state": "reserved", "repetitions": repetitions}


# ---------------------------------------------------------------------------------------------- views for the hosted routes
def is_job(runs_root: Path | None, job_id: str) -> bool:
    return bool(runs_root) and (Path(runs_root) / "jobs" / f"{job_id}.json").is_file()


def _runs(runs_root: Path, job: dict):
    from ..investigate.run import InvestigationRun
    return [InvestigationRun(runs_root / rel) for rel in (job.get("runs") or {}).values()]


def _arm_labels(job: dict) -> dict:
    """Positional arm KEYS (first and second website version): they name the hosted routes (`trials/original|modified/<n>`) and the status shape,
    so they never change. What each arm SHOWS is `arm_display` (e.g. Original vs Improved)."""
    v = (job.get("request") or {}).get("variants") or ["original", "modified"]
    return {v[0]: "Original", v[1]: "Modified"}


def arm_display(job: dict) -> dict:
    v = (job.get("request") or {}).get("variants") or ["original", "modified"]
    return {"Original": v[0].capitalize(), "Modified": v[1].capitalize()}


def _outcome(rec: dict) -> str:
    ev = rec.get("evaluation") or {}
    if ev.get("evidence_backed"):
        return "evidence_supported_pass"
    return "strict_pass" if ev.get("passed") else "not_passed"


TERMINAL = ("completed", "failed", "timed_out", "interrupted")


def record_note(held_state: str, execution_state: str, report_state: str, done: int, planned: int | None) -> str | None:
    """Why a job's preserved admission record differs from its execution outcome (M9). Before M9 a run whose report could not be published was
    recorded as failed even when every agent run completed; the record is kept as written and explained here, never rewritten."""
    if held_state not in TERMINAL or held_state == execution_state or execution_state != "completed":
        return None
    runs = f"{done}/{planned}" if planned else str(done)
    after = {"available": "The report has since passed the current publication check and is available.",
             "withheld": "The report is still withheld by the publication check (fail-closed)."}.get(report_state, "The report is not available.")
    return (f"Execution completed: {runs} agent runs finished. The job record reads \u201c{held_state}\u201d because, when the run finished, its report "
            f"did not pass the publication check of that release, which treated a completed run with an unpublishable report as failed. {after} "
            "The original record is kept unchanged.")


def job_status(runs_root: Path, job_id: str, held_state: str, *, recovery_required: bool, v2: dict | None = None, publication: dict | None = None) -> dict:
    """The hosted status shape (reps x tasks x arms) computed from Stage B trial records; per repetition, every planned trial with its state.
    M9: `state` is the preserved admission record; `execution` is what ran (from the trial records and the worker's job record); `report_status` is
    whether the readiness report may be published (from `publication`, the service's own check); `record_note` explains any difference."""
    job = J.load_job(runs_root, job_id)
    labels = _arm_labels(job)
    reps_n = job.get("repetitions") or (job.get("request") or {}).get("repetitions") or 1
    runs = _runs(runs_root, job)
    tasks, rows = [], {}
    for run in runs:
        tasks = sorted(t["task_id"] for t in run.artifact("tasks-manifest")["tasks"])
        for p in sorted((run.dir / "artifacts" / "trials").glob("*.json")):
            rows[p.stem] = run.artifact(f"trials/{p.stem}")
    alias = {tid: i + 1 for i, tid in enumerate(tasks)}
    running = None
    if held_state in ("reserved", "running"):
        latest = _latest_attempt(runs_root, job)
        running = latest[1] if latest else None
    reps = []
    for r in range(1, reps_n + 1):
        out = []
        for tid in tasks:
            for var, arm in labels.items():
                name = f"{var}-{tid}-r{r}"
                rec = rows.get(name)
                if rec:
                    m = rec.get("metrics") or {}
                    done = rec["outcome"]["run_status"] == "completed"
                    out.append({"arm": arm, "task": alias[tid], "state": "completed" if done else "failed", "outcome": _outcome(rec) if done else rec["outcome"]["run_status"],
                                "requests": m.get("model_requests"), "page_views": m.get("page_views"), "steps": m.get("steps"), "elapsed_seconds": m.get("elapsed_seconds")})
                else:
                    state = "running" if name == running else ("pending" if held_state in ("reserved", "running") else "incomplete")
                    out.append({"arm": arm, "task": alias[tid], "state": state, "outcome": state, "requests": None, "page_views": None, "steps": None, "elapsed_seconds": None})
        st = "completed" if out and all(t["state"] == "completed" for t in out) else ("running" if held_state in ("reserved", "running") else job["state"] if job["state"] != "completed" else "completed")
        reps.append({"index": r, "state": st if out else ("preparing" if held_state in ("reserved", "running") else "incomplete"), "tasks": out, "assessment": None})
    summary = {}
    for arm in ("Original", "Modified"):
        rs = [t for rep in reps for t in rep["tasks"] if t["arm"] == arm]
        done = [t for t in rs if t["state"] == "completed"]
        mean = lambda k: round(sum(t[k] for t in done) / len(done), 2) if done and all(t.get(k) is not None for t in done) else None
        summary[arm] = {"planned": len(tasks) * reps_n, "completed": len(done), "failed": sum(t["state"] == "failed" for t in rs),
                        "evidence_supported_passes": sum(t["outcome"] == "evidence_supported_pass" for t in done),
                        "strict_passes": sum(t["outcome"] in ("evidence_supported_pass", "strict_pass") for t in done),
                        "requests_total": sum(t.get("requests") or 0 for t in done), "requests_mean": mean("requests"), "page_views_mean": mean("page_views"),
                        "steps_mean": mean("steps"), "elapsed_mean": mean("elapsed_seconds")}
    planned = len(tasks) * reps_n * 2 if tasks else None
    trials = [t for rep in reps for t in rep["tasks"]]
    ran = [rows[n] for n in rows]
    exec_state = job["state"] if job["state"] in TERMINAL else ("running" if held_state in ("reserved", "running") else job["state"])
    execution = {"state": exec_state, "trials_planned": planned, "trials_completed": sum(t["state"] == "completed" for t in trials),
                 "trials_failed": sum(t["state"] == "failed" for t in trials),
                 "trials_void": sum((r.get("outcome") or {}).get("run_status") in VOID_STATUSES for r in ran)}
    pub = publication or {"state": "pending" if held_state in ("reserved", "running") else ("unavailable" if exec_state != "completed" else "unknown")}
    pub_check = job.get("publication_check")
    report_status = {**pub, **({"recorded_at_completion": {k: pub_check.get(k) for k in ("publishable", "report_audit_clean", "runner_public_report_clean")}}
                               if pub_check else {})}
    return {"id": job_id, "engine": ENGINE, "state": held_state, "recovery_required": recovery_required, "mode": "live" if job["mode"] == "paid" else "rehearsal",
            "repetitions": reps_n, "created_at": job["created_at"], "started_at": job.get("started_at"), "finished_at": job.get("finished_at"),
            "execution": execution, "report_status": report_status,
            "record_note": record_note(held_state, exec_state, report_status["state"], execution["trials_completed"], planned),
            "reps": reps, "summary": summary, "summary_v2": v2, "report": job_id if report_status["state"] == "available" else None,
            "evaluation": {k: (job.get("request") or {}).get(k) for k in ("frozen_suite", "variants", "repetitions")},
            "arm_display": arm_display(job),
            "error": job.get("error"), "stopped": job.get("stopped"), "tasks_planned": len(tasks) * reps_n * 2 if tasks else None}


def _latest_attempt(runs_root: Path, job: dict):
    latest = None
    for run in _runs(runs_root, job):
        for tr in (run.dir / "trial-data").glob("*/*/trace.jsonl"):
            m = tr.stat().st_mtime
            if latest is None or m > latest[0]:
                latest = (m, tr.parent.parent.name, tr.parent, run)
    return latest


def trial_name(runs_root: Path, job_id: str, index: int, arm: str, task: int) -> str | None:
    job = J.load_job(runs_root, job_id)
    labels = {a.lower(): v for v, a in _arm_labels(job).items()}
    runs = _runs(runs_root, job)
    if arm not in labels or not runs:
        return None
    tasks = sorted(t["task_id"] for t in runs[0].artifact("tasks-manifest")["tasks"])
    if not 1 <= task <= len(tasks) or not 1 <= index <= (job.get("repetitions") or 1):
        return None
    return f"{labels[arm]}-{tasks[task - 1]}-r{index}"


def attempt_dir(runs_root: Path, job_id: str, name: str) -> Path | None:
    job = J.load_job(runs_root, job_id)
    for run in _runs(runs_root, job):
        if run.has_artifact(f"trials/{name}"):
            return run.dir / run.artifact(f"trials/{name}")["trial_dir"]
        base = run.dir / "trial-data" / name
        attempts = sorted(x for x in base.iterdir() if x.is_dir()) if base.is_dir() else []
        if attempts:
            return attempts[-1]
    return None


def timeline(runs_root: Path, job_id: str, attempt: Path) -> dict:
    from ..lifecycle.projection import _redact_stand_in
    job = J.load_job(runs_root, job_id)
    tl = telemetry.timeline(attempt)
    if job["mode"] != "paid":                                                          # the stand-in's replies are derived from the private answers
        tl = {**tl, "steps": _redact_stand_in(tl["steps"])}
    return tl


def live(runs_root: Path, job_id: str, held_state: str, tasks: list[dict]) -> dict:
    job = J.load_job(runs_root, job_id)
    latest = _latest_attempt(runs_root, job)
    if latest is None:
        return {"active": held_state in ("reserved", "running"), "trial": None}
    _, name, attempt, run = latest
    labels = _arm_labels(job)
    var, rest = name.split("-", 1)
    tid, rep = rest.rsplit("-r", 1)
    order = sorted(t["task_id"] for t in run.artifact("tasks-manifest")["tasks"])
    n = order.index(tid) + 1 if tid in order else None
    state = "completed" if run.has_artifact(f"trials/{name}") else "running"
    return {"active": held_state in ("reserved", "running"),
            "trial": {"repetition": int(rep), "arm": labels.get(var, var).lower(), "task": n, "state": state,
                      "question": next((t["question"] for t in tasks if t["task_id"] == tid), None), **timeline(runs_root, job_id, attempt)}}
