"""Controlled website design factors for electronics-v1. Underlying data and task wording never change when a factor changes.

availability: where stock state is shown.   listing  = on listing/search/home cards AND on the detail page (an in-stock filter exists)
                                              detail   = on the product detail page only (listing-level stock cues and the in-stock filter are removed)
specs:        how specifications are presented. structured = labelled specification table on the detail page and key-attribute chips on cards
                                              fragmented = the same facts written as marketing prose on the detail page; no chips on cards
Neither level is assumed better. The variant is selected by server configuration only; it never appears in URLs, headers or page text."""
from __future__ import annotations

from itertools import product

from ...suite.core import Variant
from .catalog import ENVIRONMENT_ID

FACTORS = {"availability": ("listing", "detail"), "specs": ("structured", "fragmented")}
DESCRIPTIONS = {
    ("availability", "listing"): "stock state visible on listing, search and home cards (and an in-stock filter)",
    ("availability", "detail"): "stock state only on product detail pages (no listing cue, no in-stock filter)",
    ("specs", "structured"): "labelled specification table on detail pages; key-attribute chips on cards",
    ("specs", "fragmented"): "the same specification facts written as prose on detail pages; no attribute chips on cards",
}


def make_variant(availability: str = "listing", specs: str = "structured") -> Variant:
    if availability not in FACTORS["availability"] or specs not in FACTORS["specs"]:
        raise ValueError(f"unknown factor level: availability={availability!r} specs={specs!r}")
    return Variant(ENVIRONMENT_ID, (("availability", availability), ("specs", specs)))


def all_variants() -> list[Variant]:
    return [make_variant(a, s) for a, s in product(FACTORS["availability"], FACTORS["specs"])]


DEFAULT_VARIANT = make_variant()
