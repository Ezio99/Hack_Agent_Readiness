"""M9: the launch-only judge access code (zero cost; no model, no browser).

The judge code is a SEPARATE secret. It authorises exactly one thing, `POST /api/ironbark/jobs` (launching the evaluation the owner armed), through the
unchanged launch path: the arming (launch count, total), the hosted admission (single slot, ceiling, per-client rate limit) and durable launch
claims. It is refused everywhere else, never returned or recorded, and the operator token keeps working. The worker subprocess is replaced (no
browser, no model); everything else is the real Stage B executor and admission."""
import importlib.util
import json
import threading
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from agent_readiness.evalruns import authorization as AU
from agent_readiness.hosted import serve, stageb
from agent_readiness.hosted.admission import Admission
from agent_readiness.hosted.api import create_app, recover
from agent_readiness.lifecycle import arming as AR
from agent_readiness.lifecycle import jobs as J
from agent_readiness.lifecycle.service import LifecycleService

OPERATOR = b"o" * 32
JUDGE = b"judge-access-code-0123456789abcdef"
OP = {"authorization": "Bearer " + OPERATOR.decode()}
JG = {"authorization": "Bearer " + JUDGE.decode()}
AT = "2026-11-03T12:00:00+00:00"
REF = "larkspur-judge-test@v1"


def _T():
    spec = importlib.util.spec_from_file_location("stageb_suite", Path(__file__).parent / "test_hosted_stageb.py")
    T = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(T)
    return T


@pytest.fixture
def env(tmp_path, monkeypatch):
    T = _T()
    monkeypatch.setattr(AU, "STAGE_B", tmp_path / "stage-b")
    store, f, msha, m = T._guard().build(tmp_path, real_name="larkspur-judge-test")
    store.ref("frozen_suite", REF, f)
    kw = dict(arming_id="judge-test-1", mode="paid", frozen_ref=REF, variants=["original", "modified"], repetitions=[1], launches=4)
    p = AR.plan(store, **kw)
    AR.arm(store, typed=p["attestation"], at=AT, interactive=True, **kw)
    return {"tmp": tmp_path, "store": store, "root": tmp_path / "hosted", "plan": p}


class Exec(stageb.StageBExecutor):
    """The real Stage B executor; its worker subprocess is replaced by a controllable stand-in (no browser, no model)."""
    gate: threading.Event | None = None
    fail = False

    def run(self, job_id):
        if self.gate is not None:
            self.gate.wait(10)
        J.update_job(self.runs_root, job_id, state="failed" if self.fail else "completed", finished_at=time.time())
        if self.fail:
            raise RuntimeError("worker failed")


def app(env, *, judge=JUDGE, operator=OPERATOR, public=False, interval=1, db="a.sqlite"):
    a = Admission(env["tmp"] / db, ceiling_microusd=33_000_000, job_cap_microusd=1_650_000, min_interval_seconds=interval)
    ex = Exec(env["root"], env["store"].root, a, mode="live")
    svc = LifecycleService(store_root=env["store"].root, runs_root=env["root"] / "stageb", executor=ex, admission=a, log=lambda *_: None)
    c = TestClient(create_app(env["root"], a, client_key=b"k" * 32, executor=ex, operator_token=operator, public_start=public, mode="live",
                              lifecycle=svc, judge_token=judge))
    return c, ex, a


def settle(a, job):
    for _ in range(300):
        if a.get(job)["state"] not in ("reserved", "running"):
            return a.get(job)["state"]
        time.sleep(0.01)
    return a.get(job)["state"]


def launch(c, headers=JG):
    return c.post("/api/ironbark/jobs", json={"repetitions": 1}, headers=headers)


# ------------------------------------------------------------------------------------------------------------------------------- authorisation
def test_the_judge_code_launches_the_armed_evaluation_through_the_normal_path(env):
    c, ex, a = app(env)
    cfg = c.get("/api/ironbark/config").json()
    assert cfg["judge_access"] is True and cfg["launch"]["authorized"] and cfg["available"]
    r = launch(c)
    assert r.status_code == 202, r.text
    job = r.json()["id"]
    assert settle(a, job) in ("completed", "failed")              # the stand-in worker yields no results; the launch path is what is tested here
    claim = AR.claims("judge-test-1")[0]
    assert claim["job"] == job and claim["launch"] == 1 and claim["reservation_microusd"] == env["plan"]["options"][0]["reservation_microusd"]
    assert a.get(job)["reserved_microusd"] == claim["reservation_microusd"]                                  # reserved in the shared admission
    assert (AU.STAGE_B / "authorizations" / "judge-test-1-l1.json").is_file()                               # its own write-once authorisation


@pytest.mark.parametrize("headers", [{}, {"authorization": "Bearer wrong-code-but-long-enough-xxxxxx"}, {"authorization": JUDGE.decode()},
                                     {"authorization": "Basic " + JUDGE.decode()}, {"x-judge-code": JUDGE.decode()}])
