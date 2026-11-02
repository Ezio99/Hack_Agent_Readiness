"""Lifecycle M2b: ranked_subset and either_of. Offline and free.

The shared engine is not modified (pinned in test_taskeval_v2.py); these tests prove the new kinds compile, are answered identically by the
independent record oracle, are refused when ill-posed (ties, degenerate filters), grade under the unchanged grader v1 and under grader v2 with a
key built by the same extractors, and that the replica gate used for them behaves exactly like gate v1 on existing kinds."""
import json

import pytest

from agent_readiness.framework.site import get
from agent_readiness.investigate.inspect.profile import build_profile
from agent_readiness.investigate.taskgen import criteria as C
from agent_readiness.investigate.taskgen.candidates import candidates
from agent_readiness.investigate.taskgen.gate import Accepted, Draft, evaluate as gate_v1
from agent_readiness.grading import v2 as G2
from agent_readiness.research.taskplan import catalogue as K
from agent_readiness.research.taskplan import context as X
from agent_readiness.research.taskplan import planner as P
from agent_readiness.research.taskplan.schema import parse_item
from agent_readiness.research.taskplan.schema_v3 import json_schema_v3, parse_item_v3
from agent_readiness.research.taskplan.verify import Verifier
from agent_readiness.taskeval.v2 import evaluator as E2
from agent_readiness.taskeval.v2 import kinds as KD

M2B = {"new_kinds": ["ranked_subset", "either_of"]}


@pytest.fixture(scope="module")
def sites():
    out = {}
    for sid in ("larkspur", "ironbark"):
        s = get(sid)
        out[sid] = (s, K.view(s), {v: build_profile(s.snapshot(v)) for v in s.variants})
    return out


def ranked(conds, label, direction, listing="/courses"):
    return {"kind": "ranked_subset", "listing": listing, "conditions": [dict(zip(("label", "op", "value"), c)) for c in conds], "label": label, "direction": direction}


def either(label, values, conds=(), listing="/courses"):
    return {"kind": "either_of", "listing": listing, "label": label, "values": list(values), "conditions": [dict(zip(("label", "op", "value"), c)) for c in conds]}


# --------------------------------------------------------------------------------------------------------------------------- oracle agreement
@pytest.mark.parametrize("sid", ["larkspur", "ironbark"])
def test_oracle_and_compile_agree_on_every_generated_instance(sites, sid):
    site, view, profs = sites[sid]
    oracle = site.oracle()
    compiled = refused = oracle_only = 0
    for crit in KD.enumerate_instances(view):
        res = {}
        for v, prof in profs.items():
            try:
                res[v] = KD.compile_ext(crit, prof).truth
            except C.CriterionError:
                res[v] = None
        assert len({json.dumps(r) for r in res.values()}) == 1, crit                      # stable across the site's variants
        truth, ans = res[site.variants[0]], KD.oracle_answer(oracle, crit)
        if truth is not None:
            compiled += 1
            assert ans.supported and (sorted(ans.truth) if isinstance(ans.truth, list) else ans.truth) == truth, crit   # never a compiled task the oracle disputes
        elif ans.supported:
            oracle_only += 1                         # safe direction (no task is created): v1's unit comparison refuses '1 day' vs '2 days' (Ironbark minimum hire)
            assert crit["conditions"][0]["label"] == "minimum hire"
        else:
            refused += 1
    assert compiled >= 90 and refused >= 1
    assert oracle_only <= 3


def test_ties_and_degenerate_filters_are_refused(sites):
    _, _, profs = sites["larkspur"]
    prof = profs["original"]
    cases = [(ranked([("duration", "ge", "10 weeks")], "course fee", "min"), "tied"),                 # $230 twice among the 10-week courses
             (ranked([("seats left", "ge", "0")], "course fee", "min"), "every item"),                 # filter keeps everything: an extremum
             (ranked([("level", "eq", "Advanced")], "course fee", "min"), "at least 2"),                # one item: no ranking
             (either("class day", ["Saturday", "Sunday"], [("level", "eq", "Advanced")]), "selects 0"),
             (either("class day", ["Saturday", "Sunday"], [("campus", "eq", "Northside")]), "degenerate"),
             (either("class day", ["Saturday", "Friday"]), "not a value"),
             (either("class day", ["Saturday", "saturday"]), "malformed")]
    for crit, why in cases:
        with pytest.raises(C.CriterionError, match=why):
            KD.compile_ext(crit, prof)
        assert not KD.oracle_answer(get("larkspur").oracle(), crit).supported or why == "malformed"


