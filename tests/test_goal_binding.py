"""Goal-bound task generation (after the Step A smoke test: 0 of 4 accepted tasks addressed the goal). Offline only: the real model's 12 proposals are replayed from a fixture; no provider is called."""
import json
from pathlib import Path

import pytest

from agent_readiness.exp2 import snapshot as S
from agent_readiness.investigate import flow
from agent_readiness.investigate.inspect.profile import build_profile
from agent_readiness.investigate.inspect.stage import run_inspect
from agent_readiness.investigate.llm import LLMRequest, ScriptedClient
from agent_readiness.investigate.pipeline import Context, Pipeline, Stage
from agent_readiness.investigate.run import InvestigationRun
from agent_readiness.investigate.taskgen import goal as G, propose
from agent_readiness.investigate.taskgen.gate import Draft, evaluate
from agent_readiness.investigate.taskgen.stage import taskgen_stage
from agent_readiness.live.lexicon import RENTAL

GOAL = "Can a shopper compare the hire price and availability of the two cheapest cutting tools?"
GOAL_OK = "Can a shopper compare the engine, power and fuel of the cutting tools?"
REAL = json.loads((Path(__file__).parent / "fixtures" / "step_a_real_proposals.json").read_text())["batches"]
_state = {}


def profile():
    if "p" not in _state:
        _state["p"] = build_profile(S.snapshot("control"))
    return _state["p"]


def crit(**kw):
    return {**{"kind": None, "page": None, "label": None, "target": None, "listing": None, "direction": None, "conditions": None}, **kw}


def response(tasks, goal=GOAL):
    return json.dumps({"goal_analysis": {"entities": ["cutting tools"], "attributes": ["price", "availability"], "comparisons": ["cheapest two"], "information_gaps": ["rates"]},
                       "tasks": [{"question": t["question"], "start_path": t.get("start_path", "/"), "criterion": crit(**t["criterion"]), "rationale": t.get("rationale", "r"), "goal_link": t.get("goal_link", "n/a")} for t in tasks]})


def make_run(tmp_path):
    run = InvestigationRun.create(tmp_path, "g", target="ironbark", mode="scripted", stages=flow.STAGES)
    Pipeline([Stage("inspect", lambda c: run_inspect(c, S.snapshot("control")))]).run(Context(run))
    return run


def stage(tmp_path, batches, goal=GOAL, bound=True, **opts):
    run = make_run(tmp_path)
    llm = ScriptedClient([response(b) if bound else json.dumps({"tasks": [{**t, "criterion": crit(**t["criterion"]), "start_path": t.get("start_path", "/"), "rationale": "r"} for t in b]}) for b in batches])
    ctx = Context(run, llm=llm, options={"goals": {"focus": goal}, "goal_binding": bound, "goal_lexicon": RENTAL, "rule_topup": False, "n_tasks": 4, **opts})
    try:
        taskgen_stage(ctx)
        err = None
    except ValueError as exc:
        err = str(exc)
    return run, err, llm


# ------------------------------------------------------------------------------------------------------------------------------------------------------------------ the real failure, replayed
def test_the_real_step_a_proposals_pass_the_gate_but_none_serves_the_goal():
    p, acc, rej = profile(), [], []
    for b in REAL:
        for d in b:
            r = evaluate(Draft(d["question"], d["start_path"], d["criterion"], "model", ""), p, acc)
            (acc if hasattr(r, "compiled") else rej).append(r)
    assert (len(acc), len(rej)) == (7, 5), "12 proposals: 5 rejected by the gate (as reported) and 7 accepted; the old stage then kept the first 4 and dropped 3 silently"
    ga = G.analyse(GOAL, p, RENTAL)
    verdicts = [G.assess(ga, a, RENTAL) for a in acc]
    assert [v["goal_relevant"] for v in verdicts] == [False] * 7, "the answerable-but-irrelevant tasks are exactly what a person found: 0 of 4 (and 0 of the 3 hidden ones)"
    hammer = next(v for v in verdicts if "availability page" in v["question"])
    assert hammer["aspects_matched"] == ["availability"] and hammer["entity_match"] is False, "right aspect, wrong entity (an electric hammer is not a cutting tool)"
    assert next(v for v in verdicts if "deposit" in v["question"])["aspects_matched"] == [], "a deposit is not a hire price"


