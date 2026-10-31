"""Live evaluation M1: user-approved paid runs. Everything here is zero-spend: authorization logic is tested directly, and the end-to-end tests run the real live code path (preflight, spend gate, ledger,
approvals, HTTP, browser agent) against the LOOPBACK DEV PROVIDER, a fixture that is not a model. No test can reach a real endpoint: the base URL is always loopback."""
import json
import os
import socket
import subprocess
import threading
import time
from pathlib import Path

import pytest
import uvicorn

from agent_readiness.investigate.pipeline import Result
from agent_readiness.investigate.run import InvestigationRun
from agent_readiness.ledger import Halt
from agent_readiness.live import devprovider as D, grant as G, worker
from agent_readiness.live.jobs import JobError, JobManager, LiveSettings

GOAL = "Can an agent compare hire prices and availability?"
KEY = "dev-key-not-a-real-key-0123456789"
ENDPOINT = "http://127.0.0.1:9/v1"                         # nothing listens here: tests that reach it would fail loudly
SNAP = "d2824b210ed9e9d85dac527eb0b4eeb519540a70a7c59ff8690c204ff677538f"


def settings(**kw):
    base = dict(enabled=True, cap_usd=2.0, global_budget_usd=10.0, base_url=ENDPOINT)
    return LiveSettings(**{**base, **kw})


def grant(**kw):
    base = dict(job_id="live-aaaaaaaaaa", owner="sess-1", target_id="ironbark", goal=GOAL, budget_usd=2.0, model="muse-spark-1.3", endpoint=ENDPOINT, snapshot_sha256=SNAP)
    return G.make_grant(**{**base, **kw})


def live_run(tmp_path, job_id="live-aaaaaaaaaa"):
    from agent_readiness.investigate import flow
    return InvestigationRun.create(tmp_path, job_id, target="ironbark", mode="live", stages=flow.STAGES)


def manifest(stage="taskgen", **kw):
    m = {"stage": stage, "model": "muse-spark-1.3", "endpoint": ENDPOINT + "/chat/completions", "snapshot_sha256": SNAP, "run_cap_usd": 0.15, "worst_case_stage_usd": 0.1}
    if stage == "baseline_trials":
        m |= {"endpoint": ENDPOINT, "stage_cap_usd": 1.4, "ledger_ceiling_usd": 2.0, "allocation": {"ledger_ceiling_usd": 2.0}}
    return {**m, **kw}


def approver(tmp_path, **gk):
    g = grant(**gk)
    run = live_run(tmp_path)
    return G.Approver(g, job_id="live-aaaaaaaaaa", owner="sess-1", run_id="live-aaaaaaaaaa"), run


# ------------------------------------------------------------------------------------------------------------------------------------------------------------------ authorization
def test_a_grant_is_bound_to_job_owner_run_budget_and_scope_and_detects_tampering():
    g = grant()
    G.verify(g, job_id="live-aaaaaaaaaa", owner="sess-1", run_id="live-aaaaaaaaaa")
    for field, value in (("budget_usd", 99.0), ("goal", "something else"), ("stages", ["taskgen", "post_trials"]), ("model", "other"), ("endpoint", "https://evil.example/v1")):
        with pytest.raises(G.GrantRefused) as e:
            G.verify({**g, field: value}, job_id="live-aaaaaaaaaa", owner="sess-1", run_id="live-aaaaaaaaaa")
        assert e.value.kind in ("integrity", "scope"), field
    for ids in (dict(job_id="live-bbbbbbbbbb", owner="sess-1", run_id="live-aaaaaaaaaa"), dict(job_id="live-aaaaaaaaaa", owner="sess-2", run_id="live-aaaaaaaaaa"), dict(job_id="live-aaaaaaaaaa", owner="sess-1", run_id="live-bbbbbbbbbb")):
        with pytest.raises(G.GrantRefused):
            G.verify(g, **ids)
    with pytest.raises(G.GrantRefused):
        G.make_grant(job_id="j", owner="o", target_id="t", goal="g", budget_usd=0, model="m", endpoint="e", snapshot_sha256="s") and G.verify({**grant(budget_usd=0)}, job_id="live-aaaaaaaaaa", owner="sess-1", run_id="live-aaaaaaaaaa")


