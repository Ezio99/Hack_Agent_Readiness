"""Patch DSL: effective, deterministic, provenance-bound and unable to escape the mirror (plan D9)."""
import pytest
from pydantic import ValidationError

from agent_readiness.investigate import zoo
from agent_readiness.investigate.inspect.profile import build_profile, observations
from agent_readiness.investigate.sitemodel.patch import MAX_OPS, Patch, PatchError, apply_patch


def listing_gap(snap, path="/workshops"):
    obs = [o for o in observations(build_profile(snap)) if o.kind == "listing_detail_fields" and o.data["listing"] == path][0]
    return obs.data["not_in_listing"]


def test_copy_field_to_listing_moves_information_to_where_the_choice_is_made():
    snap = zoo.snapshot("site-1")
    assert {"price", "date", "seats left"} <= set(listing_gap(snap))
    patch = {"description": "show key fields on cards", "ops": [{"op": "copy_field_to_listing", "pages": ["/workshops"], "css": "li.card", "source_label": l} for l in ("price", "date", "seats left")]}
    new, rep = apply_patch(snap, patch)
    assert rep["pages_changed"] == ["/workshops"] and rep["parent_sha256"] == snap.sha256 and rep["new_sha256"] == new.sha256 != snap.sha256
    assert new.meta["parent_sha256"] == snap.sha256 and new.meta["patch_sha256"] == rep["patch_sha256"]
    assert not {"price", "date", "seats left"} & set(listing_gap(new))                      # the static re-check: the original observation no longer holds
    assert b"Price: $45" in new.get("/workshops").body and "Seats left: 0" in " ".join(rep["ops"][2]["inserted_texts"])
    assert new.get("/workshops/pottery-basics").body == snap.get("/workshops/pottery-basics").body    # other pages byte-identical
    assert zoo.snapshot("site-1").sha256 == snap.sha256                                       # the original is never modified


def test_label_unnamed_controls_with_provenance_vocabulary():
    snap = zoo.snapshot("site-2")
    def unnamed(s):
        return sum(len(v) for v in build_profile(s)["unnamed_controls"].values())
    base = unnamed(snap)
    ops = [{"op": "set_attribute", "pages": ["/*"], "css": f'nav a[href="{h}"]', "attr": "aria-label", "value": v} for h, v in (("/hours", "Opening hours"), ("/contact", "Contact"), ("/", "Home"))]
    new, rep = apply_patch(snap, {"ops": ops})
    assert unnamed(new) < base and all(o["elements_changed"] > 0 for o in rep["ops"])


def test_patch_application_is_deterministic():
    snap = zoo.snapshot("site-1")
    p = {"ops": [{"op": "insert_text", "pages": ["/workshops"], "css": "h1", "position": "after", "text": "Back to workshops"}]}
    assert apply_patch(snap, p)[0].sha256 == apply_patch(snap, Patch.model_validate(p))[0].sha256
    assert Patch.model_validate(p).sha256 == Patch.model_validate(p).sha256


def op(**kw):
    return {"ops": [{"op": "insert_text", "pages": ["/workshops"], "css": "h1", "text": "Back", **kw}]}


@pytest.mark.parametrize("text", ["<script>alert(1)</script>", "click javascript:alert(1)", "<b>x</b>", "onclick=steal()", "", "x" * 201, "data:text/html;base64,AAA"])
def test_unsafe_or_oversized_text_is_rejected_at_validation(text):
    with pytest.raises(ValidationError):
        Patch.model_validate(op(text=text))


def test_attribute_allowlist_and_unknown_ops_and_bounds():
    snap = zoo.snapshot("site-1")
    for bad in ({"op": "set_attribute", "pages": ["/*"], "css": "a", "attr": "onclick", "value": "Home"}, {"op": "set_attribute", "pages": ["/*"], "css": "a", "attr": "href", "value": "Home"},
                {"op": "run_script", "pages": ["/*"], "css": "a"}, {"op": "insert_text", "pages": ["workshops"], "css": "h1", "text": "Home"}):
        with pytest.raises(ValidationError):
            Patch.model_validate({"ops": [bad]})
    with pytest.raises(ValidationError):
        Patch.model_validate({"ops": [{"op": "insert_text", "pages": ["/*"], "css": "h1", "text": "Home"}] * (MAX_OPS + 1)})
    assert apply_patch(snap, {"ops": [{"op": "insert_text", "pages": ["/*"], "css": "h1", "tag": "small", "text": "Home"}]})


def test_inserted_text_must_have_provenance_on_the_site():
    snap = zoo.snapshot("site-1")
    with pytest.raises(PatchError, match="provenance"):
        apply_patch(snap, op(text="The answer is 42 and seats are unlimited"))                  # invented content is refused
    apply_patch(snap, op(text="Pottery Basics"))                                              # existing site text is fine
    apply_patch(snap, op(text="Skip to main content"))                                        # interface vocabulary is fine


def test_links_may_only_target_pages_in_the_snapshot():
    snap = zoo.snapshot("site-1")
    for href in ("https://evil.invalid/x", "//evil.invalid/x", "/does-not-exist", "javascript:alert(1)"):
        with pytest.raises(PatchError):
            apply_patch(snap, {"ops": [{"op": "add_link", "pages": ["/workshops"], "css": "h1", "href": href, "text": "Contact"}]})
    new, _ = apply_patch(snap, {"ops": [{"op": "add_link", "pages": ["/workshops"], "css": "h1", "href": "/faq", "text": "Contact"}]})
    assert b'href="/faq"' in new.get("/workshops").body


def test_ops_that_match_nothing_are_rejected_not_ignored():
    snap = zoo.snapshot("site-1")
    with pytest.raises(PatchError, match="changed nothing"):
        apply_patch(snap, op(text="Back", css=".no-such-class"))
    with pytest.raises(PatchError, match="no page matches"):
        apply_patch(snap, {"ops": [{"op": "insert_text", "pages": ["/nowhere/*"], "css": "h1", "text": "Back"}]})
    with pytest.raises(PatchError, match="invalid selector"):
        apply_patch(snap, op(css="h1[["))
    with pytest.raises(PatchError, match="changed nothing"):
        apply_patch(snap, {"ops": [{"op": "copy_field_to_listing", "pages": ["/workshops"], "css": "li.card", "source_label": "nonexistent label"}]})


def test_only_html_pages_change_never_assets():
    snap = zoo.snapshot("site-3")
    assert any(not r.is_html for r in snap.resources.values())
    with pytest.raises(PatchError, match="no page matches"):
        apply_patch(snap, {"ops": [{"op": "insert_text", "pages": ["/img/*"], "css": "svg", "text": "Home"}]})
    new, _ = apply_patch(snap, {"ops": [{"op": "insert_text", "pages": ["/*"], "css": "h1", "text": "Home"}]})
    assert all(new.get(p).body == r.body for p, r in snap.resources.items() if not r.is_html)


def test_inserted_volume_is_bounded():
    snap = zoo.snapshot("site-1")
    long_but_genuine = build_profile(snap)["pages"]["/workshops"]["text"][:190]               # 190 characters that really are on the site, so only the volume rule can refuse
    with pytest.raises(PatchError, match="volume"):
        apply_patch(snap, {"ops": [{"op": "insert_text", "pages": ["/workshops/*"], "css": "dd", "position": "append", "text": long_but_genuine}] * 30})
