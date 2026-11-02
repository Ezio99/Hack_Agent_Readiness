"""M8 end-to-end integration rehearsal through the HOSTED launch path (zero cost; run ALONE: real Chromium in the network jail, the loopback dev
provider standing in for the model).

The owner arms a frozen suite (terminal attestation) -> the operator launches `POST /api/ironbark/jobs {"repetitions": 1}` with the operator token,
exactly as before -> the Stage B executor reserves in the hosted admission and claims the launch -> the real worker subprocess re-checks the claim
and runs the Stage B runner (prepare, jailed execute, report, public leak audit) -> the hosted progress, trial, screenshot, live and export routes
read the Stage B records -> the readiness report is the SAME lifecycle projection as the preloaded M7 dataset, with the stand-in's replies
withheld and the evaluation labelled a rehearsal."""
import importlib.util
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from agent_readiness.evalruns import authorization as AU
from agent_readiness.hosted.admission import Admission
from agent_readiness.hosted.api import create_app
from agent_readiness.hosted.stageb import StageBExecutor
from agent_readiness.lifecycle import arming as AR
from agent_readiness.lifecycle import audit
from agent_readiness.lifecycle.service import LifecycleService

TOKEN = b"t" * 32
OP = {"authorization": "Bearer " + TOKEN.decode()}


@pytest.mark.browser
def test_an_operator_launch_runs_the_stage_b_pipeline_and_reports_through_the_lifecycle(tmp_path, monkeypatch):
    monkeypatch.setenv("AR_STAGE_B_ROOT", str(tmp_path / "stage-b"))                 # the worker subprocess inherits it
    monkeypatch.setattr(AU, "STAGE_B", tmp_path / "stage-b")
    spec = importlib.util.spec_from_file_location("m7_paid_guard_fixture", Path(__file__).parent / "test_m7_paid_guard.py")
    T = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(T)
    store, f, msha, _ = T.build(tmp_path, real_name="synthetic-larkspur-m8-e2e")
    store.ref("frozen_suite", "synthetic-larkspur-m8-e2e@v1", f)
    kw = dict(arming_id="e2e-rehearsal-1", mode="rehearsal", frozen_ref="synthetic-larkspur-m8-e2e@v1", variants=["original", "modified"], repetitions=[1], launches=1)
    p = AR.plan(store, **kw)
    AR.arm(store, typed=p["attestation"], at="2026-11-04T03:00:00+00:00", interactive=True, **kw)

    root = tmp_path / "hosted"
    a = Admission(tmp_path / "a.sqlite", ceiling_microusd=10_000_000, job_cap_microusd=1_650_000, min_interval_seconds=60)
    ex = StageBExecutor(root, store.root, a, mode="rehearsal", timeout=1800)
    svc = LifecycleService(datasets=None, store_root=store.root, runs_root=root / "stageb", executor=ex, admission=a, log=lambda *_: None)
    c = TestClient(create_app(root, a, client_key=b"k" * 32, executor=ex, operator_token=TOKEN, public_start=False, mode="rehearsal", lifecycle=svc))

    cfg = c.get("/api/ironbark/config").json()
    assert cfg["available"] and cfg["engine"] == "stage-b" and cfg["repetitions"] == [1] and len(cfg["tasks"]) == 3
    r = c.post("/api/ironbark/jobs", json={"repetitions": 1}, headers=OP)
    assert r.status_code == 202, r.text
    job = r.json()["id"]
    seen_live = False
    deadline = time.time() + 1500
    while time.time() < deadline:
        st = c.get(f"/api/ironbark/jobs/{job}").json()
        if st["state"] not in ("reserved", "running"):
            break
        live = c.get(f"/api/ironbark/jobs/{job}/live").json()
        seen_live |= bool(live.get("trial"))
        time.sleep(3)
    assert st["state"] == "completed", (st.get("error"), st.get("stopped"))
    assert st["engine"] == "stage-b" and st["report"] == job and st["mode"] == "rehearsal"
    rows = st["reps"][0]["tasks"]
    assert len(rows) == 6 and all(t["state"] == "completed" for t in rows) and {t["arm"] for t in rows} == {"Original", "Modified"}
    assert st["summary"]["Original"]["completed"] == st["summary"]["Modified"]["completed"] == 3
    assert a.get(job)["state"] == "completed" and a.get(job)["reserved_microusd"] == 0
    assert seen_live

    tr = c.get(f"/api/ironbark/jobs/{job}/repetitions/1/trials/original/1").json()           # the workspace's agent panel
    assert tr["steps"] and all(s["memory"] is None for s in tr["steps"])                      # stand-in replies withheld
    shot = c.get(f"/api/ironbark/jobs/{job}/repetitions/1/trials/original/1/screenshots/{tr['steps'][0]['screenshot']}")
    assert shot.status_code == 200 and shot.headers["content-type"] == "image/png"

    ev = c.get(f"/api/lifecycle/evaluations/{job}").json()                                    # the readiness report: the lifecycle projection
    assert ev["mode"] == "rehearsal" and "not from a model" in ev["notice"] and ev["manifest"]["sha256"] == msha and len(ev["trials"]) == 6
    assert set(ev["dimensions"]) == {"task_success", "navigation_efficiency", "evidence_quality", "information_accessibility", "agent_reliability", "coverage"}
    assert all(t["answer"] is None for t in ev["trials"]) and all(x["jail_selftest_ok"] for x in ev["execution"].values())
    from agent_readiness.evalruns import runner as RN
    assert audit.check_evaluation(ev, RN._answers(store, f)) == []
    assert c.get(f"/api/ironbark/jobs/{job}/repetitions/1/export").json()["id"] == job        # the export is the same audited document
    assert c.get(f"/api/lifecycle/evaluations/{job}/trials/{ev['trials'][0]['id']}").json()["steps"]
    assert c.post("/api/ironbark/jobs", json={"repetitions": 1}, headers=OP).status_code in (409, 429)   # the single armed launch is used
