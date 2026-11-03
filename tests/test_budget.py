"""Separate A$20 evaluation budget, scoped hosted ceiling, global cap, off-host allocations, programme-ledger identity and the copied-ledger rule
for the historical Ironbark jobs (2026-11).

Synthetic databases cover the rules; copies of the PRODUCTION admission database, Stage B store/ledgers and the retired engine's forked ledgers
cover compatibility (git-ignored local copies; those tests skip without them). Nothing here touches production or makes a model call."""
import hashlib
import json
import shutil
import sqlite3
import threading
from pathlib import Path

import pytest

from agent_readiness.hosted import budget as BG
from agent_readiness.hosted import ceiling as CE
from agent_readiness.hosted import programme as PG
from agent_readiness.hosted import settlement as ST
from agent_readiness.hosted.admission import Admission, Refused, aud_micro

ROOT = Path(__file__).resolve().parents[1]
FS = ROOT / "scanner-data" / "hosted-copy-fs" / "data" / "hosted"
M9 = ROOT / "scanner-data" / "hosted-copy-m9" / "data" / "hosted"
SOURCE = ROOT / "scanner-data" / "live" / "live-2d58a80e14" / "spend" / "ledger.jsonl"
LEDGER = ROOT / "collaboration" / "budget" / "programme-ledger.json"
C04, E529 = "eval-c04fdb100d6b1c877de96dabe76eb052", "eval-e529db2aafecbfddd21e5c571eb85243"
IRON = {"eval-9aaac35ca488c2bf951e01e58746604a": ("paired-60c6a26199b44190a4bc751a45eda7da", 1_090_968),
        "eval-aa23e33012717c4a30ca21be1239e85f": ("paired-86a646169296419eb8fffbb59a31dcab", 1_126_097)}
need_prod = pytest.mark.skipif(not (FS / "live" / "admission.sqlite").is_file() or not (M9 / "live").is_dir(), reason="needs the local production copies")
B = "ar-a20-2026-11"
CEIL = 21_956_000
CLIENT = "c" * 64


