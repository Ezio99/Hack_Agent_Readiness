"""Diagnostic-quality work: grant-bound owner-authored tasks, the four detail-field tasks, the pre-registration, the listing-field recommendation on Ironbark and the offline rehearsal of the whole chain
(scripted agent + scripted investigator: this validates the pipeline, NOT any model's investigative ability). Offline / dev provider only."""
import hashlib
import json
from pathlib import Path

import pytest

from agent_readiness.agent import ModelConfig
from agent_readiness.exp2 import snapshot as S
from agent_readiness.investigate import flow
from agent_readiness.investigate.inspect.profile import build_profile
from agent_readiness.investigate.recommend import templates as T
from agent_readiness.investigate.taskgen import goal as G
from agent_readiness.investigate.taskgen.gate import Accepted, Draft, evaluate
from agent_readiness.live import cli as live_cli, grant as GR, mock_investigator, worker
from agent_readiness.live.jobs import JobError, JobManager, clean_owner_tasks
from agent_readiness.live.lexicon import RENTAL
from agent_readiness.suite.core import canonical_hash

from .test_live_m1 import KEY, SNAP, approver, grant, manifest, provider, settings, wait_for  # noqa: F401

ROOT = Path(__file__).resolve().parent.parent
TASKS_FILE = ROOT / "collaboration" / "proposals" / "ironbark-owner-tasks.json"
PREREG = ROOT / "collaboration" / "proposals" / "IRONBARK-DIAGNOSTIC-DEMO-preregistration.md"
GOAL = "Can an AI agent compare the refundable deposit, minimum hire period, and delivery requirements across the hire machines?"
_state = {}


def profile():
    if "p" not in _state:
        _state["p"] = build_profile(S.snapshot("control"))
    return _state["p"]


def owner_tasks():
    return clean_owner_tasks(json.loads(TASKS_FILE.read_text()))


# ------------------------------------------------------------------------------------------------------------------------------------------------ the tasks file
def test_the_four_owner_tasks_compile_pass_the_unchanged_benchmark_gate_and_cover_the_goal():
    ot = owner_tasks()
    assert len(ot["tasks"]) == 4 and ot["model_tasks"] is False
    acc = []
    for t in ot["tasks"]:
        r = evaluate(Draft(t["question"], t["start_path"], t["criterion"], "owner", t["rationale"]), profile(), acc)            # default policy = the strict benchmark rule
        assert isinstance(r, Accepted) and r.tags == [], (t["question"], getattr(r, "reason", None))
        acc.append(r)
    ga = G.analyse(GOAL, profile(), RENTAL)
    assert sorted(ga["attribute_labels"]) == ["delivery and collection", "minimum hire", "refundable deposit"]
    assessed = [G.assess(ga, a, RENTAL) for a in acc]
    assert all(v["goal_relevant"] for v in assessed) and sorted(G.select(assessed, 4)) == [0, 1, 2, 3]
    assert G.coverage(ga, assessed)["status"] == "complete"
    truths = [a.compiled.truth for a in acc]
    assert len(truths[0]) == 4 and len(truths[1]) == 2 and len(truths[2]) == 4 and truths[3] == "Electric scissor lift 6 m"


def test_the_questions_name_the_fields_but_not_where_they_are_or_what_is_wrong():
    text = " ".join(t["question"] + " " + t["rationale"] for t in owner_tasks()["tasks"]).lower()
    import re
    for leak in (r"\blisting\b", r"detail page", r"only on", r"friction", r"info_absent", r"buried", r"hidden"):
        assert not re.search(leak, text), leak


def test_owner_tasks_are_validated_and_bounded():
    with pytest.raises(JobError):
        clean_owner_tasks({"tasks": []})
    with pytest.raises(JobError):
        clean_owner_tasks({"tasks": [{"question": "too short", "criterion": {"kind": "item_set"}}]})
    with pytest.raises(JobError):
        clean_owner_tasks({"tasks": [{"question": "a perfectly long enough question text", "criterion": {"nokind": 1}}]})
    assert clean_owner_tasks(None) is None


