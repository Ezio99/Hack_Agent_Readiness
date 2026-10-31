"""Website Context Pack: an optional client briefing that guides task generation and the investigator, is saved with the run, is part of the approved scope, and is never evidence. Offline plus dev-provider real-path."""
import json

import pytest

from agent_readiness.investigate.inspect.profile import build_profile
from agent_readiness.investigate.llm.meta import reservation_bound_usd
from agent_readiness.investigate.taskgen import goal as G, propose
from agent_readiness.live import cli as live_cli, grant as GR, worker
from agent_readiness.live.jobs import JobError, JobManager, clean_context
from agent_readiness.live.lexicon import RENTAL
from agent_readiness.live.targets import CONTEXT_MAX, SAMPLE_CONTEXT, listing

from .test_goal_binding import GOAL, make_run, profile, response, stage
from .test_live_m1 import ENDPOINT, KEY, SNAP, approver, manifest, provider, settings, wait_for  # noqa: F401
from .test_live_smoke import smoke_settings  # noqa: F401

CTX = SAMPLE_CONTEXT["ironbark"]
FALSE_CTX = "Every cutting tool at Ironbark costs exactly $1 per day and is always available."


# ------------------------------------------------------------------------------------------------------------------------------------------------------------------ the field and the sample
def test_the_ironbark_sample_briefing_is_offered_bounded_and_clearly_a_briefing():
    ib = next(t for t in listing() if t["id"] == "ironbark")
    assert ib["sample_context"] == CTX and len(CTX) <= CONTEXT_MAX and "Marrickville" in CTX and "site4" not in CTX
    assert all("sample_context" not in t for t in listing() if t["id"] != "ironbark")


def test_context_is_cleaned_and_bounded_and_blank_means_none():
    assert clean_context(None) is None and clean_context("  \n ") is None
    assert clean_context("a  b\x00c\n\n  d") == "a bc\n\nd"
    assert len(clean_context("x" * CONTEXT_MAX)) == CONTEXT_MAX
    with pytest.raises(JobError) as e:
        clean_context("x" * (CONTEXT_MAX + 1))
    assert e.value.status == 422


# ------------------------------------------------------------------------------------------------------------------------------------------------------------------ it influences task generation and the investigator, as guidance
def test_context_reaches_the_goal_bound_prompts_with_a_rule_that_it_is_not_evidence():
    p = profile()
    with_ctx = propose.batch_requests(p, GOAL, True, CTX)
    without = propose.batch_requests(p, GOAL, True, None)
    for a, b in zip(with_ctx, without):
        ta, tb = a.messages[1]["content"], b.messages[1]["content"]
        assert "<client_context>" in ta and CTX in ta and "UNVERIFIED and NOT evidence about the website" in ta and "answerable from the website itself" in ta
        assert "<client_context>" not in tb and ta != tb and a.response_schema == b.response_schema
    assert propose.batch_requests(p, GOAL, False, CTX) == propose.batch_requests(p, GOAL, False, None), "without goal binding nothing changes (frozen paths are byte-identical)"


def test_the_investigator_prompt_carries_the_context_with_a_citation_rule(tmp_path):
    from agent_readiness.investigate.investigator.loop import first_user_message
    from agent_readiness.investigate.investigator.tools import Workspace
    from .test_investigate_investigator import ws_for
    ws = ws_for(tmp_path)
    plain, ctx = first_user_message(ws, GOAL), first_user_message(ws, GOAL, CTX)
    assert "<client_context>" not in plain and "<client_context>" in ctx and CTX in ctx and "the client context is never evidence" in ctx and ctx.startswith(plain.rstrip())


# ------------------------------------------------------------------------------------------------------------------------------------------------------------------ provenance boundaries
def test_a_false_context_claim_cannot_change_what_the_independent_gate_derives(tmp_path):
    from agent_readiness.investigate.taskgen.criteria import compile_criterion
    t = [{"question": "What is the per day hire rate listed on the page of the Petrol cut-off saw 350 mm?", "criterion": {"kind": "page_fact", "page": "/hire/petrol-cut-off-saw-350mm", "label": "per day"}, "goal_link": "price"}]
    run, err, _ = stage(tmp_path, [t, [], []], context=FALSE_CTX)
    rep = run.artifact("taskgen-report")
    assert len(rep["accepted"]) == 1
    truth = compile_criterion({"kind": "page_fact", "page": "/hire/petrol-cut-off-saw-350mm", "label": "per day"}, run.artifact("site-profile")).truth
    assert truth == "$110" and "$1 " not in json.dumps(run.artifact("taskgen-report")) and FALSE_CTX not in json.dumps(run.artifact("site-profile")), "answers come from the page, never from the briefing"
    assert FALSE_CTX not in json.dumps([o.summary for o in run.evidence.observations.values()]), "context is not an observation"


