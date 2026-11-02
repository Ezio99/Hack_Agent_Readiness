"""M1: immutable lifecycle records, write-once store, hashes and provenance, private-answer isolation, Stage A / Stage B boundary. Offline."""
import json
import os
import stat
from pathlib import Path

import pytest
from pydantic import ValidationError

from agent_readiness.suites import boundary as B
from agent_readiness.suites.records import (AgentConfig, Approval, EvaluationManifest, FrozenSuite, InputRef, Limits, PrivateOutcome, Provenance, RunResult,
                                            StatisticalPlan, SuiteRecord, TaskRecord, TaskSpec, Validation, Wording, content_hash, min_p_sign_flip, public_task_view)
from agent_readiness.suites.store import OverwriteError, StoreError, TamperError, WriteOnceStore

H = lambda c: c * 64                                                            # a well-formed sha256 placeholder
SECRET = "Quokka pottery evenings"                                              # a fictional expected answer that must never appear in public files


def prov(*inputs, by="system"):
    return Provenance(created_at="2026-11-02T10:00:00+00:00", created_by=by, tool="test", tool_version="1", config_fingerprint="cfg",
                      inputs=tuple(inputs) or (InputRef(kind="catalogue", name="larkspur", sha256=H("a")),))


def spec(**kw):
    return TaskSpec(kind="item_set", criterion={"listing": "/courses", "conditions": [{"label": "class day", "op": "eq", "value": "Saturday"}]},
                    verifiability=kw.pop("verifiability", "deterministic"), evidence_paths=("/courses",), **kw)


def outcome(s):
    return PrivateOutcome(spec_sha256=content_hash(s), expected=[SECRET], evidence_texts=((None, SECRET),), oracle="larkspur data.COURSES", derived_from_snapshot=H("b"))


def task(store, *, wording=None, s=None, task_id="t1", inputs=()):
    s = s or spec()
    w = wording or Wording(customer="Which courses meet on Saturdays?", executed="Which courses meet on Saturdays?", category="natural_verifiable",
                           interpretation_decisions=("field implied by a value unique to the class-day domain",))
    priv = store.put(outcome(s)) if s.verifiability == "deterministic" else None
    return TaskRecord(task_id=task_id, site="larkspur", persona="career_switcher", journey="fit_schedule", capability="filter-1", wording=w, spec=s,
                      limits=Limits(max_steps=14, max_model_requests=14, timeout_seconds=240), private_sha256=priv,
                      validation=Validation(evaluator="taskeval", evaluator_version="2", config_fingerprint="x", passed=True), provenance=prov(*inputs))


def suite(store, tasks, version=1, inputs=()):
    return SuiteRecord(suite_name="larkspur-core", version=version, site="larkspur", task_sha256s=tuple(store.put(t) for t in tasks), selection_rule="selection-1",
                       coverage={"personas": "1/4"}, provenance=prov(*inputs))


def plan(**kw):
    base = dict(designation="exploratory", primary_outcome="evidence-supported pass", comparison_rule="paired-exact-sign-flip", n_tasks=4, repetitions=1,
                analysis="per-task mean over repetitions; paired difference", stopping_rule="all planned trials; no retries")
    return StatisticalPlan(**{**base, **kw})


def frozen(store, s):
    ssha = store.put(s)
    a = store.put(Approval(suite_sha256=ssha, decision="approved", approved_at="2026-11-02T11:00:00+00:00", notes="owner review"))
    return store.put(FrozenSuite(suite_sha256=ssha, approval_sha256=a, frozen_at="2026-11-02T11:01:00+00:00")), ssha


def manifest(fsha, **kw):
    return EvaluationManifest(frozen_suite_sha256=fsha, variants=(("original", H("c")), ("modified", H("d"))), oracle="larkspur data.COURSES",
                              graders={"official": "generated-criteria v1", "post_hoc": ["generated-criteria v2"]},
                              agent=AgentConfig(model="muse-spark-1.3", endpoint="https://api.meta.ai/v1", reasoning_effort="low", max_completion_tokens=4096,
                                                profile="suite-v2-compat2", profile_sha256=H("e")), repetitions=1, seed=7, plan=plan(),
                              budget={"hard_cap_usd": 5.0}, provenance=prov(InputRef(kind="frozen_suite", name="larkspur-core@1", sha256=fsha)), **kw)


