"""Turn probe observations into findings. Every finding is an OBSERVED website property with counts and evidence; none attributes agent behaviour and none asserts an effect.

kinds:  attribute_detail_only  (problem)   an attribute is shown on product pages but not on listing cards
        attribute_partial_on_cards (problem) the attribute appears on some cards only (no library recommendation covers inconsistency yet)
        attribute_on_cards     (positive)  the attribute is shown on (almost) every listing card
        filter_present         (positive)  a listing page offers a filter for the attribute
        filter_absent          (problem)   listing pages offer filters, none for the attribute, and the attribute is detail-only
        insufficient_coverage  (limit)     the probe could not examine enough cards / detail pages to conclude
A finding's `fingerprint` (kind:attribute) is how a later audit recognises the same property, so lifecycle tracking never needs a human-supplied label."""
from __future__ import annotations

from .probe import ATTRIBUTES, FILTER_HINT, SiteObservations

MIN_CARDS, MIN_DETAILS = 3, 2
CARD_ABSENT_MAX, CARD_PRESENT_MIN, DETAIL_PRESENT_MIN = 0.10, 0.90, 0.50


def _rate(hits: int, n: int) -> float:
    return round(hits / n, 3) if n else 0.0


def attribute_stats(obs: SiteObservations) -> dict[str, dict]:
    stats = {}
    for spec in ATTRIBUTES:
        c_hits = [c for c in obs.cards if c.cues.get(spec.name)]
        d_hits = [d for d in obs.details if d.cues.get(spec.name)]
        stats[spec.name] = {"description": spec.description, "cards_examined": len(obs.cards), "cards_with_cue": len(c_hits), "card_cue_rate": _rate(len(c_hits), len(obs.cards)),
                            "details_examined": len(obs.details), "details_with_cue": len(d_hits), "detail_cue_rate": _rate(len(d_hits), len(obs.details)),
                            "listing_pages": len(obs.listing_pages)}
    return stats


def _card_evidence(obs, attr, present: bool, limit=4):
    cards = [c for c in obs.cards if bool(c.cues.get(attr)) == present][:limit]
    return [{"type": "listing_card", "url": c.listing_url, "card_index": c.index, "product_link": c.href, "locator": c.locator, "excerpt": c.text[:140],
             "cue": c.cues.get(attr)} for c in cards]


def _detail_evidence(obs, attr, limit=3):
    return [{"type": "product_page", "url": d.url, "locator": d.locator.get(attr), "cue": d.cues.get(attr), "title": d.title[:80]} for d in obs.details if d.cues.get(attr)][:limit]


def derive_findings(obs: SiteObservations) -> list[dict]:
    stats, out = attribute_stats(obs), []
    if len(obs.cards) < MIN_CARDS or not obs.listing_pages:
        return [{"fingerprint": "insufficient_coverage:site", "kind": "insufficient_coverage", "attribute": None, "category": "probe_limitation", "confidence": "observed",
                 "title": "The probe could not identify enough product cards to analyse", "summary": f"{len(obs.cards)} product cards on {len(obs.listing_pages)} listing pages were identified (need >= {MIN_CARDS}).",
                 "counts": {"cards": len(obs.cards), "listing_pages": len(obs.listing_pages)}, "evidence": []}]
    for attr, st in stats.items():
        if st["details_examined"] < MIN_DETAILS:
            out.append({"fingerprint": f"insufficient_coverage:{attr}", "kind": "insufficient_coverage", "attribute": attr, "category": "probe_limitation", "confidence": "observed",
                        "title": f"Too few product pages were examined to judge {attr}", "summary": f"{st['details_examined']} product pages examined (need >= {MIN_DETAILS}).", "counts": st, "evidence": []})
            continue
        if st["card_cue_rate"] <= CARD_ABSENT_MAX and st["detail_cue_rate"] >= DETAIL_PRESENT_MIN:
            out.append({"fingerprint": f"attribute_detail_only:{attr}", "kind": "attribute_detail_only", "attribute": attr, "category": "website_property", "confidence": "observed",
                        "title": f"{attr} is shown on product pages but not on listing cards",
                        "summary": (f"{st['cards_with_cue']} of {st['cards_examined']} listing cards (across {st['listing_pages']} listing pages) show {st['description']}; "
                                    f"{st['details_with_cue']} of {st['details_examined']} sampled product pages do."),
                        "counts": st, "evidence": _card_evidence(obs, attr, False, 3) + _detail_evidence(obs, attr)})
        elif CARD_ABSENT_MAX < st["card_cue_rate"] < CARD_PRESENT_MIN and st["detail_cue_rate"] >= DETAIL_PRESENT_MIN:
            out.append({"fingerprint": f"attribute_partial_on_cards:{attr}", "kind": "attribute_partial_on_cards", "attribute": attr, "category": "website_property", "confidence": "observed",
                        "title": f"{attr} is shown on only some listing cards",
                        "summary": f"{st['cards_with_cue']} of {st['cards_examined']} listing cards show {st['description']} (inconsistent); {st['details_with_cue']} of {st['details_examined']} product pages do.",
                        "counts": st, "evidence": _card_evidence(obs, attr, False, 2) + _card_evidence(obs, attr, True, 2)})
        elif st["card_cue_rate"] >= CARD_PRESENT_MIN:
            out.append({"fingerprint": f"attribute_on_cards:{attr}", "kind": "attribute_on_cards", "attribute": attr, "category": "website_property_positive", "confidence": "observed",
                        "title": f"{attr} is shown on listing cards",
                        "summary": f"{st['cards_with_cue']} of {st['cards_examined']} listing cards show {st['description']}.", "counts": st,
                        "evidence": _card_evidence(obs, attr, True, 3)})
    for attr in ("availability",):
        if any(f.attribute_filters.get(attr) for f in obs.filters):
            fl = [f for f in obs.filters if f.attribute_filters.get(attr)]
            out.append({"fingerprint": f"filter_present:{attr}", "kind": "filter_present", "attribute": attr, "category": "website_property_positive", "confidence": "observed",
                        "title": f"A {attr} filter is offered on listing pages", "summary": f"{len(fl)} listing pages offer a filter for {attr}.", "counts": {"listing_pages_with_filter": len(fl)},
                        "evidence": [{"type": "filter_form", "url": f.listing_url, "controls": [c for c in f.controls if FILTER_HINT[attr].search(c)][:3]} for f in fl[:2]]})
        if any(f["fingerprint"] == f"attribute_detail_only:{attr}" for f in out):
            with_filters = [f for f in obs.filters if f.controls]
            if with_filters and not any(f.attribute_filters.get(attr) for f in obs.filters):
                out.append({"fingerprint": f"filter_absent:{attr}", "kind": "filter_absent", "attribute": attr, "category": "website_property", "confidence": "observed",
                            "title": f"No {attr} filter is offered on listing pages",
                            "summary": f"{len(with_filters)} listing pages offer filters ({', '.join(sorted({c.split(' [')[0] for f in with_filters for c in f.controls if c.strip()})[:5])}) but none for {attr}.",
                            "counts": {"listing_pages_with_filters": len(with_filters)}, "evidence": [{"type": "filter_form", "url": f.listing_url, "controls": f.controls[:8]} for f in with_filters[:2]]})
    return out
