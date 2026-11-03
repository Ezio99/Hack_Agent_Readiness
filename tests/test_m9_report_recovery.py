"""M9 follow-up: report recovery and execution-vs-publication status (zero cost; no model, no browser).

* Only the ONE browser-local origin a trial's snapshot was served from (recorded at the start of its own trace) is shown as a site path in the
  public projection; any other loopback URL, credential, local path, oracle material or authorisation record is still rejected by the audit.
* Raw evidence (trial records, traces) is never changed.
* A Stage B run whose agent runs all completed is not reported as an execution failure because its report could not be published; the preserved
  admission record is shown as written, with an explanation; a withheld report stays withheld.
* The historical paid production run `eval-e529db2a…` projects and passes the audit (uses the local, git-ignored copy of the production data;
  skipped elsewhere), with the recorded results, not the M7 dataset's."""
import hashlib
import json
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from agent_readiness.hosted import stageb
from agent_readiness.hosted.admission import Admission
from agent_readiness.hosted.api import create_app
from agent_readiness.lifecycle import audit, jobs as J, projection as P, service as SV

ROOT = Path(__file__).resolve().parents[1]
COPY = ROOT / "scanner-data" / "hosted-copy-m9" / "data" / "hosted"
PAID = "eval-e529db2aafecbfddd21e5c571eb85243"
ORIGIN = "http://127.0.0.1:34723"


def _trace(d: Path, *events) -> Path:
    d.mkdir(parents=True, exist_ok=True)
    (d / "trace.jsonl").write_text("".join(json.dumps(e) + "\n" for e in events))
    return d


ISO = {"kind": "browser_isolation", "mode": "netns-loopback-mirror-only"}


def nav(url):
    return {"kind": "initial_actions", "actions": [{"navigate": {"url": url}}]}


# ------------------------------------------------------------------------------------------------------------------------------- fixture origin
def test_the_fixture_origin_is_the_trials_own_recorded_jailed_mirror(tmp_path):
    assert P.fixture_origin(_trace(tmp_path / "a", ISO, nav(ORIGIN + "/"))) == ORIGIN
    assert P.fixture_origin(_trace(tmp_path / "b", ISO, nav(ORIGIN))) == ORIGIN


@pytest.mark.parametrize("events", [
    [nav(ORIGIN + "/")],                                                              # no isolation record
    [{"kind": "browser_isolation", "mode": "none"}, nav(ORIGIN + "/")],               # not the jailed mirror
    [ISO, nav("https://127.0.0.1:34723/")],                                           # another scheme
    [ISO, nav("http://localhost:34723/")],                                            # another host
    [ISO, nav("http://10.0.0.5:34723/")],
    [ISO, nav("http://127.0.0.1/")],                                                  # no port
    [ISO, nav("http://127.0.0.1:34723/courses")],                                    # not the site root
    [ISO, nav("http://127.0.0.1:34723/?x=1")],
    [ISO, nav("http://user:pw@127.0.0.1:34723/")],                                    # credentials
    [ISO],                                                                            # no initial navigation
])
def test_anything_else_is_not_an_approved_fixture_origin(tmp_path, events):
    assert P.fixture_origin(_trace(tmp_path / "t", *events)) is None


def test_no_trace_means_no_fixture_origin(tmp_path):
    assert P.fixture_origin(tmp_path) is None


def test_only_the_exact_fixture_origin_becomes_a_site_path():
    s, n = P.site_relative(f"see {ORIGIN}/courses/x and {ORIGIN}", ORIGIN)
    assert (s, n) == ("see /courses/x and /", 2)
    for other in ("http://127.0.0.1:34724/courses", "http://127.0.0.1:347231/x", "http://localhost:34723/x", "https://127.0.0.1:34723/x"):
        assert P.site_relative(other, ORIGIN) == (other, 0)
    assert P.site_relative(["a", f"{ORIGIN}/b"], ORIGIN) == (["a", "/b"], 1)
    assert P.site_relative(f"{ORIGIN}/b", None) == (f"{ORIGIN}/b", 0)


