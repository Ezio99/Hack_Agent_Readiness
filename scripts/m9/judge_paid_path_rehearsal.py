"""M9 judge live evaluation: zero-cost rehearsal of the PAID judge path up to the provider boundary (nothing can be sent).

Inputs (local-only, git-ignored): a copy of the production data (scanner-data/hosted-copy-m9/data/hosted: admission DB at US$10.736 fully reserved,
and the lifecycle store). On COPIES: the owner tooling builds and freezes larkspur-core@v3 (the reproducible hash), arms a paid 4-launch judge pool;
a judge launch at today's ceiling is refused; the ceiling is migrated to US$20.768; two judge launches run the real paid worker branch with a DUMMY
key behind the M9 network guard (reserve-before-send, connection refused, trial void, halt, no retry); the pool and budget arithmetic is checked.

    S=$(mktemp -d); cd "$S" && M9_NO_NETWORK=1 PYTHONPATH=<repo>/scripts/m9/no_network_guard \\
        <repo>/.venv/bin/python <repo>/scripts/m9/judge_paid_path_rehearsal.py <repo> "$S/run"

Final showcase: set M9_JUDGE_VARIANTS=original,improved to rehearse the featured Original-vs-Improved pool (default: original,modified).
"""
import json
import os
import shutil
import socket
import sys
import time
from pathlib import Path

REPO, S = Path(sys.argv[1]), Path(sys.argv[2])
if S.exists():
    shutil.rmtree(S)
S.mkdir(parents=True)
assert os.environ.get("M9_NO_NETWORK") == "1" and "no_network_guard" in os.environ.get("PYTHONPATH", ""), "run with the M9 guard"
for probe in (lambda: socket.create_connection(("1.1.1.1", 443), timeout=3), lambda: socket.getaddrinfo("api.meta.ai", 443)):
    try:
        probe()
        raise SystemExit("ABORT: network reachable")
    except OSError as exc:
        print("network blocked as required:", exc)
os.environ["HTTPS_PROXY"] = os.environ["HTTP_PROXY"] = os.environ["ALL_PROXY"] = "http://127.0.0.1:9"
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
from agent_readiness.suites.stage_a import approval as AP  # noqa: E402
from agent_readiness.suites.store import WriteOnceStore  # noqa: E402

V2_SUITE = "172d1e712eb18871fd4f24b227a2448ec44a546347bb9874f0946c5609f7848b"
V3_SUITE = "f45694788ea9e1f7b28c95193e25870bfe3aed2975d7f00276cdc87d7c6b09e3"
NOTES = "judge live evaluation: tasks gen-23f1802ee0-n and gen-f302fa8fe2-n of v2 (their deciding facts are on the Modified listing cards)"
OPERATOR, JUDGE = b"m9-operator-token-0123456789abcdef", b"m9-judge-access-code-0123456789abcdef"
JG = {"authorization": "Bearer " + JUDGE.decode()}
AR.set_stage_b_root(S / "stage-b")
out = {}

src = REPO / "scanner-data/hosted-copy-m9/data/hosted"
root = S / "hosted" / "live"
root.mkdir(parents=True)
db = root / "admission.sqlite"
shutil.copy(src / "live/admission.sqlite", db)
(root / ".service.lock").touch()
shutil.copytree(src / "lifecycle/store", S / "store")
st = WriteOnceStore(S / "store")
out["before"] = {k: v for k, v in CE.status(db).items() if k in ("ceiling", "reserved", "remaining", "jobs", "active")}

# owner tooling (production: at an interactive terminal; here on a copy)
v3 = AP.revise_keep(st, V2_SUITE, keep=["gen-23f1802ee0-n", "gen-f302fa8fe2-n"], context=AP._context(type("A", (), {"context": None})()),
                    at="2026-11-03T12:00:00+00:00", by="owner", notes=NOTES)
