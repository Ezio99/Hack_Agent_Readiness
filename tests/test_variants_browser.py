"""Task 006 Stage 1 in real Chromium: what Browser Use actually shows the agent, the accessibility tree and screenshots."""
import base64
import hashlib
import json
import re
import pytest
from agent_readiness.agent import browser_options, prepare_browser_environment, profile
from agent_readiness.evaluator import evaluate
from agent_readiness.inventory import PRODUCTS
from agent_readiness.server import local_storefront
from agent_readiness.storefront import VARIANT_B_ID, VARIANT_D0_ID, VARIANT_ID
from agent_readiness.tasks import generate

pytestmark = pytest.mark.browser
PILOT_SEEDS = (2, 9, 7, 5, 14, 13)
ALL_VARIANT_STRINGS = (VARIANT_ID, VARIANT_B_ID, VARIANT_D0_ID, "variant", "diagnostic")


async def observe(variant, query=""):
    """Everything an agent (or auditor) can see on the listing: Browser Use view, AX links, screenshot, raw HTML."""
    prepare_browser_environment()
    from browser_use import Browser
    from playwright.async_api import async_playwright
    async with local_storefront(variant) as url, async_playwright() as pw:
        session = Browser(**browser_options(url, pw.chromium.executable_path, profile("natural-shopping-v3-compat1")))
        try:
            await session.start()
            connection = await pw.chromium.connect_over_cdp(session.cdp_url)
            context = connection.contexts[0]
            page = context.pages[0] if context.pages else await context.new_page()
            await page.goto(url + query)
            await page.wait_for_load_state("load")
            state = await session.get_browser_state_summary(include_screenshot=True, cached=False)
            cdp = await context.new_cdp_session(page)
            ax = await cdp.send("Accessibility.getFullAXTree")
            await cdp.detach()
            links = [(n["name"]["value"]) for n in ax["nodes"]
                     if (n.get("role") or {}).get("value") == "link" and n.get("name", {}).get("value") not in ("Clear filters", "Skip to products", "Field & Home")]
            return {"url": state.url, "agent_dom": state.dom_state.llm_representation(), "ax_links": links,
                    "ax_json": json.dumps(ax), "html": await page.content(), "screenshot": hashlib.sha256(base64.b64decode(state.screenshot)).hexdigest()}
        finally:
            await session.kill()


def cards(rep):
    """The product-card region of the Browser Use view (the search form legitimately has its own aria-label)."""
    return rep.split("20 products\n", 1)[1]


def card_lines(rep):
    return sorted(l.strip() for l in rep.splitlines() if re.match(r"^\s*(\$\d|\w+ · \w+$)", l))


async def test_browser_use_observation_accessibility_and_screenshots_per_variant():
    a, b, d0 = [await observe(v) for v in (VARIANT_ID, VARIANT_B_ID, VARIANT_D0_ID)]
    names = [p.name for p in PRODUCTS]
    # Arm A: the link's text is the product name; no generic text, no aria attributes
    assert a["ax_links"] == names and "View details" not in cards(a["agent_dom"]) and "aria-label" not in cards(a["agent_dom"])
    assert all(re.search(rf"<a />\s*\n\s*{re.escape(n)}\n", a["agent_dom"]) for n in names)
    # Arm B: 20 generic links; every name is plain text immediately before its link; no aria/title attribute
    assert b["ax_links"] == ["View details"] * 20 and b["agent_dom"].count("View details") == 20
    assert "aria-label" not in cards(b["agent_dom"]) and "title=" not in cards(b["agent_dom"])
    assert all(re.search(rf"\n{re.escape(n)}\n\[\d+\]<a />\s*\n\s*View details\n", b["agent_dom"]) for n in names)
    # Offline diagnostic: accessible name generic, visible name and its Browser Use text unchanged, screenshot identical
    assert d0["ax_links"] == ["View details"] * 20 and cards(d0["agent_dom"]).count("aria-label=View details") == 20
    assert all(n in d0["agent_dom"] for n in names)
    assert d0["screenshot"] == a["screenshot"] and b["screenshot"] != a["screenshot"]
    # All other product information is identical in what the agent sees
    assert card_lines(a["agent_dom"]) == card_lines(b["agent_dom"]) == card_lines(d0["agent_dom"]) and len(card_lines(a["agent_dom"])) == 40
    assert all(name in b["agent_dom"] for name in names)
    # Element order is the inventory order in both arms and the targets of the clickable elements are the same set
    routes = lambda html: re.findall(r'href="/products/([0-9a-f]+)"', html)
    assert routes(a["html"]) == routes(b["html"]) == routes(d0["html"]) == [p.route for p in PRODUCTS]
    # Leakage: no variant identity and no product ID or truth in any agent-visible payload of the initial observation
    for view in (a, b, d0):
        blob = view["agent_dom"] + view["ax_json"] + view["html"] + view["url"]
        assert not any(s in blob for s in ALL_VARIANT_STRINGS)
        assert not any(p.product_id in view["agent_dom"] or p.product_id in view["html"] for p in PRODUCTS)


@pytest.mark.parametrize("variant", [VARIANT_ID, VARIANT_B_ID])
async def test_filtered_pilot_observations_isolate_the_target_in_both_arms(variant):
    for seed in PILOT_SEEDS[:3]:
        task = generate(seed, "discovery")
        brand, category, price = re.match(r"Find the (.+) product in (.+) costing at most \$(\d+\.\d{2}) AUD\.", task.public.prompt).groups()
        view = await observe(variant, f"?brand={brand}&category={category}&max_price={price}")
        target = next(p for p in PRODUCTS if p.product_id == task.expected_id)
        assert "1 products" in view["agent_dom"] and target.name in view["agent_dom"] and f"${target.price_cents / 100:.2f}" in view["agent_dom"]
        assert len(view["ax_links"]) == 1


