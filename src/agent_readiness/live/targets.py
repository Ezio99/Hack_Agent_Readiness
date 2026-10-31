"""Registered demo targets for live evaluation. There is no field anywhere that accepts a URL: a target is one of these ids, resolved to a captured snapshot served from loopback."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from ..investigate.sitemodel.snapshot import Snapshot


CONTEXT_MAX = 2000
SAMPLE_CONTEXT = {"ironbark": ("Ironbark Hire Co. is a family-run equipment-hire business in Marrickville, Sydney. Customers are mostly tradies and weekend DIY renovators who need a machine for a day, a weekend or a "
                               "week, and who usually compare two or three similar machines on daily or weekend rate, whether the machine is free on the dates they need, and the refundable deposit. Cutting tools "
                               "(tile saws, cut-off saws, chainsaws) are popular for paving and landscaping jobs. Priorities: shoppers should be able to see the hire rate and availability without phoning us, "
                               "and the booking calendar should be easy to find from the product page.")}


@dataclass(frozen=True)
class DemoTarget:
    id: str
    label: str
    description: str
    snapshot: Callable[[], Snapshot]


def _ironbark() -> Snapshot:
    from ..exp2 import snapshot as S
    return S.snapshot("control")


def _zoo(site: str) -> Callable[[], Snapshot]:
    def load() -> Snapshot:
        from ..investigate import zoo
        return zoo.snapshot(site)
    return load


TARGETS: dict[str, DemoTarget] = {t.id: t for t in (
    DemoTarget("ironbark", "Ironbark Hire Co.", "Fictional equipment-rental storefront: catalogue, kits, accessories, availability calendars and hire terms.", _ironbark),
    DemoTarget("site-4", "Synthetic test site 4", "Generated test site from the investigation zoo (opaque; used for pipeline testing).", _zoo("site-4")),
)}


def listing() -> list[dict]:
    return [{"id": t.id, "label": t.label, "description": t.description, **({"sample_context": SAMPLE_CONTEXT[t.id]} if t.id in SAMPLE_CONTEXT else {})} for t in TARGETS.values()]
