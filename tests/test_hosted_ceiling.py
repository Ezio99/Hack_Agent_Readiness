"""Owner-authorised hosted ceiling migration (zero cost; no model, no browser).

A production-style admission database (US$10 ceiling, US$1.65 unit, two completed US$1.65 jobs) is migrated to the recommended US$10.736 ceiling:
one value and one audit row change, atomically; nothing in the accounting changes; the fail-closed policy check still holds; and the hosted launch
API then admits exactly one full six-task Original-vs-Modified evaluation (US$7.436), and no more."""
import fcntl
import importlib.util
import json
import shutil
import sqlite3
import threading
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from agent_readiness.hosted import ceiling as CE
from agent_readiness.hosted.admission import Admission, Refused

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


def jobs(db: Path):
    c = sqlite3.connect(db)
    try:
        return c.execute("SELECT * FROM jobs ORDER BY id").fetchall()
    finally:
        c.close()


def go(db, *, to="10.736", ec="10", er="3.3", reason=REASON, typed=None, interactive=True, **kw):
    p = CE.plan(db, to=to, expect_ceiling=ec, expect_reserved=er, reason=reason)
    return CE.migrate(db, to=to, expect_ceiling=ec, expect_reserved=er, reason=reason, typed=p["confirmation"] if typed is None else typed,
                      interactive=interactive, actor="test", **kw)


# ------------------------------------------------------------------------------------------------------------------------------- authorised
def test_status_shows_the_policy_reservations_and_remaining_capacity(tmp_path):
    st = CE.status(prod_like(tmp_path))
    assert (st["ceiling"], st["cap"], st["interval"], st["reserved"], st["remaining"], st["jobs"], st["active"]) == (10_000_000, 1_650_000, 120, 3_300_000, 6_700_000, 2, [])


def test_an_authorised_increase_changes_one_value_appends_one_audit_row_and_preserves_the_accounting(tmp_path):
    db = prod_like(tmp_path)
    before = jobs(db)
    p = CE.plan(db, to="10.736", expect_ceiling="10", expect_reserved="3.3", reason=REASON)
    assert "from US$10.000000 to US$10.736000 with US$3.300000 reserved by 2 job(s)" in p["confirmation"]
    out = go(db)
    assert out["applied"] and out["to"] == 10_736_000 and out["reserved"] == 3_300_000 and out["remaining"] == 7_436_000
    assert jobs(db) == before                                                                   # every reservation, state and timestamp unchanged
    st = CE.status(db)
    assert len(st["history"]) == 1 and st["history"][0]["from_ceiling"] == 10_000_000 and st["history"][0]["to_ceiling"] == 10_736_000
    c = sqlite3.connect(db)
    row = c.execute("SELECT jobs_fingerprint, reserved, cap, interval, confirmation FROM policy_migrations").fetchone()
    assert row[0] == p["jobs_fingerprint"] and row[1:4] == (3_300_000, 1_650_000, 120) and row[4] == p["confirmation"]


def test_the_fail_closed_policy_check_still_holds_after_migration(tmp_path):
    db = prod_like(tmp_path)
    go(db)
    with pytest.raises(ValueError, match="durable policy"):
        Admission(db, ceiling_microusd=10_000_000, job_cap_microusd=1_650_000, min_interval_seconds=120)    # old setting: refused
    a = Admission(db, ceiling_microusd=10_736_000, job_cap_microusd=1_650_000, min_interval_seconds=120)     # new setting: opens
    assert a.totals() == {"ceiling_microusd": 10_736_000, "reserved_microusd": 3_300_000, "per_repetition_microusd": 1_650_000}


def test_after_migration_exactly_one_full_evaluation_fits_and_nothing_more(tmp_path):
    db = prod_like(tmp_path)
    go(db)
    a = Admission.open_existing(db)
    with pytest.raises(Refused, match="budget"):
        a.reserve_amount("eval-" + "a" * 32, "b" * 64, 7_436_001)                             # a launch above the new ceiling
    a.reserve_amount("eval-" + "a" * 32, "b" * 64, 7_436_000)
    a.transition("eval-" + "a" * 32, "reserved", "failed")                                     # even a failed launch keeps its reservation
    with pytest.raises(Refused, match="budget"):
        a.reserve_amount("eval-" + "c" * 32, "d" * 64, 1)
    with pytest.raises(Refused, match="budget"):
        a.reserve("eval-" + "e" * 32, "f" * 64, units=1)                                       # nor a legacy unit


