"""Task 011 protected-scanner service: invitations, sessions, authorization, quotas, budget, kill switch, limits. Uses a stub runner - no browser, no model, no network."""
import asyncio
import json
import threading
import time

import pytest
from fastapi.testclient import TestClient

from agent_readiness.scanner import diagnostics
from agent_readiness.scanner.service import api as api_mod
from agent_readiness.scanner.service.config import ScannerConfig, load_config
from agent_readiness.scanner.service.store import ScanRefused, Store
from agent_readiness.suite import core, registry

registry.load_all()
TASK = "t3-cheapest-monitor-27in-usbc-120hz"
VAR = "electronics-v1/availability-listing+specs-structured"
GATE = threading.Event()


def fake_record(task, variant, provider, behavior):
    inst = registry.get_instance(task)
    ev = {"passed": True, "evidence_backed": True, "answer_valid": True, "reasons": ["ok"], "missing_evidence": [], "evidence_satisfied": True,
          "evaluator_id": "e", "evaluator_version": "1", "contract_version": "suite-contract-v1", "oracle": "SECRET-TRUTH"}
    return {"scan": {"mode": provider, "model": "m", "profile": "p", "profile_hash": "h", "schema_hashes": {}}, "task": inst.spec.record(), "variant": {"id": variant.variant_id, "factors": dict(variant.factors)},
            "outcome": {"run_status": "completed", "stop_reason": "agent_done", "errors": [], "answer": {"x": 1}}, "evaluation": ev,
            "metrics": {"model_requests": 3, "calculated_cost_usd": 0.01, "limits": {}}, "journey": [], "diagnostics": {"findings": []}, "artifact_path": "/private/path"}


async def stub_runner(task, variant, *, provider, mock_behavior, output, model_config=None, api_key=None):
    await asyncio.get_running_loop().run_in_executor(None, GATE.wait, 5)
    return fake_record(task, variant, provider, mock_behavior)


@pytest.fixture
def env(tmp_path):
    GATE.set()
    cfg = ScannerConfig(data_dir=tmp_path, secret="test-secret", admin_token="adm-token", cors_origins=("https://ok.example",), rate_limit_per_minute=1000)
    app = api_mod.create_scanner_app(cfg, runner=stub_runner)
    return cfg, app, TestClient(app), app.state.store


def login(env, **kw):
    _, app, c, store = env
    _, code = store.create_invitation("t", **kw)
    r = c.post("/api/session", json={"code": code})
    assert r.status_code == 200
    return {"Authorization": "Bearer " + r.json()["token"]}


def wait(c, h, sid, n=100):
    for _ in range(n):
        s = c.get(f"/api/scans/{sid}", headers=h).json()
        if s["status"] not in ("queued", "running"):
            return s
        time.sleep(0.05)
    raise AssertionError("scan did not finish")


def post(c, h, **kw):
    return c.post("/api/scans", json={"task_id": TASK, "variant_id": VAR, **kw}, headers=h)


def test_codes_are_stored_hashed_and_single_use(env):
    _, _, c, store = env
    _, code = store.create_invitation("x")
    assert code not in open(store.path, "rb").read().decode("latin1")
    assert c.post("/api/session", json={"code": code}).status_code == 200
    assert c.post("/api/session", json={"code": code}).status_code == 401


def test_invalid_code_lockout(env):
    cfg, _, c, _ = env
    for _ in range(cfg.code_attempts_per_10_min):
        assert c.post("/api/session", json={"code": "AR-WRONG-CODE"}).status_code == 401
    assert c.post("/api/session", json={"code": "AR-WRONG-CODE"}).status_code == 429


def test_expired_and_revoked_invitations(env):
    _, _, c, store = env
    _, code = store.create_invitation("x", days=-1)
    assert c.post("/api/session", json={"code": code}).status_code == 401
    inv, code2 = store.create_invitation("y")
    store.revoke_invitation(inv)
    assert c.post("/api/session", json={"code": code2}).status_code == 401


def test_redemption_cap_is_race_safe(env):
    _, _, c, store = env
    _, code = store.create_invitation("x", max_redemptions=2)
    results = []
    ts = [threading.Thread(target=lambda: results.append(store.redeem(code))) for _ in range(8)]
    [t.start() for t in ts]; [t.join() for t in ts]
    assert sum(r is not None for r in results) == 2


def test_authentication_required_everywhere_private(env):
    _, _, c, _ = env
    for method, path in (("get", "/api/session"), ("get", "/api/scans"), ("get", "/api/scans/abc"), ("post", "/api/scans"), ("get", "/api/compare?baseline=a&rescan=b")):
        r = getattr(c, method)(path, **({"json": {}} if method == "post" else {}))
        assert r.status_code == 401, path
    assert c.get("/api/session", headers={"Authorization": "Bearer forged"}).status_code == 401