def sha(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def jid(n: int) -> str:
    return "eval-" + f"{n:032x}"


@pytest.fixture(autouse=True)
def _stage_b_env(monkeypatch):
    monkeypatch.delenv("AR_STAGE_B_ROOT", raising=False)


def setup(tmp_path, ceiling=CEIL):
    root = tmp_path / "hosted" / "live"
    root.mkdir(parents=True)
    return Admission(root / "admission.sqlite", ceiling_microusd=ceiling, job_cap_microusd=1_650_000, min_interval_seconds=1), root


def open_b20(a, budget_id=B, limit="20", rate="1.50"):
    p = BG.plan_open(a, budget_id, limit, rate)
    return BG.open_budget(a, budget_id, limit, rate, actor="owner terminal (test)", typed=p["text"])


def launch(a, root, n, reserve, *, entries, now, state="completed", budget=None):
    """A settlement-aware Stage B job (claim, paid authorisation, ledger), optionally charged to a budget."""
    job = jid(n)
    a.reserve_amount(job, "%064x" % n, reserve, now=now, budget=budget)
    exp = f"pool-l{n}"
    sb = root.parent / "lifecycle" / "stage-b"
    (sb / "authorizations").mkdir(parents=True, exist_ok=True)
    (sb / "authorizations" / f"{exp}.json").write_text(json.dumps({"experiment_id": exp}))
    if entries is not None:
        (sb / "ledgers" / exp).mkdir(parents=True, exist_ok=True)
        (sb / "ledgers" / exp / "ledger.jsonl").write_text("".join(json.dumps({"ts": "t", "kind": k, "id": i, "usd": u}) + "\n" for k, i, u in entries))
    (root / "stageb" / "jobs").mkdir(parents=True, exist_ok=True)
    (root / "stageb" / "jobs" / f"{job}.json").write_text(json.dumps({"id": job, "mode": "paid", "launch": {"job": job, "experiment_id": exp}}))
    a.transition(job, "reserved", "running")
    if state != "running":
        a.transition(job, "running", state)
    return job


def ok_ledger(n=3, reserved=0.04, actual=0.01):
    return [e for i in range(n) for e in (("reserve", f"r{i}", reserved), ("settle", f"r{i}", actual))]


def budget_fig(a, budget_id=B):
    return next(b for b in a.totals()["budgets"] if b["budget"] == budget_id)


def ledger_file(tmp_path, name, entries):
    p = tmp_path / name
    p.write_text("".join(json.dumps({"ts": "t", "kind": k, "id": i, "usd": u}) + "\n" for k, i, u in entries))
    return p


# --------------------------------------------------------------------------------------------------------------- opening a budget
def test_a_budget_is_opened_once_by_typed_confirmation_and_raises_the_global_cap_by_exactly_its_limit(tmp_path):
    a, _ = setup(tmp_path)
    p = BG.plan_open(a, B, "20", "1.50")
    assert (p["limit_micro_aud"], p["rate_num"], p["rate_den"], p["limit_microusd"]) == (20_000_000, 3, 2, 13_333_333)
    assert (p["global_cap_before"], p["global_cap_after"]) == (None, CEIL + 13_333_333)
    assert "separate from the A$50 programme and all historical spending" in p["text"]
    with pytest.raises(BG.BudgetRefused, match="does not match"):
        BG.open_budget(a, B, "20", "1.50", actor="owner", typed=p["text"].replace("A$20", "A$21"))
    assert a.totals()["budgets"] == [] and a.totals()["global_cap_microusd"] is None                    # nothing recorded
    open_b20(a)
    t = a.totals()
    assert t["global_cap_microusd"] == 35_289_333 and [b["available_micro_aud"] for b in t["budgets"]] == [20_000_000]
    with pytest.raises(BG.BudgetRefused, match="already open"):
        open_b20(a)
    with pytest.raises(BG.BudgetRefused, match="reviewed maximum"):                                     # no second budget without a reviewed release
        open_b20(a, "another-budget", "0.01")
    with pytest.raises(BG.BudgetRefused):
        BG.plan_open(a, "Bad Id", "20", "1.50")
    with pytest.raises(BG.BudgetRefused):
        BG.plan_open(a, "x-budget", "20.0000001", "1.50")                                                 # integer micro-A$ only


def test_amounts_are_integer_micro_units_rounded_conservatively():
    assert [aud_micro(x, 3, 2) for x in (0, 1, 2, 3, 3_740_000, 631_751, 13_333_333)] == [0, 2, 3, 5, 5_610_000, 947_627, 20_000_000]
    assert BG._rate("1.50") == (3, 2) and BG._rate("1.4567") == (14567, 10000)


# --------------------------------------------------------------------------------------------------------------- enforcement and isolation
def test_the_budget_limit_is_exact_in_micro_aud(tmp_path):
    a, _ = setup(tmp_path)
    open_b20(a)
    a.reserve_amount(jid(1), CLIENT, 13_333_333, now=10, budget=B)                     # 13 333 333 µUS$ -> 20 000 000 µA$ (rounded up): exactly the limit
    a.transition(jid(1), "reserved", "failed")                                        # free the slot; a failed run keeps its reservation
    assert budget_fig(a)["available_micro_aud"] == 0
    with pytest.raises(Refused, match="budget ar-a20-2026-11 exhausted"):
        a.reserve_amount(jid(2), CLIENT, 1, now=20, budget=B)                         # 1 µUS$ = 2 µA$ more: refused
    with pytest.raises(Refused, match="no such budget"):
        a.reserve_amount(jid(3), CLIENT, 1, now=30, budget="not-opened")
    assert a.job_budget(jid(1)) == B and a.job_budget(jid(2)) is None


def test_historical_and_programme_jobs_never_touch_the_budget_and_budget_jobs_never_touch_the_ceiling(tmp_path):
    a, root = setup(tmp_path, ceiling=10_000_000)
    launch(a, root, 1, 9_000_000, entries=ok_ledger(), now=10)                        # a historical/programme run under the ceiling
    launch(a, root, 2, 1_000_000, entries=None, now=20, state="failed")              # an uncertain programme run: held in full
    before = a.totals()
    open_b20(a)
    b = budget_fig(a)
    assert (b["spent_micro_aud"], b["outstanding_micro_aud"], b["available_micro_aud"], b["jobs"]) == (0, 0, 20_000_000, 0)
    with pytest.raises(Refused, match="hosted budget exhausted"):                     # the ceiling is full ...
        a.reserve_amount(jid(3), CLIENT, 1, now=30)
    launch(a, root, 4, 3_740_000, entries=ok_ledger(), now=40, budget=B)             # ... but a budget launch is bounded by its budget only
    t = a.totals()
    assert {k: t[k] for k in ("committed_microusd", "reserved_microusd", "available_microusd")} == \
           {k: before[k] for k in ("committed_microusd", "reserved_microusd", "available_microusd")}  # the ceiling's scope is unchanged
    assert budget_fig(a)["outstanding_micro_aud"] == 5_610_000
    assert ST.settle_automatic(a, root, jid(1), log=lambda *_: None)["settled_microusd"] == 30_000   # settling a programme run never changes the budget
    assert budget_fig(a)["outstanding_micro_aud"] == 5_610_000 and budget_fig(a)["spent_micro_aud"] == 0


def test_settlement_replaces_a_budget_jobs_reservation_by_its_actual_cost(tmp_path):
    a, root = setup(tmp_path)
    open_b20(a)
    j = launch(a, root, 1, 3_740_000, entries=ok_ledger(3, 0.04, 0.2105836667), now=10, budget=B)
    assert budget_fig(a)["outstanding_micro_aud"] == 5_610_000
    s = ST.settle_automatic(a, root, j, log=lambda *_: None)
    b = budget_fig(a)
    assert s["settled_microusd"] == b["spent_microusd"] == 631_752                    # 3 x 210 584 µUS$ (each rounded up)
    assert (b["spent_micro_aud"], b["outstanding_micro_aud"], b["available_micro_aud"]) == (947_628, 0, 19_052_372)
    assert b["released_microusd"] == 3_740_000 - 631_752
    assert ST.settle_automatic(a, root, j, log=lambda *_: None) is None              # once only
    assert a.totals()["settled_microusd"] == 0                                        # not the ceiling's (programme) settled spend


def test_failed_interrupted_or_running_budget_jobs_keep_their_full_reservation(tmp_path):
    a, root = setup(tmp_path)
    open_b20(a)
    running = launch(a, root, 1, 3_740_000, entries=[("reserve", "r0", 0.04)], now=10, state="running", budget=B)
    assert ST.settle_automatic(a, root, running, log=lambda *_: None) is None
    a.transition(running, "running", "interrupted")                                   # restart while a request was in flight
    assert ST.reconcile_automatic(a, root, log=lambda *_: None) == []
    failed = launch(a, root, 2, 3_740_000, entries=None, now=20, state="failed", budget=B)
    assert ST.settle_automatic(a, root, failed, log=lambda *_: None) is None         # "failed" alone releases nothing
    assert budget_fig(a)["outstanding_micro_aud"] == 2 * 5_610_000
    out = ST.settle(a, root, running, actor="owner terminal", allow_open=True)       # owner recovery: the open request at its full bound
    assert out["settled_microusd"] == 40_000 and budget_fig(a)["spent_micro_aud"] == 60_000


def test_the_global_cap_bounds_every_commitment_even_if_the_ceiling_is_raised_later(tmp_path):
    a, root = setup(tmp_path, ceiling=10_000_000)
    open_b20(a)
    assert a.totals()["global_cap_microusd"] == 23_333_333
    db = sqlite3.connect(a.path)                                                      # simulate a later ceiling increase (owner migration)
    db.execute("UPDATE policy SET ceiling=100000000 WHERE id=1")
    db.commit()
    db.close()
    a2 = Admission.open_existing(a.path)
    launch(a2, root, 1, 13_333_333, entries=None, now=10, state="failed", budget=B)
    with pytest.raises(Refused, match="global hosted cap reached"):
        a2.reserve_amount(jid(2), CLIENT, 10_000_001, now=20)                       # within the raised ceiling, above the global cap
    a2.reserve_amount(jid(3), CLIENT, 10_000_000, now=30)
    assert a2.totals()["global_available_microusd"] == 0 and a2.capacity_microusd(None) == 0


# --------------------------------------------------------------------------------------------------------------- concurrency
def test_concurrent_allocations_never_exceed_the_budget(tmp_path):
    a, _ = setup(tmp_path)
    open_b20(a)
    ok, refused, gate = [], [], threading.Barrier(10)

    def go(n):
        conn = Admission.open_existing(a.path)                                        # separate connection per thread
        gate.wait()
        try:
            BG.allocate(conn, B, f"dev-{n:02d}", "2", "concurrency test", actor="owner")  # US$2 = A$3 each: 6 fit in A$20, the 7th would be A$21
            ok.append(n)
        except Refused:
            refused.append(n)

    ts = [threading.Thread(target=go, args=(n,)) for n in range(10)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    b = budget_fig(a)
    assert (len(ok), len(refused)) == (6, 4)
    assert (b["outstanding_micro_aud"], b["available_micro_aud"], b["open_allocations"]) == (18_000_000, 2_000_000, 6)


def test_concurrent_launches_across_scopes_admit_exactly_one_within_every_limit(tmp_path):
    a, _ = setup(tmp_path, ceiling=5_000_000)
    open_b20(a)
    ok, gate = [], threading.Barrier(8)

    def go(n):
        conn = Admission.open_existing(a.path)
        gate.wait()
        try:
            conn.reserve_amount(jid(100 + n), "%064x" % n, 3_740_000, now=1000, budget=B if n % 2 else None)
            ok.append(n)
        except Refused:
            pass

    ts = [threading.Thread(target=go, args=(n,)) for n in range(8)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    t = a.totals()
    assert len(ok) == 1 and len(a.active()) == 1                                      # the single evaluation slot
    assert t["committed_microusd"] <= 5_000_000 and budget_fig(a)["committed_micro_aud"] <= 20_000_000
    assert t["all_committed_microusd"] <= t["global_cap_microusd"]


# --------------------------------------------------------------------------------------------------------------- off-host allocations
def test_an_off_host_allocation_is_held_before_use_and_settles_once_from_its_ledger(tmp_path):
    a, root = setup(tmp_path)
    open_b20(a)
    with pytest.raises(Refused, match="no such budget"):
        BG.allocate(a, "nope-budget", "dev-1", "1", "x", actor="owner")
    BG.allocate(a, B, "dev-taskgen-1", "0.50", "task generation", actor="owner")
    assert budget_fig(a)["outstanding_micro_aud"] == 750_000                          # held at its maximum before any request is sent
    with pytest.raises(BG.BudgetRefused, match="exists"):
        BG.allocate(a, B, "dev-taskgen-1", "0.10", "again", actor="owner")
    led = ledger_file(tmp_path, "dev.jsonl", ok_ledger(2, 0.05, 0.0123456))
    with pytest.raises(BG.BudgetRefused, match="not the expected"):
        BG.settle_allocation(a, "dev-taskgen-1", [led], actor="owner", expect_microusd=1)
    out = BG.settle_allocation(a, "dev-taskgen-1", [led], actor="owner", expect_microusd=24_692)
    b = budget_fig(a)
    assert out["settled_microusd"] == 24_692 and (b["spent_micro_aud"], b["outstanding_micro_aud"]) == (37_038, 0)
    assert BG.settle_allocation(a, "dev-taskgen-1", [led], actor="owner")["already"] is True       # idempotent
    BG.allocate(a, B, "dev-taskgen-2", "0.50", "second", actor="owner")
    with pytest.raises(BG.BudgetRefused, match="already settled allocation dev-taskgen-1"):        # one ledger is charged once
        BG.settle_allocation(a, "dev-taskgen-2", [led], actor="owner")
    open_led = ledger_file(tmp_path, "open.jsonl", ok_ledger(1) + [("reserve", "late", 0.05)])
    with pytest.raises(BG.BudgetRefused, match="never settled"):
        BG.settle_allocation(a, "dev-taskgen-2", [open_led], actor="owner")
    big = ledger_file(tmp_path, "big.jsonl", ok_ledger(1, 0.9, 0.6))
    with pytest.raises(BG.BudgetRefused, match="more than the allocation"):
        BG.settle_allocation(a, "dev-taskgen-2", [big], actor="owner")
    assert BG.settle_allocation(a, "dev-taskgen-2", [open_led], actor="owner", allow_open=True)["settled_microusd"] == 60_000   # open at its bound
    j = launch(a, root, 1, 3_740_000, entries=ok_ledger(), now=10, budget=B)         # a hosted job's ledger can never also settle an allocation
    ST.settle_automatic(a, root, j, log=lambda *_: None)
    BG.allocate(a, B, "dev-taskgen-3", "0.50", "third", actor="owner")
    job_ledger = root.parent / "lifecycle" / "stage-b" / "ledgers" / "pool-l1" / "ledger.jsonl"
    with pytest.raises(BG.BudgetRefused, match="already settled hosted job"):
        BG.settle_allocation(a, "dev-taskgen-3", [job_ledger], actor="owner")
    assert budget_fig(a)["open_allocations"] == 1                                     # never settled -> still held in full


def test_a_crash_during_allocation_settlement_leaves_no_partial_record(tmp_path):
    a, _ = setup(tmp_path)
    open_b20(a)
    BG.allocate(a, B, "dev-1", "1", "x", actor="owner")
    led = ledger_file(tmp_path, "l.jsonl", ok_ledger())
    db = sqlite3.connect(a.path)
    db.execute("CREATE TRIGGER boom BEFORE INSERT ON allocation_settlements BEGIN SELECT RAISE(ABORT, 'injected crash'); END")
    db.commit()
    with pytest.raises(sqlite3.IntegrityError, match="injected crash"):
        BG.settle_allocation(a, "dev-1", [led], actor="owner")
    assert budget_fig(a)["outstanding_micro_aud"] == 1_500_000                         # still held in full
    db.execute("DROP TRIGGER boom")
    db.commit()
    db.close()
    assert BG.settle_allocation(a, "dev-1", [led], actor="owner")["settled_microusd"] == 30_000      # the retry settles


# --------------------------------------------------------------------------------------------------------------- rollback, read-only, CLI
def test_an_older_image_counts_budget_jobs_against_the_ceiling_and_is_more_conservative(tmp_path):
    a, root = setup(tmp_path)
    launch(a, root, 1, 3_740_000, entries=ok_ledger(), now=10)
    open_b20(a)
    launch(a, root, 2, 3_740_000, entries=None, now=20, state="failed", budget=B)
    db = sqlite3.connect(a.path)
    old_dde7e22 = db.execute("SELECT COALESCE(SUM(CASE WHEN s.job_id IS NULL THEN j.reserved ELSE s.settled END),0) FROM jobs j LEFT JOIN settlements s "
                             "ON s.job_id=j.id").fetchone()[0]                        # dde7e22's committed (no scopes)
    old_83be351 = db.execute("SELECT SUM(reserved) FROM jobs").fetchone()[0]
    with pytest.raises(sqlite3.IntegrityError):                                       # a job can be in at most one budget
        db.execute("INSERT INTO budget_jobs VALUES (?,?,?)", (jid(2), "other", 0))
    db.close()
    assert old_83be351 >= old_dde7e22 >= a.totals()["committed_microusd"] + 3_740_000
    assert CE.status(a.path)["budget_jobs"] == 1 and CE.status(a.path)["committed"] == a.totals()["committed_microusd"]


def test_budget_status_is_read_only_and_changes_need_a_terminal(tmp_path, capsys):
    a, _ = setup(tmp_path)
    open_b20(a)
    before = sha(a.path)
    st = BG.status(Admission.open_read_only(a.path))
    assert sha(a.path) == before and st["budgets"][0]["available_micro_aud"] == 20_000_000
    assert BG.main(["allocate", "--db", str(a.path), "--budget", B, "--ref", "dev-1", "--max-usd", "1", "--purpose", "x"]) == 2   # stdin is not a TTY
    assert BG.main(["open", "--db", str(a.path), "--id", "x-budget", "--limit-aud", "1", "--rate", "1.50"]) == 2
    assert sha(a.path) == before


# --------------------------------------------------------------------------------------------------------------- programme ledger identity
def test_the_programme_ledger_matches_jobs_by_identity_and_detects_duplicates():
    doc = json.loads(LEDGER.read_text())
    assert PG.check(doc) == []
    assert PG.recorded_jobs(doc) == {"eval-9aaac35ca488c2bf951e01e58746604a": "hosted-live-1", "eval-aa23e33012717c4a30ca21be1239e85f": "hosted-live-2",
                                     E529: "hosted-stageb-live-1"}
    dup = json.loads(json.dumps(doc))
    dup["entries"].append({"id": "again", "usd": 1.546226, "hosted_job": E529})
    assert any("recorded twice" in p for p in PG.check(dup))
    dup2 = json.loads(json.dumps(doc))
    dup2["entries"].append(dict(dup2["entries"][0]))
    assert any("appears twice" in p for p in PG.check(dup2))
    hidden = json.loads(json.dumps(doc))
    hidden["entries"].append({"id": "x", "usd": 0.1, "label": f"mentions {C04} in text only"})
    assert any("without declaring it" in p for p in PG.check(hidden))                  # text never counts as identity
    assert any("charged to budget" in p for p in PG.check({"entries": [{"id": "y", "usd": 1, "hosted_job": C04}]}, {C04: B}))
    assert any("belongs to budget" in p for p in PG.check({"entries": [{"id": "z", "usd": 1, "budget": B}]}))
    assert any("differs from its recorded identity" in p for p in PG.check({"entries": [{"id": "hosted-live-1", "usd": 1, "hosted_job": C04}]}))
    with pytest.raises(PG.ProgrammeRefused):
        PG.append(doc, {"id": "again", "usd": 1, "hosted_job": E529})


# --------------------------------------------------------------------------------------------------------------- production copies
@pytest.fixture
def prod(tmp_path, monkeypatch):
    """A copy of production's hosted data (after eval-c04) plus the retired engine's job records, forked ledgers AND fork records."""
    data = tmp_path / "hosted"
    shutil.copytree(FS, data)
    for j, (run, _) in IRON.items():
        shutil.copy(M9 / "live" / f"{j}.job.json", data / "live")
        (data / "live" / run / "spend").mkdir(parents=True, exist_ok=True)
        shutil.copy(M9 / "live" / run / "spend" / "ledger.jsonl", data / "live" / run / "spend")
        shutil.copy(M9 / "live" / run / "fork.json", data / "live" / run)
    monkeypatch.setenv("AR_STAGE_B_ROOT", str(data / "lifecycle" / "stage-b"))
    return data


@need_prod
def test_the_copied_ledger_rule_attributes_each_ironbark_job_exactly_its_own_requests(prod):
    db = prod / "live" / "admission.sqlite"
    files = {p: sha(p) for p in (prod / "live").rglob("*") if p.is_file() and ("paired-" in str(p) or p.suffix == ".json")}
    source_before = sha(SOURCE) if SOURCE.is_file() else None
    rep = ST.audit(Admission.open_read_only(db), prod / "live")
    by = {j["job"]: j for j in rep["jobs"]}
    for job, (run, own) in IRON.items():
        j = by[job]
        assert j["eligible"] is True and j["commit_microusd"] == own and j["release_microusd"] == 1_650_000 - own
        assert j["ledger"]["open_requests"] == 0 and j["ledger"]["bound_violations"] == 0
        assert ST.FORK_RULE in j["basis"] and "recorded once as ironbark-source" in j["basis"]
        assert j["fork"] == [{"run": run, "source_run": "live-2d58a80e14", "imported_lines": 126, "imported_sha256": next(iter(ST.RECORDED_SOURCES)),
                              "imported_settled_microusd": 864_825, "recorded_as": "ironbark-source"}]
    doc = json.loads(LEDGER.read_text())
    entries = {e["id"]: e for e in doc["entries"]}
    assert (by[list(IRON)[0]]["commit_microusd"], by[list(IRON)[1]]["commit_microusd"]) == (PG.micro(entries["hosted-live-1"]["usd"]), PG.micro(entries["hosted-live-2"]["usd"]))
    assert PG.micro(entries["ironbark-source"]["usd"]) == 864_825                      # the imported part is recorded once, separately
    a = Admission.open_existing(db)
    assert ST.reconcile_automatic(a, prod / "live", log=lambda *_: None) == []       # historical: never settled automatically
    before = a.totals()["available_microusd"]
    for job, (_, own) in IRON.items():
        assert ST.settle(a, prod / "live", job, actor="owner terminal", expect_microusd=own)["settled_microusd"] == own
    assert a.totals()["available_microusd"] - before == 1_082_935
    assert all(sha(p) == h for p, h in files.items())                                 # no ledger, fork record or job record changed
    if source_before:
        assert sha(SOURCE) == source_before


@need_prod
def test_the_copied_ledger_rule_refuses_anything_it_cannot_prove(prod):
    job, (run, _) = next(iter(IRON.items()))
    led = prod / "live" / run / "spend" / "ledger.jsonl"
    fork = prod / "live" / run / "fork.json"
    a = Admission.open_read_only(prod / "live" / "admission.sqlite")
    raw = led.read_bytes()
    i = raw.index(b'"usd": ') + 8
    led.write_bytes(raw[:i] + (b"9" if raw[i:i + 1] != b"9" else b"8") + raw[i + 1:])  # one byte of the imported part
    assert ST.assess(a, prod / "live", job)["reason"] == "fork_prefix_mismatch"
    led.write_bytes(raw)
    f = json.loads(fork.read_text())
    f["source_ledger"]["sha256"] = "0" * 64
    fork.write_text(json.dumps(f))
    assert ST.assess(a, prod / "live", job)["reason"] == "fork_source_unrecorded"
    f["source_ledger"].pop("sha256")
    fork.write_text(json.dumps(f))
    assert ST.assess(a, prod / "live", job)["reason"] == "exceeds_reservation"       # no declared import: the whole ledger counts (as before)
    first = json.loads(raw.splitlines()[0])
    fork.write_text(json.dumps({**f, "source_ledger": {"sha256": next(iter(ST.RECORDED_SOURCES)), "entries": 126}}))
    led.write_bytes(raw + (json.dumps({"ts": "t", "kind": "settle", "id": first["id"], "usd": 0.0}) + "\n").encode())
    assert ST.assess(a, prod / "live", job)["reason"] == "ledger_malformed"          # the remainder may not touch an imported request


@need_prod
def test_existing_judge_launches_stay_programme_jobs_and_a_v2_arming_is_charged_to_its_budget(prod, monkeypatch):
    from agent_readiness.evalruns import authorization as AU
    from agent_readiness.hosted.stageb import StageBExecutor
    from agent_readiness.lifecycle import arming as AR
    from agent_readiness.suites.store import WriteOnceStore
    sb = prod / "lifecycle" / "stage-b"
    monkeypatch.setattr(AU, "STAGE_B", sb)
    AR.set_stage_b_root(sb)
    store = WriteOnceStore(prod / "lifecycle" / "store")
    claims = {json.loads(p.read_text())["arming_id"]: json.loads(p.read_text())["arming_sha256"] for p in (sb / "launches").glob("*.json")}
    for aid in ("larkspur-judge-1", "larkspur-live-1"):                              # recorded v1 armings: unchanged hash, still verify
        rec = AR.load(aid)
        assert rec.schema_ == AR.SCHEMA and rec.budget is None and "budget" not in rec.content()
        assert rec.sha256 == claims[aid] and AR.verify(store, rec) == []
    db = prod / "live" / "admission.sqlite"
    a = Admission.open_existing(db)
    ST.settle(a, prod / "live", C04, actor="owner terminal", expect_microusd=631_751)
    legacy_before = a.capacity_microusd(None)
    open_b20(a)
    assert a.capacity_microusd(None) == legacy_before == 10_588_249                  # opening the budget does not change the programme's capacity
    ex = StageBExecutor(prod / "live", prod / "lifecycle" / "store", a, mode="live")
    first = ex.admit(jid(900), "%064x" % 900, 1)["id"]                                # larkspur-judge-1 (v1): a programme job
    assert a.job_budget(first) is None and budget_fig(a)["jobs"] == 0
    a.transition(first, "reserved", "failed")
    assert a.capacity_microusd(None) == 10_588_249 - 3_740_000
    kw = dict(arming_id="budget-pool-1", mode="paid", frozen_ref="larkspur-core@v3", variants=["original", "improved"], repetitions=[1], launches=3, budget=B)
    p = AR.plan(store, **kw)
    assert p["attestation"].endswith(f"every launch is charged to the separate budget {B}, not to the A$50 programme or the hosted ceiling")
    AR.arm(store, typed=p["attestation"], at="2026-11-04T00:00:00+00:00", interactive=True, **kw)
    rec = AR.active()
    assert (rec.schema_, rec.budget, AR.verify(store, rec)) == (AR.SCHEMA_V2, B, [])
    summ = AR.summary(store, rec, a)
    assert summ["charged_to"] == f"budget {B}" and summ["capacity"]["launches_affordable"] == 3       # A$20 / A$5.61
    admitted = []
    for n in range(4):
        try:
            admitted.append(ex.admit(jid(910 + n), "%064x" % (910 + n), 1)["id"])
        except AR.ArmingRefused:
            break
        a.transition(admitted[-1], "reserved", "failed")
    assert len(admitted) == 3 and all(a.job_budget(j) == B for j in admitted)
    b = budget_fig(a)
    assert (b["outstanding_micro_aud"], b["available_micro_aud"]) == (3 * 5_610_000, 20_000_000 - 3 * 5_610_000)
    assert a.capacity_microusd(None) == 10_588_249 - 3_740_000                       # the programme scope is untouched by budget launches
    t = a.totals()
    assert t["all_committed_microusd"] <= t["global_cap_microusd"] == CEIL + 13_333_333
    with pytest.raises(Exception):                                                    # a v2 arming without a budget, or a v1 with one, is invalid
        AR.Arming.model_validate({**rec.content(), "budget": None})
    with pytest.raises(Exception):
        AR.Arming.model_validate({**AR.load("larkspur-judge-1").content(), "budget": B})


@need_prod
def test_the_programme_view_counts_actual_costs_once_and_the_c04_append_never_double_counts(prod):
    db = prod / "live" / "admission.sqlite"
    doc = json.loads(LEDGER.read_text())
    a = Admission.open_existing(db)
    v0 = PG.view(doc, a, prod / "live")                                               # before settlement: c04's verified ledger, not its reservation
    assert (v0["spend_to_date_usd"], v0["not_in_ledger"][0]["job"], v0["unverified_exposure_usd"]) == (19.418057, C04, 0)
    ST.settle(a, prod / "live", C04, actor="owner terminal", expect_microusd=631_751)
    v = PG.view(doc, a, prod / "live")
    assert (v["known_usd"], v["spend_to_date_usd"], v["spend_to_date_aud"], v["hosted_available_usd"]) == (18.786306, 19.418057, 29.13, 10.588249)
    assert (v["worst_case_usd"], v["worst_case_aud"], v["within_limit"], v["problems"]) == (30.006306, 45.01, True, [])
    assert sorted(r["entry"] for r in v["recorded_jobs"]) == ["hosted-live-1", "hosted-live-2", "hosted-stageb-live-1"]
    prop = PG.propose(doc, a, prod / "live", job=C04, entry_id="hosted-stageb-judge-1", label="t", authorized_by="owner", recorded_on="2026-11-04")
    assert (prop["entry"]["usd"], prop["entry"]["hosted_job"], prop["known_usd_after"], prop["problems_after"]) == (0.631751, C04, 19.418057, [])
    raw = LEDGER.read_text()
    new_raw = PG.append_text(raw, prop["entry"])
    close = PG._entries_close(raw)
    assert new_raw.startswith(raw[:close].rstrip()) and new_raw.endswith(raw[close:])   # every existing byte kept
    new = json.loads(new_raw)
    v2 = PG.view(new, a, prod / "live")
    assert (v2["spend_to_date_usd"], v2["not_in_ledger"], v2["worst_case_aud"]) == (19.418057, [], 45.01)    # recorded once, not twice
    with pytest.raises(PG.ProgrammeRefused, match="already recorded"):
        PG.propose(new, a, prod / "live", job=C04, entry_id="again", label="t", authorized_by="o", recorded_on="d")
    with pytest.raises(PG.ProgrammeRefused, match="not_settled|no settlement"):
        PG.propose(doc, a, prod / "live", job=E529, entry_id="x", label="t", authorized_by="o", recorded_on="d")
    assert LEDGER.read_text() == raw                                                  # the repository's programme ledger is never written by tests


@need_prod
def test_the_workspace_api_separates_programme_ceiling_and_budget(prod, monkeypatch):
    from fastapi.testclient import TestClient

    from agent_readiness.hosted.api import create_app
    from agent_readiness.hosted.stageb import StageBExecutor
    from agent_readiness.lifecycle import arming as AR
    from agent_readiness.lifecycle.service import LifecycleService
    monkeypatch.setenv("AR_PROGRAMME_LEDGER", str(LEDGER))
    AR.set_stage_b_root(prod / "lifecycle" / "stage-b")
    root = prod / "live"
    a = Admission(root / "admission.sqlite", ceiling_microusd=CEIL, job_cap_microusd=1_650_000, min_interval_seconds=120)
    ST.settle(a, root, C04, actor="owner terminal", expect_microusd=631_751)
    ex = StageBExecutor(root, prod / "lifecycle" / "store", a, mode="live")
    svc = LifecycleService(datasets=None, store_root=prod / "lifecycle" / "store", runs_root=root / "stageb", executor=ex, admission=a, log=lambda *_: None)
    c = TestClient(create_app(root, a, client_key=b"k" * 32, executor=ex, operator_token=b"o" * 32, public_start=False, mode="live", lifecycle=svc))
    s = c.get("/api/ironbark/config").json()["spending"]
    assert (s["ceiling"], s["settled"], s["outstanding"], s["available"], s["global"], s["budgets"], s["charged_to"]) == (21.956, 0.631751, 10.736, 10.588249, None, [], None)
    p = s["programme"]
    assert (p["spent_usd"], p["spent_aud"], p["worst_case_aud"], p["within_limit"], p["ledger_problems"]) == (19.418057, 29.13, 45.01, True, 0)
    open_b20(a)
    c2 = TestClient(create_app(root, a, client_key=b"k" * 32, executor=ex, operator_token=b"o" * 32, public_start=False, mode="live", lifecycle=svc))
    s = c2.get("/api/ironbark/config").json()["spending"]
    assert s["budgets"] == [{"id": B, "limit_aud": 20.0, "rate_aud_per_usd": 1.5, "spent_aud": 0.0, "outstanding_aud": 0.0, "available_aud": 20.0, "spent_usd": 0.0,
                             "outstanding_usd": 0.0, "available_usd": 13.333333, "jobs": 0, "settled_jobs": 0, "allocations": 0, "open_allocations": 0}]
    assert s["global"]["cap_usd"] == 35.289333 and s["available"] == 10.588249 and s["programme"]["spent_usd"] == 19.418057
    rows = {r["id"]: r for r in c2.get("/api/ironbark/jobs").json()}
    assert rows[C04]["cost_usd"] == 0.631751 and rows[C04]["budget"] is None