def test_rerunning_a_completed_migration_is_idempotent(tmp_path):
    db = prod_like(tmp_path)
    go(db)
    again = go(db, ec="10.736")
    assert again == {"applied": False, "already_applied": True, "ceiling": 10_736_000} and len(CE.status(db)["history"]) == 1


# ------------------------------------------------------------------------------------------------------------------------------- refusals
@pytest.mark.parametrize("kw,code", [({"interactive": False}, "not_interactive"), ({"typed": "yes"}, "confirmation_mismatch")])
def test_unconfirmed_or_non_terminal_migrations_change_nothing(tmp_path, kw, code):
    db = prod_like(tmp_path)
    before = CE.status(db)
    with pytest.raises(CE.MigrationRefused) as e:
        go(db, **kw)
    assert e.value.code == code and CE.status(db) == before


@pytest.mark.parametrize("kw,code", [({"to": "-1"}, "malformed"), ({"to": "10.7360001"}, "malformed"), ({"to": "ten"}, "malformed"),
                                     ({"reason": "x"}, "malformed"), ({"ec": "9"}, "policy_mismatch"), ({"er": "1.65"}, "reservations_mismatch"),
                                     ({"to": "3.29"}, "below_reservations"), ({"to": "40"}, "above_programme"), ({"to": "10"}, "no_change")])
def test_malformed_mismatched_or_out_of_bounds_requests_are_refused(tmp_path, kw, code):
    db = prod_like(tmp_path)
    with pytest.raises(CE.MigrationRefused) as e:
        go(db, **kw)
    assert e.value.code == code and CE.status(db)["ceiling"] == 10_000_000 and CE.status(db)["history"] == []


def test_a_decrease_is_allowed_only_down_to_the_reservations_held(tmp_path):
    db = prod_like(tmp_path)
    go(db)
    with pytest.raises(CE.MigrationRefused, match="below"):
        go(db, to="3.299999", ec="10.736")
    out = go(db, to="3.3", ec="10.736", reason="close the hosted budget after the evaluation")
    assert out["to"] == 3_300_000 and len(CE.status(db)["history"]) == 2


def test_active_jobs_or_a_running_service_block_the_migration(tmp_path):
    db = prod_like(tmp_path)
    a = Admission.open_existing(db)
    a.reserve_amount("eval-" + "9" * 32, "c" * 64, 0)
    with pytest.raises(CE.MigrationRefused) as e:
        go(db)
    assert e.value.code == "active_jobs"
    a.transition("eval-" + "9" * 32, "reserved", "failed")
    lock = (db.parent / ".service.lock").open("a")
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)                                            # what the running service holds
    try:
        with pytest.raises(CE.MigrationRefused) as e:
            go(db)
        assert e.value.code == "service_running"
    finally:
        lock.close()
    assert go(db)["applied"]


def test_unexpected_database_state_is_refused(tmp_path):
    db = prod_like(tmp_path)
    c = sqlite3.connect(db)
    c.execute("UPDATE jobs SET reserved=-5 WHERE id=?", ("eval-" + "0" * 32,))
    c.commit()
    c.close()
    with pytest.raises(CE.MigrationRefused) as e:
        CE.status(db)
    assert e.value.code == "unexpected_jobs"
    with pytest.raises(CE.MigrationRefused) as e:
        CE.status(tmp_path / "nope.sqlite")
    assert e.value.code == "no_database"


