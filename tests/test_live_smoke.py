"""Taskgen-only smoke mode: stop boundary, cost controls, report, operator CLI. Zero-spend: stubs, fixtures and the loopback dev provider only; nothing here can reach a real endpoint."""
import dataclasses
import json
import time
from types import SimpleNamespace

import pytest

from agent_readiness.investigate.pipeline import Result
from agent_readiness.investigate.run import InvestigationRun
from agent_readiness.live import cli as live_cli, grant as G, smoke, worker
from agent_readiness.live.jobs import JobError, JobManager, LiveSettings

from .test_live_m1 import ENDPOINT, GOAL, KEY, StubPipe, _run_worker_with_snapshot, approver, live_run, manifest, provider, settings, wait_for  # noqa: F401

SMOKE = dict(smoke_until="taskgen")


def smoke_settings(**kw):
    return settings(**{**SMOKE, **kw})


def test_a_smoke_grant_covers_task_generation_only_with_the_taskgen_allocation_and_no_retries(tmp_path):
    g = G.make_grant(job_id="live-aaaaaaaaaa", owner="o", target_id="ironbark", goal=GOAL, budget_usd=G.SMOKE_CAP_USD, model="muse-spark-1.3", endpoint=ENDPOINT, snapshot_sha256="s" * 64,
                     stages=G.SMOKE_STAGES, limits=G.default_limits(smoke=True))
    assert g["stages"] == ["taskgen"] and g["budget_usd"] == 0.15 and g["limits"]["stage_caps_usd"] == {"taskgen": 0.15} and g["limits"]["max_retries_per_request"] == 0 and g["limits"]["per_request_cap_usd"] == 0.05
    run = live_run(tmp_path)
    ap = G.Approver({**g, "job_id": "live-aaaaaaaaaa", "run_id": "live-aaaaaaaaaa"} | {"grant_sha256": G.digest({**g, "job_id": "live-aaaaaaaaaa", "run_id": "live-aaaaaaaaaa", "owner": "o"})}, job_id="live-aaaaaaaaaa", owner="o", run_id="live-aaaaaaaaaa") \
        if False else None
    g = G.make_grant(job_id="live-aaaaaaaaaa", owner="sess-1", target_id="ironbark", goal=GOAL, budget_usd=0.15, model="muse-spark-1.3", endpoint=ENDPOINT, snapshot_sha256="d2824b210ed9e9d85dac527eb0b4eeb519540a70a7c59ff8690c204ff677538f",
                     stages=G.SMOKE_STAGES, limits=G.default_limits(smoke=True))
    ap = G.Approver(g, job_id="live-aaaaaaaaaa", owner="sess-1", run_id="live-aaaaaaaaaa")
    tg = manifest("taskgen", retries_per_request=0, target_tasks=4)
    ap.decide(run, "taskgen", run.manifest_sha256(tg), tg, 0.0)
    for stage in ("baseline_trials", "investigate", "apply_fix", "post_trials"):
        m = manifest("baseline_trials" if stage == "baseline_trials" else "taskgen")
        m["stage"] = stage
        with pytest.raises(G.GrantRefused) as e:
            ap.decide(run, stage, run.manifest_sha256(m), m, 0.0)
        assert e.value.kind == "scope", stage
    run2 = live_run(tmp_path / "b")
    for change, kind in (({"run_cap_usd": 0.2}, "budget"), ({"retries_per_request": 1}, "scope"), ({"per_request_cap_usd": 0.1}, "budget")):
        bad = {**tg, **change}
        with pytest.raises(G.GrantRefused) as e:
            ap.decide(run2, "taskgen", run2.manifest_sha256(bad), bad, 0.0)
        assert e.value.kind == kind and run2.approvals() == []


