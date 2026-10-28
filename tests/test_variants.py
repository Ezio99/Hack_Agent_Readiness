"""Task 006 Stage 1: storefront variant invariants (rendered HTML, truth and evaluator), offline."""
import hashlib
import itertools
import json
import re
import pytest
from fastapi.testclient import TestClient
from agent_readiness import runner
from agent_readiness.evaluator import evaluate
from agent_readiness.inventory import INVENTORY_HASH, PRODUCTS
from agent_readiness.metrics import run_metrics
from agent_readiness.storefront import (EXPERIMENTAL_ARMS, LISTING_TEMPLATES, VARIANT_B_ID, VARIANT_D0_ID, VARIANT_ID, app,
                                        create_app)
from agent_readiness.tasks import generate

TPL = "src/agent_readiness/templates/"
# SHA-256 of the baseline responses rendered by the storefront BEFORE any Task 006 change (captured from the pre-change code).
BASELINE_GOLDEN = {
    "/": "910a8322de81141be66015b9d743e240eba17a7f2218f57092dde5bb20fc9ae8",
    "/?category=Home&brand=Fern&max_price=29": "6269d913063f09f5c4410ccf6d54f83f10b6e405034bbd398499fac961cfc9d9",
    "/?q=cushion": "b854382eaa06e212c377f1610f81dd6913ce23e3172868b96d7837770102f867",
    "/?max_price=abc": "ccee8ec77c37886e1c966b9cc422942a8a4bfd034032f47eac09746c1f59964a",
    f"/products/{PRODUCTS[0].route}": "0033c7a2e529e165e9989f968a39a145d17781cc65f05eef0bd77fa1d799b084",
    f"/products/{PRODUCTS[11].route}": "9bdec29b8d487aeae6017e409230c92e6928ee2930f423ab906da0a5e8c15931",
    "/products/nope": "49deaa6e8bd4425741b57557b1e5d3f2a371a8a62685819b2f9afb13c66dd03f",
}
TASKS_GOLDEN = "f6c5e94ed6cb9c6419f645b3fcc27e61d6d32dd1053993eef79ef6f4d2d528d5"
INVENTORY_GOLDEN = "e61614b81af8ed6f6c445e650a7d4beae942735e4ffbbf5df7cd67f5517c78b9"
PILOT_SEEDS = (2, 9, 7, 5, 14, 13)
A_LINK = '<h2><a href="/products/{route}">{name}</a></h2>'
B_LINK = '<h2>{name}</h2><p><a href="/products/{route}">View details</a></p>'
D0_LINK = '<h2><a href="/products/{route}" aria-label="View details">{name}</a></h2>'
clients = {v: TestClient(create_app(v)) for v in LISTING_TEMPLATES}


def sha(content):
    return hashlib.sha256(content).hexdigest()


def queries():
    cats = ["", "Home", "Bags", "Kitchen", "Outdoors"]
    brands = ["", "Fern", "Harbor", "Ember"]
    prices = ["", "29", "35.50", "0", "100"]
    paths = ["/"] + [f"/?category={c}&brand={b}&max_price={p}" for c, b, p in itertools.product(cats, brands, prices)]
    return paths + ["/?q=cushion", "/?q=zzz", "/?q=Fern", "/?max_price=abc", "/?max_price=-1", "/?max_price=1.005"]


def transform(html, src, dst):
    for p in PRODUCTS:
        html = html.replace(src.format(route=p.route, name=p.name), dst.format(route=p.route, name=p.name))
    return html


def test_baseline_rendering_is_byte_identical_to_the_pre_change_storefront():
    for path, golden in BASELINE_GOLDEN.items():
        assert sha(clients[VARIANT_ID].get(path).content) == golden, path
        assert sha(TestClient(app).get(path).content) == golden, path  # the unchanged module-level app too


