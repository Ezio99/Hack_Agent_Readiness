"""Phase 4 diagnostics: structural, behavioural and evidence-linked layers. Deterministic and offline (synthetic records + the two controlled sites)."""
import copy
from pathlib import Path

import pytest

from agent_readiness.diagnostics import behavioral as B
from agent_readiness.diagnostics import hypotheses as H
from agent_readiness.diagnostics import structural as ST
from agent_readiness.diagnostics.model import STATUSES, Finding
from agent_readiness.framework import site as S
from agent_readiness.investigate.inspect.profile import build_profile


@pytest.fixture(scope="module")
def sites():
    out = {}
    for name in ("larkspur", "ironbark"):
        site = S.get(name)
        out[name] = {v: ST.observe(build_profile(site.snapshot(v)), site=name, version=v) for v in site.variants}
    return out


@pytest.mark.parametrize("name,expected", [("larkspur", {"course fee", "duration", "seats left"}), ("ironbark", {"refundable deposit", "minimum hire", "delivery and collection"})])
def test_structural_diagnostics_detect_exactly_the_intentional_listing_change(sites, name, expected):
    o, m = sites[name]["original"], sites[name]["modified"]
    ch = ST.compare(o, m)
    resolved = {f.detail["label"] for f in o if f.id in ch["resolved"]}
    assert resolved == expected and ch["introduced"] == []                       # the change, all of the change, and nothing else
    assert all(f.status == "observed" and f.layer == "structural" for f in o + m)


def test_listing_gaps_are_reported_once_per_item_template_and_ignore_navigation_chips(sites):
    gaps = [f for f in sites["ironbark"]["original"] if f.rule == "listing-fact-gap"]
    keys = [(f.detail["template"], f.detail["label"]) for f in gaps]
    assert len(keys) == len(set(keys)) and not any(f.detail["label"] == "sort" for f in gaps)
    assert {f.detail["listing"] for f in gaps if f.detail["template"] == "/hire/{}"} == {"/hire"}
    assert all(f.evidence and f.recommendation and f.verify for f in gaps)


def test_ids_are_stable_across_versions_and_reruns(sites):
    again = ST.observe(build_profile(S.get("larkspur").snapshot("original")), site="larkspur", version="original")
    assert [f.id for f in again] == [f.id for f in sites["larkspur"]["original"]]
    persisting = ST.compare(sites["larkspur"]["original"], sites["larkspur"]["modified"])["persisting"]
    assert persisting and all(i.startswith("S-") for i in persisting)


def _profile(**page):
    base = {"title": "T", "facts": [], "item_groups": [], "landmarks": ["main", "nav"], "headings": [{"level": 1, "text": "H"}], "images": [], "controls": [], "forms": [], "structured_data": []}
    return {"snapshot_sha256": "s" * 64, "listings": [], "unreachable": [], "pages": {"/": {**base, **page}}}


@pytest.mark.parametrize("page,rule", [({"controls": [{"tag": "a", "name": "", "href": "/x", "locator": "a"}]}, "unnamed-control"),
                                       ({"headings": [{"level": 1, "text": "a"}, {"level": 3, "text": "b"}]}, "heading-structure"),
                                       ({"headings": []}, "heading-structure"), ({"landmarks": ["main"]}, "missing-landmark"),
                                       ({"images": [{"src": "/a.png", "alt": None}]}, "image-alt"),
                                       ({"forms": [{"fields": [{"name": "q", "label": "", "name_source": "none", "locator": "input"}]}]}, "form-label")])
def test_each_structural_rule_fires_on_its_defect_and_not_on_a_clean_page(page, rule):
    assert [f.rule for f in ST.observe(_profile(**page), site="x", version="v")] == [rule]
    assert ST.observe(_profile(), site="x", version="v") == []