def test_the_approver_records_an_auditable_approval_only_for_in_scope_manifests(tmp_path):
    ap, run = approver(tmp_path)
    m = manifest()
    rec = ap.decide(run, "taskgen", run.manifest_sha256(m), m, 0.0)
    assert rec["stage"] == "taskgen" and "USER-GRANT approval" in rec["note"] and ap.grant["grant_sha256"][:16] in rec["note"] and "live-aaaaaaaaaa" in rec["note"]
    assert run.is_approved("taskgen", run.manifest_sha256(m)) and len(run.approvals()) == 1
    b = manifest("baseline_trials")
    ap.decide(run, "baseline_trials", run.manifest_sha256(b), b, 0.15)
    assert [a["stage"] for a in run.approvals()] == ["taskgen", "baseline_trials"]


@pytest.mark.parametrize("stage", ["apply_fix", "post_trials", "final_report", "anything-else"])
def test_stages_outside_the_users_scope_are_never_approved(tmp_path, stage):
    ap, run = approver(tmp_path)
    m = manifest(stage if stage in ("apply_fix", "post_trials") else "taskgen")
    m["stage"] = stage
    with pytest.raises(G.GrantRefused) as e:
        ap.decide(run, stage, run.manifest_sha256(m), m, 0.0)
    assert e.value.kind == "scope" and run.approvals() == []


@pytest.mark.parametrize("change,kind", [({"model": "a-more-expensive-model"}, "scope"), ({"endpoint": "https://other.example/v1/chat/completions"}, "scope"), ({"snapshot_sha256": "0" * 64}, "scope"),
                                         ({"run_cap_usd": 5.0}, "budget"), ({"worst_case_stage_usd": 2.5}, "budget")])
def test_a_manifest_that_differs_from_what_the_user_approved_is_refused(tmp_path, change, kind):
    ap, run = approver(tmp_path)
    m = manifest(**change)
    with pytest.raises(G.GrantRefused) as e:
        ap.decide(run, "taskgen", run.manifest_sha256(m), m, 0.0)
    assert e.value.kind == kind and run.approvals() == []


def test_the_approver_enforces_the_remaining_budget_and_the_manifest_hash(tmp_path):
    ap, run = approver(tmp_path, budget_usd=1.5)
    b = manifest("baseline_trials", stage_cap_usd=1.4, ledger_ceiling_usd=1.5, allocation={"ledger_ceiling_usd": 1.5})
    with pytest.raises(G.GrantRefused) as e:
        ap.decide(run, "baseline_trials", run.manifest_sha256(b), b, 0.2)               # 0.2 already committed + 1.4 > 1.5
    assert e.value.kind == "budget"
    ap.decide(run, "baseline_trials", run.manifest_sha256(b), b, 0.1)                   # 0.1 + 1.4 fits
    with pytest.raises(G.GrantRefused) as e:
        ap.decide(run, "taskgen", "0" * 64, manifest(), 0.0)
    assert e.value.kind == "integrity"


def test_a_grant_cannot_approve_another_run_or_a_mock_run_or_be_reused_with_a_different_owner(tmp_path):
    g = grant()
    other = live_run(tmp_path, "live-bbbbbbbbbb")
    ap = G.Approver(g, job_id="live-aaaaaaaaaa", owner="sess-1", run_id="live-aaaaaaaaaa")
    m = manifest()
    with pytest.raises(G.GrantRefused) as e:
        ap.decide(other, "taskgen", other.manifest_sha256(m), m, 0.0)
    assert "not the run the grant was issued for" in e.value.reason and other.approvals() == []
    from agent_readiness.investigate import flow
    mock = InvestigationRun.create(tmp_path, "live-aaaaaaaaaa-mock", target="ironbark", mode="mock", stages=flow.STAGES)
    with pytest.raises(G.GrantRefused):
        ap.decide(mock, "taskgen", mock.manifest_sha256(m), m, 0.0)
    with pytest.raises(G.GrantRefused):
        G.Approver(g, job_id="live-aaaaaaaaaa", owner="someone-else", run_id="live-aaaaaaaaaa")


# ------------------------------------------------------------------------------------------------------------------------------------------------------------------ server policy and keys
def manager(tmp_path, live=None, spawn=None):
    spawned = []
    m = JobManager(tmp_path / "live", spawn=spawn or (lambda jid: spawned.append(jid) or 0), live=live or settings())
    return m, spawned


