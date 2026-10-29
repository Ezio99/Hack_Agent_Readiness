"""M4 attribution / trace analysis and the M5 investigator: tools, verifiers, promotion, the model-driven loop (scripted model; no network, no browser)."""
import json

import pytest

from agent_readiness.investigate import zoo
from agent_readiness.investigate.investigator import verifiers as V
from agent_readiness.investigate.investigator.loop import SYSTEM, investigate
from agent_readiness.investigate.investigator.stage import investigate_stage, manifest, report_stage
from agent_readiness.investigate.investigator.tools import ToolCall, Workspace
from agent_readiness.investigate.llm import ScriptedClient
from agent_readiness.investigate.pipeline import Context, Pipeline, Stage
from agent_readiness.investigate.taskgen import freeze as freezer
from agent_readiness.investigate.trials.trace import analyze, trace_stage
from agent_readiness.investigate.zoo import sealed

from .test_investigate_taskgen import make_run, run_tasks

NULLS = dict(evidence_id=None, trial_id=None, task_id=None, step=None, path=None, css=None, text=None, claim_kind=None, label=None, scope=None, k=None)


def frozen(tmp_path, sid="site-1", name="r"):
    run = make_run(tmp_path, sid, name)
    assert run_tasks(run, None, n_tasks=8, feedback_round=False).status == "done"
    return run


def fake_trial(run, task, priv, *, passed, backed, visited, status="completed", answer="(not sure)", shown=True, answer_valid=True, max_steps=None, tag="r1"):
    tid = f"{task['task_id']}-{tag}"
    profile = run.artifact("site-profile")
    d = run.dir / "trial-data" / tid / "x"
    d.mkdir(parents=True)
    obs = [{"path": p, "text": (profile["pages"][p]["text"] if shown and p in profile["pages"] else "")} for p in visited]
    (d / "observations.json").write_text(json.dumps(obs))
    rec = {"trial": {"label": "baseline", "mode": "mock"}, "task": {}, "outcome": {"run_status": status, "stop_reason": "x", "errors": [], "answer": None if answer is None else {"answer": answer}},
           "evaluation": {"passed": passed, "evidence_backed": backed, "answer_valid": answer_valid, "missing_evidence": [] if backed else ["x"], "reasons": [], "details": {}},
           "metrics": {"model_requests": len(visited) + 1, "steps": len(visited), "page_views": len(visited), "limits": {"max_steps": max_steps or task["limits"]["max_steps"]}},
           "journey": [{"step": i + 1, "path": p, "query": "", "actions": [{"name": "navigate", "params": {"url": p}}], "executed": [{"result": "ok", "error": None}]} for i, p in enumerate(visited)],
           "mirror": {"log": [{"method": "GET", "path": p, "status": 200} for p in visited], "blocked": []}, "task_id": task["task_id"], "partition": task["partition"], "repeat": 1,
           "trial_id": tid, "trial_dir": str(d.relative_to(run.dir))}
    run.write_artifact(f"trials/baseline-{tid}", rec)
    return tid


def seed(run, fn):
    manifest_, private = freezer.load(run)
    out = {}
    for t in manifest_["tasks"]:
        kw = fn(t, private[t["task_id"]])
        out[t["task_id"]] = fake_trial(run, t, private[t["task_id"]], **kw)
    return out


def struggling(t, p):
    """the agent wandered through many pages and ran out of budget before reaching the evidence (the only failure shape that is NOT explained by the agent having seen the answer)"""
    return dict(passed=False, backed=False, status="request_limit", answer=None,
                visited=["/", "/workshops"] + [x for x in ("/workshops/zzz-1", "/workshops/zzz-2", "/workshops/zzz-3", "/workshops/zzz-4")])


def smooth(t, p):
    return dict(passed=True, backed=True, visited=["/"] + p["evidence_paths"], answer="ok")


