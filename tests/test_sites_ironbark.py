"""Ironbark Hire Co. storefront (candidate Experiment-2 site): data consistency, navigation, page-vs-data truth, determinism, variant isolation, server behaviour and grading consistency.
All offline; no model, no network (the server test uses a loopback socket)."""
import json
import re
import threading
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import timedelta
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urldefrag, urlparse

import pytest
from bs4 import BeautifulSoup

from agent_readiness.sites.ironbark import data as D, grading, variants as V
from agent_readiness.sites.ironbark.build import build_site, make_handler, serve, site_fingerprint, write_site

CATALOGUE = Path(D.__file__).with_name("catalogue.json")
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}


@pytest.fixture(scope="module")
def sites():
    cache = {}
    def get(spec: str = "control") -> dict[str, bytes]:
        if spec not in cache:
            cache[spec] = build_site(V.parse(spec))
        return cache[spec]
    return get


def pages_of(files):
    return {p: b.decode() for p, b in files.items() if not p.startswith("/assets/")}


def soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "html.parser")


def text(el) -> str:
    return re.sub(r"\s+", " ", el.get_text(" ", strip=True))


# ---------------------------------------------------------------------------------------------------------------------------------------------------------------- data consistency
def test_catalogue_has_sixteen_products_with_unique_stable_ids_and_slugs():
    assert len(D.PRODUCTS) == 16
    ids = [x.id for x in [*D.PRODUCTS, *D.ACCESSORIES, *D.BUNDLES]]
    assert len(ids) == len(set(ids)) and all(re.fullmatch(r"IB-[A-Z]{3}-\d{3}", i) for i in ids)
    slugs = [x.slug for x in [*D.PRODUCTS, *D.ACCESSORIES, *D.BUNDLES]]
    assert len(slugs) == len(set(slugs)) and all(re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", s) for s in slugs)
    assert {p.category for p in D.PRODUCTS} == {c.slug for c in D.CATEGORIES} and all(sum(p.category == c.slug for p in D.PRODUCTS) >= 2 for c in D.CATEGORIES)


def test_prices_and_terms_are_internally_consistent():
    for p in D.PRODUCTS:
        assert p.daily <= p.weekend <= 2 * p.daily + 10 and p.weekend < p.weekly < 7 * p.daily, p.id          # a weekend costs more than a day, a week less than seven days
        assert p.deposit >= p.daily and p.min_days >= 1 and p.units >= 1 and p.delivery in ("optional", "required") and p.delivery_class in D.DELIVERY_FEES
        assert p.delivery == "optional" or p.delivery_class == "machine", f"{p.id}: required delivery implies a machine delivery"
        assert p.weight_kg > 0 and p.specs and p.included and p.conditions and p.also_called and p.jobs
        assert any(label == "Weight" or label.startswith("Weight") for label, _ in p.specs) or p.weight_kg > 0
    assert D.WAIVER_RATE == 0.10 and D.DELIVERY_FEES == {"courier": 45, "machine": 120}


def test_cross_references_resolve():
    jobs_used = {j for p in D.PRODUCTS for j in p.jobs}
    assert jobs_used == set(D.JOBS), "every job has at least one product and every product job exists"
    tags = {t for p in D.PRODUCTS for t in p.compat}
    for a in D.ACCESSORIES:
        assert all(t in tags for t in a.fits), a.id
        assert a.kind in ("purchase", "hire") and a.price > 0
        assert a.fits == () or D.compatible_products(a), f"{a.id} fits nothing"
    for b in D.BUNDLES:
        assert all(i in D.BY_ID for i in (*b.hire, *b.hire_acc, *b.buy))
        assert all(i.startswith("IB-") and not D.BY_ID[i].__class__.__name__ == "Bundle" for i in (*b.hire, *b.hire_acc, *b.buy))
        assert D.bundle_rates(b)["hire"]["daily"] < D.bundle_rates(b)["list"]["daily"]


def test_committed_catalogue_json_is_the_export_of_the_data_module():
    assert json.loads(CATALOGUE.read_text()) == json.loads(json.dumps(D.export_catalogue(), ensure_ascii=False)), "regenerate with: readiness site catalogue --out src/agent_readiness/sites/ironbark/catalogue.json"


def test_bookings_are_deterministic_inside_the_window_and_leave_real_variety():
    assert D.bookings(D.PRODUCTS[0]) == D.bookings(D.PRODUCTS[0])
    for p in D.PRODUCTS:
        assert all(0 <= a <= b < D.WINDOW_DAYS and 0 <= u < p.units for u, a, b in D.bookings(p))
    today = [D.available_on(p, D.AS_OF) for p in D.PRODUCTS]
    assert any(today) and not all(today), "some items are booked today and some are free"
    assert 0 < len(grading.available_for_weekend(D.AS_OF + timedelta(days=4))) < len(D.PRODUCTS)
    with pytest.raises(ValueError):
        D.units_free(D.PRODUCTS[0], D.LAST_DAY + timedelta(days=1))


def test_quote_rules():
    saw, scaffold, drill = D.PRODUCT_BY_SLUG["wet-tile-saw-250mm"], D.PRODUCT_BY_SLUG["aluminium-scaffold-tower-4m"], D.PRODUCT_BY_SLUG["cordless-drill-driver-kit-18v"]
    assert D.quote(saw, "weekend", waiver=True, delivery=True) == {"product": "IB-CUT-001", "period": "weekend", "hire": 105, "waiver": 10.5, "delivery": 45, "total": 160.5, "deposit_held": 200}
    assert D.quote(scaffold, "3d", waiver=True)["total"] == 225 + 22.5 + 120                       # delivery is required for this machine and is added automatically
    assert D.quote(drill, "7d")["total"] == drill.weekly == 90 and D.quote(drill, "4d")["hire"] == 90   # 4 x $25 is capped at the weekly rate
    assert D.quote(drill, "2d", delivery=True)["delivery"] == 45 and D.quote(drill, "2d")["delivery"] == 0
    with pytest.raises(ValueError):
        D.quote(scaffold, "1d")                                                                   # two-day minimum
    with pytest.raises(ValueError):
        D.quote(saw, "8d")


# --------------------------------------------------------------------------------------------------------------------------------------------------------------------- build and crawl
class Balanced(HTMLParser):
    def __init__(self):
        super().__init__(); self.stack, self.errors = [], []

    def handle_starttag(self, tag, attrs):
        if tag not in VOID:
            self.stack.append(tag)

    def handle_endtag(self, tag):
        if tag in VOID:
            return
        if not self.stack or self.stack[-1] != tag:
            self.errors.append(f"unexpected </{tag}> (open: {self.stack[-3:]})")
        else:
            self.stack.pop()


def internal(href: str):
    u = urlparse(href)
    return None if u.scheme or u.netloc else urldefrag(u.path or "/")[0].rstrip("/") or "/"


def test_build_is_deterministic_and_variants_have_distinct_fingerprints(sites):
    a, b = build_site(V.CONTROL), sites("control")
    assert a == b and site_fingerprint(V.CONTROL) == site_fingerprint(V.CONTROL)
    prints = {v.name: site_fingerprint(v) for v in V.all_single()}
    assert len(set(prints.values())) == 5


@pytest.mark.parametrize("spec", ["control", "discoverability", "availability", "cost", "compatibility", "discoverability+cost+compatibility+availability"])
def test_every_internal_link_and_asset_resolves_and_every_page_is_reachable_from_home(sites, spec):
    files = sites(spec)
    pages = pages_of(files)
    seen, queue = {"/"}, ["/"]
    while queue:
        path = queue.pop()
        s = soup(pages[path])
        refs = [a["href"] for a in s.find_all("a", href=True)]
        for href in refs:
            if href.startswith(("mailto:", "tel:")):
                continue
            target = internal(href)
            assert target is not None, f"{path}: external link {href}"
            assert target in pages, f"{path}: dead link {href}"
            if target not in seen:
                seen.add(target); queue.append(target)
        for tag, attr in (("img", "src"), ("link", "href")):
            for el in s.find_all(tag, **{attr: True}):
                assert internal(el[attr]) in files, f"{path}: missing asset {el[attr]}"
    assert seen == set(pages), f"unreachable pages: {sorted(set(pages) - seen)}"


@pytest.mark.parametrize("spec", ["control", "cost"])
def test_pages_are_well_formed_accessible_html_without_scripts_or_external_references(sites, spec):
    for path, html in pages_of(sites(spec)).items():
        p = Balanced(); p.feed(html)
        assert not p.errors and not p.stack, f"{path}: {p.errors or p.stack}"
        s = soup(html)
        assert s.html["lang"] == "en-AU" and s.title and s.title.string and len(s.find_all("h1")) == 1, path
        assert s.find("main", id="main") and s.find("a", class_="skip") and s.find("meta", attrs={"name": "viewport"})
        assert not s.find("script") and not s.find("form") and not s.find("iframe"), f"{path}: no scripts, forms or frames"
        assert all(img.get("alt") for img in s.find_all("img") if img.get("src") != "/assets/logo.svg"), f"{path}: image without alt text"
        assert not re.search(r"https?://", html), f"{path}: external URL"
        levels = [int(h.name[1]) for h in s.find("main").find_all(re.compile(r"h[1-4]"))]
        assert all(b - a <= 1 for a, b in zip(levels, levels[1:])), f"{path}: heading levels skip: {levels}"
        for table in s.find_all("table"):
            assert table.find("caption") or table.find("th"), f"{path}: table without caption or headers"


def test_images_are_self_contained_svg_with_titles(sites):
    for path, body in sites("control").items():
        if path.endswith(".svg"):
            root = ET.fromstring(body)
            assert root.tag.endswith("svg") and root.find("{http://www.w3.org/2000/svg}title") is not None, path
            assert b"href" not in body and b"<script" not in body and b"http://" not in body.replace(b"http://www.w3.org/2000/svg", b""), path
    assert sum(p.endswith(".svg") for p in sites("control")) == 2 * 16 + 8 + 3 + 5 + 2     # 2 per product, accessories, kits, categories, hero + logo


def test_every_product_has_two_images_and_distinct_artwork(sites):
    files = sites("control")
    assert len({files[f"/assets/img/{p.slug}-1.svg"] for p in D.PRODUCTS}) == 16, "each product has its own illustration"
    for p in D.PRODUCTS:
        assert f"/assets/img/{p.slug}-1.svg" in files and f"/assets/img/{p.slug}-2.svg" in files


# ---------------------------------------------------------------------------------------------------------------- the pages show exactly what the data says (no hidden answers)
def test_product_pages_show_the_data(sites):
    pages = pages_of(sites("control"))
    for p in D.PRODUCTS:
        s = soup(pages[f"/hire/{p.slug}"])
        page = text(s)
        assert text(s.h1) == p.name and f"Product code {p.id}" in page
        rates = [text(r.find("b")) for r in s.select(".rate")]
        assert rates == [D.money(p.daily), D.money(p.weekend), D.money(p.weekly)]
        facts = {text(dt): text(dd) for dt, dd in zip(s.select("dl.facts dt"), s.select("dl.facts dd"))}
        assert facts["Power"] == p.power and facts["Weight"] == f"{p.weight_kg:g} kg" and facts["Refundable deposit"] == D.money(p.deposit)
        assert facts["Minimum hire"].startswith(str(p.min_days)) and facts["Delivery and collection"].lower().startswith("required" if p.delivery == "required" else "optional")
        spec = {text(tr.th): text(tr.td) for tr in s.select("table tr") if tr.th and tr.td}
        assert spec == {k: v for k, v in p.specs}
        assert all(i in page for i in p.included) and all(c in page for c in p.conditions) and p.description in page
        assert f"Today, {D.fmt_date(D.AS_OF)}: {'available' if D.available_on(p, D.AS_OF) else 'fully booked'}." in page


def test_catalogue_cards_match_the_data_and_availability(sites):
    pages = pages_of(sites("control"))
    cards = {c["aria-labelledby"].removeprefix("c-"): c for c in soup(pages["/hire"]).select("article.card")}
    assert set(cards) == {p.id for p in D.PRODUCTS}
    for p in D.PRODUCTS:
        t = text(cards[p.id])
        assert p.name in t and p.summary in t and f"from {D.money(p.daily)}" in t
        assert ("Available today" if D.available_on(p, D.AS_OF) else "Fully booked today") in t
        assert cards[p.id].find("a")["href"] == f"/hire/{p.slug}"
    order = lambda path: [c["aria-labelledby"].removeprefix("c-") for c in soup(pages[path]).select("article.card")]
    assert order("/hire/sort/price-asc") == [p.id for p in sorted(D.PRODUCTS, key=lambda p: (p.daily, p.id))]
    assert order("/hire/sort/price-desc") == [p.id for p in sorted(D.PRODUCTS, key=lambda p: (-p.daily, p.id))]
    assert order("/hire/sort/name") == [p.id for p in sorted(D.PRODUCTS, key=lambda p: p.name.lower())]
    for c in D.CATEGORIES:
        assert order(f"/hire/category/{c.slug}") == [p.id for p in D.PRODUCTS if p.category == c.slug]


def test_availability_pages_show_every_modelled_day(sites):
    pages = pages_of(sites("control"))
    for p in D.PRODUCTS:
        cells = soup(pages[f"/hire/{p.slug}/availability"]).select("table.cal tbody td")
        assert len(cells) == D.WINDOW_DAYS
        for i, td in enumerate(cells):
            day = D.AS_OF + timedelta(days=i)
            free = D.units_free(p, day)
            assert text(td.find(class_="d")) == D.fmt_date(day, weekday=False)
            assert (text(td.find(class_="s")) == "Booked") == (free == 0)
            assert ("free" in td["class"]) == (free == p.units) and ("booked" in td["class"]) == (free == 0)
            if 0 < free < p.units or (p.units > 1 and free > 0):
                assert text(td.find(class_="s")) == f"{free} free"


def test_accessory_pages_show_the_data_including_the_free_text_fit_line(sites):
    pages = pages_of(sites("control"))
    for a in D.ACCESSORIES:
        s = soup(pages[f"/accessories/{a.slug}"])
        detail = {text(tr.th): text(tr.td) for tr in s.select("table tr") if tr.th and tr.td}
        assert text(s.h1) == a.name and detail["Fits"] == a.fits_text and all(detail[k] == v for k, v in a.detail)
        assert text(s.select_one(".rate b")) == D.money(a.price) and ("Per day to hire" if a.kind == "hire" else "To buy") in text(s)
    required = [p.id for p in D.PRODUCTS if p.delivery == "required"]
    assert required == ["IB-LND-003", "IB-LND-004", "IB-ACC-002", "IB-ACC-003"]


def test_hire_terms_state_the_pricing_rules_used_by_quote(sites):
    t = text(soup(pages_of(sites("control"))["/hire-terms"]))
    for needle in (f"costs {int(D.WAIVER_RATE * 100)}% of the hire charge", D.money(D.DELIVERY_FEES["courier"]), D.money(D.DELIVERY_FEES["machine"]), "never more than the weekly rate", "Seven days cost the weekly rate", D.WEEKEND_RULE, "not a charge"):
        assert needle in t, needle
    kits = text(soup(pages_of(sites("control"))["/kits"]))
    for b in D.BUNDLES:
        r = D.bundle_rates(b)
        assert b.name in kits and D.money(r["hire"]["daily"]) in kits and D.money(r["hire"]["weekend"]) in kits and D.money(r["consumables"]) in kits


def test_the_control_exposes_no_answer_the_variants_add_and_no_candidate_markup(sites):
    control = sites("control")
    assert not any(b"data-variant" in body for body in control.values())
    t = text(soup(pages_of(control)["/hire/electric-demolition-hammer-15kg"]))
    for absent in ("jackhammer", "Your hire cost", "Dates at a glance", "Works with", "Total with"):
        assert absent not in t, absent
    assert "/jobs" not in pages_of(control)["/"]


# ------------------------------------------------------------------------------------------------------------------------------------------------------------------ variant isolation
FLAG_OF = {"discoverability": "discover", "availability": "avail", "cost": "cost", "compatibility": "compat"}


def stripped(html: str, flags) -> str:
    s = soup(html)
    for el in s.find_all(attrs={"data-variant": True}):
        if el.decomposed if hasattr(el, "decomposed") else False:
            continue
        if el.get("data-variant") in flags:
            el.decompose()
    return s.prettify()


@pytest.mark.parametrize("name", list(FLAG_OF))
def test_a_variant_differs_from_control_only_by_its_own_marked_additions(sites, name):
    flag = FLAG_OF[name]
    control, variant = pages_of(sites("control")), pages_of(sites(name))
    new_pages = set(variant) - set(control)
    assert set(control) <= set(variant) and (new_pages != set()) == (flag == "discover"), "only the discoverability variant adds pages"
    assert all(p.startswith("/jobs") for p in new_pages)
    for path, html in variant.items():
        marks = {el["data-variant"] for el in soup(html).find_all(attrs={"data-variant": True})}
        assert marks <= {flag}, f"{path}: a variant must only mark its own additions, found {marks}"
        if path in control:
            assert stripped(html, {flag}) == stripped(control[path], set()), f"{path}: differs from control beyond the '{name}' additions"
    changed = {p for p in control if control[p] != variant[p]}
    assert changed, "the variant actually changes something"
    non_page = {p: b for p, b in sites(name).items() if p.startswith("/assets/")}
    assert non_page == {p: b for p, b in sites("control").items() if p.startswith("/assets/")}, "stylesheet and images are byte-identical in every variant"


def test_the_changed_pages_are_the_expected_ones_for_each_variant(sites):
    control = pages_of(sites("control"))
    def changed(name):
        v = pages_of(sites(name)); return {p for p in v if p in control and v[p] != control[p]}
    products = {f"/hire/{p.slug}" for p in D.PRODUCTS}
    assert products <= changed("cost") and changed("cost") - products == set(), "cost: product pages only"
    listing = {"/", "/hire", *[p for p in control if p.startswith(("/hire/sort/", "/hire/category/"))]}                 # pages that show product cards
    assert changed("availability") == products | listing, "availability: product pages and the pages that list products, nothing else"
    assert products <= changed("compatibility") and {f"/accessories/{a.slug}" for a in D.ACCESSORIES} <= changed("compatibility") and "/hire-terms" not in changed("compatibility")
    assert "/" in changed("discoverability") and "/hire-terms" in changed("discoverability")      # the extra navigation link appears on every page


def test_combined_variant_is_exactly_the_union_of_its_parts(sites):
    spec = "discoverability+availability+cost+compatibility"
    control, full = pages_of(sites("control")), pages_of(sites(spec))
    assert V.parse(spec).flags == V.FLAGS and V.parse(spec).name == spec
    for path, html in full.items():
        if path in control:
            assert stripped(html, set(V.FLAGS)) == stripped(control[path], set())
    with pytest.raises(ValueError):
        V.parse("nonsense")


def test_variant_content_is_correct_and_comes_from_the_data(sites):
    cost = pages_of(sites("cost"))
    for p in D.PRODUCTS:
        s = soup(cost[f"/hire/{p.slug}"])
        panel = s.select_one('[data-variant="cost"]')
        rows = {text(tr.th): [text(td) for td in tr.find_all("td")] for tr in panel.select("tbody tr")}
        for r in V_rows(p):
            label, hire, plain, waiver, wd = r
            cells = rows[label]
            assert cells[0] == D.money(hire) and cells[1] == D.money(plain) and cells[2] == D.money(waiver)
            if p.delivery != "required":
                assert cells[3] == D.money(wd)
        assert D.money(p.deposit) in text(panel) and "not part of these totals" in text(panel)
    av = pages_of(sites("availability"))
    for p in D.PRODUCTS:
        panel = soup(av[f"/hire/{p.slug}"]).select_one('[data-variant="avail"]')
        wk = D.next_free_weekend(p)
        assert (D.fmt_date(wk[0]) in text(panel)) if wk else ("none before" in text(panel))
    card = {c["aria-labelledby"].removeprefix("c-"): text(c.select_one(".nextfree")) for c in soup(av["/hire"]).select("article.card")}
    cut = D.PRODUCT_BY_SLUG["petrol-cut-off-saw-350mm"]
    assert not D.available_on(cut, D.AS_OF) and card[cut.id] == f"Next free: {D.fmt_date(D.next_free_day(cut))}"
    co = pages_of(sites("compatibility"))
    ham = soup(co["/hire/electric-demolition-hammer-15kg"]).select_one('[data-variant="compat"]')
    assert {a["href"] for a in ham.find_all("a") if a["href"].startswith("/accessories/")} == {f"/accessories/{a.slug}" for a in D.compatible_accessories(D.PRODUCT_BY_SLUG["electric-demolition-hammer-15kg"])}
    acc = soup(co["/accessories/hex-30-chisel-set"]).select_one('[data-variant="compat"]')
    assert {a["href"] for a in acc.find_all("a") if a["href"].startswith("/hire/")} == {"/hire/electric-demolition-hammer-15kg"}
    di = pages_of(sites("discoverability"))
    h = soup(di["/hire/electric-demolition-hammer-15kg"]).select_one('section[data-variant="discover"]')
    assert "jackhammer" in text(h) and "Break up concrete" in text(h)
    assert {c["aria-labelledby"].removeprefix("c-") for c in soup(di["/jobs/break-up-concrete"]).select("article.card")} == {p.id for p in D.PRODUCTS if "break-up-concrete" in p.jobs}


def V_rows(p):
    periods = [(f"{n}d", f"{n} day{'s' if n != 1 else ''}") for n in (1, 2, 3) if n >= p.min_days] + [("weekend", "Weekend (Fri to Mon)"), ("7d", "1 week")]
    return [(label, D.quote(p, k)["hire"], D.quote(p, k)["total"], D.quote(p, k, waiver=True)["total"], D.quote(p, k, waiver=True, delivery=True)["total"]) for k, label in periods]


# --------------------------------------------------------------------------------------------------------------------------------------------------------------- grading is consistent with the site
def test_candidate_answers_are_derivable_from_what_the_control_site_shows(sites):
    pages = pages_of(sites("control"))
    tasks = {t.id: t for t in grading.candidate_tasks()}
    num = lambda s: float(re.search(r"[\d.]+", s.replace(",", "")).group())
    # ex-01: cheapest item with a listed maximum cutting depth of at least 100 mm, read from the product pages
    best = None
    for p in D.PRODUCTS:
        s = soup(pages[f"/hire/{p.slug}"])
        spec = {text(tr.th): text(tr.td) for tr in s.select("table tr") if tr.th and tr.td}
        if "Max cutting depth" in spec and num(spec["Max cutting depth"]) >= 100:
            price = num(text(s.select_one(".rate b")))
            best = min(best or (price, p.id), (price, p.id))
    assert tasks["ex-01"].answer == best[1]
    # ex-03 and ex-04: total cost recomputed from the rates and the rules a visitor can read on the site
    terms = text(soup(pages["/hire-terms"]))
    waiver = int(re.search(r"costs (\d+)% of the hire charge", terms).group(1)) / 100
    fees = {k: num(v) for k, v in re.findall(r"(Courier|Machine delivery) \$(\d+)", terms)}
    saw = soup(pages["/hire/wet-tile-saw-250mm"]); w = num(text(saw.select(".rate b")[1]))
    assert tasks["ex-03"].answer == w + w * waiver + fees["Courier"]
    sc = soup(pages["/hire/aluminium-scaffold-tower-4m"]); daily, weekly = num(text(sc.select(".rate b")[0])), num(text(sc.select(".rate b")[2]))
    assert tasks["ex-04"].answer == min(3 * daily, weekly) * (1 + waiver) + fees["Machine delivery"]
    # ex-02: weekend availability recomputed from the calendar pages (a unit free on every day, Fri to Mon)
    fri = 4
    ok = []
    for p in D.PRODUCTS:
        cells = soup(pages[f"/hire/{p.slug}/availability"]).select("table.cal tbody td")
        if all("Booked" not in text(cells[fri + i]) for i in range(4)):
            ok.append(p.id)
    assert tasks["ex-02"].answer == sorted(ok)
    # ex-07 / ex-08: descriptions on the pages
    assert tasks["ex-08"].answer == [p.id for p in D.PRODUCTS if "breaking up paths" in text(soup(pages[f"/hire/{p.slug}"]))]
    assert all("porcelain" in text(soup(pages[f"/hire/{D.BY_ID[i].slug}"])) for i in tasks["ex-07"].answer)


def test_candidate_tasks_are_labelled_illustrative_and_cover_every_friction_class():
    ts = grading.candidate_tasks()
    assert {t.friction for t in ts} >= {"discoverability", "availability", "cost", "compatibility"} and len({t.id for t in ts}) == len(ts)
    assert all(t.answer not in (None, [], {}) for t in ts)


# ---------------------------------------------------------------------------------------------------------------------------------------------------------------------- server and CLI
def test_local_server_serves_pages_assets_and_refuses_writes(sites):
    srv = serve(V.CONTROL, 0)
    port = srv.server_address[1]
    t = threading.Thread(target=srv.serve_forever, daemon=True); t.start()
    try:
        def req(path, method="GET"):
            r = urllib.request.Request(f"http://127.0.0.1:{port}{path}", method=method)
            try:
                with urllib.request.urlopen(r) as resp:
                    return resp.status, resp.headers.get("Content-Type"), resp.read()
            except urllib.error.HTTPError as e:
                return e.code, e.headers.get("Content-Type"), e.read()
        assert req("/")[0:2] == (200, "text/html; charset=utf-8") and b"Ironbark" in req("/")[2]
        assert req("/hire/")[0] == 200 and req("/hire?sort=x")[0] == 200 and req("/hire/cutting")[0] == 404
        assert req("/assets/site.css")[1] == "text/css; charset=utf-8" and req("/assets/logo.svg")[1] == "image/svg+xml"
        status, _, body = req("/definitely-missing")
        assert status == 404 and b"Page not found" in body
        assert req("/", "HEAD")[0] == 200 and req("/", "POST")[0] == 405
    finally:
        srv.shutdown(); srv.server_close()


def test_write_site_creates_a_deployable_directory_tree(tmp_path):
    out = write_site(V.parse("cost"), tmp_path / "cost")
    assert (out / "index.html").exists() and (out / "hire" / "electric-demolition-hammer-15kg" / "index.html").exists() and (out / "assets" / "site.css").exists()
    meta = json.loads((out / "VARIANT.json").read_text())
    assert meta["variant"] == "cost" and meta["fingerprint"] == site_fingerprint(V.parse("cost"))
    assert (out / "hire" / "electric-demolition-hammer-15kg" / "index.html").read_bytes() == build_site(V.parse("cost"))["/hire/electric-demolition-hammer-15kg"]


def test_cli_group_is_registered_and_lists_variants(capsys, monkeypatch):
    from agent_readiness.cli import main
    monkeypatch.setattr("sys.argv", ["readiness", "site", "variants"])
    main()
    out = capsys.readouterr().out
    assert all(name in out for name in ("control", "discoverability", "availability", "cost", "compatibility"))
    monkeypatch.setattr("sys.argv", ["readiness", "site", "tasks"])
    main()
    assert "ex-03" in capsys.readouterr().out


def test_the_site_does_not_touch_experiment_artifacts():
    """Isolation: the storefront package imports nothing from the investigation, scanner or experiment code, and writes nothing outside its output directory."""
    pkg = Path(D.__file__).parent
    for f in pkg.glob("*.py"):
        src = f.read_text()
        assert not re.search(r"from \.\.?\.?(investigate|scanner|experiments|suite|remediation)|import agent_readiness\.(investigate|scanner|experiments)", src), f.name
    assert "investigations" not in (pkg / "build.py").read_text()
