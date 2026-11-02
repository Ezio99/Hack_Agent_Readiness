"""Structural observations from a frozen snapshot's profile (investigate/inspect: the same profiler the task generator uses). Every observation is
reproducible from the snapshot hash. Status is `observed` (it is a page fact); whether it matters to agents is the hypothesis layer's question.

Rules (deliberately few):
  listing-fact-gap        a fact stated on (almost) every item page of a listing is absent from (almost) every listing card: comparing items on it
                          requires opening every item page
  unnamed-control         a link or button with no accessible name
  heading-structure       a page without exactly one h1, or with a skipped heading level
  missing-landmark        a page without a main or nav landmark
  image-alt               an image without a text alternative
  form-label              a form control without a label
  no-structured-data      item pages carry no machine-readable (JSON-LD / microdata) description of the item
  unreachable-page        a captured page not reachable by links from the start page"""
from __future__ import annotations

import re

from .model import Evidence, Finding, stable_id

GAP_DETAIL_MIN, GAP_LISTING_MAX = 0.8, 0.2


def _f(rule, title, site, version, sha, severity, impact, evidence, rec, verify, subject, detail=None) -> Finding:
    return Finding(stable_id("S", rule, site, subject), "structural", rule, title, site, version, sha, severity, impact, "observed", evidence, rec, verify, detail=detail or {})


