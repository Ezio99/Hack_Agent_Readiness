"""M9: zero-cost rehearsal of the PAID hosted launch path up to the provider boundary (nothing can be sent).

Inputs (local-only, git-ignored): a copy of the production admission DB (scanner-data/hosted-copy/admission.sqlite, 2026-11-02 06:22 UTC) and a
copy of the real lifecycle store (scanner-data/research/stage-a/store). Steps: paid arming of larkspur-core@v2 (TTY semantics), operator launch
at US$10 (refused), owner ceiling migration 10 -> 10.736, operator launch through POST /api/ironbark/jobs (admitted), real worker subprocess,
real runner paid branch with a DUMMY key, jailed Chromium.

Three independent layers keep it zero-cost: (1) the M9 sitecustomize guard refuses every non-loopback connect and non-local DNS lookup in every
Python process (inherited by the worker through PYTHONPATH); (2) HTTP(S)_PROXY points at a dead loopback port; (3) the key is a dummy (the process
environment wins over any .env). (`unshare -rn` is NOT usable: the browser jail cannot nest its own namespaces inside it.)

    S=$(mktemp -d); cd "$S" && M9_NO_NETWORK=1 PYTHONPATH=<repo>/scripts/m9/no_network_guard \
        <repo>/.venv/bin/python <repo>/scripts/m9/paid_path_rehearsal.py <repo> "$S/run"
"""
import json
import os
import shutil
import socket
import sys
import time
from pathlib import Path

REPO = Path(sys.argv[1])
S = Path(sys.argv[2])
if S.exists():
    shutil.rmtree(S)
S.mkdir(parents=True)

# ---- safety: the M9 sitecustomize guard must be active (inherited by the worker through PYTHONPATH/M9_NO_NETWORK)
assert os.environ.get("M9_NO_NETWORK") == "1" and "guard" in os.environ.get("PYTHONPATH", ""), "run with the M9 guard"
try:
    socket.create_connection(("1.1.1.1", 443), timeout=3)
    raise SystemExit("ABORT: network reachable")
except OSError as exc:
    print("network check: refused as required:", exc)
try:
    socket.getaddrinfo("api.meta.ai", 443)
    raise SystemExit("ABORT: DNS works")
except OSError as exc:
    print("dns check: refused as required:", exc)
os.environ["HTTPS_PROXY"] = os.environ["HTTP_PROXY"] = os.environ["ALL_PROXY"] = "http://127.0.0.1:9"     # a dead loopback proxy: third layer
os.environ["NO_PROXY"] = os.environ["no_proxy"] = "127.0.0.1,localhost,::1"
os.environ["META_MODEL_API_KEY"] = "dummy-m9-key-not-a-secret"
(S / "dummy_key").write_text("dummy-m9-key-file-not-a-secret")
os.environ["META_MODEL_API_KEY_FILE"] = str(S / "dummy_key")
os.environ["AR_STAGE_B_ROOT"] = str(S / "stage-b")

from fastapi.testclient import TestClient  # noqa: E402

from agent_readiness.evalruns import authorization as AU  # noqa: E402
from agent_readiness.hosted import ceiling as CE  # noqa: E402
from agent_readiness.hosted.admission import Admission  # noqa: E402
from agent_readiness.hosted.api import create_app  # noqa: E402
from agent_readiness.hosted.stageb import StageBExecutor  # noqa: E402
from agent_readiness.lifecycle import arming as AR  # noqa: E402
from agent_readiness.lifecycle.service import LifecycleService  # noqa: E402

AR.set_stage_b_root(S / "stage-b")
assert AU.STAGE_B == S / "stage-b"
results = {}

root = S / "hosted" / "live"
root.mkdir(parents=True)
db = root / "admission.sqlite"
shutil.copy(REPO / "scanner-data/hosted-copy/admission.sqlite", db)
(root / ".service.lock").touch()
shutil.copytree(REPO / "scanner-data/research/stage-a/store", S / "store")
store = AR.open_store(S / "store")
TOKEN = b"m9-operator-token-0123456789abcdef"
OP = {"authorization": "Bearer " + TOKEN.decode()}

before = CE.status(db)
results["before"] = {k: before[k] for k in ("ceiling", "reserved", "remaining", "jobs", "active")}

# ---- paid arming (owner terminal semantics: interactive + exact typed attestation)
kw = dict(arming_id="m9-nonet-1", mode="paid", frozen_ref="larkspur-core@v2", variants=["original", "modified"], repetitions=[1], launches=1)
p = AR.plan(store, **kw)
assert p["options"][0]["manifest_sha256"].startswith("64a55c5f") and p["options"][0]["reservation_microusd"] == 7_436_000, p["options"]
try:
    AR.arm(store, typed=p["attestation"], at="2026-11-03T00:00:00+00:00", interactive=False, **kw)
    raise SystemExit("FAIL: non-interactive arm accepted")
except AR.ArmingRefused as exc:
    results["arm_noninteractive"] = exc.code
try:
    AR.arm(store, typed=p["attestation"][:-1], at="2026-11-03T00:00:00+00:00", interactive=True, **kw)
    raise SystemExit("FAIL: wrong attestation accepted")
except AR.ArmingRefused as exc:
    results["arm_wrong_attestation"] = exc.code
AR.arm(store, typed=p["attestation"], at="2026-11-03T00:00:00+00:00", interactive=True, **kw)


