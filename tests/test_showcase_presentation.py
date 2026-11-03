"""Final presentation fixes, with the real production run `eval-c04fdb10…` (Original vs Improved, owner-authorised paid launch) as the fixture.

1. The workspace grid reads like the readiness report: each finished agent run carries the report's `correct` (v2, else v1) and `exact_match`
   (official v1) beside its recorded outcome, which is unchanged.
2. Equivalent-page evidence (`equivalent-page-1`): a visited page that states every deciding fact for every catalogue item, exactly as the
   site's own records hold them (the Improved comparison table), is reported beside the recorded evidence rule. Recorded evidence, grades and
   every earlier projection are unchanged; the derived cache gets a new key so production re-projects.
The production copy is local-only and git-ignored (scanner-data/hosted-copy-fs, copied read-only from the VM); those tests skip without it."""
import copy
import json
from pathlib import Path

import pytest

from agent_readiness.framework.site import get
from agent_readiness.hosted import stageb
from agent_readiness.lifecycle import projection as P
from agent_readiness.sites.larkspur import render

ROOT = Path(__file__).resolve().parents[1]
COPY = ROOT / "scanner-data" / "hosted-copy-fs" / "data" / "hosted"
C04 = "eval-c04fdb100d6b1c877de96dabe76eb052"
E529 = "eval-e529db2aafecbfddd21e5c571eb85243"
need_copy = pytest.mark.skipif(not (COPY / "live" / "stageb" / "jobs" / f"{C04}.json").is_file(), reason="needs the local production copy")


def test_only_the_comparison_table_states_every_deciding_fact_for_every_course():
    site = get("larkspur")
    for labels in (["course fee", "seats left"], ["level", "class day"], ["course fee", "duration"]):
        assert P.equivalent_pages(site, render.snapshot("improved"), labels) == ["/courses/compare"]
        assert P.equivalent_pages(site, render.snapshot("original"), labels) == []
        assert P.equivalent_pages(site, render.snapshot("modified"), labels) == []      # cards are not labelled per-item values
    assert P.equivalent_pages(site, render.snapshot("improved"), ["no such field"]) == []
    assert P.equivalent_pages(site, render.snapshot("improved"), []) == []
    assert P.CACHE_KEY != P.VERSION and P.VERSION == "projection-1"                    # output format unchanged; derived caches re-keyed


@need_copy
def test_job_status_rows_carry_the_report_grades_without_changing_the_recorded_outcome():
    out = stageb.job_status(COPY / "live" / "stageb", C04, "completed", recovery_required=False, grades={("Modified", 1): {"correct": True, "exact_match": False}})
    cells = {(t["arm"], t["task"]): t for t in out["reps"][0]["tasks"]}
    assert cells[("Modified", 1)]["correct"] is True and cells[("Modified", 1)]["exact_match"] is False
    assert cells[("Modified", 1)]["outcome"] == "not_passed"                         # the recorded official outcome is unchanged
    assert "correct" not in cells[("Original", 1)]                                     # no grade given -> nothing invented
    assert "correct" not in stageb.job_status(COPY / "live" / "stageb", C04, "completed", recovery_required=False)["reps"][0]["tasks"][0]


