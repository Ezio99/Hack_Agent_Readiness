"""M7 (offline): the dashboard export is sanitized, rebuilds baseline/patched outcomes (including void trials) from trial records, resolves evidence references, and tolerates incomplete runs."""
import json
import shutil

import pytest

from agent_readiness.cli import main as cli_main
from agent_readiness.investigate.demo import run_demo
from agent_readiness.investigate.export import SCHEMA, ExportError, check_clean, export_run
from agent_readiness.investigate.run import InvestigationRun

from .synthetic_investigation import FIXTURE, build


@pytest.fixture
def full(tmp_path):
    return build(tmp_path)


def _walk(o):
    if isinstance(o, dict):
        for k, v in o.items():
            yield k
            yield from _walk(v)
    elif isinstance(o, list):
        for v in o:
            yield from _walk(v)
    else:
        yield o


def test_complete_run_rebuilds_outcomes_void_trials_and_labels(full):
    d = export_run(full)
    assert d["schema"] == SCHEMA and d["run"]["complete"] and d["run"]["report_source"] == "report-final" and d["modes"] == ["scripted"]
    by = {t["task_id"]: t for t in d["tasks"]}
    assert by["syn-t5"]["baseline"][0]["void"] is True and by["syn-t5"]["baseline"][0]["passed"] is None          # void is neither pass nor fail
    assert by["syn-t3"]["baseline"][0]["run_status"] == "request_limit" and by["syn-t3"]["baseline"][0]["passed"] is False
    (pid, rows), = by["syn-t1"]["patched"].items()
    assert pid.startswith("prp-") and rows[0]["passed"] is True
    assert d["trials"]["void"] == 1 and d["trials"]["baseline"] == 6 and d["trials"]["patched"] == 6
    ev = d["evaluation"]
    assert ev["state"] == "evaluated" and ev["results"][0]["verdict"] == "improvement" and ev["results"][0]["measured"] is False and ev["results"][0]["effect_mode"] == "scripted"   # scripted is never "measured"
    assert d["effects"][0]["measured"] is False and any("SCRIPTED" in n for n in d["notices"])


def test_findings_resolve_observations_and_support(full):
    d = export_run(full)
    f = d["findings"][0]
    obs = {o["id"] for o in d["observations"]}
    assert f["observation_ids"] and set(f["observation_ids"]) <= obs and f["unresolved_observation_ids"] == []
    assert all(s["resolved"] for s in f["support"])
    novel = next(h for h in d["hypotheses"] if h["tier"] == "novel")
    assert novel["status"] == "unverified" and not novel["promoted"] and novel["verification"] is None
    assert any(p["basis"] == "unverified_hypothesis" and "EXPERIMENTAL" in p["label"] for p in d["proposals"])


def test_dangling_support_is_reported_not_hidden(full):
    run = InvestigationRun(full)
    h = next(h for h in run.evidence.hypotheses.values() if h.tier == "verifiable" and h.status == "supported")
    run.evidence.promote(h.id, attribution="website", support=["trial:ghost-r1", "trial:ghost-r2"], statement="second finding")
    d = export_run(full)
    f = next(f for f in d["findings"] if f["statement"] == "second finding")
    assert [s["resolved"] for s in f["support"]] == [False, False]


def test_incomplete_run_is_supported(tmp_path):
    d = export_run(build(tmp_path, complete=False))
    assert d["run"]["complete"] is False and d["run"]["report_source"] == "evidence" and "report-final" in d["run"]["missing_artifacts"]
    assert d["evaluation"]["state"] == "missing" and d["evaluation"]["results"] == []
    assert any(s["status"] == "awaiting_approval" and s["manifest_sha256"] for s in d["stages"])
    assert d["findings"]                                                                    # evidence recorded so far is still shown


def test_run_without_trials_or_manifest_still_exports(tmp_path):
    run, _ = run_demo(tmp_path, "d")                                                         # scripted demo: no taskgen, trials or report-final
    d = export_run(run.dir)
    assert d["tasks"] == [] and d["trials"]["baseline"] == 0 and d["run"]["complete"] is False and "tasks-manifest" in d["run"]["missing_artifacts"]
    assert d["evaluation"]["state"] == "missing"


def test_unreadable_artifact_is_treated_as_missing(full):
    (full / "artifacts" / "evaluation.json").write_text("{truncated")
    assert export_run(full)["evaluation"]["state"] == "missing"