assert v3 == V3_SUITE, v3
sys.stdin.isatty = lambda: True                                       # the owner's terminal (the gate itself is tested in the unit tests)
appr = AP.decide(st, v3, decision="approved", attestation=AP.attestation_text(v3, "approved"), at="2026-11-03T12:01:00+00:00", notes="rehearsal copy")
AP.freeze(st, v3, appr, at="2026-11-03T12:02:00+00:00")
VARIANTS = os.environ.get("M9_JUDGE_VARIANTS", "original,modified").split(",")          # final showcase: M9_JUDGE_VARIANTS=original,improved
kw = dict(arming_id="larkspur-judge-1", mode="paid", frozen_ref="larkspur-core@v3", variants=VARIANTS, repetitions=[1], launches=4)
p = AR.plan(st, **kw)
AR.arm(st, typed=p["attestation"], at="2026-11-03T12:03:00+00:00", interactive=True, **kw)
out["arming"] = {"manifest": p["options"][0]["manifest_sha256"], "trials": p["options"][0]["trials"], "reservation_usd": p["options"][0]["reservation_microusd"] / 1e6,
                 "cap_usd": p["options"][0]["cap_usd"], "pool_total_usd": p["total_reservation_microusd"] / 1e6}


def app_for(ceiling):
    a = Admission(db, ceiling_microusd=ceiling, job_cap_microusd=1_650_000, min_interval_seconds=120)
    ex = StageBExecutor(root, st.root, a, mode="live", timeout=1200)
    svc = LifecycleService(datasets=None, store_root=st.root, runs_root=root / "stageb", executor=ex, admission=a, log=lambda *_: None)
    return a, TestClient(create_app(root, a, client_key=b"k" * 32, executor=ex, operator_token=OPERATOR, public_start=False, mode="live", lifecycle=svc,
                                    judge_token=JUDGE))


a, c = app_for(10_736_000)
cfg = c.get("/api/ironbark/config").json()
out["at_10.736"] = {"launch": cfg["launch"], "judge_access": cfg["judge_access"]}
r = c.post("/api/ironbark/jobs", json={"repetitions": 1}, headers=JG)
out["judge_launch_at_10.736"] = [r.status_code, r.json().get("detail")]
assert r.status_code in (409, 429) and not AR.claims("larkspur-judge-1") and CE.status(db)["reserved"] == 10_736_000

mp = CE.plan(db, to="20.768", expect_ceiling="10.736", expect_reserved="10.736", reason="four judge-triggered live runs of larkspur-core@v3")
out["migration"] = CE.migrate(db, to="20.768", expect_ceiling="10.736", expect_reserved="10.736", reason=mp["reason"], typed=mp["confirmation"],
                              interactive=True, actor="m9 rehearsal")
a, c = app_for(20_768_000)
out["at_20.768"] = c.get("/api/ironbark/config").json()["launch"]
runs = []
for i in (1, 2):
    if i == 2:
        time.sleep(121)                                                # the per-client rate limit of the copied policy (120 s)
    t0 = time.time()
    r = c.post("/api/ironbark/jobs", json={"repetitions": 1}, headers=JG)
    assert r.status_code == 202, r.text
    job = r.json()["id"]
    while time.time() - t0 < 900:
        s = c.get(f"/api/ironbark/jobs/{job}").json()
        if s["state"] not in ("reserved", "running"):
            break
        time.sleep(3)
    led = AU.ledger_dir(f"larkspur-judge-1-l{i}") / "ledger.jsonl"
    lines = [json.loads(x) for x in led.read_text().splitlines()] if led.exists() else []
    runs.append({"job": job, "state": s["state"], "stopped": s.get("stopped"), "seconds": round(time.time() - t0, 1),
                 "admission_reserved_usd": a.get(job)["reserved_microusd"] / 1e6,
                 "ledger": {"reserve": sum(e["kind"] == "reserve" for e in lines), "settle": sum(e["kind"] == "settle" for e in lines)},
                 "authorization": (AU.STAGE_B / "authorizations" / f"larkspur-judge-1-l{i}.json").is_file()})
out["judge_runs"] = runs
out["after"] = {k: v for k, v in CE.status(db).items() if k in ("ceiling", "reserved", "remaining", "jobs", "active")}
out["pool"] = c.get("/api/ironbark/config").json()["evaluation"]["launches"]
secret_found = [str(f) for f in list(root.rglob("*")) + list((S / "stage-b").rglob("*")) if f.is_file() and JUDGE in f.read_bytes()]
out["judge_code_in_any_file"] = secret_found
print(json.dumps(out, indent=1, default=str))