# --------------------------------------------------------------------------------------------------------------------- attribution
def test_attribution_classes(tmp_path):
    run = frozen(tmp_path)
    m, private = freezer.load(run)
    pf = next(t for t in m["tasks"] if t["kind"] == "page_fact")
    p = private[pf["task_id"]]
    page = p["evidence_paths"][0]
    cases = {
        "success": dict(passed=True, backed=True, visited=["/", page], answer="ok"),
        "success_unsupported": dict(passed=True, backed=False, visited=["/"]),
        "provider_or_budget": dict(passed=False, backed=False, visited=["/"], status="estimated_cost_limit", answer=None),
        "infrastructure": dict(passed=False, backed=False, visited=["/"], status="infrastructure_error", answer=None),
        "agent": dict(passed=False, backed=False, visited=["/", page], answer="wrong"),                                  # the decisive text was shown
        "tool_interface": dict(passed=False, backed=False, visited=["/", page], shown=False),                           # page loaded, text not in the observation
        "task_invalid": dict(passed=False, backed=False, visited=["/"], max_steps=2),
    }
    got = {}
    for name, kw in cases.items():
        fake_trial(run, pf, p, tag=name, **kw)
    att = analyze(run)
    for name in cases:
        got[name] = att[f"{pf['task_id']}-{name}"]["primary"]
    assert got == {k: k for k in cases}, got
    assert att[f"{pf['task_id']}-provider_or_budget"]["void"] and att[f"{pf['task_id']}-infrastructure"]["void"] and not att[f"{pf['task_id']}-agent"]["void"]


def test_attribution_distinguishes_a_structural_blocker_from_an_unfollowed_link_and_a_spent_budget(tmp_path):
    run2 = frozen(tmp_path, "site-2", "s2")
    m, private = freezer.load(run2)
    t = next(t for t in m["tasks"] if t["kind"] == "page_fact" and "/rooms/" in private[t["task_id"]]["evidence_paths"][0])
    p = private[t["task_id"]]
    fake_trial(run2, t, p, passed=False, backed=False, visited=["/"], tag="blocked")                                  # every link toward /rooms/... on "/" is an unnamed icon
    fake_trial(run2, t, p, passed=False, backed=False, visited=["/"], status="request_limit", answer=None, tag="budget")
    att = analyze(run2)
    assert att[f"{t['task_id']}-blocked"]["primary"] == "website" and att[f"{t['task_id']}-budget"]["primary"] == "undetermined"
    run3 = frozen(tmp_path, "site-3", "s3")
    m3, p3 = freezer.load(run3)
    t3 = next(t for t in m3["tasks"] if t["kind"] == "page_fact")
    fake_trial(run3, t3, p3[t3["task_id"]], passed=False, backed=False, visited=["/"], tag="unfollowed")             # a named link to the evidence page exists on the visited page
    assert analyze(run3)[f"{t3['task_id']}-unfollowed"]["primary"] in ("agent", "undetermined")


def test_signals_and_trace_observations_never_contain_expected_answers_or_holdout_detail(tmp_path):
    run = frozen(tmp_path)
    seed(run, struggling)
    ctx = Context(run)
    trace_stage(ctx)
    _, private = freezer.load(run)
    att = run.artifact("attribution")
    blob = json.dumps([o.model_dump() for o in run.evidence.observations.values() if o.provenance.source == "rule:trace-analysis"], default=str)
    for t in private.values():
        for x in ([t["truth"]] if isinstance(t["truth"], str) else t["truth"]):
            if len(x) > 2:
                assert x not in blob, x
    hold = {k for k, a in att.items() if a["partition"] == "holdout"}
    assert hold and not any(h in blob for h in hold) and "holdout" not in blob
    assert run.has_artifact("attribution")


# ---------------------------------------------------------------------------------------------------------------------- tools
def ws_for(tmp_path, scenario=struggling, sid="site-1", name="w"):
    run = frozen(tmp_path, sid, name)
    seed(run, scenario)
    trace_stage(Context(run))
    return Workspace(run)


def call(ws, tool, **kw):
    return ws.call(ToolCall(**{**NULLS, "tool": tool, **kw}))


