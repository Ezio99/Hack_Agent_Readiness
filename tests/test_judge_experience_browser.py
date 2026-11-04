"""The exact judge experience, in a real browser, against the real website build and API (zero cost; run ALONE).

The shared budget is opened on a COPY of the lifecycle store (rehearsal mode: real jailed Chromium agents, the loopback dev provider instead of the
model). A judge opens the Workspace, sees the shared budget, enters the access code, clicks Run, watches progress, and inspects the results and an
agent trace. A second visitor without a code sees the running evaluation and can watch it. Nothing is reserved or spent (rehearsal)."""
import shutil
import socket
import sys
import threading
import time
from pathlib import Path

import pytest

from agent_readiness.evalruns import authorization as AU
from agent_readiness.hosted import budget as BG
from agent_readiness.hosted.admission import Admission
from agent_readiness.hosted.api import create_app
from agent_readiness.hosted.stageb import StageBExecutor
from agent_readiness.lifecycle import arming as AR
from agent_readiness.lifecycle.service import LifecycleService
from agent_readiness.suites.stage_a import approval as AP
from agent_readiness.suites.store import WriteOnceStore

ROOT = Path(__file__).resolve().parents[1]
STORE = ROOT / "scanner-data" / "research" / "stage-a" / "store"
DIST = ROOT / "dashboard" / "dist"
V2_SUITE = "172d1e712eb18871fd4f24b227a2448ec44a546347bb9874f0946c5609f7848b"
V3_SUITE = "0e46a1efe0a628ff2fb69c72ce0c0eb2323919570e4e3fbde1ac296d93460360"
KEEP = ["gen-23f1802ee0-n", "gen-8334922e62-n", "gen-f302fa8fe2-n"]
NOTES = "judge live evaluation: v2 tasks gen-23f1802ee0-n, gen-8334922e62-n and gen-f302fa8fe2-n (fee and seats; weekend class day and level; fee and duration)"
CODE = "shared-access-code-0123456789abcdef"
SHOTS = Path(__import__("os").environ.get("AR_JUDGE_SHOTS", "/tmp"))