def test_private_material_is_never_exported(full):
    run = InvestigationRun(full)
    run.write_private("criteria", {"syn-t1": {"truth": "PRIVATE-TRUTH-9f3a", "criterion": {"x": 1}}})
    run.write_private("investigator-transcript", ["PRIVATE-TRANSCRIPT-77c1"])
    (full / "artifacts" / "trials" / "baseline-syn-t1-r1.json").write_text(json.dumps({**run.artifact("trials/baseline-syn-t1-r1"), "outcome": {"run_status": "completed", "answer": "PRIVATE-ANSWER-12ab"},
                                                                                   "journey": [{"path": "/secret"}]}))
    text = json.dumps(export_run(full))
    for secret in ("PRIVATE-TRUTH-9f3a", "PRIVATE-TRANSCRIPT-77c1", "PRIVATE-ANSWER-12ab", "/secret", "journey", "criterion"):
        assert secret not in text


def test_guard_refuses_forbidden_keys_credentials_and_paths(monkeypatch):
    for bad in ({"truth": "x"}, {"a": [{"answer": "x"}]}, {"a": "Bearer abcdefghijklmnopqrstuv"}, {"a": "see /home/user/run"}, {"a": "key sk-abcdefghijklmnopqrstu"}):
        with pytest.raises(ExportError):
            check_clean(bad)
    monkeypatch.setenv("META_MODEL_API_KEY", "super-secret-value")
    with pytest.raises(ExportError):
        check_clean({"note": "oops super-secret-value"})
    check_clean({"ok": "plain text", "n": 1})


def test_committed_fixture_matches_the_exporter_and_is_labelled_synthetic(tmp_path):
    committed = json.loads(FIXTURE.read_text())
    fresh = export_run(build(tmp_path))
    for d in (committed, fresh):
        d.pop("synthetic", None), d.pop("exported_at"), d["run"].pop("created_at")
        for s in d["stages"]:
            s.pop("updated_at")
    assert committed == fresh, "regenerate with: python -m tests.synthetic_investigation"
    assert json.loads(FIXTURE.read_text())["synthetic"] is True and "fixture" in committed["run"]["target"]
    assert "scripted" in " ".join(committed["notices"]).lower()


def test_cli_export_writes_file(full, tmp_path, capsys, monkeypatch):
    out = tmp_path / "x.json"
    monkeypatch.setattr("sys.argv", ["readiness", "investigate", "export", str(full), "--out", str(out)])
    cli_main()
    assert json.loads(out.read_text())["schema"] == SCHEMA and "complete=True" in capsys.readouterr().out
    monkeypatch.setattr("sys.argv", ["readiness", "investigate", "export", str(tmp_path / "nope"), "--out", str(out)])
    with pytest.raises(SystemExit):
        cli_main()


def test_stages_are_exported_in_pipeline_order(full):
    names = [s["name"] for s in export_run(full)["stages"]]
    assert names[:4] == ["inspect", "taskgen", "freeze", "baseline_trials"] and names[-1] == "final_report"


def test_fixture_numbers_are_rederivable_from_its_own_trial_rows():
    """The synthetic before/after figures must follow from the displayed trials under the real pre-registered rule, and be labelled illustrative."""
    from agent_readiness.investigate.evaluate import design
    d = json.loads(FIXTURE.read_text())
    (r,) = d["evaluation"]["results"]
    pid = r["proposal_id"]
    row = lambda t: {"void": t["void"], "passed": bool(t["passed"]), "evidence_backed": bool(t["evidence_backed"]), "model_requests": t["model_requests"], "primary": "x", "page_views": t["page_views"]}
    base = {t["task_id"]: [row(x) for x in t["baseline"]] for t in d["tasks"]}
    post = {t["task_id"]: [row(x) for x in t["patched"][pid]] for t in d["tasks"]}
    c = design.compare(base, post, {t["task_id"]: t["partition"] for t in d["tasks"]}, design.RULE)
    for k in ("verdict", "pairs", "pass_delta", "request_change", "p_pass", "p_requests", "holdout_consistent"):
        assert r[k] == c[k], k
    assert r["by_partition"] == c["by_partition"] and [e["task_id"] for e in r["excluded"]] == [e["task_id"] for e in c["excluded"]]
    assert r["measured"] is False and r["reason"].startswith("ILLUSTRATIVE") and d["synthetic"] is True