@pytest.mark.parametrize("variant", [VARIANT_ID, VARIANT_B_ID])
async def test_scripted_browser_navigators_complete_all_pilot_seeds_and_a_blind_one_fails(variant):
    from decimal import Decimal
    prepare_browser_environment()
    from browser_use import Browser
    from playwright.async_api import async_playwright
    async with local_storefront(variant) as url, async_playwright() as pw:
        session = Browser(**browser_options(url, pw.chromium.executable_path, profile("natural-shopping-v3-compat1")))
        try:
            await session.start()
            connection = await pw.chromium.connect_over_cdp(session.cdp_url)
            context = connection.contexts[0]
            page = context.pages[0] if context.pages else await context.new_page()

            async def answer():
                return {"product_id": (await page.locator("#product-id").inner_text()).strip(),
                        "price_cents": int(Decimal((await page.locator("#price").inner_text()).strip().removeprefix("$")) * 100),
                        "available": (await page.locator("#availability").inner_text()).strip() == "In stock"}
            for seed in PILOT_SEEDS:
                task = generate(seed, "discovery")
                target = next(p for p in PRODUCTS if p.product_id == task.expected_id)
                await page.goto(url)                                 # unfiltered: pick the card by its visible facts
                card = page.locator("article").filter(has_text=target.name).filter(has_text=f"{target.brand} · {target.category}")
                assert await card.count() == 1
                await card.locator("a[href^='/products/']").click()
                await page.wait_for_load_state("load")
                assert evaluate(await answer(), task).passed
                await page.goto(url)                                 # a blind navigator opening the first listing link fails
                await page.locator("article a[href^='/products/']").first.click()
                await page.wait_for_load_state("load")
                assert not evaluate(await answer(), task).passed
        finally:
            await session.kill()


# ---- end-to-end through the real runner, Browser Use and Chromium with a scripted mock model -----------------

def link_index(user_text, name, variant):
    pattern = (rf"\[(\d+)\]<a />\s*\n\s*{re.escape(name)}\n" if variant == VARIANT_ID
               else rf"\n{re.escape(name)}\n\*?\[(\d+)\]<a />\s*\n\s*View details\n")
    return int(re.search(pattern, user_text).group(1))


@pytest.mark.parametrize("variant", [VARIANT_ID, VARIANT_B_ID])
async def test_runner_records_non_target_visits_and_metrics_in_both_arms(tmp_path, monkeypatch, variant):
    import httpx
    from openai import DefaultAsyncHttpxClient
    from agent_readiness import runner
    from agent_readiness.capture import FULL_AGENT_SCHEMA_SHA256
    from tests.test_step_aware_guard import reply
    task = generate(2, "discovery")                       # City Tote (Fern, Bags, $24.00, unavailable)
    target = next(p for p in PRODUCTS if p.product_id == task.expected_id)
    other = PRODUCTS[0]
    monkeypatch.setenv("META_MODEL_API_KEY", "sentinel-model-credential-0123456789-not-real")
    calls = []

    def handler(request):
        body = json.loads(request.content)
        calls.append(body)
        user = body["messages"][1]["content"][0]["text"]
        n = len(calls)
        if n == 1:
            action = {"click": {"index": link_index(user, other.name, variant)}}
        elif n == 2:
            action = {"go_back": {}}
        elif n == 3:
            action = {"click": {"index": link_index(user, target.name, variant)}}
        else:
            action = {"done": {"data": {"product_id": target.product_id, "price_cents": target.price_cents, "available": target.available}}}
        return reply(n, action)
    original = runner.create_model

    def make(config, effective):
        model = original(config, effective)
        model.http_client = DefaultAsyncHttpxClient(transport=httpx.MockTransport(handler))
        sdk = model.get_client()
        sdk._platform = "Linux"
        model.get_client = lambda: sdk
        return model
    monkeypatch.setattr(runner, "create_model", make)
    path, record = await runner.run(mode="live", allow_model_calls=True, output=tmp_path, seed=2, kind="discovery",
                                    profile_id="natural-shopping-v3-compat1", storefront_variant=variant, max_steps=6,
                                    max_model_requests=6, timeout_seconds=120, expect_schema_sha256=FULL_AGENT_SCHEMA_SHA256,
                                    max_estimated_cost_usd=0.04, max_cumulative_estimated_cost_usd=0.25)
    assert record["status"] == "completed" and record["evaluation"]["passed"], record.get("errors")
    assert record["storefront_variant"] == variant and record["fidelity_violations"] is None and len(calls) == 4
    m = record["metrics"]
    nav = m["navigation"]
    assert [a["is_target"] for a in nav["product_page_arrivals"]] == [False, True]
    assert nav["non_target_product_page_arrivals"] == 1 and nav["distinct_non_target_products"] == 1
    assert nav["first_product_page_is_target"] is False and nav["target_page_reached"] is True
    assert nav["proposed_action_counts"]["click"] == 2 and nav["proposed_action_counts"]["go_back"] == 1
    assert m["task_success"]["evaluator_passed"] is True and m["strategy"]["used_search_or_filter"] is False
    assert m["tokens"]["prompt"] == 4 * 9000 and m["tokens"]["completion"] == 4 * 300 and m["tokens"]["reasoning"] == 4 * 200
    assert m["protocol"]["raw_protocol_compliant"] == 4 and m["cost"]["calculated_actual_usd"] > 0
    assert "private" not in json.dumps(m) and target.product_id in json.dumps(nav["product_page_arrivals"])
