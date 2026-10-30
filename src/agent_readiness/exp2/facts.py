"""Facts read ONLY from the rendered pages of the control site (HTML text), never from `sites.ironbark.data`. This is the independent second path used to verify every generated answer:
the generator computes a truth from the source-of-truth data; `PageFacts` recomputes it from what a visitor can read, and the two must agree or the task is rejected."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, timedelta

from bs4 import BeautifulSoup

from ..sites.ironbark import data as D  # ONLY for the fixed calendar origin and the page URL scheme; no product facts are read from it

AS_OF, WINDOW = D.AS_OF, D.WINDOW_DAYS
MONTHS = {m: i for i, m in enumerate(["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], 1)}


def text(el) -> str:
    return re.sub(r"\s+", " ", el.get_text(" ", strip=True))


def number(s: str) -> float:
    return float(re.search(r"-?\d[\d,]*\.?\d*", s).group().replace(",", ""))


@dataclass
class ProductFacts:
    id: str
    slug: str
    name: str
    category: str
    daily: float
    weekend: float
    weekly: float
    deposit: float
    min_days: int
    delivery_required: bool
    power: str
    weight_kg: float
    specs: dict
    description: str
    full_text: str
    units: int = 1
    free: list[int] = field(default_factory=list)      # units free on each of the 56 days from AS_OF


@dataclass
class AccessoryFacts:
    id: str
    slug: str
    name: str
    price: float
    hire: bool
    fits: str
    full_text: str


@dataclass
class KitFacts:
    slug: str
    name: str
    daily: float
    weekend: float
    weekly: float
    consumables: float
    hired: list[str]
    included: list[str]
    bought: list[str]


@dataclass
class Terms:
    waiver_rate: float
    courier_fee: float
    machine_fee: float
    courier_below_kg: float
    cap_rule: bool


class PageFacts:
    def __init__(self, pages: dict[str, str]):
        self.pages = pages
        self.terms = self._terms()
        self.products = self._products()
        self.accessories = self._accessories()
        self.kits = self._kits()

    # -- parsing -------------------------------------------------------------------------------------------------------------------------------------------------------------------
    def _terms(self) -> Terms:
        t = text(BeautifulSoup(self.pages["/hire-terms"], "html.parser"))
        return Terms(float(re.search(r"costs (\d+)% of the hire charge", t).group(1)) / 100, float(re.search(r"Courier \$(\d+)", t).group(1)), float(re.search(r"Machine delivery \$(\d+)", t).group(1)),
                     float(re.search(r"under about (\d+) kg", t).group(1)), "never more than the weekly rate" in t)

    def _products(self) -> dict[str, ProductFacts]:
        out = {}
        listing = BeautifulSoup(self.pages["/hire"], "html.parser")
        for art in listing.select("article.card"):
            href = art.select_one("h2 a, h3 a")["href"]
            s = BeautifulSoup(self.pages[href], "html.parser")
            facts = {text(dt): text(dd) for dt, dd in zip(s.select("dl.facts dt"), s.select("dl.facts dd"))}
            rates = [number(text(b)) for b in s.select(".rates .rate b")]
            spec_table = next(t for t in s.find_all("table") if t.find("caption") and text(t.find("caption")) == "Specifications")
            specs = {text(tr.th): text(tr.td) for tr in spec_table.select("tr") if tr.th and tr.td}
            code = re.search(r"Product code (IB-[A-Z]+-\d+)", text(s)).group(1)
            crumbs = [text(a) for a in s.select("nav.crumbs a")]
            slug = href.rsplit("/", 1)[1]
            pf = ProductFacts(code, slug, text(s.h1), crumbs[-1], rates[0], rates[1], rates[2], number(facts["Refundable deposit"]), int(number(facts["Minimum hire"])),
                              facts["Delivery and collection"].lower().startswith("required"), facts["Power"], number(facts["Weight"]), specs,
                              text(s.find("h2", string="About this equipment").parent.find("p")), text(s))
            cal = BeautifulSoup(self.pages[f"{href}/availability"], "html.parser")
            pf.units = int(re.search(r"Fleet size: (\d+)", text(cal)).group(1))
            for td in cal.select("table.cal tbody td"):
                s_ = text(td.find(class_="s"))
                pf.free.append(0 if s_ == "Booked" else pf.units if s_ == "Free" and pf.units == 1 else int(s_.split()[0]))
            out[code] = pf
        return out

    def _accessories(self) -> dict[str, AccessoryFacts]:
        out = {}
        for art in BeautifulSoup(self.pages["/accessories"], "html.parser").select("article.card"):
            href = art.select_one("h2 a")["href"]
            s = BeautifulSoup(self.pages[href], "html.parser")
            code = re.search(r"Product code (IB-[A-Z]+-\d+)", text(s)).group(1)
            detail = {text(tr.th): text(tr.td) for tr in next(t for t in s.find_all("table") if t.find("caption") and text(t.find("caption")) == "Details").select("tr") if tr.th and tr.td}
            out[code] = AccessoryFacts(code, href.rsplit("/", 1)[1], text(s.h1), number(text(s.select_one(".rate b"))), "Per day to hire" in text(s), detail["Fits"], text(s))
        return out

    def _kits(self) -> dict[str, KitFacts]:
        out = {}
        for art in BeautifulSoup(self.pages["/kits"], "html.parser").select("article.panel"):
            heads = {text(h): h for h in art.find_all("h3")}
            names = lambda title: [text(a) for a in heads[title].find_next_sibling("ul").find_all("a")]
            rates = [number(text(b)) for b in art.select(".rates .rate b")]
            cons = number(re.search(r"Plus \$([\d,]+) for the consumables", text(art)).group(1))
            out[art["id"]] = KitFacts(art["id"], text(art.find("h2")), rates[0], rates[1], rates[2], cons, names("Hired items"), names("Included at no extra charge"), names("Consumables you keep"))
        return out

    # -- recomputation from what the pages say --------------------------------------------------------------------------------------------------------------------------------------
    def by_name(self, name: str) -> ProductFacts:
        return next(p for p in self.products.values() if p.name == name)

    def accessory_by_name(self, name: str) -> AccessoryFacts:
        return next(a for a in self.accessories.values() if a.name == name)

    def free_on(self, pid: str, day: date) -> int:
        return self.products[pid].free[(day - AS_OF).days]

    def available_for(self, pid: str, start: date, end: date) -> bool:
        d = start
        while d <= end:
            if self.free_on(pid, d) == 0:
                return False
            d += timedelta(days=1)
        return True

    def hire_charge(self, pid: str, period: str) -> float:
        p = self.products[pid]
        if period == "weekend":
            return p.weekend
        n = int(period.rstrip("d"))
        if n < p.min_days:
            raise ValueError("below the minimum hire")
        return min(n * p.daily, p.weekly) if self.terms.cap_rule else n * p.daily

    def delivery_fee(self, pid: str) -> float:
        return self.terms.courier_fee if self.products[pid].weight_kg < self.terms.courier_below_kg else self.terms.machine_fee

    def total(self, pid: str, period: str, *, waiver: bool, delivered: bool) -> float:
        p, h = self.products[pid], self.hire_charge(pid, period)
        deliver = delivered or p.delivery_required
        return round(h + (h * self.terms.waiver_rate if waiver else 0) + (self.delivery_fee(pid) if deliver else 0), 2)
