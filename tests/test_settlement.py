"""Actual-cost settlement of hosted reservations (final showcase).

Synthetic databases cover the rules; copies of the PRODUCTION admission database and real request ledgers (git-ignored local copies) cover
historical compatibility. Nothing here touches production or makes a model call."""
import hashlib
import json
import shutil
import sqlite3
import threading
from pathlib import Path

import pytest

from agent_readiness.hosted import ceiling as CE
from agent_readiness.hosted import settlement as ST
from agent_readiness.hosted.admission import Admission, Refused

ROOT = Path(__file__).resolve().parents[1]
FS = ROOT / "scanner-data" / "hosted-copy-fs" / "data" / "hosted"            # production copy after eval-c04 (admission DB, Stage B jobs, ledgers)
M9 = ROOT / "scanner-data" / "hosted-copy-m9" / "data" / "hosted"            # earlier production copy (the retired paired engine's job records + ledgers)
C04, E529 = "eval-c04fdb100d6b1c877de96dabe76eb052", "eval-e529db2aafecbfddd21e5c571eb85243"
IRON = ("eval-9aaac35ca488c2bf951e01e58746604a", "eval-aa23e33012717c4a30ca21be1239e85f")
need_prod = pytest.mark.skipif(not (FS / "live" / "admission.sqlite").is_file() or not (M9 / "live").is_dir(), reason="needs the local production copies")
CLIENT = "c" * 64


