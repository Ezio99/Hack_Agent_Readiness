"""M9 final sprint: the hosted config separates service health (`worker`, `service`) from launch authorisation (`launch`, `available`).

`launch` is derived from the same server-side facts the launch path enforces (the arming summary: launches left, the arming's remaining total, the
hosted ceiling); it is display only, and every launch is still checked by `StageBExecutor.admit` (zero cost; no model, no browser)."""
import time

from fastapi.testclient import TestClient

from agent_readiness.hosted import stageb
from agent_readiness.hosted.admission import Admission
from agent_readiness.hosted.api import create_app

OP = {"authorization": "Bearer " + "t" * 32}


def _ev(left=1, available=True, fits=True):
    return {"arming_id": "larkspur-live-1", "mode": "paid", "launches": {"max": 1, "used": 1 - left, "left": left},
            "options": [{"repetitions": 1, "trials": 12, "reservation_usd": 7.436, "manifest_sha256": "0" * 64, "available": available, "fits_hosted_ceiling": fits}],
            "agent": {"model": "muse-spark-1.3", "profile": "suite-v2-compat2"}}


class _Exec:
    engine, mode = stageb.ENGINE, "live"

    def __init__(self, cfg, available=True):
        self.cfg, self.available, self.admitted = cfg, available, []

    def configuration(self):
        return self.cfg

    def admit(self, job_id, client, repetitions):                   # the real refusal is StageBExecutor.admit; here: record that nothing got through
        self.admitted.append(job_id)
        raise AssertionError("must not be reached when no launch is authorised")


def _cfg(armed=True, reason=None, ev=None):
    return {"engine": stageb.ENGINE, "armed": armed, "reason": reason, "evaluation": ev, "tasks": [{"task": 1}], "repetitions": [1] if ev and ev["options"][0]["available"] else []}


def _config(tmp_path, cfg, available=True, active=False):
    a = Admission(tmp_path / "admission.sqlite", ceiling_microusd=10_736_000, job_cap_microusd=1_650_000, min_interval_seconds=1)
    if active:
        a.reserve_amount("eval-" + "a" * 32, "b" * 64, 0)
    c = TestClient(create_app(tmp_path, a, client_key=b"k" * 32, executor=_Exec(cfg, available), operator_token=b"t" * 32, public_start=False, mode="live"))
    return c.get("/api/ironbark/config").json()


def test_authorised_and_idle(tmp_path):
    c = _config(tmp_path, _cfg(ev=_ev()))
    assert c["worker"]["state"] == "idle" and c["service"]["state"] == "operational"
    assert c["launch"] == {"authorized": True, "ready": True, "reason": None, "detail": None, "launches_left": 1, "covers": None} and c["available"] is True and c["reason"] is None


def test_the_used_launch_is_not_an_available_worker(tmp_path):
    """Production after the paid run: the worker is healthy, but the single authorised launch is used."""
    c = _config(tmp_path, _cfg(ev=_ev(left=0, available=False)))
    assert c["worker"]["state"] == "idle" and c["service"]["state"] == "operational"
    assert c["launch"]["authorized"] is False and c["launch"]["reason"] == "launches_exhausted" and "All live runs" in c["launch"]["detail"]
    assert c["available"] is False and c["reason"] == "launches_exhausted" and c["repetitions"] == []


def test_not_armed_and_budget_exhausted(tmp_path):
    assert _config(tmp_path / "a", _cfg(armed=False, reason="not_armed"))["launch"]["reason"] == "not_armed"
    c = _config(tmp_path / "b", _cfg(ev=_ev(left=1, available=False, fits=False)))
    assert c["launch"]["reason"] == "budget_exhausted" and c["available"] is False
    assert _config(tmp_path / "c", _cfg(ev=_ev(left=1, available=False, fits=True)))["launch"]["reason"] == "arming_total_exhausted"


def test_service_unavailable_is_reported_as_such(tmp_path):
    c = _config(tmp_path, _cfg(ev=_ev()), available=False)
    assert c["service"]["state"] == "unavailable" and c["worker"]["state"] == "unavailable" and c["launch"]["reason"] == "service_unavailable" and c["available"] is False


def test_a_running_evaluation_is_busy_not_unauthorised(tmp_path):
    c = _config(tmp_path, _cfg(ev=_ev()), active=True)
    assert c["worker"]["state"] == "busy" and c["launch"]["authorized"] is True and c["launch"]["ready"] is False