def test_baseline_template_is_untouched_and_variants_differ_only_in_the_card_link_markup():
    import subprocess
    assert subprocess.run(["git", "diff", "--quiet", "HEAD", "--", TPL + "listing.html", TPL + "base.html", TPL + "detail.html"]).returncode == 0
    base = open(TPL + "listing.html").read()
    marker = A_LINK.format(route="{{ p.route }}", name="{{ p.name }}")
    assert base.count(marker) == 1
    assert open(TPL + "listing_b.html").read() == base.replace(marker, B_LINK.format(route="{{ p.route }}", name="{{ p.name }}"))
    assert open(TPL + "listing_d0.html").read() == base.replace(marker, D0_LINK.format(route="{{ p.route }}", name="{{ p.name }}"))


@pytest.mark.parametrize("variant,link", [(VARIANT_B_ID, B_LINK), (VARIANT_D0_ID, D0_LINK)])
def test_rendered_pages_differ_from_baseline_only_by_the_link_markup_for_every_query(variant, link):
    for path in queries():
        a, b = clients[VARIANT_ID].get(path), clients[variant].get(path)
        assert a.status_code == b.status_code, path
        assert transform(a.text, A_LINK, link) == b.text, path
        if "<article>" in a.text:
            assert a.text != b.text


def test_detail_pages_and_errors_are_byte_identical_across_all_variants():
    paths = [f"/products/{p.route}" for p in PRODUCTS] + ["/products/nope", "/products/"]
    for path in paths:
        digests = {v: sha(c.get(path).content) for v, c in clients.items()}
        assert len(set(digests.values())) == 1, path


def test_inventory_ids_routes_order_prices_availability_and_listing_order_are_identical():
    assert INVENTORY_HASH == INVENTORY_GOLDEN
    ordered = []
    for variant, client in clients.items():
        html = client.get("/").text
        routes = re.findall(r'href="/products/([0-9a-f]+)"', html)
        assert routes == [p.route for p in PRODUCTS] and len(set(routes)) == 20
        assert re.findall(r'<p class="price">\$([\d.]+)</p>', html) == [f"{p.price_cents / 100:.2f}" for p in PRODUCTS]
        assert re.findall(r"<p>(\w+) · (\w+)</p>", html) == [(p.brand, p.category) for p in PRODUCTS]
        ordered.append(routes)
    assert ordered[0] == ordered[1] == ordered[2]


def test_task_generation_truth_and_evaluator_are_independent_of_the_variant():
    rows = [[kind, s, t.public.task_id, t.public.prompt, t.expected_id]
            for kind in ("discovery", "availability") for s in range(60) for t in [generate(s, kind)]]
    assert sha(json.dumps(rows).encode()) == TASKS_GOLDEN
    import agent_readiness.tasks, agent_readiness.evaluator
    for module in (agent_readiness.tasks, agent_readiness.evaluator):
        assert "storefront" not in open(module.__file__).read()


def read_answer(client, route):
    html = client.get(f"/products/{route}").text
    return {"product_id": re.search(r'id="product-id">([^<]+)<', html).group(1),
            "price_cents": round(float(re.search(r'id="price">\$([\d.]+)<', html).group(1)) * 100),
            "available": "In stock" in html}


@pytest.mark.parametrize("variant", EXPERIMENTAL_ARMS)
def test_the_pilot_tasks_are_solvable_and_graded_identically_in_both_arms(variant):
    client = clients[variant]
    for seed in PILOT_SEEDS:
        task = generate(seed, "discovery")
        m = re.match(r"Find the (.+) product in (.+) costing at most \$(\d+\.\d{2}) AUD\.", task.public.prompt)
        brand, category, price = m.groups()
        html = client.get("/", params={"brand": brand, "category": category, "max_price": price}).text
        routes = re.findall(r'href="/products/([0-9a-f]+)"', html)
        assert len(routes) == 1                                  # filtering isolates the target in both arms
        answer = read_answer(client, routes[0])
        assert evaluate(answer, task).passed and answer["product_id"] == task.expected_id
        # a navigator that opens the first listed product (first "View details" in B) fails the independent evaluator
        first = read_answer(client, re.findall(r'href="/products/([0-9a-f]+)"', client.get("/").text)[0])
        assert not evaluate(first, task).passed