def test_concurrent_migrations_apply_at_most_once(tmp_path):
    db = prod_like(tmp_path)
    results = []
    def attempt():
        try:
            results.append(go(db))
        except CE.MigrationRefused as exc:
            results.append(exc.code)
    ts = [threading.Thread(target=attempt) for _ in range(4)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    applied = [r for r in results if isinstance(r, dict) and r.get("applied")]
    assert len(applied) == 1 and len(CE.status(db)["history"]) == 1 and CE.status(db)["ceiling"] == 10_736_000


def test_a_crash_before_commit_leaves_the_old_state_and_a_restart_can_migrate(tmp_path):
    db = prod_like(tmp_path)
    before = (CE.status(db), jobs(db))
    with pytest.raises(RuntimeError, match="simulated crash"):
        go(db, _fail_before_commit=True)
    assert (CE.status(db), jobs(db)) == before                                                 # nothing partial
    assert go(db)["applied"]                                                                    # the next (restarted) attempt succeeds


def test_no_api_route_can_change_the_ceiling(tmp_path):
    from agent_readiness.hosted.api import create_app
    app = create_app(tmp_path, Admission.open_existing(prod_like(tmp_path)), client_key=b"k" * 32, operator_token=b"t" * 32, public_start=False)
    paths = [getattr(r, "path", "") for r in app.routes]
    assert not any("ceiling" in p or "policy" in p or "migrat" in p for p in paths)
    c = TestClient(app)
    for p in ("/api/ironbark/ceiling", "/api/admin/ceiling", "/api/ironbark/policy"):
        assert c.post(p, json={"to": 100}, headers={"authorization": "Bearer " + "t" * 32}).status_code in (404, 405)


def test_the_cli_refuses_without_a_terminal(tmp_path, monkeypatch, capsys):
    db = prod_like(tmp_path)
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    code = CE.main(["migrate", "--db", str(db), "--to", "10.736", "--expect-ceiling", "10", "--expect-reserved", "3.3", "--reason", REASON])
    assert code == 2 and "interactive terminal" in capsys.readouterr().err and CE.status(db)["ceiling"] == 10_000_000


# ------------------------------------------------------------------------------------------------------------------------------- the exact M7 manifest
STORE = ROOT / "scanner-data" / "research" / "stage-a" / "store"


@pytest.mark.skipif(not (STORE / "refs" / "frozen_suite" / "larkspur-core@v2.json").is_file(), reason="the owner-frozen store exists only on the owner's workstation")
def test_the_hosted_launch_api_admits_the_exact_m7_manifest_only_after_the_migration(tmp_path, monkeypatch):
    """A COPY of the real store; a paid arming recorded in tmp_path only; the executor's worker is replaced, so nothing is sent."""
    from agent_readiness.evalruns import authorization as AU
    from agent_readiness.hosted import stageb
    from agent_readiness.hosted.api import create_app
    from agent_readiness.lifecycle import arming as AR
    from agent_readiness.lifecycle.service import LifecycleService
    monkeypatch.setattr(AU, "STAGE_B", tmp_path / "stage-b")
    store_copy = tmp_path / "store"
    shutil.copytree(STORE, store_copy)
    store = AR.open_store(store_copy)
    kw = dict(arming_id="larkspur-live-1", mode="paid", frozen_ref="larkspur-core@v2", variants=["original", "modified"], repetitions=[1], launches=1)
    p = AR.plan(store, **kw)
    o = p["options"][0]
    assert o["manifest_sha256"].startswith("64a55c5f3a93") and o["trials"] == 12 and o["reservation_microusd"] == 7_436_000
    AR.arm(store, typed=p["attestation"], at="2026-11-04T05:00:00+00:00", interactive=True, **kw)
    db = prod_like(tmp_path / "hosted")

    class NoRun(stageb.StageBExecutor):
        def run(self, job_id):
            pass

    def app():
        a = Admission.open_existing(db)
        ex = NoRun(db.parent, store_copy, a, mode="live")
        svc = LifecycleService(store_root=store_copy, runs_root=db.parent / "stageb", executor=ex, admission=a, log=lambda *_: None)
        return TestClient(create_app(db.parent, a, client_key=b"k" * 32, executor=ex, operator_token=b"t" * 32, public_start=False, mode="live", lifecycle=svc)), a

    op = {"authorization": "Bearer " + "t" * 32}
    c, a = app()
    cfg = c.get("/api/ironbark/config").json()
    assert cfg["evaluation"]["options"][0]["fits_hosted_ceiling"] is False and cfg["repetitions"] == []
    assert c.post("/api/ironbark/jobs", json={"repetitions": 1}, headers=op).status_code == 429                # does not fit at US$10
    assert a.totals()["reserved_microusd"] == 3_300_000 and AR.claims("larkspur-live-1") == []
    go(db)                                                                                                     # the owner's migration
    c, a = app()
    assert c.get("/api/ironbark/config").json()["repetitions"] == [1]
    r = c.post("/api/ironbark/jobs", json={"repetitions": 1}, headers=op)
    assert r.status_code == 202, r.text
    assert a.get(r.json()["id"])["reserved_microusd"] == 7_436_000 and a.totals()["reserved_microusd"] == 10_736_000
    auth = AU.load(AU.STAGE_B / "authorizations" / "larkspur-live-1-l1.json")
    assert auth.manifest_sha256.startswith("64a55c5f3a93") and auth.max_trials == 12 and auth.cap_usd == 8.0
    assert not (AU.STAGE_B / "ledgers").exists()                                                               # nothing was sent: no ledger entry
