"""Black-box probe of a storefront over plain HTTP (no JavaScript, GET only, same origin, bounded). It records OBSERVED facts with evidence; it makes no judgement.

It finds listing pages by structure, not by site-specific selectors: a listing page is a page containing >= 3 links that share a path template (e.g. /p/{}) where each link
sits in a repeated 'card' element that also contains a price. Cards, detail pages and filter controls are then examined for attribute cues (availability, SKU).
Only use it on sites you operate or have permission to test."""
from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from urllib.parse import urldefrag, urljoin, urlsplit

import httpx
from bs4 import BeautifulSoup, Tag

PRICE = re.compile(r"(?:A\$|US\$|\$|€|£|AUD|USD)\s?\d[\d,]*(?:\.\d{1,2})?")
STATIC_EXT = (".css", ".js", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".woff", ".woff2", ".pdf", ".zip", ".xml", ".json", ".webp")
MIN_GROUP = 3


@dataclass(frozen=True)
class AttributeSpec:
    name: str
    pattern: re.Pattern
    description: str


ATTRIBUTES = (
    AttributeSpec("availability", re.compile(r"\b(in stock|out of stock|sold out|unavailable|back-?order(?:ed)?|low stock|only \d+ left|pre-?order)\b", re.I), "stock / availability state"),
    AttributeSpec("sku", re.compile(r"\bSKU\b\s*[:#]?\s*([A-Za-z0-9][A-Za-z0-9._-]{2,})"), "product SKU / identifier"),
)
FILTER_HINT = {"availability": re.compile(r"in[\s_-]?stock|availab", re.I)}


def _text(node: Tag) -> str:
    return re.sub(r"\s+", " ", node.get_text(" ", strip=True))


def _locator(node: Tag) -> str:
    parts = []
    for n in [node, *node.parents][:4]:
        if getattr(n, "name", None) in (None, "[document]"):
            break
        cls = ".".join((n.get("class") or [])[:2])
        parts.append(n.name + (f"#{n['id']}" if n.get("id") else "") + (f".{cls}" if cls else ""))
    return " < ".join(parts)


def template_of(path: str) -> str:
    return re.sub(r"[^/]+$", "{}", path.rstrip("/") or "/") if path.strip("/") else "/"


@dataclass
class Card:
    listing_url: str
    index: int
    href: str
    text: str
    locator: str
    cues: dict[str, str | None] = field(default_factory=dict)       # attribute -> matched text on the card (None = absent)


@dataclass
class DetailPage:
    url: str
    status: int
    title: str
    cues: dict[str, str | None] = field(default_factory=dict)
    locator: dict[str, str | None] = field(default_factory=dict)


@dataclass
class FilterObs:
    listing_url: str
    controls: list[str]                  # visible labels / names of GET form controls
    attribute_filters: dict[str, bool]


@dataclass
class SiteObservations:
    origin: str
    pages_fetched: int
    listing_pages: list[str]
    product_template: str | None
    cards: list[Card]
    details: list[DetailPage]
    filters: list[FilterObs]
    limits: dict
    errors: list[str]


