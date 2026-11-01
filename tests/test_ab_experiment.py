"""Controlled Ironbark before/after experiment (EXP-C), OFFLINE: the combined three-field listing patch, its safety on the real Ironbark capture, plan caps, and the pre-registered inputs.
Nothing here calls a model; the dev-provider pipeline run is a plumbing check done by hand and is not evidence about any effect."""
import json
import math

import pytest

from agent_readiness.exp2 import snapshot as ironbark
from agent_readiness.investigate import allocation as alloc
from agent_readiness.investigate.evaluate import exploratory
from agent_readiness.investigate.inspect.crawl import Limits, MappingFetcher, crawl
from agent_readiness.investigate.inspect.pagemodel import internal_path, parse_page
from agent_readiness.investigate.inspect.profile import build_profile
from agent_readiness.investigate.recommend import templates
from agent_readiness.investigate.sitemodel.patch import apply_patch
from agent_readiness.investigate.taskgen.criteria import compile_criterion
from agent_readiness.live import abtest

LABELS = abtest.LABELS
# --- the three fields on the listing cards of a small generic catalogue ----------------------------------------------------------------------------------------------------
NAV = '<nav><a href="/">Home</a> <a href="/items">Items</a></nav>'


def pg(title, body):
    return f"<!doctype html><html><head><title>{title}</title></head><body>{NAV}<main>{body}</main></body></html>"


ITEMS = [(f"item-{i}", f"Item {i}", [("Deposit", f"${100 + 25 * i}"), ("Minimum term", f"{1 + i % 3} days"), ("Delivery", ["Required", "Optional"][i % 2])]) for i in range(1, 7)]


def catalogue():
    cards = "".join(f'<article class="card"><h2><a href="/items/{s}">{n}</a></h2><p>A machine.</p></article>' for s, n, _ in ITEMS)
    files = {"/": pg("Home", '<h1>Home</h1><a href="/items">Items</a>'), "/items": pg("Items", f"<h1>Items</h1><div>{cards}</div>")}
    for k, (s, n, facts) in enumerate(ITEMS):
        related = "".join(f'<li><a href="/items/{t}">{m}</a></li>' for t, m, _ in ITEMS[:3] if t != s)
        files[f"/items/{s}"] = pg(n, f"<h1>{n}</h1><dl>" + "".join(f"<dt>{a}</dt><dd>{b}</dd>" for a, b in facts) + f'</dl><h2>Related</h2><ul class="related">{related}</ul>')
    return crawl(MappingFetcher(files), Limits(max_pages=30))


def test_the_combined_patch_shows_all_fields_on_the_listing_cards_and_never_on_item_pages_that_state_them():
    snap = catalogue()
    prof = json.loads(json.dumps(build_profile(snap)))
    labels = ["deposit", "minimum term", "delivery"]
    patch, info = templates.build("info_absent_on_template", {"labels": labels}, prof, snap)
    assert info["offered"] and info["recheck"]["passed"] and info["pages_changed"] == ["/items"]                  # the related lists on item pages are left alone
    assert len(patch["ops"]) == 3 and {o["source_label"] for o in patch["ops"]} == set(labels)
    new, rep = apply_patch(snap, patch)
    after = parse_page("/items", new.get("/items").text())
    rows = [(f["label"], f["value"]) for it in after["item_groups"][0]["items"] for f in it["facts"]]
    assert ("deposit", "$125") in rows and ("delivery", "Required") in rows and len(rows) == 18, "6 cards x 3 fields"
    assert new.get("/items/item-1").body == snap.get("/items/item-1").body                                          # item pages (which state the fields themselves) are byte-identical


def test_the_single_label_template_is_unchanged_by_the_combined_one():
    snap = catalogue()
    prof = json.loads(json.dumps(build_profile(snap)))
    patch, info = templates.build("info_absent_on_template", {"label": "deposit"}, prof, snap)
    assert info["offered"] and all(len(o["pages"]) == 1 for o in patch["ops"])


def test_plan_caps_default_to_the_constants_and_an_override_is_validated_and_summed():
    d = alloc.post_trials_caps(2.05, 0.670252)
    assert (d["patched_arm"], d["placebo_arm"], d["post_trials_combined"]) == (0.80, 0.55, 1.35)
    c = alloc.post_trials_caps(2.5, 0.864825, {"placebo_arm": 0.8, "patched_arm": 0.8})
    assert (c["patched_arm"], c["placebo_arm"], c["post_trials_combined"], c["combined_cap_fits_ceiling"]) == (0.8, 0.8, 1.6, True)
    for bad in ({"placebo_arm": 1.5}, {"placebo_arm": 0}, {"combined": 1.0}, {"patched_arm": "x"}):
        with pytest.raises(ValueError):
            alloc.post_trials_caps(2.4, 0.86, bad)
    assert exploratory.validate_plan({"placebo_tasks": ["a"], "affected": ["a"], "same_shape_controls": [], "detail_controls": [], "caps_usd": {"placebo_arm": 0.8}}, ["a"])["caps_usd"] == {"placebo_arm": 0.8}