# ------------------------------------------------------------------------------------------------------------------------------------------------ grant binding
def test_the_grant_binds_the_exact_tasks_and_a_model_generated_run_is_unchanged(tmp_path):
    ot = owner_tasks()
    g = grant(owner_tasks=ot)
    assert g["tasks_sha256"] == canonical_hash(ot) and grant()["tasks_sha256"] == "" and g["grant_sha256"] != grant()["grant_sha256"]
    ap, run = approver(tmp_path, owner_tasks=ot)
    m = manifest(owner_tasks_sha256=canonical_hash(ot), owner_tasks_only=True)
    ap.decide(run, "taskgen", run.manifest_sha256(m), (run.write_artifact(f"manifests/taskgen-{run.manifest_sha256(m)[:16]}", m), m)[1], 0.0)
    for n, bad in enumerate((manifest(), manifest(owner_tasks_sha256="0" * 64))):                                           # no tasks / different tasks than approved
        ap2, run2 = approver(tmp_path / f"x{n}", owner_tasks=ot)
        with pytest.raises(GR.GrantRefused, match="owner-authored tasks"):
            ap2.decide(run2, "taskgen", run2.manifest_sha256(bad), bad, 0.0)
    ap3, run3 = approver(tmp_path / "y")                                                                                    # a grant without tasks refuses a manifest that carries some
    m3 = manifest(owner_tasks_sha256=canonical_hash(ot))
    with pytest.raises(GR.GrantRefused, match="owner-authored tasks"):
        ap3.decide(run3, "taskgen", run3.manifest_sha256(m3), m3, 0.0)


def test_the_plan_and_the_worker_options_carry_the_tasks_and_the_tasks_only_manifest_requests_nothing():
    ot = owner_tasks()
    opts = worker.live_options(S.snapshot("control"), GOAL, None, budget=2.0, cfg=ModelConfig(), owner_tasks=ot)
    assert opts["goals"]["tasks"] == ot["tasks"] and opts["owner_tasks_only"] is True and opts["owner_tasks_sha256"] == canonical_hash(ot)
    plain = worker.live_options(S.snapshot("control"), GOAL, None, budget=2.0, cfg=ModelConfig())
    assert "owner_tasks_only" not in plain and plain["goals"] == {"focus": GOAL}
    p = live_cli.plan(GOAL, None, False, ot)
    assert p["owner_tasks_sha256"] == canonical_hash(ot) and p["max_provider_requests"] == 0 and p["worst_case_stage_usd"] == 0
    q = live_cli.plan(GOAL, None, False, None)
    assert q["owner_tasks_sha256"] is None and q["max_provider_requests"] == 3, "the model-generated path stays the default"
    assert p["manifest_sha256"] != q["manifest_sha256"]
    mixed = live_cli.plan(GOAL, None, False, {**ot, "model_tasks": True})
    assert mixed["max_provider_requests"] == 3 and mixed["owner_tasks_sha256"] != p["owner_tasks_sha256"]


def test_owner_tasks_cannot_be_supplied_to_a_mock_job_or_through_the_client_api(tmp_path):
    m = JobManager(tmp_path / "live", spawn=lambda j: 0)
    with pytest.raises(JobError, match="live evaluations only"):
        m.create("o", "ironbark", GOAL, "mock", None, None, owner_tasks())
    from agent_readiness.live.api import NewJob
    assert "owner_tasks" not in NewJob.model_fields and NewJob.model_config.get("extra") == "forbid"


# ------------------------------------------------------------------------------------------------------------------------------------------------ pre-registration
def test_the_preregistration_records_the_hashes_and_the_expected_claim_but_is_not_investigator_input():
    text = PREREG.read_text()
    assert hashlib.sha256(TASKS_FILE.read_bytes()).hexdigest() in text and canonical_hash(owner_tasks()) in text and GOAL in text
    assert "info_absent_on_template" in text and "Success criteria" in text and "Not claimed" in text
    from agent_readiness.investigate.investigator import loop
    assert "preregistration" not in loop.SYSTEM.lower() and "IRONBARK-DIAGNOSTIC" not in loop.SYSTEM