def test_a_live_job_needs_server_enablement_a_key_the_exact_confirmation_ironbark_and_budget(tmp_path, monkeypatch):
    monkeypatch.delenv("META_MODEL_API_KEY", raising=False)
    m, _ = manager(tmp_path)
    with pytest.raises(JobError) as e:
        m.create("o", "ironbark", GOAL, "live", 2.0)
    assert e.value.status == 409 and "not enabled" in e.value.message, "no key on the server: refused"
    monkeypatch.setenv("META_MODEL_API_KEY", KEY)
    m, spawned = manager(tmp_path / "a")
    for bad in (None, 0.0, 1.0, 2.01, 20.0):
        with pytest.raises(JobError) as e:
            m.create("o", "ironbark", GOAL, "live", bad)
        assert e.value.status == 409 and "confirmation" in e.value.message, bad
    with pytest.raises(JobError) as e:
        m.create("o", "site-4", GOAL, "live", 2.0)
    assert e.value.status == 422 and spawned == [], "live is Ironbark-only"
    off, _ = manager(tmp_path / "b", live=settings(enabled=False))
    with pytest.raises(JobError):
        off.create("o", "ironbark", GOAL, "live", 2.0)
    j = m.create("o", "ironbark", GOAL, "live", 2.0)
    assert j["mode"] == "live" and not j["mock"] and j["grant"]["budget_usd"] == 2.0 and j["spend"]["hard_cap_usd"] == 2.0 and spawned == [j["id"]]
    raw = worker.read(m.root, j["id"])
    assert raw["grant"]["owner"] == "o" and raw["grant"]["job_id"] == j["id"] == raw["grant"]["run_id"] and raw["grant"]["stages"] == list(G.LIVE_STAGES)
    G.verify(raw["grant"], job_id=j["id"], owner="o", run_id=j["id"])


def test_the_server_cap_is_the_grant_and_the_global_budget_counts_promises_and_actual_spend(tmp_path, monkeypatch):
    monkeypatch.setenv("META_MODEL_API_KEY", KEY)
    m, _ = manager(tmp_path, live=settings(cap_usd=2.0, global_budget_usd=3.0))
    first = m.create("o", "ironbark", GOAL, "live", 2.0)
    assert first["grant"]["budget_usd"] == 2.0
    with pytest.raises(JobError):
        m.create("o", "ironbark", GOAL, "live", 2.0)                # one at a time
    worker.update(m.root, first["id"], state="completed", finished_at=time.time())
    InvestigationRun.create(m.root, first["id"], target="ironbark", mode="live", stages=("inspect",)).ledger(2.0).reserve("x", 1.5)
    with pytest.raises(JobError) as e:
        m.create("o", "ironbark", GOAL, "live", 2.0)                # 1.5 actually committed + 2.0 promised > 3.0
    assert e.value.status == 409 and "budget" in e.value.message
    roomy, _ = manager(tmp_path / "r", live=settings(cap_usd=2.0, global_budget_usd=3.6))
    one = roomy.create("o", "ironbark", GOAL, "live", 2.0)
    worker.update(roomy.root, one["id"], state="completed", finished_at=time.time())
    InvestigationRun.create(roomy.root, one["id"], target="ironbark", mode="live", stages=("inspect",)).ledger(2.0).reserve("x", 1.5)
    assert roomy.create("o", "ironbark", GOAL, "live", 2.0)["state"] == "queued"       # 1.5 + 2.0 <= 3.6: what a finished job did not spend is released