def test_the_ledger_ceiling_is_the_imported_spend_plus_both_arm_caps_rounded_up_to_five_cents():
    assert abtest.ledger_ceiling(0.864825) == 2.5 and abtest.ledger_ceiling(0.670252) == 2.3
    assert math.isclose(sum(abtest.CAPS.values()), 1.6)


# --- the REAL Ironbark capture ------------------------------------------------------------------------------------------------------------------------------------------------------------
ORIGINAL, PATCHED = "d2824b210ed9e9d85dac527eb0b4eeb519540a70a7c59ff8690c204ff677538f", "40c5d886963c925a7b99ff721d7971d5ebacbc52d0237d9549febe301d74f1ed"
FROZEN = [  # the four criteria of the frozen tasks of live-2d58a80e14 (public structure: where the answer lives; no answers)
    {"kind": "extremum", "listing": "/hire", "label": "refundable deposit", "direction": "max"},
    {"kind": "item_set", "listing": "/hire", "conditions": [{"label": "refundable deposit", "op": "lt", "value": "$200"}]},
    {"kind": "item_set", "listing": "/hire", "conditions": [{"label": "delivery and collection", "op": "eq", "value": "Required for this item"}]},
    {"kind": "item_set", "listing": "/hire", "conditions": [{"label": "minimum hire", "op": "eq", "value": "2 days"}]}]


@pytest.fixture(scope="module")
def ib():
    snap = ironbark.snapshot("control")
    prof = json.loads(json.dumps(build_profile(snap)))
    patch, info = templates.build("info_absent_on_template", {"labels": LABELS}, prof, snap)
    new, rep = apply_patch(snap, patch)
    return snap, prof, patch, info, new, rep


def test_the_ironbark_patch_is_exactly_the_pre_registered_one(ib):
    snap, _, patch, info, new, rep = ib
    assert snap.sha256 == ORIGINAL and new.sha256 == PATCHED and rep["parent_sha256"] == ORIGINAL and new.meta["parent_sha256"] == ORIGINAL
    assert info["pages_changed"] == ["/", "/hire", "/hire/category/access", "/hire/category/cutting", "/hire/category/drilling-and-breaking", "/hire/category/landscaping", "/hire/sort/name", "/hire/sort/price-asc", "/hire/sort/price-desc"]
    assert info["excluded_bundle_listings"] == ["/kits"] and info["inserted_bytes"] == 6688 and len(patch["ops"]) == 3
    assert info["recheck"]["passed"]


def test_the_patch_adds_only_existing_site_facts_with_no_markers_and_changes_nothing_else(ib):
    from bs4 import BeautifulSoup
    import re
    snap, _, _, info, new, _ = ib
    changed = [p for p in snap.resources if new.resources[p].body != snap.resources[p].body]
    assert sorted(changed) == info["pages_changed"] and all(snap.resources[p].is_html for p in changed)
    labels = re.compile(r"^(Refundable deposit|Minimum hire|Delivery and collection): ")
    inserted = 0
    for path in changed:
        old, cur = BeautifulSoup(snap.get(path).text(), "html.parser"), BeautifulSoup(new.get(path).text(), "html.parser")
        for p in [e for e in cur.find_all("p") if labels.match(e.get_text())]:
            assert not p.attrs, "the inserted line carries no class, id or data attribute"
            card = p.find_parent("article")
            href = internal_path(card.find("a", href=True)["href"], path)
            label, value = p.get_text().split(": ", 1)
            facts = {f["label"]: f["value"] for f in parse_page(href, snap.get(href).text())["facts"]}
            assert facts[label.lower()] == value, "every inserted value is the machine's own detail-page fact"
            p.decompose()
            inserted += 1
        assert cur.decode() == old.decode(), "after removing the inserted lines the page is identical to the original"
    assert inserted == 252
    text = " ".join(new.get(p).text().lower() for p in changed)
    assert not any(w in text for w in ("patch", "variant", "experiment", "intervention", "treatment", "placebo", "hypothesis"))
    assert new.get("/kits").body == snap.get("/kits").body and new.get("/hire/stump-grinder-13hp").body == snap.get("/hire/stump-grinder-13hp").body


def test_all_four_frozen_task_answers_are_unchanged_on_the_patched_site(ib):
    snap, _, _, _, new, _ = ib
    before, after = build_profile(snap), build_profile(new)
    for c in FROZEN:
        a, b = compile_criterion(c, before), compile_criterion(c, after)
        assert a.truth == b.truth and a.kind == b.kind
    assert compile_criterion(FROZEN[0], before).truth == "Electric scissor lift 6 m"


def test_the_pre_registered_inputs_name_no_task_answer_and_cite_a_listing_observation():
    text = abtest.HYPOTHESIS + abtest.PREDICTION
    assert "Electric scissor lift" not in text and "$200" not in text and abtest.CITES == ["obs-8d20d6d5d9"]
    assert abtest.LABELS == ["refundable deposit", "minimum hire", "delivery and collection"]
