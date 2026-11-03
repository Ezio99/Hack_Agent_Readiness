"""One access code, one launch flow, one shared A$20 budget (2026-11).

Every valid access code launches the same way. While the shared budget is open, launches run its evaluation (no launch count; the budget is the
limit) and the owner's earlier arming and its count are not used. Each launch reserves its maximum atomically; a double-click or retry returns the
same run; one evaluation runs at a time; invalid codes are rate-limited; codes are never returned or recorded. The real Stage B executor and
admission are used; only the worker subprocess is replaced (no browser, no model; see test_m9_judge_access)."""
import importlib.util
import sqlite3
import threading
import time
from pathlib import Path

import pytest

from agent_readiness.evalruns import authorization as AU
from agent_readiness.lifecycle import arming as AR

_spec = importlib.util.spec_from_file_location("m9_judge_access", Path(__file__).parent / "test_m9_judge_access.py")
M = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(M)
CODE = {"authorization": "Bearer " + M.JUDGE.decode()}                 # the shared access code (the judge code file in production)


@pytest.fixture
def env(tmp_path, monkeypatch):
    return M.env.__wrapped__(tmp_path, monkeypatch)


def run(c, key=None, headers=CODE):
    return c.post("/api/ironbark/jobs", json={"repetitions": 1}, headers={**headers, **({"idempotency-key": key} if key else {})})


def test_a_valid_code_launches_the_shared_budget_evaluation_without_any_launch_count(env):
    c, ex, a = M.app(env)
    budget = M.open_pool(env, a)
    cfg = c.get("/api/ironbark/config").json()
    assert cfg["launch"]["authorized"] and cfg["launch"]["launches_left"] is None and cfg["evaluation"]["launches"] is None
    assert cfg["spending"]["charged_to"] == budget and cfg["spending"]["budgets"][0]["available_aud"] == 20.0
    jobs = []
    for n in range(6):                                                                # beyond the arming's count of 4: no quota, only the budget
        r = run(c, key=f"click-{n}-0123456789abcdef")
        if r.status_code != 202:
            break
        jobs.append(r.json()["id"])
        M.settle(a, jobs[-1])
        a.record_settlement(jobs[-1], 0, basis="test: nothing sent", ledger_sha256="%064x" % n, ledger_requests=0, open_requests=0, actor="test") \
            if a.settlement(jobs[-1]) is None else None
        time.sleep(1.05)
    assert len(jobs) == 6 and all(a.job_budget(j) == budget for j in jobs)
    assert AR.claims("judge-test-1") == [] and len(AR.claims(budget)) == 6           # the arming was never used; its record is untouched
    st = c.get(f"/api/ironbark/jobs/{jobs[0]}").json()["accounting"]
    assert st["budget"] == budget and st["settled"] is True and st["cost_usd"] == 0


