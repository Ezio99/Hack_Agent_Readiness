"""Website-aware task generation for Ironbark Hire Co. Every task family is derived from the site's real catalogue, booking calendars, kits, accessories, hire terms and business rules; no
task is written by a model. Each candidate carries (a) a truth computed from the source-of-truth data and (b) `recompute`, an independent recomputation from the RENDERED CONTROL PAGES.
`verify.py` accepts a candidate only when both agree and the other ambiguity/leak/duplicate checks pass.

Families: lookup (negative controls), discovery, availability, kit_vs_items, total_cost, delivery_deposit, compatibility, planning."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Callable

from ..sites.ironbark import data as D
from . import answers as A
from .facts import PageFacts

FAMILIES = ("lookup", "discovery", "availability", "kit_vs_items", "total_cost", "delivery_deposit", "compatibility", "planning")
VARIANTS = ("discoverability", "availability", "cost", "compatibility")
PRODUCT = {p.id: p for p in D.PRODUCTS}
ACCESSORY = {a.id: a for a in D.ACCESSORIES}
PNAME = {p.id: p.name for p in D.PRODUCTS}
ANAME = {a.id: a.name for a in D.ACCESSORIES}
PERIOD_TEXT = {"1d": "for one day", "2d": "for two days", "3d": "for three days", "4d": "for four days", "5d": "for five days", "6d": "for six days", "7d": "for one week (seven days)",
               "weekend": "for one weekend (collected on Friday afternoon, returned on Monday morning)"}


def fd(d: date) -> str:
    return f"{d:%A} {d.day} {d:%B %Y}"


def digest(*parts) -> str:
    return hashlib.sha256(json.dumps(parts, sort_keys=True, default=str).encode()).hexdigest()


@dataclass
class Candidate:
    family: str
    sub: str
    question: str
    kind: str
    truth: object
    pages_needed: int
    sensitive_to: tuple
    evidence: tuple                                   # page paths a pass must have visited (identical for every variant)
    params: dict
    recompute: Callable[[PageFacts], object] | None = field(default=None, repr=False, compare=False)
    options: tuple = ()
    start_path: str = "/"
    near_key: str = ""

    @property
    def fingerprint(self) -> str:
        return digest(self.family, self.sub, self.params)[:10]

    @property
    def task_id(self) -> str:
        return f"ib-{self.fingerprint}"

    @property
    def difficulty(self) -> str:
        return "easy" if self.pages_needed <= 2 else "medium" if self.pages_needed <= 4 else "hard"

    @property
    def names(self) -> dict[str, str]:
        return ANAME if self.kind in ("accessory", "accessories") else PNAME if self.kind in ("product", "products") else {}

    @property
    def expected_text(self):
        return A.format_expected(self.kind, self.truth, self.names)

    @property
    def full_question(self) -> str:
        hint = A.HINTS.get(self.kind, "")
        if self.kind == "choice":
            hint = "Answer with exactly one of: " + ", ".join(f"'{o}'" for o in self.options) + "."
        return f"{self.question} {hint}".strip()


def pp(pid: str) -> str:
    return f"/hire/{PRODUCT[pid].slug}"


def make(family, sub, question, kind, truth, pages, sens, evidence, params, recompute, options=(), near_key=None) -> Candidate:
    return Candidate(family, sub, question, kind, truth, pages, tuple(sens), tuple(evidence), params, recompute, tuple(options), near_key=near_key or f"{family}/{sub}")


def _hash_order(items, salt):
    return sorted(items, key=lambda x: digest(salt, x))


# ------------------------------------------------------------------------------------------------------------------------------------------------------------------------- lookup
def gen_lookup():
    for p in D.PRODUCTS:
        n = p.name
        yield make("lookup", "deposit", f"What is the refundable deposit for the {n}?", "money", float(p.deposit), 1, (), [pp(p.id)], {"p": p.id}, lambda pf, i=p.id: pf.products[i].deposit)
        yield make("lookup", "weight", f"How heavy is the {n}, in kilograms?", "number", p.weight_kg, 1, (), [pp(p.id)], {"p": p.id}, lambda pf, i=p.id: pf.products[i].weight_kg)
        yield make("lookup", "delivery_required", f"Is delivery and collection compulsory when hiring the {n}?", "yesno", p.delivery == "required", 1, (), [pp(p.id)], {"p": p.id},
                   lambda pf, i=p.id: pf.products[i].delivery_required)
        if p.min_days > 1:
            yield make("lookup", "min_hire", f"What is the minimum number of days the {n} can be hired for?", "integer", p.min_days, 1, (), [pp(p.id)], {"p": p.id}, lambda pf, i=p.id: pf.products[i].min_days)
    for pid, label in (("IB-CUT-001", "Max cutting depth"), ("IB-CUT-002", "Max cutting depth"), ("IB-ACC-001", "Safe working reach"), ("IB-GRD-002", "Drum capacity")):
        p = PRODUCT[pid]
        val = float(next(v for k, v in p.specs if k == label).split()[0])
        yield make("lookup", "spec", f"According to its specification, what is the {label.lower()} of the {p.name}?", "number", val, 1, (), [pp(pid)], {"p": pid, "label": label},
                   lambda pf, i=pid, l=label: float(pf.products[i].specs[l].split()[0]))


# ------------------------------------------------------------------------------------------------------------------------------------------------------------------- discovery
NEEDS = [  # (customer phrase, keyword that appears in the item's own page, expected product id, why only one item fits)
    ("break up an old concrete path", "breaking up paths", "IB-DRL-003", "only the demolition hammer is described as breaking up paths and slabs"),
    ("cut porcelain bathroom tiles cleanly", "porcelain", "IB-CUT-001", "only the tile saw is described for porcelain"),
    ("grind out a tree stump", "grinds stumps", "IB-LND-003", "only the stump grinder grinds stumps"),
    ("turn pruned branches into mulch", "mulch", "IB-LND-004", "only the chipper produces mulch"),
    ("trim a garden hedge without a petrol machine", "hedges", "IB-LND-001", "only the hedge trimmer is described for hedges"),
    ("remove thatch and moss from a lawn", "thatch", "IB-LND-002", "only the scarifier lifts thatch"),
    ("compact the sand bedding before laying pavers", "sand bedding", "IB-GRD-001", "only the plate compactor compacts sand bedding"),
    ("mix a few barrow-loads of concrete on site", "mixed concrete", "IB-GRD-002", "only the mixer mixes concrete"),
    ("cut a 150 mm hole through a concrete wall for a pipe", "pipes and vents", "IB-DRL-004", "only the core drill is described for pipe and vent holes"),
    ("fix anchors into a concrete wall", "anchors into concrete", "IB-DRL-002", "only the rotary hammer fixes anchors into concrete"),
    ("cut up a fallen tree for firewood", "firewood", "IB-CUT-003", "only the chainsaw is described for firewood"),
    ("reach the guttering of a double-storey house with a ladder", "second-storey gutter", "IB-ACC-001", "only the extension ladder is described for a second-storey gutter"),
]
SYNONYMS = {"jackhammer": "demolition hammer", "cement mixer": "concrete mixer", "whacker packer": "plate compactor", "scaffolding": "scaffold tower", "concrete saw": "cut-off saw",
            "tile cutter": "tile saw", "hedge cutter": "hedge trimmer", "mulcher": "wood chipper", "stump removal machine": "stump grinder", "dethatcher": "lawn scarifier",
            "screw gun": "drill driver", "hammer drill": "rotary hammer", "tall ladder": "extension ladder"}


def gen_discovery():
    for phrase, kw, pid, why in NEEDS:
        yield make("discovery", "need", f"A customer wants to {phrase}. Which single item in Ironbark's hire range is the best fit?", "product", pid, 3, ("discoverability",), [pp(pid)],
                   {"need": phrase, "kw": kw}, lambda pf, k=kw: _unique([p.id for p in pf.products.values() if k in p.description.lower()]))
    for term, kw in SYNONYMS.items():
        pid = next(p.id for p in D.PRODUCTS if term in p.also_called)
        yield make("discovery", "synonym", f"A customer asks Ironbark whether they hire out a \"{term}\". Which item in the hire range is that?", "product", pid, 3, ("discoverability",), [pp(pid)],
                   {"term": term}, lambda pf, k=kw: _unique([p.id for p in pf.products.values() if k in p.name.lower()]), near_key="discovery/synonym")


def _unique(xs):
    return xs[0] if len(xs) == 1 else f"AMBIGUOUS:{sorted(xs)}"


# ----------------------------------------------------------------------------------------------------------------------------------------------------------------- availability
DAYS = [date(2026, 11, 6), date(2026, 11, 10), date(2026, 11, 14), date(2026, 11, 17), date(2026, 11, 20), date(2026, 11, 26), date(2026, 12, 3)]


def cal(pid):
    return f"/hire/{PRODUCT[pid].slug}/availability"


def gen_availability():
    for p in D.PRODUCTS:
        for d in _hash_order(DAYS, p.id)[:2]:
            yield make("availability", "day", f"Can the {p.name} be hired on {fd(d)}?", "yesno", D.available_on(p, d), 2, ("availability",), [pp(p.id)],
                       {"p": p.id, "d": d}, lambda pf, i=p.id, dd=d: pf.free_on(i, dd) > 0)
    for p in D.PRODUCTS:
        for a, b in D.unavailable_periods(p)[:2]:
            nxt = b + timedelta(days=1)
            if nxt <= D.LAST_DAY:
                yield make("availability", "next_free", f"The {p.name} is fully booked on {fd(a)}. What is the first date after that on which it is available to hire again?", "date", nxt.isoformat(), 2,
                           ("availability",), [pp(p.id)], {"p": p.id, "from": a}, lambda pf, i=p.id, aa=a: _first_free_after(pf, i, aa))
    for c in D.CATEGORIES:
        items = [p for p in D.PRODUCTS if p.category == c.slug]
        for fri, mon in D.weekends()[:5]:
            truth = sorted(p.id for p in items if D.available_for(p, fri, mon))
            yield make("availability", "category_weekend", f"Which of the items in the \"{c.name}\" category can be hired for the whole weekend from {fd(fri)} to {fd(mon)}?", "products", truth, len(items) + 1,
                       ("availability",), [pp(p.id) for p in items], {"cat": c.slug, "fri": fri},
                       lambda pf, cc=c.slug, f=fri, m=mon: sorted(i for i, p in pf.products.items() if p.category == _cname(cc) and pf.available_for(i, f, m)))
    names = [p.id for p in D.PRODUCTS]
    for k in range(12):
        group = _hash_order(names, f"grp{k}")[:4]
        start = DAYS[k % len(DAYS)]
        end = start + timedelta(days=2)
        truth = sorted(i for i in group if D.available_for(PRODUCT[i], start, end))
        yield make("availability", "named_list", "Which of these items can be hired every day from " + f"{fd(start)} to {fd(end)}: " + ", ".join(PNAME[i] for i in sorted(group)) + "?", "products", truth, 5,
                   ("availability",), [pp(i) for i in group], {"group": sorted(group), "start": start}, lambda pf, g=tuple(group), s=start, e=end: sorted(i for i in g if pf.available_for(i, s, e)))
    for p in [x for x in D.PRODUCTS if x.units > 1]:
        d = _hash_order(DAYS, p.id + "u")[0]
        yield make("availability", "units_free", f"How many units of the {p.name} are free to hire on {fd(d)}?", "integer", D.units_free(p, d), 2, ("availability",),
                   [pp(p.id)], {"p": p.id, "d": d}, lambda pf, i=p.id, dd=d: pf.free_on(i, dd))


def _cname(slug):
    return next(c.name for c in D.CATEGORIES if c.slug == slug)


def _first_free_after(pf, pid, a):
    d = a
    while d <= D.LAST_DAY:
        if pf.free_on(pid, d) > 0:
            return d.isoformat()
        d += timedelta(days=1)


# --------------------------------------------------------------------------------------------------------------------------------------------------------------------- kit vs items
def kit_numbers(b: D.Bundle, n: int):
    """(separate_all, separate_minimal, kit_total, consumables) for n in (1, 7) days, from the source data."""
    prod = PRODUCT[b.hire[0]]
    hire = prod.daily if n == 1 else prod.weekly
    lead = sum(ACCESSORY[i].price for i in b.hire_acc) * n
    cons = sum(ACCESSORY[i].price for i in b.buy)
    r = D.bundle_rates(b)["hire"]
    kit = (r["daily"] if n == 1 else r["weekly"]) + cons
    keep = sum(ACCESSORY[i].price for i in b.buy if "Safety pack" not in ACCESSORY[i].name)
    return hire + lead + cons, hire + keep, kit, cons


def _kit_pf(pf: PageFacts, slug: str, n: int):
    k = pf.kits[slug]
    prod = pf.by_name(k.hired[0])
    hire = prod.daily if n == 1 else prod.weekly
    lead = sum(pf.accessory_by_name(x).price for x in k.included) * n
    cons = sum(pf.accessory_by_name(x).price for x in k.bought)
    kit = (k.daily if n == 1 else k.weekly) + k.consumables
    keep = sum(pf.accessory_by_name(x).price for x in k.bought if "Safety pack" not in x)
    return hire + lead + cons, hire + keep, kit, cons


def gen_kits():
    for b in D.BUNDLES:
        prod = PRODUCT[b.hire[0]]
        for n in (1, 7):
            per = "for one day" if n == 1 else "for one week (seven days)"
            ev = ["/kits", pp(prod.id)]
            all_, minimal, kit, cons = kit_numbers(b, n)
            common = {"kit": b.slug, "n": n}
            yield make("kit_vs_items", "choice_own_gear", f"I already own safety gear and an extension lead, and I only want the {prod.name} and the consumables the {b.name} contains other than the safety pack. "
                       f"For hire {per}, is it cheaper to take the {b.name} or to hire the {prod.name} on its own and buy those consumables separately?", "choice", "kit" if kit < minimal else "separately", 4,
                       ("compatibility", "cost"), ev, common | {"own": True}, lambda pf, s=b.slug, nn=n: "kit" if (r := _kit_pf(pf, s, nn))[2] < r[1] else "separately", options=("kit", "separately"))
            yield make("kit_vs_items", "saving", f"I own nothing. How much money do I save, {per}, by taking the {b.name} instead of hiring the {prod.name} alone, hiring an extension lead for the same period and buying the same "
                       f"consumables separately?", "money", round(all_ - kit, 2), 4, ("compatibility", "cost"), ev + [f"/accessories/{ACCESSORY[b.hire_acc[0]].slug}"],
                       common, lambda pf, s=b.slug, nn=n: round((r := _kit_pf(pf, s, nn))[0] - r[2], 2))
            yield make("kit_vs_items", "kit_total", f"What is the total cost of the {b.name}, {per}, including the consumables that come with it? (Ignore the damage waiver, delivery and the deposit.)", "money", float(kit), 2,
                       ("cost",), ["/kits"], common, lambda pf, s=b.slug, nn=n: float(_kit_pf(pf, s, nn)[2]))


# ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- total cost
def gen_total_cost():
    periods = ["1d", "2d", "3d", "weekend", "7d"]
    combos = []
    for p in D.PRODUCTS:
        for per in periods:
            if per != "weekend" and int(per[:-1]) < p.min_days:
                continue
            for waiver in (False, True):
                combos.append((p.id, per, waiver, p.delivery == "required" or (digest(p.id, per, waiver) < "8")))
    for pid, per, waiver, delivered in _hash_order(combos, "cost")[:44]:
        p = PRODUCT[pid]
        req = p.delivery == "required"
        how = "It must be delivered and collected." if req else ("I want it delivered and collected." if delivered else "I will collect and return it myself.")
        yield make("total_cost", "single", f"What is the total I pay to hire the {p.name} {PERIOD_TEXT[per]}? {how} {'I take the optional damage waiver.' if waiver else 'I do not take the damage waiver.'} "
                   "Include everything charged for the hire, but not the refundable deposit.", "money", D.quote(p, per, waiver=waiver, delivery=delivered)["total"], 3 if not req else 3, ("cost",), [pp(pid)],
                   {"p": pid, "per": per, "waiver": waiver, "deliv": delivered}, lambda pf, i=pid, pe=per, w=waiver, dl=delivered: pf.total(i, pe, waiver=w, delivered=dl))
    for p in D.PRODUCTS:                                                       # the "never more than the weekly rate" rule, where it actually binds
        for n in (4, 5, 6):
            if n >= p.min_days and n * p.daily > p.weekly and p.delivery == "optional":
                yield make("total_cost", "weekly_cap", f"What is the total hire charge for the {p.name} for {n} consecutive days, collected and returned by me, with no damage waiver? (The refundable deposit is not a charge.)",
                           "money", float(D.hire_charge(p, f"{n}d")), 3, ("cost",), [pp(p.id)], {"p": p.id, "n": n}, lambda pf, i=p.id, nn=n: pf.hire_charge(i, f"{nn}d"))
                break
    pairs = [("IB-GRD-001", "IB-GRD-002"), ("IB-CUT-001", "IB-GRD-002"), ("IB-DRL-002", "IB-CUT-001"), ("IB-LND-001", "IB-DRL-001"), ("IB-DRL-003", "IB-CUT-002"), ("IB-GRD-001", "IB-CUT-002"),
             ("IB-ACC-001", "IB-DRL-001"), ("IB-LND-002", "IB-GRD-001")]
    for a, b in pairs:
        for per, waiver in (("2d", True), ("weekend", False)):
            pa, pb = PRODUCT[a], PRODUCT[b]
            if any(PRODUCT[i].delivery == "required" for i in (a, b)):
                continue
            tot = round(sum(D.quote(PRODUCT[i], per, waiver=waiver, delivery=False)["total"] for i in (a, b)), 2)
            yield make("total_cost", "two_items", f"I will collect and return both the {pa.name} and the {pb.name} myself and hire them together {PERIOD_TEXT[per]}. "
                       f"{'I take the optional damage waiver on both.' if waiver else 'I take no damage waiver.'} What is the total charge for the two items? (Not the deposits.)", "money", tot, 4, ("cost",),
                       [pp(a), pp(b)], {"a": a, "b": b, "per": per, "waiver": waiver}, lambda pf, x=a, y=b, pe=per, w=waiver: round(pf.total(x, pe, waiver=w, delivered=False) + pf.total(y, pe, waiver=w, delivered=False), 2))


# ------------------------------------------------------------------------------------------------------------------------------------------------------------------ delivery and deposit
def gen_delivery_deposit():
    for p in D.PRODUCTS:
        yield make("delivery_deposit", "delivery_fee", f"How much does delivery and collection of the {p.name} cost? (One fee covers both delivery and collection.)", "money", float(D.DELIVERY_FEES[p.delivery_class]), 3,
                   ("cost",), [pp(p.id), "/hire-terms"], {"p": p.id}, lambda pf, i=p.id: pf.delivery_fee(i))
    for c in D.CATEGORIES:
        items = [p for p in D.PRODUCTS if p.category == c.slug]
        req = sorted(p.id for p in items if p.delivery == "required")
        yield make("delivery_deposit", "category_delivery", f"Which items in the \"{c.name}\" category can only be hired with delivery and collection (collecting them yourself is not possible)?", "products", req, len(items) + 1,
                   ("cost",), [pp(p.id) for p in items], {"cat": c.slug}, lambda pf, cc=c.slug: sorted(i for i, p in pf.products.items() if p.category == _cname(cc) and p.delivery_required))
        top = sorted(items, key=lambda p: -p.deposit)
        yield make("delivery_deposit", "max_deposit", f"Which item in the \"{c.name}\" category has the highest refundable deposit?", "product", top[0].id, len(items) + 1, (), [pp(p.id) for p in items],
                   {"cat": c.slug}, lambda pf, cc=c.slug: _top_deposit(pf, cc))
    for a, b in [("IB-DRL-003", "IB-CUT-002"), ("IB-ACC-003", "IB-GRD-001"), ("IB-LND-003", "IB-ACC-002"), ("IB-DRL-001", "IB-CUT-001"), ("IB-LND-004", "IB-DRL-004")]:
        yield make("delivery_deposit", "two_deposits", f"If I hire the {PNAME[a]} and the {PNAME[b]} at the same time, how much refundable deposit will be held in total?", "money",
                   float(PRODUCT[a].deposit + PRODUCT[b].deposit), 3, (), [pp(a), pp(b)], {"a": a, "b": b}, lambda pf, x=a, y=b: pf.products[x].deposit + pf.products[y].deposit)


def _top_deposit(pf, cat):
    ps = sorted([p for p in pf.products.values() if p.category == _cname(cat)], key=lambda p: -p.deposit)
    return ps[0].id if ps[0].deposit != ps[1].deposit else f"AMBIGUOUS:tie {ps[0].deposit}"


# ---------------------------------------------------------------------------------------------------------------------------------------------------------------------- compatibility
PAIR_RULES = {   # accessory id -> predicate over a product's own page text (the second path never uses the compat tags)
    "IB-ACX-001": lambda p: p.specs.get("Chuck") == "SDS-Plus",
    "IB-ACX-002": lambda p: p.specs.get("Chuck") == "30 mm hex",
    "IB-ACX-003": lambda p: p.specs.get("Blade diameter") == "350 mm",
    "IB-ACX-004": lambda p: p.specs.get("Blade diameter") == "250 mm",
    "IB-ACX-005": lambda p: "18 V" in p.power and "Kestrel" in p.full_text,
    "IB-ACX-008": lambda p: "2-stroke" in p.power,
}


def gen_compat():
    for aid, rule in PAIR_RULES.items():
        a = ACCESSORY[aid]
        prods = sorted(p.id for p in D.PRODUCTS if set(a.fits) & set(p.compat))
        if len(prods) == 1:
            pid = prods[0]
            yield make("compatibility", "product_to_accessory", f"Which accessory on Ironbark's site is made for the {PNAME[pid]}'s {_what(aid)}?", "accessory", aid, 3, ("compatibility",),
                       [pp(pid), f"/accessories/{a.slug}"], {"p": pid, "a": aid}, lambda pf, i=pid, g=aid: _acc_for(pf, i, g))
        yield make("compatibility", "accessory_to_products", f"Which hire items can the accessory \"{a.name}\" be used with?", "products", prods, 4, ("compatibility",),
                   [f"/accessories/{a.slug}"] + [pp(i) for i in prods], {"a": aid}, lambda pf, r=aid: sorted(i for i, p in pf.products.items() if PAIR_RULES[r](p)))
    for aid, pid, truth in [("IB-ACX-003", "IB-CUT-001", False), ("IB-ACX-004", "IB-CUT-001", True), ("IB-ACX-005", "IB-LND-003", False), ("IB-ACX-001", "IB-DRL-001", False), ("IB-ACX-008", "IB-CUT-003", True),
                            ("IB-ACX-002", "IB-DRL-002", False), ("IB-ACX-005", "IB-LND-001", True), ("IB-ACX-008", "IB-LND-001", False)]:
        yield make("compatibility", "fits_yesno", f"Can the accessory \"{ANAME[aid]}\" be used with the {PNAME[pid]}?", "yesno", truth, 3, ("compatibility",), [pp(pid), f"/accessories/{ACCESSORY[aid].slug}"],
                   {"a": aid, "p": pid}, lambda pf, r=aid, i=pid: bool(PAIR_RULES[r](pf.products[i])))
    yield make("compatibility", "fuel_price", "What does the pre-mixed fuel that Ironbark sells for 2-stroke tools cost?", "money", float(ACCESSORY["IB-ACX-008"].price), 2,
               ("compatibility",), ["/accessories/two-stroke-fuel-mix-5l"], {"a": "IB-ACX-008"}, lambda pf: pf.accessories["IB-ACX-008"].price)


def _what(aid):
    return {"IB-ACX-001": "SDS-Plus chuck", "IB-ACX-002": "30 mm hex chuck", "IB-ACX-003": "350 mm blade", "IB-ACX-004": "250 mm blade", "IB-ACX-005": "18 V battery platform", "IB-ACX-008": "2-stroke engine"}[aid]


GROUPS = {"IB-ACX-001": ("IB-ACX-001", "IB-ACX-002"), "IB-ACX-002": ("IB-ACX-001", "IB-ACX-002"), "IB-ACX-003": ("IB-ACX-003", "IB-ACX-004"), "IB-ACX-004": ("IB-ACX-003", "IB-ACX-004"),
          "IB-ACX-005": ("IB-ACX-005",), "IB-ACX-008": ("IB-ACX-008",)}      # accessories that compete for the same attribute of a machine (chuck, blade size, battery, fuel)


def _acc_for(pf, pid, aid):
    hits = [a for a in GROUPS[aid] if PAIR_RULES[a](pf.products[pid])]
    return hits[0] if len(hits) == 1 else f"AMBIGUOUS:{hits}"


# ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------- planning
CONSTRAINTS = {   # id -> (phrase, predicate on a data Product, predicate on page ProductFacts)
    "depth60": ("can cut at least 60 mm deep", lambda p: _num(p, "Max cutting depth") >= 60, lambda p: _pnum(p, "Max cutting depth") >= 60),
    "depth100": ("can cut at least 100 mm deep", lambda p: _num(p, "Max cutting depth") >= 100, lambda p: _pnum(p, "Max cutting depth") >= 100),
    "height3": ("reaches a working height of at least 3 m", lambda p: _num(p, "Platform") >= 3, lambda p: _pnum(p, "Platform") >= 3),
    "cordless_light": ("is cordless or battery powered and weighs under 10 kg", lambda p: ("cordless" in p.power or "Battery" in p.power) and p.weight_kg < 10,
                       lambda p: ("cordless" in p.power or "Battery" in p.power) and p.weight_kg < 10),
    "petrol_40": ("is petrol powered and weighs no more than 40 kg", lambda p: p.power.startswith("Petrol") and p.weight_kg <= 40, lambda p: p.power.startswith("Petrol") and p.weight_kg <= 40),
    "mains_light": ("runs on 240 V mains power and weighs under 20 kg", lambda p: p.power.startswith("240 V") and p.weight_kg < 20, lambda p: p.power.startswith("240 V") and p.weight_kg < 20),
}


def _num(p, prefix):
    for k, v in p.specs:
        if k.startswith(prefix):
            return float(v.split()[0])
    return -1.0


def _pnum(p, prefix):
    for k, v in p.specs.items():
        if k.startswith(prefix):
            return float(v.split()[0])
    return -1.0


def _cheapest(cands, key):
    s = sorted(cands, key=key)
    if not s:
        return "AMBIGUOUS:none"
    return s[0] if len(s) == 1 or key(s[0]) != key(s[1]) else "AMBIGUOUS:tie"


def gen_planning():
    ranges = [(date(2026, 11, 6), date(2026, 11, 8)), (date(2026, 11, 10), date(2026, 11, 12)), (date(2026, 11, 13), date(2026, 11, 15)), (date(2026, 11, 17), date(2026, 11, 19)), (date(2026, 11, 20), date(2026, 11, 22))]
    for cid, (phrase, dp, fp) in CONSTRAINTS.items():
        for s, e in ranges:
            n = (e - s).days + 1
            cand = [p for p in D.PRODUCTS if dp(p) and p.min_days <= n and D.available_for(p, s, e)]
            anyc = [p for p in D.PRODUCTS if dp(p) and p.min_days <= n]
            if len(anyc) < 2:
                continue
            win = _cheapest(cand, lambda p: p.daily)
            if isinstance(win, str):
                continue
            hard = _cheapest(anyc, lambda p: p.daily)
            q = (f"I need an item that {phrase}. I want to hire it every day from {fd(s)} to {fd(e)} ({n} days). Among the items that qualify and are free on all of those days, which has the lowest daily rate?")
            yield make("planning", "cheapest_feasible", q, "product", win.id, 6 if (not isinstance(hard, str) and hard.id != win.id) else 5, ("availability",), [pp(p.id) for p in anyc],
                       {"c": cid, "s": s, "e": e}, lambda pf, f=fp, ss=s, ee=e, nn=n: _plan_pf(pf, f, ss, ee, nn))
            # the same plan, priced
            tot = D.quote(win, f"{n}d", waiver=False, delivery=False)["total"] if n <= 7 else None
            yield make("planning", "plan_total", f"I need an item that {phrase}, free every day from {fd(s)} to {fd(e)} ({n} days). I will pick the qualifying item with the lowest daily rate. If I collect it myself and take no damage waiver, "
                       "what do I pay for the hire? (Delivery, if the item requires it, is also charged and included; the deposit is not.)", "money",
                       D.quote(win, f"{n}d")["total"], 7, ("availability", "cost"), [pp(p.id) for p in anyc], {"c": cid, "s": s, "e": e, "total": True},
                       lambda pf, f=fp, ss=s, ee=e, nn=n: (lambda w: w if w.startswith("AMBIGUOUS") else pf.total(w, f"{nn}d", waiver=False, delivered=False))(_plan_pf(pf, f, ss, ee, nn)))
    two = [("cut porcelain bathroom tiles cleanly", "porcelain", "IB-CUT-001"), ("compact the sand bedding before laying pavers", "sand bedding", "IB-GRD-001"), ("mix a few barrow-loads of concrete on site", "mixed concrete", "IB-GRD-002"),
           ("break up an old concrete path", "breaking up paths", "IB-DRL-003")]
    for i in range(len(two)):
        for j in range(i + 1, len(two)):
            (ph1, k1, p1), (ph2, k2, p2) = two[i], two[j]
            for per, w in (("weekend", True), ("2d", False)):
                pa, pb = PRODUCT[p1], PRODUCT[p2]
                tot = round(D.quote(pa, per, waiver=w, delivery=False)["total"] + D.quote(pb, per, waiver=w, delivery=False)["total"], 2)
                yield make("planning", "two_jobs_total", f"For a home renovation I need to {ph1} and to {ph2}. I will hire the single best-fitting item for each job, collect both myself, and keep them {PERIOD_TEXT[per]}. "
                           f"{'I take the damage waiver on both.' if w else 'I take no damage waiver.'} What is the total hire charge? (Not the deposits.)", "money", tot, 7, ("discoverability", "cost"), [pp(p1), pp(p2)],
                           {"j1": k1, "j2": k2, "per": per, "waiver": w}, lambda pf, a=k1, b=k2, pe=per, ww=w: _two_jobs(pf, a, b, pe, ww))
    for c in D.CATEGORIES:
        items = [p for p in D.PRODUCTS if p.category == c.slug]
        for n in (1, 3):
            for budget in sorted({p.daily * n for p in items if p.daily * n <= p.weekly}):
                truth = sorted(p.id for p in items if p.min_days <= n and D.hire_charge(p, f"{n}d") <= budget and D.available_for(p, date(2026, 11, 17), date(2026, 11, 17) + timedelta(days=n - 1)))
                if 1 <= len(truth) < len(items):
                    s = date(2026, 11, 17); e = s + timedelta(days=n - 1)
                    yield make("planning", "budget_set", f"Which items in the \"{c.name}\" category can be hired for {n} day{'s' if n > 1 else ''} starting {fd(s)} (free on every day of that period) with a hire charge of no more than ${budget:g} "
                               "(ignore waiver, delivery and the deposit)?", "products", truth, len(items) + 1, ("availability", "cost"), [pp(p.id) for p in items], {"cat": c.slug, "n": n, "budget": budget},
                               lambda pf, cc=c.slug, nn=n, b=budget, ss=s, ee=e: sorted(i for i, p in pf.products.items() if p.category == _cname(cc) and p.min_days <= nn and pf.hire_charge(i, f"{nn}d") <= b and pf.available_for(i, ss, ee)))
                    break


def _plan_pf(pf, pred, s, e, n):
    cand = [p for p in pf.products.values() if pred(p) and p.min_days <= n and pf.available_for(p.id, s, e)]
    win = _cheapest(cand, lambda p: p.daily)
    return win if isinstance(win, str) else win.id


def _two_jobs(pf, k1, k2, per, w):
    ids = []
    for k in (k1, k2):
        hit = [p.id for p in pf.products.values() if k in p.description.lower()]
        if len(hit) != 1:
            return f"AMBIGUOUS:{k}"
        ids.append(hit[0])
    return round(sum(pf.total(i, per, waiver=w, delivered=False) for i in ids), 2)


GENERATORS = {"lookup": gen_lookup, "discovery": gen_discovery, "availability": gen_availability, "kit_vs_items": gen_kits, "total_cost": gen_total_cost, "delivery_deposit": gen_delivery_deposit,
              "compatibility": gen_compat, "planning": gen_planning}


def generate() -> list[Candidate]:
    """Every candidate from every family, in a fixed order (deterministic; nothing here draws on a clock or an unseeded RNG)."""
    return [c for fam in FAMILIES for c in GENERATORS[fam]()]