# ------------------------------------------------------------------------------------------------------------------------------- the audit still blocks real leaks
def _doc(answer, **extra):
    return {"mode": "paid", "tasks": [], "trials": [{"id": "t", "answer": answer}], **extra}


def test_a_normalised_answer_passes_and_unknown_loopback_urls_are_still_rejected():
    shown, _ = P.site_relative(["x", f"page {ORIGIN}/courses/abc"], ORIGIN)
    assert audit.check_evaluation(_doc(shown), {}) == []
    assert audit.check_evaluation(_doc(["x", "page http://127.0.0.1:34999/courses/abc"]), {})          # another port: rejected
    assert audit.check_evaluation(_doc(["x", f"page {ORIGIN}/courses/abc"]), {})                         # not normalised: rejected


@pytest.mark.parametrize("doc", [
    _doc("Bearer abcdefghijklmnop"),                                         # a credential, even in the agent's answer
    _doc("sk-abcdefghijklmnopqrstuv"),
    _doc("see /home/someone/secret.txt"),                                    # a local filesystem path
    _doc("ok", note="scanner-data/research"),                                # the private data directory
    _doc("ok", authorization={"x": 1}),                                      # authorisation records
    _doc("ok", ledger=[1]),
    _doc("ok", truth="Beginners yoga"),                                      # oracle material
    _doc("ok", note="META_MODEL_API_KEY=abc"),
])
def test_genuinely_sensitive_content_stays_blocked(doc):
    assert audit.check_evaluation(doc, {"t": ["Beginners yoga"]})


def test_an_expected_answer_outside_the_agents_output_stays_blocked():
    assert audit.check_evaluation(_doc("ok", note="the answer is Beginners yoga"), {"t": ["Beginners yoga"]})


# ------------------------------------------------------------------------------------------------------------------------------- execution vs publication
class _Exec:
    engine, available, mode = stageb.ENGINE, True, "live"

    def __init__(self, root, a):
        self.root, self.admission = root, a

    def configuration(self):
        return {"engine": stageb.ENGINE, "armed": True, "reason": None, "evaluation": None, "tasks": [], "repetitions": [1]}

    def admit(self, job_id, client, repetitions):
        self.admission.reserve_amount(job_id, client, 0)
        J.new_job(self.root / "stageb", job_id, manifest_sha="0" * 64, mode="paid", request={"repetitions": 1}, label="m9")
        return {"id": job_id, "state": "reserved", "repetitions": 1}

    def run(self, job_id):
        J.update_job(self.root / "stageb", job_id, state="completed", runs={}, finished_at=time.time())


class _Lifecycle:
    def __init__(self, raise_code=None):
        self.raise_code = raise_code

    def evaluation(self, eid):
        if self.raise_code:
            raise SV.Refused(self.raise_code, "x", 409)
        return {"id": eid, "dimensions": {"task_success": {"variants": {}}}}


def _app(tmp_path, lifecycle):
    root = tmp_path / "live"
    a = Admission(root / "admission.sqlite", ceiling_microusd=10_000_000, job_cap_microusd=1_650_000, min_interval_seconds=1)
    c = TestClient(create_app(root, a, client_key=b"k" * 32, executor=_Exec(root, a), operator_token=b"t" * 32, public_start=False, mode="live", lifecycle=lifecycle,
                                judge_token=b"judge-code-for-arming-launches-0123456789"))
    return root, a, c


def _launch_and_wait(c, a):
    job = c.post("/api/ironbark/jobs", json={"repetitions": 1}, headers={"authorization": "Bearer judge-code-for-arming-launches-0123456789"}).json()["id"]
    for _ in range(200):
        if a.get(job)["state"] not in ("reserved", "running"):
            break
        time.sleep(0.02)
    return job


