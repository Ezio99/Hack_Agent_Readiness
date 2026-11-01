"""Owner insights (derived, model-free): measured site properties and agent effort kept apart, hypotheses grouped and labelled with the checker's own status, text-only UNVALIDATED suggestions only where trial friction
exists, strict grade labelled as name matching next to what the answer text mentions. Nothing here is VERIFIED, and no patch is built. Offline."""
import json

from agent_readiness.investigate.insights import FRICTION_EXTRA_VIEWS, build_insights
from agent_readiness.investigate.investigator.loop import investigate
from agent_readiness.investigate.llm import ScriptedClient
from agent_readiness.investigate.taskgen import freeze as freezer

from .test_investigate_investigator import hyp, scripted_model, smooth, step, struggling, ws_for


def finish_with(ws, claims, max_calls=0):
    res = investigate(ws, ScriptedClient(scripted_model([lambda last, req: step("finish", hyps=claims)])), max_calls=max_calls)
    inv = {k: v for k, v in res.items() if k != "transcript"}
    ws.run.write_artifact("investigation", {**inv, "skipped": False, "model": "scripted-model", "mode": "mock"})
    return res


def obs(ws):
    return next(iter(ws.run.evidence.observations))


def bad(ws, label):
    return hyp(f"{label} is only visible after 1 hop on the detail pages", [obs(ws)], claim_kind="info_only_after_k_hops", k=1, label=label)


def labels_of(ws):
    _, private = freezer.load(ws.run)
    return sorted({l for p in private.values() for l in ([p["criterion"].get("label")] if p["criterion"].get("label") else [c["label"] for c in p["criterion"].get("conditions", [])])})


def test_friction_on_fields_missing_from_the_cards_gives_measurements_hypotheses_and_one_unvalidated_text_suggestion(tmp_path):
    ws = ws_for(tmp_path, struggling, "site-1", "fr")
    labels = labels_of(ws)
    finish_with(ws, [bad(ws, l) for l in labels[:3]])                                  # k=1 claims the checker cannot use, as in the archived owner-task run
    d = build_insights(ws.run)
    assert d["schema"] == "owner-insights-v1" and d["site_properties"] and any(p["absent_from_cards"] for p in d["site_properties"])
    assert d["task_effort"] and all(e["trial_id"] and e["page_views"] >= e["minimum_page_views"] for e in d["task_effort"]) and any(e["friction"] for e in d["task_effort"])
    kinds = [c["source"] for c in d["possible_causes"]]
    assert kinds.count("rule") == 1 and kinds.count("the investigator (model)") == 1, "three similar claims are grouped into ONE entry"
    inv_cause = next(c for c in d["possible_causes"] if c["source"] != "rule")
    assert "could not be checked" in inv_cause["status"] and "k` >= 2" in inv_cause["status"] and "not as a finding" in inv_cause["status"] and len(inv_cause["fields"]) == len(labels[:3])
    assert all(c["label"].startswith("POSSIBLE CAUSE (hypothesis") for c in d["possible_causes"])
    assert len(d["suggestions"]) == 1 and d["suggestions"][0]["label"] == "SUGGESTED IMPROVEMENT (UNVALIDATED)" and d["suggestions"][0]["patch"] is None
    assert d["suggestions"][0]["expected_benefit"].startswith("HYPOTHESIS, not measured") and d["suggestions"][0]["basis"]
    assert d["strict_findings"] == 0 and not ws.run.evidence.findings


def test_an_unverifiable_claim_is_never_called_verified_and_no_patch_or_change_is_built(tmp_path):
    ws = ws_for(tmp_path, struggling, "site-1", "nv")
    finish_with(ws, [bad(ws, l) for l in labels_of(ws)[:2]])
    before = sorted(p.name for p in (ws.run.dir / "artifacts").iterdir())
    d = build_insights(ws.run)
    blob = json.dumps(d)
    assert "VERIFIED" not in blob and '"ops"' not in blob and "copy_field_to_listing" not in blob
    assert all(s["patch"] is None for s in d["suggestions"])
    assert sorted(p.name for p in (ws.run.dir / "artifacts").iterdir()) == before, "building insights writes nothing and creates no recommendation or patch"


