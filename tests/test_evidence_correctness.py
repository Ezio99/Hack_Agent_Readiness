"""Evidence correctness of the site profile: accessible names from hidden aria-labelledby targets, controls hidden in the capture, and listing classification (catalogue / uncertain /
navigation group). Offline fixtures only: a Sphinx-style documentation page set, a generic catalogue, and the registered Ironbark control snapshot."""
import pytest

from agent_readiness.investigate import zoo
from agent_readiness.investigate.inspect.crawl import Limits, MappingFetcher, crawl
from agent_readiness.investigate.inspect.pagemodel import parse_page
from agent_readiness.investigate.inspect.profile import build_profile, observations


def page(title, body, head_nav=""):
    return f"<!doctype html><html lang='en'><head><title>{title}</title></head><body>{head_nav}<main>{body}</main></body></html>"


def kinds(profile):
    return {o.kind: o for o in observations(profile)}


# --- accessible names --------------------------------------------------------------------------------------------------------------------------------------------------------------
def test_hidden_aria_labelledby_target_still_names_the_control():
    html = page("t", '<div id="box" style="display:none"><h3 id="lbl">Quick search</h3><form><input type="text" name="q" aria-labelledby="lbl"></form></div>')
    rec = parse_page("/", html)
    f = rec["forms"][0]["fields"][0]
    assert f["accessible_name"] == "Quick search" and f["name_source"] == "aria-labelledby"


def test_text_in_hidden_descendants_of_the_target_is_not_used():
    html = page("t", '<span id="l">Search <span style="display:none">secret</span></span><input type="text" aria-labelledby="l">')
    assert parse_page("/", html)["forms"] == [] and parse_page("/", html)["controls"][0]["name"] == "Search"


def test_visible_unlabeled_control_stays_a_finding_and_hidden_unlabeled_is_reported_separately():
    files = {"/": page("Home", '<a href="/a">A</a><form><input type="text" name="visible"></form>'
                       '<div style="display:none"><form><input type="text" name="hidden"></form><button></button></div>'),
             "/a": page("A", "<p>x</p>")}
    prof = build_profile(crawl(MappingFetcher(files), Limits()))
    k = kinds(prof)
    assert "form_fields_without_label" in k and "1 field(s)" in k["form_fields_without_label"].summary           # only the visible field is a finding
    hid = k["controls_hidden_in_capture"]
    assert hid.data["count_fields"] == 1 and "NOT counted" in hid.summary
    assert hid.data["count_controls"] == 2                                    # the hidden input and the unnamed button inside the hidden container: reported, not counted as findings
    assert all(c["page"] == "/" for c in prof["hidden_unnamed_controls"]) and [r["locator"] for rows in prof["unnamed_controls"].values() for r in rows] == ["input < form < main < body"]     # only the visible input is a finding


def test_sphinx_style_search_box_is_not_an_unlabeled_finding():
    sidebar = ('<search id="searchbox" style="display: none" role="search"><h3 id="searchlabel">Quick search</h3><form action="/search/" method="get">'
               '<input type="text" name="q" aria-labelledby="searchlabel"><input type="submit" value="Go"></form></search>')
    files = {"/": page("Docs", '<h1>Docs</h1><a href="/a/">A</a> <a href="/b/">B</a>', sidebar), "/a/": page("A", "<h1>A</h1>", sidebar), "/b/": page("B", "<h1>B</h1>", sidebar)}
    prof = build_profile(crawl(MappingFetcher(files), Limits()))
    k = kinds(prof)
    assert "form_fields_without_label" not in k and "controls_without_accessible_name" not in k and prof["unnamed_controls"] == {}


# --- listing classification -------------------------------------------------------------------------------------------------------------------------------------------------------
def docs_site(shared_note=False):
    toc = "".join(f'<li><a href="/p/{i}/">Topic {i}</a></li>' for i in range(6))
    files = {"/": page("Docs", f"<h1>Docs</h1><ul>{toc}</ul>")}
    for i in range(6):
        files[f"/p/{i}/"] = page(f"Topic {i}", f"<h1>Topic {i}</h1><ul>{toc}</ul>" + (f"<dl><dt>option_{i}</dt><dd>Default: {i}</dd></dl>" if i < 2 else "") + ("<p>Notes: see manual</p>" if shared_note else ""))
    return build_profile(crawl(MappingFetcher(files), Limits()))


def test_a_table_of_contents_is_a_navigation_group_not_a_listing_and_is_reported():
    prof = docs_site()
    assert prof["listings"] == [] and len(prof["navigation_groups"]) >= 1
    assert all(g["classification"] == "navigation_group" for g in prof["navigation_groups"])
    nav = kinds(prof)["navigation_link_groups"]
    assert "NAVIGATION" in nav.summary and "listing_detail_fields" not in kinds(prof)


