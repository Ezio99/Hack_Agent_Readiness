"""Site profile and neutral observations from a Snapshot.

`build_profile` parses every page with the generic page model and derives site-level structure: link graph and click depth from the entry page, page templates (clusters of
pages sharing a parent path), listing->detail relations discovered from repeated item groups, and the distribution of labelled facts across them. `observations` turns that into
deterministic `Observation` records (facts with `page:` refs). Nothing here names a problem: it states what is present where. A reader (rule, verifier or model) draws conclusions."""
from __future__ import annotations

from collections import Counter, defaultdict, deque
from urllib.parse import parse_qsl, urlsplit

from ..models import Observation, Provenance
from ..sitemodel.snapshot import Snapshot
from .pagemodel import norm, parse_page


def template_of(path: str, siblings: dict[str, int]) -> str:
    """`/courses/pottery` -> `/courses/{}` when >= 3 pages share the parent `/courses`; otherwise the exact path."""
    p = urlsplit(path).path.rstrip("/") or "/"
    parent, _, last = p.rpartition("/")
    return f"{parent}/{{}}" if siblings.get(parent or "/", 0) >= 3 and last else p


# PROVISIONAL heuristics: tuned on Ironbark, one Sphinx documentation site and four generic test sites only; not generally validated. Changing them changes model-visible observations and prompts.
CATALOGUE_SHARE, CATALOGUE_MIN_PAGES, UNCERTAIN_SHARE = 0.5, 2, 0.25


def classify_listing(distinct: dict[str, int], n_pages: int) -> tuple[str, str]:
    """A group of repeated links is an item LISTING when its linked pages state the same labelled field (counted over distinct pages). A group whose linked pages share no field (a sidebar contents,
    filter chips, category tiles, a list of examples) is a NAVIGATION GROUP. In between it is kept as a listing and marked `uncertain`; nothing is dropped silently."""
    best = max(distinct.values(), default=0)
    share = best / n_pages if n_pages else 0.0
    shared = sorted(k for k, v in distinct.items() if v >= CATALOGUE_MIN_PAGES and v / n_pages >= CATALOGUE_SHARE)
    basis = f"{len(shared)} labelled field(s) are stated on at least half of the {n_pages} distinct linked pages; the best is stated on {best}"
    if len(shared) >= 2:                                           # a real catalogue states several of the same fields on most of its item pages
        return "catalogue", basis
    if best >= CATALOGUE_MIN_PAGES and share >= UNCERTAIN_SHARE:   # one shared field, or weaker overlap: kept as a listing, flagged
        return "uncertain", basis
    return "navigation_group", basis


