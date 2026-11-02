"""M7: the paid Stage B authorisation guard (zero cost; nothing here can reach a model). A paid run needs a write-once owner authorisation that matches
the exact frozen suite, manifest, trial count and cap; synthetic suites never qualify; trials are counted from the experiment's fixed durable
ledger, so an interrupted trial is never re-run and a restart cannot exceed the authorised number."""
import json

import pytest

from agent_readiness.evalruns import authorization as AU
from agent_readiness.evalruns import manifest as MF
from agent_readiness.evalruns import runner as RN
from agent_readiness.framework.site import get
from agent_readiness.ledger import Ledger
from agent_readiness.research.taskplan import catalogue as K
from agent_readiness.research.taskplan import context as X
from agent_readiness.suites import plan as PL
from agent_readiness.suites.records import Approval, FrozenSuite, SuiteRecord
from agent_readiness.suites.stage_a import approval as AP
from agent_readiness.suites.stage_a import generators as G
from agent_readiness.suites.stage_a import loop as LP
from agent_readiness.suites.stage_a import stopping as ST
from agent_readiness.suites.store import WriteOnceStore

AT = "2026-11-02T15:00:00+00:00"
POOL = {t["intent_id"]: t for t in json.loads(G.POOL.read_text())["tasks"]}


def build(tmp_path, *, real_name="larkspur-guard-test", cap=8.0):
    """A suite under a NON-synthetic name whose approval/freeze records are written directly (a test of the guard, not an owner decision: the
    approval workflow itself refuses non-synthetic suites without a terminal, so the records are constructed here and never leave tmp_path)."""
    site = get("larkspur")
    store = WriteOnceStore(tmp_path / "store")
    out = LP.run(site, K.view(site), X.CONTEXT, G.RoundsFixture([[POOL[i] for i in ("p04", "p06", "p07")]]),
                 config=LP.LoopConfig(suite_name=real_name, stop=ST.StopRule(max_rounds=1)), created_at=AT, store=store)
    s = out["suite_sha256"]
    a = store.put(Approval(suite_sha256=s, decision="approved", approved_at=AT, notes="guard test (constructed in tmp_path; not an owner decision)"))
    f = store.put(FrozenSuite(suite_sha256=s, approval_sha256=a, frozen_at=AT))
    plan = PL.make_plan(n_tasks=3, repetitions=1, requested="exploratory", sims=20)
    m = MF.build(store, f, variants=[(v, site.snapshot(v).sha256) for v in site.variants], oracle=site.oracle().label, plan=plan, repetitions=1, seed=7,
                 created_at=AT, hard_cap_usd=cap)
    return store, f, store.put(m), m


def auth(f, msha, **kw):
    base = dict(experiment_id="m7-guard-test", frozen_suite_sha256=f, manifest_sha256=msha, max_trials=6, cap_usd=8.0,
                instruction="test instruction: run this exact manifest once", recorded_at=AT, recorded_by="test")
    return AU.PaidAuthorization(**{**base, **kw})


def test_a_matching_authorisation_verifies(tmp_path):
    store, f, msha, m = build(tmp_path)
    assert m.budget["worst_case_reservation_usd"] == pytest.approx(3 * 2 * 14 * MF.PER_REQUEST_CAP_USD)
    assert AU.verify(auth(f, msha), store, msha, planned_trials=6) == []


@pytest.mark.parametrize("change,needle", [({"manifest_sha256": "a" * 64}, "not the authorised manifest"), ({"frozen_suite_sha256": "b" * 64}, "frozen suite"),
                                           ({"cap_usd": 5.0}, "hard cap"), ({"max_trials": 5}, "exceed the authorised")])
def test_any_mismatch_refuses(tmp_path, change, needle):
    store, f, msha, _ = build(tmp_path)
    assert any(needle in p for p in AU.verify(auth(f, msha, **change), store, msha, planned_trials=6))


def test_worst_case_over_the_cap_is_refused_not_relaxed(tmp_path):
    store, f, msha, m = build(tmp_path, cap=3.0)
    probs = AU.verify(auth(f, msha, cap_usd=3.0), store, msha, planned_trials=6)
    assert any("worst-case reservation" in p and "revised design" in p for p in probs)


def test_synthetic_suites_never_authorise_paid_execution(tmp_path):
    store, f, msha, _ = build(tmp_path, real_name="synthetic-larkspur-guard")
    assert any("synthetic" in p for p in AU.verify(auth(f, msha), store, msha, planned_trials=6))


def test_authorisation_is_write_once(tmp_path):
    a = auth("c" * 64, "d" * 64)
    path = AU.write(a, tmp_path)
    assert AU.load(path) == a and AU.load(path).sha256 == a.sha256
    with pytest.raises(FileExistsError):
        AU.write(a, tmp_path)


def test_attempted_trials_are_counted_from_the_durable_ledger(tmp_path):
    led = Ledger(tmp_path / "ledger", 8.0)
    led.reserve("natural-original-gen-x-n-r1:req01", 0.04)
    led.reserve("natural-original-gen-x-n-r1:req02", 0.04)
    led.reserve("natural-modified-gen-x-n-r1:req01", 0.04)                                     # interrupted: reserved, never settled, no record
    again = Ledger(tmp_path / "ledger", 8.0)                                                   # a restart reads the same file
    assert RN.attempted_trials(again) == {"natural-original-gen-x-n-r1", "natural-modified-gen-x-n-r1"} and again.committed() == 0.12


def test_paid_mode_without_or_with_a_mismatched_authorisation_refuses_before_any_browser(tmp_path):
    store, f, msha, _ = build(tmp_path)
    runs = RN.prepare(store, msha, tmp_path / "runs", mode="paid", label="paid")
    with pytest.raises(PermissionError, match="authorisation record"):
        RN.execute(runs["natural"], store)
    bad = AU.write(auth(f, "e" * 64, experiment_id="m7-guard-mismatch"), tmp_path / "auth")
    with pytest.raises(PermissionError, match="authorisation mismatch"):
        RN.execute(runs["natural"], store, authorization=bad)
    assert not any((tmp_path / "runs").rglob("trials/*.json"))


def test_ledger_location_is_fixed_per_experiment():
    assert AU.ledger_dir("m7-larkspur-browser-1") == AU.STAGE_B / "ledgers" / "m7-larkspur-browser-1"
    with pytest.raises(ValueError):
        AU.ledger_dir("../escape")