def test_v1_gate_still_refuses_the_new_kinds_as_malformed(sites):
    _, _, profs = sites["larkspur"]
    d = Draft("Which beginner course has the lowest course fee? Give its name.", "/", ranked([("level", "eq", "Beginner")], "course fee", "min"))
    r = gate_v1(d, profs["original"], [])
    assert not isinstance(r, Accepted) and "malformed" in r.reason
    with pytest.raises(Exception):
        C.compile_criterion(d.criterion, profs["original"])


# --------------------------------------------------------------------------------------------------------------------------- grading
def test_grader_v1_and_v2_grade_the_new_kinds(sites):
    _, _, profs = sites["larkspur"]
    prof = profs["original"]
    r = ranked([("level", "eq", "Beginner")], "course fee", "min")
    comp = KD.compile_ext(r, prof)
    other = next(d for d in comp.distractors if d != comp.truth)
    assert C.grade(comp, comp.truth)[0] and not C.grade(comp, other)[0] and not C.grade(comp, f"{comp.truth} or {other}")[0]
    key = KD.build_key_any("r", {"criterion": r, "truth": comp.truth}, prof)
    assert G2.grade(key, comp.truth).passed and G2.grade(key, f"{comp.truth}, the cheapest beginner course").passed
    assert not G2.grade(key, f"{comp.truth}, the most expensive").passed and not G2.grade(key, other).passed
    e = either("class day", ["Saturday", "Sunday"])
    ce = KD.compile_ext(e, prof)
    assert C.grade(ce, ce.truth)[0] and not C.grade(ce, ce.truth[:-1])[0] and not C.grade(ce, ce.truth + [other] if other not in ce.truth else ["x"])[0]
    ke = KD.build_key_any("e", {"criterion": e, "truth": ce.truth}, prof)
    assert G2.grade(ke, ce.truth).passed and not G2.grade(ke, ce.truth[:-1]).passed
    with pytest.raises(G2.KeyError_):
        KD.build_key_any("e", {"criterion": e, "truth": ce.truth[:-1]}, prof)                    # a frozen truth that no longer re-derives is refused


# --------------------------------------------------------------------------------------------------------------------------- existing kinds unchanged
def _corpus():
    out = []
    for sid in ("larkspur", "ironbark", "zoo-site-1"):
        site = get(sid)
        prof = build_profile(site.snapshot(site.variants[0]))
        out += [(prof, d) for d in candidates(prof, site.start_path, 6)]
    site = get("larkspur")
    view = K.view(site)
    prof = build_profile(site.snapshot("original"))
    for framing in ("raw", "framed"):
        ver = Verifier(site, view, framing)
        for t in json.loads(P.FIXTURE.read_text())["tasks"]:
            p, _, _ = parse_item(t)
            if p is None:
                continue
            crit, cat, _ = ver.criterion_for(p)
            if crit:
                out.append((prof, Draft(ver.question(p, crit) if framing == "framed" else p.scenario, site.start_path, crit, "llm")))
    return out


def test_replica_gate_equals_gate_v1_on_existing_kinds():
    corpus = _corpus()
    assert len(corpus) >= 40
    acc_v1, acc_r = {}, {}
    for prof, d in corpus:
        key = id(prof)
        a = gate_v1(d, prof, acc_v1.setdefault(key, []))
        b = KD.gate_replica(d, prof, acc_r.setdefault(key, []))
        assert type(a) is type(b), (d.question, a, b)
        if isinstance(a, Accepted):
            assert (a.fingerprint, a.hops, a.tags, a.compiled.truth, a.criterion) == (b.fingerprint, b.hops, b.tags, b.compiled.truth, b.criterion)
            acc_v1[key].append(a)
            acc_r[key].append(b)
        else:
            assert a.reason == b.reason
        try:
            assert KD.compile_any(d.criterion, prof).truth == C.compile_criterion(d.criterion, prof).truth
        except C.CriterionError:
            with pytest.raises(C.CriterionError):
                KD.compile_any(d.criterion, prof)


# --------------------------------------------------------------------------------------------------------------------------- end to end through evaluator v2
def cand(scenario, task_type, constraints, ranking=None, cid="m1", persona="budget_learner", journey="fit_schedule"):
    raw = {"intent_id": cid, "persona": persona, "journey": journey, "scenario": scenario, "task_type": task_type, "entity": None, "attribute": None,
           "constraints": constraints, "ranking": ranking, "answer_form": "single" if task_type == "best" else "list"}
    return {"candidate_id": cid, "provenance": {"source": "synthetic-test"}, "raw": raw}