def test_smoke_mode_makes_every_live_job_a_015_taskgen_only_job(tmp_path, monkeypatch):
    monkeypatch.setenv("META_MODEL_API_KEY", KEY)
    m = JobManager(tmp_path / "live", spawn=lambda jid: 0, live=smoke_settings(cap_usd=2.0))
    for bad in (2.0, 0.5, None):
        with pytest.raises(JobError) as e:
            m.create("o", "ironbark", GOAL, "live", bad)
        assert e.value.status == 409 and "0.15" in e.value.message
    j = m.create("o", "ironbark", GOAL, "live", 0.15)
    raw = worker.read(m.root, j["id"])
    assert raw["until"] == "taskgen" and raw["grant"]["stages"] == ["taskgen"] and raw["grant"]["budget_usd"] == 0.15 and raw["timeout_seconds"] == 600
    assert j["spend"]["hard_cap_usd"] == 0.15 and j["until"] == "taskgen"
    normal = JobManager(tmp_path / "n", spawn=lambda jid: 0, live=settings())
    assert normal.create("o", "ironbark", GOAL, "live", 2.0)["until"] is None


def test_the_ui_contract_advertises_the_smoke_cap(tmp_path, monkeypatch):
    monkeypatch.setenv("META_MODEL_API_KEY", KEY)
    from fastapi.testclient import TestClient
    from agent_readiness.scanner.service import api as api_mod
    from agent_readiness.scanner.service.config import ScannerConfig
    cfg = ScannerConfig(data_dir=tmp_path, secret="s", rate_limit_per_minute=1000, live_enabled=True, live_budget_usd=1.0, live_model_base_url=ENDPOINT, live_allow_dev_provider=True, live_smoke_until="taskgen")
    app = api_mod.create_scanner_app(cfg, live_jobs=JobManager(tmp_path / "live", spawn=lambda jid: 0, live=LiveSettings.from_config(cfg)))
    c = TestClient(app)
    _, code = app.state.store.create_invitation("t", 1, 1, 5)
    h = {"Authorization": "Bearer " + c.post("/api/session", json={"code": code}).json()["token"]}
    t = c.get("/api/live/targets", headers=h).json()
    assert t["live"]["cap_usd"] == 0.15 and t["live"]["smoke"] == "taskgen"


# ------------------------------------------------------------------------------------------------------------------------------------------------------------------ the stop boundary
class Recording(StubPipe):
    def __init__(self, results):
        super().__init__(results)
        self.untils = []

    def run(self, ctx, until=None):
        self.untils.append(until)
        return super().run(ctx, until)


def drive_smoke(tmp_path, monkeypatch, results, manifests=None):
    monkeypatch.setenv("META_MODEL_API_KEY", KEY)
    m = JobManager(tmp_path / "live", spawn=lambda jid: 0, live=smoke_settings())
    j = m.create("o", "ironbark", GOAL, "live", 0.15)
    from agent_readiness.investigate import flow
    pipe = Recording(results)

    def build(root, job_id, site, *, mode, options):
        assert options["total_cap_usd"] == 0.15 and options["rule_topup"] is False and options["goals"] == {"focus": GOAL}
        run = InvestigationRun.create(root, job_id, target=site, mode="live", stages=flow.STAGES)
        for stage, man in (manifests or {}).items():
            run.write_artifact(f"manifests/{stage}-{run.manifest_sha256(man)[:16]}", man)
        return run, pipe, SimpleNamespace(options=options)
    monkeypatch.setattr(flow, "build", build)
    return m, j, pipe


def test_the_worker_runs_the_pipeline_only_until_freeze_and_approves_taskgen_alone(tmp_path, monkeypatch):
    man = manifest("taskgen", endpoint=ENDPOINT, retries_per_request=0, target_tasks=4)
    h = InvestigationRun.manifest_sha256(man)
    m, j, pipe = drive_smoke(tmp_path, monkeypatch, [Result("awaiting_approval", "taskgen", h), Result("done")], {"taskgen": man})
    _run_worker_with_snapshot(m, j, monkeypatch)
    got = worker.read(m.root, j["id"])
    assert got["state"] == "completed" and pipe.untils == ["freeze", "freeze"], "the pipeline is never asked to go past freeze"
    run = InvestigationRun(m.root / j["id"])
    assert [a["stage"] for a in run.approvals()] == ["taskgen"] and run.has_artifact("smoke-report")


def test_a_pipeline_that_asks_for_a_trial_in_a_smoke_job_is_refused_before_anything_is_approved(tmp_path, monkeypatch):
    man = manifest("baseline_trials", ledger_ceiling_usd=0.15, allocation={"ledger_ceiling_usd": 0.15})
    h = InvestigationRun.manifest_sha256(man)
    m, j, pipe = drive_smoke(tmp_path, monkeypatch, [Result("awaiting_approval", "baseline_trials", h)], {"baseline_trials": man})
    _run_worker_with_snapshot(m, j, monkeypatch)
    got = worker.read(m.root, j["id"])
    assert got["state"] == "awaiting_approval" and got["stop"]["kind"] == "scope" and got["stop"]["stage"] == "baseline_trials"
    assert InvestigationRun(m.root / j["id"]).approvals() == []


