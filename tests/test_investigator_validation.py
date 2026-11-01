"""Bounded claim validation for the investigator: invalid or unverifiable claim parameters are returned once with the checker's exact reason, a single correction is allowed per claim within the existing tool
budget, and the original claim, the feedback and the correction stay in the audit trail. Nothing is substituted, no checker is relaxed, the promotion rule is unchanged. Offline (scripted model)."""
import json

from agent_readiness.investigate.investigator.loop import SYSTEM, Step, investigate
from agent_readiness.investigate.llm import ScriptedClient

from .test_investigate_investigator import hyp, scripted_model, smooth, step, ws_for

BAD_K = dict(claim_kind="info_only_after_k_hops", k=1, label="price")


def first_obs(ws):
    return next(iter(ws.run.evidence.observations))


def bad_claim(ws):
    return hyp("Prices are only visible after 1 hop on the detail pages", [first_obs(ws)], **BAD_K)


def good_fix(ws, n=1):
    return hyp("The price is only on detail pages, not on the listing", [first_obs(ws)], claim_kind="info_absent_on_template", label="price", replaces=n)


def run(tmp_path, plan_fn, max_calls=6, scenario=None, sid="site-1", name="v"):
    ws = ws_for(tmp_path, *( [scenario] if scenario else []), sid, name) if scenario else ws_for(tmp_path, sid=sid, name=name)
    seen = []
    plan = plan_fn(ws, seen)
    llm = ScriptedClient(scripted_model(plan))
    return ws, investigate(ws, llm, max_calls=max_calls), llm, seen


def feedback_of(llm):
    for c in llm.calls:
        for m in c.messages:
            if m["role"] == "user" and m["content"].startswith('{"claim_validation"'):
                return json.loads(m["content"])
    return None


def test_an_invalid_parameter_is_returned_with_the_checkers_reason_and_one_correction_is_accepted_verified_and_promoted_by_the_unchanged_rule(tmp_path):
    ws, res, llm, _ = run(tmp_path, lambda ws, seen: [step("list_trials"), lambda last, req: step("finish", hyps=[bad_claim(ws)]), lambda last, req: step("finish", hyps=[good_fix(ws)])])
    fb = feedback_of(llm)
    assert fb and fb["claim_validation"][0]["claim_number"] == 1 and fb["claim_validation"][0]["result"] == "unverifiable" and "k` >= 2" in fb["claim_validation"][0]["reason"]
    assert fb["claim_validation"][0]["claim_kind"] == "info_only_after_k_hops" and fb["claim_validation"][0]["parameters"] == {"label": "price", "k": 1}
    assert res["finished"] and res["incomplete"] is None and res["model_requests"] == 3, "list_trials, the first finish and exactly one correction reply"
    a = res["claim_audit"]
    assert len(a) == 1 and a[0]["original"]["claim_kind"] == "info_only_after_k_hops" and a[0]["original"]["parameters"]["k"] == 1
    assert a[0]["feedback"]["result"] == "unverifiable" and a[0]["corrected"]["claim_kind"] == "info_absent_on_template" and a[0]["outcome"].startswith("corrected")
    store = ws.run.evidence
    assert [h.claim_kind for h in store.hypotheses.values()] == ["info_absent_on_template"], "only the corrected claim is stored; the original lives in the audit trail"
    assert len(store.findings) == 1 and res["verification"][0]["promotion"] == "promoted"


def test_a_failed_correction_keeps_the_original_claim_as_unverifiable_and_there_is_no_second_round(tmp_path):
    again = lambda ws: hyp("Prices are only visible after 1 hop on the detail pages", [first_obs(ws)], replaces=1, **BAD_K)
    ws, res, llm, _ = run(tmp_path, lambda ws, seen: [step("list_trials"), lambda last, req: step("finish", hyps=[bad_claim(ws)]), lambda last, req: step("finish", hyps=[again(ws)]),
                                                      lambda last, req: (_ for _ in ()).throw(AssertionError("a second correction round must never be requested"))])
    assert res["model_requests"] == 3 and res["finished"]
    a = res["claim_audit"][0]
    assert a["outcome"].startswith("correction_still_invalid") and a["corrected_feedback"]["result"] == "unverifiable"
    h = list(ws.run.evidence.hypotheses.values())
    assert len(h) == 1 and h[0].claim_kind == "info_only_after_k_hops" and h[0].params["k"] == 1 and h[0].verification.result == "unverifiable" and not ws.run.evidence.findings