def test_the_model_key_reaches_only_a_live_worker_and_never_argv_files_views_or_responses(tmp_path, monkeypatch):
    monkeypatch.setenv("META_MODEL_API_KEY", KEY)
    monkeypatch.setenv("SCANNER_ADMIN_TOKEN", "adm")
    seen = []

    def fake(cmd, **kw):
        seen.append((cmd, kw["env"]))
        class P:
            pid = 0
            def wait(self): return 0
        return P()
    monkeypatch.setattr(subprocess, "Popen", fake)
    m = JobManager(tmp_path / "live", live=settings())
    mock = m.create("o", "ironbark", GOAL)
    m.cancel(mock["id"], "o")
    live = m.create("o", "ironbark", GOAL, "live", 2.0)
    (mcmd, menv), (lcmd, lenv) = seen
    assert "META_MODEL_API_KEY" not in menv and "SCANNER_ADMIN_TOKEN" not in menv, "a mock worker holds no credential"
    assert lenv["META_MODEL_API_KEY"] == KEY and "SCANNER_ADMIN_TOKEN" not in lenv, "a live worker gets exactly the model key and no other secret"
    assert KEY not in " ".join(lcmd) and KEY not in " ".join(mcmd), "never on a command line"
    for text in (json.dumps(live), json.dumps(m.get(live["id"], "o")), (m.root / f"{live['id']}.job.json").read_text(), json.dumps(m.list("o"))):
        assert KEY not in text


def test_the_api_exposes_the_confirmation_contract_and_never_the_key(tmp_path, monkeypatch):
    monkeypatch.setenv("META_MODEL_API_KEY", KEY)
    from fastapi.testclient import TestClient
    from agent_readiness.scanner.service import api as api_mod
    from agent_readiness.scanner.service.config import ScannerConfig
    cfg = ScannerConfig(data_dir=tmp_path, secret="s", rate_limit_per_minute=1000, live_enabled=True, live_budget_usd=10.0, live_model_base_url=ENDPOINT)
    app = api_mod.create_scanner_app(cfg, live_jobs=JobManager(tmp_path / "live", spawn=lambda jid: 0, live=LiveSettings.from_config(cfg)))
    c = TestClient(app)
    _, code = app.state.store.create_invitation("t", 1, 1, 5)
    h = {"Authorization": "Bearer " + c.post("/api/session", json={"code": code}).json()["token"]}
    t = c.get("/api/live/targets", headers=h).json()
    assert t["modes"]["live"] is True and t["live"]["cap_usd"] == 2.0 and t["live"]["targets"] == ["ironbark"] and t["live"]["dev_provider"] is True and KEY not in json.dumps(t)
    assert c.post("/api/live/jobs", headers=h, json={"target_id": "ironbark", "goal": GOAL, "mode": "live"}).status_code == 409
    assert c.post("/api/live/jobs", headers=h, json={"target_id": "ironbark", "goal": GOAL, "mode": "live", "confirm_budget_usd": 2.0, "budget_usd": 50}).status_code == 422, "the client cannot name a budget"
    r = c.post("/api/live/jobs", headers=h, json={"target_id": "ironbark", "goal": GOAL, "mode": "live", "confirm_budget_usd": 2.0})
    assert r.status_code == 202 and r.json()["grant"]["budget_usd"] == 2.0 and KEY not in r.text


# ------------------------------------------------------------------------------------------------------------------------------------------------------------------ worker gate handling (stubbed pipeline)
class StubPipe:
    def __init__(self, results):
        self.results = list(results)
        self.calls = 0

    def run(self, ctx, until=None):
        self.calls += 1
        return self.results.pop(0)


def drive(tmp_path, monkeypatch, results, *, manifests=None, budget=2.0):
    m, _ = manager(tmp_path, live=settings(cap_usd=budget))
    monkeypatch.setenv("META_MODEL_API_KEY", KEY)
    j = m.create("o", "ironbark", GOAL, "live", budget)
    from agent_readiness.investigate import flow
    pipe = StubPipe(results)

    def build(root, job_id, site, *, mode, options):
        assert mode == "live" and options["total_cap_usd"] == budget and options["allow_model_calls"] is True and options["rule_topup"] is False
        assert options["goals"] == {"focus": GOAL}, "the user's goal is what steers task generation"
        run = InvestigationRun.create(root, job_id, target=site, mode="live", stages=flow.STAGES)
        for stage, man in (manifests or {}).items():
            run.write_artifact(f"manifests/{stage}-{run.manifest_sha256(man)[:16]}", man)
        return run, pipe, type("C", (), {"options": options})()
    monkeypatch.setattr(flow, "build", build)
    return m, j, pipe


