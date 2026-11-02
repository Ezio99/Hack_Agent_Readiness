"""M8: the lifecycle in the product (zero cost; nothing here can reach a model).

Covers the shared evaluation projection and its leak audit, the sanitized M7 dataset (structure, integrity, tamper detection, and, where the
git-ignored source artefacts exist on this machine, byte-exact re-derivation), the prospective grading and evidence rules, the diagnostics fix
for either_of / ranked_subset, admission coordination of lifecycle jobs with the hosted ceiling and slot, the paid-coordination guard, and the
API: what it serves, and what it refuses (web approval, paid launch, non-operator launch, any client-supplied task/URL/model/limit field)."""
import json
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from agent_readiness.diagnostics import hypotheses as H
from agent_readiness.diagnostics.model import Finding
from agent_readiness.framework.site import get
from agent_readiness.grading import contrast as GC
from agent_readiness.grading import evidence_ranked as ER
from agent_readiness.grading import v2 as G2
from agent_readiness.hosted.admission import Admission, Refused
from agent_readiness.hosted.api import create_app
from agent_readiness.investigate.inspect.profile import build_profile
from agent_readiness.lifecycle import audit, dataset as DS, jobs as J, projection as P
from agent_readiness.lifecycle.service import LifecycleService

ROOT = Path(__file__).resolve().parents[1]
DATASETS = ROOT / "datasets" / "lifecycle"
M7 = DATASETS / "m7-larkspur-browser-1" / "v1"
SRC_STORE = ROOT / "scanner-data" / "research" / "stage-a" / "store"
SRC_RUN = ROOT / "scanner-data" / "research" / "stage-b" / "paid" / "evalrun-paid-64a55c5f3a-natural"
SRC_GEN = ROOT / "scanner-data" / "research" / "stage-a" / "m6-larkspur-core-20261102T121242Z"
TOKEN = b"t" * 32


def m7() -> dict:
    return json.loads((M7 / "evaluation.json").read_text())


# ------------------------------------------------------------------------------------------------------------------------------- dataset
def test_m7_dataset_is_valid_and_lists_every_file():
    rep = DS.validate(M7)
    assert rep["valid"], rep["problems"]
    meta = json.loads((M7 / "DATASET.json").read_text())
    assert meta["mode"] == "paid" and meta["source"]["manifest_sha256"].startswith("64a55c5f3a")
    assert len([f for f in meta["files"] if f.endswith(".webp")]) == len(meta["source"]["screenshots_png_sha256"]) > 100


def test_m7_dataset_reports_the_recorded_measurements():
    ev = m7()
    assert ev["mode"] == "paid" and ev["exploratory"] and "no statistical power" in ev["caveat"]
    t1 = {r["variant"]: r for r in ev["trials"] if r["task"] == 1}
    o, m = t1["original"], t1["modified"]
    assert (o["answer_coverage"]["named_expected"], o["answer_coverage"]["expected_items"]) == (1, 5)
    assert (m["answer_coverage"]["named_expected"], m["answer_coverage"]["expected_items"]) == (5, 5)
    assert (o["metrics"]["model_requests"], round(o["metrics"]["elapsed_seconds"])) == (12, 67)
    assert (m["metrics"]["model_requests"], round(m["metrics"]["elapsed_seconds"])) == (3, 16)
    assert not o["grades"]["v1"]["passed"] and not m["grades"]["v1"]["passed"]            # official v1, unchanged
    assert not o["grades"]["v2"]["passed"] and m["grades"]["v2"]["passed"]                  # post-hoc v2, labelled
    ts = ev["dimensions"]["task_success"]["variants"]
    assert (ts["original"]["v1_passed"], ts["modified"]["v1_passed"], ts["original"]["v2_passed"], ts["modified"]["v2_passed"]) == (2, 1, 3, 4)
    assert ev["cost"]["settled_spend"]["settled_usd"] == pytest.approx(1.520696, abs=1e-9) and ev["cost"]["settled_spend"]["settled_requests"] == 111
    assert ev["cost"]["settled_spend"]["unsettled_requests"] == 0 and ev["cost"]["total_usd"] == pytest.approx(1.52069, abs=1e-6)   # per-trial records round
    assert set(ev["dimensions"]) == {"task_success", "navigation_efficiency", "evidence_quality", "information_accessibility", "agent_reliability", "coverage"}


