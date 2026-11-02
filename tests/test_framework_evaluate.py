"""Phase 3 milestone: the same orchestration (prepare -> execute -> results) evaluates every controlled site end to end at zero cost.

Fast tests (no browser): preparation, provenance, the loopback-only guard, the dev-provider per-trial script fix, and the absence of site-specific
branching in the core evaluator. Browser tests (marked): the complete loop on Ironbark and Larkspur through real Chromium with the loopback dev
provider, and the in-process scripted agent answering wrongly (grading must discriminate)."""
import ast
import json
from pathlib import Path

import pytest

from agent_readiness.framework import evaluate as E
from agent_readiness.framework import site as S
from agent_readiness.investigate.taskgen import freeze as freezer
from agent_readiness.live.devprovider import DevProvider

SITES = ("ironbark", "larkspur")
CORE = [Path(E.__file__), Path(E.__file__).with_name("generate.py"), Path(E.__file__).with_name("verifiability.py"), Path(E.__file__).with_name("oracle.py")]


@pytest.mark.parametrize("site", SITES)
def test_prepare_persists_a_standard_run_with_full_provenance(tmp_path, site):
    run = E.prepare(site, tmp_path, provider="dev", run_id=f"t-{site}")
    manifest, private = freezer.load(run)                                       # manifest, criteria and snapshot verify against each other
    prov = run.artifact("framework-provenance")
    assert prov["site"]["id"] == site and prov["site"]["controlled"] and set(prov["variants"]) == set(S.get(site).variants)
    assert prov["oracle"] and prov["task_generation"]["id"] == "framework-rules" and prov["tasks_manifest_sha256"] and prov["criteria_sha256"] == manifest["criteria_sha256"]
    assert prov["graders"]["official"]["version"] == "1" and prov["graders"]["post_hoc"]["version"] == "2" and "NOT a model" in prov["agent"]["model"]
    assert prov["variants"][prov["generated_on"]] == manifest["snapshot_sha256"] and run.has_artifact("dev-provider")
    assert len(manifest["tasks"]) == run.artifact("framework-taskset")["eligible"] >= 5


@pytest.mark.parametrize("site", SITES)
def test_the_plan_covers_every_eligible_task_on_every_variant(tmp_path, site):
    run = E.prepare(site, tmp_path, provider="mock", run_id=f"p-{site}")
    steps, excluded = E._plan(run, S.get(site))
    n = len(freezer.load(run)[0]["tasks"])
    assert excluded == [] and len(steps) == n * len(S.get(site).variants)
    assert {s["snap"].sha256 for s in steps} == set(run.artifact("framework-provenance")["variants"].values())


def test_only_loopback_model_endpoints_are_accepted():
    assert E._loopback("http://127.0.0.1:8199/v1")
    for url in ("https://api.meta.ai/v1", "http://10.0.0.5/v1", "http://example.com/v1"):
        with pytest.raises(ValueError, match="refused"):
            E._loopback(url)


def test_the_dev_provider_starts_a_fresh_scripted_agent_for_each_trial_of_the_same_task(tmp_path):
    """Regression: the dev provider cached ONE script per (run, task), so a second arm (or repeat) of the same task got an exhausted script and the
    first trial's stale mirror URL, and answered at step 1. It is now keyed per trial (each trial has its own mirror port)."""
    run = E.prepare("larkspur", tmp_path, provider="dev", run_id="dp")
    prov = DevProvider(tmp_path)
    prov.run = lambda: run
    inst = freezer.instances(run)[0]

    def first_action(port):
        body = {"messages": [{"role": "user", "content": f"{inst.spec.objective} http://127.0.0.1:{port}/"}]}
        return json.loads(prov.handle(body)["choices"][0]["message"]["content"])["action"][0]
    a, b = first_action(41001), first_action(41002)
    assert "navigate" in a and "navigate" in b                                 # both trials begin by navigating (not 'done')
    assert "41001" in a["navigate"]["url"] and "41002" in b["navigate"]["url"]  # each against its own mirror


def test_no_site_specific_branching_in_the_core_evaluator():
    """The engine never names a site: everything site-specific lives in SiteDefinition (framework/site.py) and the site packages."""
    names = set(S.SITES) | {"ironbark", "larkspur", "zoo"}
    for f in CORE:
        tree = ast.parse(f.read_text())
        docs = {id(n.body[0].value) for n in ast.walk(tree) if isinstance(n, (ast.Module, ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef))
                and n.body and isinstance(n.body[0], ast.Expr) and isinstance(n.body[0].value, ast.Constant)}                   # prose may mention sites; code may not
        consts = {n.value.lower() for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in docs}
        assert not any(any(name in c for name in names) for c in consts), f"{f.name} names a site"
        imports = {getattr(n, "module", "") or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)} | {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
        assert not any("sites." in m or m.endswith("sites") or "ironbark" in m or "larkspur" in m for m in imports), f"{f.name} imports a site package"


@pytest.mark.browser
@pytest.mark.slow
@pytest.mark.parametrize("site", SITES)
def test_complete_zero_cost_loop_through_the_same_orchestration(tmp_path, site):
    run = E.prepare(site, tmp_path, provider="dev", run_id=f"e2e-{site}")
    ex = E.execute(run)
    res = E.results(run)
    n = len(freezer.load(run)[0]["tasks"])
    variants = S.get(site).variants
    assert ex["excluded"] == [] and len(ex["executed"]) == n * len(variants) and res["complete"] and res["rescore_faithful"]
    for v in variants:
        t = res["totals"][v]
        assert t["trials"] == n and t["void"] == 0 and t["v1_evidence_backed"] == t["v2_evidence_backed"] and t["requests"] > n
    for row in res["trials"]:                                                   # the stand-in always answers correctly (it is given the frozen answer) ...
        assert row["v1_passed"] and row["v2_passed"] and {"trace.jsonl", "observations.json", "trial-result.json"} <= set(row["evidence_files"]) and row["steps"] >= 2
        if not row["v1_evidence_backed"]:                                       # ... but is credited only when the answer text was actually shown to it; it navigates without
            missing = run.artifact(f"trials/{row['variant']}-{row['task_id']}-r1")["evaluation"]["missing_evidence"]   # scrolling, so items low on a long listing stay unobserved
            assert missing and all(m.startswith("observed_text:") for m in missing)
    assert sum(r["v1_evidence_backed"] for r in res["trials"]) >= len(res["trials"]) // 2
    assert run.artifact("framework-results")["totals"] == res["totals"]
    assert not any(e["kind"] == "settle" and e["usd"] > E.PER_REQUEST_CAP_USD for e in run.ledger(E.FIXTURE_LEDGER_CEILING_USD).entries())   # every request went through the gate
    again = E.execute(run)                                                      # resumable: recorded trials are not re-run
    assert again["executed"] == []


@pytest.mark.browser
@pytest.mark.slow
@pytest.mark.parametrize("site", SITES)
def test_wrong_answers_are_graded_as_failures_on_every_site(tmp_path, site):
    run = E.prepare(site, tmp_path, provider="mock", run_id=f"wrong-{site}")
    E.execute(run, behavior="wrong")
    res = E.results(run)
    assert res["complete"] and res["rescore_faithful"]
    assert all(t["v1_evidence_backed"] == 0 and t["v2_evidence_backed"] == 0 and t["trials"] > 0 for t in res["totals"].values())