def _trial(task="t1", paths=("/", "/list", "/item/a", "/list", "/item/b", "/list"), passed=True, backed=True, status="completed", requests=6, limit=14, http=(), actions=None, errors=()):
    journey = [{"step": i + 1, "path": p, "actions": (actions or {}).get(i + 1, [{"name": "navigate", "params": {"url": f"{p}#{i}"}}]),
                "executed": [{"error": "boom" if i + 1 in errors else None}]} for i, p in enumerate(paths)]
    return {"task_id": task, "task": {"start_path": "/"}, "journey": journey, "mirror": {"log": [{"path": p, "status": s} for p, s in http], "blocked": []},
            "metrics": {"model_requests": requests, "limits": {"max_model_requests": limit}}, "outcome": {"run_status": status, "stop_reason": "agent_done"},
            "evaluation": {"passed": passed, "evidence_backed": backed, "missing_evidence": [] if backed else ["observed_text:x"]}}


def _rules(trial, priv=None, v2=None):
    return sorted(r for r, _, _ in B._trial_findings("n", trial, priv, v2))


def test_behavioural_rules():
    assert _rules(_trial()) == ["revisit"]                                                       # /list visited 3 times (returned twice)
    assert _rules(_trial(paths=("/", "/list", "/list", "/list", "/list"))) == []                 # scrolling one page is one visit
    assert "loop" in _rules(_trial(paths=("/", "/a", "/b", "/a", "/b")))
    assert "retry" in _rules(_trial(paths=("/", "/a", "/a"), actions={2: [{"name": "click", "params": {"index": 3}}], 3: [{"name": "click", "params": {"index": 3}}]}))
    assert "dead-end" in _rules(_trial(http=[("/item/zz", 404)])) and "dead-end" in _rules(_trial(errors=(2,)))
    assert "dead-end" not in _rules(_trial(http=[("/favicon.ico", 404)]))                      # the browser's own request, not the agent's
    assert "unnecessary-navigation" in _rules(_trial(paths=("/", "/x", "/y", "/z")), {"evidence_paths": ["/list"]})
    assert "budget-exhaustion" in _rules(_trial(requests=13, limit=14))
    assert "unsupported-answer" in _rules(_trial(backed=False))
    unsup = [e.detail for r, evs, _ in B._trial_findings("n", _trial(backed=False), None) if r == "unsupported-answer" for e in evs]
    assert unsup == ["1 required evidence item(s) were not shown to the agent (1 answer text, 0 page visit)"] and "observed_text:x" not in unsup[0]
    assert "incorrect-answer" in _rules(_trial(passed=False, backed=False))
    ev = B._trial_findings("n", _trial(passed=False, backed=False), None, {"passed": True})
    assert any("post-hoc grader v2: correct" in e.detail for r, evs, _ in ev if r == "v1-format-rejection" for e in evs)     # behavioral-2 (M8)
    assert "incorrect-answer" not in [r for r, _, _ in ev]


def test_behavioural_findings_aggregate_per_task_and_cite_trials():
    fs = B.observe({"a-t1-r1": _trial(), "b-t1-r2": _trial()}, {}, site="x", version="v", version_sha="s", origin="real_model")
    assert len(fs) == 1 and fs[0].tasks == ["t1"] and fs[0].detail["trials"] == ["a-t1-r1", "b-t1-r2"] and "(2/2 trials)" in fs[0].title and fs[0].status == "observed"


def _gap(version):
    return Finding(f"S-gap", "structural", "listing-fact-gap", "gap", "x", version, "s", "medium", "i", "observed", [], "rec", "verify",
                   detail={"listing": "/list", "label": "fee", "template": "/item/{}"})