def test_m7_dataset_holds_no_oracle_data_or_secrets():
    for p in M7.rglob("*.json"):
        doc = json.loads(p.read_text())
        assert audit.check(doc, None, where=p.name) == []
        text = p.read_text()
        for needle in ("\"criteria\"", "variant-criteria", "missing_evidence", "evidence_texts", "api.meta.ai/v1/chat", "ledger.jsonl", "authorizations/", "127.0.0.1:"):
            assert needle not in text, (p, needle)


def test_tampered_dataset_is_detected_and_not_served(tmp_path):
    d = tmp_path / "m7-larkspur-browser-1" / "v1"
    shutil.copytree(M7, d)
    ev = json.loads((d / "evaluation.json").read_text())
    ev["trials"][0]["grades"]["v1"]["passed"] = True
    (d / "evaluation.json").write_text(json.dumps(ev))
    assert not DS.validate(d)["valid"]
    svc = LifecycleService(datasets=tmp_path, log=lambda *_: None)
    assert svc.datasets == {} and svc.problems


@pytest.mark.skipif(not (SRC_RUN.is_dir() and SRC_STORE.is_dir()), reason="the git-ignored M7 source artefacts exist only on the owner's workstation")
def test_m7_dataset_rederives_byte_for_byte_from_the_source():
    rep = DS.validate(M7, store_root=SRC_STORE, run_dirs=[SRC_RUN], generation_dir=SRC_GEN)
    assert rep["valid"] and rep["rederived_from_source"], rep["problems"]


# ------------------------------------------------------------------------------------------------------------------------------- audit
def test_audit_flags_forbidden_keys_patterns_and_answers():
    assert audit.check({"a": {"truth": "x"}}) and audit.check({"x": "http://127.0.0.1:8123/y"}) and audit.check({"x": "/home/someone/f"})
    assert audit.check({"note": "the answer is Beginners yoga"}, ["Beginners yoga"])
    assert audit.check({"answer": "Beginners yoga"}, ["Beginners yoga"]) == []                      # the agent's own output (paid run)
    assert audit.check({"answer": "Beginners yoga"}, ["Beginners yoga"], exempt_agent=False)        # a rehearsal stand-in's output is not exempt


def test_rehearsal_documents_never_exempt_the_stand_in():
    doc = {"mode": "rehearsal", "trials": [{"answer": "Beginners yoga"}], "tasks": []}
    assert audit.check_evaluation(doc, {"t": ["Beginners yoga"]})
    steps = P._redact_stand_in([{"memory": "Beginners yoga", "goal": "g", "assessment": "a", "actions": [{"name": "Answer", "target": "Beginners yoga"}, {"name": "Click", "target": "x"}]}])
    assert steps[0]["memory"] is None and steps[0]["actions"][0]["target"] == P.STAND_IN_WITHHELD and steps[0]["actions"][1]["target"] == "x"


# ------------------------------------------------------------------------------------------------------------------------------- grading (prospective)
def _key():
    cands = [G2.Candidate("Spanish conversation 2", (("seats left", "8"), ("class day", "Thursday"))),
             G2.Candidate("Furniture restoration", (("seats left", "1"), ("class day", "Sunday"))), G2.Candidate("Watercolour foundations", (("seats left", "7"),))]
    return G2.AnswerKey("t5", "ranked_subset", "string", "Spanish conversation 2", cands, set(), "max", ("seats left", "class day"))


def test_contrast_rule_accepts_an_explicit_comparison_and_never_changes_v2():
    ans = "Spanish conversation 2 - with 8 seats left (vs Furniture restoration with 1 seat on Sunday); it has the most seats."
    assert G2.grade(_key(), ans).reasons == ["multiple_candidates"]                                  # v2 unchanged
    g = GC.grade(_key(), ans)
    assert g["passed"] and g["applied"] and g["review"] and g["version"] == "2.1-contrast"


@pytest.mark.parametrize("ans", ["Spanish conversation 2 or Furniture restoration",                 # hedge, not a contrast
                                 "Furniture restoration (vs Spanish conversation 2 with 8 seats)",    # the wrong one first
                                 "Spanish conversation 2 with 8 seats vs Furniture restoration with 5 seats",   # contradicts its own facts
                                 "Spanish conversation 2, Furniture restoration"])                    # no contrast marker
def test_contrast_rule_refuses_anything_else(ans):
    assert not GC.grade(_key(), ans)["passed"]


def test_ranked_subset_rule_2_requires_every_subset_member():
    prof = build_profile(get("larkspur").snapshot("original"))
    crit = {"kind": "ranked_subset", "listing": "/courses", "label": "seats left", "direction": "max",
            "conditions": [{"label": "level", "op": "eq", "value": "Intermediate"}, {"label": "campus", "op": "eq", "value": "Riverside"}]}
    need = ER.required_pages(crit, prof)
    assert need[0] == "/courses" and len(need) >= 3                                                  # the listing + every member's page
    assert not ER.check(need, set(need[:-1]))["satisfied"] and ER.check(need, set(need))["satisfied"]
    assert ER.required_pages({"kind": "item_set"}, prof) is None


