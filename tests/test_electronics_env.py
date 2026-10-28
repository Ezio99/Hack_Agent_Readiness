"""Task 010: electronics-v1 store behaviour, data integrity, variant invariants, accessibility basics and leakage checks (in-process, no browser)."""
import dataclasses
import json
import re
from collections import deque
from html.parser import HTMLParser

import pytest
from fastapi.testclient import TestClient

from agent_readiness.environments.electronics import catalog as C
from agent_readiness.environments.electronics.app import create_app
from agent_readiness.environments.electronics.presentation import facts
from agent_readiness.environments.electronics.variants import FACTORS, all_variants, make_variant
from agent_readiness.suite import core, registry

registry.load_all()
VARIANTS = all_variants()
clients = {v.variant_id: TestClient(create_app(v), base_url="http://shop.local") for v in VARIANTS}
LS, LF, DS, DF = (make_variant(a, s) for a in ("listing", "detail") for s in ("structured", "fragmented"))
get = lambda v, path: clients[v.variant_id].get(path)
slugs = lambda html: re.findall(r'<h2><a href="/p/([a-z0-9-]+)">', html)
plain = lambda html: re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))


# ---- data integrity -----------------------------------------------------------------------------------------------------------------

def test_catalogue_is_the_documented_immutable_fixture():
    assert len(C.PRODUCTS) == 48 and {c: sum(p.category == c for p in C.PRODUCTS) for c in C.CATEGORIES} == {"headphones": 14, "laptops": 10, "monitors": 12, "accessories": 12}
    assert len({p.sku for p in C.PRODUCTS}) == len({p.slug for p in C.PRODUCTS}) == 48
    assert C.DATA_HASH == "7c4eaccbb161330cf111e36b490035024d3fed475b68b84fd6905da656c5d621" and C.DATA_VERSION == "electronics-v1+7c4eaccbb161"
    with pytest.raises(dataclasses.FrozenInstanceError):
        C.PRODUCTS[0].price_cents = 1
    assert all(isinstance(p.price_cents, int) and p.price_cents > 0 and 0 < p.rating <= 5 for p in C.PRODUCTS)
    assert not re.search(r"@|\b\d{3}[- ]\d{3,4}\b", json.dumps(C.data_snapshot()))               # no emails/phone-like data


def test_catalogue_has_the_decoys_the_tasks_need():
    anc = [p for p in C.HEADPHONES if p.spec("anc")]
    assert any(p.in_stock for p in anc) and any(not p.in_stock and p.price_cents <= 25000 for p in anc) and any(p.in_stock and p.price_cents > 25000 for p in anc)
    assert any(not p.spec("anc") and p.in_stock and p.price_cents < 10000 for p in C.HEADPHONES)
    mons = {p.sku: p for p in C.MONITORS}
    failing = lambda p: sum([p.spec("size_in") < 27, not p.spec("usb_c"), p.spec("refresh_hz") < 120, not p.in_stock])
    cheaper = [p for p in C.MONITORS if p.price_cents < mons["MN-3006"].price_cents]
    assert len(cheaper) == 5 and all(failing(p) >= 1 for p in cheaper) and sum(failing(p) == 1 for p in cheaper) == 4       # four decoys each fail exactly one criterion
    assert len([p.name for p in C.LAPTOPS if p.name.startswith("Kestrel Air 14")]) == 2                                 # similar product names exist


# ---- store behaviour -------------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("v", VARIANTS, ids=lambda v: v.variant_id)
def test_every_route_works_and_unknown_inputs_fail_safely(v):
    ok = ["/", "/c/headphones", "/c/headphones?page=2", "/c/laptops", "/c/monitors", "/c/accessories", "/search?q=anc", "/search", "/help", "/help/returns", "/help/delivery"] + [p.path for p in C.PRODUCTS]
    assert all(get(v, p).status_code == 200 for p in ok)
    assert [get(v, p).status_code for p in ("/nope", "/c/phones", "/p/nothing", "/c/laptops?max_price=abc", "/c/laptops?sort=chaos", "/c/laptops?min_ram=lots", "/c/monitors?min_screen=big")] == [404, 404, 404, 422, 422, 422, 422]
    assert get(v, "/c/laptops?page=999").status_code == 200                       # clamps to the last page