def test_supported_but_unpromoted_claims_say_so_and_do_not_become_findings(tmp_path):
    ws = ws_for(tmp_path, smooth, "site-1", "sp")
    lab = labels_of(ws)[0]
    finish_with(ws, [hyp(f"{lab} is only on the detail pages, not on the listing", [obs(ws)], claim_kind="info_absent_on_template", label=lab)])
    d = build_insights(ws.run)
    c = next(c for c in d["possible_causes"] if c["source"] != "rule")
    assert "the checker supported it" in c["status"] and "below the promotion rule" in c["status"] and not ws.run.evidence.findings and d["strict_findings"] == 0
    assert d["suggestions"] == [] and d["summary"].startswith("No friction was observed"), "no friction on the trials: no friction-based suggestion, whatever the claims say"


def test_no_friction_gives_measurements_only_and_an_honest_empty_state(tmp_path):
    ws = ws_for(tmp_path, smooth, "site-3", "nf")
    finish_with(ws, [])
    d = build_insights(ws.run)
    assert d["possible_causes"] == [] and d["suggestions"] == [] and d["friction_tasks"] == [] and "No friction-based suggestion is made" in d["summary"]
    assert all(e["extra_page_views"] < FRICTION_EXTRA_VIEWS for e in d["task_effort"])


def test_a_strict_name_mismatch_is_labelled_as_such_and_not_as_failing_to_find_the_answer(tmp_path):
    from .test_investigate_investigator import fake_trial, seed
    ws = ws_for(tmp_path, smooth, "site-1", "sg")
    run = ws.run
    manifest, private = freezer.load(run)
    t = next(t for t in manifest["tasks"] if t["kind"] == "page_fact")
    truth = private[t["task_id"]]["truth"]
    for f in (run.dir / "artifacts" / "trials").glob(f"*{t['task_id']}*"):
        rec = json.loads(f.read_text())
        rec["outcome"]["answer"] = {"answer": f"I believe it is {truth}, though the page also lists other figures"}
        rec["evaluation"]["passed"] = False
        f.unlink()
        run.write_artifact(f"trials/{f.stem}", rec)
    d = build_insights(run)
    row = next(e for e in d["task_effort"] if e["task_id"] == t["task_id"])
    assert row["passed"] is False and row["strict_grade"].startswith("strict answer match") and row["names_mentioned_in_answer"] == "1 of 1"
    assert any("wording or format mismatch, not that the agent failed to find the answer" in n for n in row["notes"])


def test_provenance_records_task_sources_model_and_status(tmp_path):
    ws = ws_for(tmp_path, struggling, "site-1", "pv")
    finish_with(ws, [])
    p = build_insights(ws.run)["provenance"]
    assert p["run_id"] == ws.run.state["id"] and p["source_run"] is None and sum(p["task_sources"].values()) == p["frozen_tasks"] and p["investigator_model"] == "scripted-model" and "no model call" in p["note"]


def test_a_run_without_trials_has_no_insights(tmp_path):
    from agent_readiness.investigate.run import InvestigationRun
    run = InvestigationRun.create(tmp_path, "empty", target="ironbark", mode="live", stages=("inspect",))
    assert build_insights(run) is None


def test_an_investigator_proposed_change_is_not_suggested_when_no_trial_showed_friction(tmp_path):
    ws = ws_for(tmp_path, smooth, "site-1", "pc")
    finish_with(ws, [hyp("Agents lose track of which workshops they opened", [obs(ws)], prediction="if cards listed seats, page views would drop", proposed_change="Add seats left to each card")])
    d = build_insights(ws.run)
    assert d["suggestions"] == [] and any("open-ended idea" in c["status"] for c in d["possible_causes"]), "the idea stays a hypothesis; with no measured friction it is not turned into a suggestion"
