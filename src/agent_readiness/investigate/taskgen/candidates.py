"""Deterministic (rule-generated) task candidates from a site profile: an offline baseline and a top-up when the model proposes too few valid tasks. Questions are templated from the
site's own headings and field labels — no domain vocabulary. Every candidate still passes the same gate as model and owner tasks."""
from __future__ import annotations

from .criteria import CriterionError, _fact, _items, norm_answer, quantity
from .gate import Draft


def _noun(profile: dict, listing: str) -> str:
    h = profile["pages"][listing]["headings"]
    return (h[0]["text"] if h else listing.strip("/") or "items").lower()


def _title(page: dict) -> str:
    return page["headings"][0]["text"] if page["headings"] else page["title"]


def candidates(profile: dict, start: str = "/", per_kind: int = 3) -> list[Draft]:
    pages = profile["pages"]
    out: dict[str, list[Draft]] = {"page_fact": [], "item_set": [], "extremum": []}
    for l in profile["listings"]:
        L = l["listing"]
        try:
            items = _items(profile, L)
        except CriterionError:
            continue
        noun = _noun(profile, L)
        for label in l["fields"]:
            vals = [(_fact(pages[i["href"]], label), i) for i in items]
            if any(len(v) != 1 for v, _ in vals):
                continue
            raw = [v[0] for v, _ in vals]
            qs = [quantity(r) for r in raw]
            numeric = all(q is not None for q in qs) and len({q[1] for q in qs}) == 1 and len({q[0] for q in qs}) >= 3
            if numeric:
                ordered = sorted(zip(qs, raw), key=lambda x: x[0][0])
                med = ordered[len(ordered) // 2][1]
                out["extremum"].append(Draft(f"Among the {noun} listed, which one has the highest {label}? Give its name.", start, {"kind": "extremum", "listing": L, "label": label, "direction": "max"}, "rule"))
                out["extremum"].append(Draft(f"Among the {noun} listed, which one has the lowest {label}? Give its name.", start, {"kind": "extremum", "listing": L, "label": label, "direction": "min"}, "rule"))
                out["item_set"].append(Draft(f"Which of the {noun} have a {label} below {med}? List their names.", start, {"kind": "item_set", "listing": L, "conditions": [{"label": label, "op": "lt", "value": med}]}, "rule"))
            else:
                counts: dict[str, int] = {}
                for r in raw:
                    counts[norm_answer(r)] = counts.get(norm_answer(r), 0) + 1
                minority = [r for r in dict.fromkeys(raw) if 1 <= counts[norm_answer(r)] <= len(raw) // 2 and len(r) <= 30]
                if minority:
                    out["item_set"].append(Draft(f"Which of the {noun} have {label} '{minority[0]}'? List their names.", start, {"kind": "item_set", "listing": L, "conditions": [{"label": label, "op": "eq", "value": minority[0]}]}, "rule"))
        first = items[0]
        for label in list(l["fields"])[:2]:
            out["page_fact"].append(Draft(f"What is the {label} of {first['name']}?", start, {"kind": "page_fact", "page": first["href"], "label": label}, "rule"))
    listing_pages = {l["listing"] for l in profile["listings"]}
    detail_pages = {i["href"] for l in profile["listings"] for g in pages[l["listing"]]["item_groups"] for i in g["items"]}
    for p, rec in sorted(pages.items()):
        if p in listing_pages or p in detail_pages or not rec["facts"]:
            continue
        for f in rec["facts"][:1]:
            out["page_fact"].append(Draft(f"What is the {f['label']} listed under '{_title(rec)}'?", start, {"kind": "page_fact", "page": p, "label": f["label"]}, "rule"))
    result, i = [], 0
    kinds = [k for k in out if out[k]]
    while any(out[k][i:i + 1] for k in kinds) and i < per_kind:
        result += [out[k][i] for k in kinds if i < len(out[k])]
        i += 1
    return result