def test_a_real_catalogue_is_a_catalogue():
    prof = build_profile(zoo.snapshot("site-1"))
    assert [l["classification"] for l in prof["listings"]] == ["catalogue"] and prof["navigation_groups"] == []
    assert all(v["distinct_pages"] <= v["of"] for l in prof["listings"] for v in l["fields"].values())


@pytest.fixture(scope="module")
def ironbark():
    from agent_readiness.exp2 import snapshot as S
    return build_profile(S.snapshot("control"))


def test_ironbark_item_listings_and_their_field_measurements_are_preserved(ironbark):
    hire = next(l for l in ironbark["listings"] if l["listing"] == "/hire" and l["detail_template"] == "/hire/{}")
    assert hire["classification"] == "catalogue" and hire["items"] == 16
    for field in ("refundable deposit", "minimum hire", "delivery and collection"):
        f = hire["fields"][field]
        assert (f["detail_pages"], f["in_listing_item"], f["of"], f["distinct_pages"]) == (16, 0, 16, 16)
    assert any(l["listing"] == "/accessories" and l["classification"] == "catalogue" for l in ironbark["listings"])


def test_ironbark_filter_chips_and_category_tiles_are_navigation_and_sort_chips_are_uncertain_and_visible(ironbark):
    nav, unc = ironbark["navigation_groups"], [l for l in ironbark["listings"] if l["classification"] == "uncertain"]
    assert len(nav) == 10 and {g["detail_template"] for g in nav} == {"/hire/category/{}"}
    assert len(unc) == 4 and {l["detail_template"] for l in unc} == {"/hire/sort/{}"}                  # kept as listings, flagged: nothing uncertain is dropped
    assert any("UNCERTAIN" in o.summary for o in observations(ironbark) if o.kind == "listing_detail_fields")
    assert len(ironbark["listings"]) + len(nav) == 33                                                  # the profiler's original 33 groups are all accounted for


def test_a_contents_list_whose_pages_all_state_one_common_label_is_uncertain_not_dropped():
    prof = docs_site(shared_note=True)
    assert {l["classification"] for l in prof["listings"]} == {"uncertain"} and prof["navigation_groups"] == []
    assert any("UNCERTAIN" in o.summary for o in observations(prof) if o.kind == "listing_detail_fields")


# --- definition-list fact cleaning (P2a) ------------------------------------------------------------------------------------------------------------------------------------------
SPHINX_DL = ('<dl class="py data"><dt class="sig" id="SESSION_COOKIE_NAME"><span class="pre">SESSION_COOKIE_NAME</span><a class="headerlink" href="#SESSION_COOKIE_NAME" title="Link">¶</a></dt>'
             '<dd><p>The name of the <code>session</code> cookie, see <a href="/x">sessions</a>.</p><p>Default: <code>\'session\'</code></p>'
             '<details class="changelog"><summary>Changelog</summary><div class="versionchanged"><p>Changed in version 2.0: renamed.</p></div></details>'
             '<div class="admonition note"><p>Note: careful.</p></div><pre>x = 1</pre>'
             '<dl class="field-list"><dt>Parameters</dt><dd><p>app: the app</p></dd></dl></dd></dl>')


def test_definition_term_label_has_no_permalink_and_description_has_no_nested_or_changelog_blocks():
    rec = parse_page("/c", page("Config", SPHINX_DL))
    dl = {f["label"]: f["value"] for f in rec["facts"] if f["how"] == "dl"}
    assert "session_cookie_name" in dl and not any("¶" in k for k in dl)
    v = dl["session_cookie_name"]
    assert v.startswith("The name of the session cookie, see sessions") and "Default: 'session'" in v          # ordinary descriptive text (inline code, links) is kept
    for gone in ("Changelog", "Changed in version", "careful", "x = 1", "Parameters", "app: the app"):
        assert gone not in v
    assert dl["parameters"] == "app: the app"                       # the nested field list is still its own fact, with its own text
    assert "¶" in rec["text"]                                       # the captured page text (evidence) is untouched


def test_plain_spec_style_definition_lists_are_unchanged():
    rec = parse_page("/h", page("Drill", "<dl><dt>Refundable deposit</dt><dd>$150</dd><dt>Minimum hire</dt><dd>2 days <a href='/t'>terms</a></dd></dl>"))
    assert [(f["label"], f["value"]) for f in rec["facts"]] == [("refundable deposit", "$150"), ("minimum hire", "2 days terms")]


def test_a_permalink_is_recognised_by_its_symbol_even_without_the_headerlink_class():
    rec = parse_page("/p", page("P", "<dl><dt>Term<a href='#t'> # </a></dt><dd>Short value</dd></dl>"))
    assert [(f["label"], f["value"]) for f in rec["facts"]] == [("term", "Short value")]