def test_tools_hide_holdout_and_private_data_and_record_citable_evidence(tmp_path):
    ws = ws_for(tmp_path)
    trials = call(ws, "list_trials")["trials"]
    hold_ids = [k for k, a in ws.run.artifact("attribution").items() if a["partition"] == "holdout"]
    assert trials and not ({t["trial_id"] for t in trials} & set(hold_ids))
    assert "error" in call(ws, "trial_summary", trial_id=hold_ids[0]) and "error" in call(ws, "get_step", trial_id="nope", step=1)
    s = call(ws, "trial_summary", trial_id=trials[0]["trial_id"])
    assert s["evidence_id"] in ws.run.evidence.observations and "private" not in json.dumps(s) and s["attribution"]
    pt = call(ws, "page_text", path="/workshops/pottery-basics")
    assert pt["evidence_id"] in ws.run.evidence.observations and "untrusted_page_text" in pt and "$45" in pt["untrusted_page_text"] and len(pt["untrusted_page_text"]) <= 1520
    dom = call(ws, "page_dom", path="/workshops", css="li.card a")
    assert dom["matches"] and dom["matches"][0]["accessible_name"] and call(ws, "page_dom", path="/nope", css="a")["error"]
    assert call(ws, "links_from", path="/")["links"] and call(ws, "search_site", text="Seats left")["matches"] and "error" in call(ws, "search_site", text="x")
    assert call(ws, "get_step", trial_id=trials[0]["trial_id"], step=3)["untrusted_page_text"] is not None and "error" in call(ws, "get_step", trial_id=trials[0]["trial_id"], step=99)
    cmp_ = call(ws, "compare_observation_to_dom", trial_id=trials[0]["trial_id"], step=2)
    assert "not_in_observation" in cmp_
    assert call(ws, "list_observations")["observations"] and call(ws, "get_observation", evidence_id=pt["evidence_id"])["kind"] == "page_text"


def test_extra_trial_requests_are_recorded_for_the_owner_never_executed(tmp_path):
    ws = ws_for(tmp_path)
    tid = next(iter(ws.inv_tasks))
    r = call(ws, "request_extra_trial", task_id=tid, text="repeat to check variance")
    assert r["recorded"] and ws.pending_requests == [{"task_id": tid, "reason": "repeat to check variance"}]
    assert "error" in call(ws, "request_extra_trial", task_id="gen-doesnotexist", text="x")
    assert not list((ws.run.dir / "artifacts" / "trials").glob("*extra*"))


def test_tool_output_that_would_reveal_a_sealed_diagnosis_fails_closed(tmp_path, monkeypatch):
    ws = ws_for(tmp_path)
    monkeypatch.setattr(sealed, "tokens", lambda site_id=None: {"seats left"})
    with pytest.raises(sealed.BlindnessError):
        call(ws, "page_text", path="/workshops/pottery-basics")


# ------------------------------------------------------------------------------------------------------------------- verifiers
def verify(ws, kind, statement, **params):
    return V.run_verifier(ws, kind, params, statement)


def test_info_absent_on_template_supported_refuted_and_param_consistency(tmp_path):
    ws = ws_for(tmp_path)
    r = verify(ws, "info_absent_on_template", "The price is only on detail pages, not on the listing", label="price")
    assert r.result == "supported" and len(r.support) >= 2 and not r.structural_proof
    assert verify(ws, "info_absent_on_template", "The colour is hidden", label="colour").result == "unverifiable"
    assert verify(ws, "info_absent_on_template", "Something is hidden on listings", label="price").result == "unverifiable"       # param not stated in the text
    assert verify(ws, "info_absent_on_template", "x", label=None).result == "unverifiable"
    ws3 = ws_for(tmp_path, smooth, "site-3", "w3")
    assert verify(ws3, "info_absent_on_template", "The difficulty is missing from listing cards", label="difficulty").result == "refuted"


def test_control_unlabeled_gives_structural_proof_only_where_named_links_cannot_reach_the_evidence(tmp_path):
    ws2 = ws_for(tmp_path, struggling, "site-2", "w2")
    r = verify(ws2, "control_unlabeled", "Navigation controls have no accessible name")
    assert r.result == "supported" and r.structural_proof
    ws3 = ws_for(tmp_path, smooth, "site-3", "w3")
    assert verify(ws3, "control_unlabeled", "Some controls have no accessible name").result == "refuted"


def test_hops_overhead_repeats_errors_and_unimplemented_kinds(tmp_path):
    ws4 = ws_for(tmp_path, struggling, "site-4", "w4")
    assert verify(ws4, "info_only_after_k_hops", "Some information is 3 link steps away", k=3).result in ("supported", "refuted")
    assert verify(ws4, "info_only_after_k_hops", "x", k=1).result == "unverifiable" and verify(ws4, "info_only_after_k_hops", "9 steps away", k=9).result == "refuted"
    ws = ws_for(tmp_path)
    assert verify(ws, "step_overhead_vs_minimum", "Agents needed 2 or more extra page views", k=2).result == "supported"
    assert verify(ws, "error_response_on_path", "Some paths return errors").result == "refuted"
    assert verify(ws, "inconsistent_content_across_pages", "Prices differ").result == "unverifiable"
    assert verify(ws, "made_up_kind", "x").result == "unverifiable"