def test_launch_is_refused_without_a_valid_code(env, headers):
    c, _, a = app(env)
    assert launch(c, headers).status_code == 403 and a.recent() == [] and AR.claims("judge-test-1") == []


def test_the_judge_code_authorises_nothing_else(env):
    c, _, a = app(env)
    routes = {(m, r.path) for r in c.app.routes for m in getattr(r, "methods", set()) if m not in ("GET", "HEAD")}
    assert routes == {("POST", "/api/ironbark/jobs"), ("POST", "/api/lifecycle/suites/{sha}/decision")}       # no other write route exists
    for h in (JG, OP, {}):                                                                                      # web suite decisions: refused for everyone
        r = c.post("/api/lifecycle/suites/" + "0" * 64 + "/decision", json={"decision": "approved", "attestation": "x"}, headers=h)
        assert r.status_code == 403
    assert not any(any(w in path for w in ("arming", "arm", "ceiling", "migrat", "disarm", "admin", "secret", "file")) for _, path in routes)
    for path in ("/api/health", "/api/ironbark/config", "/api/ironbark/jobs", "/api/lifecycle/overview", "/api/lifecycle/evaluations"):
        with_code, without = c.get(path, headers=JG), c.get(path)
        assert with_code.status_code == without.status_code and with_code.json() == without.json()             # reads are public; the code changes nothing


def test_the_code_is_never_returned_or_recorded(env):
    c, _, a = app(env)
    job = launch(c).json()["id"]
    settle(a, job)
    secret = JUDGE.decode()
    for path in ("/api/health", "/api/ironbark/config", "/api/ironbark/jobs", f"/api/ironbark/jobs/{job}", f"/api/ironbark/jobs/{job}/live"):
        assert secret not in c.get(path, headers=JG).text
    for f in list(env["root"].rglob("*")) + list(AU.STAGE_B.rglob("*")) + [env["tmp"] / "a.sqlite"]:
        if f.is_file():
            assert JUDGE not in f.read_bytes(), f                                                                # job files, claims, authorisations, admission


def test_operator_token_still_works_and_identities_differ(env):
    c, _, a = app(env)
    j1 = launch(c, OP).json()["id"]
    settle(a, j1)
    time.sleep(1.05)
    j2 = launch(c, JG).json()["id"]
    settle(a, j2)
    import sqlite3
    db = sqlite3.connect(env["tmp"] / "a.sqlite")
    clients = dict(db.execute("SELECT id, client FROM jobs").fetchall())
    assert clients[j1] != clients[j2]                                    # the operator is one client; a judge is identified by address (rate limit per judge)


@pytest.mark.parametrize("judge", [b"short", OPERATOR, None])
def test_a_short_or_reused_or_absent_code_leaves_judge_access_off(env, judge):
    c, _, _ = app(env, judge=judge)
    assert c.get("/api/ironbark/config").json()["judge_access"] is False
    assert launch(c, {"authorization": "Bearer short"}).status_code == 403
    assert launch(c, OP).status_code == 202                                                                     # operator unaffected


def test_public_access_does_not_advertise_a_judge_code(env):
    c, _, _ = app(env, public=True)
    assert c.get("/api/ironbark/config").json()["judge_access"] is False


# ------------------------------------------------------------------------------------------------------------------------------- the pool
def test_four_launches_then_the_pool_is_exhausted_and_nothing_more_is_reserved(env):
    c, _, a = app(env)
    jobs = []
    for i in range(4):
        r = launch(c)
        assert r.status_code == 202, (i, r.text)
        jobs.append(r.json()["id"])
        settle(a, jobs[-1])
        time.sleep(1.05)                                                                                        # the per-client rate limit (1 s here)
    assert [x["launch"] for x in sorted(AR.claims("judge-test-1"), key=lambda x: x["launch"])] == [1, 2, 3, 4]
    reserved = a.totals()["reserved_microusd"]
    r = launch(c)
    assert r.status_code == 409 and "All armed launches have been used" in r.json()["detail"]
    assert a.totals()["reserved_microusd"] == reserved and len(a.recent()) == 4                                  # nothing reserved by the refusal
    cfg = c.get("/api/ironbark/config").json()
    assert cfg["launch"]["reason"] == "launches_exhausted" and cfg["available"] is False and cfg["repetitions"] == []


