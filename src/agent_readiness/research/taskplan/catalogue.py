"""The verified catalogue view given to the planner: only attributes the site's independent oracle can answer, with their value domains and units,
taken from the site's source records (never from the LLM). Its fingerprint, together with the site version hashes, identifies exactly what the
planner saw."""
from __future__ import annotations

from ...framework.site import SiteDefinition
from ...suite.core import canonical_hash


def view(site: SiteDefinition) -> dict:
    oracle = site.oracle()
    listing, records = next(iter(oracle.listings.items()))
    attrs = []
    for label, f in sorted(oracle.fields.items()):
        vals = [r.values[f.name] for r in records if f.name in r.values]
        a = {"attribute": label, "kind": f.kind, "unit": "$" if f.kind == "money" else f.unit or None}
        if f.kind == "text":
            a["values"] = sorted({f.show(v) for v in vals})
        else:
            a["range"] = [f.show(min(vals)), f.show(max(vals))]
        attrs.append(a)
    items = [{"name": r.name, "page": r.path, **{label: oracle.fields[label].show(r.values[f.name]) for label, f in oracle.fields.items() if f.name in r.values}} for r in records]
    return {"site": site.id, "label": site.label, "listing": listing, "start_path": site.start_path, "entity": site.noun[0] if site.noun else "item",
            "attributes": attrs, "items": items, "versions": {v: site.snapshot(v).sha256 for v in site.variants}}


def fingerprint(v: dict) -> str:
    return canonical_hash(v)
