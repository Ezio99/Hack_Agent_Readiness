"""The complete diagnose -> recommend -> modify -> rescan workflow through the product API (protected scanner service) with a managed demo target.
Nothing here names a variant or an arm; the only inputs are a registered target id, an optional shopper objective and the previous audit id. No model call, no key."""
import pytest
from fastapi.testclient import TestClient

from agent_readiness.remediation.targets import TargetRegistry
from agent_readiness.scanner.service import api as api_mod
from agent_readiness.scanner.service.config import ScannerConfig

OBJECTIVE = "List every in-stock ANC headphone at or below A$250.00"
ADMIN = {"X-Admin-Token": "adm-token"}


@pytest.fixture
def product(tmp_path):
    targets = TargetRegistry.demo().start()                 # operator-side initial state: stock only on product pages
    cfg = ScannerConfig(data_dir=tmp_path, secret="s", admin_token="adm-token", rate_limit_per_minute=1000)
    app = api_mod.create_scanner_app(cfg, targets=targets)
    c = TestClient(app)
    _, code = app.state.store.create_invitation("t")
    token = c.post("/api/session", json={"code": code}).json()["token"]
    yield c, {"Authorization": "Bearer " + token}, app
    targets.stop()


@pytest.mark.slow
def test_full_workflow_through_the_api(product):
    c, h, _ = product
    assert c.get("/api/targets", headers=h).json()["targets"] == [{"id": "demo-shop", "description": "Managed demo electronics storefront (electronics-v1)", "managed": True}]
    # 1-3 baseline audit: detection, library selection, evidence, rationale, benefit, confidence/validation
    r = c.post("/api/audits", headers=h, json={"target_id": "demo-shop", "objective": OBJECTIVE})
    assert r.status_code == 201
    base = r.json()
    f = next(f for f in base["findings"] if f["fingerprint"] == "attribute_detail_only:availability")
    assert f["counts"]["cards_with_cue"] == 0 and f["counts"]["details_with_cue"] == f["counts"]["details_examined"] > 0
    rec = next(x for x in base["recommendations"] if x["template"] == "show-availability-on-listing-cards")
    assert rec["supporting_evidence"] and rec["rationale"] and rec["expected_benefit"] and rec["validation"] == "unvalidated" and rec["confidence"]["level"]
    assert base["lifecycle"] is None and base["measured_effects"]["effects"] == [] and "demo-shop" == base["target"] and "127.0.0.1" not in str(base["target"])
    # the operator applies the recommended change (stand-in for the site owner), identified only by the product's own change id
    assert c.post("/api/admin/targets/demo-shop/changes", headers=ADMIN, json={"change_id": rec["change_id"]}).json() == {"target_id": "demo-shop", "applied": ["availability-on-listing-cards"]}
    # 4-5 independent rescan: the finding is recognised as resolved; no labels were supplied
    r2 = c.post("/api/audits", headers=h, json={"target_id": "demo-shop", "objective": OBJECTIVE, "previous_audit_id": base["audit_id"]})
    after = r2.json()
    item = next(i for i in after["lifecycle"]["items"] if i["fingerprint"] == "attribute_detail_only:availability")
    assert item["status"] == "resolved" and item["evidence"] and "attribute_detail_only:availability" not in [x["fingerprint"] for x in after["findings"]]
    assert not [x for x in after["recommendations"] if x["template"] == "show-availability-on-listing-cards"]
    assert after["measured_effects"]["status"] == "not_measured" and "no longer observed" in after["lifecycle"]["statement"]
    # persisted, listed and retrievable
    assert {a["audit_id"] for a in c.get("/api/audits", headers=h).json()["audits"]} == {base["audit_id"], after["audit_id"]}
    assert c.get(f"/api/audits/{after['audit_id']}", headers=h).json()["audit_id"] == after["audit_id"]


@pytest.mark.slow
def test_api_boundaries(product):
    c, h, app = product
    post = lambda body, headers=h: c.post("/api/audits", headers=headers, json=body)
    assert post({"target_id": "demo-shop"}, {}).status_code == 401
    assert post({"target_id": "http://evil.example/"}).status_code == 422                       # registered ids only: no URL can be audited through the service
    assert post({"target_id": "demo-shop", "url": "http://x"}).status_code == 422               # no extra fields (url, variant, labels)
    assert post({"target_id": "demo-shop", "variant_id": "electronics-v1/availability-listing+specs-structured"}).status_code == 422
    assert post({"target_id": "demo-shop", "with_scan": True}).status_code == 422               # a scan needs a registered task
    assert post({"target_id": "demo-shop", "task_id": "nope"}).status_code == 422
    assert post({"target_id": "demo-shop", "previous_audit_id": "missing"}).status_code == 404
    assert c.post("/api/admin/targets/demo-shop/changes", json={"change_id": "availability-on-listing-cards"}).status_code == 403
    assert c.post("/api/admin/targets/demo-shop/changes", headers={"X-Admin-Token": "wrong"}, json={"change_id": "availability-on-listing-cards"}).status_code == 403
    assert c.post("/api/admin/targets/demo-shop/changes", headers=ADMIN, json={"change_id": "make-it-fast"}).status_code == 422
    # another session cannot read or build on this session's audits
    a = post({"target_id": "demo-shop"}).json()["audit_id"]
    _, code2 = app.state.store.create_invitation("other")
    h2 = {"Authorization": "Bearer " + c.post("/api/session", json={"code": code2}).json()["token"]}
    assert c.get(f"/api/audits/{a}", headers=h2).status_code == 404 and post({"target_id": "demo-shop", "previous_audit_id": a}, h2).status_code == 404


@pytest.mark.browser
def test_audit_with_a_mock_agent_scan_keeps_agent_evidence_separate_from_website_findings(product):
    c, h, _ = product
    without = c.post("/api/audits", headers=h, json={"target_id": "demo-shop", "objective": OBJECTIVE}).json()
    with_scan = c.post("/api/audits", headers=h, json={"target_id": "demo-shop", "task_id": "t1-anc-headphones-under-250-all", "with_scan": True}).json()
    ex = with_scan["agent_execution"]
    assert ex["scan_mode"] == "mock" and "MOCK" in ex["mode_notice"] and {i["id"] for i in ex["items"]} >= {"outcome", "effort", "product-page-visits"}
    assert all(i["category"] in ("task_outcome", "agent_execution", "agent_tool_interface", "infrastructure_or_limit") for i in ex["items"])
    assert {f["fingerprint"] for f in with_scan["findings"]} == {f["fingerprint"] for f in without["findings"]}      # agent evidence never creates or removes website findings
    assert ex["corroborates"] and all(x["confidence"] == "inferred" for x in ex["corroborates"]) and with_scan["objective"] and "in stock" in with_scan["objective"].lower()
    assert "variant" not in str(with_scan["agent_execution"]).lower()