def _spend(a, budget, target):
    """Record settled budget runs so the pool's actual spending reaches at least `target` µA$ (simulates earlier paid runs; rehearsals cost 0)."""
    import sqlite3
    db = sqlite3.connect(a.path)
    n = 0
    while True:
        spent = next(x for x in a.totals()["budgets"] if x["budget"] == budget)["spent_micro_aud"]
        if spent >= target:
            break
        job = "eval-" + f"{0xa00 + n + int(spent):032x}"
        db.execute("INSERT INTO jobs VALUES (?,?,?,?,?)", (job, "f" * 64, 1.0, "completed", 3_740_000))
        db.execute("INSERT INTO budget_jobs VALUES (?,?,?)", (job, budget, 1.0))
        db.commit()
        a.record_settlement(job, max(1, min(3_740_000, (target - spent) * 2 // 3)), basis="test", ledger_sha256="%064x" % (0xa00 + n + int(spent)),
                            ledger_requests=1, open_requests=0, actor="test")
        n += 1
    db.close()


def _port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.mark.browser
@pytest.mark.skipif(not (STORE / "objects").is_dir() or not (DIST / "index.html").is_file(), reason="needs the local lifecycle store and a dashboard build")
def test_a_judge_opens_the_site_enters_the_code_runs_watches_and_inspects(tmp_path, monkeypatch):
    import uvicorn
    from playwright.sync_api import expect, sync_playwright
    monkeypatch.setenv("AR_STAGE_B_ROOT", str(tmp_path / "stage-b"))
    monkeypatch.setattr(AU, "STAGE_B", tmp_path / "stage-b")
    AR.set_stage_b_root(tmp_path / "stage-b")
    shutil.copytree(STORE, tmp_path / "store")
    st = WriteOnceStore(tmp_path / "store")
    assert AP.revise_keep(st, V2_SUITE, keep=KEEP, context=AP._context(type("A", (), {"context": None})()), at="2026-11-04T00:00:00+00:00", by="owner",
                          notes=NOTES) == V3_SUITE
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    appr = AP.decide(st, V3_SUITE, decision="approved", attestation=AP.attestation_text(V3_SUITE, "approved"), at="2026-11-04T00:01:00+00:00", notes="test copy")
    AP.freeze(st, V3_SUITE, appr, at="2026-11-04T00:02:00+00:00")
    root = tmp_path / "hosted"
    a = Admission(tmp_path / "a.sqlite", ceiling_microusd=12_000_000, job_cap_microusd=1_650_000, min_interval_seconds=60)
    kw = dict(store=st, frozen="larkspur-core@v3", variants=["polishedoriginal", "modifiedpolished"], mode="rehearsal")   # as in production: Before and After, paired
    p = BG.plan_open(a, "ar-a20-2026-11", "20", "1.50", **kw)
    BG.open_budget(a, "ar-a20-2026-11", "20", "1.50", actor="owner (test copy)", typed=p["text"], **kw)
    ex = StageBExecutor(root, st.root, a, mode="rehearsal", timeout=1800)
    svc = LifecycleService(datasets=None, store_root=st.root, runs_root=root / "stageb", executor=ex, admission=a, log=lambda *_: None)
    app = create_app(root, a, client_key=b"k" * 32, executor=ex, operator_token=b"o" * 32, public_start=False, mode="rehearsal", lifecycle=svc,
                     judge_token=CODE.encode(), static_dir=DIST)
    port = _port()
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    th = threading.Thread(target=server.run, daemon=True)
    th.start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.1)
    base = f"http://127.0.0.1:{port}/"
    try:
        with sync_playwright() as pw:
            b = pw.chromium.launch()
            judge = b.new_page(viewport={"width": 1440, "height": 1000})
            errors, writes = [], []
            judge.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
            judge.on("request", lambda r: writes.append((r.method, r.url, r.headers.get("authorization"))) if r.method not in ("GET", "HEAD") else None)
            # 1. open the Workspace: the shared budget is visible, no launch count, Run waits for a code
            judge.goto(base + "#/run")
            judge.wait_for_selector(".ws-shared-budget")
            assert "A$20.00 of A$20.00 evaluation budget left" in judge.inner_text(".ws-shared-budget")
            assert "runs while the budget lasts" in judge.inner_text(".ws-target")
            run = judge.get_by_role("button", name="Run evaluation")
            assert run.is_disabled()
            judge.screenshot(path=str(SHOTS / "judge-1-workspace.png"))
            # 2. enter the code and launch
            judge.fill("#ws-operator-token", CODE)
            assert run.is_enabled()
            run.dblclick()                                                            # even a double-click starts exactly one run
            judge.wait_for_selector(".ws-job-head", timeout=30_000)
            expect(judge.locator(".ws-status")).to_contain_text("agent runs finished", timeout=30_000)
            jobs = a.recent()
            assert len(jobs) == 1 and a.job_budget(jobs[0]["id"]) == "ar-a20-2026-11"
            job = jobs[0]["id"]
            posts = [w for w in writes if w[0] == "POST"]
            assert len(posts) == 1 and posts[0][2] == f"Bearer {CODE}"
            # 3. a second visitor without a code sees the running evaluation and can watch it
            visitor = b.new_page(viewport={"width": 1440, "height": 1000})
            visitor.goto(base + "#/run")
            visitor.wait_for_selector(".ws-worker.busy", timeout=30_000)
            assert "Another evaluation is running" in visitor.inner_text(".ws-worker") or "Running your selected evaluation" in visitor.inner_text(".ws-worker")
            visitor.wait_for_selector(".ws-job-head", timeout=30_000)                  # the public Workspace opens the running evaluation by itself
            assert job[:13] in visitor.inner_text(".ws-job-meta")
            visitor.screenshot(path=str(SHOTS / "judge-2-visitor-watching.png"))
            # 4. watch progress to completion
            judge.screenshot(path=str(SHOTS / "judge-3-running.png"))
            expect(judge.locator(".ws-status")).to_contain_text("Completed", timeout=1_200_000)
            assert "6 / 6 agent runs finished" in judge.inner_text(".ws-status")
            # 5. inspect the results: the readiness report and an agent trace
            judge.get_by_role("tab", name="Readiness report").click()
            judge.wait_for_selector(".ws-report", timeout=60_000)
            report = judge.inner_text(".ws-report")
            assert "Before" in report and "After" in report and "Task success" in report and "Original" not in report and "Improved" not in report
            judge.screenshot(path=str(SHOTS / "judge-4-report.png"))
            judge.get_by_role("tab", name="Agent runs").click()
            cells = judge.locator(".ws-grid tbody td button, .ws-grid tbody td[role=button], .ws-grid tbody td")
            assert cells.count() >= 6
            assert judge.locator(".ws-grid tbody tr").count() == 3
            judge.locator(".ws-grid tbody td").nth(0).click()
            judge.wait_for_selector(".ws-agent, .ws-trace, [class*=step]", timeout=30_000)
            judge.screenshot(path=str(SHOTS / "judge-5-trace.png"))
            assert not errors, errors
            assert [w[0] for w in writes] == ["POST"]                                 # the only write the judge's browser made

            # 6. repeated launches beyond the old three-launch limit: the same code, the same button, no quota, no cooldown
            def launch_and_finish(n):
                before = {j["id"] for j in a.recent()}
                judge.get_by_role("button", name="Run evaluation").click()
                new, deadline = [], time.time() + 30
                while not new and time.time() < deadline:
                    new = [j["id"] for j in a.recent() if j["id"] not in before]
                    time.sleep(0.3)
                assert len(new) == 1, (n, new, judge.inner_text(".ws-compose"))
                expect(judge.locator(".ws-job-meta")).to_contain_text(new[0][:13], timeout=30_000)
                expect(judge.locator(".ws-status")).to_contain_text("Completed", timeout=1_200_000)
                expect(judge.get_by_role("button", name="Run evaluation")).to_be_enabled(timeout=60_000)
                return new[0]
            more = [launch_and_finish(n) for n in (2, 3, 4)]
            assert all(a.job_budget(j) == "ar-a20-2026-11" for j in [job, *more]) and len(AR.claims("ar-a20-2026-11")) == 4
            judge.screenshot(path=str(SHOTS / "judge-6-fourth-run.png"))

            # 7. near the limit: just under A$20 actually spent -> still admitted (its worst case is not compared with what remains)
            _spend(a, "ar-a20-2026-11", 19_990_000)
            judge.reload()
            judge.wait_for_selector(".ws-shared-budget")
            assert "A$0.01 of A$20.00 evaluation budget left" in judge.inner_text(".ws-shared-budget")
            judge.fill("#ws-operator-token", CODE)                                    # a reload clears the code from the page's memory
            fifth = launch_and_finish(5)
            assert a.job_budget(fifth) == "ar-a20-2026-11"

            # 8. once A$20 has been spent: Run is disabled with a clear reason; the server refuses too; results stay available
            _spend(a, "ar-a20-2026-11", 20_000_000)
            fresh = b.new_context(viewport={"width": 1440, "height": 1000}).new_page()   # a clean browser
            fresh.goto(base + "#/run")
            fresh.wait_for_selector(".ws-shared-budget")
            assert "A$0.00 of A$20.00 evaluation budget left" in fresh.inner_text(".ws-shared-budget")
            assert fresh.locator("#ws-operator-token").count() == 0                     # no code field once nothing can be started
            assert fresh.get_by_role("button", name="Run evaluation").is_disabled()
            assert "The A$20 evaluation budget has been used" in fresh.inner_text("#ws-run-note")
            fresh.screenshot(path=str(SHOTS / "judge-7-budget-used.png"))
            assert "eval-" in fresh.inner_text(".history-table")                       # completed evaluations remain listed and open
            b.close()
    finally:
        server.should_exit = True
        th.join(10)
    for _ in range(20):
        if a.settlement(job) is not None:
            break
        time.sleep(0.5)
    assert a.settlement(job)["settled_microusd"] == 0                                 # reconciled automatically (a rehearsal spends nothing)
    for f in list(root.rglob("*")) + list((tmp_path / "stage-b").rglob("*")):
        if f.is_file():
            assert CODE.encode() not in f.read_bytes()