def test_the_context_is_kept_in_its_own_artifact_and_its_own_export_block_with_an_unverified_label(tmp_path):
    from agent_readiness.live.jobs import CONTEXT_LABEL
    assert "Unverified" in CONTEXT_LABEL and "not evidence" in CONTEXT_LABEL and "no finding rests on it" in CONTEXT_LABEL
    src = (__import__("pathlib").Path(worker.__file__)).read_text()
    assert 'run.write_artifact("client-context"' in src and "CONTEXT_LABEL" in src


# ------------------------------------------------------------------------------------------------------------------------------------------------------------------ scope: a different context is a different approval
def test_the_grant_and_every_manifest_bind_the_exact_context(tmp_path):
    g1, g2, g0 = GR.make_grant(job_id="live-aaaaaaaaaa", owner="sess-1", target_id="ironbark", goal=GOAL, budget_usd=2.0, model="muse-spark-1.3", endpoint=ENDPOINT, snapshot_sha256=SNAP, context=CTX), \
        GR.make_grant(job_id="live-aaaaaaaaaa", owner="sess-1", target_id="ironbark", goal=GOAL, budget_usd=2.0, model="muse-spark-1.3", endpoint=ENDPOINT, snapshot_sha256=SNAP, context=CTX + " "), \
        GR.make_grant(job_id="live-aaaaaaaaaa", owner="sess-1", target_id="ironbark", goal=GOAL, budget_usd=2.0, model="muse-spark-1.3", endpoint=ENDPOINT, snapshot_sha256=SNAP)
    assert g1["context_sha256"] != g2["context_sha256"] and g0["context_sha256"] == "" and len({g1["grant_sha256"], g2["grant_sha256"], g0["grant_sha256"]}) == 3
    with pytest.raises(GR.GrantRefused):
        GR.verify({**g1, "context_sha256": g2["context_sha256"]}, job_id="live-aaaaaaaaaa", owner="sess-1", run_id="live-aaaaaaaaaa")
    from .test_live_m1 import live_run
    for stage_name in ("taskgen", "investigate"):
        for ctx_sha, ok in ((g1["context_sha256"], True), (g2["context_sha256"], False), (None, False)):
            run = live_run(tmp_path / f"{stage_name}{ok}{ctx_sha and ctx_sha[:4]}")
            ap = GR.Approver(g1, job_id="live-aaaaaaaaaa", owner="sess-1", run_id="live-aaaaaaaaaa")
            m = manifest("taskgen", target_tasks=4, retries_per_request=0) if stage_name == "taskgen" else {"stage": "investigate", "model": "muse-spark-1.3", "endpoint": ENDPOINT + "/chat/completions", "run_cap_usd": 0.4, "per_request_cap_usd": 0.05, "retries_per_request": 1}
            if ctx_sha:
                m["client_context_sha256"] = ctx_sha
            if ok:
                ap.decide(run, stage_name, run.manifest_sha256(m), m, 0.0)
            else:
                with pytest.raises(GR.GrantRefused, match="client context"):
                    ap.decide(run, stage_name, run.manifest_sha256(m), m, 0.0)
                assert run.approvals() == []
    ap0 = GR.Approver(g0, job_id="live-aaaaaaaaaa", owner="sess-1", run_id="live-aaaaaaaaaa")
    run = live_run(tmp_path / "none")
    m = manifest("taskgen", target_tasks=4, retries_per_request=0, client_context_sha256=g1["context_sha256"])
    with pytest.raises(GR.GrantRefused):
        ap0.decide(run, "taskgen", run.manifest_sha256(m), m, 0.0)


