from dataclasses import replace
import pytest
from httpx import ASGITransport, AsyncClient
from agent_readiness.inventory import PRODUCTS
from agent_readiness.storefront import app
from agent_readiness.tasks import generate
from agent_readiness.evaluator import evaluate


def answer_for(task):
    p = next(p for p in PRODUCTS if p.product_id == task.expected_id)
    return dict(product_id=p.product_id, price_cents=p.price_cents, available=p.available)


@pytest.mark.parametrize("kind,available", [("discovery", None), ("availability", True), ("availability", False)])
def test_seeded_tasks_feasible_unique_and_private(kind, available):
    for seed in range(100):
        t = generate(seed, kind, available)
        assert t == generate(seed, kind, available)
        matches = [p for p in PRODUCTS if t.matches(p)]
        assert len(matches) == 1 and matches[0].product_id == t.expected_id
        assert evaluate(answer_for(t), t).passed
        assert "expected_id" not in t.public.model_dump()
        assert all(p.product_id not in t.public.model_dump_json() for p in PRODUCTS)
        if available is not None:
            assert matches[0].available is available


def test_evaluator_rejects_wrong_fields_and_constraints():
    t = generate()
    correct = answer_for(t)
    for field, wrong in [("product_id", "unknown"), ("price_cents", 0), ("available", not correct["available"])]:
        result = evaluate({**correct, field: wrong}, t)
        assert not result.passed and result.reasons
    inconsistent_private_task = replace(t, category="Nonexistent")
    assert not evaluate(correct, inconsistent_private_task).passed
    other = next(p for p in PRODUCTS if p.product_id != t.expected_id)
    assert not evaluate(dict(product_id=other.product_id, price_cents=other.price_cents, available=other.available), t).passed


@pytest.mark.parametrize("raw", [None, {}, [], "not json", {"product_id": "x", "price_cents": True, "available": "false"}])
def test_malformed_answer(raw):
    assert not evaluate(raw, generate()).passed


def assert_no_leaks(text):
    for p in PRODUCTS:
        assert p.product_id not in text
        assert p.product_id not in p.route
    for forbidden in ['In stock', 'Out of stock', 'available', 'availability', 'product_id', 'application/json', 'data-stock']:
        assert forbidden.casefold() not in text.casefold()


async def test_storefront_boundary_routes_and_filters():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        for params in [{}, {"q": "Fern"}, {"category": "Bags", "brand": "Fern", "max_price": "24.00"}, {"available": "true"}]:
            r = await c.get("/", params=params)
            assert r.status_code == 200
            assert_no_leaks(r.text)
        filtered = await c.get("/", params={"q": "Tote", "category": "Bags", "brand": "Fern", "max_price": "24"})
        assert "City Tote" in filtered.text and "Trail Daypack" not in filtered.text
        assert (await c.get("/", params={"max_price": ""})).status_code == 200
        for value in ["-1", "nan", "Infinity", "oops", "1.001"]:
            assert (await c.get("/", params={"max_price": value})).status_code == 422
        for p in PRODUCTS:
            r = await c.get(f"/products/{p.route}")
            assert p.product_id in r.text
            assert ("In stock" if p.available else "Out of stock") in r.text
        for path in ["/inventory.json", "/api/products", "/openapi.json", "/docs", "/tasks", "/products/unknown", "/.env", "/src/agent_readiness/inventory.py"]:
            assert (await c.get(path)).status_code == 404
        assert {r.path for r in app.routes} == {"/", "/products/{route}"}