def test_a_gate_outside_the_grant_leaves_the_job_awaiting_approval_not_failed_and_spends_nothing(tmp_path, monkeypatch):
    man = manifest("apply_fix", endpoint=ENDPOINT)
    h = InvestigationRun.manifest_sha256(man)
    m, j, pipe = drive(tmp_path, monkeypatch, [Result("awaiting_approval", "apply_fix", h)], manifests={"apply_fix": man})
    _run_worker_with_snapshot(m, j, monkeypatch)
    got = worker.read(m.root, j["id"])
    assert got["state"] == "awaiting_approval" and got["stop"]["stage"] == "apply_fix" and got["stop"]["kind"] == "scope" and "Nothing further was spent" in got["error"]
    assert pipe.calls == 1 and InvestigationRun(m.root / j["id"]).approvals() == []
    v = m.get(j["id"], "o")
    assert v["state"] == "awaiting_approval" and v["stop"]["reason"] and not any(e["kind"] == "approval" for e in v["events"])
    assert m.create("o", "ironbark", GOAL, "live", 2.0)["state"] == "queued", "an awaiting_approval job does not hold the slot"


def _run_worker_with_snapshot(m, j, monkeypatch):
    from agent_readiness.live import targets
    sha = worker.read(m.root, j["id"])["grant"]["snapshot_sha256"]
    t = targets.TARGETS["ironbark"]
    monkeypatch.setattr(targets, "TARGETS", {**targets.TARGETS, "ironbark": targets.DemoTarget(t.id, t.label, t.description, lambda: type("S", (), {"sha256": sha})())})
    worker.execute_live(m.root, j["id"], worker.read(m.root, j["id"]))


def test_an_in_scope_gate_is_approved_once_and_the_run_proceeds_to_completion(tmp_path, monkeypatch):
    man = manifest("taskgen", endpoint=ENDPOINT)
    h = InvestigationRun.manifest_sha256(man)
    m, j, pipe = drive(tmp_path, monkeypatch, [Result("awaiting_approval", "taskgen", h), Result("done")], manifests={"taskgen": man})
    _run_worker_with_snapshot(m, j, monkeypatch)
    got = worker.read(m.root, j["id"])
    assert got["state"] == "completed" and pipe.calls == 2
    run = InvestigationRun(m.root / j["id"])
    assert [a["stage"] for a in run.approvals()] == ["taskgen"] and run.artifact("live-grant")["grant_sha256"] == got["grant"]["grant_sha256"]
    assert any(e["kind"] == "approval" for e in m.get(j["id"], "o")["events"]), "approvals are visible in the trace"


def test_a_cap_above_the_users_budget_stops_the_run_safely_before_the_stage(tmp_path, monkeypatch):
    man = manifest("baseline_trials", ledger_ceiling_usd=5.0, allocation={"ledger_ceiling_usd": 5.0})
    h = InvestigationRun.manifest_sha256(man)
    m, j, pipe = drive(tmp_path, monkeypatch, [Result("awaiting_approval", "baseline_trials", h)], manifests={"baseline_trials": man})
    _run_worker_with_snapshot(m, j, monkeypatch)
    got = worker.read(m.root, j["id"])
    assert got["state"] == "awaiting_approval" and got["stop"]["kind"] == "budget" and "exceeds the approved budget" in got["stop"]["reason"]


def test_a_budget_halt_inside_a_stage_is_reported_as_a_safe_stop_not_a_crash(tmp_path, monkeypatch):
    m, j, pipe = drive(tmp_path, monkeypatch, [Result("failed", "baseline_trials", error="Halt: budget ceiling US$2.00 would be exceeded (committed US$1.9 + reservation US$0.2)")])
    _run_worker_with_snapshot(m, j, monkeypatch)
    got = worker.read(m.root, j["id"])
    assert got["state"] == "stopped" and got["stop"]["kind"] == "budget" and got["stop"]["stage"] == "baseline_trials"


def test_an_ordinary_stage_failure_is_a_failure_and_a_pipeline_that_keeps_asking_is_stopped(tmp_path, monkeypatch):
    m, j, pipe = drive(tmp_path, monkeypatch, [Result("failed", "taskgen", error="ValueError: only 0 acceptable tasks (need 4)")])
    _run_worker_with_snapshot(m, j, monkeypatch)
    assert worker.read(m.root, j["id"])["state"] == "failed"
    man = manifest("taskgen", endpoint=ENDPOINT)
    h = InvestigationRun.manifest_sha256(man)
    m2, j2, pipe2 = drive(tmp_path / "x", monkeypatch, [Result("awaiting_approval", "taskgen", h)] * 10, manifests={"taskgen": man})
    _run_worker_with_snapshot(m2, j2, monkeypatch)
    assert worker.read(m2.root, j2["id"])["state"] in ("failed", "awaiting_approval") and pipe2.calls <= len(G.LIVE_STAGES) + 2