# ------------------------------------------------------------------------------------------------------------------------------------------------ the recommendation on Ironbark
def test_the_listing_field_recommendation_targets_the_product_group_and_passes_its_static_recheck_on_ironbark():
    snap, p = S.snapshot("control"), profile()
    assert T.item_css(p, "/hire/category/cutting") == "a.chip" and T.item_css(p, "/hire/category/cutting", "delivery and collection") == "article.card", "navigation chips are the larger group, the products are the one that carries the field"
    patch, info = T.build("info_absent_on_template", {"label": "delivery and collection"}, p, snap)
    assert patch is not None and info["offered"] and info["recheck"]["passed"] and not info["recheck"]["failing"] and len(info["pages_changed"]) >= 10
    assert "/hire" in info["pages_changed"] and all(not pg.startswith("/hire/category/") or pg in info["pages_changed"] for pg in ("/hire/category/cutting",))
    assert info["inserted_bytes"] <= 20_000


def test_a_bundle_listing_is_left_out_because_one_machines_field_is_not_the_bundles(tmp_path):
    snap, p = S.snapshot("control"), profile()
    patch, info = T.build("info_absent_on_template", {"label": "delivery and collection"}, p, snap)
    assert info["excluded_bundle_listings"] == ["/kits"] and "/kits" not in info["pages_changed"] and all(o["pages"][0] != "/kits" for o in patch["ops"])
    assert "/hire" in info["pages_changed"] and "/hire/category/cutting" in info["pages_changed"], "single-item listings are still patched"
    kits = snap.get("/kits")
    assert kits is not None and "delivery and collection" not in kits.text().lower(), "the kit page itself is unchanged by the patch"
    ops = T.patch_for("info_absent_on_template", {"label": "delivery and collection"}, p)[0]["ops"]
    assert T._bundle_pages(snap, ops) == ["/kits"], "only the bundle listing is flagged; product cards and related-item lists are not"
    # a site whose listing items are single items is never flagged (site-1: workshop cards)
    from agent_readiness.investigate import zoo
    s1 = zoo.snapshot("site-1"); p1 = build_profile(s1)
    patch1, info1 = T.build("info_absent_on_template", {"label": "price"}, p1, s1)
    assert info1.get("offered") and "excluded_bundle_listings" not in info1


def test_the_static_recheck_fails_when_nothing_was_changed_and_names_the_listings():
    snap, p = S.snapshot("control"), profile()
    rc = T.static_recheck("info_absent_on_template", {"label": "delivery and collection"}, p, snap)
    assert rc["passed"] is False and "/hire" in rc["failing"] and "still missing" in rc["detail"]


# ------------------------------------------------------------------------------------------------------------------------------------------------ rehearsals (real Chromium, scripted agent)
def rehearse(tmp_path, behavior):
    opts = {"snapshot": S.snapshot("control"), "n_tasks": 4, "goals": {"focus": GOAL, "tasks": owner_tasks()["tasks"]}, "focus": GOAL, "rule_topup": False, "goal_binding": True, "first_page_policy": "tag",
            "goal_lexicon": RENTAL, "mock_behavior": behavior, "repeats": 1}
    run, pipe, ctx = flow.build(tmp_path, f"reh-{behavior}", "ironbark", mode="mock", options=opts)
    ctx.options["investigator_llm"] = mock_investigator.make(run)
    res = pipe.run(ctx)
    assert res.status == "done", (res.stage, res.error)
    return run