def test_an_uncorrected_or_unmatched_reply_changes_nothing_and_extra_claims_are_rejected(tmp_path):
    other = lambda ws: hyp("A brand new idea after seeing the checker", [first_obs(ws)], prediction="if X, Y", proposed_change="do X")        # no `replaces`
    ws, res, llm, _ = run(tmp_path, lambda ws, seen: [step("list_trials"), lambda last, req: step("finish", hyps=[bad_claim(ws)]), lambda last, req: step("finish", hyps=[other(ws)])])
    assert res["claim_audit"][0]["outcome"].startswith("not_corrected") and res["claim_audit"][0]["corrected"] is None
    store = ws.run.evidence
    assert [h.claim_kind for h in store.hypotheses.values()] == ["info_only_after_k_hops"] and next(iter(store.hypotheses.values())).verification.result == "unverifiable"
    assert any("not a correction of a flagged claim" in r["reason"] for r in res["rejected_hypotheses"]) and not res["novel_changes"]
    ws2, res2, _, _ = run(tmp_path, lambda ws, seen: [step("list_trials"), lambda last, req: step("finish", hyps=[bad_claim(ws)]), step("page_text", path="/faq")], name="v2")
    assert res2["finished"] and res2["claim_audit"][0]["outcome"].startswith("not_corrected"), "a tool call during the correction round is not executed; the original stays unverifiable"
    assert res2["tool_calls"] == 1


def test_a_correction_may_restate_the_claim_as_an_open_ended_hypothesis_which_stays_unverified(tmp_path):
    restated = lambda ws: hyp("Agents must open every item to compare a field the cards omit", [first_obs(ws)], prediction="if cards showed it, page views would drop", proposed_change="show it on cards", replaces=1)
    ws, res, _, _ = run(tmp_path, lambda ws, seen: [step("list_trials"), lambda last, req: step("finish", hyps=[bad_claim(ws)]), lambda last, req: step("finish", hyps=[restated(ws)])])
    store = ws.run.evidence
    assert [h.tier for h in store.hypotheses.values()] == ["novel"] and not store.findings and res["claim_audit"][0]["outcome"].endswith("open-ended hypothesis")


def test_no_correction_round_when_the_tool_budget_is_spent_and_the_claim_is_kept_as_submitted(tmp_path):
    ws, res, llm, _ = run(tmp_path, lambda ws, seen: [lambda last, req: step("finish", hyps=[bad_claim(ws)])], max_calls=0)
    assert feedback_of(llm) is None and res["model_requests"] == 1 and res["claim_audit"] == []
    h = list(ws.run.evidence.hypotheses.values())
    assert len(h) == 1 and h[0].verification.result == "unverifiable"


def test_claims_the_checker_can_use_get_no_feedback_and_the_promotion_rule_is_unchanged(tmp_path):
    ok = lambda ws: hyp("The price is only on detail pages, not on the listing", [first_obs(ws)], claim_kind="info_absent_on_template", label="price")
    ws, res, llm, _ = run(tmp_path, lambda ws, seen: [step("list_trials"), lambda last, req: step("finish", hyps=[ok(ws)])])
    assert feedback_of(llm) is None and res["model_requests"] == 2 and res["claim_audit"] == []
    ws2, res2, llm2, _ = run(tmp_path, lambda ws, seen: [step("list_trials"), lambda last, req: step("finish", hyps=[bad_claim(ws)]), lambda last, req: step("finish", hyps=[good_fix(ws)])], name="v3")
    assert res2["verification"][0]["support"] >= 2 and res2["verification"][0]["promotion"] == "promoted"
    ws3 = ws_for(tmp_path, smooth, "site-1", "v4")                       # supported by the checker, but no trial shows a cost: stays below the promotion rule
    llm3 = ScriptedClient(scripted_model([step("list_trials"), lambda last, req: step("finish", hyps=[bad_claim(ws3)]), lambda last, req: step("finish", hyps=[good_fix(ws3)])]))
    res3 = investigate(ws3, llm3, max_calls=6)
    assert res3["verification"][0]["result"] == "supported" and res3["verification"][0]["promotion"].startswith("not promoted") and not ws3.run.evidence.findings


def test_the_prompt_asks_for_check_claim_before_finishing_and_states_the_k_rule_and_the_schema_requires_replaces():
    assert "BEFORE you call `finish`, call `check_claim`" in SYSTEM and "integer of at least 2" in SYSTEM and "you may correct it once" in SYSTEM
    s = Step.model_json_schema()["$defs"]["HypothesisOut"]
    assert "replaces" in s["properties"] and "replaces" in s["required"]


def test_the_feedback_and_every_prompt_stay_blind(tmp_path):
    from agent_readiness.investigate.zoo import sealed
    ws, res, llm, _ = run(tmp_path, lambda ws, seen: [step("list_trials"), lambda last, req: step("finish", hyps=[bad_claim(ws)]), lambda last, req: step("finish", hyps=[good_fix(ws)])])
    for c in llm.calls:
        sealed.assert_blind(json.dumps(c.messages))