@pytest.fixture
def store(tmp_path):
    return WriteOnceStore(tmp_path / "store")


# ----------------------------------------------------------------------------------------------------------------------------- immutability
def test_records_are_frozen_and_reject_unknown_fields(store):
    t = task(store)
    with pytest.raises(ValidationError):
        t.task_id = "other"
    with pytest.raises(ValidationError):
        TaskRecord(**{**t.model_dump(), "expected": SECRET})


def test_store_is_write_once_content_addressed_and_idempotent(store):
    t = task(store)
    sha = store.put(t)
    assert sha == content_hash(t) and store.put(t) == sha                      # same record, same object
    path = store.root / "objects" / "task" / f"{sha}.json"
    assert not (path.stat().st_mode & (stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))   # read-only on disk
    assert store.get("task", sha) == t


def test_named_references_cannot_be_repointed(store):
    s1 = store.put(suite(store, [task(store)]))
    s2 = store.put(suite(store, [task(store)], version=2))
    store.ref("suite", "larkspur-core@1", s1)
    store.ref("suite", "larkspur-core@1", s1)                                  # idempotent
    with pytest.raises(OverwriteError):
        store.ref("suite", "larkspur-core@1", s2)
    assert store.resolve("suite", "larkspur-core@1") == s1


# ----------------------------------------------------------------------------------------------------------------------------- tampering
def _tamper(path: Path, mutate):
    os.chmod(path, 0o600)
    data = json.loads(path.read_text())
    mutate(data)
    path.write_text(json.dumps(data, sort_keys=True, separators=(",", ":")))


def test_tampered_public_record_is_detected_on_read(store):
    sha = store.put(task(store))
    _tamper(store.root / "objects" / "task" / f"{sha}.json", lambda d: d["wording"].update(customer="Which courses meet on Sundays?", executed="Which courses meet on Sundays?"))
    with pytest.raises(TamperError):
        store.get("task", sha)


def test_tampered_private_outcome_and_store_level_overwrite_are_detected(store):
    t = task(store)
    _tamper(store.root / "private" / f"{t.private_sha256}.json", lambda d: d.update(expected=["Something else"]))
    with pytest.raises(TamperError):
        store.get("private_outcome", t.private_sha256)
    with pytest.raises(TamperError):
        store.put(t)                                                            # re-validation of the referenced private outcome fails


def test_a_private_outcome_for_another_spec_is_refused(store):
    other = TaskSpec(kind="item_set", criterion={"listing": "/courses", "conditions": [{"label": "campus", "op": "eq", "value": "Northside"}]},
                     verifiability="deterministic", evidence_paths=("/courses",))
    t = task(store)
    bad = TaskRecord(**{**t.model_dump(), "private_sha256": store.put(outcome(other))})
    with pytest.raises(StoreError, match="different task specification"):
        store.put(bad)


# ----------------------------------------------------------------------------------------------------------------------------- provenance and hashing
def test_provenance_is_part_of_the_identity_and_records_inputs(store):
    a, b = task(store), task(store, inputs=(InputRef(kind="catalogue", name="larkspur", sha256=H("f")),))
    assert content_hash(a) != content_hash(b) and a.provenance.inputs[0].kind == "catalogue"
    with pytest.raises(ValidationError):
        Provenance(created_at="2026", created_by="system", tool="t", tool_version="1")      # timestamp required
    with pytest.raises(ValidationError):
        InputRef(kind="catalogue", name="x", sha256="not-a-hash")


def test_hash_is_canonical_and_order_independent_for_dicts(store):
    s1 = TaskSpec(kind="item_set", criterion={"a": 1, "b": 2}, verifiability="deterministic")
    s2 = TaskSpec(kind="item_set", criterion={"b": 2, "a": 1}, verifiability="deterministic")
    assert content_hash(s1) == content_hash(s2)


# ----------------------------------------------------------------------------------------------------------------------------- private-answer isolation
def test_public_views_and_files_never_contain_expected_answers(store):
    t = task(store)
    s = store.put(suite(store, [t]))
    view = json.dumps(store.public_suite_view(s)) + json.dumps(public_task_view(t))
    assert SECRET not in view and "expected" not in view
    for p in (store.root / "objects").rglob("*.json"):
        assert SECRET not in p.read_text()
    priv = store.root / "private"
    assert stat.S_IMODE(priv.stat().st_mode) == 0o700 and all(stat.S_IMODE(p.stat().st_mode) == 0o400 for p in priv.iterdir())