def test_concurrent_launches_admit_exactly_one(env):
    c, ex, a = app(env)
    ex.gate = threading.Event()
    codes = []
    threads = [threading.Thread(target=lambda: codes.append(launch(c).status_code)) for _ in range(6)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    try:
        assert sorted(codes).count(202) == 1 and all(x in (202, 409, 429) for x in codes), codes
        assert len(AR.claims("judge-test-1")) == 1 and len(a.recent()) == 1
        busy = c.get("/api/ironbark/config").json()
        assert busy["worker"]["state"] == "busy" and busy["launch"]["ready"] is False
    finally:
        ex.gate.set()


def test_a_restart_interrupts_the_running_launch_which_is_never_re_run(env):
    c, ex, a = app(env)
    ex.gate = threading.Event()
    job = launch(c).json()["id"]
    try:
        assert recover(env["root"], a) == [job]                                                                 # what the service does at start
        assert a.get(job)["state"] == "interrupted" and J.load_job(env["root"] / "stageb", job)["state"] == "interrupted"
    finally:
        ex.gate.set()
    c2, _, a2 = app(env)                                                                                         # the restarted service, same data
    cfg = c2.get("/api/ironbark/config").json()
    assert cfg["evaluation"]["launches"] == {"max": 4, "used": 1, "left": 3}
    time.sleep(1.05)
    j2 = launch(c2).json()["id"]
    assert [x["launch"] for x in AR.claims("judge-test-1") if x["job"] == j2] == [2]                           # the next number; launch 1 is never reused


def test_a_failed_run_consumes_its_launch_and_keeps_its_reservation(env):
    c, ex, a = app(env)
    ex.fail = True
    job = launch(c).json()["id"]
    assert settle(a, job) == "failed"
    assert a.get(job)["reserved_microusd"] > 0
    assert c.get("/api/ironbark/config").json()["evaluation"]["launches"]["left"] == 3


# ------------------------------------------------------------------------------------------------------------------------------- service start
def test_the_service_loads_the_judge_code_from_its_file_and_never_logs_it(tmp_path, monkeypatch, capsys):
    spec = importlib.util.spec_from_file_location("svc", Path(__file__).parent / "test_hosted_service.py")
    S = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(S)
    gen = S.env.__wrapped__(tmp_path, monkeypatch)
    e = next(gen)
    code = tmp_path / "judge"
    for content, expected in (("j" * 40, "on"), ("short", "off"), ("t" * 32, "off")):                         # "t"*32 is the operator token here
        code.write_text(content)
        monkeypatch.setenv("AR_JUDGE_TOKEN_FILE", str(code))
        app_, out = S.built(capsys)
        assert f"judge_access={expected}" in out and content not in out.replace("judge_access=", "")
        assert TestClient(app_).get("/api/ironbark/config").json()["judge_access"] is (expected == "on")    # advertised as a boolean only


# ------------------------------------------------------------------------------------------------------------------------------- the v3 suite (owner tooling)
STORE = Path(__file__).resolve().parents[1] / "scanner-data" / "research" / "stage-a" / "store"
V2_SUITE = "172d1e712eb18871fd4f24b227a2448ec44a546347bb9874f0946c5609f7848b"
V3_SUITE = "f45694788ea9e1f7b28c95193e25870bfe3aed2975d7f00276cdc87d7c6b09e3"
V3_ARGS = ["--keep", "gen-23f1802ee0-n", "gen-f302fa8fe2-n", "--context-site", "larkspur", "--at", "2026-11-03T12:00:00+00:00", "--by", "owner",
           "--notes", "judge live evaluation: tasks gen-23f1802ee0-n and gen-f302fa8fe2-n of v2 (their deciding facts are on the Modified listing cards)"]


@pytest.mark.skipif(not (STORE / "objects").is_dir(), reason="needs the local lifecycle store")
def test_revise_keeps_exactly_the_two_tasks_with_a_reproducible_hash_and_leaves_v2_unchanged(tmp_path, capsys):
    import shutil
    from agent_readiness.suites.stage_a import approval as AP
    from agent_readiness.suites.store import WriteOnceStore
    store = tmp_path / "store"
    shutil.copytree(STORE, store)
    before = sorted((p.name, p.read_bytes()) for p in store.rglob("*") if p.is_file())
    assert AP.main(["revise", str(store), V2_SUITE, *V3_ARGS]) == 0
    assert capsys.readouterr().out.strip() == V3_SUITE                                                          # the hash the owner checks before approving
    st = WriteOnceStore(store)
    v3 = st.get("suite", V3_SUITE)
    assert (v3.suite_name, v3.version) == ("larkspur-core", 3) and sorted(st.get("task", t).task_id for t in v3.task_sha256s) == ["gen-23f1802ee0-n", "gen-f302fa8fe2-n"]
    assert set(v3.task_sha256s) <= set(st.get("suite", V2_SUITE).task_sha256s)                                 # the same immutable task records
    after = {p.name: p.read_bytes() for p in store.rglob("*") if p.is_file()}
    assert all(after[n] == b for n, b in before)                                                                 # nothing existing changed (v2, its approval, freeze)
    assert st.resolve("frozen_suite", "larkspur-core@v2") == "0816af7f7440bb08fae6235c9cb77642d434dce1a8db585d08f5be5983b9b1d7"
    with pytest.raises(Exception):
        st.resolve("frozen_suite", "larkspur-core@v3")                                                          # a proposal only: not approved, not frozen
    with pytest.raises(ValueError, match="not tasks of suite"):
        AP.revise_keep(st, V2_SUITE, keep=["gen-nope"], context={}, at="x", by="owner", notes="n")
