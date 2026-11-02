"""EvaluationManifest builder (lifecycle M4/M5; proposal §4.1).

The manifest names the REAL agent configuration a paid run would use (model, endpoint, reasoning effort, completion cap, profile and its hash, jail
policy hash). A zero-cost rehearsal executes the byte-identical manifest with the loopback dev provider standing in for the model; the execution
provider is recorded in the run, never in the manifest, so the manifest hash is the same for the rehearsal and any later approved paid run.

Regression: re-evaluating the same frozen suite on new snapshots creates a NEW manifest that differs only in its variants (and provenance), with
a diff report; tasks whose answer changed on a new snapshot are invalidated per run by the runner, with the reason."""
from __future__ import annotations

import re

from ..grading import v2 as G2
from ..suite.core import canonical_hash
from ..suites import plan as PL
from ..suites.records import AgentConfig, EvaluationManifest, InputRef, Provenance, StatisticalPlan, TaskRecord, content_hash
from ..suites.store import WriteOnceStore

VERSION = "evalruns-manifest-1"
PROFILE = "suite-v2-compat2"
PER_REQUEST_CAP_USD = 0.044          # as the Larkspur pilot: >= 18 % above the highest per-request bound observed on real bodies
JAIL_POLICY = {"hide": ["~/Projects", "~/.ssh", "~/.claude", "/root"], "dir": "/tmp/arj"}     # '~' expanded at execution time (the hash is portable)
VARIANT_NAME = re.compile(r"^[a-z0-9]{1,24}$")


def agent_config(profile: str = PROFILE) -> AgentConfig:
    from ..agent import ModelConfig, profile as load_profile
    from ..investigate.llm.meta import DEFAULT_REASONING_EFFORT
    eff = load_profile(profile)
    return AgentConfig(model=ModelConfig().model, endpoint=ModelConfig().base_url, reasoning_effort=eff.get("reasoning_effort", DEFAULT_REASONING_EFFORT),
                       max_completion_tokens=int(eff.get("max_completion_tokens") or 4096), profile=profile, profile_sha256=canonical_hash(eff),
                       jail_policy_sha256=canonical_hash(JAIL_POLICY))


def suite_tasks(store: WriteOnceStore, frozen_sha: str) -> tuple[object, object, list[TaskRecord]]:
    frozen = store.get("frozen_suite", frozen_sha)
    suite = store.get("suite", frozen.suite_sha256)
    return frozen, suite, [store.get("task", t) for t in suite.task_sha256s]


def worst_case_usd(tasks: list[TaskRecord], n_variants: int, repetitions: int, per_request_cap: float) -> float:
    return round(sum(t.limits.max_model_requests for t in tasks if t.spec.verifiability == "deterministic") * n_variants * repetitions * per_request_cap, 6)