def test_changing_the_context_changes_the_approval_manifest_hash_offline():
    a, b, c = live_cli.plan(GOAL), live_cli.plan(GOAL, CTX), live_cli.plan(GOAL, CTX + "!")
    assert len({a["manifest_sha256"], b["manifest_sha256"], c["manifest_sha256"]}) == 3 and b["client_context_sha256"] and a["client_context_sha256"] is None


def test_the_job_stores_the_cleaned_context_and_binds_it_into_its_grant(tmp_path, monkeypatch):
    monkeypatch.setenv("META_MODEL_API_KEY", KEY)
    m = JobManager(tmp_path / "live", spawn=lambda jid: 0, live=settings())
    j = m.create("o", "ironbark", GOAL, "live", 2.0, "  Hello   world \n\n  second line ")
    raw = worker.read(m.root, j["id"])
    assert raw["context"] == "Hello world\n\nsecond line" and raw["grant"]["context_sha256"] == GR.context_digest(raw["context"])
    assert j["client_context"]["text"] == raw["context"] and "Unverified" in j["client_context"]["label"] and j["client_context"]["sha256"] == raw["grant"]["context_sha256"]
    assert JobManager(tmp_path / "l2", spawn=lambda jid: 0, live=settings()).create("o", "ironbark", GOAL, "live", 2.0)["client_context"] is None


# ------------------------------------------------------------------------------------------------------------------------------------------------------------------ cost controls
def test_the_compact_summary_gives_comfortable_headroom_under_the_per_request_cap_even_with_a_full_context():
    p = profile()
    full = len(json.dumps(propose.site_summary(p), ensure_ascii=False))
    small = len(json.dumps(propose.site_summary(p, compact=True), ensure_ascii=False))
    assert small < full * 0.5, (small, full)
    big = "x" * CONTEXT_MAX
    for ctx in (None, CTX, big):
        res = [reservation_bound_usd(r) for r in propose.batch_requests(p, GOAL, True, ctx)]
        assert max(res) < 0.05 * 0.8 and sum(res) < 0.15 * 0.8, (ctx and len(ctx), res)
    p0 = live_cli.plan(GOAL, big)
    assert p0["max_provider_requests"] == 3 and p0["retries_per_request"] == 0 and p0["per_request_cap_usd"] == 0.05 and max(p0["per_request_reservation_usd"]) < 0.04


def test_compaction_keeps_the_names_and_paths_goal_tasks_need_and_does_not_touch_other_requests():
    p = profile()
    s = propose.site_summary(p, compact=True)
    items = {i["path"] for l in s["listings"] for i in l["items"]}
    assert {"/hire/wet-tile-saw-250mm", "/hire/petrol-cut-off-saw-350mm", "/hire/petrol-chainsaw-45cm"} <= items
    assert not any("/sort/" in l["listing"] for l in s["listings"]) and not any(propose.DATE_LABEL.match(k) for l in s["listings"] for k in l["fields_on_item_pages"])
    assert propose.site_summary(p) == propose.site_summary(p, compact=False), "the default summary is unchanged"


# ------------------------------------------------------------------------------------------------------------------------------------------------------------------ partial coverage is visible
def test_coverage_status_is_complete_partial_or_insufficient_with_explicit_reasons():
    p = profile()
    ga = G.analyse(GOAL, p, RENTAL)
    sel = [{"aspects_matched": ["price"], "entities_touched": ga["entity_items"], "goal_relevant": True}, {"aspects_matched": ["availability"], "entities_touched": ga["entity_items"], "goal_relevant": True}]
    partial = G.coverage(ga, sel)
    assert partial["status"] == "partial" and partial["passes"] and any("not verifiable as asked: ordering" in w for w in partial["partial_because"]) and partial["unverified_aspects"] == ["ordering"]
    complete = G.coverage({**ga, "limitation_details": [], "limitations": []}, sel)
    assert complete["status"] == "complete" and complete["partial_because"] == []
    thin = G.coverage({**ga, "limitation_details": [], "limitations": []}, [{"aspects_matched": ["price"], "entities_touched": ga["entity_items"][:1], "goal_relevant": True}, {"aspects_matched": ["availability"], "entities_touched": ga["entity_items"][:1], "goal_relevant": True}])
    assert thin["status"] == "partial" and thin["partial_because"] == ["entities not covered: 2 of 3"]
    unsup = G.coverage({**ga, "support": {**ga["support"], "price": {"supported": False}}, "limitation_details": [{"aspect": "price", "kind": "capture", "detail": "d"}]}, sel[1:])
    assert unsup["status"] == "partial" and unsup["unsupported_aspects"] == ["price"] and "aspect not expressible on the site: price" in unsup["partial_because"]
    assert G.coverage(ga, [])["status"] == "insufficient" and G.coverage(ga, sel[1:])["status"] == "insufficient", "none relevant, or a supportable aspect left uncovered"


