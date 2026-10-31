"""Registered demo targets for live evaluation. There is no field anywhere that accepts a URL: a target is one of these ids, resolved to a captured snapshot served from loopback."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from ..investigate.sitemodel.snapshot import Snapshot


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
    return [{"id": t.id, "label": t.label, "description": t.description} for t in TARGETS.values()]
