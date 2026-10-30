"""Independent ground truth for candidate tasks on the Ironbark site. Everything is computed from `data.py` (the same source the pages are rendered from), so an expected answer can never
contradict what a page shows. These are ILLUSTRATIVE task shapes for a possible Experiment 2; none is a frozen task and none has been run on any agent."""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from . import data as D


def spec_number(p: D.Product, label_prefix: str) -> float | None:
    """The first number in the spec row whose label starts with `label_prefix`, read from the same text the product page shows."""
    for label, value in p.specs:
        if label.startswith(label_prefix):
            m = re.search(r"\d[\d,]*\.?\d*", value)
            return float(m.group().replace(",", "")) if m else None
    return None


def cheapest_with_spec(label_prefix: str, at_least: float) -> D.Product:
    return min((p for p in D.PRODUCTS if (spec_number(p, label_prefix) or 0) >= at_least), key=lambda p: (p.daily, p.id))


def available_for_weekend(friday: date) -> list[str]:
    from datetime import timedelta
    return sorted(p.id for p in D.PRODUCTS if D.available_for(p, friday, friday + timedelta(days=3)))


def accessories_for(product_id: str) -> list[str]:
    return sorted(a.id for a in D.compatible_accessories(D.BY_ID[product_id]))


def tile_cutter_for(day: date) -> list[str]:
    return sorted(p.id for p in D.PRODUCTS if "porcelain" in p.description.lower() and D.available_on(p, day))


@dataclass(frozen=True)
class Candidate:
    id: str
    friction: str          # which candidate scenario it is most sensitive to: discoverability | availability | cost | compatibility | none
    question: str
    answer: object
    how_graded: str


def candidate_tasks() -> list[Candidate]:
    tile, scaffold = D.PRODUCT_BY_SLUG["wet-tile-saw-250mm"], D.PRODUCT_BY_SLUG["aluminium-scaffold-tower-4m"]
    depth = cheapest_with_spec("Max cutting depth", 100)
    kit = D.BUNDLES[0]
    return [
        Candidate("ex-01", "none", "Which is the cheapest item (by daily rate) that can cut at least 100 mm deep?", depth.id, "exact product ID; derived from the 'Max cutting depth' spec rows"),
        Candidate("ex-02", "availability", "Which items can be hired for the whole weekend from Friday 6 November 2026 to Monday 9 November 2026?", available_for_weekend(date(2026, 11, 6)), "exact set of product IDs; uses the calendar rule that one unit is free every day"),
        Candidate("ex-03", "cost", "What is the total cost, including damage waiver and delivery, of hiring the wet tile saw for one weekend?", D.quote(tile, "weekend", waiver=True, delivery=True)["total"], "number in AUD; deposit excluded"),
        Candidate("ex-04", "cost", "What is the total cost of hiring the aluminium scaffold tower for three days with the damage waiver?", D.quote(scaffold, "3d", waiver=True)["total"], "number in AUD; delivery is required for this item and is included"),
        Candidate("ex-05", "compatibility", "Which accessories fit the electric demolition hammer?", accessories_for("IB-DRL-003"), "exact set of accessory IDs; includes universal and 240 V accessories"),
        Candidate("ex-06", "compatibility", "What are the weekend hire rate and the consumables cost of the concrete demolition kit?", {"weekend": D.bundle_rates(kit)["hire"]["weekend"], "consumables": D.bundle_rates(kit)["consumables"]}, "two numbers in AUD"),
        Candidate("ex-07", "discoverability", "I need to cut 20 porcelain bathroom tiles on Saturday 14 November 2026. Which item should I hire?", tile_cutter_for(date(2026, 11, 14)), "exact set of product IDs whose description mentions porcelain and that are free that day"),
        Candidate("ex-08", "discoverability", "I want to break up an old concrete path. Which item suits that job?", sorted(p.id for p in D.PRODUCTS if "breaking up paths" in p.description), "product ID; the only item whose description says it suits breaking up paths"),
    ]
