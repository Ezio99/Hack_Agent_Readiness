"""M8 follow-up: the hosted evaluation runs the lifecycle Stage B engine (zero cost; nothing here can reach a model: the worker subprocess is replaced,
and the worker's paid branch is exercised with the Stage B runner stubbed before any request is built).

The launch contract is unchanged ({"repetitions"} only, operator token). What runs is the owner's ACTIVE ARMING, recorded only at a terminal: an
owner-approved frozen suite, registered variants, one exact manifest per repetition count, the model, the number of launches and their total.
Each launch reserves its worst case (plus one request bound) in the hosted admission, claims its launch number once, and (paid) gets its own
write-once PaidAuthorization and ledger."""
import importlib.util
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from agent_readiness.evalruns import authorization as AU
from agent_readiness.hosted import stageb
from agent_readiness.hosted.admission import Admission
from agent_readiness.hosted.api import create_app, recover
from agent_readiness.lifecycle import arming as AR
from agent_readiness.lifecycle import jobs as J
from agent_readiness.lifecycle.service import LifecycleService

TOKEN = b"t" * 32
OP = {"authorization": "Bearer " + TOKEN.decode()}
AT = "2026-11-04T02:00:00+00:00"
REF = "larkspur-hosted-test@v1"


def _guard():
    spec = importlib.util.spec_from_file_location("m7_paid_guard_fixture", Path(__file__).parent / "test_m7_paid_guard.py")
    T = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(T)
    return T


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(AU, "STAGE_B", tmp_path / "stage-b")
    store, f, msha, m = _guard().build(tmp_path, real_name="larkspur-hosted-test")
    store.ref("frozen_suite", REF, f)
    return {"tmp": tmp_path, "store": store, "frozen": f, "manifest": msha, "m": m, "root": tmp_path / "hosted"}


def _arm(env, *, mode="paid", launches=1, reps=(1,), arming="hosted-test-1", store=None, ref=REF):
    kw = dict(arming_id=arming, mode=mode, frozen_ref=ref, variants=["original", "modified"], repetitions=list(reps), launches=launches)
    st = store or env["store"]
    p = AR.plan(st, **kw)
    AR.arm(st, typed=p["attestation"], at=AT, interactive=True, **kw)
    return p


class NoRun(stageb.StageBExecutor):
    """The real Stage B executor with its worker subprocess replaced (no browser, no model)."""
    def run(self, job_id):
        self.ran = getattr(self, "ran", []) + [job_id]


def _app(env, *, mode="live", ceiling=10_000_000):
    a = Admission(env["tmp"] / f"a-{mode}.sqlite", ceiling_microusd=ceiling, job_cap_microusd=1_650_000, min_interval_seconds=60)
    ex = NoRun(env["root"], env["store"].root, a, mode=mode)
    svc = LifecycleService(store_root=env["store"].root, runs_root=env["root"] / "stageb", executor=ex, admission=a, log=lambda *_: None)
    c = TestClient(create_app(env["root"], a, client_key=b"k" * 32, executor=ex, operator_token=TOKEN, public_start=False, mode=mode, lifecycle=svc))
    return c, ex, a


def _wait(a, job, states=("completed", "failed", "timed_out", "interrupted")):
    import time
    for _ in range(200):
        if a.get(job)["state"] in states:
            return a.get(job)["state"]
        time.sleep(0.02)
    return a.get(job)["state"]


# ------------------------------------------------------------------------------------------------------------------------------- owner arming
def test_the_plan_binds_the_existing_manifest_and_a_worst_case_reservation(env):
    p = AR.plan(env["store"], arming_id="hosted-test-1", mode="paid", frozen_ref=REF, variants=["original", "modified"], repetitions=[1], launches=2)
    o = p["options"][0]
    assert o["manifest_sha256"] == env["manifest"] and o["trials"] == 6
    assert o["reservation_microusd"] == round((env["m"].budget["worst_case_reservation_usd"] + env["m"].budget["per_request_cap_usd"]) * 1_000_000)
    assert p["total_reservation_microusd"] == 2 * o["reservation_microusd"]
    for part in ("hosted-test-1", env["frozen"], env["manifest"], "muse-spark-1.3", "https://api.meta.ai/v1", "at most 2 launch(es)"):
        assert part in p["attestation"]