def test_a_smoke_job_whose_grant_covers_more_than_task_generation_does_not_start(tmp_path, monkeypatch):
    m, j, pipe = drive_smoke(tmp_path, monkeypatch, [Result("done")])
    raw = worker.read(m.root, j["id"])
    broad = G.make_grant(job_id=j["id"], owner="o", target_id="ironbark", goal=GOAL, budget_usd=0.15, model=raw["grant"]["model"], endpoint=raw["grant"]["endpoint"], snapshot_sha256=raw["grant"]["snapshot_sha256"])
    worker.update(m.root, j["id"], grant=broad)
    _run_worker_with_snapshot(m, j, monkeypatch)
    got = worker.read(m.root, j["id"])
    assert got["state"] == "stopped" and "task generation only" in got["error"] and pipe.untils == []


# ------------------------------------------------------------------------------------------------------------------------------------------------------------------ the report
def fake_run(tmp_path, accepted, rejected, calls, ledger):
    from agent_readiness.investigate import flow
    run = InvestigationRun.create(tmp_path, "live-aaaaaaaaaa", target="ironbark", mode="live", stages=flow.STAGES)
    run.write_artifact("taskgen-report", {"accepted": accepted, "rejected": rejected, "model_calls": calls, "rule_topup": 0})
    led = run.ledger(0.15)
    for i, (r, s) in enumerate(ledger, 1):
        led.reserve(f"live-aaaaaaaaaa-taskgen:req{i:02d}", r)
        if s is not None:
            led.settle(f"live-aaaaaaaaaa-taskgen:req{i:02d}", s)
    return run


def test_the_report_states_yield_verification_relevance_cost_and_compatibility_without_any_truth(tmp_path):
    acc = [{"question": "What is the daily hire price of the petrol cut-off saw?", "source": "model", "kind": "page_fact", "fingerprint": "f1"},
           {"question": "Which item has the highest refundable deposit?", "source": "model", "kind": "extremum", "fingerprint": "f2"}]
    rej = [{"question": "q3", "source": "model", "reason": "answer visible on the start page: x"}, {"question": "q4", "source": "model", "reason": "criterion cites an unknown label: y"}]
    calls = [{"batch": 0, "status": "ok", "model": "muse-spark-1.3", "attempts": 1, "proposed": 3, "usage": {"prompt_tokens": 5000, "completion_tokens": 900}},
             {"batch": 1, "status": "invalid", "error": "schema", "diagnostics": {"kind": "schema_mismatch"}}, {"batch": 2, "status": "provider_error", "error": "http 429"}]
    run = fake_run(tmp_path, acc, rej, calls, [(0.0477, 0.012), (0.0477, 0.0477), (0.0477, None)])
    rep = smoke.build_report(run, {"id": "live-aaaaaaaaaa", "goal": "compare the hire price of cutting tools"}, cap_usd=0.15, state="stopped")
    assert rep["yield"]["tasks_accepted"] == 2 and rep["yield"]["meets_minimum"] is False and rep["yield"]["requests_made"] == 3 and rep["yield"]["batches_ok"] == 1 and rep["yield"]["rule_topup_tasks"] == 0
    assert rep["independent_verification"]["rejection_reasons"] == {"answer visible on the start page": 1, "criterion cites an unknown label": 1}
    assert rep["relevance_to_goal"]["tasks_sharing_a_goal_term"] == 1 and "lexical heuristic" in rep["relevance_to_goal"]["method"]
    assert rep["cost"]["calculated_usd"] == pytest.approx(0.012 + 0.0477 + 0.0477) and len(rep["cost"]["per_request"]) == 3 and len(rep["cost"]["unsettled_requests"]) == 1
    assert [c["status"] for c in rep["provider_compatibility"]] == ["ok", "invalid", "provider_error"] and rep["provider_compatibility"][0]["usage_has_prompt_and_completion_tokens"] is True
    assert rep["provider_compatibility"][1]["unusable_output"] == {"kind": "schema_mismatch"} and rep["provider_compatibility"][2]["error"] == "http 429"
    text = json.dumps(rep)
    for forbidden in ("criterion\":", "truth", "expected", "fingerprint", KEY):
        assert forbidden not in text, forbidden


