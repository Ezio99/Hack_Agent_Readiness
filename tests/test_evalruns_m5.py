"""Lifecycle M5: the generalised Stage B runner over an approved frozen suite manifest.

Fast tests (no browser): per-condition runs, snapshot-specific validity and invalidation, counterbalancing, refusal of paid execution, manifest
identity, the public-artefact leak audit, isolation. Browser test (marked): a small frozen Larkspur suite (natural filter, either/or and ranked
within a filter) end to end through real Chromium in the network jail with the loopback dev provider (NOT a model; zero cost)."""
import ast
import json
from pathlib import Path

import pytest

from agent_readiness.evalruns import manifest as MF
from agent_readiness.evalruns import rehearse as RH
from agent_readiness.evalruns import runner as RN
from agent_readiness.framework.site import get
from agent_readiness.investigate.taskgen import freeze as freezer
from agent_readiness.research.taskplan import catalogue as K
from agent_readiness.research.taskplan import context as X
from agent_readiness.suites import boundary as B
from agent_readiness.suites import plan as PL
from agent_readiness.suites.stage_a import approval as AP
from agent_readiness.suites.stage_a import generators as G
from agent_readiness.suites.stage_a import loop as LP
from agent_readiness.suites.stage_a import stopping as ST
from agent_readiness.suites.store import WriteOnceStore

ROOT = Path(__file__).resolve().parents[1]
AT = "2026-11-02T14:00:00+00:00"
POOL = {t["intent_id"]: t for t in json.loads(G.POOL.read_text())["tasks"]}


def frozen_manifest(root: Path, ids=("p04", "p06", "p07", "u02"), regression=False):
    site = get("larkspur")
    store = WriteOnceStore(root / "store")
    out = LP.run(site, K.view(site), X.CONTEXT, G.RoundsFixture([[POOL[i] for i in ids]]), config=LP.LoopConfig(suite_name="synthetic-larkspur-m5", stop=ST.StopRule(max_rounds=1)),
                 created_at=AT, store=store)
    s = out["suite_sha256"]
    fz = AP.freeze(store, s, AP.decide(store, s, decision="approved", attestation=AP.attestation_text(s, "approved"), at=AT), at=AT)
    _, _, tasks = MF.suite_tasks(store, fz)
    det = [t for t in tasks if t.spec.verifiability == "deterministic"]
    plan = PL.make_plan(n_tasks=sum(t.condition == "natural" for t in det), repetitions=1, requested="exploratory", sims=20)
    m = MF.build(store, fz, variants=[(v, site.snapshot(v).sha256) for v in site.variants], oracle=site.oracle().label, plan=plan, repetitions=1, seed=7, created_at=AT)
    return site, store, store.put(m), m


@pytest.fixture(scope="module")
def prepared(tmp_path_factory):
    root = tmp_path_factory.mktemp("m5")
    site, store, msha, m = frozen_manifest(root)
    runs = RN.prepare(store, msha, root / "runs", mode="rehearsal")
    return site, store, msha, m, runs, root


def test_one_run_per_condition_with_frozen_executed_wordings(prepared):
    site, store, msha, m, runs, _ = prepared
    assert set(runs) == set(m.conditions) == {"natural", "assisted"}                            # u02 is underspecified: its assisted derivative is the assisted task
    _, _, tasks = MF.suite_tasks(store, m.frozen_suite_sha256)
    by_id = {t.task_id: t for t in tasks}
    for cond, run in runs.items():
        tm, priv = freezer.load(run)
        assert run.state["config"]["manifest_sha256"] == msha and run.state["config"]["condition"] == cond
        for e in tm["tasks"]:
            t = by_id[e["task_id"]]
            assert t.condition == cond and e["question"] == t.wording.executed and e["limits"]["max_model_requests"] == t.limits.max_model_requests
            if cond == "natural":
                assert e["question"] == t.wording.customer
    kinds = {e["kind"] for e in runs["natural"].artifact("tasks-manifest")["tasks"]}
    assert {"item_set", "either_of", "ranked_subset"} <= kinds


def test_steps_are_counterbalanced_from_the_seed_and_complete(prepared):
    _, _, _, m, runs, _ = prepared
    run = runs["natural"]
    a, b = RN.steps(run, m), RN.steps(run, m)
    assert [(s["variant"], s["task"]["task_id"]) for s in a] == [(s["variant"], s["task"]["task_id"]) for s in b]
    n = len(run.artifact("tasks-manifest")["tasks"])
    assert len(a) == n * 2 and len({(s["variant"], s["task"]["task_id"], s["rep"]) for s in a}) == n * 2
    firsts = {a[i]["variant"] for i in range(0, len(a), 2)}
    assert firsts == {"original", "modified"} or n < 3                                         # both orders occur