@pytest.mark.browser
def test_rehearsal_an_inefficient_scripted_agent_yields_a_promoted_finding_and_an_unvalidated_recommendation(tmp_path):
    run = rehearse(tmp_path, "thorough")
    rep = run.artifact("report-final")
    assert rep["outcome"] == "findings" and len(rep["findings"]) == 1
    f = rep["findings"][0]
    assert f["attribution"] == "website" and len(f["support"]) >= 2 and not f["structural_proof"], "promotion by the unchanged rule: at least two independent tasks"
    att = run.artifact("attribution")
    rows = att.get("trials") or att
    assert all(v["primary"] == "success" for v in rows.values()), "every trial passed: the cost shows as extra page views, not failures"
    assert sum(1 for v in rows.values() if v["signals"]["extra_page_views"] >= 2) >= 2
    rec = run.artifact("recommendations")
    assert rec["verified_finding_proposals"] and rec["verified_finding_proposals"][0]["recheck"]["passed"], rec["not_offered"]
    props = rep["proposals"]
    assert props and all(p["validation"] == "unvalidated" for p in props) and {p["basis"] for p in props} == {"verified_finding", "unverified_hypothesis"}
    assert [t["source"] for t in run.artifact("tasks-manifest")["tasks"]] == ["owner"] * 4
    first = __import__("agent_readiness.investigate.investigator.loop", fromlist=["x"]).first_user_message(__import__("agent_readiness.investigate.investigator.tools", fromlist=["x"]).Workspace(run), GOAL)
    for leak in ("info_absent_on_template", "detail-only", "listing cards", "refundable deposit < ", "Electric scissor lift 6 m"):
        assert leak not in first, f"the investigator's first message must not carry the expected diagnosis or an answer: {leak}"
    from agent_readiness.investigate import export as ex
    d = ex.export_run(run.dir)
    ex.check_clean(d)
    assert d["findings"] and d["hypotheses"] and d["proposals"]


@pytest.mark.browser
def test_rehearsal_a_scripted_agent_that_does_not_try_is_attributed_to_the_agent_and_nothing_is_promoted(tmp_path):
    run = rehearse(tmp_path, "stuck")
    rep = run.artifact("report-final")
    att = run.artifact("attribution")
    rows = att.get("trials") or att
    assert {v["primary"] for v in rows.values()} == {"agent"} and rep["findings"] == [] and rep["outcome"] != "findings"
    assert run.artifact("recommendations")["verified_finding_proposals"] == []


@pytest.mark.browser
def test_dev_provider_live_job_with_owner_tasks_only_makes_no_taskgen_request_labels_the_tasks_and_reports_honestly(tmp_path, monkeypatch, provider):
    monkeypatch.setenv("META_MODEL_API_KEY", KEY)
    prov, url = provider()
    m = JobManager(tmp_path / "live", live=settings(base_url=url))
    j = m.create("o", "ironbark", GOAL, "live", 2.0, None, owner_tasks())
    v = wait_for(lambda: (lambda x: x if x["state"] not in ("queued", "running") else None)(m.get(j["id"], "o")), 420)
    assert v["state"] == "completed", (v["error"], v["stop"])
    assert prov.calls["taskgen"] == 0 and not prov.taskgen_prompts, "owner-tasks-only generation sends no model request"
    from agent_readiness.investigate.run import InvestigationRun
    run = InvestigationRun(m.root / j["id"])
    art = run.artifact("owner-tasks")
    g = worker.read(m.root, j["id"])["grant"]
    assert art["sha256"] == g["tasks_sha256"] == canonical_hash(owner_tasks()) and "OWNER-AUTHORED" in art["provenance"]
    mans = [json.loads(f.read_text()) for f in (run.dir / "artifacts" / "manifests").glob("taskgen-*.json")]
    assert len(mans) == 1 and mans[0]["owner_tasks_sha256"] == g["tasks_sha256"] and mans[0]["max_requests"] == 0
    d = m.export(j["id"], "o")
    assert d["goal_coverage"]["owner_authored_selected"] == 4 and all(t["source"] == "owner" for t in d["tasks"])
    ins = d["insights"]
    assert ins["provenance"]["task_sources"] == {"owner": 4} and "owner-authored" in json.dumps(ins["provenance"]) or ins["provenance"]["task_sources"] == {"owner": 4}
    assert ins["suggestions"] == [] and ins["summary"].startswith("No friction was observed"), "the minimal-route agent shows no friction, so no friction-based suggestion"
    assert d["findings"] == [], "the dev provider's agent takes the minimal route, so there is no friction to find: an honest empty result"
    assert [a["stage"] for a in run.approvals()] == ["taskgen", "baseline_trials", "investigate"]