class SiteProbe:
    def __init__(self, base_url: str, *, client: httpx.Client | None = None, max_pages: int = 24, max_details: int = 6, max_depth: int = 2, timeout: float = 10.0):
        parts = urlsplit(base_url)
        if parts.scheme not in ("http", "https") or not parts.netloc:
            raise ValueError("base_url must be an http(s) URL")
        self.origin = f"{parts.scheme}://{parts.netloc}"
        self.base = base_url
        self.max_pages, self.max_details, self.max_depth = max_pages, max_details, max_depth
        self._own = client is None
        self.client = client or httpx.Client(timeout=timeout, follow_redirects=True, headers={"User-Agent": "agent-readiness-audit/1 (site owner testing)"})
        self.errors: list[str] = []

    def _get(self, url: str) -> tuple[int, str]:
        try:
            r = self.client.get(url)
            ctype = r.headers.get("content-type", "")
            return r.status_code, (r.text[:1_000_000] if "html" in ctype else "")
        except httpx.HTTPError as exc:
            self.errors.append(f"{url}: {type(exc).__name__}")
            return 0, ""

    def _same_origin_links(self, soup: BeautifulSoup, url: str) -> list[str]:
        out = []
        for a in soup.find_all("a", href=True):
            href = urldefrag(urljoin(url, a["href"]))[0]
            p = urlsplit(href)
            if f"{p.scheme}://{p.netloc}" == self.origin and not p.path.lower().endswith(STATIC_EXT) and href not in out:
                out.append(href)
        return out

    @staticmethod
    def _groups(soup: BeautifulSoup, url: str) -> dict[str, list[Tag]]:
        groups: dict[str, dict[str, Tag]] = defaultdict(dict)
        for a in soup.find_all("a", href=True):
            href = urldefrag(urljoin(url, a["href"]))[0]
            path = urlsplit(href).path
            if path.strip("/"):
                groups[template_of(path)].setdefault(href, a)
        return {t: list(d.values()) for t, d in groups.items() if len(d) >= MIN_GROUP}

    @staticmethod
    def _card_for(anchor: Tag, others: set[str], url: str) -> Tag | None:
        """Largest ancestor that holds exactly this product link (among the group) and a price."""
        best = None
        for anc in anchor.parents:
            if not isinstance(anc, Tag) or anc.name in ("body", "html", "[document]"):
                break
            hrefs = {urldefrag(urljoin(url, a["href"]))[0] for a in anc.find_all("a", href=True)} & others
            if len(hrefs) != 1:
                break
            if PRICE.search(_text(anc)):
                best = anc
        return best

    def run(self) -> SiteObservations:
        pages: dict[str, tuple[int, BeautifulSoup]] = {}
        queue, seen = [(self.base, 0)], {self.base}
        while queue and len(pages) < self.max_pages:
            url, depth = queue.pop(0)
            status, html = self._get(url)
            if not html:
                continue
            soup = BeautifulSoup(html, "html.parser")
            pages[url] = (status, soup)
            if depth < self.max_depth:
                for link in self._same_origin_links(soup, url):
                    if link not in seen:
                        seen.add(link)
                        queue.append((link, depth + 1))
        # listing pages: >= MIN_GROUP product-like links in cards with prices
        cards: list[Card] = []
        listing_pages: list[str] = []
        template_votes: dict[str, int] = defaultdict(int)
        product_urls: dict[str, list[str]] = {}
        for url, (_status, soup) in pages.items():
            for tmpl, anchors in self._groups(soup, url).items():
                hrefs = {urldefrag(urljoin(url, a["href"]))[0] for a in anchors}
                found = []
                for a in anchors:
                    card = self._card_for(a, hrefs, url)
                    if card is not None:
                        found.append((a, card))
                if len(found) >= MIN_GROUP:
                    listing_pages.append(url) if url not in listing_pages else None
                    template_votes[tmpl] += len(found)
                    product_urls.setdefault(url, [])
                    for i, (a, card) in enumerate(found):
                        text = _text(card)
                        href = urldefrag(urljoin(url, a["href"]))[0]
                        c = Card(url, len(cards), href, text[:200], _locator(card))
                        for spec in ATTRIBUTES:
                            m = spec.pattern.search(text)
                            c.cues[spec.name] = m.group(0) if m else None
                        c.cues["_template"] = tmpl
                        cards.append(c)
                        product_urls[url].append(href)
        product_template = max(template_votes, key=template_votes.get) if template_votes else None
        cards = [c for c in cards if c.cues.get("_template") == product_template]
        for c in cards:
            c.cues.pop("_template", None)
        listing_pages = [u for u in listing_pages if any(c.listing_url == u for c in cards)]
        # filters on listing pages (GET forms only)
        filters = []
        for url in listing_pages:
            controls, match_texts = [], []
            for form in pages[url][1].find_all("form"):
                if (form.get("method") or "get").lower() != "get":
                    continue
                for ctl in form.find_all(["input", "select", "textarea", "button"]):
                    if ctl.get("type") in ("hidden", "submit"):
                        continue
                    label = ctl.get("aria-label") or ctl.get("placeholder") or ""
                    if ctl.get("id"):
                        lab = form.find("label", attrs={"for": ctl["id"]})
                        label = _text(lab) if lab else label
                    if not label and ctl.parent is not None and ctl.parent.name == "label":
                        label = _text(ctl.parent)
                    controls.append((label or ctl.get("name") or "").strip() + (f" [{ctl.get('name')}]" if ctl.get("name") else ""))
                    match_texts.append(controls[-1] + (" " + " ".join(_text(o) for o in ctl.find_all("option")) if ctl.name == "select" else ""))
            filters.append(FilterObs(url, controls, {a: any(h.search(c) for c in match_texts) for a, h in FILTER_HINT.items()}))
        # detail pages: deterministic, spread over listing pages
        targets: list[str] = []
        for i in range(max((len(v) for v in product_urls.values()), default=0)):
            for u in listing_pages:
                lst = [h for h in product_urls.get(u, []) if urlsplit(h).path and template_of(urlsplit(h).path) == product_template]
                if i < len(lst) and lst[i] not in targets:
                    targets.append(lst[i])
        details: list[DetailPage] = []
        for url in targets[: self.max_details]:
            status, html = self._get(url)
            if not html:
                continue
            soup = BeautifulSoup(html, "html.parser")
            main = soup.find("main") or soup.find("article") or soup.body or soup
            d = DetailPage(url, status, _text(soup.title) if soup.title else "")
            for spec in ATTRIBUTES:
                cands = [(len(t), e) for e in main.find_all(True) if len(t := _text(e)) < 200 and spec.pattern.search(t)]
                el = min(cands, key=lambda c: c[0])[1] if cands else None        # the smallest element that carries the cue
                m = spec.pattern.search(_text(el)) if el is not None else None
                d.cues[spec.name] = m.group(0) if m else None
                d.locator[spec.name] = _locator(el) if el is not None else None
            details.append(d)
        if self._own:
            self.client.close()
        return SiteObservations(self.origin, len(pages) + len(details), listing_pages, product_template, cards, details, filters,
                                {"max_pages": self.max_pages, "max_details": self.max_details, "max_depth": self.max_depth, "javascript": False, "methods": ["GET"]}, self.errors)
