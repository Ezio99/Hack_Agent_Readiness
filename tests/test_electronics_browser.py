"""Task 010 in real Chromium (credential-free): scripted navigators through the live pages in every variant, real UI interaction, mobile layout,
keyboard/accessibility basics and the Browser Use agent view. Scripted runs are smoke checks, NOT model task success."""
import re

import pytest
from playwright.sync_api import sync_playwright

from agent_readiness.environments.electronics import catalog as C
from agent_readiness.environments.electronics.scripted import solve
from agent_readiness.environments.electronics.variants import all_variants, make_variant
from agent_readiness.suite import core, registry
from tests.electronics_server import serve

pytestmark = pytest.mark.browser
registry.load_all()
INSTANCES = registry.instances()
VARIANTS = all_variants()


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as pw:
        b = pw.chromium.launch(args=["--no-sandbox"])
        yield b
        b.close()


@pytest.mark.parametrize("variant", VARIANTS, ids=lambda v: v.variant_id.split("/")[1])
def test_every_task_is_solvable_through_the_real_browser_and_graded_independently(browser, variant):
    with serve(variant) as base:
        page = browser.new_context(viewport={"width": 1280, "height": 900}).new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        for inst in INSTANCES:
            visited = []

            def fetch(path):
                visited.append(path)
                response = page.goto(base + path)
                assert response.status == 200, (path, response.status)
                return page.content()
            answer = solve(inst.spec.template_id, dict(inst.spec.parameters), inst.spec.outcome_type, fetch)
            result = core.evaluate(inst, answer, variant, visited)
            assert result.passed and result.evidence_backed, (inst.spec.task_id, result.reasons, result.missing_evidence)
            # a deliberately wrong answer from the same run still fails: the verdict does not depend on the navigator succeeding
            wrong = dict(answer)
            if "products" in wrong:
                wrong = {"products": []}
            elif "sku" in wrong:
                wrong = {**wrong, "sku": "HP-1009"}
            else:
                wrong = {**wrong, "more_ram": "tie" if wrong["more_ram"] != "tie" else "a"}
            assert not core.evaluate(inst, wrong, variant, visited).passed
        assert not errors


def test_a_visitor_can_browse_search_filter_sort_page_and_use_policy_links(browser):
    with serve(make_variant("listing", "structured")) as base:
        page = browser.new_context(viewport={"width": 1280, "height": 900}).new_page()
        page.goto(base)
        page.get_by_role("navigation", name="Main").get_by_role("link", name="Headphones").click()
        assert page.url.endswith("/c/headphones") and page.locator("h1").inner_text() == "Headphones"
        assert "Showing 1–12 of 14" in page.get_by_role("status").inner_text()
        page.get_by_label("Active noise cancelling").check()
        page.get_by_label("Sort by").select_option("price_asc")
        page.get_by_role("button", name="Apply").click()
        assert "anc=1" in page.url and "sort=price_asc" in page.url
        prices = [float(t.replace("A$", "").replace(",", "")) for t in page.locator(".card .price").all_inner_texts()]
        assert prices == sorted(prices) and len(prices) == 8
        page.get_by_label("In stock only").check()
        page.get_by_role("button", name="Apply").click()
        assert page.locator(".card .stock.out").count() == 0 and page.locator(".card").count() == 5
        page.goto(base + "/c/headphones")
        page.get_by_role("link", name="Next page →").click()
        assert "page=2" in page.url and page.locator(".card").count() == 2
        page.go_back(); page.go_forward()
        assert "page=2" in page.url
        page.get_by_role("link", name="Lumio Hush 3").click() if page.get_by_role("link", name="Lumio Hush 3").count() else page.goto(base + "/p/lumio-hush-3")
        assert page.locator("h1").inner_text() == "Lumio Hush 3" and page.locator("#availability").inner_text() == "In stock"
        page.get_by_role("navigation", name="Breadcrumb").get_by_role("link", name="Headphones").click()
        assert page.url.endswith("/c/headphones")
        page.get_by_role("link", name="Returns policy").last.click()
        assert page.url.endswith("/help/returns") and "30 days" in page.inner_text("main")
        page.get_by_role("link", name="Delivery information").last.click()
        assert page.url.endswith("/help/delivery") and "A$29.00" in page.inner_text("main")
        page.get_by_role("searchbox", name="Search products").fill("usb-c charger")
        page.get_by_role("button", name="Search").click()
        assert "/search?q=usb-c+charger" in page.url and page.locator(".card").count() >= 3


def test_detail_only_availability_variant_shows_stock_only_after_opening_a_product(browser):
    with serve(make_variant("detail", "structured")) as base:
        page = browser.new_context().new_page()
        page.goto(base + "/c/monitors")
        assert page.locator(".stock").count() == 0 and page.get_by_label("In stock only").count() == 0
        page.get_by_role("link", name="Aurel Vision 27C").click()
        assert page.locator("#availability").inner_text() == "Out of stock"


@pytest.mark.parametrize("path", ["/", "/c/laptops", "/c/monitors?sort=price_asc", "/p/kestrel-air-14", "/help/delivery", "/search?q=anc"])
@pytest.mark.parametrize("specs", ["structured", "fragmented"])
def test_mobile_layout_has_no_horizontal_scroll_and_controls_stay_usable(browser, path, specs):
    with serve(make_variant("listing", specs)) as base:
        page = browser.new_context(viewport={"width": 390, "height": 844}, is_mobile=True).new_page()
        page.goto(base + path)
        assert page.evaluate("document.documentElement.scrollWidth") <= 391
        assert page.get_by_role("searchbox", name="Search products").is_visible()
        box = page.get_by_role("button", name="Search").bounding_box()
        assert box and box["width"] >= 40 and box["height"] >= 30
        if path.startswith("/c/"):
            page.get_by_label("Sort by").select_option("price_desc")
            page.get_by_role("button", name="Apply").click()
            assert "sort=price_desc" in page.url


def test_keyboard_and_semantics_basics(browser):
    with serve(make_variant("listing", "structured")) as base:
        page = browser.new_context(viewport={"width": 1280, "height": 900}).new_page()
        for path in ("/", "/c/headphones", "/p/aurel-quiet-700", "/help/returns"):
            page.goto(base + path)
            page.keyboard.press("Tab")
            assert page.evaluate("document.activeElement.className") == "skip" and page.evaluate("document.activeElement.getBoundingClientRect().left") >= 0   # skip link appears on focus
            page.keyboard.press("Enter")
            assert page.evaluate("location.hash") == "#main"
            names = page.evaluate("""() => [...document.querySelectorAll('a,button,input,select')].filter(e => e.type !== 'hidden').map(e =>
                (e.getAttribute('aria-label') || e.innerText || (e.labels && e.labels[0] && e.labels[0].innerText) || e.value || '').trim()).filter(n => !n)""")
            assert names == [], (path, names)                                 # every control and link has an accessible name
            assert page.evaluate("document.querySelectorAll('h1').length") == 1 and page.evaluate("document.documentElement.lang") == "en"
        page.goto(base + "/c/laptops")
        for _ in range(40):                                                    # focus never gets trapped and always lands on something visible
            page.keyboard.press("Tab")
            assert page.evaluate("document.activeElement.getBoundingClientRect().width") > 0
