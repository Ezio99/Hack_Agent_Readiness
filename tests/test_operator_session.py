"""One-click operator evaluations against the separate budget (2026-11): a server-side operator session instead of a token held by the page, a
CSRF guard on cookie-authenticated launches, idempotent launches (double-click / retry), and the judge path kept separate.

The real Stage B executor and admission are used; only the worker subprocess is replaced (no browser, no model; see test_m9_judge_access)."""
import importlib.util
import threading
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from agent_readiness.evalruns import authorization as AU
from agent_readiness.lifecycle import arming as AR

_spec = importlib.util.spec_from_file_location("m9_judge_access", Path(__file__).parent / "test_m9_judge_access.py")
M = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(M)
OPERATOR, JUDGE = M.OPERATOR, M.JUDGE
CSRF = {"x-agent-readiness": "1"}


@pytest.fixture
def env(tmp_path, monkeypatch):
    return M.env.__wrapped__(tmp_path, monkeypatch)


def client(env, **kw):
    c, ex, a = M.app(env, **kw)
    return TestClient(c.app, base_url="https://testserver"), ex, a


def sign_in(c):
    return c.post("/api/operator/session", headers={**CSRF, "authorization": "Bearer " + OPERATOR.decode()})


def run(c, key=None, headers=None):
    h = {**CSRF, **(headers or {})}
    if key:
        h["idempotency-key"] = key
    return c.post("/api/ironbark/jobs", json={"repetitions": 1}, headers=h)


def test_sign_in_once_sets_a_secure_server_side_session_and_returns_no_secret(env):
    c, _, _ = client(env)
    assert c.post("/api/operator/session", headers={"authorization": "Bearer " + OPERATOR.decode()}).status_code == 403   # no CSRF header
    assert c.post("/api/operator/session", headers={**CSRF, "authorization": "Bearer " + "x" * 32}).status_code == 403    # wrong token
    assert c.post("/api/operator/session", headers={**CSRF, "authorization": "Bearer " + JUDGE.decode()}).status_code == 403  # the judge code
    assert c.get("/api/operator/session").json()["signed_in"] is False
    r = sign_in(c)
    assert r.status_code == 200 and r.json()["signed_in"] is True and OPERATOR.decode() not in r.text
    cookie = r.headers["set-cookie"]
    for attr in ("__Host-ar_operator=", "HttpOnly", "Secure", "SameSite=strict", "Path=/"):
        assert attr.lower() in cookie.lower(), attr
    assert "no-store" in r.headers["cache-control"]
    assert c.get("/api/operator/session").json()["signed_in"] is True and c.get("/api/ironbark/config").json()["operator"]["signed_in"] is True
    raw = c.cookies.get("__Host-ar_operator")
    db = (env["root"] / "operator-sessions.sqlite").read_bytes()
    assert raw.encode() not in db and OPERATOR not in db                               # only a hash of the session id is stored; the token never


def test_failed_sign_ins_are_rate_limited(env):
    c, _, _ = client(env)
    for _ in range(10):
        assert c.post("/api/operator/session", headers={**CSRF, "authorization": "Bearer " + "x" * 32}).status_code == 403
    assert sign_in(c).status_code == 429


def test_one_click_launches_charge_the_budget_and_need_no_token_in_the_page(env):
    c, _, a = client(env)
    sign_in(c)
    r = run(c, key="k" * 20)
    assert r.status_code == 409 and "No operator evaluation budget is open" in r.json()["detail"]
    assert AR.claims("judge-test-1") == [] and a.recent() == []                        # never the judge pool, nothing reserved
    budget = M.open_pool(env, a)
    cfg = c.get("/api/ironbark/config").json()
    assert cfg["budget_launch"]["authorized"] is True and cfg["budget_evaluation"]["budget"] == budget and cfg["budget_tasks"]
    r = run(c, key="a" * 20)
    assert r.status_code == 202, r.text
    job = r.json()["id"]
    assert a.job_budget(job) == budget and [x["job"] for x in AR.claims(budget)] == [job]
    M.settle(a, job)
    st = c.get(f"/api/ironbark/jobs/{job}").json()["accounting"]
    assert st["budget"] == budget and st["reserved_usd"] > 0                          # the run's own cost line (reservation until settled)
    assert c.get("/api/ironbark/config").json()["evaluation"]["launches"]["left"] == 4   # the judge pool is untouched


def test_a_cookie_never_authorises_a_cross_site_launch(env):
    c, _, a = client(env)
    sign_in(c)
    M.open_pool(env, a)
    assert c.post("/api/ironbark/jobs", json={"repetitions": 1}).status_code == 403                       # no CSRF header
    assert run(c, headers={"origin": "https://evil.example"}).status_code == 403                          # wrong origin
    assert a.recent() == []
    assert run(c, headers={"origin": "https://testserver"}).status_code == 202


