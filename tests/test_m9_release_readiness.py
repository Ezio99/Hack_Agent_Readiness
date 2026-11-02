"""M9 release-readiness regressions (zero cost; no model, no browser).

* `ceiling migrate`: re-running the runbook's exact command after it was applied (e.g. after a dropped SSH session) is a no-op, not a
  policy_mismatch refusal; after a launch has reserved more, the same command is refused and nothing changes.
* The ceiling printed for `deploy/.env` is exact (a `:g` rendering would leave the service fail-closed for some values).
* `hosted.admin watch` counts a Stage B job's planned trials (12 for larkspur-core@v2), not the retired engine's 8 per repetition, and prints
  the stop reason.
* Rollback compatibility: the DEPLOYED image's admission code (`140a4e8`) on a migrated database stays fail-closed with the old ceiling; with the
  migrated ceiling it can reserve legacy repetitions until a Stage B launch has reserved the rest (hence: roll back with the old ceiling)."""
import importlib.util
import subprocess
from pathlib import Path

import pytest

from agent_readiness.hosted import admin
from agent_readiness.hosted import ceiling as CE
from agent_readiness.hosted.admission import Admission
from agent_readiness.hosted.serve import ceiling_microusd

ROOT = Path(__file__).resolve().parents[1]
REASON = "one full six-task Original-vs-Modified paid evaluation of larkspur-core@v2"


def prod_like(tmp_path) -> Path:
    db = tmp_path / "live" / "admission.sqlite"
    a = Admission(db, ceiling_microusd=10_000_000, job_cap_microusd=1_650_000, min_interval_seconds=120)
    for i, t in enumerate((1793582937.7368062, 1793597557.6389794)):
        j = f"eval-{str(i) * 32}"
        a.reserve(j, "4f" * 32, now=t, units=1)
        a.transition(j, "reserved", "running")
        a.transition(j, "running", "completed")
    return db


def runbook(db, typed=None, ec="10"):
    p = CE.plan(db, to="10.736", expect_ceiling=ec, expect_reserved="3.3", reason=REASON)
    return CE.migrate(db, to="10.736", expect_ceiling=ec, expect_reserved="3.3", reason=REASON, typed=p["confirmation"] if typed is None else typed,
                      interactive=True, actor="test")


def test_rerunning_the_exact_runbook_command_after_it_applied_is_a_no_op(tmp_path):
    db = prod_like(tmp_path)
    assert runbook(db)["applied"]
    before = CE.status(db)
    again = runbook(db, typed="anything")                                   # the same --expect-ceiling 10 --expect-reserved 3.3 command
    assert again == {"applied": False, "already_applied": True, "ceiling": 10_736_000}
    after = CE.status(db)
    assert after["history"] == before["history"] and after["jobs_fingerprint"] == before["jobs_fingerprint"]


def test_after_a_launch_reserved_more_the_runbook_command_is_refused_and_changes_nothing(tmp_path):
    db = prod_like(tmp_path)
    runbook(db)
    a = Admission.open_existing(db)
    a.reserve_amount("eval-" + "a" * 32, "b" * 64, 7_436_000)
    a.transition("eval-" + "a" * 32, "reserved", "failed")
    before = CE.status(db)
    with pytest.raises(CE.MigrationRefused) as exc:
        runbook(db)
    assert exc.value.code == "reservations_mismatch"
    assert CE.status(db)["history"] == before["history"] and CE.status(db)["ceiling"] == 10_736_000


def test_an_unrelated_expected_ceiling_is_still_refused(tmp_path):
    db = prod_like(tmp_path)
    runbook(db)
    with pytest.raises(CE.MigrationRefused) as exc:
        CE.plan(db, to="10.736", expect_ceiling="9", expect_reserved="3.3", reason=REASON)
    assert exc.value.code == "policy_mismatch"


@pytest.mark.parametrize("micro,text", [(10_736_000, "10.736"), (10_000_000, "10"), (12_345_678, "12.345678"), (33_333_333, "33.333333"), (500_000, "0.5")])
def test_the_printed_env_ceiling_is_exact(micro, text):
    assert CE.env_value(micro) == text
    assert ceiling_microusd(text) == micro                                  # what the service parses back: no budget_policy_mismatch


def _job(engine, reps, tasks_planned, **extra):
    t = {"state": "completed", "outcome": "not_passed", "arm": "Original", "task": 1}
    summary = {arm: {"evidence_supported_passes": 0, "completed": 1, "requests_total": 3} for arm in ("Original", "Modified")}
    return {"state": "running", "engine": engine, "repetitions": 1, "reps": [{"state": "running", "tasks": [t] * reps}], "summary": summary,
            "tasks_planned": tasks_planned, **extra}


