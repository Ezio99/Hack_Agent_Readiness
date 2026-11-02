"""Lifecycle M3: the bounded Stage A generation loop. Offline and free: every generator is a deterministic, developer-written fixture (NOT a model).

Covers every stopping path (targets met, max rounds, diminishing returns, budget cap before a round), targeted regeneration from feedback, feedback
hygiene (no expected answers), provenance and preservation of every round, stability of earlier records across rounds, and the Stage A boundary."""
import json
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

from agent_readiness.framework.site import get
from agent_readiness.research.taskplan import catalogue as K
from agent_readiness.research.taskplan import context as X
from agent_readiness.research.taskplan.planner_v2 import MetaGenerator
from agent_readiness.suites import boundary as B
from agent_readiness.suites.stage_a import feedback as FB
from agent_readiness.suites.stage_a import generators as G
from agent_readiness.suites.stage_a import loop as LP
from agent_readiness.suites.stage_a import stopping as ST
from agent_readiness.suites.store import WriteOnceStore
from agent_readiness.taskeval.v2 import evaluator as E2

ROOT = Path(__file__).resolve().parents[1]
POOL = {t["intent_id"]: t for t in json.loads(G.POOL.read_text())["tasks"]}
AT = "2026-11-02T12:00:00+00:00"


@pytest.fixture(scope="module")
def larkspur():
    s = get("larkspur")
    return s, K.view(s)


def batch(*ids):
    return [POOL[i] for i in ids]


def run(larkspur, gen, tmp_path, **cfg):
    site, view = larkspur
    store = WriteOnceStore(tmp_path / "store")
    out = LP.run(site, view, X.CONTEXT, gen, config=LP.LoopConfig(suite_name="synthetic-larkspur-test", **cfg), created_at=AT, out_dir=tmp_path / "run", store=store)
    return out, store


FIRST = ["p04", "p05", "p08", "p09", "p18", "u01", "u02", "r01", "r02", "r03"]


def test_targeted_regeneration_meets_targets_and_stops(larkspur, tmp_path):
    gen = G.FeedbackFixture(FIRST, n=8)
    out, store = run(larkspur, gen, tmp_path)
    s = out["summary"]
    assert s["stop_reason"] == "targets_met" and len(s["rounds"]) == 2 and out["gap_report"]["targets_met"]
    assert gen.read_feedback[0] is None and gen.read_feedback[1] is not None                      # round 2 was generated FROM the feedback
    fb = gen.read_feedback[1]
    cells = {(c["persona"], c["journey"]) for c in fb["uncovered_cells"]}
    r2 = [POOL[c.split("-", 1)[1]] for c in s["rounds"][1]["candidates"]]
    assert r2 and all((t["persona"], t["journey"]) in cells for t in r2)
    assert {"ranked_subset", "either_of"} <= set(fb["missing_capabilities"])
    assert out["coverage"]["deterministic"] == 12 and out["coverage"]["natural_share"] == 1.0
    suite = store.get("suite", out["suite_sha256"])
    assert suite.agent_evidence_consulted is False and suite.selection_rule == "selection-2" and len(suite.task_sha256s) == 12
    assert {i.kind for i in suite.provenance.inputs} == {"catalogue", "context", "snapshot", "generator", "evaluator", "proposals"}
    assert any("a few weeks" in g for g in suite.gaps)                                                # the preserved underspecified request is reported


def test_max_rounds_stop_reports_gaps_without_lowering_targets(larkspur, tmp_path):
    gen = G.RoundsFixture([batch("p04", "p05", "p09"), batch("p01", "p06", "p07"), batch("p10", "p11", "p13")])
    out, _ = run(larkspur, gen, tmp_path, targets={"min_tasks_per_persona": 5})
    assert out["summary"]["stop_reason"] == "max_rounds" and len(gen.calls) == 3
    assert not out["gap_report"]["targets_met"] and out["gap_report"]["thresholds_lowered"] is False
    assert any("target >= 5" in g for g in out["gap_report"]["gaps"]) and out["summary"]["config"]["targets"]["min_tasks_per_persona"] == 5


def test_diminishing_returns_stop(larkspur, tmp_path):
    gen = G.RoundsFixture([batch("p04"), batch("p09"), batch("p10")])
    out, _ = run(larkspur, gen, tmp_path)
    s = out["summary"]
    assert s["stop_reason"] == "diminishing_returns" and len(gen.calls) == 2
    assert [len(r["useful_additions"]) for r in s["rounds"]] == [1, 1]


