"""Autonomous diagnosis -> recommendation -> re-audit lifecycle (Task 015). Credential-free; no model call. Real HTTP against served storefronts, plus a structurally different
stub shop to show the probe is not tied to one template."""
import asyncio
import inspect
import json
import re
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from agent_readiness import budget
from agent_readiness.environments.electronics.variants import make_variant
from agent_readiness.remediation import discovery, engine, library
from agent_readiness.remediation.engine import attach_measured_effects, build_report, lifecycle
from agent_readiness.remediation.probe import SiteProbe
from agent_readiness.scanner.serve import serve_app
from agent_readiness.suite import core, registry

OBJECTIVE = "List every in-stock ANC headphone at or below A$250.00"


def audit_variant(av, sku="hidden", specs="structured", objective=OBJECTIVE, previous=None):
    registry.load_all()

    async def go():
        async with serve_app(core.ENVIRONMENTS["electronics-v1"].create_app(make_variant(av, specs, sku))) as base:
            obs = await asyncio.to_thread(lambda: SiteProbe(base).run())
            return build_report(obs, objective=objective, previous=previous)
    return asyncio.run(go())


def fps(report, category=None):
    return {f["fingerprint"] for f in report["findings"] if category is None or f["category"] == category}


@pytest.fixture(scope="module")
def baseline():
    return audit_variant("detail", "hidden")


@pytest.fixture(scope="module")
def modified():
    return audit_variant("listing", "hidden")


def test_baseline_detects_availability_absent_from_cards_but_present_on_product_pages(baseline):
    f = next(f for f in baseline["findings"] if f["fingerprint"] == "attribute_detail_only:availability")
    c = f["counts"]
    assert c["cards_examined"] >= 40 and c["cards_with_cue"] == 0 and c["details_examined"] >= 4 and c["details_with_cue"] == c["details_examined"]
    kinds = {e["type"] for e in f["evidence"]}
    assert {"listing_card", "product_page"} <= kinds and all(e.get("url") for e in f["evidence"])      # evidence links to concrete pages and elements
    assert "filter_absent:availability" in fps(baseline)


def test_recommendation_is_selected_from_the_library_by_observed_evidence(baseline):
    rec = next(r for r in baseline["recommendations"] if r["template"] == "show-availability-on-listing-cards")
    assert "attribute_detail_only:availability" in rec["addresses"] and rec["change_id"] == "availability-on-listing-cards"
    assert rec["status"] == "proposed" and rec["validation"] == "unvalidated" and rec["task_relevance"] == "task_depends_on_attribute"
    assert rec["supporting_evidence"] and rec["rationale"].startswith("Observed: 0 of ") and rec["expected_benefit"] and rec["risks"]
    assert rec["confidence"]["level"] == "prior_evidence_other_site" and "NOT validated" in rec["confidence"]["statement"] and rec["confidence"]["basis"][0]["limits"]
    assert rec["how_to_validate"]["resolution_check"] and rec["how_to_validate"]["effect_measurement"]
    assert {r["template"] for r in baseline["recommendations"]} == {"show-availability-on-listing-cards", "show-sku-on-listing-cards"}      # SKU is also detail-only here


def test_modified_site_is_recognised_as_resolved_by_an_independent_rescan(baseline, modified):
    assert "attribute_on_cards:availability" in fps(modified) and "attribute_detail_only:availability" not in fps(modified)
    assert not [r for r in modified["recommendations"] if r["template"] == "show-availability-on-listing-cards"]
    lc = lifecycle(baseline, modified)
    items = {i["fingerprint"]: i for i in lc["items"]}
    assert items["attribute_detail_only:availability"]["status"] == "resolved" and items["filter_absent:availability"]["status"] == "resolved"
    assert items["attribute_detail_only:sku"]["status"] == "persisting"                                  # an unrelated finding stays open
    assert items["attribute_detail_only:availability"]["evidence"][0]["type"] == "listing_card" and "no longer observed" in lc["statement"]