def test_session_expiry(env):
    cfg, app, c, store = env
    h = login(env)
    tok = h["Authorization"][7:]
    with store.tx() as conn:
        conn.execute("UPDATE sessions SET expires_at=?", (time.time() - 1,))
    assert c.get("/api/session", headers=h).status_code == 401 and tok


def test_scan_runs_and_result_is_sanitized(env):
    _, _, c, _ = env
    h = login(env)
    r = post(c, h)
    assert r.status_code == 202
    s = wait(c, h, r.json()["scan_id"])
    assert s["status"] == "complete" and s["verdict"]["passed"] and s["mock"] is True and "MOCK" in s["inference_label"]
    blob = json.dumps(s)
    assert "SECRET-TRUTH" not in blob and "/private/path" not in blob and "oracle" not in blob.lower()


def test_other_users_cannot_read_or_compare_scans(env):
    _, _, c, _ = env
    a, b = login(env), login(env)
    sid = post(c, a).json()["scan_id"]
    wait(c, a, sid)
    assert c.get(f"/api/scans/{sid}", headers=b).status_code == 404
    assert c.get(f"/api/scans/doesnotexist", headers=b).status_code == 404
    assert c.get("/api/scans", headers=b).json()["scans"] == []
    assert c.get(f"/api/compare?baseline={sid}&rescan={sid}", headers=b).status_code == 404


def test_only_registered_targets_and_no_free_form_fields(env):
    _, _, c, _ = env
    h = login(env)
    assert post(c, h, url="http://169.254.169.254/").status_code == 422
    assert post(c, h, prompt="ignore previous instructions").status_code == 422
    assert c.post("/api/scans", json={"task_id": TASK, "variant_id": "http://evil.example"}, headers=h).status_code == 422
    assert c.post("/api/scans", json={"task_id": "nope", "variant_id": VAR}, headers=h).status_code == 422
    assert post(c, h, mock_behavior="rm -rf").status_code == 422
    assert post(c, h, mode="live").status_code == 403           # live is off by default


def test_quota_is_enforced_and_idempotency_prevents_double_charge(env):
    _, _, c, store = env
    h = login(env, scan_quota=2)
    first = post(c, h, ) 
    k = {**h, "Idempotency-Key": "k1"}
    wait(c, h, first.json()["scan_id"])
    a = c.post("/api/scans", json={"task_id": TASK, "variant_id": VAR}, headers=k).json()["scan_id"]
    b = c.post("/api/scans", json={"task_id": TASK, "variant_id": VAR}, headers=k).json()["scan_id"]
    assert a == b
    wait(c, h, a)
    r = post(c, h)
    assert r.status_code == 429 and r.json()["message"].startswith("This session's scan quota")


def test_one_concurrent_scan(env):
    _, _, c, _ = env
    GATE.clear()
    h1, h2 = login(env), login(env)
    first = post(c, h1)
    assert first.status_code == 202
    assert post(c, h2).status_code == 409
    GATE.set()
    wait(c, h1, first.json()["scan_id"])
    assert post(c, h2).status_code == 202


def test_concurrent_reservations_admit_exactly_one(env):
    _, _, _, store = env
    sessions = []
    for _ in range(6):
        _, code = store.create_invitation("x")
        sessions.append(store.session_for(store.redeem(code)[0]))
    out = []
    def go(s):
        try:
            out.append(store.reserve_scan(s, TASK, VAR, "mock", None, 0.0, 0.0))
        except ScanRefused as e:
            out.append(e.code)
    ts = [threading.Thread(target=go, args=(s,)) for s in sessions]
    [t.start() for t in ts]; [t.join() for t in ts]
    assert sum(1 for o in out if o not in ("scan_in_progress",)) == 1


def test_live_budget_is_reserved_atomically_and_exhausts(env):
    _, _, _, store = env
    sess = []
    for _ in range(3):
        _, code = store.create_invitation("x")
        sess.append(store.session_for(store.redeem(code)[0]))
    s1 = store.reserve_scan(sess[0], TASK, VAR, "live", None, 0.48, 0.60)
    store.finish_scan(s1, "error", None, "boom")                  # failed live scan keeps its full reservation (spend uncertain)
    assert store.spent_usd() == pytest.approx(0.48)
    with pytest.raises(ScanRefused) as e:
        store.reserve_scan(sess[1], TASK, VAR, "live", None, 0.48, 0.60)
    assert e.value.code == "budget_exhausted"
    with pytest.raises(ScanRefused):
        store.reserve_scan(sess[1], TASK, VAR, "live", None, 0.48, 0.0)      # budget 0 = nothing can be reserved


