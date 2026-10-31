"""What each task's answer depends on, and every route by which the Ironbark site can show it (see `evidence.py`). Needles are the exact strings the pages render, derived from the source data with the
templates' own formatting; `verify.py` proves, for every arm of the site, that at least one route per fact can be satisfied from the RENDERED pages, so a wrong needle fails the pool, not a trial."""
from __future__ import annotations

from datetime import date, timedelta

from ..sites.ironbark import data as D
from itertools import product as _product

from .evidence import Fact, Ident, clause as C, fact

TERMS = "Hire terms and pricing"
PRODUCT = {p.id: p for p in D.PRODUCTS}
ACCESSORY = {a.id: a for a in D.ACCESSORIES}
M = D.money
FEE_LABEL = {"courier": "Courier", "machine": "Machine delivery"}
ATTR = {"IB-ACX-001": ("Chuck", "SDS-Plus"), "IB-ACX-002": ("Chuck", "30 mm hex"), "IB-ACX-003": ("Blade diameter", "350 mm"), "IB-ACX-004": ("Blade diameter", "250 mm")}


def sigp(pid):                 # identifies the item a page or a card is about, by the name the site displays (its code is an optional extra)
    return Ident(PRODUCT[pid].name, pid, f"/hire/{PRODUCT[pid].slug}")


def siga(aid):                 # the same for an accessory
    return Ident(ACCESSORY[aid].name, aid, f"/accessories/{ACCESSORY[aid].slug}")


def sigk(b):                   # and for a kit
    return Ident(b.name, b.id, None, 450)


# Accessories whose LISTING CARD (not only their own page) states what they fit, so a card is an honest alternative route for the fit fact (asserted against the real text in the tests)
CARD_STATES_FIT = {"IB-ACX-002": "30 mm hex demolition hammers", "IB-ACX-005": "Kestrel 18 V", "IB-ACX-008": "cut-off saws"}


def sigc(pid):                 # identifies a booking-calendar page
    return f"Availability: {PRODUCT[pid].name}"


def route(*cl):
    return tuple(cl)


def cell(pid: str, day: date) -> str:
    p = PRODUCT[pid]
    free = D.units_free(p, day)
    return f"{D.fmt_date(day, weekday=False)} " + ("Booked" if free == 0 else "Free" if p.units == 1 else f"{free} free")


def glance(pid: str) -> str:
    p = PRODUCT[pid]
    per = D.unavailable_periods(p)
    return "Fully booked: " + ("; ".join(D.fmt_date(a) + (f" to {D.fmt_date(b)}" if a != b else "") for a, b in per) if per else f"no fully booked days before {D.fmt_date(D.LAST_DAY)}")


def days(a: date, b: date):
    d = a
    while d <= b:
        yield d
        d += timedelta(days=1)


def availability(pid: str, a: date, b: date, label: str) -> Fact:
    """Calendar cells for every day, OR the 'Dates at a glance' panel a candidate variant adds to the product page."""
    return fact(label, route(*[C(sigc(pid), cell(pid, d)) for d in days(a, b)]), route(C(sigp(pid), glance(pid))))


def charge_clauses(pid: str, per: str) -> list:
    p = PRODUCT[pid]
    if per == "weekend":
        return [C(sigp(pid), f"{M(p.weekend)} Weekend")]
    n = int(per[:-1])
    if n == 1:
        return [C(sigp(pid), f"{M(p.daily)} Per day")]
    if n == 7:
        return [C(sigp(pid), f"{M(p.weekly)} Per week"), C(TERMS, "Seven days cost the weekly rate")]
    return [C(sigp(pid), f"{M(p.daily)} Per day"), C(sigp(pid), f"{M(p.weekly)} Per week"), C(TERMS, "never more than the weekly rate")]


def delivery_clauses(pid: str) -> list:
    p = PRODUCT[pid]
    return [C(sigp(pid), f"Weight {p.weight_kg:g} kg"), C(TERMS, f"{FEE_LABEL[p.delivery_class]} {M(D.DELIVERY_FEES[p.delivery_class])}")]