def test_arming_needs_the_terminal_the_exact_attestation_and_is_write_once(env):
    kw = dict(arming_id="hosted-test-1", mode="paid", frozen_ref=REF, variants=["original", "modified"], repetitions=[1], launches=1)
    p = AR.plan(env["store"], **kw)
    with pytest.raises(AR.ArmingRefused, match="interactive"):
        AR.arm(env["store"], typed=p["attestation"], at=AT, interactive=False, **kw)
    with pytest.raises(AR.ArmingRefused, match="does not match"):
        AR.arm(env["store"], typed=p["attestation"].replace("at most 1", "at most 9"), at=AT, interactive=True, **kw)
    assert AR.active() is None
    AR.arm(env["store"], typed=p["attestation"], at=AT, interactive=True, **kw)
    assert AR.active().arming_id == "hosted-test-1" and AR.verify(env["store"], AR.active()) == []
    with pytest.raises(AR.ArmingRefused, match="write-once"):
        AR.arm(env["store"], typed=p["attestation"], at=AT, interactive=True, **kw)


def test_the_cli_refuses_to_arm_without_a_tty(env, monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    code = AR.main(["arm", "--arming", "hosted-test-1", "--mode", "paid", "--frozen", REF, "--variants", "original", "modified", "--store", str(env["store"].root)])
    assert code == 2 and "interactive terminal" in capsys.readouterr().err and AR.active() is None


def test_synthetic_suites_cannot_be_armed_for_paid_and_a_forged_arming_never_verifies(env, tmp_path):
    store, f, _, _ = _guard().build(tmp_path / "s", real_name="synthetic-larkspur-hosted")
    store.ref("frozen_suite", "synthetic-larkspur-hosted@v1", f)
    with pytest.raises(AR.ArmingRefused, match="synthetic"):
        AR.plan(store, arming_id="x-1", mode="paid", frozen_ref="synthetic-larkspur-hosted@v1", variants=["original", "modified"], repetitions=[1], launches=1)
    p = AR.plan(env["store"], arming_id="forged-1", mode="paid", frozen_ref=REF, variants=["original", "modified"], repetitions=[1], launches=1)
    forged = AR.Arming(**{"schema": AR.SCHEMA, **{k: p[k] for k in ("arming_id", "mode", "site", "frozen_suite", "frozen_suite_sha256", "max_launches")},
                          "total_reservation_microusd": p["total_reservation_microusd"] * 10, "variants": tuple(tuple(v) for v in p["variants"]),
                          "options": tuple(AR.Option(**o) for o in p["options"]), "agent": p["agent"], "attestation": p["attestation"], "recorded_at": AT, "recorded_by": AR.RECORDED_BY})
    assert any("attestation" in x for x in AR.verify(env["store"], forged))


# ------------------------------------------------------------------------------------------------------------------------------- operator launch
def test_without_an_arming_nothing_can_launch(env):
    c, _, a = _app(env)
    cfg = c.get("/api/ironbark/config").json()
    assert cfg["engine"] == "stage-b" and cfg["available"] is False and cfg["reason"] == "not_armed"
    assert c.post("/api/ironbark/jobs", json={"repetitions": 1}, headers=OP).status_code == 409 and a.recent() == []


def test_a_paid_launch_reserves_the_worst_case_claims_once_and_writes_its_own_authorisation(env):
    p = _arm(env)
    c, ex, a = _app(env)
    cfg = c.get("/api/ironbark/config").json()
    assert cfg["available"] and cfg["repetitions"] == [1] and len(cfg["tasks"]) == 3 and "attestation" not in json.dumps(cfg)
    assert c.post("/api/ironbark/jobs", json={"repetitions": 1}).status_code == 403                                            # operator only
    for body in ({"repetitions": 1, "url": "https://x"}, {"repetitions": 1, "model": "m"}, {"repetitions": 1, "tasks": []}, {"repetitions": 1, "cap_usd": 1}):
        assert c.post("/api/ironbark/jobs", json=body, headers=OP).status_code == 422
    assert c.post("/api/ironbark/jobs", json={"repetitions": 3}, headers=OP).status_code == 409                                 # not armed for 3
    r = c.post("/api/ironbark/jobs", json={"repetitions": 1}, headers=OP)
    assert r.status_code == 202, r.text
    job = r.json()["id"]
    assert a.get(job)["reserved_microusd"] == p["options"][0]["reservation_microusd"]
    claim = json.loads((AU.STAGE_B / "launches" / "hosted-test-1-l1.json").read_text())
    assert claim["job"] == job and claim["manifest_sha256"] == env["manifest"]
    auth = AU.load(AU.STAGE_B / "authorizations" / "hosted-test-1-l1.json")
    assert auth.instruction == p["attestation"] and AU.verify(auth, env["store"], env["manifest"], planned_trials=6) == []
    rec = J.load_job(env["root"] / "stageb", job)
    assert rec["mode"] == "paid" and rec["launch"]["experiment_id"] == "hosted-test-1-l1"
    _wait(a, job)
    again = c.post("/api/ironbark/jobs", json={"repetitions": 1}, headers=OP)
    assert again.status_code == 409 and "launches have been used" in again.json()["detail"]
    assert a.totals()["reserved_microusd"] == p["options"][0]["reservation_microusd"]                                            # never doubled, never released


def test_a_launch_that_does_not_fit_the_hosted_ceiling_reserves_and_claims_nothing(env):
    p = _arm(env)
    c, _, a = _app(env, ceiling=p["options"][0]["reservation_microusd"] - 1)
    r = c.post("/api/ironbark/jobs", json={"repetitions": 1}, headers=OP)
    assert r.status_code == 429 and a.recent() == [] and AR.claims("hosted-test-1") == []


def test_the_arming_mode_must_match_the_service_mode(env):
    _arm(env)                                                                    # paid arming
    c, _, a = _app(env, mode="rehearsal")
    assert c.get("/api/ironbark/config").json()["reason"] == "arming_mode_mismatch"
    assert c.post("/api/ironbark/jobs", json={"repetitions": 1}, headers=OP).status_code == 409 and a.recent() == []


def test_a_rehearsal_reserves_nothing_and_writes_no_paid_authorisation(env, tmp_path):
    _arm(env, mode="rehearsal", arming="rehearsal-test-1")
    c, _, a = _app(env, mode="rehearsal")
    r = c.post("/api/ironbark/jobs", json={"repetitions": 1}, headers=OP)
    assert r.status_code == 202 and a.get(r.json()["id"])["reserved_microusd"] == 0
    assert not (AU.STAGE_B / "authorizations").exists() and J.load_job(env["root"] / "stageb", r.json()["id"])["mode"] == "rehearsal"


def test_restart_recovery_interrupts_the_job_and_never_reuses_its_launch(env):
    p = _arm(env, launches=2)
    c, ex, a = _app(env)
    import threading
    gate = threading.Event()
    ex.run = lambda job_id: gate.wait(5)
    job = c.post("/api/ironbark/jobs", json={"repetitions": 1}, headers=OP).json()["id"]
    try:
        assert recover(env["root"], a) == [job]
        assert a.get(job)["state"] == "interrupted" and J.load_job(env["root"] / "stageb", job)["state"] == "interrupted"
        st = c.get(f"/api/ironbark/jobs/{job}").json()
        assert st["engine"] == "stage-b" and st["state"] == "interrupted"
    finally:
        gate.set()
    c2, _, _ = _app(env)
    second = c2.post("/api/ironbark/jobs", json={"repetitions": 1}, headers={**OP, "x-client": "2"})
    assert second.status_code in (202, 429)                                      # the same operator client may be rate-limited; never launch 1 again
    assert [x["launch"] for x in AR.claims("hosted-test-1")][0] == 1 and len({x["job"] for x in AR.claims("hosted-test-1")}) == len(AR.claims("hosted-test-1"))


# ------------------------------------------------------------------------------------------------------------------------------- worker
def _launched(env, mode="paid"):
    _arm(env, mode=mode, arming="w-1")
    c, ex, a = _app(env, mode="live" if mode == "paid" else "rehearsal")
    ex.run = lambda job_id: None
    job_id = J.new_id()
    ex.admit(job_id, "c" * 64, 1)
    a.transition(job_id, "reserved", "running")
    return ex, a, job_id


def test_the_worker_rechecks_and_hands_the_launch_authorisation_to_the_runner(env, monkeypatch):
    ex, a, job = _launched(env)
    from agent_readiness.evalruns import runner as RN
    from agent_readiness.hosted import paired
    seen = {}

    class Run:
        dir = ex.runs_root / "evalruns" / "x"
        state = {"id": "x"}
    monkeypatch.setattr(paired, "_loopback_only_sockets", lambda: seen.setdefault("loopback_guard", True))
    monkeypatch.setattr(paired, "_load_key_file", lambda: seen.setdefault("key_loaded", True))
    monkeypatch.setattr(RN, "prepare", lambda store, msha, root, mode, label: seen.update(mode=mode, manifest=msha) or {"natural": Run()})
    monkeypatch.setattr(RN, "steps", lambda run, m: [1] * 6)

    def execute(run, store, authorization=None):
        seen["authorization"] = authorization
        raise RuntimeError("stop before any request (test)")
    monkeypatch.setattr(RN, "execute", execute)
    from agent_readiness.evalruns import manifest as MF
    declared = MF.JAIL_POLICY
    with pytest.raises(RuntimeError, match="stop before"):
        J.run_job(ex.runs_root, env["store"].root, job, a)
    assert MF.JAIL_POLICY is declared                                  # the runtime-only jail extension never leaks into the pinned agent config
    assert seen["mode"] == "paid" and seen["manifest"] == env["manifest"]
    assert seen["authorization"] == AU.STAGE_B / "authorizations" / "w-1-l1.json" and seen.get("key_loaded") and "loopback_guard" not in seen


def test_the_worker_refuses_a_foreign_claim_or_a_wrong_reservation(env, monkeypatch):
    ex, a, job = _launched(env)
    from agent_readiness.evalruns import runner as RN
    monkeypatch.setattr(RN, "prepare", lambda *a_, **k: pytest.fail("must not prepare"))
    rec = J.load_job(ex.runs_root, job)
    J.update_job(ex.runs_root, job, launch={**rec["launch"], "experiment_id": "w-1-l9"})
    with pytest.raises(AR.ArmingRefused, match="claim"):
        J.run_job(ex.runs_root, env["store"].root, job, a)
    J.update_job(ex.runs_root, job, launch=rec["launch"])
    monkeypatch.setattr(AR, "check_launch", lambda store, job: {**rec["launch"], "reservation_microusd": 1})
    with pytest.raises(PermissionError, match="reservation"):
        J.run_job(ex.runs_root, env["store"].root, job, a)


def test_hosted_status_of_a_stage_b_job_before_its_runs_exist(env):
    _arm(env)
    c, ex, a = _app(env)
    import threading
    gate = threading.Event()
    ex.run = lambda job_id: gate.wait(5)
    job = c.post("/api/ironbark/jobs", json={"repetitions": 1}, headers=OP).json()["id"]
    try:
        st = c.get(f"/api/ironbark/jobs/{job}").json()
        assert st["engine"] == "stage-b" and st["mode"] == "live" and st["repetitions"] == 1 and st["reps"][0]["state"] == "preparing"
        assert c.get(f"/api/ironbark/jobs/{job}/repetitions/1/trials/original/1").status_code == 404     # no runs yet
        assert c.get(f"/api/ironbark/jobs/{job}/insights").status_code == 409
        assert c.get("/api/ironbark/config").json()["worker"]["state"] == "busy"
    finally:
        gate.set()


def test_m9_config_reports_the_used_launch_as_not_authorised_and_the_launch_path_agrees(env):
    """M9 final sprint: after the single armed launch, the worker is still healthy (idle) but no launch is authorised; the config says so from
    the arming summary, and the real launch path (StageBExecutor.admit) refuses, reserving nothing."""
    _arm(env, launches=1)
    c, ex, a = _app(env, ceiling=10_736_000)
    before = c.get("/api/ironbark/config").json()
    assert before["launch"]["authorized"] and before["launch"]["ready"] and before["available"] and before["worker"]["state"] == "idle"
    job = c.post("/api/ironbark/jobs", json={"repetitions": 1}, headers=OP).json()["id"]
    _wait(a, job)
    after = c.get("/api/ironbark/config").json()
    assert after["worker"]["state"] == "idle" and after["service"]["state"] == "operational"
    assert after["launch"]["authorized"] is False and after["launch"]["reason"] == "launches_exhausted" and after["available"] is False and after["repetitions"] == []
    n = len(a.recent())
    assert c.post("/api/ironbark/jobs", json={"repetitions": 1}, headers={**OP, "x-client": "2"}).status_code in (409, 429) and len(a.recent()) == n