def test_admin_watch_counts_stage_b_trials_and_prints_the_stop_reason():
    line = admin.line(_job("stage-b", 12, 12, stopped="natural: original-x-r1: void (infrastructure_error); remaining trials not run (no retries)"))
    assert "12/12 runs" in line and "void (infrastructure_error)" in line
    legacy = {k: v for k, v in _job(None, 8, None).items() if k not in ("engine", "tasks_planned")}
    assert "8/8 runs" in admin.line(legacy)


def _deployed_admission():
    try:
        src = subprocess.run(["git", "-C", str(ROOT), "show", "140a4e8:src/agent_readiness/hosted/admission.py"], capture_output=True, text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("the deployed commit 140a4e8 is not in this clone")
    path = Path(__file__).with_name("_m9_deployed_admission.py")
    spec = importlib.util.spec_from_loader("deployed_admission", loader=None)
    mod = importlib.util.module_from_spec(spec)
    exec(compile(src, str(path), "exec"), mod.__dict__)
    return mod


def test_rollback_image_on_a_migrated_database(tmp_path):
    O = _deployed_admission()
    db = prod_like(tmp_path)
    runbook(db)
    with pytest.raises(ValueError, match="durable policy"):
        O.Admission(db, ceiling_microusd=10_000_000, job_cap_microusd=1_650_000, min_interval_seconds=120)     # .env 10: fail-closed
    old = O.Admission(db, ceiling_microusd=10_736_000, job_cap_microusd=1_650_000, min_interval_seconds=120)  # .env 10.736: opens
    assert old.totals()["reserved_microusd"] == 3_300_000
    # before any Stage B launch the retired engine could reserve 4 legacy repetitions (US$6.60) of the capacity meant for the Stage B launch
    n = 0
    while True:
        try:
            old.reserve(f"eval-legacy{n}", "c" * 64, now=2e9 + n * 1000, units=1)
        except O.Refused:
            break
        old.transition(f"eval-legacy{n}", "reserved", "failed")
        n += 1
    assert n == 4


def test_rollback_image_after_the_stage_b_launch_admits_nothing(tmp_path):
    O = _deployed_admission()
    db = prod_like(tmp_path)
    runbook(db)
    Admission.open_existing(db).reserve_amount("eval-" + "a" * 32, "b" * 64, 7_436_000)
    old = O.Admission(db, ceiling_microusd=10_736_000, job_cap_microusd=1_650_000, min_interval_seconds=120)
    assert old.totals()["reserved_microusd"] == 10_736_000
    with pytest.raises(O.Refused):
        old.reserve("eval-legacy", "c" * 64, now=2e9, units=1)


def test_restart_recovery_kills_a_surviving_stage_b_worker_and_keeps_its_reservation(tmp_path):
    """`recover` (service start) finds a worker that outlived its service by its command line, kills its process group, and marks the admission
    row and the Stage B job interrupted; the reservation stays held (a paid launch is never re-run)."""
    import signal
    import sys

    from agent_readiness.hosted.api import recover
    from agent_readiness.lifecycle import jobs as J

    root = tmp_path / "live"
    a = Admission(root / "admission.sqlite", ceiling_microusd=10_736_000, job_cap_microusd=1_650_000, min_interval_seconds=120)
    job = "eval-" + "d" * 32
    a.reserve_amount(job, "e" * 64, 7_436_000)
    a.transition(job, "reserved", "running")
    J.new_job(root / "stageb", job, manifest_sha="0" * 64, mode="paid", request={"repetitions": 1}, label="m9")
    worker = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)", "agent_readiness.lifecycle.jobs", job], start_new_session=True)
    bystander = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)", "agent_readiness.lifecycle.jobs", "eval-" + "f" * 32],
                                 start_new_session=True)
    try:
        assert recover(root, a) == [job]
        assert worker.wait(timeout=10) == -signal.SIGKILL
        assert bystander.poll() is None                                     # only the interrupted job's worker is killed
        assert a.get(job) == {**a.get(job), "state": "interrupted", "reserved_microusd": 7_436_000}
        assert J.load_job(root / "stageb", job)["state"] == "interrupted"
        assert a.totals()["reserved_microusd"] == 7_436_000
    finally:
        for p in (worker, bystander):
            if p.poll() is None:
                p.kill()
                p.wait()