def in_cost_table(pid: str, per: str, total: float) -> bool:
    p = PRODUCT[pid]
    return total in {D.quote(p, per)["total"], D.quote(p, per, waiver=True)["total"], D.quote(p, per, waiver=True, delivery=True)["total"]} and per in ("1d", "2d", "3d", "weekend", "7d") and (per == "weekend" or int(per[:-1]) >= p.min_days)


def total_fact(pid: str, per: str, waiver: bool, delivered: bool, label: str) -> Fact:
    p = PRODUCT[pid]
    a = charge_clauses(pid, per) + ([C(TERMS, "costs 10% of the hire charge")] if waiver else []) + (delivery_clauses(pid) if (delivered or p.delivery == "required") else [])
    total = D.quote(p, per, waiver=waiver, delivery=delivered)["total"]
    routes = [route(*a)]
    if in_cost_table(pid, per, total):
        routes.append(route(C(sigp(pid), "Your hire cost"), C(sigp(pid), M(total))))        # a candidate variant shows the total itself
    return fact(label, *routes)


def deposit(pid):
    return fact(f"deposit of {PRODUCT[pid].name}", route(C(sigp(pid), f"Refundable deposit {M(PRODUCT[pid].deposit)}")))


def delivery_text(pid):
    p = PRODUCT[pid]
    return fact(f"delivery of {p.name}", route(C(sigp(pid), f"Delivery and collection {'Required for this item' if p.delivery == 'required' else 'Optional'}")))


def described(pid: str, kw: str | None = None) -> Fact:
    p = PRODUCT[pid]
    routes = [route(C(None, p.summary)), route(C(sigp(pid), p.name))]
    if kw:
        routes.append(route(C(sigp(pid), kw)))
    return fact(f"description of {p.name}", *routes)


def attr_options(aid: str, pid: str) -> list:
    """Alternative product-side clauses that show what decides whether an accessory fits (chuck, blade size, battery platform, engine type): the specification row, or the chuck named in prose."""
    p = PRODUCT[pid]
    if aid in ATTR:
        label, _ = ATTR[aid]
        value = dict(p.specs).get(label)
        if not value:
            return [[C(sigp(pid), f"Power {p.power}")]]
        return [[C(sigp(pid), f"{label} {value}")]] + ([[C(sigp(pid), f"{value} chuck")]] if label == "Chuck" else [])
    if aid == "IB-ACX-005":
        return [[C(sigp(pid), "Kestrel"), C(sigp(pid), f"Power {p.power}")]]
    return [[C(sigp(pid), f"Power {p.power}")]]


def fit_options(aid: str) -> list:
    """Alternative accessory-side clauses that state what it fits: its own page, or its listing card where the card says so."""
    a = ACCESSORY[aid]
    out = [[C(siga(aid), a.fits_text)]]
    if aid in CARD_STATES_FIT:
        out.append([C(siga(aid), a.summary)])
    return out


def fit_routes(aid: str, pids, fit_first: bool = False) -> list:
    """Every combination of (one option per product's attributes) x (one accessory-side option): any of them shows both halves of the compatibility. `fit_first` only orders the clauses (the scripted
    mock agent walks the first route's pages in that order)."""
    out = []
    for combo in _product(*[attr_options(aid, i) for i in pids], fit_options(aid)):
        parts = [combo[-1], *combo[:-1]] if fit_first else list(combo)
        out.append(tuple(cl for part in parts for cl in part))
    return out


def fits(aid: str) -> Fact:
    return fact("accessory fit text", *[tuple(o) for o in fit_options(aid)])


def kit_rate(b: D.Bundle, n: int):
    r = D.bundle_rates(b)["hire"]
    return C(sigk(b), f"{M(r['daily'] if n == 1 else r['weekly'])} Per {'day' if n == 1 else 'week'}")