def test_double_clicks_and_retries_start_one_run(env):
    c, ex, a = client(env)
    sign_in(c)
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
    assert [r.status_code for r in out] == [202] * 4 and len(ids) == 1 and len(a.recent()) == 1   # one job, one reservation
    assert run(c, key="same-click-0123456789").json()["duplicate"] is True             # a later retry returns the same run
    assert run(c, key="other-click-0123456789").status_code == 429                      # a new click while it runs: the single slot
    ex.gate.set()
    M.settle(a, ids.pop())
    assert run(c, key="x").status_code == 422                                           # malformed keys are refused


def test_sign_out_revokes_the_session_even_if_the_cookie_is_replayed(env):
    c, _, a = client(env)
    sign_in(c)
    M.open_pool(env, a)
    raw = c.cookies.get("__Host-ar_operator")
    assert c.request("DELETE", "/api/operator/session", headers=CSRF).json()["signed_in"] is False
    c.cookies.set("__Host-ar_operator", raw)
    assert c.get("/api/operator/session").json()["signed_in"] is False and run(c).status_code == 403 and a.recent() == []


def test_the_operator_token_and_session_never_appear_in_responses_or_files(env, capsys):
    c, _, a = client(env)
    r = sign_in(c)
    raw = c.cookies.get("__Host-ar_operator")
    M.open_pool(env, a)
    job = run(c, key="b" * 20).json()["id"]
    M.settle(a, job)
    for path in ("/api/health", "/api/ironbark/config", "/api/ironbark/jobs", f"/api/ironbark/jobs/{job}", "/api/operator/session"):
        text = c.get(path).text
        assert OPERATOR.decode() not in text and raw not in text, path
    assert raw not in r.text
    for f in list(env["root"].rglob("*")) + list(AU.STAGE_B.rglob("*")) + [env["tmp"] / "a.sqlite"]:
        if f.is_file():
            data = f.read_bytes()
            assert OPERATOR not in data and raw.encode() not in data, f
    out = capsys.readouterr()
    assert OPERATOR.decode() not in out.out + out.err and raw not in out.out + out.err


def test_the_judge_path_is_unchanged_and_cannot_use_the_budget(env):
    c, _, a = client(env)
    M.open_pool(env, a)
    r = c.post("/api/ironbark/jobs", json={"repetitions": 1}, headers={"authorization": "Bearer " + JUDGE.decode()})
    assert r.status_code == 202
    job = r.json()["id"]
    assert a.job_budget(job) is None and AR.claims("judge-test-1")[0]["job"] == job    # the arming, a programme job


def test_a_session_expires_after_seven_days_and_expired_rows_are_purged(env, monkeypatch):
    import time as T
    c, _, a = client(env)
    r = sign_in(c)
    assert "max-age=604800" in r.headers["set-cookie"].lower()
    M.open_pool(env, a)
    real = T.time
    monkeypatch.setattr(T, "time", lambda: real() + 7 * 24 * 3600 + 1)               # the server's clock, a week later
    assert c.get("/api/operator/session").json()["signed_in"] is False
    assert run(c, key="late-click-0123456789").status_code == 403 and a.recent() == []
    monkeypatch.setattr(T, "time", real)
    import sqlite3
    db = sqlite3.connect(env["root"] / "operator-sessions.sqlite")
    db.execute("UPDATE sessions SET expires = 0")
    db.commit()
    sign_in(c)                                                                        # a new sign-in purges expired sessions
    assert db.execute("SELECT COUNT(*) FROM sessions").fetchone()[0] == 1


def test_concurrent_operator_launches_never_exceed_the_budget(env):
    """Distinct clicks racing (different idempotency keys): the single slot admits one at a time, and across a run of launches the A$20 budget is
    never exceeded; the launch that would exceed it is refused with the budget message and reserves nothing."""
    c, ex, a = client(env, interval=1)
    budget = M.open_pool(env, a)
    sign_in(c)
    import time as T
    res = []
    for wave in range(8):
        out, bar = [], threading.Barrier(5)

        def click(n):
            bar.wait()
            out.append(run(c, key=f"wave{wave}-click{n}-0123456789"))

        ts = [threading.Thread(target=click, args=(n,)) for n in range(5)]
        [t.start() for t in ts]
        [t.join() for t in ts]
        ok = [r for r in out if r.status_code == 202]
        assert len(ok) <= 1                                                           # never two runs at once
        b = next(x for x in a.totals()["budgets"] if x["budget"] == budget)
        assert b["committed_micro_aud"] <= b["limit_micro_aud"]
        for r in ok:
            M.settle(a, r.json()["id"])                                               # the stand-in run ends without results: kept in full (failed)
            res.append(r.json()["id"])
        if not ok and any(r.status_code == 429 and "remaining budget" in r.json()["detail"] for r in out):
            break
        T.sleep(1.05)                                                                 # the operator's per-client rate limit
    b = next(x for x in a.totals()["budgets"] if x["budget"] == budget)
    reserve_aud = b["outstanding_micro_aud"] // max(1, len(res))
    assert len(res) == 20_000_000 // reserve_aud and b["committed_micro_aud"] <= 20_000_000 < b["committed_micro_aud"] + reserve_aud
    assert all(a.job_budget(j) == budget for j in res) and AR.claims("judge-test-1") == []
