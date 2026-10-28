"""Credential-free scripted navigators for the electronics-v1 P0 tasks (T1-T4).

These are *scripted smoke solvers*, not model agents: they prove that every task is feasible through the real pages in every variant and that the evaluator
accepts the correct result. A passing scripted run says nothing about how any AI agent would perform. The navigator only uses what a visitor can see
(page text); it never imports the oracle or touches truth. ``fetch(path_with_query) -> html`` is injected so the same code drives an in-process
HTTP client and a real browser."""
from __future__ import annotations

import html as htmllib
import re
from typing import Callable

Fetch = Callable[[str], str]
TAGS = re.compile(r"<[^>]+>")


def text(fragment: str) -> str:
    return re.sub(r"\s+", " ", htmllib.unescape(TAGS.sub(" ", fragment))).strip()


def slugs(page: str) -> list[str]:
    return list(dict.fromkeys(re.findall(r'<h2><a href="/p/([a-z0-9-]+)">', page)))


def next_page(page: str) -> str | None:
    m = re.search(r'<a href="([^"]+)" rel="next">', page)
    return htmllib.unescape(m.group(1)) if m else None


def walk_listing(fetch: Fetch, first: str) -> list[str]:
    """All product slugs across every page of a listing, following the real 'Next page' links."""
    found, url = [], first
    while url:
        page = fetch(url)
        found += slugs(page)
        nxt = next_page(page)
        url = (url.split("?", 1)[0] + nxt[nxt.index("?"):]) if nxt and "?" in nxt else (nxt if nxt else None)
        if nxt and not nxt.startswith("/"):
            url = first.split("?", 1)[0] + "?" + nxt.split("?", 1)[-1]
    return found


def read_product(fetch: Fetch, slug: str) -> dict:
    page = fetch(f"/p/{slug}")
    body = text(page)
    sku = re.search(r'id="sku">([A-Z]{2}-\d{4})<', page).group(1)
    price = int(round(float(re.search(r'id="price">A\$([\d,]+\.\d{2})<', page).group(1).replace(",", "")) * 100))
    stock = re.search(r'id="availability">([^<]+)<', page).group(1).strip()
    crumbs = re.search(r'aria-label="Breadcrumb">(.*?)</nav>', page, re.S).group(1)
    category = re.search(r'<a href="/c/([a-z]+)">', crumbs).group(1)
    ram = re.search(r"Memory \(RAM\)\s*(\d+) GB", body) or re.search(r"(\d+) GB of memory", body)
    battery = re.search(r"Battery life \(advertised\)\s*up to (\d+) hours", body) or re.search(r"up to (\d+) hours (?:of battery|of listening)", body) \
        or re.search(r"quotes up to (\d+) hours", body)
    return {"slug": slug, "sku": sku, "price_cents": price, "in_stock": stock == "In stock", "category": category,
            "ram_gb": int(ram.group(1)) if ram else None, "battery_hours": int(battery.group(1)) if battery else None}


def find_slug(fetch: Fetch, name: str) -> str:
    from urllib.parse import quote_plus
    page = fetch(f"/search?q={quote_plus(name)}")
    for slug in slugs(page):
        if re.search(rf'<a href="/p/{slug}">{re.escape(htmllib.escape(name))}</a>', page):
            return slug
    raise LookupError(f"product {name!r} not found via search")


def solve_t1(fetch: Fetch, params: dict, outcome: str) -> dict:
    budget = params["budget_cents"]
    found = walk_listing(fetch, f"/c/headphones?anc=1&max_price={budget / 100:.2f}&sort=price_asc")
    products = []
    for slug in found:                              # always confirm stock on the product page (works in every availability variant)
        p = read_product(fetch, slug)
        if p["in_stock"] and p["price_cents"] <= budget:
            products.append({"sku": p["sku"], "price_cents": p["price_cents"]})
            if outcome == "any_valid":
                break
    return {"products": products}


def solve_t2(fetch: Fetch, params: dict) -> dict:
    a, b = (read_product(fetch, find_slug(fetch, params[k])) for k in ("laptop_a", "laptop_b"))
    cmp = lambda x, y: "tie" if x == y else ("a" if x > y else "b")
    side = lambda p: {"sku": p["sku"], "ram_gb": p["ram_gb"], "battery_hours": p["battery_hours"]}
    return {"a": side(a), "b": side(b), "more_ram": cmp(a["ram_gb"], b["ram_gb"]), "longer_battery": cmp(a["battery_hours"], b["battery_hours"])}


def solve_t3(fetch: Fetch, params: dict) -> dict:
    size, hz = params["min_size_in"], params["min_refresh_hz"]
    for slug in walk_listing(fetch, f"/c/monitors?min_screen={size:g}&usb_c=1&min_refresh={hz}&sort=price_asc"):
        p = read_product(fetch, slug)               # cheapest first; the first one that is actually in stock wins
        if p["in_stock"]:
            return {"sku": p["sku"], "price_cents": p["price_cents"]}
    raise LookupError("no eligible monitor found")


def solve_t4(fetch: Fetch, params: dict) -> dict:
    from .catalog import BY_SKU
    p = read_product(fetch, BY_SKU[params["sku"]].slug)             # the task names the product; the slug is its public URL
    cat_name = {"headphones": "Headphones", "laptops": "Laptops", "monitors": "Monitors", "accessories": "Accessories"}[p["category"]]
    returns = fetch("/help/returns")
    row = re.search(rf"<th scope=\"row\">{cat_name}</th><td>(\d+) days</td><td>(\d+)%</td>", returns)
    delivery = fetch("/help/delivery")
    cost = threshold = lo = hi = None
    for cls_row in re.findall(r"<tr><th scope=\"row\">.*?</tr>", delivery):
        cells = [text(c) for c in re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", cls_row)]
        if cat_name in [c.strip() for c in cells[1].split(",")]:
            money = lambda s: int(round(float(s.replace("A$", "").replace(",", "")) * 100))
            cost, threshold = money(cells[2]), money(cells[3])
            lo, hi = (int(x) for x in re.match(r"(\d+)–(\d+) business days", cells[4]).groups())
    return {"sku": p["sku"], "return_window_days": int(row.group(1)), "restocking_fee_percent": int(row.group(2)),
            "delivery_cost_cents": 0 if p["price_cents"] >= threshold else cost, "delivery_days_min": lo, "delivery_days_max": hi}


def solve(template_id: str, params: dict, outcome: str, fetch: Fetch) -> dict:
    if template_id == "t1-discovery-anc-headphones":
        return solve_t1(fetch, params, outcome)
    if template_id == "t2-compare-laptops":
        return solve_t2(fetch, params)
    if template_id == "t3-cheapest-monitor":
        return solve_t3(fetch, params)
    if template_id == "t4-policy-delivery":
        return solve_t4(fetch, params)
    raise KeyError(template_id)