def kit_facts(b: D.Bundle, n: int, which: str) -> list:
    prod = PRODUCT[b.hire[0]]
    kit_sig = sigk(b)
    cons = D.bundle_rates(b)["consumables"]
    out = [fact("kit rate", route(kit_rate(b, n))), fact("kit consumables", route(C(kit_sig, f"Plus {M(cons)} for the consumables in the kit")))]
    if which in ("saving", "own"):
        out.append(fact("product rate", route(C(sigp(prod.id), f"{M(prod.daily if n == 1 else prod.weekly)} Per {'day' if n == 1 else 'week'}"))))
    if which == "saving":
        lead = ACCESSORY[b.hire_acc[0]]
        out.append(fact("lead hire price", route(C(siga(lead.id), f"{M(lead.price)} Per day to hire")), route(C(sigp(prod.id), f"hire {M(lead.price)} / day"))))
    if which == "own":
        for i in b.buy:
            if "Safety pack" not in ACCESSORY[i].name:
                out.append(fact(f"price of {ACCESSORY[i].name}", route(C(kit_sig, f"({M(ACCESSORY[i].price)})"))))
    return out


def facts_for(c) -> tuple:
    f, s, q = c.family, c.sub, c.params
    P = q.get("p")
    if f == "lookup":
        p = PRODUCT[P]
        if s == "deposit":
            return (deposit(P),)
        if s == "weight":
            return (fact("weight", route(C(sigp(P), f"Weight {p.weight_kg:g} kg"))),)
        if s == "delivery_required":
            return (delivery_text(P),)
        if s == "min_hire":
            return (fact("minimum hire", route(C(sigp(P), f"Minimum hire {p.min_days} days"))),)
        label = q["label"]
        return (fact(label, route(C(sigp(P), f"{label} {dict(p.specs)[label]}"))),)
    if f == "discovery":
        return (described(c.truth, q.get("kw")),)
    if f == "availability":
        if s == "day":
            return (fact("calendar entry", route(C(sigc(P), cell(P, q["d"]))), route(C(sigp(P), glance(P)))),)
        if s == "next_free":
            nxt = date.fromisoformat(c.truth)
            return (availability(P, q["from"], nxt, "booked run and the next free day"),)
        if s == "units_free":
            return (fact("units free", route(C(sigc(P), cell(P, q["d"])))),)
        if s == "category_weekend":
            fri = q["fri"]
            return tuple(availability(p.id, fri, fri + timedelta(days=3), f"weekend of {p.name}") for p in D.PRODUCTS if p.category == q["cat"])
        return tuple(availability(i, q["start"], q["start"] + timedelta(days=2), f"availability of {PRODUCT[i].name}") for i in q["group"])
    if f == "kit_vs_items":
        b = next(x for x in D.BUNDLES if x.slug == q["kit"])
        return tuple(kit_facts(b, q["n"], {"choice_own_gear": "own", "saving": "saving", "kit_total": "total"}[s]))
    if f == "total_cost":
        if s == "single":
            return (total_fact(P, q["per"], q["waiver"], q["deliv"], "cost inputs"),)
        if s == "weekly_cap":
            return (fact("cost inputs", route(*charge_clauses(P, f"{q['n']}d"))),)
        return tuple(total_fact(i, q["per"], q["waiver"], False, f"cost inputs for {PRODUCT[i].name}") for i in (q["a"], q["b"]))
    if f == "delivery_deposit":
        if s == "delivery_fee":
            p = PRODUCT[P]
            return (fact("delivery fee", route(*delivery_clauses(P)), route(C(sigp(P), f"Delivery and collection for this item: {M(D.DELIVERY_FEES[p.delivery_class])} per job"))),)
        if s == "category_delivery":
            return tuple(delivery_text(p.id) for p in D.PRODUCTS if p.category == q["cat"])
        if s == "max_deposit":
            return tuple(deposit(p.id) for p in D.PRODUCTS if p.category == q["cat"])
        return (deposit(q["a"]), deposit(q["b"]))
    if f == "compatibility":
        a = q["a"]
        if s == "product_to_accessory":
            return (fact("accessory fit", *fit_routes(a, [P]), route(C(sigp(P), "Works with"), C(sigp(P), ACCESSORY[a].name))),)
        if s == "accessory_to_products":
            ps = [i for i in c.truth]
            return (fact("which items an accessory fits", *fit_routes(a, ps, fit_first=True), route(C(siga(a), "Fits these hire items"), *[C(siga(a), PRODUCT[i].name) for i in ps])),)
        if s == "fits_yesno":
            return (fact("accessory fit", *fit_routes(a, [P], fit_first=True), route(C(siga(a), "Fits these hire items"))),)
        return (fact("fuel price", route(C(siga(a), M(ACCESSORY[a].price))), route(C(siga(a), f"{M(ACCESSORY[a].price)} to buy"))),)
    if f == "planning":
        return planning_facts(c)
    return ()