# ---- EXP-B: unmodified-repeat ("placebo") trials and the separate exploratory evaluation ----
@pytest.fixture
def expb(tmp_path):
    from tests.synthetic_investigation import build_expb
    return build_expb(tmp_path)


def test_expb_export_carries_the_three_arms_and_counts(expb):
    d = export_run(expb)
    by = {t["task_id"]: t for t in d["tasks"]}
    (pid,) = by["syn-t1"]["patched"]
    assert [r["model_requests"] for r in (by["syn-t1"]["baseline"] + by["syn-t1"]["placebo"][pid] + by["syn-t1"]["patched"][pid])] == [13, 12, 4]
    assert set(t for t, v in by.items() if v["placebo"]) == {"syn-t1", "syn-t2", "syn-t3"}        # detail-page controls have no unmodified repeat
    assert by["syn-t2"]["placebo"][pid][0]["passed"] is False and by["syn-t2"]["patched"][pid][0]["passed"] is True
    assert d["trials"]["baseline"] == 6 and d["trials"]["patched"] == 6 and d["trials"]["placebo"] == 3 and d["trials"]["void"] == 0 and d["trials"]["quarantined"] == 0
    assert d["run"]["outcome"] == "experimental_only" and d["findings"] == []


def test_frozen_and_exploratory_verdicts_are_separate_and_both_exported(expb):
    ev = export_run(expb)["evaluation"]
    (frozen,) = ev["results"]
    assert ev["rule"]["id"] == "paired-signflip-v1" and frozen["verdict"] == "inconclusive" and frozen["measured"] is False
    x = ev["exploratory"]
    assert x["rules_id"] == "exploratory-listing-v1" and x["verdict"] == "consistent_with_h1" and "never its replacement" in x["label"]
    assert x["rules_sha256"] == "f8c25e461c64eb87c0bd77c5e0a38dce0a5721ddfd471a2d2eb35efc4aa6ea99" and x["rules_match_code"] is True and x["rules"]["effect_floor"] == 0.25
    assert x["plan"]["affected"] == ["syn-t1", "syn-t2"] and x["noise_estimate_requests"] == 1 and x["controls_within_tolerance"] is True
    assert x["tasks"]["placebo"]["syn-t1"]["requests"] == 12 and x["tasks"]["patched"]["syn-t1"]["requests"] == 4 and x["tasks"]["baseline"]["syn-t1"]["requests"] == 13
    assert x["affected"]["syn-t1"]["primary_meets_floor"] is True
    assert "exploratory" not in frozen                                                          # the exploratory block never leaks into the frozen result


def test_owner_selected_change_is_labelled_and_never_a_verified_finding(expb):
    d = export_run(expb)
    (p,) = d["proposals"]
    assert p["basis"] == "unverified_hypothesis" and p["owner_selected"] is True and p["exploratory"] is True and p["label"].startswith("EXPERIMENTAL — OWNER-SELECTED") and p["approved"] is True
    hyp = {h["id"]: h for h in d["hypotheses"]}
    assert hyp[p["source_id"]]["tier"] == "novel" and hyp[p["source_id"]]["status"] == "unverified" and hyp[p["source_id"]]["provenance"]["source"].startswith("owner:")
    assert any(h["status"] == "supported" and not h["promoted"] for h in hyp.values())            # the verified-but-unpromoted pattern stays a hypothesis
    assert d["findings"] == []


def test_exploratory_block_is_absent_for_a_run_without_one_and_exports_are_clean(full, expb):
    assert export_run(full)["evaluation"]["exploratory"] is None and export_run(full)["trials"]["placebo"] == 0
    d = export_run(expb)
    check_clean(d)
    assert not (set(_walk(d)) & {"truth", "criteria", "answer", "transcript", "journey"})


def test_exploratory_rules_are_dropped_when_the_stored_hash_does_not_match_the_code(expb):
    ev = json.loads((expb / "artifacts" / "evaluation.json").read_text())
    ev["exploratory"]["rules_sha256"] = "0" * 64
    (expb / "artifacts" / "evaluation.json").write_text(json.dumps(ev))
    x = export_run(expb)["evaluation"]["exploratory"]
    assert x["rules"] is None and x["rules_match_code"] is False and x["verdict"] == "consistent_with_h1"