def test_the_relevance_heuristic_is_lexical_and_says_so():
    r = smoke.relevance("Can a shopper compare the hire price and availability of cutting tools?", ["What is the deposit for the wet tile saw?", "What is the daily hire price of the cut-off saw?", "Which tool is free on 14 Nov?"])
    assert [bool(x["shared_goal_terms"]) for x in r["per_task"]] == [False, True, True] and r["tasks_sharing_a_goal_term"] == 2 and r["of"] == 3


# ------------------------------------------------------------------------------------------------------------------------------------------------------------------ the operator CLI
def args(**kw):
    return SimpleNamespace(**{**dict(live_command="smoke", goal=GOAL, plan=False, confirm_spend=None, wait=5), **kw})


def test_the_plan_is_offline_deterministic_and_states_the_request_and_cost_bounds(monkeypatch, capsys):
    monkeypatch.delenv("META_MODEL_API_KEY", raising=False)
    p1, p2 = live_cli.plan(GOAL), live_cli.plan(GOAL)
    assert p1 == p2 and p1["max_provider_requests"] == 3 and p1["retries_per_request"] == 0 and p1["run_cap_usd"] == 0.15 and p1["per_request_cap_usd"] == 0.05 and p1["grant_budget_usd"] == 0.15
    assert p1["worst_case_stage_usd"] <= 0.15 and sum(p1["per_request_reservation_usd"]) == pytest.approx(p1["worst_case_stage_usd"], abs=1e-5) and p1["endpoint"] == "https://api.meta.ai/v1/chat/completions"
    assert live_cli.plan("a completely different goal about accessories")["manifest_sha256"] != p1["manifest_sha256"], "the approval hash binds the goal"
    assert live_cli.main(args(plan=True)) == 0 and "manifest_sha256" in capsys.readouterr().out


