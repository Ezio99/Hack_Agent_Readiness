"""The site zoo and the isolation of planted diagnoses from everything an investigator can see (plan D13)."""
import json
import re
from pathlib import Path

import pytest

from agent_readiness.investigate import zoo
from agent_readiness.investigate.inspect.profile import build_profile, observations
from agent_readiness.investigate.zoo import sealed

ROOT = Path(__file__).resolve().parents[1] / "src" / "agent_readiness" / "investigate"
INVESTIGATOR_FACING = ["inspect", "sitemodel"]
SHOP_WORDS = re.compile(r"\b(sku|in stock|out of stock|add to cart|checkout|availability|basket)\b", re.I)


def test_manifests_cover_two_friction_categories_a_clean_control_and_a_development_site():
    ms = sealed.manifests()
    assert set(ms) == set(zoo.ids())
    by_cat = {m["category"]: m for m in ms.values()}
    assert {"information_placement", "unlabeled_icon_controls", "clean_control"} <= set(by_cat)
    assert by_cat["clean_control"]["planted"] == [] and by_cat["clean_control"]["role"] == "demonstration"
    assert sorted(m["role"] for m in ms.values()).count("demonstration") == 3 and any(m["role"] == "development" for m in ms.values())


def test_no_investigator_facing_module_can_read_the_sealed_manifests():
    """Outside the zoo package the only permitted contact is `from ...zoo.sealed import assert_blind` (the guard prompt builders must call); manifests/tokens are unreachable."""
    guard_import = re.compile(r"^from \.+(?:investigate\.)?zoo\.sealed import (assert_blind|BlindnessError)(, (assert_blind|BlindnessError))*\s*$", re.M)
    offenders = []
    for f in ROOT.rglob("*.py"):
        rel = f.relative_to(ROOT).parts
        if rel[0] == "zoo":
            continue
        if "sealed" in guard_import.sub("", f.read_text()).lower():
            offenders.append(str(f.relative_to(ROOT)))
    assert offenders == [], offenders
    for pkg in INVESTIGATOR_FACING:
        for f in (ROOT / pkg).rglob("*.py"):
            assert "zoo" not in f.read_text(), f"{f} must not depend on the zoo"


def all_investigator_visible_text(sid):
    snap = zoo.snapshot(sid)
    prof = build_profile(snap)
    obs = observations(prof)
    chunks = [r.text() for r in snap.resources.values()] + [json.dumps(snap.meta, default=str), json.dumps(prof, default=str)]
    chunks += [o.summary + json.dumps(o.data, default=str) + " ".join(o.refs) for o in obs]
    chunks += [sid, *snap.resources]
    return "\n".join(chunks)


@pytest.mark.parametrize("sid", zoo.ids())
def test_nothing_an_investigator_can_see_reveals_a_sealed_diagnosis(sid):
    sealed.assert_blind(all_investigator_visible_text(sid))                                  # served pages, snapshot meta, profile and observations


def test_blindness_guard_actually_detects_leaks_and_passes_clean_text():
    m = sealed.manifest("site-1")
    for leak in (m["category"], m["summary"].upper(), m["planted"][0]["description"], "information placement issue"):
        with pytest.raises(sealed.BlindnessError):
            sealed.assert_blind(f"Prompt: please look at {leak} now")
    sealed.assert_blind("Listing cards show a title and a blurb. Detail pages show a price.")
    sealed.assert_blind("Our trees were planted in 1990 along the avenue.")                       # ordinary site text containing a generic word must not abort a pipeline


def test_site_ids_and_titles_are_opaque_and_sites_differ_structurally():
    titles = []
    for sid in zoo.ids():
        assert re.fullmatch(r"site-\d+", sid)
        prof = build_profile(zoo.snapshot(sid))
        titles.append(prof["pages"]["/"]["title"])
    assert len(set(titles)) == len(titles)
    assert not any(re.search(r"icon|label|hidden|buried|clean|control|placement|issue|problem|friction", t, re.I) for t in titles)
    sig = {sid: tuple(sorted(build_profile(zoo.snapshot(sid))["templates"])) for sid in zoo.ids()}
    assert len(set(sig.values())) == len(sig)                                                 # structurally different path templates


def test_inspector_reports_neutral_facts_that_distinguish_the_sites_without_naming_a_problem():
    p1, p2, p3, p4 = (build_profile(zoo.snapshot(f"site-{i}")) for i in (1, 2, 3, 4))
    l1 = p1["listings"][0]["fields"]
    assert l1["price"]["in_listing_item"] == 0 and l1["price"]["detail_pages"] == 8                 # facts on detail pages that no listing item repeats
    assert all(v["in_listing_item"] == v["detail_pages"] for v in p3["listings"][0]["fields"].values())   # the clean control repeats its decision fields
    assert sum(len(v) for v in p2["unnamed_controls"].values()) >= 20 and p3["unnamed_controls"] == {} and p1["unnamed_controls"] == {}
    assert p4["depth"]["/plan/permits/day-use"] == 3 and max(p3["depth"].values()) <= 2


def test_inspector_and_mirror_code_contain_no_shop_specific_vocabulary():
    hits = []
    for pkg in INVESTIGATOR_FACING:
        for f in (ROOT / pkg).rglob("*.py"):
            for m in SHOP_WORDS.finditer(re.sub(r'""".*?"""', "", f.read_text(), flags=re.S)):
                hits.append((f.name, m.group(0)))
    assert hits == []


def test_zoo_pages_are_script_free_and_self_contained():
    for sid in zoo.ids():
        for r in zoo.snapshot(sid).pages():
            t = r.text()
            assert "<script" not in t and "http://" not in t and "https://" not in t
