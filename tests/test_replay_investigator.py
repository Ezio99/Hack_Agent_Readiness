"""Investigator-only replay of a finished live run (offline): a fork imports the frozen tasks, the baseline trials and the spending history unchanged; only the investigator and the later free stages run, under a
fresh exact-manifest approval and a ceiling of imported spend plus the investigator stage cap. Scripted model; no network, no key, no browser."""
import hashlib
import json
from types import SimpleNamespace

import pytest

from agent_readiness.investigate import zoo
from agent_readiness.investigate.llm import ScriptedClient
from agent_readiness.investigate.run import InvestigationRun
from agent_readiness.live import cli as live_cli, targets, worker

from .test_investigate_investigator import hyp, scripted_model, step
from .test_investigate_recovery import source  # noqa: F401  (a finished 'live' run with frozen tasks, trials, history and approvals)

GOAL = "Can a visitor compare the price, date and seats left across the workshops?"


def tree(root):
    return hashlib.sha256(b"".join(p.relative_to(root).as_posix().encode() + p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file())).hexdigest()


@pytest.fixture
def src(tmp_path, source, monkeypatch):                                  # noqa: F811
    snap = zoo.snapshot("site-1")
    source.write_artifact("live-grant", {"goal": GOAL, "snapshot_sha256": snap.sha256, "model": "muse-spark-1.3", "endpoint": "https://api.meta.ai/v1", "context_sha256": "", "target_id": "site-1"})
    monkeypatch.setitem(targets.TARGETS, "site-1", targets.DemoTarget("site-1", "Test site 1", "zoo site", lambda: snap))
    return source


def args(tmp_path, src, **kw):
    return SimpleNamespace(**{**dict(source=src.dir, id="replay-1", root=tmp_path, max_calls=12, approve_hash=None, allow_model_calls=False, export=None), **kw})


def plan(tmp_path, src, capsys, **kw):
    assert live_cli.replay_investigator(args(tmp_path, src, **kw)) == 0
    return json.loads(capsys.readouterr().out)


def test_the_plan_is_free_reproducible_bounded_and_leaves_the_source_untouched(tmp_path, src, capsys):
    before = tree(src.dir)
    p = plan(tmp_path, src, capsys)
    assert tree(src.dir) == before, "the source run is only read"
    assert p["source_run"] == "src-live" and p["forked_from"] == "src-live" and p["paid_stages_rerun"] is False and p["stage"] == "investigate" and p["retries_per_request"] == 1
    assert p["imported_spend_usd"] == pytest.approx(0.034125, abs=1e-6) and p["run_cap_usd"] == 0.4
    assert p["ledger_ceiling_usd"] == pytest.approx(0.45, abs=0.011) and p["maximum_new_spend_usd"] <= 0.42, "new spend is capped at about the investigator stage cap"
    again = plan(tmp_path, src, capsys)
    assert again["manifest_sha256"] == p["manifest_sha256"], "the replay approval hash is reproducible"
    fork = InvestigationRun(tmp_path / "replay-1")
    assert [fork.status(s) for s in ("taskgen", "freeze", "baseline_trials")] == ["done"] * 3 and fork.status("investigate") == "awaiting_approval" and fork.approvals() == []
    assert (fork.dir / "artifacts" / "tasks-manifest.json").read_bytes() == (src.dir / "artifacts" / "tasks-manifest.json").read_bytes()
    assert (fork.dir / "spend" / "ledger.jsonl").read_bytes() == (src.dir / "spend" / "ledger.jsonl").read_bytes()


def test_the_replay_manifest_differs_from_the_original_and_shows_the_fork_provenance(tmp_path, src, capsys):
    p = plan(tmp_path, src, capsys)
    m = json.loads(next((tmp_path / "replay-1" / "artifacts" / "manifests").glob("investigate-*.json")).read_text())
    assert m["forked_from"]["source_run"] == "src-live" and m["forked_from"]["paid_stages_rerun"] is False and p["manifest_sha256"] != "c" * 64
    assert m["forked_from"]["source_approvals_not_inherited"][1] == {"stage": "investigate", "manifest_sha256": "c" * 64}


def test_it_refuses_a_wrong_hash_a_missing_flag_and_a_changed_site(tmp_path, src, capsys, monkeypatch):
    p = plan(tmp_path, src, capsys)
    with pytest.raises(SystemExit, match="not the one you approved"):
        live_cli.replay_investigator(args(tmp_path, src, approve_hash="0" * 64, allow_model_calls=True))
    with pytest.raises(SystemExit, match="--allow-model-calls"):
        live_cli.replay_investigator(args(tmp_path, src, approve_hash=p["manifest_sha256"]))
    assert InvestigationRun(tmp_path / "replay-1").approvals() == []
    other = zoo.snapshot("site-2")
    monkeypatch.setitem(targets.TARGETS, "site-1", targets.DemoTarget("site-1", "x", "x", lambda: other))
    with pytest.raises(SystemExit, match="no longer matches"):
        live_cli.replay_investigator(args(tmp_path, src, id="replay-2"))


def test_an_approved_replay_runs_only_the_investigator_with_one_bounded_correction_and_writes_a_labelled_export(tmp_path, src, capsys, monkeypatch):
    p = plan(tmp_path, src, capsys)
    before = tree(src.dir)
    seen = {}

    def bad(last, req):
        seen["obs"] = last["evidence_id"]
        return step("finish", hyps=[hyp("Prices are only visible after 1 hop on the detail pages", [seen["obs"]], claim_kind="info_only_after_k_hops", k=1, label="price")])
    fix = lambda last, req: step("finish", hyps=[hyp("The price is only on detail pages, not on the listing", [seen["obs"]], claim_kind="info_absent_on_template", label="price", replaces=1)])
    llm = ScriptedClient(scripted_model([step("list_trials"), step("page_dom", path="/workshops", css="li.card a"), bad, fix]))
    real = worker.live_options
    monkeypatch.setattr(worker, "live_options", lambda *a, **k: {**real(*a, **k), "investigator_llm": llm})
    out = tmp_path / "export.json"
    assert live_cli.replay_investigator(args(tmp_path, src, approve_hash=p["manifest_sha256"], allow_model_calls=True, export=out)) == 0
    fork = InvestigationRun(tmp_path / "replay-1")
    assert [a["stage"] for a in fork.approvals()] == ["investigate"] and "OPERATOR replay approval" in fork.approvals()[0]["note"] and fork.approvals()[0]["manifest_sha256"] == p["manifest_sha256"]
    inv = fork.artifact("investigation")
    assert inv["status"] == "completed" and inv["model_requests"] == 4 and inv["claim_audit"][0]["original"]["parameters"]["k"] == 1 and inv["claim_audit"][0]["outcome"].startswith("corrected")
    assert [fork.status(s) for s in ("taskgen", "freeze", "baseline_trials")] == ["done"] * 3 and tree(src.dir) == before, "no task generation, no browser trial, the source run untouched"
    data = json.loads(out.read_text())
    assert data["goal"] == GOAL and data["notices"][0].startswith("INVESTIGATOR REPLAY") and "goal_coverage" in data
    assert data["insights"] is not None and data["insights"]["provenance"]["source_run"] == "src-live" and data["insights"]["provenance"]["task_sources"], "the replay export carries insights with the fork provenance"