def build_profile(snap: Snapshot) -> dict:
    pages = {r.path: parse_page(r.path, r.text()) for r in snap.pages()}
    parents = Counter((urlsplit(p).path.rstrip("/").rpartition("/")[0] or "/") for p in pages if urlsplit(p).path != "/")
    tmpl = {p: template_of(p, parents) for p in pages}
    # link graph + click depth from "/"
    edges = {p: sorted({l["href"] for l in rec["links"] + rec["nav_links"] if l["href"] in pages}) for p, rec in pages.items()}
    # A GET form is navigation too: submitting it opens its action with the form's own field names, so every captured page it can produce is one
    # interaction away (pages reached only through a form were otherwise reported as unreachable). Sites without GET forms are unaffected.
    via_form = {p: sorted({t for f in rec["forms"] if f["method"] == "get" and f["action"] for t in pages
                           if urlsplit(t).query and urlsplit(t).path == urlsplit(f["action"]).path
                           and {k for k, _ in parse_qsl(urlsplit(t).query, keep_blank_values=True)} <= {x["name_attr"] for x in f["fields"] if x.get("name_attr")}})
                for p, rec in pages.items() if rec["forms"]}
    depth, q = {"/": 0} if "/" in pages else {}, deque(["/"] if "/" in pages else [])
    while q:
        cur = q.popleft()
        for nxt in edges.get(cur, []) + via_form.get(cur, []):
            if nxt not in depth:
                depth[nxt] = depth[cur] + 1
                q.append(nxt)
    # listing -> detail relations from repeated item groups
    listings, navigation_groups = [], []
    for p, rec in pages.items():
        for g in rec["item_groups"]:
            details = [i for i in g["items"] if i["href"] in pages]
            if len(details) >= 3:
                labels = defaultdict(lambda: {"detail_pages": 0, "in_listing_item": 0})
                for it in details:
                    d_facts = pages[it["href"]]["facts"]
                    for f in d_facts:
                        row = labels[f["label"]]
                        row["detail_pages"] += 1
                        row["in_listing_item"] += int(norm(f["value"]).lower() in it["text"].lower())
                hrefs = sorted({i["href"] for i in details})
                distinct = {k: sum(1 for h in hrefs if any(f["label"] == k for f in pages[h]["facts"])) for k in labels}       # the fact-row counts above can exceed the page count (one page, many same-labelled terms)
                row = {"listing": p, "group": g["locator"], "items": len(g["items"]), "detail_template": Counter(tmpl[i["href"]] for i in details).most_common(1)[0][0],
                       "fields": {k: {**v, "of": len(details), "distinct_pages": distinct[k]} for k, v in sorted(labels.items())}}
                row["classification"], row["classification_basis"] = classify_listing(distinct, len(hrefs))
                (navigation_groups if row["classification"] == "navigation_group" else listings).append(row)
    unnamed, hidden_unnamed = defaultdict(list), []
    for p, rec in pages.items():
        for c in rec["controls"]:
            if not c["name"] or c["name_source"] == "placeholder":
                row = {"page": p, "tag": c["tag"], "type": c["type"], "href": c["href"], "landmark": c["landmark"], "locator": c["locator"], "weak_only": bool(c["name"])}
                (hidden_unnamed if c.get("hidden_in_capture") else unnamed[tmpl[p]]).append(row)       # a control inside an element hidden in the capture is reported separately, never counted as a finding nor dropped
    return {"snapshot_sha256": snap.sha256, "pages": pages, "templates": {t: sorted(p for p, tt in tmpl.items() if tt == t) for t in sorted(set(tmpl.values()))},
            "depth": depth, "unreachable": sorted(set(pages) - set(depth)), "listings": listings, "navigation_groups": navigation_groups, "unnamed_controls": dict(unnamed), "hidden_unnamed_controls": hidden_unnamed, "fidelity": snap.meta.get("fidelity", {})}