def test_the_smoke_command_refuses_without_the_exact_confirmation_or_server_enablement(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("SCANNER_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("SCANNER_LIVE_ENABLED", raising=False)
    monkeypatch.setenv("META_MODEL_API_KEY", KEY)
    assert live_cli.main(args(confirm_spend=0.15)) == 2 and "not available" in capsys.readouterr().err, "not enabled on the server"
    monkeypatch.setenv("SCANNER_LIVE_ENABLED", "1")
    monkeypatch.setenv("SCANNER_LIVE_BUDGET_USD", "1")
    for bad in (None, 0.0, 2.0, 0.16):
        assert live_cli.main(args(confirm_spend=bad)) == 2, bad
    assert "--confirm-spend 0.15" in capsys.readouterr().err
    monkeypatch.delenv("META_MODEL_API_KEY")
    assert live_cli.main(args(confirm_spend=0.15)) == 2, "no key: refused before anything starts"


# ------------------------------------------------------------------------------------------------------------------------------------------------------------------ real path against the dev provider
@pytest.mark.browser
def test_a_smoke_job_makes_at_most_three_requests_and_stops_before_any_trial(tmp_path, monkeypatch, provider):
    monkeypatch.setenv("META_MODEL_API_KEY", KEY)
    prov, url = provider()
    m = JobManager(tmp_path / "live", live=smoke_settings(base_url=url))
    j = m.create("o", "ironbark", GOAL, "live", 0.15)
    v = wait_for(lambda: (lambda x: x if x["state"] not in ("queued", "running") else None)(m.get(j["id"], "o")), 240)
    assert v["state"] == "completed", (v["error"], v["stop"])
    assert prov.calls == {"taskgen": 3, "agent": 0, "investigator": 0}, "exactly the three task-generation requests; no browser, no investigator"
    run = InvestigationRun(m.root / j["id"])
    assert [a["stage"] for a in run.approvals()] == ["taskgen"] and not list((run.dir / "artifacts").glob("trials*")) and not run.has_artifact("investigation")
    assert {s["name"]: s["status"] for s in v["stages"]} == {"inspect": "done", "taskgen": "done", "freeze": "done", **{n: "pending" for n in ("baseline_trials", "trace", "investigate", "recommend", "report", "apply_fix", "post_trials", "evaluate", "final_report")}}
    sp = v["spend"]
    assert 0 < sp["committed_usd"] <= 0.15 == sp["hard_cap_usd"] and set(sp["stages"]) == {"taskgen", "baseline_trials", "investigate"} and sp["stages"]["baseline_trials"] == 0
    rep = v["smoke"]
    assert rep["yield"]["requests_made"] == 3 and rep["yield"]["meets_minimum"] and rep["yield"]["rule_topup_tasks"] == 0 and rep["yield"]["accepted_by_source"] == {"model": rep["yield"]["tasks_accepted"]}
    assert rep["cost"]["calculated_usd"] == pytest.approx(sp["committed_usd"]) and rep["cost"]["unsettled_requests"] == [] and all(c["usage_has_prompt_and_completion_tokens"] for c in rep["provider_compatibility"])
    rel = rep["relevance_to_goal"]
    assert rel["relevant_tasks"] >= 4 and rel["gate_accepted_tasks"] >= rel["relevant_tasks"] and rep["proposal_accounting"]["unaccounted"] == 0 and all(p["goal_relevant"] for p in rel["per_task"] if p["question"] in {a["question"] for a in rep["accepted_tasks"]})
    assert all(GOAL in p for p in prov.taskgen_prompts) and all("EVALUATION GOAL (binding)" in p for p in prov.taskgen_prompts)
    man = run.artifact([p.stem for p in (run.dir / "artifacts" / "manifests").glob("taskgen-*.json")][0].join(["manifests/", ""]))
    assert man["max_requests"] == 3 and man["run_cap_usd"] == 0.15 and man["retries_per_request"] == 0 and man["worst_case_stage_usd"] <= 0.15
    assert m.export(j["id"], "o")["run"]["complete"] is False, "a partial run exports as incomplete, never as a finished evaluation"


@pytest.mark.browser
def test_a_smoke_job_against_an_over_billing_provider_stops_after_the_first_request_and_still_reports(tmp_path, monkeypatch, provider):
    monkeypatch.setenv("META_MODEL_API_KEY", KEY)
    prov, url = provider(usage_scale=4000.0)
    m = JobManager(tmp_path / "live", live=smoke_settings(base_url=url))
    j = m.create("o", "ironbark", GOAL, "live", 0.15)
    v = wait_for(lambda: (lambda x: x if x["state"] not in ("queued", "running") else None)(m.get(j["id"], "o")), 240)
    assert v["state"] == "stopped" and v["stop"]["kind"] == "budget" and prov.calls["taskgen"] == 1 and prov.calls["agent"] == 0
    rep = v["smoke"]
    assert rep and rep["cost"]["calculated_usd"] > rep["cost"]["cap_usd"], "the report shows the overshoot the ledger recorded"


@pytest.mark.browser
def test_the_operator_command_runs_the_smoke_test_end_to_end_against_the_dev_provider(tmp_path, monkeypatch, provider, capsys):
    prov, url = provider()
    for k, v in {"SCANNER_DATA_DIR": str(tmp_path), "SCANNER_LIVE_ENABLED": "1", "SCANNER_LIVE_BUDGET_USD": "0.5", "LIVE_MODEL_BASE_URL": url, "LIVE_ALLOW_DEV_PROVIDER": "1", "META_MODEL_API_KEY": KEY}.items():
        monkeypatch.setenv(k, v)
    code = live_cli.main(args(confirm_spend=0.15, wait=240))
    out = capsys.readouterr()
    assert code == 0, out.err
    data = json.loads(out.out)
    assert data["job"]["state"] == "completed" and data["smoke"]["yield"]["meets_minimum"] and data["smoke"]["yield"]["requests_made"] == 3 and prov.calls["agent"] == 0
    assert KEY not in out.out and KEY not in out.err


# ------------------------------------------------------------------------------------------------------------------------------------------------------------------ a test can never reach the real endpoint
def test_a_test_process_can_never_start_a_live_job_against_the_real_endpoint_even_with_a_key_and_an_env_file(monkeypatch, tmp_path, capsys):
    """Regression for an incident: a CLI test with live enabled loaded the repository .env key and started a real worker against api.meta.ai. Now: .env is not read under pytest, job creation refuses a
    non-loopback endpoint, the worker refuses too, and this test fails loudly if anything is spawned."""
    import subprocess
    from agent_readiness import env as envmod
    from agent_readiness.live import worker as w
    spawned = []
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: spawned.append(a) or (_ for _ in ()).throw(AssertionError("a worker was spawned")))
    monkeypatch.setenv("SCANNER_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("SCANNER_LIVE_ENABLED", "1")
    monkeypatch.setenv("SCANNER_LIVE_BUDGET_USD", "1")
    monkeypatch.setenv("META_MODEL_API_KEY", KEY)
    monkeypatch.delenv("LIVE_MODEL_BASE_URL", raising=False)                      # the default is the REAL endpoint
    assert live_cli.main(args(confirm_spend=0.15)) == 2 and spawned == [] and "test process" in capsys.readouterr().err
    (tmp_path / ".env").write_text("META_MODEL_API_KEY=should-not-be-read\n")
    monkeypatch.delenv("META_MODEL_API_KEY")
    assert envmod.load_repo_env() is False and "META_MODEL_API_KEY" not in __import__("os").environ, "no implicit .env read under pytest"
    assert envmod.load_repo_env(tmp_path / ".env") is True                           # an explicit path still works (the env module's own tests)
    monkeypatch.delenv("META_MODEL_API_KEY")
    m = JobManager(tmp_path / "live2", spawn=lambda jid: 0, live=smoke_settings(base_url="https://api.meta.ai/v1", allow_dev_provider=False))
    monkeypatch.setenv("META_MODEL_API_KEY", KEY)
    with pytest.raises(JobError):
        m.create("o", "ironbark", GOAL, "live", 0.15)
    j = JobManager(tmp_path / "live3", spawn=lambda jid: 0, live=smoke_settings()).create("o", "ironbark", GOAL, "live", 0.15)
    raw = w.read(tmp_path / "live3", j["id"])
    w.update(tmp_path / "live3", j["id"], grant={**raw["grant"], "endpoint": "https://api.meta.ai/v1", "grant_sha256": G.digest({**raw["grant"], "endpoint": "https://api.meta.ai/v1"})})
    w.execute_live(tmp_path / "live3", j["id"], w.read(tmp_path / "live3", j["id"]))
    got = w.read(tmp_path / "live3", j["id"])
    assert got["state"] == "stopped" and "real model endpoint" in got["error"] and not (tmp_path / "live3" / j["id"]).exists(), "the worker itself refuses before building any run"


# ------------------------------------------------------------------------------------------------------------------------------------------------------------------ final readiness checks
def test_a_test_process_is_loopback_only_and_so_is_any_worker_it_spawns(tmp_path):
    import socket
    import subprocess
    import sys
    srv = socket.create_server(("127.0.0.1", 0))
    s = socket.create_connection(srv.getsockname(), timeout=2)                       # loopback works
    s.close(); srv.close()
    for target in (("8.8.8.8", 53), ("93.184.216.34", 443), ("api.meta.ai", 443)):
        with pytest.raises(OSError, match="netguard"):
            socket.create_connection(target, timeout=1)
        with pytest.raises(OSError, match="netguard"):
            socket.socket().connect_ex(target)
    code = "import socket,sys\ntry:\n    socket.create_connection(('8.8.8.8',53),timeout=1); print('REACHED')\nexcept OSError as e:\n    print('BLOCKED' if 'netguard' in str(e) else 'OTHER '+str(e))\n"
    out = subprocess.run([sys.executable, "-c", "import agent_readiness\n" + code], capture_output=True, text=True, env={**__import__("os").environ, "PYTEST_CURRENT_TEST": "x"}, timeout=30)
    assert out.stdout.strip() == "BLOCKED", out
    out = subprocess.run([sys.executable, "-c", "import agent_readiness\n" + code], capture_output=True, text=True, env={**{k: v for k, v in __import__("os").environ.items() if k != "PYTEST_CURRENT_TEST"}, "AR_BLOCK_NONLOOPBACK": "1"}, timeout=30)
    assert out.stdout.strip() == "BLOCKED", out


def test_no_production_key_is_in_the_environment_of_a_test_and_workers_neutralise_dotenv(tmp_path, monkeypatch):
    import os
    import subprocess
    import sys
    assert "META_MODEL_API_KEY" not in os.environ, "the autouse fixture removed whatever Browser Use loaded from the repository .env"
    (tmp_path / ".env").write_text("META_MODEL_API_KEY=from-a-dotenv-file\n")
    code = ("import os\nfrom agent_readiness.live import worker\nworker.neutralize_dotenv()\nimport dotenv\n"
            f"print(dotenv.load_dotenv({str(tmp_path / '.env')!r}), 'META_MODEL_API_KEY' in os.environ)\n")
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env={k: v for k, v in os.environ.items() if k != "META_MODEL_API_KEY"}, timeout=60)
    assert out.stdout.strip() == "False False", out
    from agent_readiness.env import REPO_ROOT
    if (REPO_ROOT / ".env").is_file():                                                  # only meaningful on a machine that has the operator's file
        probe = "import os\nfrom agent_readiness.live import worker\nworker.neutralize_dotenv()\nimport agent_readiness.agent as a\na.prepare_browser_environment()\nimport browser_use\nprint('META_MODEL_API_KEY' in os.environ)\n"
        out = subprocess.run([sys.executable, "-c", probe], capture_output=True, text=True, env={k: v for k, v in os.environ.items() if k != "META_MODEL_API_KEY"}, timeout=120)
        assert out.stdout.strip() == "False", "a worker that imports Browser Use must not pick up the operator's key"


def test_the_plan_hash_is_the_hash_of_the_manifest_the_worker_will_present(tmp_path, monkeypatch):
    """The approval hash printed by `--plan` must be what the worker's pipeline presents: build the worker's exact options (captured from execute_live) with the production model config and compare."""
    from agent_readiness.agent import ModelConfig
    from agent_readiness.investigate import flow
    captured = {}
    monkeypatch.setenv("META_MODEL_API_KEY", KEY)
    m = JobManager(tmp_path / "live", spawn=lambda jid: 0, live=smoke_settings(base_url="https://api.meta.ai/v1", allow_dev_provider=False))
    monkeypatch.setattr("agent_readiness.live.jobs.under_test_with_real_endpoint", lambda e: False)
    j = m.create("o", "ironbark", GOAL, "live", 0.15)
    real_build = flow.build

    def spy(root, job_id, site, *, mode, options):
        captured.update(options)
        raise RuntimeError("stop after capturing the options")
    monkeypatch.setattr(flow, "build", spy)
    monkeypatch.setattr("agent_readiness.live.worker.under_test_with_real_endpoint" if False else "agent_readiness.live.jobs.under_test_with_real_endpoint", lambda e: False)
    with pytest.raises(RuntimeError):
        worker.execute_live(m.root, j["id"], worker.read(m.root, j["id"]))
    monkeypatch.setattr(flow, "build", real_build)
    assert captured["model_config"] == ModelConfig() and captured["total_cap_usd"] == 0.15 and captured["rule_topup"] is False and captured["goals"] == {"focus": GOAL} and captured["n_tasks"] == 4
    run, pipe, ctx = flow.build(tmp_path / "plan", "p", "ironbark", mode="live", options=captured)
    assert pipe.run(ctx, until="inspect").status == "done"
    assert run.manifest_sha256(flow.taskgen_manifest(ctx)) == live_cli.plan(GOAL)["manifest_sha256"]


def test_after_a_failure_or_a_restart_a_smoke_job_cannot_reach_any_other_paid_stage(tmp_path, monkeypatch):
    """The REAL pipeline against a dead loopback port (nothing real is reachable): task generation fails, then the worker is re-run, then the record is reset to 'running' as after a crash, then the
    scope is widened in the job file. In none of these does a trial, an investigation or a further approval happen, and the ledger never grows beyond the three task-generation requests."""
    monkeypatch.setenv("META_MODEL_API_KEY", KEY)
    monkeypatch.setenv("AR_ALLOW_LOOPBACK_MODEL", "1")
    m = JobManager(tmp_path / "live", spawn=lambda jid: 0, live=smoke_settings())
    j = m.create("o", "ironbark", GOAL, "live", 0.15)
    job = worker.read(m.root, j["id"])
    worker.execute_live(m.root, j["id"], job)
    run = InvestigationRun(m.root / j["id"])
    state = lambda: {s: run.state["stages"][s]["status"] for s in run.state["stages"]}
    led = lambda: [e["id"] for e in run.ledger(0.15).entries()]
    first = led()
    assert worker.read(m.root, j["id"])["state"] in ("failed", "stopped") and state()["taskgen"] == "failed" and all(v == "pending" for k, v in state().items() if k not in ("inspect", "taskgen"))
    assert 1 <= len({i.split(":")[0] for i in first}) <= 1 and len([i for i in first if i.endswith(("req01", "req02", "req03"))]) <= 6 and all("-taskgen" in i for i in first)
    assert [a["stage"] for a in run.approvals()] == ["taskgen"] and run.has_artifact("smoke-report")
    # a plain re-run (a restart): the failed spending stage is not re-run, nothing is sent, nothing new is approved
    worker.execute_live(m.root, j["id"], worker.read(m.root, j["id"]))
    assert led() == first and [a["stage"] for a in InvestigationRun(m.root / j["id"]).approvals()] == ["taskgen"]
    # a crash left the record 'running': same result
    raw = worker.read(m.root, j["id"])
    (m.root / f"{j['id']}.job.json").write_text(json.dumps({**raw, "state": "running"}))
    worker.execute_live(m.root, j["id"], worker.read(m.root, j["id"]))
    assert led() == first and all(v == "pending" for k, v in {s: InvestigationRun(m.root / j["id"]).state["stages"][s]["status"] for s in run.state["stages"]}.items() if k not in ("inspect", "taskgen"))
    # the job file is edited to drop the smoke marker: the grant still covers taskgen only, so no other stage can be approved
    raw = worker.read(m.root, j["id"])
    raw.pop("until")
    (m.root / f"{j['id']}.job.json").write_text(json.dumps({**raw, "state": "running"}))
    worker.execute_live(m.root, j["id"], worker.read(m.root, j["id"]))
    assert led() == first and [a["stage"] for a in InvestigationRun(m.root / j["id"]).approvals()] == ["taskgen"]
    # ... and if the grant itself is replaced by a broad one, the worker refuses to start
    broad = G.make_grant(job_id=j["id"], owner="o", target_id="ironbark", goal=GOAL, budget_usd=0.15, model=raw["grant"]["model"], endpoint=raw["grant"]["endpoint"], snapshot_sha256=raw["grant"]["snapshot_sha256"])
    (m.root / f"{j['id']}.job.json").write_text(json.dumps({**raw, "grant": broad, "until": "taskgen", "state": "running"}))
    worker.execute_live(m.root, j["id"], worker.read(m.root, j["id"]))
    assert worker.read(m.root, j["id"])["state"] == "stopped" and led() == first


@pytest.mark.browser
def test_the_exact_goal_through_the_real_path_reports_the_coverage_limit_instead_of_substituting_tasks(tmp_path, monkeypatch, provider):
    exact = "Can a shopper compare the hire price and availability of the two cheapest cutting tools?"
    monkeypatch.setenv("META_MODEL_API_KEY", KEY)
    prov, url = provider()
    m = JobManager(tmp_path / "live", live=smoke_settings(base_url=url))
    j = m.create("o", "ironbark", exact, "live", 0.15)
    v = wait_for(lambda: (lambda x: x if x["state"] not in ("queued", "running") else None)(m.get(j["id"], "o")), 240)
    assert v["state"] == "stopped" and v["stop"]["kind"] == "coverage" and "goal coverage insufficient" in v["error"], (v["state"], v["error"])
    assert prov.calls == {"taskgen": 3, "agent": 0, "investigator": 0} and v["spend"]["committed_usd"] <= 0.15
    rep = v["smoke"]
    assert rep["yield"]["meets_minimum"] is False and rep["yield"]["rule_topup_tasks"] == 0 and rep["proposal_accounting"]["unaccounted"] == 0
    rel = rep["relevance_to_goal"]
    assert any(l.startswith("price:") for l in rel["limitations"]) and rel["relevant_tasks"] == 3 and all("availability" in p["aspects_matched"] for p in rel["per_task"] if p["goal_relevant"])
    assert {s["name"]: s["status"] for s in v["stages"]}["freeze"] == "pending", "no task set was frozen from an insufficient selection"