def test_a_completed_run_whose_report_is_withheld_is_completed_and_its_report_stays_withheld(tmp_path):
    root, a, c = _app(tmp_path, _Lifecycle("withheld"))
    job = _launch_and_wait(c, a)
    assert a.get(job)["state"] == "completed"                                    # execution outcome, not a misleading "failed"
    st = c.get(f"/api/ironbark/jobs/{job}").json()
    assert st["execution"]["state"] == "completed" and st["report_status"]["state"] == "withheld" and st["report"] is None and st["record_note"] is None
    assert c.get(f"/api/ironbark/jobs/{job}/repetitions/1/export").status_code == 409             # fail-closed: nothing published
    assert [i for i in c.get("/api/ironbark/jobs").json() if i["id"] == job][0]["report_state"] == "withheld"


def test_a_run_with_no_results_is_still_an_execution_failure(tmp_path):
    root, a, c = _app(tmp_path, _Lifecycle("not_ready"))
    assert a.get(_launch_and_wait(c, a))["state"] == "failed"


def test_a_historical_failed_record_is_kept_and_explained_when_execution_completed(tmp_path):
    root, a, c = _app(tmp_path, _Lifecycle(None))
    job = "eval-" + "b" * 32
    a.reserve_amount(job, "c" * 64, 7_436_000)
    a.transition(job, "reserved", "running")
    a.transition(job, "running", "failed")                                      # as recorded before M9
    J.new_job(root / "stageb", job, manifest_sha="0" * 64, mode="paid", request={"repetitions": 1}, label="m9")
    J.update_job(root / "stageb", job, state="completed", runs={})
    st = c.get(f"/api/ironbark/jobs/{job}").json()
    assert st["state"] == "failed" and a.get(job)["state"] == "failed"         # never rewritten
    assert st["execution"]["state"] == "completed" and st["report_status"]["state"] == "available" and st["report"] == job
    assert "Execution completed" in st["record_note"] and "kept unchanged" in st["record_note"]


def test_record_note_only_when_the_record_differs_from_a_completed_execution():
    assert stageb.record_note("completed", "completed", "available", 12, 12) is None
    assert stageb.record_note("failed", "failed", "unavailable", 3, 12) is None
    assert stageb.record_note("running", "completed", "pending", 12, 12) is None
    assert "12/12" in stageb.record_note("failed", "completed", "withheld", 12, 12) and "still withheld" in stageb.record_note("failed", "completed", "withheld", 12, 12)


# ------------------------------------------------------------------------------------------------------------------------------- worker and service share one policy
def test_the_worker_records_the_services_publication_check(tmp_path, monkeypatch):
    J.new_job(tmp_path, "eval-" + "c" * 32, manifest_sha="0" * 64, mode="paid", request={}, label="x")
    monkeypatch.setattr(SV, "project_and_audit", lambda store, runs_root, job: ({}, ["evaluation.x: loopback address with port"]))
    out = J._publication_check(None, tmp_path, "eval-" + "c" * 32, runner_audit_clean=True)
    assert out["report_audit_clean"] is False and out["report_problems"] == 1 and out["publishable"] is False and "loopback" not in json.dumps(out)
    monkeypatch.setattr(SV, "project_and_audit", lambda store, runs_root, job: ({}, []))
    assert J._publication_check(None, tmp_path, "eval-" + "c" * 32, runner_audit_clean=False)["publishable"] is False
    assert J._publication_check(None, tmp_path, "eval-" + "c" * 32, runner_audit_clean=True)["publishable"] is True

    def boom(*a):
        raise KeyError("x")
    monkeypatch.setattr(SV, "project_and_audit", boom)
    assert J._publication_check(None, tmp_path, "eval-" + "c" * 32, runner_audit_clean=True)["report_error"] == "KeyError"


def test_the_service_withholds_a_report_whose_runner_audit_failed(tmp_path, monkeypatch):
    runs = tmp_path / "stageb"
    (tmp_path / "store" / "objects").mkdir(parents=True)
    job = "eval-" + "d" * 32
    J.new_job(runs, job, manifest_sha="0" * 64, mode="paid", request={}, label="x")
    J.update_job(runs, job, state="completed", runs={"natural": "evalruns/x"}, audit_clean=False)
    monkeypatch.setattr(SV, "project_and_audit", lambda store, runs_root, j: ({"id": j["id"]}, []))
    svc = SV.LifecycleService(datasets=None, store_root=tmp_path / "store", runs_root=runs, log=lambda *_: None)
    with pytest.raises(SV.Refused) as exc:
        svc.evaluation(job)
    assert exc.value.code == "withheld"


