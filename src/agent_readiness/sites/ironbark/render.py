"""Render every page of the Ironbark storefront for one variant. Pure and deterministic: the same variant always yields byte-identical pages and assets."""
from __future__ import annotations

import hashlib
from datetime import timedelta
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from . import art, data as D
from .variants import Variant

HERE = Path(__file__).parent
NAV = [("/hire", "Hire equipment"), ("/accessories", "Accessories"), ("/kits", "Kits"), ("/hire-terms", "Hire terms"), ("/about", "About"), ("/contact", "Contact")]
SORTS = [("default", "Featured order"), ("price-asc", "Price: low to high"), ("price-desc", "Price: high to low"), ("name", "Name A to Z")]
FEATURED = ("IB-DRL-002", "IB-DRL-003", "IB-CUT-001", "IB-LND-003", "IB-ACC-001", "IB-GRD-001")

env = Environment(loader=FileSystemLoader(HERE / "templates"), autoescape=select_autoescape(["html"]), trim_blocks=True, lstrip_blocks=True, keep_trailing_newline=True)
env.globals.update(B=D.BUSINESS, money=D.money, fmt_date=D.fmt_date, AS_OF=D.AS_OF, LAST_DAY=D.LAST_DAY, CATEGORIES=D.CATEGORIES, PRODUCTS=D.PRODUCTS, ACCESSORIES=D.ACCESSORIES, JOBS=D.JOBS, NAV=NAV,
                   DELIVERY=D.DELIVERY_FEES, WAIVER=D.WAIVER_RATE, BUNDLE_DISCOUNT=D.BUNDLE_DISCOUNT, GST=D.GST_NOTE, WEEKEND=D.WEEKEND_RULE, SORTS=SORTS)


def product_view(p: D.Product) -> dict:
    free = D.units_free(p, D.AS_OF)
    return {"p": p, "cat": D.CATEGORY_BY_SLUG[p.category], "url": f"/hire/{p.slug}", "img": f"/assets/img/{p.slug}-1.svg", "available_today": free > 0,
            "next_free": D.next_free_day(p) if free == 0 else None, "next_booked": D.next_booked_day(p) if free > 0 else None}


def _views(products) -> list[dict]:
    return [product_view(p) for p in products]


def _page(name: str, v: Variant, **ctx) -> str:
    return env.get_template(name).render(v=v, **ctx)