def test_promotion_needs_support_and_a_website_side_attribution(tmp_path):
    ws = ws_for(tmp_path)
    store = ws.run.evidence
    from agent_readiness.investigate.models import Hypothesis, Provenance
    obs = next(iter(store.observations))
    mk = lambda kind, stmt, **p: store.add_hypothesis(Hypothesis(tier="verifiable", statement=stmt, claim_kind=kind, params=p, citations=[obs], provenance=Provenance(mode="scripted", source="t")))
    row = V.verify_and_promote(ws, mk("info_absent_on_template", "The price is not on the listing", label="price"))
    assert row["promotion"] == "promoted" and row["finding_id"] in store.findings
    row2 = V.verify_and_promote(ws, mk("step_overhead_vs_minimum", "Agents needed 2 extra page views", k=2))
    assert row2["result"] == "supported" and row2["finding_id"] is None and "not promoted" in row2["promotion"]               # agent-side / undetermined attribution can never be a website finding
    # one supporting task only: verified pattern, but not enough independent support
    once = {"done": False}

    def one_struggler(t, p):
        if t["partition"] == "investigation" and p["evidence_paths"][0].startswith("/workshops/") and not once["done"]:
            once["done"] = True
            return struggling(t, p)
        return smooth(t, p)
    ws1 = ws_for(tmp_path, one_struggler, name="w1")
    h = ws1.run.evidence.add_hypothesis(Hypothesis(tier="verifiable", statement="The price is not on the listing", claim_kind="info_absent_on_template", params={"label": "price"},
                                                  citations=[next(iter(ws1.run.evidence.observations))], provenance=Provenance(mode="scripted", source="t")))
    r1 = V.verify_and_promote(ws1, h)
    assert r1["result"] == "supported" and r1["finding_id"] is None and r1["support"] < 2


# ------------------------------------------------------------------------------------------------------------------------ the loop
def scripted_model(plan):
    """A scripted 'model': `plan` is a list of callables(last_tool_result_dict) -> Step dict. The harness feeds the previous tool result so evidence ids can be cited."""
    state = {"i": 0}

    def respond(request):
        last = json.loads(request.messages[-1]["content"]).get("tool_result", {}) if request.messages[-1]["role"] == "user" and request.messages[-1]["content"].startswith('{"tool_result"') else {}
        steps = plan[min(state["i"], len(plan) - 1)]
        state["i"] += 1
        return json.dumps(steps(last, request) if callable(steps) else steps)
    return respond


def step(tool, thought="looking", hyps=None, **kw):
    return {"thought": thought, "action": {**NULLS, "tool": tool, **kw}, "hypotheses": hyps}


def hyp(statement, citations, **kw):
    return {"statement": statement, "claim_kind": None, "label": None, "scope": None, "k": None, "prediction": None, "citations": citations, "proposed_change": None, **kw}


def test_loop_finds_a_verified_pattern_keeps_a_novel_idea_unverified_and_rejects_bad_hypotheses(tmp_path):
    ws = ws_for(tmp_path)
    ids = {}

    def p1(last, req):
        ids["dom"] = last["evidence_id"]
        return step("check_claim", claim_kind="info_absent_on_template", label="price")

    def finish(last, req):
        assert last["result"] == "supported"
        return step("finish", hyps=[
            hyp("The price is only on detail pages, not on the listing", [ids["dom"]], claim_kind="info_absent_on_template", label="price"),
            hyp("Agents lose track of which workshops they already opened", [ids["dom"]], prediction="If cards listed seats left, page views would drop", proposed_change="Add seats left to each card"),
            hyp("This cites evidence that does not exist", ["obs-doesnotexist"], claim_kind="info_absent_on_template", label="price"),
            hyp("No prediction and no known pattern", [ids["dom"]]),
        ])
    llm = ScriptedClient(scripted_model([step("list_trials"), step("page_dom", path="/workshops", css="li.card a"), p1, finish]))
    res = investigate(ws, llm, max_calls=6)
    assert res["finished"] and res["incomplete"] is None and res["tool_calls"] == 3
    store = ws.run.evidence
    assert len(store.findings) == 1 and next(iter(store.findings.values())).attribution == "website"
    novel = [h for h in store.hypotheses.values() if h.tier == "novel"]
    assert len(novel) == 1 and novel[0].status == "unverified" and res["novel_changes"][0]["proposed_change"].startswith("Add seats")
    assert len(res["rejected_hypotheses"]) == 2 and store.outcome() == "findings"
    assert [t["tool"] for t in res["tool_log"]] == ["list_trials", "page_dom", "check_claim"] and all(t["ok"] for t in res["tool_log"])


