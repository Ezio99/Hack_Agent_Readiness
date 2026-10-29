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