@need_copy
def test_the_production_run_reprojects_with_equivalent_evidence_and_otherwise_identical(tmp_path, monkeypatch):
    import shutil

    from agent_readiness.evalruns import runner as RN
    from agent_readiness.lifecycle import audit
    from agent_readiness.lifecycle.service import LifecycleService
    from agent_readiness.suites.store import WriteOnceStore
    data = tmp_path / "hosted"
    shutil.copytree(COPY, data)
    derived = data / "live" / "stageb" / "derived"
    before = {j: json.loads((derived / f"{j}.projection-1.json").read_text()) for j in (C04, E529)}   # production's caches (the old code's output)
    svc = LifecycleService(datasets=None, store_root=data / "lifecycle" / "store", runs_root=data / "live" / "stageb", executor=None, admission=None,
                           log=lambda *_: None)
    for j in (C04, E529):
        ev = svc.evaluation(j)
        assert (derived / f"{j}.{P.CACHE_KEY}.json").is_file()
        eq = {(t["variant"], t["task"]): t["evidence"]["equivalent"]["via"] for t in ev["trials"] if "equivalent" in t["evidence"]}
        if j == C04:
            assert eq == {("improved", 1): ["/courses/compare"], ("improved", 2): ["/courses/compare"], ("improved", 3): ["/courses/compare"]}
            assert {v: x.get("evidence_satisfied_or_equivalent") for v, x in ev["dimensions"]["evidence_quality"]["variants"].items()} == {"original": 0, "improved": 3}
            assert all(not t["evidence"]["satisfied"] for t in ev["trials"])            # the recorded evidence rule is unchanged
            assert [t["grades"]["v1"]["passed"] for t in ev["trials"]] == [False] * 6      # official grades unchanged
        else:
            assert eq == {}
        new = copy.deepcopy(ev)
        new.pop("source", None)
        for t in new["trials"]:
            t["evidence"].pop("equivalent", None)
        for x in new["dimensions"]["evidence_quality"]["variants"].values():
            x.pop("evidence_satisfied_or_equivalent", None)
        new["dimensions"]["evidence_quality"].pop("equivalent_rule", None)
        old = copy.deepcopy(before[j])
        for d in (new, old):
            d["cost"].pop("settled_spend", None)                                         # read from the VM's absolute ledger path, not this copy
        assert json.dumps(new, sort_keys=True) == json.dumps(old, sort_keys=True), j
        st = WriteOnceStore(data / "lifecycle" / "store")
        assert audit.check_evaluation(ev, RN._answers(st, ev["frozen_suite"]["sha256"])) == []   # still publishable: nothing private leaks


@need_copy
def test_the_production_job_status_shows_the_report_grades():
    ev = json.loads((ROOT / "dashboard" / "src" / "fixtures" / "live" / "eval-c04fdb10-report.json").read_text())
    lab = {"original": "Original", "improved": "Modified"}
    grades = {(lab[t["variant"]], t["task"]): {"correct": bool((t["grades"]["v2"] or t["grades"]["v1"])["passed"]), "exact_match": bool(t["grades"]["v1"]["passed"])}
              for t in ev["trials"]}
    out = stageb.job_status(COPY / "live" / "stageb", C04, "completed", recovery_required=False, grades=grades)
    cells = sorted((t["arm"], t["task"], t["outcome"], t["correct"], t["exact_match"], t["requests"]) for t in out["reps"][0]["tasks"])
    assert cells == [("Modified", n, "not_passed", True, False, 2) for n in (1, 2, 3)] + [("Original", n, "not_passed", False, False, 13) for n in (1, 2, 3)]
    assert out["arm_display"] == {"Original": "Original", "Modified": "Improved"}


@need_copy
def test_the_hosted_status_route_serves_the_report_grades_for_the_production_run(tmp_path):
    import shutil

    from fastapi.testclient import TestClient

    from agent_readiness.hosted.admission import Admission
    from agent_readiness.hosted.api import create_app
    from agent_readiness.hosted.stageb import StageBExecutor
    from agent_readiness.lifecycle.service import LifecycleService
    data = tmp_path / "hosted"
    shutil.copytree(COPY, data)
    root = data / "live"
    a = Admission(root / "admission.sqlite", ceiling_microusd=21_956_000, job_cap_microusd=1_650_000, min_interval_seconds=120)
    ex = StageBExecutor(root, data / "lifecycle" / "store", a, mode="live")
    svc = LifecycleService(datasets=None, store_root=data / "lifecycle" / "store", runs_root=root / "stageb", executor=ex, admission=a, log=lambda *_: None)
    c = TestClient(create_app(root, a, client_key=b"k" * 32, executor=ex, operator_token=b"o" * 32, public_start=False, mode="live", lifecycle=svc))
    s = c.get(f"/api/ironbark/jobs/{C04}").json()
    assert s["report_status"]["state"] == "available"
    cells = sorted((t["arm"], t["task"], t["correct"], t["exact_match"]) for t in s["reps"][0]["tasks"])
    assert cells == [("Modified", n, True, False) for n in (1, 2, 3)] + [("Original", n, False, False) for n in (1, 2, 3)]
    assert all(t["outcome"] == "not_passed" for t in s["reps"][0]["tasks"])           # recorded outcomes unchanged
    e = c.get(f"/api/ironbark/jobs/{E529}").json()                                      # the earlier run: grades from its own report
    assert sum(t["correct"] for t in e["reps"][0]["tasks"]) == 6 and sum(t["exact_match"] for t in e["reps"][0]["tasks"]) == 3