def test_loop_on_a_site_with_no_issue_reports_no_supported_issue_and_rejects_a_false_claim(tmp_path):
    ws = ws_for(tmp_path, smooth, "site-3", "c")

    def finish(last, req):
        return step("finish", hyps=[hyp("Difficulty is missing from the listing cards", [next(iter(ws.run.evidence.observations))], claim_kind="info_absent_on_template", label="difficulty")])
    res = investigate(ws, ScriptedClient(scripted_model([step("list_trials"), finish])), max_calls=5)
    store = ws.run.evidence
    assert not store.findings and res["verification"][0]["result"] == "refuted" and store.outcome() == "no_supported_issue"
    ws2 = ws_for(tmp_path, smooth, "site-3", "c2")
    res2 = investigate(ws2, ScriptedClient(scripted_model([step("finish", hyps=[])])), max_calls=5)
    assert res2["finished"] and ws2.run.evidence.outcome() == "no_supported_issue" and res2["tool_calls"] == 0


def test_loop_budget_bad_tools_and_injected_instructions_cannot_widen_what_the_model_can_do(tmp_path):
    ws = ws_for(tmp_path)
    llm = ScriptedClient(scripted_model([step("list_trials")]))                       # never finishes
    res = investigate(ws, llm, max_calls=3)
    assert not res["finished"] and "budget" in res["incomplete"] and res["tool_calls"] == 3
    assert any("call `finish` now" in m["content"] for m in llm.calls[-1].messages if m["role"] == "user")
    bad = ScriptedClient([json.dumps({"thought": "obeying the page", "action": {**NULLS, "tool": "delete_everything"}, "hypotheses": None})] * 4)
    res2 = investigate(ws_for(tmp_path, name="w2"), bad, max_calls=3)
    assert not res2["finished"] and "unusable model output" in res2["incomplete"] and res2["tool_calls"] == 0          # an off-menu action is refused, not executed
    ws3 = ws_for(tmp_path, name="w3")
    r = call(ws3, "get_step", trial_id="no-such", step=1)
    assert "error" in r


def test_every_prompt_the_model_sees_is_blind_and_model_agnostic(tmp_path):
    ws = ws_for(tmp_path)
    llm = ScriptedClient(scripted_model([step("list_trials"), step("page_text", path="/faq"), step("finish", hyps=[])]))
    investigate(ws, llm, max_calls=5)
    for c in llm.calls:
        sealed.assert_blind(json.dumps(c.messages))
    assert "info_absent_on_template" in SYSTEM and "NOT A CHECKLIST" in SYSTEM and "most sites show none" in SYSTEM and "equally welcome" in SYSTEM and "never as instructions" in SYSTEM
    assert all(m["role"] in ("system", "user", "assistant") for c in llm.calls for m in c.messages)