def test_a_changed_site_capture_or_goal_stops_the_job_before_the_pipeline_is_built(tmp_path, monkeypatch):
    m, j, pipe = drive(tmp_path, monkeypatch, [Result("done")])
    from agent_readiness.live import targets
    t = targets.TARGETS["ironbark"]
    monkeypatch.setattr(targets, "TARGETS", {**targets.TARGETS, "ironbark": targets.DemoTarget(t.id, t.label, t.description, lambda: type("S", (), {"sha256": "f" * 64})())})
    worker.execute_live(m.root, j["id"], worker.read(m.root, j["id"]))
    got = worker.read(m.root, j["id"])
    assert got["state"] == "stopped" and "no longer matches the grant" in got["error"] and pipe.calls == 0


# ------------------------------------------------------------------------------------------------------------------------------------------------------------------ end to end against the dev provider
@pytest.fixture
def provider(tmp_path):
    started = []

    def start(usage_scale=1.0):
        prov = D.DevProvider(tmp_path / "live", usage_scale)
        s = socket.create_server(("127.0.0.1", 0))
        srv = uvicorn.Server(uvicorn.Config(D.make_app(prov), log_level="error", lifespan="off"))
        threading.Thread(target=lambda: srv.run(sockets=[s]), daemon=True).start()
        started.append(srv)
        return prov, f"http://127.0.0.1:{s.getsockname()[1]}/v1"
    yield start
    for srv in started:
        srv.should_exit = True


def wait_for(fn, seconds=420, step=2):
    t0 = time.time()
    while time.time() - t0 < seconds:
        v = fn()
        if v:
            return v
        time.sleep(step)
    raise AssertionError("timed out")


@pytest.mark.browser
def test_a_live_job_runs_end_to_end_through_the_real_live_path_within_its_grant(tmp_path, monkeypatch, provider):
    monkeypatch.setenv("META_MODEL_API_KEY", KEY)
    prov, url = provider()
    m = JobManager(tmp_path / "live", live=settings(base_url=url))
    j = m.create("o", "ironbark", GOAL, "live", 2.0)
    v = wait_for(lambda: (lambda x: x if x["state"] not in ("queued", "running") else None)(m.get(j["id"], "o")))
    assert v["state"] == "completed", (v["error"], v["stop"])
    assert v["dev_provider"] and "DEV PROVIDER" in v["notice"] and not v["mock"] and v["mode"] == "live"
    run = InvestigationRun(m.root / j["id"])
    assert run.mode == "live" and [a["stage"] for a in run.approvals()] == ["taskgen", "baseline_trials", "investigate"], "exactly the three paid stages were approved, nothing else"
    assert all(a["note"].startswith("USER-GRANT approval") and v["grant"]["grant_sha256"] in a["note"] for a in run.approvals())
    sp = v["spend"]
    assert 0 < sp["committed_usd"] <= sp["hard_cap_usd"] == 2.0 and set(sp["stages"]) == {"taskgen", "baseline_trials", "investigate"} and all(x > 0 for x in sp["stages"].values())
    assert abs(sum(sp["stages"].values()) - sp["committed_usd"]) < 1e-6
    assert prov.calls["taskgen"] >= 1 and prov.calls["agent"] > 0 and prov.calls["investigator"] > 0
    assert prov.taskgen_prompts and all(GOAL in p for p in prov.taskgen_prompts), "the user's goal is in every task-generation request"
    assert json.loads((m.root / j["id"] / "artifacts" / "taskgen-report.json").read_text())["rule_topup"] == 0, "no benchmark/rule tasks were substituted"
    assert prov.keys_seen == {f"Bearer {KEY}"}, "the key was presented to the endpoint, from the live worker only"
    assert len(v["trials"]) >= 4 and any(e["kind"] == "approval" for e in v["events"]) and any(e["kind"] == "trace" for e in v["events"])
    d = m.export(j["id"], "o")
    assert d["run"]["mode"] == "live" and d["notices"][0].startswith("DEV PROVIDER") and d["goal"] == GOAL
    assert all(t["source"] == "model" for t in d["tasks"]), "tasks came from the (stand-in) model through the independent gate, not from the rule top-up"
    assert {p["basis"] for p in d["proposals"]} <= {"verified_finding", "unverified_hypothesis"} and all(h["tier"] in ("verifiable", "novel") for h in d["hypotheses"])
    assert d["spend"]["committed_usd"] == sp["committed_usd"]
    blob = "".join(p.read_text(errors="ignore") for p in (m.root).rglob("*") if p.is_file() and p.suffix in (".json", ".jsonl", ".log"))
    assert KEY not in blob, "the key is nowhere in the run directory, the job record or the log"
    assert m.export(j["id"], "o")["run"]["id"] == d["run"]["id"], "replay re-reads the stored run; no worker, no request"
    calls = dict(prov.calls)
    m.export(j["id"], "o")
    assert prov.calls == calls