def build(store: WriteOnceStore, frozen_sha: str, *, variants: list[tuple[str, str]], oracle: str, plan: StatisticalPlan, repetitions: int, seed: int,
          created_at: str, agent: AgentConfig | None = None, per_request_cap_usd: float = PER_REQUEST_CAP_USD, hard_cap_usd: float = 5.0, notes: str = "") -> EvaluationManifest:
    if any(not VARIANT_NAME.match(n) for n, _ in variants) or len({n for n, _ in variants}) != len(variants):
        raise ValueError("variant names: 1-24 lowercase letters or digits, distinct")
    frozen, suite, tasks = suite_tasks(store, frozen_sha)
    det = [t for t in tasks if t.spec.verifiability == "deterministic"]
    if not det:
        raise ValueError("the frozen suite has no deterministic task")
    conditions = tuple(c for c in ("natural", "assisted") if any(t.condition == c for t in det))
    primary = [t for t in det if t.condition == conditions[0]]
    problems = PL.preregistration_check(plan, n_tasks_in_condition=len(primary), repetitions=repetitions)
    if problems:
        raise ValueError("the statistical plan does not fit this manifest: " + "; ".join(problems))
    agent = agent or agent_config()
    worst = worst_case_usd(det, len(variants), repetitions, per_request_cap_usd)
    budget = {"worst_case_reservation_usd": worst, "hard_cap_usd": hard_cap_usd, "per_request_cap_usd": per_request_cap_usd, "within_cap": worst <= hard_cap_usd,
              "basis": "sum over deterministic tasks x variants x repetitions of max_model_requests x per-request cap",
              "paid_execution_approval": None, "note": "a paid run needs a separate, explicit owner approval (M6); a zero-cost rehearsal needs none"}
    inputs = (InputRef(kind="frozen_suite", name=f"{suite.suite_name}@v{suite.version}", sha256=frozen_sha),
              InputRef(kind="suite", name=suite.suite_name, sha256=frozen.suite_sha256),
              *(InputRef(kind="snapshot", name=f"{suite.site}@{n}", sha256=s) for n, s in variants),
              InputRef(kind="profile", name=agent.profile, sha256=agent.profile_sha256),
              *((InputRef(kind="jail_policy", name="evalruns", sha256=agent.jail_policy_sha256),) if agent.jail_policy_sha256 else ()),
              InputRef(kind="plan", name=plan.designation, sha256=content_hash(plan)))
    graders = {"official": G2.GRADER_V1, "post_hoc": [{"id": G2.GRADER_ID, "version": G2.GRADER_VERSION, "code_sha256": G2.code_sha256(),
                                                        "keys": "grading.key.build_key (existing kinds) / taskeval.v2.kinds.build_key_any (ranked_subset, either_of)"}],
               "rule": "official grades never change; post-hoc grades are labelled"}
    m = EvaluationManifest(frozen_suite_sha256=frozen_sha, variants=tuple(variants), conditions=conditions, oracle=oracle, graders=graders, agent=agent,
                           repetitions=repetitions, seed=seed, plan=plan, budget=budget,
                           provenance=Provenance(created_at=created_at, created_by="system", tool="agent_readiness.evalruns.manifest", tool_version=VERSION,
                                                 config_fingerprint=canonical_hash({"conditions": conditions, "primary": conditions[0]})[:16], inputs=inputs,
                                                 notes=notes or f"approval {frozen.approval_sha256}; primary condition {conditions[0]}; conditions analysed separately"))
    return m


def regression(store: WriteOnceStore, base_sha: str, *, variants: list[tuple[str, str]], created_at: str, notes: str = "") -> tuple[EvaluationManifest, dict]:
    """The same frozen suite, plan, agent, repetitions and seed on new snapshots: a new manifest plus its diff to the base manifest."""
    base: EvaluationManifest = store.get("manifest", base_sha)
    m = build(store, base.frozen_suite_sha256, variants=variants, oracle=base.oracle, plan=base.plan, repetitions=base.repetitions, seed=base.seed,
              created_at=created_at, agent=base.agent, per_request_cap_usd=base.budget["per_request_cap_usd"], hard_cap_usd=base.budget["hard_cap_usd"],
              notes=notes or f"regression of manifest {base_sha}")
    a, b = base.content(), m.content()
    changed = sorted(k for k in a if a[k] != b[k] and k != "provenance")
    diff = {"base_manifest_sha256": base_sha, "frozen_suite_sha256": {"base": base.frozen_suite_sha256, "new": m.frozen_suite_sha256, "same": base.frozen_suite_sha256 == m.frozen_suite_sha256},
            "variants": {"base": [list(v) for v in base.variants], "new": [list(v) for v in m.variants]}, "changed_fields": changed,
            "unchanged": sorted(k for k in a if k not in changed and k != "provenance")}
    if set(changed) - {"variants", "budget"}:
        raise ValueError(f"a regression manifest may differ only in variants (and the budget they imply), not {changed}")
    return m, diff
