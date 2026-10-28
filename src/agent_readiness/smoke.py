"""Deterministic browser wiring exercise. No LLM or private inventory access."""
import asyncio
from decimal import Decimal
import re
from .agent import browser_options, prepare_browser_environment
from .contracts import PublicTask
from .recorder import Recorder


async def smoke(task: PublicTask, url: str, recorder: Recorder, effective: dict):
    prepare_browser_environment()
    from browser_use import Browser
    from playwright.async_api import async_playwright
    async with async_playwright() as pw:
        session = Browser(**browser_options(url, pw.chromium.executable_path, effective))
        actions = 0
        steps = 0
        try:
            await session.start()
            connection = await pw.chromium.connect_over_cdp(session.cdp_url)
            recorder.event("browser_version", version=connection.version)
            context = connection.contexts[0]
            page = context.pages[0] if context.pages else await context.new_page()
            page.set_default_timeout(effective["step_timeout_seconds"] * 1000)
            responses = []
            page.on("response", lambda response: responses.append(response))

            async def capture(label):
                nonlocal steps
                steps += 1
                await page.wait_for_load_state("load")
                state = await session.get_browser_state_summary(include_screenshot=True, cached=False)
                cdp = await context.new_cdp_session(page)
                try:
                    ax = await cdp.send("Accessibility.getFullAXTree")
                    snapshot = await cdp.send("DOMSnapshot.captureSnapshot", {"computedStyles": []})
                finally:
                    await cdp.detach()
                png = await page.screenshot(full_page=True)
                (recorder.path / f"{label}.png").write_bytes(png)
                payloads = []
                for response in responses:
                    payloads.append({"url": response.url, "status": response.status,
                                     "body": await response.text()})
                responses.clear()
                observation = dict(url=page.url, html=await page.content(),
                                   accessibility=ax, dom_snapshot=snapshot, payloads=payloads,
                                   agent_dom=state.dom_state.llm_representation(),
                                   screenshot=f"{label}.png",
                                   agent_screenshot=recorder.image(f"{label}-agent", state.screenshot) if state.screenshot else None)
                recorder.write(f"{label}.json", observation)
                recorder.event("observation", step=steps, **observation)
                return observation

            recorder.event("browser_action", action="navigate", url=url)
            await page.goto(url)
            actions += 1
            await capture("initial-listing")
            if steps >= effective["max_steps"]:
                return dict(answer=None, status="step_limit", stop_reason="step_limit", action_count=actions, steps=steps, usage=None, errors=[])
            if task.kind == "instock_max":
                return await instock_max_walk(page, task, capture, recorder, effective, actions, steps_ref=lambda: steps)
            if task.kind == "availability":
                name = re.fullmatch(r"Locate (.+)\. Return its product ID, price in integer cents, and whether it is currently available\.", task.prompt).group(1)
                recorder.event("browser_action", action="search", value=name)
                await page.get_by_label("Search products", exact=True).fill(name)
                actions += 1
            else:
                match = re.match(r"Find the (.+) product in (.+) costing at most \$(\d+\.\d{2}) AUD\.", task.prompt)
                brand, category, budget = match.groups()
                recorder.event("browser_action", action="filter", brand=brand, category=category, max_price=budget)
                await page.get_by_label("Brand", exact=True).select_option(label=brand)
                await page.get_by_label("Category", exact=True).select_option(label=category)
                await page.get_by_label("Maximum price (AUD)", exact=True).fill(budget)
                actions += 3
            await page.get_by_role("button", name="Apply filters").click()
            actions += 1
            await capture("filtered-listing")
            if steps >= effective["max_steps"]:
                return dict(answer=None, status="step_limit", stop_reason="step_limit", action_count=actions, steps=steps, usage=None, errors=[])
            links = page.locator("article a[href^='/products/']")  # arm-independent: the card's only product link
            if await links.count() != 1:
                raise RuntimeError("Smoke expected a unique candidate from public task constraints")
            recorder.event("browser_action", action="open_detail", href=await links.first.get_attribute("href"))
            await links.first.click()
            actions += 1
            await capture("detail")
            answer = dict(product_id=(await page.locator("#product-id").inner_text()).strip(),
                          price_cents=int(Decimal((await page.locator("#price").inner_text()).strip().removeprefix("$")) * 100),
                          available=(await page.locator("#availability").inner_text()).strip() == "In stock")
            recorder.event("final_answer", answer=answer)
            return dict(answer=answer, status="completed", stop_reason="scripted_smoke_done",
                        action_count=actions, steps=steps, usage=None, errors=[])
        finally:
            try:
                await asyncio.wait_for(session.kill(), 15)
            except Exception as exc:
                recorder.event("cleanup_error", error=str(exc))


async def instock_max_walk(page, task, capture, recorder, effective, actions, steps_ref):
    """Scripted wiring check for the in-stock-maximum task: walk down by price, using listing availability when it is
    shown and opening detail pages when it is not. (The independent oracle lives in ``oracle.py``.)"""
    scope = re.match(r"Find the most expensive (.+) product that is currently in stock\.", task.prompt).group(1)
    brands = await page.locator("#brand option").all_inner_texts()
    recorder.event("browser_action", action="filter", scope=scope)
    await page.get_by_label("Brand" if scope in brands else "Category", exact=True).select_option(label=scope)
    await page.get_by_role("button", name="Apply filters").click()
    actions += 2
    await capture("filtered-listing")
    cards = await page.eval_on_selector_all("article", """els => els.map(e => ({
        href: e.querySelector("a[href^='/products/']").getAttribute("href"), text: e.innerText}))""")
    for card in cards:
        card["price"] = Decimal(re.search(r"\$(\d+\.\d{2})", card["text"]).group(1))
    cards.sort(key=lambda c: -c["price"])
    for card in cards:
        if "Out of stock" in card["text"]:
            continue
        if steps_ref() >= effective["max_steps"]:
            return dict(answer=None, status="step_limit", stop_reason="step_limit", action_count=actions, steps=steps_ref(), usage=None, errors=[])
        recorder.event("browser_action", action="open_detail", href=card["href"])
        await page.locator(f"a[href='{card['href']}']").click()
        actions += 1
        await capture("detail")
        if (await page.locator("#availability").inner_text()).strip() == "In stock":
            answer = dict(product_id=(await page.locator("#product-id").inner_text()).strip(),
                          price_cents=int(Decimal((await page.locator("#price").inner_text()).strip().removeprefix("$")) * 100),
                          available=True)
            recorder.event("final_answer", answer=answer)
            return dict(answer=answer, status="completed", stop_reason="scripted_smoke_done",
                        action_count=actions, steps=steps_ref(), usage=None, errors=[])
        await page.go_back()
        await page.wait_for_load_state("load")
        actions += 1
        await capture("listing-return")
    return dict(answer=None, status="agent_failure", stop_reason="no_in_stock_product", action_count=actions, steps=steps_ref(), usage=None, errors=[])