@pytest.mark.parametrize("key", ["expected", "answer", "answers", "truth", "expected_answer"])
def test_answer_fields_are_refused_in_public_specifications_and_coverage(store, key):
    with pytest.raises(ValidationError, match="answer fields"):
        TaskSpec(kind="item_set", criterion={"listing": "/courses", "nested": {key: SECRET}}, verifiability="deterministic")
    with pytest.raises(ValidationError, match="answer fields"):
        SuiteRecord(suite_name="s", version=1, site="larkspur", task_sha256s=(H("1"),), selection_rule="r", coverage={key: SECRET}, provenance=prov())


# ----------------------------------------------------------------------------------------------------------------------------- wording categories
def test_wording_categories_enforce_natural_language_rules():
    with pytest.raises(ValidationError, match="unchanged"):
        Wording(customer="Which courses meet on Saturdays?", executed="Which courses have class day 'Saturday'?", category="natural_verifiable")
    with pytest.raises(ValidationError, match="assumptions"):
        Wording(customer="Cheap courses?", executed="Cheap courses?", category="natural_verifiable", assumptions=("fee < $200",))
    with pytest.raises(ValidationError, match="unresolved"):
        Wording(customer="What can I do on a tight budget?", category="natural_underspecified")
    with pytest.raises(ValidationError, match="not executed"):
        Wording(customer="What can I do on a tight budget?", executed="... fee below $180", category="natural_underspecified", unresolved=("budget amount",))
    ok = Wording(customer="What can I do on a tight budget?", category="natural_underspecified", unresolved=("budget amount not stated",))
    assert ok.condition is None                                                 # genuine ambiguity preserved; not executed deterministically
    a = Wording(customer="Which courses are on a tight budget?", executed="... Precisely: course fee of at most $180", category="assisted_restatement", assumptions=("fee <= $180",))
    assert a.condition == "assisted"


def test_category_and_verifiability_must_agree(store):
    with pytest.raises(ValidationError, match="requires verifiability"):
        task(store, wording=Wording(customer="Which course is best for an IT career?", executed="Which course is best for an IT career?", category="natural_judgment"))
    t = task(store, wording=Wording(customer="Which course is best for an IT career?", executed="Which course is best for an IT career?", category="natural_judgment"),
             s=spec(verifiability="rubric"))
    assert t.private_sha256 is None and t.condition == "natural"


# ----------------------------------------------------------------------------------------------------------------------------- approval and freezing
def test_freezing_requires_owner_approval_of_the_exact_suite_version(store):
    s1 = suite(store, [task(store)])
    fsha, s1sha = frozen(store, s1)
    assert store.get("frozen_suite", fsha).suite_sha256 == s1sha
    s2 = suite(store, [task(store, task_id="t2")], version=2)                   # a substantive edit is a new version with a new hash
    s2sha = store.put(s2)
    old_approval = store.get("frozen_suite", fsha).approval_sha256
    with pytest.raises(StoreError, match="exactly this suite"):
        store.put(FrozenSuite(suite_sha256=s2sha, approval_sha256=old_approval, frozen_at="2026-11-02T12:00:00+00:00"))
    rej = store.put(Approval(suite_sha256=s2sha, decision="rejected", approved_at="2026-11-02T12:00:00+00:00"))
    with pytest.raises(StoreError, match="APPROVED"):
        store.put(FrozenSuite(suite_sha256=s2sha, approval_sha256=rej, frozen_at="2026-11-02T12:01:00+00:00"))
    with pytest.raises(ValidationError):
        Approval(suite_sha256=s2sha, decision="approved", approved_at="2026-11-02T12:00:00+00:00", approver_role="llm")


def test_a_manifest_references_only_a_frozen_suite(store):
    s = suite(store, [task(store)])
    ssha = store.put(s)
    with pytest.raises(StoreError, match="no frozen_suite"):
        store.put(manifest(ssha))                                                # an approved-but-unfrozen or draft suite cannot be executed
    fsha, _ = frozen(store, s)
    msha = store.put(manifest(fsha))
    assert store.get("manifest", msha).frozen_suite_sha256 == fsha