def test_report_with_previous_embeds_lifecycle_and_history_and_distinguishes_resolution_from_effect(baseline):
    again = audit_variant("listing", "hidden", previous=baseline)
    assert again["lifecycle"]["resolved"] == 2 and again["lifecycle"]["previous_audit_id"] == baseline["audit_id"]
    assert again["measured_effects"] == {"status": "not_measured", "effects": []}                        # resolution is NOT an effect


@pytest.mark.parametrize("av,sku,expect_av,expect_sku", [("detail", "hidden", True, True), ("detail", "listing", True, False), ("listing", "hidden", False, True), ("listing", "listing", False, False)])
def test_findings_follow_the_observed_site_in_every_combination(av, sku, expect_av, expect_sku):
    r = audit_variant(av, sku)
    assert ("attribute_detail_only:availability" in fps(r)) == expect_av and ("attribute_detail_only:sku" in fps(r)) == expect_sku
    assert ("attribute_on_cards:availability" in fps(r)) == (not expect_av) and ("attribute_on_cards:sku" in fps(r)) == (not expect_sku)


def test_probe_is_not_tied_to_the_electronics_templates():
    """A differently structured shop (divs, other class names, other URL scheme, other wording) is analysed by the same rules."""
    def shop(stock_on_cards):
        app = FastAPI()
        items = "".join(f'<div class="tile"><a class="t" href="/item/{i}">Gadget {i}</a><span class="amt">${10 + i}.00</span>'
                        + (('<em>Sold out</em>' if i % 2 else '<em>In stock</em>') if stock_on_cards is True else '<em>In stock</em>' if stock_on_cards == "some" and i < 4 else "") + "</div>" for i in range(8))

        @app.get("/", response_class=HTMLResponse)
        async def home():
            return f"<html><body><main><h1>Shop</h1>{items}</main></body></html>"

        @app.get("/item/{i}", response_class=HTMLResponse)
        async def item(i: str):
            return f"<html><body><main><h1>Gadget {i}</h1><p>Price $10.00</p><div class='avail'>{'Sold out' if int(i) % 2 else 'In stock'}</div></main></body></html>"
        return app

    async def go(flag):
        async with serve_app(shop(flag)) as base:
            return build_report(await asyncio.to_thread(lambda: SiteProbe(base).run()), objective="find an item that is in stock")
    base_r, mod_r = asyncio.run(go(False)), asyncio.run(go(True))
    assert "attribute_detail_only:availability" in fps(base_r) and base_r["recommendations"][0]["template"] == "show-availability-on-listing-cards"
    assert "attribute_detail_only:availability" not in fps(mod_r) and lifecycle(base_r, mod_r)["items"][0]["status"] == "resolved"
    part_r = asyncio.run(go("some"))                      # stock on half of the cards: reported as partial, no library recommendation covers it, lifecycle says partially_resolved
    assert "attribute_partial_on_cards:availability" in fps(part_r) and not part_r["recommendations"] and lifecycle(base_r, part_r)["items"][0]["status"] == "partially_resolved"


def test_insufficient_coverage_is_reported_not_guessed():
    async def go():
        app = FastAPI()

        @app.get("/", response_class=HTMLResponse)
        async def home():
            return "<html><body><h1>One page, no products</h1></body></html>"
        async with serve_app(app) as base:
            return build_report(await asyncio.to_thread(lambda: SiteProbe(base).run()))
    r = asyncio.run(go())
    assert fps(r) == {"insufficient_coverage:site"} and r["recommendations"] == []
    prev = {"audit_id": "x", "findings": [{"fingerprint": "attribute_detail_only:availability", "kind": "attribute_detail_only", "attribute": "availability", "category": "website_property", "summary": "s", "evidence": []}]}
    assert lifecycle(prev, r)["items"][0]["status"] == "indeterminate"