def test_replaying_the_real_proposals_reports_the_limitation_accounts_for_all_twelve_and_substitutes_nothing(tmp_path):
    run, err, llm = stage(tmp_path, REAL)
    assert err and err.startswith("goal coverage insufficient: 0 goal-relevant verified tasks (need 4) out of 7 gate-accepted") and "No unrelated tasks were substituted" in err
    rep = run.artifact("taskgen-report")
    acc = rep["accounting"]
    assert acc["proposed"] == 12 and acc["rejected"] == 5 and acc["accepted_not_selected"] == 7 and acc["selected"] == 0 and acc["unaccounted"] == 0
    assert all(r["reason"] == "not goal-relevant" for r in rep["not_selected"]) and rep["rule_topup"] == 0 and rep["accepted"] == []
    assert not run.has_artifact("accepted-drafts") if hasattr(run, "has_artifact") else True
    gb = rep["goal_binding"]
    assert gb["relevant_tasks"] == 0 and gb["gate_accepted_tasks"] == 7
    assert any(l.startswith("price:") and "labelled price or rate fact" in l for l in gb["analysis"]["limitations"]) and any(l.startswith("ordering:") for l in gb["analysis"]["limitations"])
    assert gb["analysis"]["support"]["availability"]["supported"] is True and len(gb["analysis"]["entity_items"]) == 3


# ------------------------------------------------------------------------------------------------------------------------------------------------------------------ what the site can and cannot support for the exact goal
def test_for_the_exact_goal_the_site_supports_availability_of_three_cutting_tools_and_not_price():
    ga = G.analyse(GOAL, profile(), RENTAL)
    assert ga["asked_aspects"] == ["availability", "price"] and ga["entity_listings"] == ["/hire/category/cutting"] and ga["ordering_terms"] == ["cheapest", "two"]
    assert ga["entity_items"] == ["/hire/wet-tile-saw-250mm", "/hire/petrol-cut-off-saw-350mm", "/hire/petrol-chainsaw-45cm"]
    assert ga["support"]["price"] == {"supported": False, "labelled_facts_found": [], "pages_found": []} and len(ga["support"]["availability"]["pages_found"]) == 3


def test_goal_following_proposals_are_selected_relevant_but_only_three_exist_so_the_stage_reports_the_limit(tmp_path):
    ga = G.analyse(GOAL, profile(), RENTAL)
    tasks = [{"question": f"Find the live availability calendar for the {n} hire.", "criterion": {"kind": "reach_page", "target": i + "/availability"}, "goal_link": f"{n}: availability"} for i, n in
             zip(ga["entity_items"], ("Wet tile saw 250 mm", "Petrol cut-off saw 350 mm", "Petrol chainsaw 45 cm"))]
    run, err, _ = stage(tmp_path, [tasks, [], []])
    rep = run.artifact("taskgen-report")
    assert rep["goal_binding"]["relevant_tasks"] == 3 and rep["goal_binding"]["selected"] == 3 and rep["accounting"]["selected"] == 3 and rep["accounting"]["unaccounted"] == 0
    assert err and "3 goal-relevant verified tasks (need 4)" in err and "price:" in err, "three real tasks are reported as insufficient coverage and the missing price part is named; nothing unrelated fills the gap"


def test_a_goal_the_site_can_express_yields_four_relevant_tasks_ranked_ahead_of_earlier_unrelated_ones(tmp_path):
    from agent_readiness.live.devprovider import follow_goal
    p = profile()
    ga = G.analyse(GOAL_OK, p, RENTAL)
    assert "engine" in ga["attribute_labels"] and ga["limitations"] == [] and ga["asked_aspects"] == []
    _, related = follow_goal(GOAL_OK, p, 12)
    assert len(related) >= 4
    unrelated = [{"question": d["question"], "start_path": d["start_path"], "criterion": d["criterion"]} for d in REAL[0][:3]]
    run, err, _ = stage(tmp_path, [unrelated + related[:1], related[1:5], related[5:]], goal=GOAL_OK)
    assert err is None, err
    rep = run.artifact("taskgen-report")
    verdict = {a["question"]: a["goal_relevant"] for a in rep["goal_binding"]["assessments"]}
    assert len(rep["accepted"]) == 4 and all(verdict[a["question"]] for a in rep["accepted"]), "four goal-relevant tasks selected"
    assert not any("deposit" in a["question"] or "collection and return" in a["question"] for a in rep["accepted"]), "the unrelated tasks that arrived first (deposit, hire terms) are not selected"
    assert rep["goal_binding"]["relevant_tasks"] >= 4 and rep["accounting"]["unaccounted"] == 0 and rep["accounting"]["proposed"] == 3 + len(related)
    assert any(r["reason"] == "not goal-relevant" for r in rep["not_selected"]) and rep["rule_topup"] == 0