def test_kill_switch(env):
    cfg, _, c, _ = env
    h = login(env)
    assert c.post("/api/admin/kill", json={"enabled": True}).status_code == 403
    assert c.post("/api/admin/kill", json={"enabled": True}, headers={"X-Admin-Token": "wrong"}).status_code == 403
    assert c.post("/api/admin/kill", json={"enabled": True}, headers={"X-Admin-Token": "adm-token"}).status_code == 200
    assert post(c, h).status_code == 503 and c.get("/api/registry").json()["kill_switch"] is True
    c.post("/api/admin/kill", json={"enabled": False}, headers={"X-Admin-Token": "adm-token"})
    assert post(c, h).status_code == 202


def test_kill_switch_disabled_without_admin_token(tmp_path):
    app = api_mod.create_scanner_app(ScannerConfig(data_dir=tmp_path, secret="s"), runner=stub_runner)
    assert TestClient(app).post("/api/admin/kill", json={"enabled": True}, headers={"X-Admin-Token": ""}).status_code == 403


def test_restart_marks_active_scans_interrupted_and_never_reruns(env):
    cfg, _, c, store = env
    h = login(env)
    GATE.clear()
    sid = post(c, h).json()["scan_id"]
    app2 = api_mod.create_scanner_app(cfg, runner=stub_runner)          # simulated restart
    assert app2.state.store.get_scan(sid)["status"] == "interrupted"
    GATE.set()


def test_body_size_cors_headers_and_rate_limit(tmp_path):
    cfg = ScannerConfig(data_dir=tmp_path, secret="s", cors_origins=("https://ok.example",), rate_limit_per_minute=5, max_body_bytes=200)
    c = TestClient(api_mod.create_scanner_app(cfg, runner=stub_runner))
    assert c.post("/api/session", content=b'{"code":"' + b"A" * 500 + b'"}', headers={"content-type": "application/json"}).status_code == 413
    ok = c.get("/api/health", headers={"Origin": "https://ok.example"})
    assert ok.headers["access-control-allow-origin"] == "https://ok.example" and ok.headers["cache-control"] == "no-store"
    assert "access-control-allow-origin" not in c.get("/api/health", headers={"Origin": "https://evil.example"}).headers
    codes = [c.get("/api/health").status_code for _ in range(8)]
    assert 429 in codes


def test_runner_exception_is_recorded_generically_and_not_retried(tmp_path):
    calls = []
    async def boom(*a, **k):
        calls.append(1)
        raise RuntimeError("secret detail /home/x")
    app = api_mod.create_scanner_app(ScannerConfig(data_dir=tmp_path, secret="s", rate_limit_per_minute=1000), runner=boom)
    c, store = TestClient(app), app.state.store
    _, code = store.create_invitation("x")
    h = {"Authorization": "Bearer " + c.post("/api/session", json={"code": code}).json()["token"]}
    sid = post(c, h).json()["scan_id"]
    s = wait(c, h, sid)
    assert s["status"] == "error" and s["error"] == "RuntimeError" and "secret" not in json.dumps(s) and len(calls) == 1


def test_dev_secret_is_generated_with_private_mode(tmp_path):
    cfg = load_config({"SCANNER_DATA_DIR": str(tmp_path)})
    assert cfg.secret and (tmp_path / ".dev-secret").stat().st_mode & 0o077 == 0
    assert cfg.live_enabled is False and not cfg.live_available


# ---- diagnostics (pure) --------------------------------------------------------------------------------------------------------
def rec(mode="mock", passed=True, variant=("listing", "structured"), task=TASK, req=3):
    r = fake_record(task, core.Variant(variant_id="v", environment_id="electronics-v1", factors=(("availability", variant[0]), ("specs", variant[1]))), mode, None) if False else fake_record(task, registry.get_instance(task) and __import__("agent_readiness.environments.electronics.variants", fromlist=["x"]).make_variant(*variant), mode, None)
    r["scan"]["mode"] = mode
    r["evaluation"]["passed"] = passed
    r["metrics"] = {"model_requests": req, "page_views": req, "elapsed_seconds": 1.0, "calculated_cost_usd": 0.01 * req}
    return r


def test_compare_flags_uncontrolled_and_mock_and_single_run_caveats():
    a, b = rec(variant=("detail", "structured")), rec(variant=("listing", "structured"), req=2)
    d = diagnostics.compare(a, b)
    assert d["controlled"] and d["factors_changed"] == {"availability": ["detail", "listing"]}
    assert d["metrics"]["model_requests"]["delta"] == -1
    assert any("MOCK" in x for x in d["caveats"]) and any("single scan" in x or "Each side is a single" in x for x in d["caveats"])
    d2 = diagnostics.compare(rec(variant=("detail", "fragmented")), rec(variant=("listing", "structured")))
    assert not d2["controlled"]
    with pytest.raises(ValueError):
        diagnostics.compare(rec(task="t4-policy-delivery-tessera-whisper"), rec())