def test_pagination_search_filters_and_sorting_behave_like_a_real_shop():
    r1, r2 = get(LS, "/c/headphones"), get(LS, "/c/headphones?page=2")
    assert len(slugs(r1.text)) == 12 and len(slugs(r2.text)) == 2 and 'rel="next"' in r1.text and 'rel="prev"' in r2.text and "Showing 13–14 of 14" in plain(r2.text)
    assert set(slugs(r1.text)) | set(slugs(r2.text)) == {p.slug for p in C.HEADPHONES}
    asc = [C.BY_SLUG[s].price_cents for s in slugs(get(LS, "/c/headphones?sort=price_asc").text)]
    assert asc == sorted(asc) and asc[0] == 3900
    assert [C.BY_SLUG[s].price_cents for s in slugs(get(LS, "/c/monitors?sort=price_desc").text)][0] == 69900
    anc = {s for pg in (1, 2) for s in slugs(get(LS, f"/c/headphones?anc=1&page={pg}").text)}
    assert anc == {p.slug for p in C.HEADPHONES if p.spec("anc")}
    both = slugs(get(LS, "/c/monitors?min_screen=27&usb_c=1&min_refresh=120&sort=price_asc").text)
    assert both == [p.slug for p in sorted(C.MONITORS, key=lambda p: p.price_cents) if p.spec("size_in") >= 27 and p.spec("usb_c") and p.spec("refresh_hz") >= 120]
    assert slugs(get(LS, "/c/laptops?min_ram=32").text) and all(C.BY_SLUG[s].spec("ram_gb") >= 32 for s in slugs(get(LS, "/c/laptops?min_ram=32").text))
    assert set(slugs(get(LS, "/c/headphones?brand=Aurel").text)) == {p.slug for p in C.HEADPHONES if p.brand == "Aurel"}
    assert {C.BY_SLUG[s].sku for s in slugs(get(LS, "/search?q=usb-c+charger").text)} >= {"AC-4001", "AC-4002", "AC-4003"}
    assert slugs(get(LS, "/search?q=zzzz").text) == [] and "No products match" in get(LS, "/search?q=zzzz").text


def test_in_stock_filter_exists_only_when_availability_is_visible_on_listings():
    with_filter = slugs(get(LS, "/c/headphones?in_stock=1").text) + slugs(get(LS, "/c/headphones?in_stock=1&page=2").text)
    assert with_filter and all(C.BY_SLUG[s].in_stock for s in with_filter) and 'name="in_stock"' in get(LS, "/c/headphones").text
    assert 'name="in_stock"' not in get(DS, "/c/headphones").text
    assert slugs(get(DS, "/c/headphones?in_stock=1").text) == slugs(get(DS, "/c/headphones").text)       # the parameter is ignored: no stock leak through filtering


# ---- controlled variants: constant facts, differing presentation -----------------------------------------------------------------------

def test_availability_factor_changes_only_where_stock_is_shown():
    for p in C.PRODUCTS:
        for v in (LS, LF, DS, DF):
            body = plain(get(v, p.path).text)
            assert ("In stock" if p.in_stock else "Out of stock") in body and p.name in body and f"A${p.price_cents / 100:,.2f}" in body   # detail pages always show stock, price, name
    for path in ("/", "/c/monitors", "/search?q=lumio"):
        assert re.search(r"\b(In stock|Out of stock)\b", get(LS, path).text) and not re.search(r"\b(In stock|Out of stock)\b", get(DS, path).text)
        assert slugs(get(LS, path).text) == slugs(get(DS, path).text)                                       # same products in the same order
        assert re.findall(r"A\$[\d,.]+", get(LS, path).text) == re.findall(r"A\$[\d,.]+", get(DS, path).text)


