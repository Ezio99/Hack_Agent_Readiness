"""Task 010: what the Browser Use agent view actually contains for each controlled factor (real Chromium; separate module so no sync-Playwright fixture is alive)."""
import re

import pytest

from agent_readiness.agent import browser_options, prepare_browser_environment, profile
from agent_readiness.environments.electronics.variants import make_variant
from tests.electronics_server import serve

pytestmark = pytest.mark.browser


@pytest.mark.parametrize("availability", ["listing", "detail"])
@pytest.mark.parametrize("specs", ["structured", "fragmented"])
async def test_browser_use_agent_view_reflects_each_controlled_factor(availability, specs):
    prepare_browser_environment()
    from browser_use import Browser
    from playwright.async_api import async_playwright
    with serve(make_variant(availability, specs)) as base:
        async with async_playwright() as pw:
            session = Browser(**browser_options(base + "/", pw.chromium.executable_path, profile("natural-shopping-v3-compat1")))
            try:
                await session.start()
                views = {}
                for name, path in (("listing", "/c/monitors"), ("detail", "/p/lumio-pro-27c")):
                    await session.navigate_to(base + path)
                    state = await session.get_browser_state_summary(include_screenshot=False, cached=False)
                    views[name] = state.dom_state.llm_representation()
            finally:
                await session.kill()
    listing, detail = views["listing"], views["detail"]
    assert ("In stock" in listing or "Out of stock" in listing) == (availability == "listing")
    assert "In stock" in detail                                                    # the detail page always states availability
    assert ("Refresh rate" in detail) == (specs == "structured") and ("USB-C" in detail) and ("refreshes at 120 Hz" in detail) == (specs == "fragmented")
    assert bool(re.search(r"(?m)^\s*120 Hz\s*$", listing)) == (specs == "structured")   # attribute chips only in the structured presentation (filter options say "… or more")
    assert "MN-3006" in detail and "MN-3006" not in listing                        # SKUs only on detail pages