def sha(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def jid(n: int) -> str:
    return "eval-" + f"{n:032x}"


# --------------------------------------------------------------------------------------------------------------- synthetic fixtures
def setup(tmp_path, ceiling=10_000_000):
    root = tmp_path / "hosted" / "live"
    root.mkdir(parents=True)
    a = Admission(root / "admission.sqlite", ceiling_microusd=ceiling, job_cap_microusd=1_650_000, min_interval_seconds=1)
    return a, root


def launch(a, root, n, reserve, *, entries, now, state="completed", mode="paid"):
    """A settlement-aware Stage B job with its own launch claim, paid authorisation and request ledger (`entries`: (kind, id, usd))."""
    job = jid(n)
    a.reserve_amount(job, CLIENT, reserve, now=now)
    exp = f"pool-l{n}"
    sb = root.parent / "lifecycle" / "stage-b"
    (sb / "authorizations").mkdir(parents=True, exist_ok=True)
    (sb / "authorizations" / f"{exp}.json").write_text(json.dumps({"experiment_id": exp}))
    if entries is not None:
        (sb / "ledgers" / exp).mkdir(parents=True, exist_ok=True)
        (sb / "ledgers" / exp / "ledger.jsonl").write_text("".join(json.dumps({"ts": "t", "kind": k, "id": i, "usd": u}) + "\n" for k, i, u in entries))
    (root / "stageb" / "jobs").mkdir(parents=True, exist_ok=True)
    (root / "stageb" / "jobs" / f"{job}.json").write_text(json.dumps({"id": job, "mode": mode, "launch": {"job": job, "experiment_id": exp}}))
    a.transition(job, "reserved", "running")
    if state != "running":
        a.transition(job, "running", state)
    return job


def ok_ledger(n=3, reserved=0.04, actual=0.01):
    return [e for i in range(n) for e in (("reserve", f"r{i}", reserved), ("settle", f"r{i}", actual))]


@pytest.fixture(autouse=True)
def _stage_b_env(monkeypatch):
    monkeypatch.delenv("AR_STAGE_B_ROOT", raising=False)


# --------------------------------------------------------------------------------------------------------------- the rules
def test_a_completed_run_releases_its_unused_reservation_exactly_once(tmp_path):
    a, root = setup(tmp_path)
    j = launch(a, root, 1, 3_740_000, entries=ok_ledger(), now=1)
    assert a.totals()["available_microusd"] == 10_000_000 - 3_740_000
    out = ST.settle_automatic(a, root, j)
    assert out == {"job_id": j, "settled_microusd": 30_000, "already": False}
    t = a.totals()
    assert (t["settled_microusd"], t["released_microusd"], t["outstanding_microusd"], t["committed_microusd"], t["available_microusd"]) == (30_000, 3_710_000, 0, 30_000, 9_970_000)
    assert a.get(j)["reserved_microusd"] == 3_740_000                                  # the reservation as written is never rewritten
    assert ST.settle_automatic(a, root, j) is None                                     # already settled: nothing more
    again = ST.settle(a, root, j, actor="x")                                            # duplicate settlement: idempotent no-op
    assert again["already"] and a.totals()["settled_microusd"] == 30_000
    with pytest.raises(Refused, match="never changed"):
        a.record_settlement(j, 31_000, basis="b", ledger_sha256="0" * 64, ledger_requests=3, open_requests=0, actor="x")


def test_a_failed_run_with_unsettled_requests_keeps_its_reservation_until_the_owner_recovers_it(tmp_path):
    a, root = setup(tmp_path)
    entries = ok_ledger(2) + [("reserve", "r9", 0.04)]                                # one request sent (reserved) but never settled
    j = launch(a, root, 1, 3_740_000, entries=entries, now=1, state="failed")
    assert ST.settle_automatic(a, root, j, log=lambda *_: None) is None
    assert a.totals()["committed_microusd"] == 3_740_000                              # "failed" alone releases nothing
    with pytest.raises(ST.SettlementRefused) as e:
        ST.settle(a, root, j, actor="owner")
    assert e.value.code == "open_requests"
    out = ST.settle(a, root, j, actor="owner", allow_open=True)                         # owner recovery: the open request counts at its full bound
    assert out["settled_microusd"] == 20_000 + 40_000 and a.settlement(j)["open_requests"] == 1


def test_failed_state_without_a_verifiable_ledger_releases_nothing(tmp_path):
    a, root = setup(tmp_path)
    j = launch(a, root, 1, 3_740_000, entries=None, now=1, state="failed")
    assert ST.settle_automatic(a, root, j, log=lambda *_: None) is None
    assert ST.assess(a, root, j)["reason"] == "ledger_missing" and a.totals()["available_microusd"] == 6_260_000


def test_a_running_job_is_never_settled(tmp_path):
    a, root = setup(tmp_path)
    j = launch(a, root, 1, 3_740_000, entries=ok_ledger(), now=1, state="running")
    assert ST.assess(a, root, j)["reason"] == "not_terminal"
    with pytest.raises(Refused, match="not terminal"):
        a.record_settlement(j, 0, basis="b", ledger_sha256="0" * 64, ledger_requests=0, open_requests=0, actor="x")


@pytest.mark.parametrize("entries,code", [
    ([("reserve", "a", 0.04), ("reserve", "a", 0.04)], "ledger_malformed"),            # reserved twice
    ([("settle", "a", 0.01)], "ledger_malformed"),                                      # settled without a reservation
    ([("reserve", "a", 0.04), ("settle", "a", 0.01), ("settle", "a", 0.01)], "ledger_malformed"),
    ([("reserve", f"x{i}", 0.04) for i in range(100)] + [("settle", f"x{i}", 0.04) for i in range(100)], "exceeds_reservation"),
])
def test_an_inconsistent_ledger_is_never_used_to_release_capacity(tmp_path, entries, code):
    a, root = setup(tmp_path)
    j = launch(a, root, 1, 3_740_000, entries=entries, now=1)
    assert ST.assess(a, root, j)["reason"] == code
    assert ST.settle_automatic(a, root, j, log=lambda *_: None) is None and a.totals()["committed_microusd"] == 3_740_000


def test_a_crash_during_settlement_leaves_no_partial_record_and_restart_recovery_settles(tmp_path):
    a, root = setup(tmp_path)
    j = launch(a, root, 1, 3_740_000, entries=ok_ledger(), now=1)
    with sqlite3.connect(a.path) as db:                                                 # the write fails inside the transaction (a crash)
        db.execute("CREATE TRIGGER boom BEFORE INSERT ON settlements BEGIN SELECT RAISE(ABORT, 'crash'); END")
    with pytest.raises(sqlite3.IntegrityError):
        ST.settle(a, root, j, actor="service")
    assert a.settlement(j) is None and a.totals()["committed_microusd"] == 3_740_000    # nothing half-written; full reservation held
    with sqlite3.connect(a.path) as db:
        db.execute("DROP TRIGGER boom")
    b = Admission.open_existing(a.path)                                                 # the restarted service
    assert ST.reconcile_automatic(b, root, log=lambda *_: None) == [j]
    assert b.totals()["committed_microusd"] == 30_000


def test_restart_recovery_never_releases_an_interrupted_job_with_requests_in_flight(tmp_path):
    a, root = setup(tmp_path)
    j = launch(a, root, 1, 3_740_000, entries=ok_ledger(1) + [("reserve", "inflight", 0.04)], now=1, state="interrupted")
    assert ST.reconcile_automatic(Admission.open_existing(a.path), root, log=lambda *_: None) == []
    assert a.totals()["committed_microusd"] == 3_740_000


def test_historical_jobs_are_never_settled_automatically(tmp_path):
    a, root = setup(tmp_path)
    j = launch(a, root, 1, 3_740_000, entries=ok_ledger(), now=1)
    with sqlite3.connect(a.path) as db:
        db.execute("DELETE FROM auto_settle")                                           # as if admitted by an earlier release
    assert ST.reconcile_automatic(a, root, log=lambda *_: None) == [] and a.settlement(j) is None
    assert ST.settle(a, root, j, actor="owner terminal")["settled_microusd"] == 30_000   # only the owner can settle it


def test_the_ceiling_is_exact_against_settled_plus_outstanding(tmp_path):
    a, root = setup(tmp_path, ceiling=7_480_000)
    j1 = launch(a, root, 1, 3_740_000, entries=ok_ledger(), now=1)
    ST.settle_automatic(a, root, j1)                                                    # committed 30_000
    j2 = launch(a, root, 2, 3_740_000, entries=ok_ledger(), now=3, state="failed")       # committed 3_740_000 (not settled yet)
    with sqlite3.connect(a.path) as db:
        db.execute("DELETE FROM auto_settle WHERE job_id=?", (j2,))
    left = 7_480_000 - 30_000 - 3_740_000
    with pytest.raises(Refused, match="budget"):
        a.reserve_amount(jid(3), CLIENT, left + 1, now=5)
    a.reserve_amount(jid(3), CLIENT, left, now=5)                                        # exactly at the ceiling
    assert a.totals()["available_microusd"] == 0


def test_concurrent_launch_attempts_admit_exactly_one_within_the_ceiling(tmp_path):
    a, root = setup(tmp_path, ceiling=7_480_000)
    j1 = launch(a, root, 1, 3_740_000, entries=ok_ledger(), now=1)
    ST.settle_automatic(a, root, j1)
    results, start = [], threading.Barrier(8)

    def go(i):
        b = Admission.open_existing(a.path)                                             # separate connections, like separate requests/processes
        start.wait()
        try:
            b.reserve_amount(jid(100 + i), "%064x" % i, 3_740_000, now=10)
            results.append(i)
        except Refused:
            pass
    ts = [threading.Thread(target=go, args=(i,)) for i in range(8)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert len(results) == 1                                                            # one slot; never above the ceiling
    assert a.totals()["committed_microusd"] <= 7_480_000


def test_the_read_only_audit_changes_nothing(tmp_path):
    a, root = setup(tmp_path)
    launch(a, root, 1, 3_740_000, entries=ok_ledger(), now=1)
    before = sha(a.path)
    rep = ST.audit(Admission.open_read_only(a.path), root)
    assert rep["jobs"][0]["eligible"] and sha(a.path) == before
    with pytest.raises(PermissionError):
        Admission.open_read_only(a.path).record_settlement(jid(1), 0, basis="b", ledger_sha256="0" * 64, ledger_requests=0, open_requests=0, actor="x")


def test_ceiling_status_and_an_older_image_stay_consistent(tmp_path):
    a, root = setup(tmp_path)
    j = launch(a, root, 1, 3_740_000, entries=ok_ledger(), now=1)
    before = CE.status(a.path)
    ST.settle_automatic(a, root, j)
    st = CE.status(a.path)
    assert st["jobs_fingerprint"] == before["jobs_fingerprint"] and st["reserved"] == 3_740_000     # job rows untouched
    assert (st["settled"], st["released"], st["committed"], st["available"]) == (30_000, 3_710_000, 30_000, 9_970_000)
    with sqlite3.connect(a.path) as db:                                                 # what an older image sums: unchanged and more conservative
        assert db.execute("SELECT SUM(reserved) FROM jobs").fetchone()[0] == 3_740_000


def test_a_rehearsal_job_reserves_nothing_and_settles_at_zero(tmp_path):
    a, root = setup(tmp_path)
    j = launch(a, root, 1, 0, entries=None, now=1, mode="rehearsal")
    assert ST.settle_automatic(a, root, j)["settled_microusd"] == 0 and a.totals()["committed_microusd"] == 0


# --------------------------------------------------------------------------------------------------------------- production copies
@pytest.fixture
def prod(tmp_path, monkeypatch):
    data = tmp_path / "hosted"
    shutil.copytree(FS, data)
    for j in IRON:                                                                      # the retired engine's job records and ledgers
        shutil.copy(M9 / "live" / f"{j}.job.json", data / "live")
        for rep in json.loads((M9 / "live" / f"{j}.job.json").read_text())["reps"]:
            (data / "live" / rep["run_id"] / "spend").mkdir(parents=True, exist_ok=True)
            shutil.copy(M9 / "live" / rep["run_id"] / "spend" / "ledger.jsonl", data / "live" / rep["run_id"] / "spend")
    monkeypatch.setenv("AR_STAGE_B_ROOT", str(data / "lifecycle" / "stage-b"))
    return data


@need_prod
def test_the_production_audit_is_read_only_and_finds_exactly_what_the_ledgers_support(prod):
    db = prod / "live" / "admission.sqlite"
    before = sha(db)
    rep = ST.audit(Admission.open_read_only(db), prod / "live")
    assert sha(db) == before                                                            # no table created, nothing written
    by = {j["job"]: j for j in rep["jobs"]}
    assert (by[C04]["eligible"], by[C04]["commit_microusd"], by[C04]["release_microusd"]) == (True, 631_751, 3_108_249)
    assert (by[E529]["eligible"], by[E529]["commit_microusd"], by[E529]["release_microusd"]) == (True, 1_546_226, 5_889_774)
    assert by[E529]["state"] == "failed"                                                 # eligible because its ledger is complete, not because it failed
    for j in IRON:                                                                       # forked ledgers include the source run: never released by the tool
        assert not by[j]["eligible"] and by[j]["reason"] == "exceeds_reservation"
    assert (by[C04]["ledger"]["requests"], by[C04]["ledger"]["open_requests"], by[E529]["ledger"]["requests"]) == (45, 0, 112)
    t = rep["totals"]
    assert (t["ceiling_microusd"], t["reserved_microusd"], t["committed_microusd"], t["available_microusd"]) == (21_956_000, 14_476_000, 14_476_000, 7_480_000)


@need_prod
def test_owner_settlement_of_the_two_live_runs_on_a_copy(prod):
    db = prod / "live" / "admission.sqlite"
    ledgers = {p: sha(p) for p in (prod / "lifecycle" / "stage-b" / "ledgers").rglob("ledger.jsonl")}
    a = Admission.open_existing(db)
    fp = CE.status(db)["jobs_fingerprint"]
    assert ST.reconcile_automatic(a, prod / "live", log=lambda *_: None) == []          # historical: nothing is settled automatically
    for j, amount in ((C04, 631_751), (E529, 1_546_226)):
        assert ST.settle(a, prod / "live", j, actor="owner terminal", expect_microusd=amount)["settled_microusd"] == amount
    t = a.totals()
    assert (t["settled_microusd"], t["released_microusd"], t["outstanding_microusd"]) == (2_177_977, 8_998_023, 3_300_000)
    assert (t["committed_microusd"], t["available_microusd"]) == (5_477_977, 16_478_023)
    assert CE.status(db)["jobs_fingerprint"] == fp                                       # historical rows unchanged
    assert all(sha(p) == h for p, h in ledgers.items())                                  # ledgers untouched
    with pytest.raises(ST.SettlementRefused, match="expected"):
        ST.settle(a, prod / "live", C04, actor="owner", expect_microusd=631_750)


@need_prod
def test_launch_count_and_financial_capacity_are_separate_limits(prod, monkeypatch):
    """After settlement the budget covers four launches, but the owner's arming still allows only its two remaining ones."""
    from agent_readiness.evalruns import authorization as AU
    from agent_readiness.hosted.stageb import StageBExecutor
    from agent_readiness.lifecycle import arming as AR
    from agent_readiness.lifecycle.arming import ArmingRefused
    from agent_readiness.suites.store import WriteOnceStore
    sb = prod / "lifecycle" / "stage-b"
    monkeypatch.setattr(AU, "STAGE_B", sb)
    AR.set_stage_b_root(sb)
    db = prod / "live" / "admission.sqlite"
    a = Admission.open_existing(db)
    for j in (C04, E529):
        ST.settle(a, prod / "live", j, actor="owner terminal")
    st = WriteOnceStore(prod / "lifecycle" / "store")
    summ = AR.summary(st, AR.active(), a)
    assert summ["launches"]["left"] == 2 and summ["capacity"]["launches_affordable"] == 4
    ex = StageBExecutor(prod / "live", prod / "lifecycle" / "store", a, mode="live")
    admitted = []
    for n in range(3):
        try:
            admitted.append(ex.admit(jid(900 + n), "%064x" % n, 1)["id"])
        except ArmingRefused:
            break
        a.transition(admitted[-1], "reserved", "failed")                                 # free the slot (no worker ran; nothing sent)
    assert len(admitted) == 2                                                            # the third launch is refused by the arming, not the budget
    assert a.totals()["available_microusd"] == 16_478_023 - 2 * 3_740_000                 # failed launches keep their full reservation
    for j in admitted:
        assert ST.assess(a, prod / "live", j)["eligible"] is False                       # no ledger yet -> never released