def observe(profile: dict, *, site: str, version: str) -> list[Finding]:
    sha = profile["snapshot_sha256"]
    pages, out = profile["pages"], []
    listing_pages = {l["listing"] for l in profile["listings"]}
    groups: dict[str, list[dict]] = {}
    for l in profile["listings"]:
        if l.get("classification") not in (None, "catalogue"):
            continue
        tpl = re.compile("^" + re.escape(l.get("detail_template") or "").replace(re.escape("{}"), "[^/?#]+") + "$")
        hrefs = [i["href"] for g in pages[l["listing"]]["item_groups"] for i in g["items"] if tpl.match(i["href"])]
        if hrefs and sum(h in listing_pages for h in hrefs) > len(hrefs) / 2:          # sort/filter chips: their "items" are other listing pages, not catalogue items
            continue
        groups.setdefault(l.get("detail_template") or l["listing"], []).append(l)
    for template, ls in sorted(groups.items()):
        l = max(ls, key=lambda x: (x["items"] if isinstance(x["items"], int) else len(x["items"]), -len(x["listing"])))     # the fullest listing of these item pages
        others = sorted({x["listing"] for x in ls} - {l["listing"]})
        n = l["items"] if isinstance(l["items"], int) else len(l["items"])
        for label, c in sorted(l["fields"].items()):
            on_pages, on_cards = c["distinct_pages"] / max(n, 1), c["in_listing_item"] / max(n, 1)
            if on_pages >= GAP_DETAIL_MIN and on_cards <= GAP_LISTING_MAX:
                ev = [Evidence("listing_field", f"{l['listing']}#{label}", f"stated on {c['distinct_pages']}/{n} item pages ({template}), on {c['in_listing_item']}/{n} listing cards"),
                      Evidence("page", l["listing"], l.get("group", ""))] + ([Evidence("page", ", ".join(others[:6]) + (" ..." if len(others) > 6 else ""), f"{len(others)} other listings of the same items")] if others else [])
                out.append(_f("listing-fact-gap", f"'{label}' is only on item pages, not on the {l['listing']} listing", site, version, sha, "medium",
                              f"an agent comparing items by {label} must open up to {n} item pages", ev,
                              f"State {label} on each card of {l['listing']} (visible text next to the item name).",
                              f"Re-run diagnostics: '{label}' appears on {n}/{n} listing cards; then run a paired evaluation on tasks that compare {label}.",
                              f"{template}#{label}", {"listing": l["listing"], "template": template, "label": label, "items": n, "detail_pages": c["distinct_pages"], "listing_cards": c["in_listing_item"]}))
    for path, rec in sorted(pages.items()):
        for c in rec.get("controls", []):
            if not (c.get("name") or "").strip() and not c.get("hidden_in_capture"):
                out.append(_f("unnamed-control", f"{c.get('tag')} without an accessible name on {path}", site, version, sha, "medium",
                              "agents that act on the accessibility tree cannot tell what this control does",
                              [Evidence("locator", f"{path} {c.get('locator')}", f"href={c.get('href')}")], "Give the control a visible label or aria-label.",
                              "Re-run diagnostics: the control has a non-empty accessible name.", f"{path}|{c.get('locator')}|{c.get('href')}"))
        h1 = [h for h in rec.get("headings", []) if h["level"] == 1]
        levels = [h["level"] for h in rec.get("headings", [])]
        skipped = any(b - a > 1 for a, b in zip(levels, levels[1:]))
        if rec.get("headings") is not None and (len(h1) != 1 or skipped):
            out.append(_f("heading-structure", f"heading structure on {path}: {len(h1)} h1{', skipped level' if skipped else ''}", site, version, sha, "low",
                          "a page outline helps an agent find the section that answers a question", [Evidence("page", path, f"levels {levels[:12]}")],
                          "Use exactly one h1 and do not skip heading levels.", "Re-run diagnostics: one h1 and no skipped levels.", path))
        lm = set(rec.get("landmarks", []))
        if not {"main", "nav"} <= lm:
            out.append(_f("missing-landmark", f"{path} lacks {', '.join(sorted({'main', 'nav'} - lm))} landmark", site, version, sha, "low",
                          "landmarks let an agent skip page chrome", [Evidence("page", path, f"landmarks {sorted(lm)}")],
                          "Wrap primary content in <main> and site navigation in <nav>.", "Re-run diagnostics: both landmarks present.", f"{path}|landmarks"))
        for img in rec.get("images", []):
            if img.get("alt") in (None,) and not img.get("decorative"):
                out.append(_f("image-alt", f"image without a text alternative on {path}", site, version, sha, "low", "information in the image is invisible to text-based agents",
                              [Evidence("locator", f"{path} {img.get('src')}")], "Add alt text (or alt=\"\" if decorative).", "Re-run diagnostics: every image has an alt attribute.", f"{path}|{img.get('src')}"))
        for form in rec.get("forms", []):
            for fld in form.get("fields", []):
                if not (fld.get("label") or fld.get("name_source") not in (None, "none")):
                    out.append(_f("form-label", f"unlabelled form control on {path}", site, version, sha, "medium", "an agent cannot tell what to type",
                                  [Evidence("locator", f"{path} {fld.get('locator', fld.get('name'))}")], "Associate a <label> with the control.", "Re-run diagnostics: the control is labelled.",
                                  f"{path}|{fld.get('locator', fld.get('name'))}"))
    detail_pages = {i for l in profile["listings"] for g in pages[l["listing"]]["item_groups"] for i in (x["href"] for x in g["items"]) if i in pages}
    if detail_pages and not any(pages[p].get("structured_data") for p in detail_pages):
        out.append(_f("no-structured-data", f"none of {len(detail_pages)} item pages carries structured data", site, version, sha, "info",
                      "agents and tools that read JSON-LD get nothing machine-readable; the visible text is the only source",
                      [Evidence("page", sorted(detail_pages)[0], f"and {len(detail_pages) - 1} more item pages")],
                      "Describe each item with schema.org JSON-LD (e.g. Product/Offer or Course) using the same values the page shows.",
                      "Re-run diagnostics: item pages carry structured data whose values match the visible facts.", "item-pages"))
    for path in sorted(profile.get("unreachable") or []):
        out.append(_f("unreachable-page", f"{path} is not reachable by links from the start page", site, version, sha, "low", "agents navigating by links cannot find it",
                      [Evidence("page", path)], "Link the page from navigation or a relevant page.", "Re-run diagnostics: the page is reachable.", path))
    return out


def compare(before: list[Finding], after: list[Finding]) -> dict:
    """Which structural findings a version change resolved, introduced or left in place (matched by stable id)."""
    b, a = {f.id: f for f in before}, {f.id: f for f in after}
    return {"resolved": sorted(set(b) - set(a)), "introduced": sorted(set(a) - set(b)), "persisting": sorted(set(a) & set(b)),
            "titles": {i: (b.get(i) or a.get(i)).title for i in set(a) | set(b)}}
