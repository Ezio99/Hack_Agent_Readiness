"""M8 end-to-end integration rehearsal (zero cost; run ALONE: real Chromium in the network jail, the loopback dev provider standing in for the model).

Through the product API: an operator launches a rehearsal of a frozen suite -> the lifecycle service reserves US$0 in the hosted admission slot ->
the real worker subprocess (`lifecycle.jobs`) runs the Stage B runner (prepare, jailed execute, report, public leak audit) -> the completed job is
projected by the SAME projection as the preloaded M7 dataset -> the report, a trial timeline and a recorded screenshot are served, with the scripted
stand-in's replies withheld (they are derived from the private expected outcomes) and the evaluation labelled a rehearsal."""
import time

import pytest
from fastapi.testclient import TestClient

from agent_readiness.hosted.admission import Admission
from agent_readiness.hosted.api import create_app
from agent_readiness.lifecycle import audit
from agent_readiness.lifecycle.jobs import LifecycleExecutor
from agent_readiness.lifecycle.service import LifecycleService

TOKEN = b"t" * 32


@pytest.mark.browser
def test_operator_rehearsal_runs_end_to_end_through_the_product_api(tmp_path):
    import importlib.util
    from pathlib import Path
    spec = importlib.util.spec_from_file_location("m7_paid_guard_fixture", Path(__file__).parent / "test_m7_paid_guard.py")
    T = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(T)
    store, f, msha, _ = T.build(tmp_path, real_name="synthetic-larkspur-m8-e2e")
    store.ref("frozen_suite", "synthetic-larkspur-m8-e2e@v1", f)
    runs = tmp_path / "runs"
    runs.mkdir()
    a = Admission(tmp_path / "a.sqlite", ceiling_microusd=10_000_000, job_cap_microusd=1_650_000, min_interval_seconds=60)
    svc = LifecycleService(datasets=None, store_root=store.root, runs_root=runs, executor=LifecycleExecutor(runs, store.root, a, timeout=1800),
                           admission=a, client_key=b"k" * 32, log=lambda *_: None)
    c = TestClient(create_app(tmp_path / "hosted", a, client_key=b"k" * 32, operator_token=TOKEN, public_start=False, mode="disabled", lifecycle=svc))
    r = c.post("/api/lifecycle/evaluations", json={"frozen_suite": "synthetic-larkspur-m8-e2e@v1", "variants": ["original", "modified"], "mode": "rehearsal"},
               headers={"authorization": "Bearer " + TOKEN.decode()})
    assert r.status_code == 202, r.text
    job = r.json()["id"]
    assert r.json()["manifest_sha256"] == msha
    deadline = time.time() + 1500
    while time.time() < deadline:
        st = c.get(f"/api/lifecycle/jobs/{job}").json()
        if st["state"] not in ("reserved", "running"):
            break
        time.sleep(5)
    assert st["state"] == "completed", (st.get("error"), st.get("stopped"))
    assert st["completed_trials"] == st["planned"] == 6 and a.get(job)["state"] == "completed" and a.get(job)["reserved_microusd"] == 0
    ev = c.get(f"/api/lifecycle/evaluations/{job}").json()
    assert ev["mode"] == "rehearsal" and "not from a model" in ev["notice"] and ev["cost"]["total_usd"] == 0.0 and ev["source"]["kind"] == "launched"
    assert len(ev["trials"]) == 6 and all(t["answer"] is None and t["answer_withheld"] for t in ev["trials"])
    assert set(ev["dimensions"]) == {"task_success", "navigation_efficiency", "evidence_quality", "information_accessibility", "agent_reliability", "coverage"}
    assert all(x["jail_selftest_ok"] for x in ev["execution"].values())
    assert ev["diagnostics"]["natural"].get("evidence_origin") in (None, "dev_fixture")                       # fixture behaviour never supports a hypothesis
    from agent_readiness.evalruns import runner as RN
    assert audit.check_evaluation(ev, RN._answers(store, f)) == []
    tid = ev["trials"][0]["id"]
    tl = c.get(f"/api/lifecycle/evaluations/{job}/trials/{tid}").json()
    assert tl["steps"] and all(s["memory"] is None for s in tl["steps"])
    shot = c.get(f"/api/lifecycle/evaluations/{job}/trials/{tid}/screenshots/{tl['screenshots'][0]}")
    assert shot.status_code == 200 and shot.headers["content-type"] == "image/png"
    assert any(e["id"] == job and e["state"] == "completed" for e in c.get("/api/lifecycle/evaluations").json())