# ------------------------------------------------------------------------------------------------------------------------------- diagnostics
def test_either_of_and_ranked_subset_tasks_count_as_comparisons():
    assert H._criterion_labels({"kind": "either_of", "listing": "/c", "label": "class day", "values": ["Saturday", "Sunday"],
                                "conditions": [{"label": "level"}]}) == ("/c", {"class day", "level"})
    assert H._criterion_labels({"kind": "ranked_subset", "listing": "/c", "label": "seats left", "conditions": [{"label": "campus"}]}) == ("/c", {"seats left", "campus"})
    assert H.RULES_VERSION == "hypotheses-2"


def test_findings_separate_observed_facts_from_hypotheses():
    f = Finding("x", "structural", "r", "t", "s", "v", "0", "low", "i", "observed", [], "rec", "verify")
    h = Finding("y", "hypothesis", "r", "t", "s", "v", "0", "low", "i", "supported_exploratory", [], "rec", "verify")
    assert f.as_dict()["basis"] == "observed" and h.as_dict()["basis"] == "hypothesis"
    ev = m7()
    fs = ev["diagnostics"]["natural"]["findings"]
    assert {f["basis"] for f in fs} == {"observed", "hypothesis"}
    assert not any("no evaluated task compares items by 'class day'" in f["title"] for f in fs)       # the M7 misclassification is fixed
    assert any(f["basis"] == "hypothesis" and "class day" in f["title"] and 3 in f["tasks"] for f in fs)


# ------------------------------------------------------------------------------------------------------------------------------- admission
def _admission(tmp_path, ceiling=10_000_000):
    return Admission(tmp_path / "a.sqlite", ceiling_microusd=ceiling, job_cap_microusd=1_650_000, min_interval_seconds=60)


def test_stage_b_reservations_share_the_hosted_slot_and_ceiling(tmp_path):
    a = _admission(tmp_path)
    a.reserve_amount("eval-" + "0" * 32, "a" * 64, 0, now=1000)
    with pytest.raises(Refused, match="capacity"):
        a.reserve("eval-" + "1" * 32, "b" * 64, now=2000)                                             # one Chromium workload at a time
    a.transition("eval-" + "0" * 32, "reserved", "failed")
    with pytest.raises(Refused, match="budget"):
        a.reserve_amount("eval-" + "2" * 32, "c" * 64, 10_000_001, now=3000)                         # never above the ceiling itself
    with pytest.raises(ValueError):
        a.reserve_amount("eval-" + "2" * 32, "c" * 64, -1, now=3000)
    with pytest.raises(ValueError):
        a.reserve_amount("lc-" + "3" * 32, "c" * 64, 0)                                             # hosted evaluation ids only


def test_reserve_amount_respects_the_ceiling(tmp_path):
    a = _admission(tmp_path, ceiling=5_000_000)
    a.reserve("eval-" + "1" * 32, "b" * 64, now=1000, units=2)                                       # US$3.30
    a.transition("eval-" + "1" * 32, "reserved", "failed")
    with pytest.raises(Refused, match="budget"):
        a.reserve_amount("eval-" + "2" * 32, "c" * 64, 2_000_000, now=3000)
    a.reserve_amount("eval-" + "3" * 32, "c" * 64, 1_700_000, now=3000)
    assert a.totals()["reserved_microusd"] == 5_000_000


def _guard_store(tmp_path, name="larkspur-guard-test"):
    import importlib.util
    spec = importlib.util.spec_from_file_location("m7_paid_guard_fixture", Path(__file__).parent / "test_m7_paid_guard.py")
    T = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(T)
    return T.build(tmp_path, real_name=name), T.auth


# ------------------------------------------------------------------------------------------------------------------------------- API
class FakeExecutor:
    available, mode = True, "rehearsal"

    def __init__(self):
        self.ran = []

    def run(self, job_id):
        self.ran.append(job_id)


def _app(tmp_path, *, store=None, executor=None, admission=None):
    a = admission or _admission(tmp_path)
    svc = LifecycleService(datasets=DATASETS, store_root=store, runs_root=(tmp_path / "runs") if store else None, executor=executor, admission=a,
                           client_key=b"k" * 32, log=lambda *_: None)
    if store:
        (tmp_path / "runs").mkdir(exist_ok=True)
    app = create_app(tmp_path / "hosted", a, client_key=b"k" * 32, operator_token=TOKEN, public_start=False, mode="disabled", lifecycle=svc)
    return TestClient(app), svc, a