def _versions(orig_pages=3, mod_pages=1, orig_req=12, mod_req=6, mod_backed=True):
    prof = {"pages": {"/list": {"item_groups": [{"items": [{"href": f"/item/{c}"} for c in "abc"]}]}}}
    priv = {"t1": {"criterion": {"kind": "extremum", "listing": "/list", "label": "fee", "direction": "max"}}, "t2": {"criterion": {"kind": "page_fact", "page": "/", "label": "x"}}}
    o = _trial(paths=("/", "/list") + tuple(f"/item/{c}" for c in "abc"[:orig_pages]), requests=orig_req, backed=False)
    m = _trial(paths=("/", "/list") + tuple(f"/item/{c}" for c in "abc"[:mod_pages]), requests=mod_req, backed=mod_backed)
    return [{"name": "original", "sha256": "o", "profile": prof, "private": priv, "trials": {"o": o}}, {"name": "modified", "sha256": "m", "profile": prof, "private": priv, "trials": {"m": m}}]


def _status(origin="real_model", comparison=None, resolved=True, **kw):
    st = {"original": [_gap("original")], "modified": [] if resolved else [_gap("modified")]}
    return H.link(site="x", versions=_versions(**kw), structural=st, behavioral={}, comparison=comparison, origin=origin)[0]


def test_hypothesis_status_rules():
    assert _status(resolved=False).status == "hypothesis"                                                         # untested
    assert _status(origin="dev_fixture", comparison={"exploratory": "consistent_with_h1"}).status == "hypothesis"   # fixture cannot support
    expl = _status(comparison={"frozen": "inconclusive", "exploratory": "consistent_with_h1"})
    assert expl.status == "supported_exploratory" and "combined change" in expl.detail["status_basis"] and "inconclusive" in expl.detail["status_basis"]
    assert _status(comparison={"frozen": "improvement", "exploratory": "consistent_with_h1"}).status == "supported"
    assert _status(comparison={"frozen": "improvement"}, mod_req=14).status == "hypothesis"                       # behaviour did not improve: never upgraded
    assert _status(comparison={"frozen": "improvement"}, mod_backed=False, orig_req=12).status == "supported"     # passes not lost (0 -> 0) still allowed
    assert _status(comparison=None).status == "hypothesis"                                                        # improved, but no recorded rule


def test_unrelated_structural_risks_are_unverified():
    v = _versions()
    for x in v:
        x["private"] = {"t2": x["private"]["t2"]}
    f = H.link(site="x", versions=v, structural={"original": [_gap("original")], "modified": []}, behavioral={}, comparison=None, origin="real_model")[0]
    assert f.status == "unverified" and f.severity == "info"


def test_every_status_is_from_the_documented_set_and_the_package_is_isolated():
    assert STATUSES == ("observed", "unverified", "hypothesis", "supported_exploratory", "supported")
    hosted = Path(__file__).resolve().parents[1] / "src" / "agent_readiness" / "hosted"
    import ast
    for p in hosted.glob("*.py"):                       # M8 follow-up: diagnostics reach the product only through lifecycle.projection
        for node in ast.walk(ast.parse(p.read_text())):
            names = [node.module or ""] if isinstance(node, ast.ImportFrom) else [a.name for a in node.names] if isinstance(node, ast.Import) else []
            assert not any("diagnostics" in n for n in names), p


RECORDED = Path(__file__).resolve().parents[1] / "scanner-data" / "hosted-copy" / "paired-86a646169296419eb8fffbb59a31dcab"


@pytest.mark.skipif(not RECORDED.is_dir(), reason="private recorded production run not present (not in the repository)")
def test_real_paid_trial_fork_diagnoses_as_documented():
    from agent_readiness.diagnostics.run import diagnose, from_recorded_fork
    rep = diagnose(from_recorded_fork(RECORDED))
    hy = {f["detail"].get("per_version") and f["title"].split("'")[1]: f["status"] for f in rep["findings"] if f["layer"] == "hypothesis" and f["status"] != "unverified"}
    assert hy == {"refundable deposit": "supported_exploratory", "minimum hire": "supported_exploratory", "delivery and collection": "supported_exploratory"}
    assert rep["evidence_origin"] == "real_model" and rep["structural_changes"]["modified"]["introduced"] == []
    assert any(f["rule"] == "dead-end" and "404" in f["evidence"][0]["detail"] for f in rep["findings"])