def test_nothing_in_the_engine_can_depend_on_arm_variant_or_demo_labels():
    for fn in (build_report, lifecycle, library.select):
        assert not {"variant", "variant_id", "arm", "baseline", "modified", "label", "expected"} & set(inspect.signature(fn).parameters)
    pkg = Path(inspect.getfile(engine)).parent
    forbidden = re.compile(r"\b(variant|baseline|modified|arm|demo_outcome)\b", re.I)
    for name in ("probe.py", "findings.py", "library.py", "engine.py", "execution.py", "discovery.py"):
        code = "\n".join(l for l in (pkg / name).read_text().splitlines() if not l.strip().startswith("#"))
        code = re.sub(r'""".*?"""', "", code, flags=re.S)
        assert not forbidden.search(code), f"{name} mentions an experiment label"


def test_taxonomy_keeps_observations_agent_evidence_proposals_and_measurements_apart(baseline):
    assert set(baseline["taxonomy"]) == {"website_observations", "findings", "agent_execution", "recommendations", "lifecycle", "measured_effects"}
    assert baseline["agent_execution"] is None and baseline["measured_effects"]["effects"] == []
    assert all(f["confidence"] == "observed" for f in baseline["findings"]) and all(r["status"] == "proposed" and r["validation"] == "unvalidated" for r in baseline["recommendations"])


def test_measured_effects_are_attached_only_with_provenance_and_change_validation(baseline):
    rep = json.loads(json.dumps(baseline))
    with pytest.raises(ValueError):
        attach_measured_effects(rep, {"experiment_id": "x"})
    with pytest.raises(ValueError):
        attach_measured_effects(rep, {"experiment_id": "x", "addresses": [], "n_pairs": 1, "metrics": {}, "verdict": "proven"})
    attach_measured_effects(rep, {"experiment_id": "task015-pilot", "addresses": ["attribute_detail_only:availability"], "n_pairs": 4, "metrics": {"model_requests": {"delta": -3.2}}, "verdict": "inconclusive"})
    rec = next(r for r in rep["recommendations"] if r["template"] == "show-availability-on-listing-cards")
    other = next(r for r in rep["recommendations"] if r["template"] == "show-sku-on-listing-cards")
    assert rep["measured_effects"]["status"] == "measured" and rec["validation"] == "measured_inconclusive" and other["validation"] == "unvalidated"


def test_trace_driven_discovery_emits_candidates_without_recommendations():
    j = lambda step, path, q="": {"step": step, "path": path, "query": q, "actions": [], "executed": []}
    journey = [j(1, "/c/monitors"), j(2, "/p/a"), j(3, "/c/monitors"), j(4, "/p/b"), j(5, "/c/monitors"), j(6, "/p/c"), j(7, "/c/monitors")]
    cands = discovery.discover({"journey": journey}, "/p/{}", [])
    assert cands and cands[0]["recommendation"] is None and cands[0]["category"] == "candidate_unexplained" and cands[0]["linked_website_findings"] == []
    linked = discovery.discover({"journey": journey}, "/p/{}", [{"kind": "attribute_detail_only", "fingerprint": "attribute_detail_only:availability"}])
    assert linked[0]["linked_website_findings"] == ["attribute_detail_only:availability"] and linked[0]["recommendation"] is None


def test_budget_is_tracked_in_aud_with_original_usd_records_and_a_documented_rate(monkeypatch):
    monkeypatch.delenv(budget.RATE_ENV, raising=False)
    ledger = budget.load()
    s = budget.summary(ledger)
    assert ledger["entries"] and all("usd" in e and "source" in e for e in ledger["entries"])           # original USD records retained
    assert s["usd_to_aud"] == 1.50 and ledger["assumptions"]["basis"] and ledger["programme_ceiling_aud"] == 50.0 and ledger["ceiling_is_authorization"] is False
    assert s["spent_usd"] == pytest.approx(3.9233, abs=1e-3) and s["spent_aud"] == pytest.approx(5.885, abs=1e-2) and s["remaining_aud"] == pytest.approx(44.115, abs=1e-2)
    assert budget.check_stage(8.0)["remaining_after_cap_aud"] == pytest.approx(36.115, abs=1e-2)
    with pytest.raises(ValueError):
        budget.check_stage(45.0)
    monkeypatch.setenv(budget.RATE_ENV, "1.60")
    assert budget.summary(ledger)["spent_aud"] == pytest.approx(3.9233 * 1.6, abs=1e-2)
