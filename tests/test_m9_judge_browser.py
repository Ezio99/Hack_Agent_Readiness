"""M9 judge live evaluation, end to end through the HOSTED launch path (zero cost; run ALONE: real Chromium in the network jail, the loopback dev
provider standing in for the model; needs the local lifecycle store).

On a COPY of the real store: the owner tooling builds `larkspur-core@v3` (exactly tasks gen-23f1802ee0-n and gen-f302fa8fe2-n of v2; the hash is
the reproducible one the owner checks), approves and freezes it, and arms a 4-launch REHEARSAL pool -> a judge starts it with the judge access
code (`POST /api/ironbark/jobs {"repetitions": 1}`) -> the real worker subprocess runs the 4 trials (Original and Modified) in jailed Chromium ->
progress, live, trials, screenshots, the readiness report and the export are served; the pool shows 3 launches left; the code appears nowhere."""
import shutil
import sys
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
from agent_readiness.suites.stage_a import approval as AP
from agent_readiness.suites.store import WriteOnceStore

STORE = Path(__file__).resolve().parents[1] / "scanner-data" / "research" / "stage-a" / "store"
V2_SUITE = "172d1e712eb18871fd4f24b227a2448ec44a546347bb9874f0946c5609f7848b"
V3_SUITE = "f45694788ea9e1f7b28c95193e25870bfe3aed2975d7f00276cdc87d7c6b09e3"
NOTES = "judge live evaluation: tasks gen-23f1802ee0-n and gen-f302fa8fe2-n of v2 (their deciding facts are on the Modified listing cards)"
OPERATOR, JUDGE = b"o" * 32, b"judge-access-code-0123456789abcdef"


@pytest.mark.browser
@pytest.mark.skipif(not (STORE / "objects").is_dir(), reason="needs the local lifecycle store")
def test_a_judge_runs_the_two_task_live_evaluation_end_to_end(tmp_path, monkeypatch):
    monkeypatch.setenv("AR_STAGE_B_ROOT", str(tmp_path / "stage-b"))                 # the worker subprocess inherits it
    monkeypatch.setattr(AU, "STAGE_B", tmp_path / "stage-b")
    shutil.copytree(STORE, tmp_path / "store")
    st = WriteOnceStore(tmp_path / "store")
    # owner tooling (on the copy): revise -> decide (interactive in production; the terminal check is tested elsewhere) -> freeze
    assert AP.revise_keep(st, V2_SUITE, keep=["gen-23f1802ee0-n", "gen-f302fa8fe2-n"], context=AP._context(type("A", (), {"context": None})()),
                          at="2026-11-03T12:00:00+00:00", by="owner", notes=NOTES) == V3_SUITE
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    appr = AP.decide(st, V3_SUITE, decision="approved", attestation=AP.attestation_text(V3_SUITE, "approved"), at="2026-11-03T12:01:00+00:00", notes="test copy")
    AP.freeze(st, V3_SUITE, appr, at="2026-11-03T12:02:00+00:00")
    kw = dict(arming_id="judge-e2e-1", mode="rehearsal", frozen_ref="larkspur-core@v3", variants=["original", "modified"], repetitions=[1], launches=4)
    p = AR.plan(st, **kw)
    assert p["options"][0]["trials"] == 4
    AR.arm(st, typed=p["attestation"], at="2026-11-03T12:03:00+00:00", interactive=True, **kw)

    root = tmp_path / "hosted"
    a = Admission(tmp_path / "a.sqlite", ceiling_microusd=10_000_000, job_cap_microusd=1_650_000, min_interval_seconds=60)
    ex = StageBExecutor(root, st.root, a, mode="rehearsal", timeout=1800)
    svc = LifecycleService(datasets=None, store_root=st.root, runs_root=root / "stageb", executor=ex, admission=a, log=lambda *_: None)
    c = TestClient(create_app(root, a, client_key=b"k" * 32, executor=ex, operator_token=OPERATOR, public_start=False, mode="rehearsal",
                              lifecycle=svc, judge_token=JUDGE))
    cfg = c.get("/api/ironbark/config").json()
    assert cfg["judge_access"] and cfg["launch"]["authorized"] and cfg["evaluation"]["launches"]["left"] == 4 and len(cfg["tasks"]) == 2
    assert c.post("/api/ironbark/jobs", json={"repetitions": 1}).status_code == 403                             # no code
    r = c.post("/api/ironbark/jobs", json={"repetitions": 1}, headers={"authorization": "Bearer " + JUDGE.decode()})
    assert r.status_code == 202, r.text
    job = r.json()["id"]
    seen_live, deadline = False, time.time() + 1200
    while time.time() < deadline:
        st_ = c.get(f"/api/ironbark/jobs/{job}").json()
        if st_["state"] not in ("reserved", "running"):
            break
        seen_live |= bool(c.get(f"/api/ironbark/jobs/{job}/live").json().get("trial"))
        time.sleep(3)
    assert st_["state"] == "completed", (st_.get("error"), st_.get("stopped"))
    assert st_["execution"] == {"state": "completed", "trials_planned": 4, "trials_completed": 4, "trials_failed": 0, "trials_void": 0}
    assert st_["report_status"]["state"] == "available" and seen_live
    tr = c.get(f"/api/ironbark/jobs/{job}/repetitions/1/trials/modified/1").json()
    assert tr["steps"]
    assert c.get(f"/api/ironbark/jobs/{job}/repetitions/1/trials/modified/1/screenshots/{tr['steps'][0]['screenshot']}").status_code == 200
    ev = c.get(f"/api/lifecycle/evaluations/{job}").json()
    assert ev["title"] == "Rehearsal evaluation · Larkspur Community College · Original vs Modified" and len(ev["trials"]) == 4
    assert {t["task_id"] for t in ev["trials"]} == {"gen-23f1802ee0-n", "gen-f302fa8fe2-n"}
    from agent_readiness.evalruns import runner as RN
    assert audit.check_evaluation(ev, RN._answers(st, ev["frozen_suite"]["sha256"])) == []
    assert c.get(f"/api/ironbark/jobs/{job}/repetitions/1/export").status_code == 200
    assert c.get("/api/ironbark/config").json()["evaluation"]["launches"]["left"] == 3
    for f in list(root.rglob("*")) + list((tmp_path / "stage-b").rglob("*")):
        if f.is_file():
            assert JUDGE not in f.read_bytes()