def test_relevance_is_judged_from_the_criterion_not_from_the_models_own_link(tmp_path):
    ga = G.analyse(GOAL, profile(), RENTAL)
    t = [{"question": "What is the refundable deposit for the Wet tile saw 250 mm?", "criterion": {"kind": "page_fact", "page": "/hire/wet-tile-saw-250mm", "label": "refundable deposit"}, "goal_link": "Wet tile saw: hire price (claimed)"}]
    run, err, _ = stage(tmp_path, [t, [], []])
    a = run.artifact("taskgen-report")["goal_binding"]["assessments"][0]
    assert a["goal_relevant"] is False and a["model_goal_link"] == "Wet tile saw: hire price (claimed)" and a["aspects_matched"] == []


def test_relevance_is_reported_separately_and_does_not_change_which_tasks_the_gate_accepts(tmp_path):
    run_b, _, _ = stage(tmp_path / "b", REAL, bound=True)
    run_u, _, _ = stage(tmp_path / "u", REAL, bound=False, goal_binding=False, rule_topup=False)
    rb, ru = run_b.artifact("taskgen-report"), run_u.artifact("taskgen-report")
    assert sorted(r["question"] for r in rb["rejected"]) == sorted(r["question"] for r in ru["rejected"]), "identical gate rejections with and without binding"
    assert rb["accounting"]["accepted_not_selected"] + rb["accounting"]["selected"] == 7 and len(ru["accepted"]) + len(ru["not_selected"]) == 7
    assert len(ru["accepted"]) == 4 and len(ru["not_selected"]) == 3, "the old behaviour: 3 gate-accepted tasks were cut by position, now at least reported"


# ------------------------------------------------------------------------------------------------------------------------------------------------------------------ the prompt and schema
def test_the_goal_is_a_binding_objective_in_the_prompt_and_the_schema_demands_a_decomposition_first():
    reqs = propose.batch_requests(profile(), GOAL, True)
    assert len(reqs) == 3 and all(r.purpose == "taskgen-goal" for r in reqs)
    text = reqs[0].messages[1]["content"]
    for must in (GOAL, "EVALUATION GOAL (binding)", "goal_analysis", "entities", "information_gaps", "goal_link", "Do NOT propose generic catalogue trivia", "propose fewer tasks rather than unrelated ones"):
        assert must in text, must
    props = reqs[0].response_schema["properties"]
    assert list(props)[0] == "goal_analysis" and "goal_link" in json.dumps(reqs[0].response_schema)
    assert [r.messages[1]["content"] for r in reqs][0] != [r.messages[1]["content"] for r in reqs][1], "three goal-focused angles"


def test_without_goal_binding_requests_are_byte_identical_to_before():
    plain = propose.batch_requests(profile(), GOAL)
    assert plain == propose.batch_requests(profile(), GOAL, False) and all(r.purpose == "taskgen" and "goal_analysis" not in json.dumps(r.response_schema) for r in plain)
    assert propose.batch_requests(profile(), None, True) == propose.batch_requests(profile(), None, False), "no goal: nothing to bind"


def test_the_approval_manifest_binds_the_goal_bound_requests(tmp_path):
    run = make_run(tmp_path)
    opts = {"goals": {"focus": GOAL}, "goal_binding": True, "goal_lexicon": RENTAL, "n_tasks": 4}
    m1 = flow.taskgen_manifest(Context(run, options=opts))
    m0 = flow.taskgen_manifest(Context(run, options={**opts, "goal_binding": False}))
    assert m1["goal_binding"] is True and "goal_binding" not in m0 and m1["batch_request_sha256"] != m0["batch_request_sha256"]
