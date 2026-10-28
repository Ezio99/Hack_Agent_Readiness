"""Search, filter, sort and pagination for the storefront (presentation-side logic; the task oracle in tasks.py is deliberately independent)."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from .catalog import CATEGORIES, PRODUCTS, Product

PAGE_SIZE = 12
SORTS = {"featured": "Featured", "price_asc": "Price: low to high", "price_desc": "Price: high to low", "rating": "Customer rating", "name": "Name A–Z"}


class BadQuery(ValueError):
    pass


@dataclass(frozen=True)
class Filters:
    q: str = ""
    category: str = ""
    brand: str = ""
    max_price_cents: int | None = None
    in_stock: bool = False
    anc: bool = False
    form: str = ""
    min_ram: int | None = None
    min_screen: float | None = None
    usb_c: bool = False
    min_refresh: int | None = None
    sort: str = "featured"
    page: int = 1


def _int(v, name, lo=0, hi=10_000):
    if v in (None, ""):
        return None
    try:
        n = int(v)
    except ValueError:
        raise BadQuery(f"{name} must be a whole number")
    if not lo <= n <= hi:
        raise BadQuery(f"{name} is out of range")
    return n


def parse(params, category: str = "", allow_in_stock: bool = True) -> Filters:
    g = lambda k: (params.get(k) or "").strip()
    price = None
    if g("max_price"):
        try:
            d = Decimal(g("max_price")) * 100
        except InvalidOperation:
            raise BadQuery("max_price must be a number")
        if not d.is_finite() or d < 0 or d != d.to_integral_value() or d > 10_000_000:
            raise BadQuery("max_price must be a non-negative amount with at most two decimals")
        price = int(d)
    screen = None
    if g("min_screen"):
        try:
            screen = float(g("min_screen"))
        except ValueError:
            raise BadQuery("min_screen must be a number")
    sort = g("sort") or "featured"
    if sort not in SORTS:
        raise BadQuery("unknown sort")
    cat = category or g("category")
    if cat and cat not in CATEGORIES:
        raise BadQuery("unknown category")
    return Filters(q=g("q")[:100], category=cat, brand=g("brand")[:40], max_price_cents=price,
                   in_stock=allow_in_stock and g("in_stock") in ("1", "on", "true"), anc=g("anc") in ("1", "on", "true"), form=g("form")[:20],
                   min_ram=_int(g("min_ram"), "min_ram"), min_screen=screen, usb_c=g("usb_c") in ("1", "on", "true"),
                   min_refresh=_int(g("min_refresh"), "min_refresh"), sort=sort, page=max(1, _int(g("page"), "page", 1, 1000) or 1))


def _keywords(p: Product) -> str:
    extra = []
    if p.spec("anc"):
        extra.append("anc active noise cancelling")
    if p.spec("usb_c"):
        extra.append("usb-c usbc")
    return " ".join([p.sku, p.name, p.brand, p.category, p.spec("kind") or "", p.spec("form") or "", p.spec("cpu") or "", p.spec("connector") or "", *extra]).lower()


def matches(p: Product, f: Filters) -> bool:
    if f.category and p.category != f.category:
        return False
    if f.q and not all(tok in _keywords(p) for tok in f.q.lower().split()):
        return False
    if f.brand and p.brand != f.brand:
        return False
    if f.max_price_cents is not None and p.price_cents > f.max_price_cents:
        return False
    if f.in_stock and not p.in_stock:
        return False
    if f.anc and not p.spec("anc"):
        return False
    if f.form and p.spec("form") != f.form:
        return False
    if f.min_ram is not None and (p.spec("ram_gb") or 0) < f.min_ram:
        return False
    if f.min_screen is not None and (p.spec("size_in") or p.spec("screen_in") or 0) < f.min_screen:
        return False
    if f.usb_c and not p.spec("usb_c"):
        return False
    if f.min_refresh is not None and (p.spec("refresh_hz") or 0) < f.min_refresh:
        return False
    return True


def order(items: list[Product], sort: str) -> list[Product]:
    key = {"featured": lambda p: (p.featured_rank, p.sku), "price_asc": lambda p: (p.price_cents, p.sku), "price_desc": lambda p: (-p.price_cents, p.sku),
           "rating": lambda p: (-p.rating, p.sku), "name": lambda p: (p.name.lower(), p.sku)}[sort]
    return sorted(items, key=key)


def run(f: Filters) -> tuple[list[Product], int, int]:
    """(products on the requested page, total matches, total pages)."""
    found = order([p for p in PRODUCTS if matches(p, f)], f.sort)
    pages = max(1, -(-len(found) // PAGE_SIZE))
    page = min(f.page, pages)
    return found[(page - 1) * PAGE_SIZE: page * PAGE_SIZE], len(found), pages
