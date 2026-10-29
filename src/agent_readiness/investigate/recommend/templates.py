"""Evidence-backed patch templates keyed by VERIFIED claim kind (general: they read the site profile, never a domain), plus the static re-check that the patch removes the very pattern the
finding verified. A template only exists where a safe, provenance-bound edit can express the fix; every other finding / idea becomes a manual (non-auto-applicable) proposal or none."""
from __future__ import annotations

from ..inspect.profile import build_profile
from ..sitemodel.patch import Patch, PatchError, apply_patch
from ..sitemodel.snapshot import Snapshot
from ..taskgen.criteria import norm_answer


def item_css(profile: dict, listing: str) -> str | None:
    groups = profile["pages"][listing]["item_groups"]
    if not groups:
        return None
    sig = max(groups, key=lambda g: len(g["items"]))["signature"]            # e.g. "li.card", "tr."
    tag, _, classes = sig.partition(".")
    return tag + "".join("." + c for c in classes.split(".") if c)


def _heading(profile: dict, path: str) -> str | None:
    p = profile["pages"].get(path)
    if not p:
        return None
    return (p["headings"][0]["text"] if p["headings"] else p["title"]) or None


def patch_for(claim_kind: str, params: dict, profile: dict) -> tuple[dict | None, str]:
    """(patch dict, why-or-note). None when no safe automatic edit exists for this kind."""
    if claim_kind == "info_absent_on_template":
        label = norm_answer(params.get("label") or "")
        ops = []
        for l in profile["listings"]:
            key = next((k for k in l["fields"] if norm_answer(k) == label), None)
            css = item_css(profile, l["listing"])
            f = l["fields"].get(key) if key else None
            if f and css and f["in_listing_item"] <= f["detail_pages"] * 0.5:
                ops.append({"op": "copy_field_to_listing", "pages": [l["listing"]], "css": css, "source_label": key})
        return ({"description": f"show the '{label}' field on each listing item", "ops": ops}, "copy the field from each item's page into the listing item") if ops else (None, "no listing lacks that field")
    if claim_kind == "control_unlabeled":
        by_href: dict[str, set[str]] = {}
        for rows in profile["unnamed_controls"].values():
            for c in rows:
                if c["href"] and c["tag"] == "a" and not c["weak_only"]:
                    by_href.setdefault(c["href"], set()).add(c["page"])
        ops = []
        for href, pages in sorted(by_href.items())[:12]:
            label = _heading(profile, href)
            if label:
                ops.append({"op": "set_attribute", "pages": sorted(pages)[:30], "css": f'a[href="{href}"]', "attr": "aria-label", "value": label, "only_unnamed": True})
        return ({"description": "give icon-only links an accessible name taken from their destination page's heading", "ops": ops}, "label unnamed links from their destination headings") if ops else (None, "no unnamed link with a labelled destination (unnamed buttons / inputs have no safe automatic label)")
    if claim_kind == "info_only_after_k_hops":
        k = params.get("k") if isinstance(params.get("k"), int) else 3
        deep = sorted((p for p, d in profile["depth"].items() if d >= k), key=lambda p: profile["depth"][p])[:3]
        ops = [{"op": "add_link", "pages": ["/"], "css": "main", "position": "append", "href": p, "text": _heading(profile, p)} for p in deep if _heading(profile, p)]
        return ({"description": f"link pages that are {k}+ steps deep from the entry page", "ops": ops}, "add entry-page links to the deepest pages") if ops else (None, "no deep page with a heading")
    return None, f"no automatic patch exists for claim kind {claim_kind!r}"


def static_recheck(claim_kind: str, params: dict, before_profile: dict, new_snapshot: Snapshot) -> dict:
    """Does the patched snapshot stop exhibiting the pattern the finding verified? (Resolution is NOT an effect on agents; this only guards against proposing a patch that does nothing.)"""
    after = build_profile(new_snapshot)
    if claim_kind == "info_absent_on_template":
        label = norm_answer(params.get("label") or "")
        for l in after["listings"]:
            key = next((k for k in l["fields"] if norm_answer(k) == label), None)
            if key and l["fields"][key]["in_listing_item"] < l["fields"][key]["detail_pages"] * 0.9:
                return {"passed": False, "detail": f"field still missing from some items on {l['listing']}"}
        return {"passed": True, "detail": "the field is now shown on (almost) every listing item"}
    if claim_kind == "control_unlabeled":
        n = lambda p: sum(1 for rows in p["unnamed_controls"].values() for c in rows if not c["weak_only"])
        b, a = n(before_profile), n(after)
        return {"passed": a < b, "detail": f"controls without an accessible name: {b} -> {a}"}
    if claim_kind == "info_only_after_k_hops":
        k = params.get("k") if isinstance(params.get("k"), int) else 3
        b = sum(1 for d in before_profile["depth"].values() if d >= k)
        a = sum(1 for d in after["depth"].values() if d >= k)
        return {"passed": a < b, "detail": f"pages {k}+ steps deep: {b} -> {a}"}
    return {"passed": False, "detail": "no static re-check for this claim kind"}


def build(claim_kind: str, params: dict, profile: dict, snapshot: Snapshot) -> tuple[dict | None, dict]:
    """(validated patch dict or None, info) where info records the template note, the application report and the static re-check."""
    patch, note = patch_for(claim_kind, params, profile)
    if patch is None:
        return None, {"offered": False, "reason": note}
    try:
        new, rep = apply_patch(snapshot, patch)
    except PatchError as exc:
        return None, {"offered": False, "reason": f"patch refused by the safety rules: {exc}"}
    rc = static_recheck(claim_kind, params, profile, new)
    if not rc["passed"]:
        return None, {"offered": False, "reason": f"static re-check failed: {rc['detail']}", "recheck": rc}
    return Patch.model_validate(patch).model_dump(), {"offered": True, "note": note, "recheck": rc, "patch_sha256": rep["patch_sha256"], "result_snapshot_sha256": rep["new_sha256"], "pages_changed": rep["pages_changed"],
                                                      "inserted_bytes": rep["inserted_bytes"]}