# ------------------------------------------------------------------------------------------------------------------------------- the historical paid run (local copy of production)
needs_copy = pytest.mark.skipif(not (COPY / "live" / "stageb" / "jobs" / f"{PAID}.json").is_file(), reason="needs the local copy of the production data")


def _tree(d: Path) -> str:
    h = hashlib.sha256()
    for p in sorted(x for x in d.rglob("*") if x.is_file()):
        h.update(str(p.relative_to(d)).encode() + p.read_bytes())
    return h.hexdigest()


@needs_copy
def test_the_historical_paid_run_projects_and_passes_the_audit_without_touching_its_evidence(tmp_path):
    import shutil
    from agent_readiness.suites.store import WriteOnceStore
    data = tmp_path / "hosted"
    shutil.copytree(COPY / "live" / "stageb", data / "stageb")
    shutil.copytree(COPY / "lifecycle" / "store", data / "store")
    before = _tree(data / "stageb")
    job = json.loads((data / "stageb" / "jobs" / f"{PAID}.json").read_text())
    doc, problems = SV.project_and_audit(WriteOnceStore(data / "store"), data / "stageb", job)
    assert problems == []
    assert _tree(data / "stageb") == before                                     # raw evidence unchanged
    run = next((data / "stageb" / "evalruns").iterdir())
    raw = json.loads((run / "artifacts" / "trials" / "original-gen-ae6c23b20b-n-r1.json").read_text())
    assert ORIGIN in json.dumps(raw["outcome"]["answer"])                      # the recorded answer keeps what the agent wrote
    shown = next(t for t in doc["trials"] if t["id"] == "original-gen-ae6c23b20b-n-r1")
    assert ORIGIN not in json.dumps(shown["answer"]) and shown["answer_normalized"]["fixture_origin_replaced"] == 1
    assert [t["id"] for t in doc["trials"] if "answer_normalized" in t] == ["original-gen-ae6c23b20b-n-r1"]
    # the real run's own results (not the M7 dataset's): 12 completed trials, the recorded grades and the settled ledger spend
    assert doc["id"] == PAID and doc["mode"] == "paid" and len(doc["trials"]) == 12 and all(t["status"] == "completed" and not t["void"] for t in doc["trials"])
    ts = doc["dimensions"]["task_success"]["variants"]
    assert (ts["original"]["v1_passed"], ts["modified"]["v1_passed"], ts["original"]["v2_passed"], ts["modified"]["v2_passed"]) == (1, 2, 2, 4)
    nav = doc["dimensions"]["navigation_efficiency"]["variants"]
    assert (nav["original"]["model_requests_total"], nav["modified"]["model_requests_total"]) == (68, 44)
    assert doc["cost"]["total_usd"] == pytest.approx(1.546229)                 # per-trial usage (the ledger-settled 1.546226 is read in the container,
                                                                                # where the run's recorded ledger path /data/... exists)
    for t in doc["trials"]:                                                    # official grades are exactly the recorded v1 grades
        rec = json.loads((run / "artifacts" / "trials" / f"{t['id']}.json").read_text())["evaluation"]
        assert (t["grades"]["v1"]["passed"], t["grades"]["v1"]["evidence_backed"]) == (bool(rec.get("passed")), bool(rec.get("evidence_backed")))


def test_the_m7_dataset_is_still_served_unchanged():
    d = ROOT / "datasets" / "lifecycle" / "m7-larkspur-browser-1" / "v1"
    ev = json.loads((d / "evaluation.json").read_text())
    assert not any("answer_normalized" in t for t in ev["trials"]) and audit.check(ev, None) == []