# ----------------------------------------------------------------------------------------------------------------------------- statistical plan
def test_confirmatory_plans_need_a_feasible_pre_registered_design():
    assert plan().alpha == 0.05 and plan().unit_of_analysis == "task"
    with pytest.raises(ValidationError, match="feasibility"):
        plan(designation="confirmatory")
    with pytest.raises(ValidationError, match="infeasible"):                     # 4 task pairs: min p = 0.125 > 0.05
        plan(designation="confirmatory", feasibility={"min_achievable_p": min_p_sign_flip(4), "minimum_detectable_effect": 0.5, "feasible": True})
    with pytest.raises(ValidationError, match="does not match"):
        plan(designation="confirmatory", n_tasks=8, feasibility={"min_achievable_p": 0.001, "power": 0.8, "feasible": True})
    ok = plan(designation="confirmatory", n_tasks=8, repetitions=3, feasibility={"min_achievable_p": min_p_sign_flip(8), "power": 0.8, "feasible": True})
    assert ok.feasibility["min_achievable_p"] == 2 / 256
    assert min_p_sign_flip(6) <= 0.05 < min_p_sign_flip(5)                     # necessary, not sufficient


def test_manifest_repetitions_must_match_the_plan(store):
    fsha, _ = frozen(store, suite(store, [task(store)]))
    with pytest.raises(ValidationError, match="repetitions"):
        EvaluationManifest(**{**manifest(fsha).model_dump(), "repetitions": 3})


# ----------------------------------------------------------------------------------------------------------------------------- Stage A / Stage B boundary
def test_stage_a_records_refuse_outcome_input_kinds(store):
    for kind in ("run_result", "trial", "result", "manifest"):
        with pytest.raises(ValidationError, match="Stage A records may not"):
            task(store, inputs=(InputRef(kind=kind, name="x", sha256=H("9")),))
        with pytest.raises(ValidationError, match="Stage A records may not"):
            suite(store, [task(store)], inputs=(InputRef(kind=kind, name="x", sha256=H("9")),))


def test_stage_a_records_cannot_reference_a_stored_stage_b_outcome_even_under_an_allowed_kind(store):
    fsha, _ = frozen(store, suite(store, [task(store)]))
    msha = store.put(manifest(fsha))
    rsha = store.put(RunResult(manifest_sha256=msha, variant="original", condition="natural", summary={"passes": 2}, provenance=prov()))
    for sha in (msha, rsha):
        disguised = suite(store, [task(store)], version=3, inputs=(InputRef(kind="evaluator", name="looks harmless", sha256=sha),))
        with pytest.raises(StoreError, match="Stage A may not depend on agent outcomes"):
            store.put(disguised)


def test_suite_records_always_declare_no_agent_evidence():
    with pytest.raises(ValidationError):
        SuiteRecord(suite_name="s", version=1, site="larkspur", task_sha256s=(H("1"),), selection_rule="r", provenance=prov(), agent_evidence_consulted=True)


def test_stage_a_modules_do_not_import_agent_execution_or_outcomes():
    pkg = Path(B.__file__).parent
    assert B.forbidden_imports(pkg) == []


def test_the_import_check_catches_a_violation(tmp_path):
    pkg = tmp_path / "agent_readiness" / "suites"
    (pkg / "stage_a").mkdir(parents=True)
    (pkg / "records.py").write_text("from ..investigate.trials.runner import run_trial\n")
    (pkg / "stage_a" / "loop.py").write_text("import agent_readiness.hosted.api\nfrom agent_readiness.grading import rescore\n")
    bad = B.forbidden_imports(pkg)
    assert any("investigate.trials.runner" in b for b in bad) and any("hosted.api" in b for b in bad) and any("grading.rescore" in b for b in bad)


def test_the_package_is_isolated_from_production():
    import re
    root = Path(B.__file__).resolve().parents[1]
    pattern = re.compile(r"(agent_readiness\.suites\b|from \.+suites\b|from \.\.?\s+import\s+suites\b)")
    # M8 follow-up: the hosted service runs the lifecycle, but ONLY through the product layer `agent_readiness.lifecycle`; nothing else in
    # production imports the lifecycle store or records directly.
    for pkg in ("hosted", "framework", "diagnostics", "grading", "investigate", "live", "taskeval", "research"):
        offenders = [str(p) for p in (root / pkg).rglob("*.py") if pattern.search(p.read_text())]
        assert offenders == [], offenders
