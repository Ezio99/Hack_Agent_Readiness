"""Evidence-backed patch templates keyed by VERIFIED claim kind (general: they read the site profile, never a domain), plus the static re-check that the patch removes the very pattern the
finding verified. A template only exists where a safe, provenance-bound edit can express the fix; every other finding / idea becomes a manual (non-auto-applicable) proposal or none."""
from __future__ import annotations

from ..inspect.profile import build_profile
from ..sitemodel.patch import Patch, PatchError, apply_patch
from ..sitemodel.snapshot import Snapshot
from ..taskgen.criteria import norm_answer


def _group(profile: dict, listing: str, label: str | None = None) -> dict | None:
    """The repeated item group of a listing page. Without `label`, the largest group. With `label`, the largest group whose linked pages carry that labelled fact (a category page's navigation chips are a
    larger group than its products, and copying a product field into them would match nothing); None when no group carries it."""
    groups = sorted(profile["pages"][listing]["item_groups"], key=lambda g: -len(g["items"]))
    if label is not None:
        want = norm_answer(label)
        groups = [g for g in groups if sum(any(norm_answer(f["label"]) == want for f in profile["pages"].get(i["href"], {"facts": []})["facts"]) for i in g["items"]) * 2 >= len(g["items"])]
    return groups[0] if groups else None


def _css(group: dict) -> str:
    tag, _, classes = group["signature"].partition(".")                    # e.g. "li.card", "tr."
    return tag + "".join("." + c for c in classes.split(".") if c)


def item_css(profile: dict, listing: str, label: str | None = None) -> str | None:
    g = _group(profile, listing, label)
    return _css(g) if g else None


def _shown(group: dict | None, label: str) -> float:
    """Share of a group's items that show the labelled fact themselves."""
    want = norm_answer(label)
    return (sum(any(norm_answer(f["label"]) == want for f in i["facts"]) for i in group["items"]) / len(group["items"])) if group and group["items"] else 0.0


def _targets(profile: dict, label: str) -> list[tuple[str, str]]:
    """(listing page, item css) for every listing whose items carry the fact on their own pages but mostly do not show it themselves: exactly what the claim verified and what a patch can change."""
    out = []
    for path in sorted(profile["pages"]):
        g = _group(profile, path, label)
        if g and _shown(g, label) <= 0.5:
            out.append((path, _css(g)))
    return out


def _heading(profile: dict, path: str) -> str | None:
    p = profile["pages"].get(path)
    if not p:
        return None
    return (p["headings"][0]["text"] if p["headings"] else p["title"]) or None


def _bundle_pages(snapshot: Snapshot, ops: list[dict]) -> list[str]:
    """Listing pages whose targeted items are BUNDLES: at least half of the matched items link to two or more distinct captured pages (a kit panel listing its machines). Copying one machine's field into
    such an item would state something about the bundle that the machine's page does not establish, so applicability is not independently established and the listing is left out."""
    from bs4 import BeautifulSoup
    from ..inspect.pagemodel import internal_path
    out = []
    for o in ops:
        path = o["pages"][0]
        page = snapshot.get(path)
        if page is None or not page.is_html:
            continue
        items = BeautifulSoup(page.text(), "html.parser").select(o["css"])
        multi = sum(len({q for a in el.find_all("a", href=True) if (q := internal_path(a["href"], path)) and q in snapshot.resources and snapshot.resources[q].is_html}) >= 2 for el in items)
        if items and multi * 2 >= len(items):
            out.append(path)
    return out


def patch_for(claim_kind: str, params: dict, profile: dict) -> tuple[dict | None, str]:
    """(patch dict, why-or-note). None when no safe automatic edit exists for this kind."""
    if claim_kind == "info_absent_on_template":
        label = norm_answer(params.get("label") or "")
        key = next((k for l in profile["listings"] for k in l["fields"] if norm_answer(k) == label), None)
        ops = [{"op": "copy_field_to_listing", "pages": [path], "css": css, "source_label": key} for path, css in _targets(profile, label)] if key else []
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


def static_recheck(claim_kind: str, params: dict, before_profile: dict, new_snapshot: Snapshot, only_pages: list[str] | None = None) -> dict:
    """Does the patched snapshot stop exhibiting the pattern the finding verified? (Resolution is NOT an effect on agents; this only guards against proposing a patch that does nothing.)"""
    after = build_profile(new_snapshot)
    if claim_kind == "info_absent_on_template":
        label = norm_answer(params.get("label") or "")
        targets = {p: css for p, css in _targets(before_profile, label) if only_pages is None or p in only_pages}
        pages = set(targets)
        after_group = lambda p, css: next((g for g in after["pages"][p]["item_groups"] if _css(g) == css), None)                       # the SAME item group the patch targeted, not whichever group now looks best
        failing = [p for p in sorted(pages) if p in after["pages"] and _shown(after_group(p, targets[p]), label) < 0.9]
        return {"passed": bool(pages) and not failing, "failing": failing, "detail": ("the field is now shown on every item of the listings the patch targeted" if pages and not failing
                                                                                    else f"field still missing from some items on {', '.join(failing[:3])}" if failing else "no listing was targeted")}
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
    """(validated patch dict or None, info) where info records the template note, the application report and the static re-check. If some targeted listings do not end up showing the field (for example a panel
    whose items are bundles, not single items), those listings are dropped from the patch once and the rest is re-checked; nothing is offered unless every remaining target is fixed."""
    patch, note = patch_for(claim_kind, params, profile)
    if patch is None:
        return None, {"offered": False, "reason": note}
    bundles: list[str] = []
    if claim_kind == "info_absent_on_template":
        bundles = _bundle_pages(snapshot, patch["ops"])
        patch = {**patch, "ops": [o for o in patch["ops"] if o["pages"][0] not in bundles]}
        if not patch["ops"]:
            return None, {"offered": False, "reason": "every targeted listing holds bundles, whose applicability the item pages do not establish", "excluded_bundle_listings": bundles}
    dropped: list[str] = []
    for _ in range(2):
        try:
            new, rep = apply_patch(snapshot, patch)
        except PatchError as exc:
            return None, {"offered": False, "reason": f"patch refused by the safety rules: {exc}", **({"dropped_listings": dropped} if dropped else {})}
        pages = [o["pages"][0] for o in patch["ops"]] if claim_kind == "info_absent_on_template" else None
        rc = static_recheck(claim_kind, params, profile, new, pages)
        if rc["passed"]:
            return Patch.model_validate(patch).model_dump(), {"offered": True, "note": note, "recheck": rc, "patch_sha256": rep["patch_sha256"], "result_snapshot_sha256": rep["new_sha256"], "pages_changed": rep["pages_changed"],
                                                              "inserted_bytes": rep["inserted_bytes"], **({"dropped_listings": dropped} if dropped else {}), **({"excluded_bundle_listings": bundles} if bundles else {})}
        failing = rc.get("failing") or []
        if not failing or dropped:
            return None, {"offered": False, "reason": f"static re-check failed: {rc['detail']}", "recheck": rc}
        dropped = failing
        patch = {**patch, "ops": [o for o in patch["ops"] if o["pages"][0] not in failing]}
        if not patch["ops"]:
            return None, {"offered": False, "reason": "static re-check failed on every targeted listing", "recheck": rc}
    return None, {"offered": False, "reason": "static re-check failed"}