def test_the_budget_is_atomic_and_an_exhausted_budget_refuses_with_an_explanation(env):
    c, ex, a = M.app(env, interval=1)
    budget = M.open_pool(env, a)
    held = []
    for wave in range(8):                                                             # waves of 5 concurrent clicks with distinct keys
        ex.gate = threading.Event()                                                   # hold the run so the clicks truly overlap with it
        out, bar = [], threading.Barrier(5)

        def click(n):
            bar.wait()
            out.append(run(c, key=f"w{wave}-c{n}-0123456789abcdef"))

        ts = [threading.Thread(target=click, args=(n,)) for n in range(5)]
        [t.start() for t in ts]
        [t.join() for t in ts]
        ok = [r for r in out if r.status_code == 202]
        assert len(ok) <= 1                                                           # one evaluation at a time
        assert all(r.status_code in (202, 409, 429) for r in out)                    # the others: "already running" (or the budget is used)
        ex.gate.set()
        for r in ok:
            M.settle(a, r.json()["id"])                                               # ends without results: kept at its full reservation
            held.append(r.json()["id"])
        if not ok and any(r.status_code == 429 and "budget has been used" in r.json()["detail"] for r in out):
            break
        time.sleep(1.05)
    b = a.totals()["budgets"][0]
    per = b["outstanding_micro_aud"] // len(held)
    # soft cap: admitted while the pool's commitments are below A$20 (unreconciled runs count in full); the last admitted run may cross it
    assert len(held) == -(-20_000_000 // per) and b["committed_micro_aud"] >= 20_000_000 > b["committed_micro_aud"] - per
    before = len(a.recent())
    r = run(c, key="after-exhaustion-0123456789")
    assert r.status_code == 429 and "budget has been used" in r.json()["detail"] and len(a.recent()) == before
    cfg = c.get("/api/ironbark/config").json()
    assert cfg["launch"]["authorized"] is False and cfg["launch"]["reason"] == "budget_exhausted"


def test_double_clicks_and_retries_start_one_run_and_others_can_watch_it(env):
    c, ex, a = M.app(env)
    M.open_pool(env, a)
    ex.gate = threading.Event()                                                       # hold the stand-in worker so the run stays active
    out, bar = [], threading.Barrier(4)

    def click():
        bar.wait()
        out.append(run(c, key="same-click-0123456789"))

    ts = [threading.Thread(target=click) for _ in range(4)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    ids = {r.json()["id"] for r in out if r.status_code == 202}
    assert [r.status_code for r in out] == [202] * 4 and len(ids) == 1 and len(a.recent()) == 1
    job = ids.pop()
    assert run(c, key="same-click-0123456789").json()["duplicate"] is True
    busy = run(c, key="another-click-0123456789")
    assert busy.status_code == 409 and "already running" in busy.json()["detail"] and job[:13] in busy.json()["detail"]   # told to watch it
    cfg = c.get("/api/ironbark/config").json()
    assert cfg["active"] == job and cfg["worker"]["state"] == "busy" and cfg["worker"]["job"] == job
    assert c.get(f"/api/ironbark/jobs/{job}").status_code == 200 and c.get(f"/api/ironbark/jobs/{job}/live").status_code == 200   # anyone can watch
    ex.gate.set()
    M.settle(a, job)
    assert run(c, key="x").status_code == 422


def test_invalid_codes_are_refused_rate_limited_and_never_reserve_but_a_valid_code_always_passes(env):
    c, _, a = M.app(env)
    M.open_pool(env, a)
    for _ in range(10):
        assert run(c, headers={"authorization": "Bearer wrong-code-but-long-enough-0123"}).status_code == 403
    assert run(c, headers={"authorization": "Bearer wrong-code-but-long-enough-0123"}).status_code == 429
    assert a.recent() == []
    assert run(c, key="valid-after-typos-0123456789").status_code == 202                # a valid code is never blocked by the limiter


def test_codes_never_appear_in_responses_or_files(env, capsys):
    c, _, a = M.app(env)
    M.open_pool(env, a)
    job = run(c, key="b" * 20).json()["id"]
    M.settle(a, job)
    for path in ("/api/health", "/api/ironbark/config", "/api/ironbark/jobs", f"/api/ironbark/jobs/{job}"):
        text = c.get(path).text
        assert M.JUDGE.decode() not in text and M.OPERATOR.decode() not in text
    for f in list(env["root"].rglob("*")) + list(AU.STAGE_B.rglob("*")) + [env["tmp"] / "a.sqlite"]:
        if f.is_file():
            assert M.JUDGE not in f.read_bytes() and M.OPERATOR not in f.read_bytes(), f
    out = capsys.readouterr()
    assert M.JUDGE.decode() not in out.out + out.err


def test_historical_jobs_stay_out_and_launches_before_opening_are_unchanged(env):
    c, _, a = M.app(env)
    before = run(c, key="before-open-0123456789").json()["id"]                        # before the budget: the owner's arming, as in production today
    M.settle(a, before)
    assert a.job_budget(before) is None and AR.claims("judge-test-1")[0]["job"] == before
    budget = M.open_pool(env, a)
    assert a.totals()["budgets"][0]["jobs"] == 0 and a.job_budget(before) is None     # the budget starts fresh; history keeps its scope
    time.sleep(1.05)
    after = run(c, key="after-open-0123456789").json()["id"]
    M.settle(a, after)
    assert a.job_budget(after) == budget and [x["job"] for x in AR.claims("judge-test-1")] == [before]
    db = sqlite3.connect(env["tmp"] / "a.sqlite")
    assert db.execute("SELECT COUNT(*) FROM budget_jobs").fetchone()[0] == 1


def _spend(a, budget, micro_aud_target):
    """Record settled budget runs (as if earlier evaluations had cost this much) so the pool's actual spending is exactly the target (in µA$)."""
    n = 0
    db = sqlite3.connect(a.path)
    while True:
        spent = next(x for x in a.totals()["budgets"] if x["budget"] == budget)["spent_micro_aud"]
        if spent >= micro_aud_target:
            break
        usd = min(3_740_000, (micro_aud_target - spent) * 2 // 3) or 1
        job = "eval-" + f"{0xf00 + n:032x}"
        db.execute("INSERT INTO jobs VALUES (?,?,?,?,?)", (job, "f" * 64, 1.0 + n, "completed", 3_740_000))
        db.execute("INSERT INTO budget_jobs VALUES (?,?,?)", (job, budget, 1.0 + n))
        db.commit()
        a.record_settlement(job, usd, basis="test", ledger_sha256="%064x" % (0xf00 + n), ledger_requests=1, open_requests=0, actor="test")
        n += 1
    db.close()


def test_exactly_two_conditions_valid_code_and_actual_spend_below_twenty(env):
    c, ex, a = M.app(env, interval=120)                                               # a 120 s per-client interval never applies to budget launches
    budget = M.open_pool(env, a)
    j1 = run(c, key="first-0123456789abcdef").json()["id"]
    M.settle(a, j1)
    a.record_settlement(j1, 0, basis="test", ledger_sha256="%064x" % 1, ledger_requests=0, open_requests=0, actor="test") if a.settlement(j1) is None else None
    r = run(c, key="second-0123456789abcdef")                                        # straight away: no cooldown, no launch count, no arming
    assert r.status_code == 202, r.text
    M.settle(a, r.json()["id"])
    a.record_settlement(r.json()["id"], 0, basis="test", ledger_sha256="%064x" % 2, ledger_requests=0, open_requests=0, actor="test") \
        if a.settlement(r.json()["id"]) is None else None
    _spend(a, budget, 19_999_990)                                                     # near the limit: just under A$20 actually spent
    b = next(x for x in a.totals()["budgets"] if x["budget"] == budget)
    assert 19_999_990 <= b["spent_micro_aud"] < 20_000_000 and c.get("/api/ironbark/config").json()["launch"]["authorized"] is True
    near = run(c, key="near-limit-0123456789ab")                                      # admitted although its worst case exceeds what remains
    assert near.status_code == 202, near.text
    job = near.json()["id"]
    M.settle(a, job)
    over = 1_000_000                                                                  # it finishes above A$20 (US$1 more, within its own cap)
    if a.settlement(job) is None:
        a.record_settlement(job, over, basis="test", ledger_sha256="%064x" % 3, ledger_requests=1, open_requests=0, actor="test")
    b = next(x for x in a.totals()["budgets"] if x["budget"] == budget)
    assert b["spent_micro_aud"] >= 20_000_000 and b["available_micro_aud"] < 0
    r = run(c, key="exhausted-0123456789abc")
    assert r.status_code == 429 and "budget has been used" in r.json()["detail"]
    cfg = c.get("/api/ironbark/config").json()
    assert cfg["launch"]["authorized"] is False and cfg["launch"]["reason"] == "budget_exhausted"
    assert AR.claims("judge-test-1") == []                                            # the arming was never consulted
    t = a.totals()
    assert t["all_committed_microusd"] <= t["global_cap_microusd"]                    # the hard global cap held, without ever refusing a launch
