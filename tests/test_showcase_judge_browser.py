"""Final showcase: a judge launch of the FEATURED configuration, end to end through the hosted launch path (zero cost; run ALONE: real Chromium
in the network jail, the loopback dev provider standing in for the model; needs the local lifecycle store).

On a COPY of the real store: the featured judge suite `larkspur-core@v3` (THREE v2 tasks: fee and seats, weekend class day and level, fee and
duration; `revise` must give the reproducible hash the owner checks) is revised, approved and frozen, and a 3-launch REHEARSAL pool is armed on
Original vs IMPROVED -> a judge starts it with the access code -> 6 jailed trials -> the job shows Original vs Improved, the readiness report is
available, audit-clean and has its diagnostics (Improved resolves every page-audit problem), and the code is nowhere."""

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
V3_SUITE = "0e46a1efe0a628ff2fb69c72ce0c0eb2323919570e4e3fbde1ac296d93460360"     # the three-task judge suite (final showcase)
KEEP = ["gen-23f1802ee0-n", "gen-8334922e62-n", "gen-f302fa8fe2-n"]
NOTES = "judge live evaluation: v2 tasks gen-23f1802ee0-n, gen-8334922e62-n and gen-f302fa8fe2-n (fee and seats; weekend class day and level; fee and duration)"
OPERATOR, JUDGE = b"o" * 32, b"judge-access-code-0123456789abcdef"


@pytest.mark.browser
@pytest.mark.skipif(not (STORE / "objects").is_dir(), reason="needs the local lifecycle store")
def test_a_judge_runs_the_featured_original_vs_improved_evaluation(tmp_path, monkeypatch):
    monkeypatch.setenv("AR_STAGE_B_ROOT", str(tmp_path / "stage-b"))                 # the worker subprocess inherits it
    monkeypatch.setattr(AU, "STAGE_B", tmp_path / "stage-b")
    shutil.copytree(STORE, tmp_path / "store")
    st = WriteOnceStore(tmp_path / "store")
    # owner tooling (on the copy): revise -> decide (interactive in production; the terminal check is tested elsewhere) -> freeze
    assert AP.revise_keep(st, V2_SUITE, keep=KEEP, context=AP._context(type("A", (), {"context": None})()),
                          at="2026-11-04T00:00:00+00:00", by="owner", notes=NOTES) == V3_SUITE
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    appr = AP.decide(st, V3_SUITE, decision="approved", attestation=AP.attestation_text(V3_SUITE, "approved"), at="2026-11-03T12:01:00+00:00", notes="test copy")
    AP.freeze(st, V3_SUITE, appr, at="2026-11-03T12:02:00+00:00")
    kw = dict(arming_id="showcase-e2e-1", mode="rehearsal", frozen_ref="larkspur-core@v3", variants=["original", "improved"], repetitions=[1], launches=3)
    p = AR.plan(st, **kw)
    assert p["options"][0]["trials"] == 6 and p["options"][0]["reservation_microusd"] == 3_740_000 and p["total_reservation_microusd"] == 11_220_000
    AR.arm(st, typed=p["attestation"], at="2026-11-03T12:03:00+00:00", interactive=True, **kw)

    root = tmp_path / "hosted"
    a = Admission(tmp_path / "a.sqlite", ceiling_microusd=12_000_000, job_cap_microusd=1_650_000, min_interval_seconds=60)
    ex = StageBExecutor(root, st.root, a, mode="rehearsal", timeout=1800)
    svc = LifecycleService(datasets=None, store_root=st.root, runs_root=root / "stageb", executor=ex, admission=a, log=lambda *_: None)
    c = TestClient(create_app(root, a, client_key=b"k" * 32, executor=ex, operator_token=OPERATOR, public_start=False, mode="rehearsal",
                              lifecycle=svc, judge_token=JUDGE))
    cfg = c.get("/api/ironbark/config").json()
    assert cfg["judge_access"] and cfg["launch"]["authorized"] and cfg["evaluation"]["launches"]["left"] == 3 and len(cfg["tasks"]) == 3
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
    assert st_["execution"] == {"state": "completed", "trials_planned": 6, "trials_completed": 6, "trials_failed": 0, "trials_void": 0}
    assert st_["report_status"]["state"] == "available" and seen_live
    assert st_["arm_display"] == {"Original": "Original", "Modified": "Improved"} and st_["evaluation"]["variants"] == ["original", "improved"]
    assert all(isinstance(t.get("correct"), bool) and isinstance(t.get("exact_match"), bool) for t in st_["reps"][0]["tasks"])   # the grid reads like the report
    for _ in range(20):                                                            # actual-cost settlement runs when the job thread ends
        if a.settlement(job) is not None:
            break
        time.sleep(0.5)
    s_ = a.settlement(job)
    assert s_ is not None and s_["settled_microusd"] == 0 and s_["actor"].startswith("service (automatic")   # rehearsal: nothing reserved, nothing spent
    assert c.get("/api/ironbark/config").json()["spending"]["settled_jobs"] == 1
    tr = c.get(f"/api/ironbark/jobs/{job}/repetitions/1/trials/modified/1").json()
    assert tr["steps"]
    assert c.get(f"/api/ironbark/jobs/{job}/repetitions/1/trials/modified/1/screenshots/{tr['steps'][0]['screenshot']}").status_code == 200
    ev = c.get(f"/api/lifecycle/evaluations/{job}").json()
    assert ev["title"] == "Rehearsal evaluation · Larkspur Community College · Original vs Improved" and len(ev["trials"]) == 6
    assert [v["name"] for v in ev["manifest"]["variants"]] == ["original", "improved"]
    diag = next(iter(ev["diagnostics"].values()))
    assert diag["available"], diag
    assert diag["structural_changes"]["improved"]["resolved"] == 7 and diag["structural_changes"]["improved"]["introduced"] == 0
    assert {t["task_id"] for t in ev["trials"]} == set(KEEP)
    from agent_readiness.evalruns import runner as RN
    assert audit.check_evaluation(ev, RN._answers(st, ev["frozen_suite"]["sha256"])) == []
    assert c.get(f"/api/ironbark/jobs/{job}/repetitions/1/export").status_code == 200
    assert c.get("/api/ironbark/config").json()["evaluation"]["launches"]["left"] == 2
    for f in list(root.rglob("*")) + list((tmp_path / "stage-b").rglob("*")):
        if f.is_file():
            assert JUDGE not in f.read_bytes()
