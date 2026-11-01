"""Registered demo targets for live evaluation. There is no field anywhere that accepts a URL: a target is one of these ids, resolved to a captured snapshot served from loopback."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from ..investigate.sitemodel.snapshot import Snapshot


CONTEXT_MAX = 2000
SAMPLE_CONTEXT = {"ironbark": ("Ironbark Hire Co. is a family-run equipment-hire business in Marrickville, Sydney. Customers are mostly tradies and weekend DIY renovators who need a machine for a day, a weekend or a "
                               "week, and who usually compare two or three similar machines on daily or weekend rate, whether the machine is free on the dates they need, and the refundable deposit. Cutting tools "
                               "(tile saws, cut-off saws, chainsaws) are popular for paving and landscaping jobs. Priorities: shoppers should be able to see the hire rate and availability without phoning us, "
                               "and the booking calendar should be easy to find from the product page.")}


SAMPLE_CONTEXT["flask-docs"] = ("Flask is an open-source Python web framework. Its documentation is read by developers who are new to Flask or are configuring an application and want an exact setting or default value "
                                "quickly. Priorities: a developer should be able to find a named configuration setting and its default from the documentation navigation without reading whole chapters.")


@dataclass(frozen=True)
class DemoTarget:
    id: str
    label: str
    description: str
    snapshot: Callable[[], Snapshot]
    lexicon_id: str = "rental"                         # goal vocabulary: "rental" (Ironbark) or "neutral" (no domain vocabulary)
    term_values: bool = False                          # opt in to the `term_value` task kind for this target only
    live: bool = False                                 # may be started as a LIVE (real-model) job; a person must still confirm the spend and approve every paid stage
    available: Callable[[], bool] = lambda: True       # a saved-snapshot target is offered only when its snapshot exists on this machine

    def lexicon(self) -> dict:
        from .lexicon import NEUTRAL, RENTAL
        return {"rental": RENTAL, "neutral": NEUTRAL}[self.lexicon_id]


def _ironbark() -> Snapshot:
    from ..exp2 import snapshot as S
    return S.snapshot("control")


def _zoo(site: str) -> Callable[[], Snapshot]:
    def load() -> Snapshot:
        from ..investigate import zoo
        return zoo.snapshot(site)
    return load


SNAPSHOT_ROOT_ENV = "AR_TARGET_SNAPSHOTS"


def snapshot_dir(name: str) -> Path:
    """Where a SAVED snapshot target lives: `$AR_TARGET_SNAPSHOTS/<name>` or `<repo>/scanner-data/targets/<name>` (git-ignored). There is no URL field: a snapshot is captured offline by an operator
    (`scripts/capture_docs_snapshot.py`) from a site they host on loopback, never fetched on request."""
    root = os.environ.get(SNAPSHOT_ROOT_ENV)
    return (Path(root) if root else Path(__file__).resolve().parents[3] / "scanner-data" / "targets") / name


def _saved(name: str) -> tuple[Callable[[], Snapshot], Callable[[], bool]]:
    def load() -> Snapshot:
        d = snapshot_dir(name)
        if not (d / "index.json").exists():
            raise FileNotFoundError(f"the saved snapshot for target {name!r} is not on this machine ({d}); capture it with scripts/capture_docs_snapshot.py")
        return Snapshot.load(d)
    return load, lambda: (snapshot_dir(name) / "index.json").exists()


_flask_load, _flask_available = _saved("flask-docs")
TARGETS: dict[str, DemoTarget] = {t.id: t for t in (
    DemoTarget("ironbark", "Ironbark Hire Co.", "Fictional equipment-rental storefront: catalogue, kits, accessories, availability calendars and hire terms.", _ironbark, live=True),
    DemoTarget("site-4", "Synthetic test site 4", "Generated test site from the investigation zoo (opaque; used for pipeline testing).", _zoo("site-4")),
    DemoTarget("flask-docs", "Flask documentation (BSD-3)", "Self-hosted static build of the open-source Flask documentation: a script-stripped capture of a documentation site (navigation, API and configuration reference).",
               _flask_load, lexicon_id="neutral", term_values=True, live=True, available=_flask_available),
)}


def live_target_ids() -> tuple[str, ...]:
    return tuple(t.id for t in TARGETS.values() if t.live and t.available())


def listing() -> list[dict]:
    return [{"id": t.id, "label": t.label, "description": t.description, **({"sample_context": SAMPLE_CONTEXT[t.id]} if t.id in SAMPLE_CONTEXT else {})} for t in TARGETS.values() if t.available()]
