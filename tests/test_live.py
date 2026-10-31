"""Live evaluation M0: job lifecycle, ownership, limits, cancellation, timeout, credential scrubbing, HTTP contract; plus one real end-to-end mock job through the unchanged investigation pipeline."""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from agent_readiness.live import jobs as J, worker
from agent_readiness.live.jobs import JobError, JobManager
from agent_readiness.scanner.service import api as api_mod
from agent_readiness.scanner.service.config import ScannerConfig

GOAL = "Can an agent compare hire prices and availability?"


def manager(tmp_path, **kw):
    spawned = []
    m = JobManager(tmp_path / "live", spawn=lambda jid: spawned.append(jid) or 0, **kw)
    return m, spawned


def test_a_job_is_validated_owned_and_one_at_a_time(tmp_path):
    m, spawned = manager(tmp_path)
    with pytest.raises(JobError) as e:
        m.create("a", "https://evil.example", GOAL)
    assert e.value.status == 422, "a URL is not a target: only registered ids exist"
    for bad in ("", "hi", "x" * 301):
        with pytest.raises(JobError) as e:
            m.create("a", "ironbark", bad)
        assert e.value.status == 422
    with pytest.raises(JobError) as e:
        m.create("a", "ironbark", GOAL, mode="live")
    assert e.value.status == 409 and "not enabled" in e.value.message
    j = m.create("a", "ironbark", GOAL)
    assert j["state"] == "queued" and j["mock"] and "No language model was called" in j["notice"] and spawned == [j["id"]]
    assert j["spend"] == {"committed_usd": 0.0, "hard_cap_usd": 0.0, "basis": "mock: no model call, nothing spent"} and j["stages"][0]["status"] == "pending"
    with pytest.raises(JobError) as e:
        m.create("b", "ironbark", GOAL)
    assert e.value.status == 409, "a second job while one is queued/running is refused"
    with pytest.raises(JobError) as e:
        m.get(j["id"], "b")
    assert e.value.status == 404, "another user's job looks like an unknown id"
    with pytest.raises(JobError):
        m.get("../../etc/passwd", "a")
    assert [x["id"] for x in m.list("a")] == [j["id"]] and m.list("b") == []


def test_cancel_timeout_restart_and_kill_switch(tmp_path):
    m, _ = manager(tmp_path)
    j = m.create("a", "ironbark", GOAL)
    c = m.cancel(j["id"], "a")
    assert c["state"] == "cancelled" and c["finished_at"]
    assert m.create("a", "ironbark", GOAL)["state"] == "queued", "after a cancel the slot is free"
    m2, _ = manager(tmp_path / "t", timeout=1)
    j2 = m2.create("a", "ironbark", GOAL)
    m2._expire(j2["id"])
    assert m2.get(j2["id"], "a")["state"] == "timed_out" and "exceeded" in m2.get(j2["id"], "a")["error"]
    m3, _ = manager(tmp_path / "k", killed=lambda: True)
    with pytest.raises(JobError) as e:
        m3.create("a", "ironbark", GOAL)
    assert e.value.status == 503
    # a job whose worker died (server restart / crash) is recorded as failed, never left 'running' forever
    m4, _ = manager(tmp_path / "r")
    j4 = m4.create("a", "ironbark", GOAL)
    worker.update(m4.root, j4["id"], state="running", pid=999999999)
    assert JobManager(m4.root).get(j4["id"], "a")["state"] == "failed", "recovery on startup"


def test_a_terminal_state_is_never_overwritten_by_the_dying_worker(tmp_path):
    m, _ = manager(tmp_path)
    j = m.create("a", "ironbark", GOAL)
    m.cancel(j["id"], "a")
    worker.update(m.root, j["id"], state="failed", error="late")
    assert m.get(j["id"], "a")["state"] == "cancelled"


def test_the_worker_never_receives_a_credential(tmp_path, monkeypatch):
    monkeypatch.setenv("META_MODEL_API_KEY", "sk-test-not-real")
    monkeypatch.setenv("SOME_SECRET_TOKEN", "x")
    seen = {}
    real = subprocess.Popen

    def fake(cmd, **kw):
        seen.update(kw["env"])
        class P: pid = 0
        return P()
    monkeypatch.setattr(subprocess, "Popen", fake)
    m = JobManager(tmp_path / "live")
    m.create("a", "ironbark", GOAL)
    assert "META_MODEL_API_KEY" not in seen and "SOME_SECRET_TOKEN" not in seen and "PATH" in seen