def observations(profile: dict, *, mode: str = "scripted", source: str = "rule:inspector") -> list[Observation]:
    prov = Provenance(mode=mode, source=source)
    pages, out = profile["pages"], []

    def add(kind, summary, data, refs):
        out.append(Observation(kind=kind, summary=summary, data=data, refs=refs, provenance=prov))
    depths = sorted(profile["depth"].values())
    add("site_overview", f"{len(pages)} pages captured in {len(profile['templates'])} templates; click depth from the entry page ranges 0-{depths[-1] if depths else 0}; "
        f"{len(profile['unreachable'])} captured pages not reachable by links from the entry page.",
        {"pages": len(pages), "templates": {t: len(v) for t, v in profile["templates"].items()}, "max_depth": depths[-1] if depths else 0, "unreachable": profile["unreachable"]}, ["page:/"])
    fid = profile["fidelity"]
    if fid:
        add("snapshot_fidelity", f"Capture removed {fid.get('scripts_removed', 0)} script(s); fidelity level {fid.get('level')}.", fid, [])
    for l in profile["listings"]:
        absent = {k: v for k, v in l["fields"].items() if v["in_listing_item"] < v["detail_pages"] and v["detail_pages"] >= max(2, v["of"] // 2)}
        present = {k: v for k, v in l["fields"].items() if k not in absent}
        add("listing_detail_fields", f"On {l['listing']} ({l['items']} repeated items linking to {l['detail_template']} pages" + ("; UNCERTAIN item listing: " + l["classification_basis"] if l.get("classification") == "uncertain" else "") + f"): labelled fields on the linked pages whose value is NOT shown in the listing item: "
            f"{', '.join(sorted(absent)) or 'none'}; shown in the item: {', '.join(sorted(present)) or 'none'}.",
            {"listing": l["listing"], "detail_template": l["detail_template"], "fields": l["fields"], "not_in_listing": sorted(absent), "in_listing": sorted(present)}, [f"page:{l['listing']}"])
    nav = profile.get("navigation_groups", [])
    if nav:                                                              # explicit, not silent: groups of repeated links whose linked pages share no labelled field are not item listings
        add("navigation_link_groups", f"{len(nav)} group(s) of repeated links were classified as NAVIGATION, not as item listings (their linked pages share no labelled field): "
            + "; ".join(f"{g['listing']} -> {g['detail_template']} ({g['items']} links)" for g in nav[:8]) + (" ..." if len(nav) > 8 else "") + ".",
            {"groups": [{"listing": g["listing"], "detail_template": g["detail_template"], "items": g["items"], "basis": g["classification_basis"]} for g in nav]}, [f"page:{g['listing']}" for g in nav[:6]])
    hid = profile.get("hidden_unnamed_controls", [])
    hid_fields = [(p, f) for p, rec in pages.items() for fm in rec["forms"] for f in fm["fields"] if f.get("hidden_in_capture") and not f["accessible_name"]]
    if hid or hid_fields:
        add("controls_hidden_in_capture", f"{len(hid)} control(s) and {len(hid_fields)} form field(s) without an accessible name sit inside an element that is hidden in the captured HTML (typically revealed by a script "
            f"the capture removed; {fid.get('scripts_removed', 0) if fid else 0} script(s) were removed). They are NOT counted as accessibility findings: the live site may show and label them.",
            {"controls": hid[:12], "fields": [{"page": p, "tag": f["tag"], "locator": f["locator"]} for p, f in hid_fields[:12]], "count_controls": len(hid), "count_fields": len(hid_fields)},
            [f"page:{i['page']}" for i in hid[:6]] + [f"page:{p}" for p, _ in hid_fields[:6]])
    for tmpl, items in sorted(profile["unnamed_controls"].items()):
        strong = [i for i in items if not i["weak_only"]]
        key = lambda i: (i["tag"], i["type"], i["href"], i["landmark"])
        distinct = {key(i) for i in strong}                      # a navigation icon repeated on every page is ONE control, not one per page
        add("controls_without_accessible_name", f"Template {tmpl}: {len(distinct)} distinct interactive control(s) have no accessible name ({len(strong)} occurrences across {len({i['page'] for i in strong})} page(s)) and "
            f"{len(items) - len(strong)} occurrence(s) rely on a placeholder only.",
            {"template": tmpl, "controls": items[:12], "count_no_name": len(strong), "distinct_no_name": len(distinct), "count_placeholder_only": len(items) - len(strong)}, [f"page:{i['page']}" for i in items[:6]])
    deep = {p: d for p, d in profile["depth"].items() if d >= 3}
    if deep:
        add("deep_pages", f"{len(deep)} page(s) are 3 or more link steps from the entry page: {', '.join(sorted(deep)[:6])}.", {"pages": deep}, [f"page:{p}" for p in sorted(deep)[:6]])
    for p, rec in pages.items():
        bad_imgs = [i for i in rec["images"] if i["alt"] is None]
        if bad_imgs:
            add("images_without_alt", f"{p}: {len(bad_imgs)} image(s) have no alt attribute.", {"page": p, "count": len(bad_imgs)}, [f"page:{p}"])
        for f in rec["forms"]:
            nameless = [x for x in f["fields"] if not x["accessible_name"] and not x.get("hidden_in_capture")]
            if nameless:
                add("form_fields_without_label", f"{p}: a form has {len(nameless)} field(s) with no label or accessible name.", {"page": p, "form": f["locator"], "count": len(nameless)}, [f"page:{p}"])
    return out