def test_budget_cap_is_checked_before_each_round(larkspur, tmp_path):
    gen = G.RoundsFixture([batch("p04", "p05"), batch("p01")], reservation_per_round_usd=0.05, cost_per_round_usd=0.05)
    out, _ = run(larkspur, gen, tmp_path / "a", stop=ST.StopRule(budget_cap_usd=0.08))
    assert out["summary"]["stop_reason"] == "budget_cap" and len(gen.calls) == 1
    assert out["summary"]["rounds"][-1] == {"round": 2, "sent": False, "reservation_usd": 0.05, "spent_usd": 0.05, "stop": "budget_cap"}
    gen0 = G.RoundsFixture([batch("p04")], reservation_per_round_usd=0.05)
    out0, _ = run(larkspur, gen0, tmp_path / "b", stop=ST.StopRule(budget_cap_usd=0.01))
    assert out0["summary"]["stop_reason"] == "budget_cap" and gen0.calls == [] and out0["suite_sha256"] is None


def test_every_round_is_preserved_with_provenance(larkspur, tmp_path):
    out, _ = run(larkspur, G.FeedbackFixture(FIRST, n=8), tmp_path)
    d = tmp_path / "run"
    files = {p.name for p in d.iterdir()}
    assert {"loop.json", "proposals.json", "evaluation.public.json", "evaluation.private.json", "coverage.json", "gap-report.json", "suite-proposal.json", "feedback-r2.json"} <= files
    assert stat.S_IMODE(os.stat(d / "evaluation.private.json").st_mode) == 0o600
    loop = json.loads((d / "loop.json").read_text())
    for r in loop["rounds"]:
        assert r["request"]["prompt_version"] == "taskplan-v2" and r["request"]["schema_version"] == "taskplan-schema-v3" and len(r["request"]["request_sha256"]) == 64
        assert json.loads(r["response_text"])["tasks"] and r["response_mode"] == "scripted"
    assert loop["evaluator"]["version"] == "taskeval-2" and loop["generator"]["kind"] == "feedback-fixture" and loop["stopping"]["max_rounds"] == 3
    props = json.loads((d / "proposals.json").read_text())
    assert len(props) == 18 and all(p["provenance"]["prompt_version"] == "taskplan-v2" for p in props)
    pub = (d / "evaluation.public.json").read_text()
    assert "expected_answer" not in pub and any(r["rejection_reasons"] for r in json.loads(pub))


def test_earlier_records_never_change_across_rounds(larkspur):
    site, view = larkspur
    ev = E2.TaskEvaluatorV2(site, view, X.CONTEXT, config={"new_kinds": LP.M2B_KINDS})
    r1 = [{"candidate_id": f"r1-{t['intent_id']}", "provenance": {}, "raw": t} for t in batch(*FIRST)]
    r2 = [{"candidate_id": f"r2-{t['intent_id']}", "provenance": {}, "raw": t} for t in batch("p01", "p03", "p06", "p11", "p19", "r04")]
    relative = ("soft", "quality", "near_duplicate")                                                  # pool-relative ranking scores (novelty), recomputed by design
    a = [{k: v for k, v in E2.public(r).items() if k not in relative} for r in ev.evaluate(r1)]
    b = [{k: v for k, v in E2.public(r).items() if k not in relative} for r in ev.evaluate(r1 + r2)]
    assert b[:len(a)] == a                                                                           # admission, category, gates, wording, specification: unchanged


def test_feedback_never_carries_answers(larkspur, tmp_path):
    out, _ = run(larkspur, G.FeedbackFixture(FIRST, n=8), tmp_path)
    answers = FB.answer_strings(out["records"]) | {"$480"}                                           # r01 states its own answer; the gate refuses it before deriving one
    for r in out["summary"]["rounds"]:
        fb = r.get("feedback_out")
        if not fb:
            continue
        text = json.dumps(fb)
        assert not any(k in text for k in ('"expected"', '"truth"', '"expected_answer"'))
        for a in answers:
            assert FB.scrub(text, {a}) == text, a                                                     # no answer string anywhere in the feedback
        assert "Advanced joinery $480" not in text and ("executable_wording_unambiguous" not in fb["rejections"] or not fb["rejections"]["executable_wording_unambiguous"]["wording_examples"])
        assert "agent" not in json.dumps(sorted(fb)) and "trial" not in text.lower()


def test_stage_a_boundary_direct_and_transitive():
    assert B.forbidden_imports(ROOT / "src/agent_readiness/suites") == []
    code = ("import sys, agent_readiness.suites.stage_a.loop as L, agent_readiness.suites.stage_a.selection, agent_readiness.suites.stage_a.feedback;"
            "from agent_readiness.suites.boundary import FORBIDDEN_FOR_STAGE_A as F;"
            "print([m for m in sys.modules if any(m == p or m.startswith(p + '.') for p in F)])")
    res = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=120, cwd=ROOT)
    assert res.returncode == 0 and res.stdout.strip() == "[]", res.stderr[-400:]


def test_paid_generator_refuses_without_approval(tmp_path):
    with pytest.raises(PermissionError):
        MetaGenerator(tmp_path / "ledger", approval_note="", run_cap_usd=0.1)