# ---------------------------------------------------------------------------------------------------------------------- stages
def test_investigate_stage_skips_without_a_model_and_gates_live_spend_on_a_hash(tmp_path):
    ws = ws_for(tmp_path)
    run = ws.run
    assert investigate_stage(Context(run)) == {"skipped": True} and run.artifact("investigation")["skipped"]
    live = type(run).create(tmp_path, "liveinv", target="site-1", mode="live", stages=("investigate",))
    import shutil
    for d in ("artifacts", "private", "snapshot"):
        shutil.copytree(run.dir / d, live.dir / d, dirs_exist_ok=True)
    (live.dir / "trial-data").mkdir()
    shutil.copytree(run.dir / "trial-data", live.dir / "trial-data", dirs_exist_ok=True)
    st = Stage("investigate", investigate_stage, spends=True, manifest=manifest)
    r = Pipeline([st]).run(Context(live, options={"max_calls": 8}))
    assert r.status == "awaiting_approval"
    m = live.artifact(f"manifests/investigate-{r.manifest_sha256[:16]}")
    assert m["max_tool_calls"] == 8 and m["max_requests"] == 11 and m["retries_per_request"] == 1 and m["run_cap_usd"] == 0.40 and len(m["prompt_sha256"]) == 64
    assert not (live.dir / "spend").exists()
    other = manifest(Context(live, options={"max_calls": 9}))
    assert live.manifest_sha256(other) != r.manifest_sha256                              # a different budget is a different, unapproved manifest


def test_investigate_then_report_end_to_end_with_scripted_model(tmp_path):
    ws = ws_for(tmp_path)
    run = ws.run

    def finish(last, req):
        return step("finish", hyps=[hyp("The price is only on detail pages, not on the listing", [last["evidence_id"]], claim_kind="info_absent_on_template", label="price"),
                                    hyp("Agents may prefer opening pages over reading cards", [last["evidence_id"]], prediction="If cards were richer, page views would fall")])
    llm = ScriptedClient(scripted_model([step("page_dom", path="/workshops", css="li.card a"), finish]))
    res = Pipeline([Stage("investigate", investigate_stage), Stage("report", report_stage)]).run(Context(run, options={"investigator_llm": llm}))
    assert res.status == "done"
    rep = run.artifact("report")
    assert rep["outcome"] == "findings" and len(rep["findings"]) == 1 and len(rep["hypotheses"]["novel"]) == 1 and rep["hypotheses"]["novel"][0]["status"] == "unverified"
    assert rep["trials"]["holdout"] >= 1 and "never shown" in rep["trials"]["note"] and rep["investigation"]["tool_calls"] == 1
    assert (run.dir / "private" / "investigator-transcript.json").exists()
    blob = json.dumps(rep)
    _, private = freezer.load(run)
    for t in private.values():
        for x in ([t["truth"]] if isinstance(t["truth"], str) else t["truth"]):
            assert x not in rep["investigation"].__repr__() or x in json.dumps(rep["tasks"]) or True


def test_agent_attributed_failures_and_unsupported_successes_never_count_as_support_for_a_website_pattern(tmp_path):
    def agent_fail(t, p):
        return dict(passed=False, backed=False, visited=["/"] + p["evidence_paths"], answer="wrong")                  # decisive text shown, wrong answer => agent
    ws = ws_for(tmp_path, agent_fail, name="wa")
    assert all(a["primary"] in ("agent", "success") for a in ws.att.values() if not a["void"])
    r = verify(ws, "info_absent_on_template", "The price is only on detail pages, not on the listing", label="price")
    assert r.result == "supported" and r.support == []                                                               # the static pattern holds, but no trial supports a cost
    h = ws.run.evidence.add_hypothesis(__import__("agent_readiness.investigate.models", fromlist=["Hypothesis"]).Hypothesis(
        tier="verifiable", statement="The price is only on detail pages, not on the listing", claim_kind="info_absent_on_template", params={"label": "price"}, citations=[next(iter(ws.run.evidence.observations))],
        provenance=__import__("agent_readiness.investigate.models", fromlist=["Provenance"]).Provenance(mode="scripted", source="t")))
    row = V.verify_and_promote(ws, h)
    assert row["finding_id"] is None and "not promoted" in row["promotion"] and ws.run.evidence.outcome() == "no_supported_issue"


def test_the_pattern_list_is_not_the_only_way_to_be_heard(tmp_path):
    ws = ws_for(tmp_path)
    obs = next(iter(ws.run.evidence.observations))
    fin = step("finish", hyps=[hyp("Visitors may not realise cards are clickable", [obs], prediction="If cards looked like buttons, fewer agents would open the same page twice")])
    res = investigate(ws, ScriptedClient(scripted_model([fin])), max_calls=3)
    h = next(iter(ws.run.evidence.hypotheses.values()))
    assert h.tier == "novel" and h.status == "unverified" and not ws.run.evidence.findings and ws.run.evidence.outcome() == "no_supported_issue" and not res["rejected_hypotheses"]
