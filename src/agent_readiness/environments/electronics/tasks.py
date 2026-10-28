"""Task templates T1-T4 for electronics-v1, their independent oracles and graders.

The oracle functions read the immutable catalogue directly; they do not import the web application, the query layer or the presentation
code, so a rendering/filtering bug cannot change the expected answer. Truth lives only in TaskInstance.truth and is never served.

Outcome types: T1 'set' (complete eligible set) and 'any_valid' (one eligible product); T2, T3, T4 'unique'."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

from ...suite.core import (EvidenceRequirement, Grade, Limits, TaskInstance, TaskSpec, register_template)
from .catalog import BY_SKU, BY_SLUG, DATA_VERSION, DELIVERY, ENVIRONMENT_ID, PRODUCTS, RETURNS, Product, delivery_cost_cents

VERSION = "1.0.0"
LIMITS = Limits(12, 240, 12)
money = lambda cents: f"A${cents / 100:,.2f}"


class Strict(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")


class ProductRef(Strict):
    sku: str
    price_cents: int


class T1Answer(Strict):
    products: list[ProductRef]


class LaptopFacts(Strict):
    sku: str
    ram_gb: int
    battery_hours: int


Side = Literal["a", "b", "tie"]


class T2Answer(Strict):
    a: LaptopFacts
    b: LaptopFacts
    more_ram: Side
    longer_battery: Side


class T3Answer(Strict):
    sku: str
    price_cents: int


class T4Answer(Strict):
    sku: str
    return_window_days: int
    restocking_fee_percent: int
    delivery_cost_cents: int
    delivery_days_min: int
    delivery_days_max: int


# ---- independent oracles (catalogue only) -----------------------------------------------------------------------------------------

def oracle_anc_in_stock(max_price_cents: int) -> list[Product]:
    return sorted((p for p in PRODUCTS if p.category == "headphones" and p.spec("anc") and p.in_stock and p.price_cents <= max_price_cents), key=lambda p: p.sku)


def oracle_cheapest_monitor(min_size: float, min_hz: int) -> tuple[Product, list[Product]]:
    eligible = sorted((p for p in PRODUCTS if p.category == "monitors" and p.in_stock and p.spec("usb_c") and p.spec("size_in") >= min_size
                       and p.spec("refresh_hz") >= min_hz), key=lambda p: (p.price_cents, p.sku))
    if len(eligible) < 2 or eligible[0].price_cents == eligible[1].price_cents:
        raise AssertionError("fixture must have a unique cheapest eligible monitor and at least one pricier eligible alternative")
    return eligible[0], eligible


def compare(a, b) -> str:
    return "tie" if a == b else ("a" if a > b else "b")


def oracle_policy(p: Product) -> dict:
    days, fee, _ = RETURNS[p.category]
    _, _, lo, hi = DELIVERY[p.shipping_class]
    return {"sku": p.sku, "return_window_days": days, "restocking_fee_percent": fee, "delivery_cost_cents": delivery_cost_cents(p), "delivery_days_min": lo, "delivery_days_max": hi}


# ---- graders ---------------------------------------------------------------------------------------------------------------------

def grade_t1(inst: TaskInstance, ans: T1Answer) -> Grade:
    truth, mode = inst.truth, inst.truth["mode"]
    reasons, details = [], {}
    skus = [x.sku for x in ans.products]
    if len(set(skus)) != len(skus):
        reasons.append("Duplicate products reported")
    eligible = {sku: price for sku, price in truth["eligible"].items()}
    wrong_price = [x.sku for x in ans.products if x.sku in eligible and x.price_cents != eligible[x.sku]]
    ineligible = [s for s in skus if s not in eligible]
    if ineligible:
        reasons.append("Reported products that are not eligible (not an in-stock ANC headphone within budget): " + ", ".join(sorted(ineligible)))
    if wrong_price:
        reasons.append("Price differs from catalogue for: " + ", ".join(sorted(wrong_price)))
    if mode == "set":
        missing = sorted(set(eligible) - set(skus))
        if missing:
            reasons.append("Missing eligible products: " + ", ".join(missing))
        tp = len(set(skus) & set(eligible))
        details.update(precision=round(tp / len(set(skus)), 3) if skus else 0.0, recall=round(tp / len(eligible), 3), missing=missing, extra=sorted(ineligible))
    else:
        if len(skus) != 1:
            reasons.append("Exactly one product must be reported for this task")
        details.update(eligible_count=len(eligible))
    return Grade(not reasons, tuple(reasons) or ("All required fields match the independent oracle",), details)


def grade_t2(inst: TaskInstance, ans: T2Answer) -> Grade:
    t, reasons = inst.truth, []
    for side, got in (("a", ans.a), ("b", ans.b)):
        want = t[side]
        if got.sku != want["sku"]:
            reasons.append(f"Laptop {side.upper()} SKU should be the laptop named in the task")
        if got.ram_gb != want["ram_gb"]:
            reasons.append(f"Laptop {side.upper()} RAM differs from the catalogue")
        if got.battery_hours != want["battery_hours"]:
            reasons.append(f"Laptop {side.upper()} advertised battery life differs from the catalogue")
    if ans.more_ram != t["more_ram"]:
        reasons.append("Wrong conclusion about which laptop has more RAM")
    if ans.longer_battery != t["longer_battery"]:
        reasons.append("Wrong conclusion about which laptop has longer advertised battery life")
    return Grade(not reasons, tuple(reasons) or ("All required fields match the independent oracle",))


def grade_t3(inst: TaskInstance, ans: T3Answer) -> Grade:
    t, reasons = inst.truth, []
    product = BY_SKU.get(ans.sku)
    if product is None:
        reasons.append("Unknown SKU")
    else:
        if ans.sku not in t["eligible"]:
            reasons.append("Selected monitor does not satisfy every criterion (size, USB-C, refresh rate, in stock)")
        elif ans.sku != t["answer_sku"]:
            reasons.append("Selected monitor is eligible but not the cheapest eligible monitor")
        if ans.price_cents != product.price_cents:
            reasons.append("Price differs from the catalogue")
    return Grade(not reasons, tuple(reasons) or ("All required fields match the independent oracle",), {"eligible_count": len(t["eligible"])})


def grade_t4(inst: TaskInstance, ans: T4Answer) -> Grade:
    want, got, reasons = inst.truth, ans.model_dump(), []
    for key, value in want.items():
        if got[key] != value:
            reasons.append(f"{key} is incorrect")
    return Grade(not reasons, tuple(reasons) or ("All required fields match the independent oracle",))


# ---- templates ------------------------------------------------------------------------------------------------------------------

def _spec(task_id, template_id, objective, model, outcome, evidence_policy, params, evaluator) -> TaskSpec:
    return TaskSpec(task_id=task_id, template_id=template_id, version=VERSION, environment_id=ENVIRONMENT_ID, data_version=DATA_VERSION, objective=objective,
                    answer_schema=model.model_json_schema(), start_path="/", outcome_type=outcome, evidence_policy=evidence_policy, limits=LIMITS,
                    evaluator_id=evaluator, evaluator_version=VERSION, parameters=params)


class T1Discovery:
    template_id, version, environment_id = "t1-discovery-anc-headphones", VERSION, ENVIRONMENT_ID
    FIXTURES = {"under-250-all": (25000, "set"), "under-200-all": (20000, "set"), "under-300-any": (30000, "any_valid")}

    def fixtures(self):
        return list(self.FIXTURES)

    def build(self, fixture_id):
        budget, mode = self.FIXTURES[fixture_id]
        eligible = oracle_anc_in_stock(budget)
        assert len(eligible) >= 2, "fixture must have several eligible products"
        if mode == "set":
            obj = (f"Find every headphone in the store that has active noise cancelling (ANC), is currently in stock and costs {money(budget)} or less. "
                   "Report each product's SKU and price in integer cents.")
        else:
            obj = (f"Find one headphone that has active noise cancelling (ANC), is currently in stock and costs {money(budget)} or less. "
                   "Report its SKU and price in integer cents.")
        spec = _spec(f"t1-anc-headphones-{fixture_id}", self.template_id, obj, T1Answer, "set" if mode == "set" else "any_valid",
                     "Reported products - names, prices AND SKUs - should have been shown to the agent (listing or product pages).", {"budget_cents": budget}, "electronics-t1-grader")
        truth = {"mode": mode, "eligible": {p.sku: p.price_cents for p in eligible}}
        # t1-evidence-v2 (Task 013): the task asks for SKUs, so each eligible product's NAME and its SKU text must have appeared in what the agent was shown
        # (SKU text may be on a product page, or on listings in a variant that shows it). v1 required names only, which let a SKU-blind run look "fully shown".
        if mode == "set":
            ev = tuple(EvidenceRequirement("observed_text", p.name, f"{p.sku} must have been shown") for p in eligible) + \
                 tuple(EvidenceRequirement("observed_text", p.sku, f"the SKU of {p.name} must have been shown") for p in eligible)
        else:
            ev = (EvidenceRequirement("observed_text_any", "|".join(p.name for p in eligible), "at least one eligible product must have been shown"),
                  EvidenceRequirement("observed_text_any", "|".join(p.sku for p in eligible), "the SKU of an eligible product must have been shown"))
        return TaskInstance(spec, truth, T1Answer, grade_t1, ev)


class T2Comparison:
    template_id, version, environment_id = "t2-compare-laptops", VERSION, ENVIRONMENT_ID
    FIXTURES = {"air14-vs-probook15": ("LT-2001", "LT-2003"), "slate16-vs-air14": ("LT-2006", "LT-2001")}

    def fixtures(self):
        return list(self.FIXTURES)

    def build(self, fixture_id):
        a, b = (BY_SKU[s] for s in self.FIXTURES[fixture_id])
        obj = (f"Compare two laptops: laptop A is the {a.name} and laptop B is the {b.name}. For each, report its SKU, its memory (RAM) in GB and its advertised battery life "
               "in hours. Then state which laptop has more RAM and which has the longer advertised battery life, answering 'a', 'b' or 'tie'.")
        f = lambda p: {"sku": p.sku, "ram_gb": p.spec("ram_gb"), "battery_hours": p.spec("battery_hours")}
        truth = {"a": f(a), "b": f(b), "more_ram": compare(a.spec("ram_gb"), b.spec("ram_gb")), "longer_battery": compare(a.spec("battery_hours"), b.spec("battery_hours"))}
        spec = _spec(f"t2-compare-{fixture_id}", self.template_id, obj, T2Answer, "unique", "Both laptops' product pages should have been viewed.",
                     {"laptop_a": a.name, "laptop_b": b.name}, "electronics-t2-grader")
        ev = tuple(e for p in (a, b) for e in (EvidenceRequirement("visited_path", p.path, f"product page of {p.name}"),
                                                EvidenceRequirement("observed_text", f"{p.spec('ram_gb')} GB", f"RAM of {p.name} was shown", p.path),
                                                EvidenceRequirement("observed_text", f"up to {p.spec('battery_hours')} hours", f"advertised battery of {p.name} was shown", p.path)))
        return TaskInstance(spec, truth, T2Answer, grade_t2, ev)


class T3Constraint:
    template_id, version, environment_id = "t3-cheapest-monitor", VERSION, ENVIRONMENT_ID
    FIXTURES = {"27in-usbc-120hz": (27.0, 120), "32in-usbc-60hz": (32.0, 60)}

    def fixtures(self):
        return list(self.FIXTURES)

    def build(self, fixture_id):
        size, hz = self.FIXTURES[fixture_id]
        best, eligible = oracle_cheapest_monitor(size, hz)
        obj = (f"Find the cheapest monitor that is currently in stock, is at least {size:g} inches, has a USB-C input and a refresh rate of at least {hz} Hz. "
               "Report its SKU and price in integer cents.")
        spec = _spec(f"t3-cheapest-monitor-{fixture_id}", self.template_id, obj, T3Answer, "unique", "The selected monitor's product page should have been viewed to verify the criteria.",
                     {"min_size_in": size, "min_refresh_hz": hz}, "electronics-t3-grader")
        truth = {"answer_sku": best.sku, "eligible": {p.sku: p.price_cents for p in eligible}}
        ev = (EvidenceRequirement("visited_path", best.path, f"product page of {best.name}"), EvidenceRequirement("observed_text", money(best.price_cents), "its price was shown", best.path),
              EvidenceRequirement("observed_text", "USB-C", "USB-C support was shown", best.path), EvidenceRequirement("observed_text", f"{best.spec('refresh_hz')} Hz", "its refresh rate was shown", best.path))
        return TaskInstance(spec, truth, T3Answer, grade_t3, ev)


class T4Policy:
    template_id, version, environment_id = "t4-policy-delivery", VERSION, ENVIRONMENT_ID
    FIXTURES = {"lumio-pro-27c": "MN-3006", "kestrel-air-14": "LT-2001", "tessera-whisper": "HP-1006"}

    def fixtures(self):
        return list(self.FIXTURES)

    def build(self, fixture_id):
        p = BY_SKU[self.FIXTURES[fixture_id]]
        obj = (f"A customer is considering the {p.name} (SKU {p.sku}). Using the store's published policies, report: the return window in days; the restocking fee "
               "percentage that applies to opened items; the delivery cost in integer cents for a metropolitan address (0 if delivery is free for this product's price); "
               "and the estimated delivery time as a minimum and maximum number of business days.")
        spec = _spec(f"t4-policy-delivery-{fixture_id}", self.template_id, obj, T4Answer, "unique",
                     "The product page and both the returns and delivery policy pages should have been viewed.", {"sku": p.sku}, "electronics-t4-grader")
        days, fee, _ = RETURNS[p.category]
        cost, threshold, lo, hi = DELIVERY[p.shipping_class]
        ev = (EvidenceRequirement("visited_path", p.path, "the product's price and category"), EvidenceRequirement("observed_text", money(p.price_cents), "the product's price was shown", p.path),
              EvidenceRequirement("visited_path", "/help/returns", "return window and restocking fee"),
              EvidenceRequirement("observed_text", f"{days} days", "the return window was shown", "/help/returns"), EvidenceRequirement("observed_text", f"{fee}%", "the restocking fee was shown", "/help/returns"),
              EvidenceRequirement("visited_path", "/help/delivery", "delivery cost, threshold and estimate"),
              EvidenceRequirement("observed_text", money(cost), "the delivery cost for its shipping class was shown", "/help/delivery"),
              EvidenceRequirement("observed_text", money(threshold), "the free-delivery threshold was shown", "/help/delivery"),
              EvidenceRequirement("observed_text", f"{lo}–{hi} business days", "the delivery estimate was shown", "/help/delivery"))
        return TaskInstance(spec, oracle_policy(p), T4Answer, grade_t4, ev)


TEMPLATE_CLASSES = (T1Discovery, T2Comparison, T3Constraint, T4Policy)


def register() -> None:
    for cls in TEMPLATE_CLASSES:
        register_template(cls())