def app_for(ceiling):
    adm = Admission(db, ceiling_microusd=ceiling, job_cap_microusd=1_650_000, min_interval_seconds=120)
    ex = StageBExecutor(root, store.root, adm, mode="live", timeout=1200)
    svc = LifecycleService(datasets=None, store_root=store.root, runs_root=root / "stageb", executor=ex, admission=adm, log=lambda *_: None)
    return adm, TestClient(create_app(root, adm, client_key=b"k" * 32, executor=ex, operator_token=TOKEN, public_start=False, mode="live", lifecycle=svc))


# ---- at US$10 the exact launch is refused before anything is reserved or claimed
adm10, c10 = app_for(10_000_000)
cfg = c10.get("/api/ironbark/config").json()
results["config_at_10"] = {"engine": cfg["engine"], "available": cfg["available"], "repetitions": cfg["repetitions"],
                           "options": cfg["evaluation"]["options"]}
r = c10.post("/api/ironbark/jobs", json={"repetitions": 1}, headers=OP)
results["launch_at_10"] = [r.status_code, r.json().get("detail")]
assert r.status_code == 429 and not AR.claims("m9-nonet-1") and CE.status(db)["reserved"] == 3_300_000
results["no_token"] = c10.post("/api/ironbark/jobs", json={"repetitions": 1}).status_code
results["extra_field"] = c10.post("/api/ironbark/jobs", json={"repetitions": 1, "model": "x"}, headers=OP).status_code
results["reps_3"] = c10.post("/api/ironbark/jobs", json={"repetitions": 3}, headers=OP).status_code

# ---- the owner's ceiling migration (TTY semantics), exactly as the runbook
mp = CE.plan(db, to="10.736", expect_ceiling="10", expect_reserved="3.3", reason="one full six-task Original-vs-Modified paid evaluation of larkspur-core@v2")
out = CE.migrate(db, to="10.736", expect_ceiling="10", expect_reserved="3.3", reason=mp["reason"], typed=mp["confirmation"], interactive=True, actor="m9 rehearsal")
results["migration"] = out
try:
    Admission(db, ceiling_microusd=10_000_000, job_cap_microusd=1_650_000, min_interval_seconds=120)
    raise SystemExit("FAIL: stale .env ceiling accepted")
except ValueError as exc:
    results["stale_env_ceiling"] = str(exc)

# ---- operator launch at US$10.736: PAID branch, no network
adm, c = app_for(10_736_000)
t0 = time.time()
r = c.post("/api/ironbark/jobs", json={"repetitions": 1}, headers=OP)
results["launch"] = [r.status_code, r.json()]
assert r.status_code == 202, r.text
job = r.json()["id"]
results["second_launch_while_running"] = c.post("/api/ironbark/jobs", json={"repetitions": 1}, headers=OP).status_code
while time.time() - t0 < 1100:
    st = c.get(f"/api/ironbark/jobs/{job}").json()
    if st["state"] in ("completed", "failed", "timed_out", "interrupted"):
        break
    time.sleep(3)
results["elapsed_s"] = round(time.time() - t0, 1)
results["final_state"] = st["state"]
results["job_error"] = st.get("error")
results["stopped"] = st.get("stopped")
results["trials"] = [(t["arm"], t["task"], t["state"], t["outcome"], t["requests"]) for rep in st["reps"] for t in rep["tasks"] if t["state"] != "incomplete"]
results["admission_row"] = adm.get(job)
results["after"] = {k: v for k, v in CE.status(db).items() if k in ("ceiling", "reserved", "remaining", "jobs", "active", "history")}
led = AU.ledger_dir("m9-nonet-1-l1") / "ledger.jsonl"
lines = [json.loads(x) for x in led.read_text().splitlines()] if led.exists() else []
results["ledger"] = {"reserve": sum(e["kind"] == "reserve" for e in lines), "settle": sum(e["kind"] == "settle" for e in lines),
                     "reserved_usd": round(sum(e["usd"] for e in lines if e["kind"] == "reserve"), 6), "ids": [e["id"] for e in lines]}
claim = AR.claims_dir() / "m9-nonet-1-l1.json"
auth = AU.STAGE_B / "authorizations" / "m9-nonet-1-l1.json"
results["claim_mode"] = oct(claim.stat().st_mode & 0o777)
results["auth_mode"] = oct(auth.stat().st_mode & 0o777)
results["auth"] = {k: v for k, v in json.loads(auth.read_text()).items() if k != "instruction"}
results["relaunch"] = [c.post("/api/ironbark/jobs", json={"repetitions": 1}, headers=OP).status_code]
results["config_after"] = {k: c.get("/api/ironbark/config").json()[k] for k in ("available", "reason", "remaining_repetitions", "ceiling")}
results["live_route"] = c.get(f"/api/ironbark/jobs/{job}/live").status_code
results["export_route"] = c.get(f"/api/ironbark/jobs/{job}/repetitions/1/export").status_code
results["history_old_job"] = c.get("/api/ironbark/jobs/eval-aa23e33012717c4a30ca21be1239e85f").status_code
sbjob = json.loads((root / "stageb" / "jobs" / f"{job}.json").read_text())
results["sb_job"] = {k: sbjob.get(k) for k in ("state", "error", "stopped", "runtime_jail_hides")}
print(json.dumps(results, indent=1, default=str))
