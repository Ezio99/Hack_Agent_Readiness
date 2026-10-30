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