def test_either_or_and_ranked_proposals_are_admitted_with_natural_wording(sites):
    site, view, _ = sites["larkspur"]
    cs = [cand("I can only come on Saturdays or Sundays. Which courses run on those days?", "filter",
               [{"attribute": "class day", "operator": "one_of", "values": ["Saturday", "Sunday"]}], cid="m1"),
          cand("I'm free on weekends only. Which courses can I take then?", "filter",
               [{"attribute": "class day", "operator": "one_of", "values": ["Saturday", "Sunday"]}], cid="m2"),
          cand("Which beginner course costs the least?", "best", [{"attribute": "level", "operator": "equals", "value": "Beginner"}],
               {"attribute": "course fee", "direction": "lowest"}, cid="m3", journey="find_affordable"),
          cand("Which Saturday course is the most expensive?", "best", [{"attribute": "class day", "operator": "equals", "value": "Saturday"}],
               {"attribute": "course fee", "direction": "lowest"}, cid="m4", journey="find_affordable")]
    ev = E2.TaskEvaluatorV2(site, view, X.CONTEXT, config=M2B)
    recs = {r["candidate_id"]: r for r in ev.evaluate([cs[0], cs[2], cs[3]])}
    dup = ev.evaluate([cs[0], cs[1]])[1]                                                         # same criterion as m1 in one batch: refused as a duplicate
    assert dup["admission"] == "rejected" and dup["rejection_reasons"][0].startswith("unique")
    recs["m2"] = ev.evaluate([cs[1]])[0]                                                        # alone: 'weekends' is the definitional value set
    assert recs["m1"]["admission"] == "natural" and recs["m1"]["capability"] == "either_of" and recs["m1"]["kind"] == "either_of"
    assert recs["m2"]["admission"] == "natural" and any("weekends" in d for d in recs["m2"]["wording"]["interpretation_decisions"])
    assert recs["m3"]["admission"] == "natural" and recs["m3"]["capability"] == "ranked_subset"
    assert recs["m4"]["admission"] == "rejected" and "intent_not_preserved" in recs["m4"]["rejection_reasons"][0]   # direction contradicts the wording
    for r in recs.values():
        if r["admission"] == "natural":
            assert all(g["pass"] for g in r["hard_gates"].values()) and r["v1"]["hard_pass"] is False   # v1 could not express them; v2's own hard gates all pass
            assert "expected_answer" not in E2.public(r)


def test_m2b_disabled_by_default_and_v3_schema_round_trips():
    raw = cand("Which courses run on Saturday or Sunday?", "filter", [{"attribute": "class day", "operator": "one_of", "values": ["Saturday", "Sunday"]}])["raw"]
    p, _, err = parse_item_v3(raw)
    assert p is not None and not err and p.constraints[0].values == ["Saturday", "Sunday"]
    assert parse_item(raw)[0] is None                                                           # v1 schema refuses one_of: v1 is unchanged
    assert parse_item_v3({**raw, "constraints": [{"attribute": "class day", "operator": "one_of", "values": ["Saturday"]}]})[0] is None
    assert parse_item_v3({**raw, "constraints": [{"attribute": "class day", "operator": "equals", "value": None, "values": None}]})[0] is None
    for t in json.loads(P.FIXTURE.read_text())["tasks"]:                                        # every v1-valid proposal parses identically
        a, b = parse_item(t)[0], parse_item_v3(t)[0]
        assert (a is None) == (b is None) and (a is None or a.model_dump(exclude={"constraints"}) == b.model_dump(exclude={"constraints"}))
    s = json_schema_v3()
    assert s["additionalProperties"] is False and "one_of" in json.dumps(s)
    assert E2.CONFIG["new_kinds"] == []


def test_recorded_proposals_with_m2b(sites):
    from pathlib import Path
    path = Path(__file__).resolve().parents[1] / "scanner-data/research/taskplan/taskplan-20261102T203537-meta-7aca17/proposals.json"
    if not path.exists():
        pytest.skip("recorded Muse Spark proposals are local, git-ignored data")
    site, view, _ = sites["larkspur"]
    cs = [{"candidate_id": it["raw"].get("intent_id") or f"idx{it['index']}", "provenance": {"source": "llm", "index": it["index"]}, "raw": it["raw"]}
          for it in json.loads(path.read_text())["items"]]
    recs = E2.TaskEvaluatorV2(site, view, X.CONTEXT, config=M2B).evaluate(cs)
    d = E2.distribution(recs)
    assert d["categories"] == {"natural_verifiable": 13, "natural_underspecified": 6, "natural_judgment": 1} and d["assisted_derivatives"] == 6
    caps = {r["candidate_id"]: r["capability"] for r in recs}
    assert caps["bl_cheapest_beginner_03"] == "ranked_subset" and caps["rg_best_cheap_short_06"] == "ranked_subset"