def fact_tokens(p):
    out = []
    for label, value in facts(p):
        if value in ("Yes", "No"):
            continue
        if "not applicable" in value:        # wired headphones: the fact is "no battery"; asserted separately below
            continue
        out += re.findall(r"\d+(?:\.\d+)?", value) + ([] if re.fullmatch(r"[\d.]+ ?\w*", value) else [value.lower()])
    return out


def test_specs_factor_keeps_every_fact_in_both_presentations():
    for p in C.PRODUCTS:
        s_text, f_text = plain(get(LS, p.path).text).lower(), plain(get(LF, p.path).text).lower()
        for tok in fact_tokens(p):
            assert tok in s_text, (p.sku, tok, "structured")
            assert tok in f_text, (p.sku, tok, "fragmented")
        if p.spec("battery_hours") is None and p.category == "headphones":
            assert "wired" in s_text and "wired" in f_text
        if p.category == "headphones":
            assert ("active noise cancelling" in f_text) and (("does not include active noise cancelling" in f_text) == (not p.spec("anc")))
        if p.category == "monitors":
            assert ("usb-c input with power delivery" in f_text) == bool(p.spec("usb_c")) and ("no usb-c input" in f_text) == (not p.spec("usb_c"))
    assert "<dl" in get(LS, "/p/kestrel-air-14").text and "<dl" not in get(LF, "/p/kestrel-air-14").text            # tables vs prose
    assert 'class="chips"' in get(LS, "/c/monitors").text and 'class="chips"' not in get(LF, "/c/monitors").text


def test_underlying_data_task_wording_and_environment_identity_are_constant_across_variants():
    assert {v.variant_id for v in VARIANTS} == {f"electronics-v1/availability-{a}+specs-{s}" for a in FACTORS["availability"] for s in FACTORS["specs"]}
    texts = {v.variant_id: [i.spec.objective for i in registry.instances()] for v in VARIANTS}
    assert len({json.dumps(t) for t in texts.values()}) == 1
    for path in ("/help/returns", "/help/delivery", "/help"):
        assert len({get(v, path).text for v in VARIANTS}) == 1                                               # policy pages identical in every variant
    assert core.ENVIRONMENTS["electronics-v1"].data_version == C.DATA_VERSION


def test_variant_identity_is_invisible_to_visitors():
    for v in VARIANTS:
        for path in ("/", "/c/headphones", "/p/aurel-quiet-700", "/help/delivery", "/nope"):
            r = get(v, path)
            blob = r.text + json.dumps(dict(r.headers))
            assert not re.search(r"availability-|specs-(?:structured|fragmented)|variant|electronics-v1|data_version", blob, re.I), (v.variant_id, path)


# ---- accessibility / structure basics -------------------------------------------------------------------------------------------------

