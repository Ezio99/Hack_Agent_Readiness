"""Rule-based recommendation library. A recommendation is SELECTED only if an observed finding matches its `addresses` rule; its text is generated from the finding's own counts.
Status vocabulary is deliberate: a recommendation is a *proposed intervention* with status `unvalidated` until a controlled experiment supplies a measured effect
(see `engine.attach_measured_effects`); prior evidence from another site is labelled as such and never presented as proof for this site.

Extending: add a `Template` (new kind/attribute rule) — and, for previously unknown problems, a trace detector in `discovery.py` that emits candidate findings with no
recommendation until a template exists."""
from __future__ import annotations

from dataclasses import dataclass

TASK007_BASIS = {"ref": "collaboration/reports/007-availability-placement-pilot.md", "kind": "prior_evidence_other_site",
                 "scope": "legacy synthetic storefront, 'most expensive in-stock product' task, n = 3 runs per cell, exploratory and descriptive; detail-only needed +2.7 to +6.0 model requests per run in scopes of rank >= 2",
                 "limits": "different site and task; one model; not a validated effect for the audited site"}
TASK_KEYWORDS = {"availability": ("in stock", "in-stock", "available", "availability", "out of stock"), "sku": ("sku", "product code", "identifier")}


@dataclass(frozen=True)
class Template:
    id: str
    addresses: tuple[str, str]               # (finding kind, attribute)
    title: str
    change: str
    mechanism: str
    expected_benefit: str
    risks: str
    measure: tuple[str, ...]
    basis: tuple[dict, ...]
    change_id: str | None = None             # id a managed target understands (demo targets only)
    related: tuple[tuple[str, str], ...] = ()


LIBRARY = (
    Template("show-availability-on-listing-cards", ("attribute_detail_only", "availability"), "Show stock status on listing cards",
             "Print 'In stock' / 'Out of stock' on every listing, search and home card, and offer an in-stock filter on listing pages.",
             "Stock state decides eligibility for many shopping tasks. When it is visible only after opening each product page, an agent (or a person) must open every candidate to learn it, "
             "or guess; showing it on the card makes the decision readable from the list.",
             "Fewer product-page visits and model requests for tasks that depend on stock, and fewer answers that include unavailable items.",
             "Cards become denser; stock data must be accurate and fresh on list pages (cache invalidation); an in-stock filter needs the same data source.",
             ("model requests per task", "product-page visits", "answer correctness for stock-dependent tasks", "calculated cost"), (TASK007_BASIS,),
             change_id="availability-on-listing-cards", related=(("filter_absent", "availability"),)),
    Template("offer-in-stock-filter", ("filter_absent", "availability"), "Offer an in-stock filter on listing pages",
             "Add an 'In stock only' filter to category and search pages, backed by the same stock data as the cards.",
             "When stock is readable but cannot be filtered on, a shopper (or agent) must still scan every result to collect the in-stock ones; a filter returns exactly the available set.",
             "Fewer pages/results to scan for stock-dependent set-collection tasks; a shorter path to a complete answer.",
             "One more control on the filter form; the filter must stay consistent with the card labels.",
             ("model requests per task", "answer completeness (recall) for stock-dependent tasks", "calculated cost"), (),
             change_id="in-stock-filter"),
    Template("show-sku-on-listing-cards", ("attribute_detail_only", "sku"), "Show the SKU on listing cards",
             "Print the SKU / product identifier on each listing and search card.",
             "Tasks that must report identifiers force a visit to every product page when the identifier is only on product pages.",
             "Fewer page visits for identifier-reporting tasks; fewer name-for-SKU substitutions.",
             "Minor visual clutter; identifiers must stay consistent between list and product pages.",
             ("product-page visits", "answer correctness for identifier-reporting tasks"), (),
             change_id="sku-on-listing-cards"),
)


def objective_relevance(attribute: str, objective: str | None) -> str:
    if not objective:
        return "task_not_provided"
    return "task_depends_on_attribute" if any(k in objective.lower() for k in TASK_KEYWORDS.get(attribute, ())) else "task_does_not_mention_attribute"


def select(findings: list[dict], objective: str | None = None) -> list[dict]:
    recs, by_fp, consumed = [], {f["fingerprint"]: f for f in findings}, set()
    for t in LIBRARY:
        fp = f"{t.addresses[0]}:{t.addresses[1]}"
        f = by_fp.get(fp)
        if f is None or fp in consumed:                  # a finding already covered as `related` by an earlier template is not recommended twice
            continue
        consumed.update(f"{k}:{a}" for k, a in t.related)
        related = [by_fp[f"{k}:{a}"] for k, a in t.related if f"{k}:{a}" in by_fp]
        c = f["counts"]
        rel = objective_relevance(t.addresses[1], objective)
        recs.append({
            "id": f"rec-{t.id}", "template": t.id, "title": t.title, "status": "proposed", "validation": "unvalidated",
            "addresses": [f["fingerprint"]] + [r["fingerprint"] for r in related], "change": t.change, "change_id": t.change_id,
            "rationale": (f"Observed: {f['summary']} " + " ".join(r["summary"] for r in related) + f" Mechanism: {t.mechanism}"),
            "task_relevance": rel,
            "expected_benefit": t.expected_benefit, "risks": t.risks,
            "confidence": {"level": "prior_evidence_other_site" if t.basis else "hypothesis", "basis": list(t.basis),
                           "statement": ("Supported by descriptive evidence from a different site/task; NOT validated for this site." if t.basis else "Hypothesis; no supporting measurement yet.")},
            "supporting_evidence": f["evidence"][:5] + [e for r in related for e in r["evidence"][:1]],
            "how_to_validate": {"resolution_check": f"re-audit and confirm finding {f['fingerprint']} is no longer observed (and attribute_on_cards:{t.addresses[1]} is)",
                                "effect_measurement": f"controlled rescan/experiment on the same task and catalogue measuring: {', '.join(t.measure)}"},
            "evidence_counts": {"cards_examined": c.get("cards_examined"), "cards_with_cue": c.get("cards_with_cue"), "details_examined": c.get("details_examined"), "details_with_cue": c.get("details_with_cue")},
        })
    return recs