def test_variant_identity_is_not_visible_in_any_response():
    for variant, client in clients.items():
        for path in queries()[:30] + [f"/products/{PRODUCTS[0].route}", "/products/nope"]:
            response = client.get(path)
            blob = response.text + json.dumps(dict(response.headers))
            for secret in (VARIANT_ID, VARIANT_B_ID, VARIANT_D0_ID, "baseline", "variant", "diagnostic"):
                assert secret not in blob, (variant, path, secret)
    titles = {v: re.search(r"<title>(.*?)</title>", c.get("/").text).group(1) for v, c in clients.items()}
    assert len(set(titles.values())) == 1


def test_unknown_variant_is_rejected():
    with pytest.raises(ValueError):
        create_app("nope")


async def test_diagnostic_variant_cannot_be_used_in_a_live_trial(tmp_path, monkeypatch):
    monkeypatch.setenv("META_MODEL_API_KEY", "sentinel-not-real-0123456789")
    path, record = await runner.run(mode="live", allow_model_calls=True, output=tmp_path, seed=2,
                                    storefront_variant=VARIANT_D0_ID, max_steps=6, max_model_requests=6, timeout_seconds=120)
    assert record["status"] == "setup_error" and "offline-only" in record["errors"][0] and record["model_request_count"] == 0
    path, record = await runner.run(mode="live", allow_model_calls=True, output=tmp_path, seed=2,
                                    storefront_variant="nope", max_steps=6, max_model_requests=6, timeout_seconds=120)
    assert record["status"] == "setup_error"


# ---- non-target product tracking (pure function over trace events) -------------------------------------------

def obs(step, url, actions=None):
    return {"kind": "observation", "step": step, "url": url, "proposed_actions": actions or []}


def test_non_target_visits_are_counted_objectively_without_classifying_them_as_errors():
    target, other, third = PRODUCTS[11], PRODUCTS[0], PRODUCTS[3]
    base = "http://127.0.0.1:1"
    events = [obs(1, f"{base}/", [{"click": {"index": 86}}]), obs(2, f"{base}/products/{other.route}", [{"go_back": {}}]),
              obs(3, f"{base}/", [{"click": {"index": 88}}]), obs(4, f"{base}/products/{third.route}", [{"go_back": {}}]),
              obs(5, f"{base}/?category=Home&brand=Fern", [{"click": {"index": 9}}]),
              obs(6, f"{base}/products/{target.route}", [{"done": {"data": {}}}]),
              obs(7, f"{base}/products/{target.route}")]   # same page observed again: one arrival
    m = run_metrics(events, {"evaluation": {"passed": True}, "status": "completed", "usage": [{"prompt_tokens": 1000, "completion_tokens": 100}],
                              "http_captures": [{"elapsed_seconds": 2.0, "reasoning_tokens": 40}]}, target.product_id)["navigation"]
    assert [a["is_target"] for a in m["product_page_arrivals"]] == [False, False, True]
    assert m["non_target_product_page_arrivals"] == 2 and m["distinct_non_target_products"] == 2
    assert m["first_product_page_is_target"] is False and m["target_page_reached"] is True
    assert m["proposed_action_counts"] == {"click": 3, "go_back": 2, "done": 1}
    full = run_metrics(events, {"evaluation": {"passed": True}, "status": "completed", "usage": [{"prompt_tokens": 1000, "completion_tokens": 100}],
                                 "http_captures": [{"elapsed_seconds": 2.0, "reasoning_tokens": 40}]}, target.product_id)
    assert full["task_success"] == {"evaluator_passed": True, "status": "completed"}   # exploratory clicks do not change success
    assert full["strategy"]["used_search_or_filter"] is True and full["strategy"]["search_or_filter_params_in_observed_urls"] == ["brand", "category"]
    assert full["tokens"] == {"prompt": 1000, "completion": 100, "reasoning": 40, "requests_with_usage": 1}
    assert full["cost"]["calculated_actual_usd"] == round(1000 * 1.25 / 1e6 + 100 * 4.25 / 1e6, 6)


def test_metrics_without_product_pages_report_none_not_failure():
    m = run_metrics([obs(1, "http://127.0.0.1:1/")], {"evaluation": None, "status": "step_limit"}, "X")["navigation"]
    assert m["product_page_arrivals"] == [] and m["first_product_page_is_target"] is None and m["non_target_product_page_arrivals"] == 0