def test_a_live_job_is_refused_by_the_worker_even_if_one_were_queued(tmp_path):
    m, _ = manager(tmp_path)
    j = m.create("a", "ironbark", GOAL)
    worker.update(m.root, j["id"], mode="live")
    worker.execute(m.root, j["id"])
    assert worker.read(m.root, j["id"])["state"] == "failed" and "not enabled" in worker.read(m.root, j["id"])["error"]


@pytest.fixture
def http(tmp_path):
    cfg = ScannerConfig(data_dir=tmp_path, secret="s", admin_token="adm", rate_limit_per_minute=1000)
    spawned = []
    app = api_mod.create_scanner_app(cfg, live_jobs=JobManager(tmp_path / "live", spawn=lambda jid: spawned.append(jid) or 0, killed=lambda: cfg.kill_switch_path.exists()))
    c = TestClient(app)
    store = app.state.store
    _, code = store.create_invitation("t", 1, 1, 5)
    tok = c.post("/api/session", json={"code": code}).json()["token"]
    return cfg, c, {"Authorization": f"Bearer {tok}"}, spawned, app


def test_http_contract_requires_a_session_has_no_url_field_and_shares_the_kill_switch(http):
    cfg, c, h, spawned, app = http
    assert c.get("/api/live/targets").status_code == 401 and c.post("/api/live/jobs", json={"target_id": "ironbark", "goal": GOAL}).status_code == 401
    t = c.get("/api/live/targets", headers=h).json()
    assert {x["id"] for x in t["targets"]} >= {"ironbark"} and t["modes"] == {"mock": True, "live": False}
    assert c.post("/api/live/jobs", headers=h, json={"target_id": "ironbark", "goal": GOAL, "url": "http://x"}).status_code == 422, "extra fields (url, prompt, key) are rejected"
    assert c.post("/api/live/jobs", headers=h, json={"target_id": "ironbark", "goal": GOAL, "mode": "live"}).status_code == 409
    r = c.post("/api/live/jobs", headers=h, json={"target_id": "ironbark", "goal": GOAL})
    assert r.status_code == 202 and r.json()["state"] == "queued"
    jid = r.json()["id"]
    assert c.get(f"/api/live/jobs/{jid}", headers=h).json()["id"] == jid and len(c.get("/api/live/jobs", headers=h).json()["jobs"]) == 1
    assert c.get(f"/api/live/jobs/{jid}/export", headers=h).status_code == 409, "no run yet: nothing to replay"
    assert c.post(f"/api/live/jobs/{jid}/cancel", headers=h).json()["state"] == "cancelled"
    assert c.post("/api/admin/kill", headers={"X-Admin-Token": "adm"}, json={"enabled": True}).status_code == 200
    assert c.post("/api/live/jobs", headers=h, json={"target_id": "ironbark", "goal": GOAL}).status_code == 503


@pytest.mark.browser
def test_a_real_mock_evaluation_runs_the_pipeline_and_is_replayable(tmp_path):
    """No fixtures: a worker subprocess runs inspect -> taskgen -> freeze -> browser trials -> trace -> investigator -> recommend -> report on Ironbark."""
    m = JobManager(tmp_path / "live")
    j = m.create("owner", "ironbark", GOAL)
    seen_running = False
    for _ in range(120):
        v = m.get(j["id"], "owner")
        seen_running |= v["state"] == "running" and 0 < v["progress"] < 1
        if v["state"] not in ("queued", "running"):
            break
        time.sleep(3)
    assert v["state"] == "completed", v.get("error")
    assert seen_running, "progress was observable while the job ran"
    assert v["progress"] == 1.0 and all(s["status"] == "done" for s in v["stages"]) and v["spend"]["committed_usd"] == 0
    assert len(v["trials"]) == 4 and any(e["kind"] == "trace" and "navigate" in e["text"] for e in v["events"]) and v["events"][-1]["text"].startswith("Evaluation completed")
    d = m.export(j["id"], "owner")
    assert d["schema"] == "investigation-dashboard-v1" and d["run"]["mode"] == "mock" and d["notices"][0].startswith("MOCK EVALUATION") and d["goal"] == GOAL
    assert d["investigation"]["mode"] == "scripted" and any(h["status"] == "supported" for h in d["hypotheses"]) and len(d["proposals"]) >= 1
    assert all("unvalidated" in p["validation"] for p in d["proposals"]) and json.dumps(d).count("sk-") == 0
    again = m.export(j["id"], "owner")                   # replay: reading the stored run again executes nothing and costs nothing
    assert again["run"]["id"] == d["run"]["id"]
    assert JobManager(m.root).get(j["id"], "owner")["state"] == "completed", "a restarted server shows the same finished job"