class Audit(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags, self.labels_for, self.controls, self.buttons_outside_form, self.h1, self.form_depth, self.landmarks = [], set(), [], 0, 0, 0, set()
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        self.tags.append(tag)
        if tag == "html":
            self.lang = a.get("lang")
        if tag == "h1":
            self.h1 += 1
        if tag == "form":
            self.form_depth += 1
        if tag == "label" and a.get("for"):
            self.labels_for.add(a["for"])
        if tag in ("input", "select") and a.get("type") not in ("hidden", "submit"):
            self.controls.append(a)
        if tag == "button" and not self.form_depth:
            self.buttons_outside_form += 1
        if tag in ("main", "nav", "header", "footer"):
            self.landmarks.add(tag)
    def handle_endtag(self, tag):
        if tag == "form":
            self.form_depth -= 1


@pytest.mark.parametrize("path", ["/", "/c/headphones", "/c/monitors?usb_c=1", "/search?q=anc", "/p/lumio-pro-27c", "/help/returns", "/help/delivery", "/nope"])
def test_pages_have_basic_semantics_and_no_decorative_or_fake_controls(path):
    html = get(LS, path).text
    a = Audit()
    a.feed(html)
    assert a.lang == "en" and a.h1 == 1 and {"main", "nav", "header", "footer"} <= a.landmarks and 'class="skip"' in html and 'name="viewport"' in html
    assert a.buttons_outside_form == 0                                            # no button that is not a real form submit
    assert all(c.get("id") in a.labels_for or c.get("aria-label") for c in a.controls), [c for c in a.controls if c.get("id") not in a.labels_for]
    assert "<img" not in html and "onclick" not in html and 'href="#"' not in html and "javascript:" not in html and "placeholder-button" not in html
    assert "Add to cart" not in html and "Checkout" not in html and "cart" not in html.lower().replace("cartridge", "")   # no simulated-but-fake commerce controls
    for table in re.findall(r"<table.*?</table>", html, re.S):
        assert "<caption" in table and 'scope="col"' in table and 'scope="row"' in table


# ---- reachability and evaluator-truth isolation ---------------------------------------------------------------------------------------

def crawl(v, limit=600):
    seen, queue, pages = set(), deque(["/"]), {}
    while queue and len(pages) < limit:
        path = queue.popleft()
        if path in seen:
            continue
        seen.add(path)
        r = get(v, path)
        if r.status_code != 200:
            continue
        pages[path] = r.text
        for href in re.findall(r'href="(/[^"#]*)"', r.text):
            href = href.replace("&amp;", "&")
            if href not in seen:
                queue.append(href)
    return pages


@pytest.mark.parametrize("v", VARIANTS, ids=lambda v: v.variant_id)
def test_site_is_fully_reachable_by_links_and_leaks_no_oracle_or_task_information(v):
    pages = crawl(v)
    reachable = {p for p in pages}
    assert {p.path for p in C.PRODUCTS} <= reachable and {"/help/returns", "/help/delivery"} <= reachable and len(pages) >= 58
    blob = "\n".join(pages.values()).lower()
    for forbidden in ("oracle", "truth", "eligible", "expected answer", "evaluator", "grader", "fixture", "task_id", "t1-anc", "t2-compare", "t3-cheapest", "t4-policy", "data-answer"):
        assert forbidden not in blob, forbidden
    assert not re.search(r"(?<!aria-)hidden|display:\s*none|visibility:\s*hidden", blob)     # decorative aria-hidden is fine; no concealed content
    assert not re.search(r"data-[\w-]+=|<!--|<script|type=\"hidden\"", blob)


def test_the_answer_to_each_task_is_not_available_on_the_home_or_first_listing_page():
    for v in VARIANTS:
        first = {path: plain(get(v, path).text) for path in ("/", "/c/headphones", "/c/laptops", "/c/monitors")}
        everything = " ".join(first.values())
        card_text = " ".join(plain(c) for path in first for c in re.findall(r"<article class=\"card\">.*?</article>", get(v, path).text, re.S))
        t1_names = [C.BY_SKU[s].name for s in ("HP-1004", "HP-1006", "HP-1007")]
        assert not all(n in first["/"] + first["/c/headphones"] for n in t1_names)                        # T1: complete eligible set spans page 2
        assert not re.search(r"up to \d+ hours| \d+ GB (?:of memory|$)", card_text) and "Memory" not in card_text   # T2: RAM/battery only on detail pages (filter option labels are controls, not facts)
        assert "up to 18 hours" not in everything and "up to 11 hours" not in everything
        cards = re.findall(r"<article class=\"card\">.*?</article>", get(v, "/c/monitors").text, re.S)
        assert cards and not any("USB-C" in c for c in cards)                                              # T3: USB-C support only via filter or detail page
        assert not re.search(r"A\$29\.00|A\$500\.00|4–7 business days|restocking", everything)               # T4: policy numbers only on /help pages
    assert not re.search(r"SKU", plain(get(LS, "/c/headphones").text))                                     # SKUs only on detail pages
