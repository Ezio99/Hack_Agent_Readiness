"""Task 013: the optional `sku` website factor (SKU printed on listing cards). The original four variants must be byte-for-byte unchanged."""
import re

import pytest
from fastapi.testclient import TestClient

from agent_readiness.environments.electronics import catalog as C
from agent_readiness.environments.electronics.scripted import solve
from agent_readiness.environments.electronics.variants import all_variants, make_variant, sku_variants
from agent_readiness.suite import core, registry

registry.load_all()
ENV = core.ENVIRONMENTS["electronics-v1"]
SKU_P = re.compile(r'\s*<p class="sku">SKU [A-Z]{2}-\d+</p>')
PAGES = ["/", "/c/headphones", "/c/headphones?anc=1&max_price=250&in_stock=1", "/c/monitors?min_screen=27&usb_c=1", "/search?q=Kestrel", "/p/lumio-hush-3", "/help/returns"]


def client(v):
    return TestClient(ENV.create_app(v), base_url="http://shop.local")


def test_original_variants_and_ids_are_unchanged_and_sku_variant_id_is_distinct():
    assert [v.variant_id.split("/")[1] for v in all_variants()] == ["availability-listing+specs-structured", "availability-listing+specs-fragmented", "availability-detail+specs-structured", "availability-detail+specs-fragmented"]
    assert make_variant("listing", "structured", "hidden") == make_variant("listing", "structured")
    (sv,) = sku_variants()
    assert sv.variant_id == "electronics-v1/availability-listing+specs-structured+sku-listing" and sv in ENV.variants()
    with pytest.raises(ValueError):
        make_variant("listing", "structured", "everywhere")


@pytest.mark.parametrize("v", all_variants(), ids=lambda v: v.variant_id.split("/")[1])
def test_original_variants_never_print_a_sku_on_cards(v):
    c = client(v)
    for path in PAGES[:5]:
        assert 'class="sku"' not in c.get(path).text


@pytest.mark.parametrize("path", PAGES)
def test_sku_variant_differs_from_baseline_only_by_the_sku_lines_on_cards(path):
    base, sku = client(make_variant()).get(path).text, client(sku_variants()[0]).get(path).text
    assert SKU_P.sub("", sku) == base
    if path.startswith("/p/") or path.startswith("/help"):
        assert sku == base                                            # detail and policy pages are identical
    elif "/c/" in path or path == "/" or "search" in path:
        assert sku != base and len(re.findall(r'class="sku"', sku)) == len(re.findall(r'class="card"', sku)) > 0


def test_every_card_shows_the_catalogue_sku_of_that_card_only():
    html = client(sku_variants()[0]).get("/c/headphones?max_price=250&anc=1&in_stock=1").text
    cards = html.split('<article class="card">')[1:]
    for card in cards:
        slug = re.search(r'href="/p/([a-z0-9-]+)"', card).group(1)
        product = next(p for p in C.PRODUCTS if p.path == f"/p/{slug}")
        assert f"SKU {product.sku}" in card


def test_data_oracles_and_fixtures_are_unaffected_and_every_fixture_is_solvable():
    from agent_readiness.suite.runner import page_text
    v = sku_variants()[0]
    c = client(v)
    for inst in core.all_instances():
        paths = []

        def fetch(path):
            paths.append(path)
            r = c.get(path)
            r.raise_for_status()
            return r.text
        answer = solve(inst.spec.template_id, dict(inst.spec.parameters), inst.spec.outcome_type, fetch)
        obs = [core.Observation(p.split("?")[0], c.get(p).text) for p in paths]
        rec = core.evaluate(inst, answer, v, obs)
        assert rec.passed and rec.evidence_backed, (inst.spec.task_id, rec.reasons, rec.missing_evidence)


def test_t1_sku_evidence_is_satisfiable_from_listing_only_when_the_sku_factor_is_on():
    inst = registry.get_instance("t1-anc-headphones-under-250-all")
    for v, expect_missing in ((make_variant(), True), (sku_variants()[0], False)):
        c = client(v)
        obs = [core.Observation("/c/headphones", c.get("/c/headphones?anc=1&max_price=250&in_stock=1").text)]
        gaps = core.evidence_gaps(inst, obs)
        assert any(g.startswith("observed_text:HP-") for g in gaps) == expect_missing, (v.variant_id, gaps)


def test_original_variant_pages_are_byte_identical_to_the_pre_task013_storefront():
    """Golden SHA-256 of sampled pages (main @ 7e9bf61) for all four original variants: the Task 012 frozen environment has not changed."""
    import hashlib, json, pathlib
    golden = json.loads((pathlib.Path(__file__).parent / "golden_pages_electronics_v1.json").read_text())
    bad = []
    for v in all_variants():
        c = client(v)
        for p in ["/", "/c/headphones?anc=1&max_price=250", "/search?q=Kestrel", "/p/lumio-hush-3", "/c/monitors?usb_c=1"]:
            if hashlib.sha256(c.get(p).content).hexdigest() != golden[v.variant_id + p]:
                bad.append(v.variant_id + p)
    assert not bad and len(golden) == 20