# ------------------------------------------------------------------------------------------------------------------------------------------------------------------ real path (dev provider)
@pytest.mark.browser
def test_a_full_live_run_with_context_binds_approves_and_separates_it_end_to_end(tmp_path, monkeypatch, provider):
    monkeypatch.setenv("META_MODEL_API_KEY", KEY)
    prov, url = provider()
    m = JobManager(tmp_path / "live", live=settings(base_url=url))
    goal = "Can a shopper compare the hire price and availability of the two cheapest cutting tools?"
    j = m.create("o", "ironbark", goal, "live", 2.0, CTX)
    v = wait_for(lambda: (lambda x: x if x["state"] not in ("queued", "running") else None)(m.get(j["id"], "o")), 420)
    assert v["state"] == "completed", (v["error"], v["stop"])
    assert prov.taskgen_prompts and all("<client_context>" in p and "Marrickville" in p for p in prov.taskgen_prompts) and "<client_context>" in prov.investigator_prompts[0], "context reached both consumers"
    from agent_readiness.investigate.run import InvestigationRun
    run = InvestigationRun(m.root / j["id"])
    art = run.artifact("client-context")
    sha = v["grant"] and worker.read(m.root, j["id"])["grant"]["context_sha256"]
    assert art["text"] == CTX and art["sha256"] == sha and "Unverified" in art["provenance"]
    mans = [json.loads(f.read_text()) for f in (run.dir / "artifacts" / "manifests").glob("*.json")]
    assert {mm["stage"] for mm in mans if mm.get("client_context_sha256")} == {"taskgen", "investigate"} and all(mm["client_context_sha256"] == sha for mm in mans if mm.get("client_context_sha256"))
    assert [a["stage"] for a in run.approvals()] == ["taskgen", "baseline_trials", "investigate"]
    assert v["coverage"]["status"] == "partial" and v["coverage"]["unverified_aspects"] == ["ordering"] and v["coverage"]["partial_because"]
    d = m.export(j["id"], "o")
    assert d["client_context"]["text"] == CTX and "Unverified" in d["client_context"]["label"]
    body = json.dumps({k: d[k] for k in ("observations", "hypotheses", "findings", "proposals")})
    assert "Marrickville" not in body and "tradies" not in body, "nothing the investigation reports as observation, hypothesis, finding or proposal contains the briefing"
    assert v["spend"]["committed_usd"] <= 2.0


@pytest.mark.browser
def test_a_different_context_makes_a_different_job_with_its_own_grant(tmp_path, monkeypatch, provider):
    monkeypatch.setenv("META_MODEL_API_KEY", KEY)
    prov, url = provider()
    m = JobManager(tmp_path / "live", live=smoke_settings(base_url=url))
    a = m.create("o", "ironbark", GOAL, "live", 0.15, CTX)
    wait_for(lambda: (lambda x: x if x["state"] not in ("queued", "running") else None)(m.get(a["id"], "o")), 240)
    b = m.create("o", "ironbark", GOAL, "live", 0.15, CTX + " Also: we offer delivery.")
    wait_for(lambda: (lambda x: x if x["state"] not in ("queued", "running") else None)(m.get(b["id"], "o")), 240)
    ga, gb = (worker.read(m.root, i)["grant"] for i in (a["id"], b["id"]))
    assert ga["context_sha256"] != gb["context_sha256"] and ga["grant_sha256"] != gb["grant_sha256"]
    ha = [p.read_text() for p in (m.root / a["id"] / "artifacts" / "manifests").glob("taskgen-*.json")]
    hb = [p.read_text() for p in (m.root / b["id"] / "artifacts" / "manifests").glob("taskgen-*.json")]
    assert ha and hb and ha != hb