def test_api_serves_the_m7_evaluation_through_the_lifecycle_routes(tmp_path):
    c, _, _ = _app(tmp_path)
    ov = c.get("/api/lifecycle/overview").json()
    assert ov["approval"]["available"] is False and ov["evaluation"] is None                                    # no executor: view-only
    assert c.post("/api/lifecycle/evaluations", json={"repetitions": 1}).status_code == 405                     # the lifecycle API launches nothing
    evs = c.get("/api/lifecycle/evaluations").json()
    assert [e["id"] for e in evs] == ["m7-larkspur-browser-1"] and evs[0]["mode"] == "paid" and evs[0]["source"] == "dataset"
    ev = c.get("/api/lifecycle/evaluations/m7-larkspur-browser-1").json()
    assert ev["source"]["kind"] == "dataset" and ev["source"]["version"] == 1 and len(ev["trials"]) == 12
    tid = next(r["id"] for r in ev["trials"] if r["task"] == 1 and r["variant"] == "original")
    tl = c.get(f"/api/lifecycle/evaluations/m7-larkspur-browser-1/trials/{tid}").json()
    assert len(tl["steps"]) == 12 and tl["steps"][0]["screenshot"].endswith(".webp")
    shot = c.get(f"/api/lifecycle/evaluations/m7-larkspur-browser-1/trials/{tid}/screenshots/{tl['steps'][0]['screenshot']}")
    assert shot.status_code == 200 and shot.headers["content-type"] == "image/webp" and shot.content[:4] == b"RIFF"
    for bad in ("../DATASET.json", "step-1.png", "x.webp"):
        assert c.get(f"/api/lifecycle/evaluations/m7-larkspur-browser-1/trials/{tid}/screenshots/{bad}").status_code == 404
    assert c.get("/api/lifecycle/evaluations/m7-larkspur-browser-1/trials/..%2Fevaluation").status_code == 404
    assert c.get("/api/lifecycle/evaluations/nope-nope").status_code == 404
    suites = c.get("/api/lifecycle/suites").json()
    frozen = next(s for s in suites if s["state"] == "frozen")
    sv = c.get(f"/api/lifecycle/suites/{frozen['sha256']}").json()
    assert sv["refs"] == ["larkspur-core@v2"] and sv["web_decision"]["available"] is False and frozen["sha256"] in sv["attestation"]["approve"]
    gens = c.get("/api/lifecycle/generations").json()
    g = c.get(f"/api/lifecycle/generations/{gens[0]['id']}").json()
    assert g["admissions"] == {"natural": 18, "rejected": 5, "rubric": 1} and g["cost"]["calculated_usd"] == pytest.approx(0.049804)
    sites = c.get("/api/lifecycle/sites").json()
    assert {s["id"] for s in sites} == {"larkspur", "ironbark"} and all("SYNTHETIC" in s["context_label"] for s in sites)


def test_web_approval_is_refused_server_side_even_for_the_operator(tmp_path):
    c, _, _ = _app(tmp_path)
    sha = "1" * 64
    body = {"decision": "approved", "attestation": f"I am the owner and I approve suite {sha}"}
    for headers in ({}, {"authorization": "Bearer " + TOKEN.decode()}):
        r = c.post(f"/api/lifecycle/suites/{sha}/decision", json=body, headers=headers)
        assert r.status_code == 403 and r.json()["detail"]["code"] == "owner_authentication_not_configured"


def test_a_re_evaluation_manifest_differs_only_in_its_variants(tmp_path):
    from agent_readiness.lifecycle import arming as AR
    (store, f, msha, m), _ = _guard_store(tmp_path, name="synthetic-larkspur-m8-regress")
    from agent_readiness.lifecycle.sites import site_view
    reg = {v["name"]: v["snapshot_sha256"] for v in site_view("larkspur")["variants"]}
    assert AR.select_manifest(store, f, [("original", reg["original"]), ("modified", reg["modified"])], 1)[0] == msha
    new_sha, basis = AR.select_manifest(store, f, [("modified", reg["modified"]), ("original", reg["original"])], 1)
    new = store.get("manifest", new_sha)
    assert new_sha != msha and "regression manifest" in basis
    assert (new.frozen_suite_sha256, new.plan, new.agent, new.seed, new.repetitions) == (m.frozen_suite_sha256, m.plan, m.agent, m.seed, m.repetitions)