def constraint_clauses(cid: str, pid: str) -> list:
    p = PRODUCT[pid]
    if cid.startswith("depth"):
        return [C(sigp(pid), f"Max cutting depth {dict(p.specs)['Max cutting depth']}")]
    if cid.startswith("height"):
        label, value = next((k, v) for k, v in p.specs if k.startswith("Platform"))
        return [C(sigp(pid), f"{label} {value}")]
    return [C(sigp(pid), f"Power {p.power}"), C(sigp(pid), f"Weight {p.weight_kg:g} kg")]


def planning_facts(c) -> tuple:
    from .tasks import CONSTRAINTS, PRODUCT as _P  # noqa: F401  (CONSTRAINTS predicates are defined with the generator)
    s, q = c.sub, c.params
    if s in ("cheapest_feasible", "plan_total"):
        a, b = q["s"], q["e"]
        n = (b - a).days + 1
        cands = [p for p in D.PRODUCTS if CONSTRAINTS[q["c"]][1](p) and p.min_days <= n]
        out = []
        for p in cands:
            out += [fact(f"{p.name}: qualifies", route(*constraint_clauses(q["c"], p.id))), fact(f"{p.name}: daily rate", route(C(sigp(p.id), f"{M(p.daily)} Per day"))), availability(p.id, a, b, f"{p.name}: free on every day")]
        if s == "plan_total":
            w = next(p for p in cands if p.id == _winner(c, cands))
            out.append(total_fact(w.id, f"{n}d", False, False, "total for the chosen item"))
        return tuple(out)
    if s == "two_jobs_total":
        out = []
        for kw in (q["j1"], q["j2"]):
            p = next(x for x in D.PRODUCTS if kw in x.description.lower())
            out += [described(p.id, kw), total_fact(p.id, q["per"], q["waiver"], False, f"cost inputs for {p.name}")]
        return tuple(out)
    cat = [p for p in D.PRODUCTS if p.category == q["cat"]]
    n = q["n"]
    start = date(2026, 11, 17)
    return tuple(x for p in cat if p.min_days <= n for x in (fact(f"charge for {p.name}", route(*charge_clauses(p.id, f"{n}d"))), availability(p.id, start, start + timedelta(days=n - 1), f"{p.name}: free for the period")))


def _winner(c, cands):
    from .tasks import _cheapest
    a, b = c.params["s"], c.params["e"]
    return _cheapest([p for p in cands if D.available_for(p, a, b)], lambda p: p.daily).id


def path_for(sig: str | None) -> str:
    """The page a clause's signature identifies (for the scripted mock agent's route). No signature = any page: the catalogue."""
    if sig is None:
        return "/hire"
    if sig == TERMS:
        return "/hire-terms"
    if isinstance(sig, Ident):
        if sig.code in PRODUCT:
            return f"/hire/{PRODUCT[sig.code].slug}"
        if sig.code in ACCESSORY:
            return f"/accessories/{ACCESSORY[sig.code].slug}"
        return "/kits"
    if sig.startswith("Availability: "):
        p = next(x for x in D.PRODUCTS if x.name == sig[len("Availability: "):])
        return f"/hire/{p.slug}/availability"
    raise ValueError(f"no page for signature {sig!r}")


def visit_from_facts(facts) -> tuple:
    """A SCRIPTED agent's walk: the pages of the first route of every fact, in order, without repeats. Real agents are free to use any route."""
    out = []
    for f in facts:
        for c in f.routes[0]:
            p = path_for(c.sig)
            if p not in out:
                out.append(p)
    return tuple(out)
