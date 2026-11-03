"""Site definitions: everything site-specific the evaluation engine needs, and nothing else.

A `SiteDefinition` names a site, its variants (each a frozen, content-hashed snapshot; no URL field exists, so nothing is crawled on request), the page
agents start from, and, for CONTROLLED sites, an independent `RecordOracle` built from the site's own source data. Uncontrolled sites (saved
snapshots, the investigation zoo) have no oracle: their generated tasks are classified for human review and never count towards a score."""
from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from typing import Callable

from ..investigate.sitemodel.snapshot import Snapshot
from .oracle import Field, Record, RecordOracle


@dataclass(frozen=True)
class SiteDefinition:
    id: str
    label: str
    domain: str
    controlled: bool
    variants: tuple[str, ...]                        # first = the variant tasks are generated on ("original")
    snapshot: Callable[[str], Snapshot]
    start_path: str = "/"
    oracle: Callable[[], RecordOracle] | None = None
    notes: str = ""
    listings: tuple[str, ...] = ()                   # catalogue pages tasks are generated from (empty = every listing the profiler finds)
    noun: tuple[str, str] | None = None              # (singular, plural) entity noun used to phrase questions, e.g. ("course", "courses")
    kinds: tuple[str, ...] = field(default=("page_fact", "item_set", "extremum"))
    releases: tuple[str, ...] = ()                   # later website versions, registered as RE-EVALUATION targets only: never used to generate or
                                                     # validate tasks (that is `variants`), so recorded generations and datasets re-derive unchanged

    @property
    def registered(self) -> tuple[str, ...]:
        """Every registered website version: the generation pair, then later releases."""
        return self.variants + self.releases


# ---------------------------------------------------------------------------------------------------------------------------------- Ironbark
def _ironbark_snapshot(variant: str) -> Snapshot:
    """original = the control site; modified = the owner-selected listing change used by the hosted evaluation (S1 patch: refundable deposit, minimum
    hire and delivery shown on the listing cards). Hashes equal the hosted runner's ORIGINAL / MODIFIED constants (tested)."""
    from ..exp2 import snapshot as S
    snap = S.snapshot("control")
    if variant == "original":
        return snap
    if variant != "modified":
        raise ValueError(variant)
    return _ironbark_modified()


@lru_cache(maxsize=1)
def _ironbark_modified() -> Snapshot:
    import json
    from ..exp2 import snapshot as S
    from ..investigate.inspect.profile import build_profile
    from ..investigate.recommend import templates
    from ..investigate.sitemodel.patch import apply_patch
    from ..live import abtest
    snap = S.snapshot("control")
    patch, _ = templates.build("info_absent_on_template", {"labels": abtest.LABELS}, json.loads(json.dumps(build_profile(snap))), snap)
    return apply_patch(snap, patch)[0]


def _ironbark_oracle() -> RecordOracle:
    from ..sites.ironbark import data as D
    days = lambda n: f"{n} day" + ("" if n == 1 else "s")
    fields = {"refundable deposit": Field("deposit", "money", lambda v: f"${v}"), "per day": Field("daily", "money", lambda v: f"${v}"),
              "weekend": Field("weekend", "money", lambda v: f"${v}"), "per week": Field("weekly", "money", lambda v: f"${v}"),
              "minimum hire": Field("min_days", "number", days, unit="days"),
              "delivery and collection": Field("delivery", "text", lambda v: "Required for this item" if v == "required" else "Optional")}
    recs = []
    for p in D.PRODUCTS:
        values = {"deposit": p.deposit, "daily": p.daily, "weekend": p.weekend, "weekly": p.weekly, "min_days": p.min_days, "delivery": p.delivery}
        recs.append(Record(p.name, f"/hire/{p.slug}", values))
    return RecordOracle({"/hire": recs}, fields, label="ironbark data.PRODUCTS")


# ---------------------------------------------------------------------------------------------------------------------------------- Larkspur
def _larkspur_snapshot(variant: str) -> Snapshot:
    from ..sites.larkspur import render
    return render.snapshot(variant)


def _larkspur_oracle() -> RecordOracle:
    from ..sites.larkspur import data as D
    fields = {"course fee": Field("fee", "money", D.money), "duration": Field("weeks", "number", D.weeks, unit="weeks"), "level": Field("level", "text", str),
              "class day": Field("day", "text", str), "seats left": Field("seats_left", "number", str), "campus": Field("campus", "text", str), "materials": Field("materials", "text", str)}
    recs = [Record(c.name, f"/courses/{c.slug}", {k: getattr(c, k) for k in ("fee", "weeks", "level", "day", "seats_left", "campus", "materials")}) for c in D.COURSES]
    return RecordOracle({"/courses": recs}, fields, label="larkspur data.COURSES")


# ---------------------------------------------------------------------------------------------------------------------------------- uncontrolled
def _zoo(site: str) -> Callable[[str], Snapshot]:
    def snap(variant: str) -> Snapshot:
        from ..investigate import zoo
        return zoo.snapshot(site)
    return snap


SITES: dict[str, SiteDefinition] = {
    "ironbark": SiteDefinition("ironbark", "Ironbark Hire Co.", "equipment hire", True, ("original", "modified"), _ironbark_snapshot, oracle=_ironbark_oracle,
                               listings=("/hire",), noun=("hire machine", "hire machines"),
                               notes="Production evaluation site; source data sites/ironbark/data.py."),
    "larkspur": SiteDefinition("larkspur", "Larkspur Community College", "short-course catalogue", True, ("original", "modified"), _larkspur_snapshot, oracle=_larkspur_oracle,
                               listings=("/courses",), noun=("course", "courses"), releases=("improved", "polished", "polished2"),
                               notes="Second controlled site; source data sites/larkspur/data.py. `improved` applies every recommendation; `polished` is the human-centred redesign (Polished v1); `polished2` applies its evaluation's findings (Polished v2)."),
    **{f"zoo-{s}": SiteDefinition(f"zoo-{s}", f"Investigation zoo {s}", "synthetic (sealed diagnoses)", False, ("original",), _zoo(s),
                                  notes="Uncontrolled for this framework: no oracle, so tasks are human-review only.") for s in ("site-1", "site-2", "site-3", "site-4")},
}


def get(site_id: str) -> SiteDefinition:
    if site_id not in SITES:
        raise KeyError(f"unknown site {site_id!r}; registered: {', '.join(sorted(SITES))}")
    return SITES[site_id]