@pytest.mark.browser
def test_a_provider_that_bills_more_than_reserved_stops_the_run_at_the_first_request(tmp_path, monkeypatch, provider):
    monkeypatch.setenv("META_MODEL_API_KEY", KEY)
    prov, url = provider(usage_scale=4000.0)
    m = JobManager(tmp_path / "live", live=settings(base_url=url))
    j = m.create("o", "ironbark", GOAL, "live", 2.0)
    v = wait_for(lambda: (lambda x: x if x["state"] not in ("queued", "running") else None)(m.get(j["id"], "o")))
    assert v["state"] == "stopped" and v["stop"]["kind"] == "budget" and v["stop"]["stage"] == "taskgen", v
    assert prov.calls["taskgen"] == 1 and prov.calls["agent"] == 0 and prov.calls["investigator"] == 0, "no request was sent after the bound violation"
    assert [s["status"] for s in v["stages"] if s["name"] in ("baseline_trials", "investigate")] == ["pending", "pending"]


@pytest.mark.browser
def test_a_budget_below_the_stage_caps_stops_before_any_paid_trial(tmp_path, monkeypatch, provider):
    monkeypatch.setenv("META_MODEL_API_KEY", KEY)
    prov, url = provider()
    m = JobManager(tmp_path / "live", live=settings(base_url=url, cap_usd=0.5))
    j = m.create("o", "ironbark", GOAL, "live", 0.5)
    v = wait_for(lambda: (lambda x: x if x["state"] not in ("queued", "running") else None)(m.get(j["id"], "o")))
    assert v["state"] == "awaiting_approval" and v["stop"]["kind"] == "budget" and v["stop"]["stage"] in ("taskgen", "baseline_trials")
    assert prov.calls["agent"] == 0 and v["spend"]["committed_usd"] <= 0.5


@pytest.mark.browser
def test_cancelling_a_running_live_job_stops_the_worker_and_its_browser_and_keeps_the_ledger(tmp_path, monkeypatch, provider):
    monkeypatch.setenv("META_MODEL_API_KEY", KEY)
    prov, url = provider()
    m = JobManager(tmp_path / "live", live=settings(base_url=url))
    j = m.create("o", "ironbark", GOAL, "live", 2.0)
    wait_for(lambda: m.get(j["id"], "o")["spend"]["committed_usd"] > 0 and prov.calls["agent"] > 0, 300, 1)
    pid = worker.read(m.root, j["id"])["pid"]
    assert KEY in open(f"/proc/{pid}/environ", "rb").read().decode(errors="replace"), "only the live worker holds the key"
    assert m.cancel(j["id"], "o")["state"] == "cancelled"

    def gone():
        try:
            os.killpg(pid, 0)
            return False
        except ProcessLookupError:
            return True
    wait_for(gone, 30, 0.5)
    seen = dict(prov.calls)
    time.sleep(3)
    assert prov.calls == seen, "no further model requests after cancel"
    v = m.get(j["id"], "o")
    assert v["state"] == "cancelled" and v["spend"]["committed_usd"] > 0, "what was reserved before the cancel stays counted"
    assert m.create("o", "ironbark", GOAL)["state"] == "queued"
    m.cancel_all()