def test_quarantined_and_void_trials_are_counted_not_hidden(expb):
    q = expb / "artifacts" / "trials-quarantine"
    q.mkdir()
    (q / "placebo-x.json").write_text("{}")
    t = json.loads((expb / "artifacts" / "trials" / next(p.name for p in (expb / "artifacts" / "trials").glob("placebo-*"))).read_text())
    t["outcome"]["run_status"] = "infrastructure_error"
    (expb / "artifacts" / "trials" / next(p.name for p in (expb / "artifacts" / "trials").glob("placebo-*"))).write_text(json.dumps(t))
    d = export_run(expb)
    assert d["trials"]["quarantined"] == 1 and d["trials"]["void"] == 1


def test_expb_fixture_matches_the_exporter_and_is_labelled_synthetic(tmp_path):
    from tests.synthetic_investigation import FIXTURE_EXPB, build_expb
    committed, fresh = json.loads(FIXTURE_EXPB.read_text()), export_run(build_expb(tmp_path))
    for d in (committed, fresh):
        d.pop("synthetic", None), d.pop("exported_at"), d["run"].pop("created_at")
        for s in d["stages"]:
            s.pop("updated_at")
    assert committed == fresh, "regenerate with: python -m tests.synthetic_investigation"
    assert json.loads(FIXTURE_EXPB.read_text())["synthetic"] is True and "fixture" in committed["run"]["target"]


def test_expb_fixture_verdicts_rederive_from_its_own_rows():
    from agent_readiness.investigate.evaluate import exploratory
    from tests.synthetic_investigation import FIXTURE_EXPB
    d = json.loads(FIXTURE_EXPB.read_text())
    (pid,) = d["tasks"][0]["patched"]
    row = lambda r: [{"void": r["void"], "passed": bool(r["passed"]), "evidence_backed": bool(r["evidence_backed"]), "model_requests": r["model_requests"], "page_views": r["page_views"]}]
    base = {t["task_id"]: row(t["baseline"][0]) for t in d["tasks"]}
    plc = {t["task_id"]: row(t["placebo"][pid][0]) for t in d["tasks"] if t["placebo"]}
    pat = {t["task_id"]: row(t["patched"][pid][0]) for t in d["tasks"]}
    x = d["evaluation"]["exploratory"]
    assert exploratory.analyze(x["plan"], base, plc, pat)["verdict"] == x["verdict"]


