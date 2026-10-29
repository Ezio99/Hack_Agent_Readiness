"""Site profile and neutral observations from a Snapshot.

`build_profile` parses every page with the generic page model and derives site-level structure: link graph and click depth from the entry page, page templates (clusters of
pages sharing a parent path), listing->detail relations discovered from repeated item groups, and the distribution of labelled facts across them. `observations` turns that into
deterministic `Observation` records (facts with `page:` refs). Nothing here names a problem: it states what is present where. A reader (rule, verifier or model) draws conclusions."""
from __future__ import annotations

from collections import Counter, defaultdict, deque
from urllib.parse import urlsplit

from ..models import Observation, Provenance
from ..sitemodel.snapshot import Snapshot
from .pagemodel import norm, parse_page


def template_of(path: str, siblings: dict[str, int]) -> str:
    """`/courses/pottery` -> `/courses/{}` when >= 3 pages share the parent `/courses`; otherwise the exact path."""
    p = urlsplit(path).path.rstrip("/") or "/"
    parent, _, last = p.rpartition("/")
    return f"{parent}/{{}}" if siblings.get(parent or "/", 0) >= 3 and last else p


def build_profile(snap: Snapshot) -> dict:
    pages = {r.path: parse_page(r.path, r.text()) for r in snap.pages()}
    parents = Counter((urlsplit(p).path.rstrip("/").rpartition("/")[0] or "/") for p in pages if urlsplit(p).path != "/")
    tmpl = {p: template_of(p, parents) for p in pages}
    # link graph + click depth from "/"
    edges = {p: sorted({l["href"] for l in rec["links"] + rec["nav_links"] if l["href"] in pages}) for p, rec in pages.items()}
    depth, q = {"/": 0} if "/" in pages else {}, deque(["/"] if "/" in pages else [])
    while q:
        cur = q.popleft()
        for nxt in edges.get(cur, []):
            if nxt not in depth:
                depth[nxt] = depth[cur] + 1
                q.append(nxt)
    # listing -> detail relations from repeated item groups
    listings = []
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
                listings.append({"listing": p, "group": g["locator"], "items": len(g["items"]), "detail_template": Counter(tmpl[i["href"]] for i in details).most_common(1)[0][0],
                                 "fields": {k: {**v, "of": len(details)} for k, v in sorted(labels.items())}})
    unnamed = defaultdict(list)
    for p, rec in pages.items():
        for c in rec["controls"]:
            if not c["name"] or c["name_source"] == "placeholder":
                unnamed[tmpl[p]].append({"page": p, "tag": c["tag"], "type": c["type"], "href": c["href"], "landmark": c["landmark"], "locator": c["locator"], "weak_only": bool(c["name"])})
    return {"snapshot_sha256": snap.sha256, "pages": pages, "templates": {t: sorted(p for p, tt in tmpl.items() if tt == t) for t in sorted(set(tmpl.values()))},
            "depth": depth, "unreachable": sorted(set(pages) - set(depth)), "listings": listings, "unnamed_controls": dict(unnamed), "fidelity": snap.meta.get("fidelity", {})}


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
        add("listing_detail_fields", f"On {l['listing']} ({l['items']} repeated items linking to {l['detail_template']} pages): labelled fields on the linked pages whose value is NOT shown in the listing item: "
            f"{', '.join(sorted(absent)) or 'none'}; shown in the item: {', '.join(sorted(present)) or 'none'}.",
            {"listing": l["listing"], "detail_template": l["detail_template"], "fields": l["fields"], "not_in_listing": sorted(absent), "in_listing": sorted(present)}, [f"page:{l['listing']}"])
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
            nameless = [x for x in f["fields"] if not x["accessible_name"]]
            if nameless:
                add("form_fields_without_label", f"{p}: a form has {len(nameless)} field(s) with no label or accessible name.", {"page": p, "form": f["locator"], "count": len(nameless)}, [f"page:{p}"])
    return out