def _weeks(p: D.Product) -> list[dict]:
    rows = []
    for w in range(D.WINDOW_DAYS // 7):
        start = D.AS_OF + timedelta(days=7 * w)
        cells = []
        for i in range(7):
            day = start + timedelta(days=i)
            free = D.units_free(p, day)
            cls = "free" if free == p.units else "booked" if free == 0 else "partial"
            text = "Booked" if free == 0 else ("Free" if p.units == 1 else f"{free} free")
            cells.append({"date": D.fmt_date(day, weekday=False), "text": text, "cls": cls})
        rows.append({"label": D.fmt_date(start, weekday=False), "cells": cells})
    return rows


def _cost_rows(p: D.Product) -> list[dict]:
    periods = [(f"{n}d", f"{n} day{'s' if n != 1 else ''}") for n in (1, 2, 3) if n >= p.min_days] + [("weekend", "Weekend (Fri to Mon)"), ("7d", "1 week")]
    rows = []
    for key, label in periods:
        base, with_w, with_wd = D.quote(p, key), D.quote(p, key, waiver=True), D.quote(p, key, waiver=True, delivery=True)
        rows.append({"label": label, "hire": base["hire"], "plain": base["total"], "waiver": with_w["total"], "waiver_delivery": with_wd["total"]})
    return rows


def _kits() -> list[dict]:
    out = []
    for b in D.BUNDLES:
        item = lambda i: {"name": D.BY_ID[i].name, "url": (f"/hire/{D.BY_ID[i].slug}" if i.startswith("IB-DRL") or i.startswith("IB-CUT") else f"/accessories/{D.BY_ID[i].slug}"), "price": getattr(D.BY_ID[i], "price", None)}
        out.append({"b": b, "rates": D.bundle_rates(b), "hire": [item(i) for i in b.hire], "included": [item(i) for i in b.hire_acc], "buy": [item(i) for i in b.buy]})
    return out


def render_pages(v: Variant) -> dict[str, str]:
    kits = _kits()
    common = {"KITS": kits}
    pages: dict[str, str] = {}
    pages["/"] = _page("home.html", v, current="/", title=None, description=D.BUSINESS["tagline"], FEATURED=_views([D.BY_ID[i] for i in FEATURED]), **common)

    def catalogue(path, heading, intro, items, sort="default", category=None, crumbs=None):
        pages[path] = _page("catalogue.html", v, current="/hire", title=heading, description=intro, heading=heading, intro=intro, items=_views(items), sort=sort, category=category,
                            CRUMBS=crumbs or [("/", "Home"), (None, "Hire equipment")])
    orders = {"default": list(D.PRODUCTS), "price-asc": sorted(D.PRODUCTS, key=lambda p: (p.daily, p.id)), "price-desc": sorted(D.PRODUCTS, key=lambda p: (-p.daily, p.id)), "name": sorted(D.PRODUCTS, key=lambda p: p.name.lower())}
    catalogue("/hire", "Hire equipment", f"All {len(D.PRODUCTS)} machines in our yard, with daily, weekend and weekly rates.", orders["default"])
    for key, label in SORTS[1:]:
        catalogue(f"/hire/sort/{key}", "Hire equipment", f"All {len(D.PRODUCTS)} machines, sorted: {label.lower()}.", orders[key], sort=key)
    for c in D.CATEGORIES:
        catalogue(f"/hire/category/{c.slug}", c.name, c.blurb, [p for p in D.PRODUCTS if p.category == c.slug], category=c,
                  crumbs=[("/", "Home"), ("/hire", "Hire equipment"), (None, c.name)])
    for p in D.PRODUCTS:
        pv = product_view(p)
        glance = {"periods": D.unavailable_periods(p), "weekend": D.next_free_weekend(p)} if v.avail else None
        accs = D.compatible_accessories(p) if v.compat else None
        pages[f"/hire/{p.slug}"] = _page("product.html", v, current="/hire", title=p.name, description=p.summary, pv=pv, p=p, cat=pv["cat"], glance=glance, cost_rows=_cost_rows(p) if v.cost else None,
                                          accessories=accs, kits=D.kits_including(p.id) if v.compat else None, others=[o for o in D.PRODUCTS if o.category == p.category and o.id != p.id])
        pages[f"/hire/{p.slug}/availability"] = _page("availability.html", v, current="/hire", title=f"Availability: {p.name}", description=f"Booking calendar for {p.name}.", p=p, weeks=_weeks(p))
    pages["/accessories"] = _page("accessories.html", v, current="/accessories", title="Accessories", description="Blades, bits, chisels, leads and safety gear.")
    for a in D.ACCESSORIES:
        pages[f"/accessories/{a.slug}"] = _page("accessory.html", v, current="/accessories", title=a.name, description=a.summary, a=a, products=D.compatible_products(a) if v.compat else None,
                                                 kits=D.kits_including(a.id) if v.compat else None)
    pages["/kits"] = _page("kits.html", v, current="/kits", title="Hire kits", description="Equipment and consumables grouped for common jobs.", **common)
    pages["/hire-terms"] = _page("terms.html", v, current="/hire-terms", title="Hire terms and pricing", description="Hire periods, weekend rates, damage waiver, delivery and deposits.")
    pages["/about"] = _page("about.html", v, current="/about", title="About us", description="A family-run equipment hire business.")
    pages["/contact"] = _page("contact.html", v, current="/contact", title="Contact and booking", description="How to book equipment.")
    if v.discover:
        pages["/jobs"] = _page("jobs.html", v, current="/jobs", title="Browse by job", description="Find equipment by the job you are doing.")
        for slug, (jt, ji) in D.JOBS.items():
            pages[f"/jobs/{slug}"] = _page("job.html", v, current="/jobs", title=jt, description=ji, intro=ji, items=_views([p for p in D.PRODUCTS if slug in p.jobs]))
    return pages


def render_assets() -> dict[str, bytes]:
    a: dict[str, bytes] = {"/assets/site.css": (HERE / "static" / "site.css").read_bytes(), "/assets/logo.svg": art.logo_svg().encode(), "/assets/img/hero.svg": art.hero_image().encode()}
    for p in D.PRODUCTS:
        a[f"/assets/img/{p.slug}-1.svg"] = art.product_image_main(p).encode()
        a[f"/assets/img/{p.slug}-2.svg"] = art.product_image_spec(p).encode()
    for x in D.ACCESSORIES:
        a[f"/assets/img/{x.slug}.svg"] = art.accessory_image(x).encode()
    for b in D.BUNDLES:
        a[f"/assets/img/{b.slug}.svg"] = art.bundle_image(b).encode()
    for c in D.CATEGORIES:
        a[f"/assets/img/cat-{c.slug}.svg"] = art.category_image(c.slug).encode()
    return a


def fingerprint(files: dict[str, bytes]) -> str:
    h = hashlib.sha256()
    for path in sorted(files):
        h.update(path.encode() + b"\0" + hashlib.sha256(files[path]).digest())
    return h.hexdigest()