def test_spend_is_exported_by_arm_from_the_ledger_as_a_calculated_estimate(expb):
    (expb / "spend").mkdir()
    rows = []
    for i, (rid, usd) in enumerate([("taskgen-batch0:req01", 0.01), ("baseline-gen-a-r1:req01", 0.02), ("placebo-prp-x-gen-a-r1:req01", 0.03), ("patched-prp-x-gen-a-r1:req01", 0.04), ("patched-prp-x-gen-a-r1:req02", 0.05)]):
        rows += [{"ts": "t", "kind": "reserve", "id": rid, "usd": usd + 0.01}, {"ts": "t", "kind": "settle", "id": rid, "usd": usd}]
    rows.append({"ts": "t", "kind": "reserve", "id": "patched-prp-x-gen-b-r1:req01", "usd": 0.02})        # an open reservation is reported, not hidden
    (expb / "spend" / "ledger.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    s = export_run(expb)["spend"]
    assert s["state"] == "ok" and "not a bill" in s["basis"] and s["committed_usd"] == 0.15 and s["open_reservations"] == 1
    assert s["by_arm_usd"] == {"baseline": 0.02, "other": 0.01, "patched": 0.09, "placebo": 0.03} and s["by_trial_usd"]["patched-prp-x-gen-a-r1"] == 0.09


def test_missing_ledger_is_reported_as_missing(expb):
    assert export_run(expb)["spend"] == {"state": "missing"}


# ---- public-demo-safe view ----
import re as _re  # noqa: E402

from agent_readiness.investigate.export import check_public, public_demo  # noqa: E402


@pytest.fixture
def pub(expb):
    (expb / "spend").mkdir()
    (expb / "spend" / "ledger.jsonl").write_text("\n".join(json.dumps(r) for r in [{"ts": "t", "kind": "reserve", "id": "patched-prp-x-syn-t1-r1:req01", "usd": 0.02}, {"ts": "t", "kind": "settle", "id": "patched-prp-x-syn-t1-r1:req01", "usd": 0.01}]) + "\n")
    private = export_run(expb)
    return private, public_demo(private)


def test_public_export_keeps_outcomes_arms_controls_both_verdicts_and_owner_provenance(pub):
    private, d = pub
    assert d["audience"] == "public-demo" and d["run"]["id"] == "public-demo" and d["exported_at"] is None
    assert [t["question"] for t in d["tasks"]] == [t["question"] for t in private["tasks"]] and [t["partition"] for t in d["tasks"]] == [t["partition"] for t in private["tasks"]]
    base = lambda x: [(r["passed"], r["model_requests"], r["page_views"]) for t in x["tasks"] for r in t["baseline"]]
    assert base(d) == base(private)
    flat = lambda x, arm: sorted((r["passed"], r["model_requests"], r["page_views"]) for t in x["tasks"] for rows in t[arm].values() for r in rows)
    assert flat(d, "patched") == flat(private, "patched") and flat(d, "placebo") == flat(private, "placebo") and len(flat(d, "placebo")) == 3
    ev, pe = d["evaluation"], private["evaluation"]
    assert ev["results"][0]["verdict"] == pe["results"][0]["verdict"] == "inconclusive" and ev["rule"]["id"] == "paired-signflip-v1"
    assert ev["exploratory"]["verdict"] == pe["exploratory"]["verdict"] and ev["exploratory"]["rules_id"] == "exploratory-listing-v1" and ev["exploratory"]["rules_sha256"] == pe["exploratory"]["rules_sha256"]
    (p,) = d["proposals"]
    assert p["owner_selected"] is True and p["label"].startswith("EXPERIMENTAL — OWNER-SELECTED") and p["basis"] == "unverified_hypothesis" and p["provenance"]["source"] == "owner" and d["findings"] == []
    assert d["spend"]["by_arm_usd"] == private["spend"]["by_arm_usd"] and "by_trial_usd" not in d["spend"] and d["trials"]["placebo"] == 3


def test_public_export_has_no_internal_ids_hashes_narratives_or_paths(pub):
    private, d = pub
    text = json.dumps(d)
    assert not _re.search(r"\b(?:syn-t\d|prp-[0-9a-f]{10}|obs-[0-9a-f]{10}|hyp-[0-9a-f]{10}|eff-[0-9a-f]{10})", text), "internal ids must be aliased"
    assert set(_re.findall(r"[0-9a-f]{64}", text)) == {private["evaluation"]["exploratory"]["rules_sha256"]}          # only the pre-registered rules hash survives
    assert '"why"' not in text and '"attribution"' not in text and "synthetic fixture attribution" not in text and "/home/" not in text and "project-owner" not in text
    assert all(s["manifest_sha256"] is None and s["updated_at"] is None for s in d["stages"])
    assert d["tasks"][0]["task_id"].startswith("task-") and all("source" not in t for t in d["tasks"])
    for r in (r for t in d["tasks"] for r in t["baseline"]):
        assert "attribution" not in r and "why" not in r


def test_public_export_is_consistent_after_aliasing(pub):
    _, d = pub
    ids = {t["task_id"] for t in d["tasks"]}
    x = d["evaluation"]["exploratory"]
    assert set(x["plan"]["affected"]) <= ids and set(x["tasks"]["patched"]) <= ids and set(x["affected"]) <= ids
    (pid,) = {k for t in d["tasks"] for k in t["patched"]}
    assert pid == "change-1" and d["proposals"][0]["id"] == pid and d["effects"][0]["proposal_id"] == pid and d["evaluation"]["results"][0]["proposal_id"] == pid
    assert d["hypotheses"][1]["id"].startswith("hypothesis-") and all(o["id"].startswith("observation-") for o in d["observations"])


@pytest.mark.parametrize("bad", [{"tasks": [{"baseline": [{"attribution": "agent"}], "patched": {}}]}, {"x": "gen-0384beb35e"}, {"x": "a" * 64}, {"x": "see /home/vaibhav/x"}, {"x": "investigations/site-5-live-c/private"},
                                 {"x": "trial-data/baseline"}, {"why": "narrative"}, {"spend": {"by_trial_usd": {"a": 1}}}, {"stages": [{"manifest_sha256": "x"}]}])
def test_public_guard_refuses_leaks(bad):
    with pytest.raises(ExportError):
        check_public(bad)


def test_public_guard_allows_the_rules_hash_and_plain_text():
    check_public({"rules_sha256": "f" * 64, "note": "plain text 13 requests"})


def test_private_export_is_unchanged_by_the_public_view(expb):
    before = export_run(expb)
    snapshot = json.dumps(before, sort_keys=True)
    public_demo(before)
    assert json.dumps(before, sort_keys=True) == snapshot                                    # the public view works on a copy
    assert "syn-t1" in snapshot and "audience" not in before


def test_cli_public_flag_writes_the_public_view(expb, tmp_path, monkeypatch, capsys):
    out = tmp_path / "pub.json"
    monkeypatch.setattr("sys.argv", ["readiness", "investigate", "export", str(expb), "--out", str(out), "--public"])
    cli_main()
    d = json.loads(out.read_text())
    assert d["audience"] == "public-demo" and "syn-t1" not in out.read_text()
    out2 = tmp_path / "priv.json"
    monkeypatch.setattr("sys.argv", ["readiness", "investigate", "export", str(expb), "--out", str(out2)])
    cli_main()
    assert "audience" not in json.loads(out2.read_text()) and "syn-t1" in out2.read_text()


def test_public_fixture_matches_the_exporter(tmp_path):
    from tests.synthetic_investigation import FIXTURE_EXPB_PUBLIC, build_expb
    committed = json.loads(FIXTURE_EXPB_PUBLIC.read_text())
    fresh = public_demo(export_run(build_expb(tmp_path)))
    for d in (committed, fresh):
        d.pop("synthetic", None), d.pop("exported_at"), d["run"].pop("created_at")
    assert committed == fresh and json.loads(FIXTURE_EXPB_PUBLIC.read_text())["synthetic"] is True


# ---- static storefront block (PR 1 of the demo journey) ----
def test_storefront_exports_original_and_patched_pages_with_an_exact_diff(expb):
    s = export_run(expb)["storefront"]
    assert s["state"] == "ok" and set(s["original"]["pages"]) == {"/", "/cabins", "/cabins/pine", "/cabins/lake", "/cabins/birch"}
    (v,) = s["variants"]
    assert v["diff"]["pages_changed"] == ["/cabins"] and v["diff"]["pages_unchanged"] == 4 and v["diff"]["elements_added"] == 3 and v["diff"]["inserted_text"]["/cabins"][0] == "Nightly fee: $95"
    assert all(v["pages"][p] == s["original"]["pages"][p] for p in s["original"]["pages"] if p != "/cabins")          # every other page is byte-identical
    assert "Nightly fee: $95" in v["pages"]["/cabins"] and "Nightly fee: $95" not in s["original"]["pages"]["/cabins"]


def test_storefront_is_missing_or_omitted_rather_than_unsafe(expb, tmp_path):
    import shutil
    from agent_readiness.investigate.sitemodel.snapshot import Resource, Snapshot
    assert export_run(expb)["storefront"]["state"] == "ok"
    snap = Snapshot.load(expb / "snapshot")
    for bad in ("<p><script>alert(1)</script></p>", '<img src="x.png">', '<a href="https://example.com/x">x</a>', '<p onclick="x()">x</p>', "x" * 21_000):
        res = dict(snap.resources)
        res["/"] = Resource("/", 200, "text/html; charset=utf-8", f"<!DOCTYPE html><html><body>{bad}</body></html>".encode())
        shutil.rmtree(expb / "snapshot")
        Snapshot(res, {}).save(expb / "snapshot")
        assert export_run(expb)["storefront"]["state"] == "omitted", bad
    shutil.rmtree(expb / "snapshot")
    assert export_run(expb)["storefront"]["state"] == "missing"


def test_public_view_keeps_the_storefront_and_refuses_unsafe_html(pub):
    private, d = pub
    assert d["storefront"]["state"] == "ok" and d["storefront"]["variants"][0]["proposal_id"] == "change-1" and d["storefront"]["variants"][0]["diff"]["elements_added"] == 3
    assert "snapshot_sha256" not in json.dumps(d["storefront"])
    for bad in ("<!DOCTYPE html><html><body><script>x</script></body></html>", "<!DOCTYPE html><html><body>see https://evil.example/x</body></html>"):
        with pytest.raises(ExportError):
            check_public({"storefront": {"original": {"pages": {"/": bad}}}})
    check_public({"storefront": {"original": {"pages": {"/": "<!DOCTYPE html><html><body><a href=\"/cabins\">Cabins</a></body></html>"}}}})