def test_regression_snapshot_invalidates_changed_tasks_with_reasons(tmp_path):
    site, store, msha, m = frozen_manifest(tmp_path, ids=("p04", "p06", "p07", "p19", "p05"))
    rel = RH.larkspur_release2()
    m2, diff = MF.regression(store, msha, variants=[("modified", site.snapshot("modified").sha256), ("release2", rel.sha256)], created_at=AT)
    assert diff["frozen_suite_sha256"]["same"] and "variants" in diff["changed_fields"] and set(diff["changed_fields"]) <= {"budget", "variants"}
    m2sha = store.put(m2)
    runs = RN.prepare(store, m2sha, tmp_path / "runs", mode="rehearsal", extra_snapshots={"release2": rel}, label="reg")
    sm = runs["natural"].artifact("snapshot-manifests")
    assert sm["modified"]["excluded"] == []
    reasons = {e["reason"] for e in sm["release2"]["excluded"]}
    assert "the expected answer changed on this snapshot" in reasons and any("degenerate either/or" in r for r in reasons)
    assert set(sm["release2"]["valid_tasks"]) < set(sm["modified"]["valid_tasks"]) and (runs["natural"].dir / "variants" / "release2" / "index.json").exists()
    with pytest.raises(ValueError, match="not the manifest"):
        RN.resolve_variants(site, m2, {"release2": site.snapshot("original")})


def test_paid_execution_is_refused_and_the_manifest_does_not_change(tmp_path, prepared):
    site, store, msha, m, _, _ = prepared
    runs = RN.prepare(store, msha, tmp_path / "paid", mode="paid", label="paid")
    assert all(r.state["config"]["manifest_sha256"] == msha for r in runs.values())             # the same manifest hash as the rehearsal
    with pytest.raises(PermissionError, match="M6"):
        RN.execute(runs["natural"], store)
    assert store.get("manifest", msha).budget["paid_execution_approval"] is None


def test_leak_audit_is_clean_and_catches_an_injected_leak(tmp_path, prepared):
    site, store, msha, m, runs, root = prepared
    clean = RN.audit_public(store, msha, runs)
    assert clean["clean"] and clean["answers_checked"] >= 3
    priv = store.get("private_outcome", MF.suite_tasks(store, m.frozen_suite_sha256)[2][0].private_sha256).expected["truth"]
    leak = tmp_path / "leaky.public.json"
    leak.write_text(json.dumps({"answer": priv}))
    assert not RN.audit_public(store, msha, runs, [leak])["clean"]


def test_stage_b_is_isolated():
    assert B.forbidden_imports(ROOT / "src/agent_readiness/suites") == []
    for pkg in ("hosted", "suites", "taskeval", "research", "framework", "investigate"):
        for f in (ROOT / "src/agent_readiness" / pkg).rglob("*.py"):
            tree = ast.parse(f.read_text())
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module and "evalruns" in node.module:
                    pytest.fail(f"{f} imports evalruns")
                if isinstance(node, ast.Import) and any("evalruns" in a.name for a in node.names):
                    pytest.fail(f"{f} imports evalruns")


@pytest.mark.browser
def test_end_to_end_zero_cost_rehearsal_through_real_chromium(tmp_path):
    site, store, msha, m = frozen_manifest(tmp_path, ids=("p04", "p06", "p07"))
    runs = RN.prepare(store, msha, tmp_path / "runs", mode="rehearsal")
    assert set(runs) == {"natural"}
    ex = RN.execute(runs["natural"], store)
    assert ex["stopped"] is None and ex["jail_selftest"]["ok"] and len(ex["executed"]) == ex["planned"] == 6
    doc = RN.report(store, msha, runs, created_at=AT)
    nat = doc["exploratory"]["natural"]
    assert nat["complete"] and nat["rescore_faithful"] and doc["conditions_pooled"] is False and doc["notice"].startswith("ZERO-COST")
    rows = doc["trials"]["natural"]
    assert all(r["v1_passed"] for r in rows)                                                     # the scripted stand-in answers correctly; grading accepts it
    assert all(r["v2_passed"] is not None for r in rows)                                         # v2 keys every kind, including either_of and ranked_subset
    assert {r["kind"] for r in rows} == {"item_set", "either_of", "ranked_subset"}
    assert len(doc["run_results"]) == 2 and all(store.get("run_result", r["sha256"]).summary["trials"] == 3 for r in doc["run_results"])
    pub = tmp_path / "report.public.json"
    pub.write_text(json.dumps(RN.public_report(doc), default=str))
    assert RN.audit_public(store, msha, runs, [pub])["clean"]


def test_grading_keys_every_kind_without_rescore_crashing(prepared):
    """rescore.rescore_run cannot key the M2b kinds (v1 compile_criterion raises a validation error, not KeyError_); the runner grades through
    rescore's own row grader with keys from kinds.build_key_any instead, so every kind is keyed and v1 reproduction is still checked."""
    _, _, _, _, runs, _ = prepared
    from agent_readiness.grading import rescore
    res = RN.condition_results(runs["natural"])
    assert res["key_errors"] == [] and res["rows"] == [] and res["rescore_faithful"] and res["grader_v2"]["row_grader"] == "grading.rescore._trial_rows"
    with pytest.raises(Exception):
        rescore.rescore_run(runs["natural"].dir)
