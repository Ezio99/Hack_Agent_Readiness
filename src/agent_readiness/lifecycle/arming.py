"""Owner arming of the hosted evaluation (M8 follow-up): which frozen suite the product's ONE launch path evaluates, and the owner's explicit paid
authorisation for it. Recorded only at an interactive terminal (over SSH); the operator token can launch an armed evaluation but never arm one.

An arming (write-once, `<STAGE_B>/armings/<arming_id>.json`) binds:
  the owner-approved frozen suite (exact hash) and its site; the website variants (registered snapshots, exact hashes);
  per allowed repetition count (the launch API's only field): the exact manifest (agent, seed, plan, budget), its trial count and per-launch
  reservation (the manifest's worst case plus one per-request bound, because the spend gate can let at most one request settle above its reservation);
  the model configuration; the maximum number of launches and the total it may reserve; the owner's typed attestation (which states all of it).
The active arming is named by `<STAGE_B>/armings/ACTIVE` (written by the CLI only; `disarm` clears it).

Every launch derives, write-once, its own experiment: `<arming_id>-l<N>` with a claim (exclusive create: one job per launch number, ever), a
PaidAuthorization (paid mode; verified by the unchanged `evalruns.authorization.verify`) whose instruction is the owner's attestation verbatim, and its
own durable ledger. A failed or interrupted launch is never retried; its number is used up.

    python -m agent_readiness.lifecycle.arming prepare --frozen larkspur-core@v2 --variants original modified --repetitions 1 --launches 1 --mode paid
    python -m agent_readiness.lifecycle.arming arm     ...same arguments...           # owner, interactive terminal, types the attestation
    python -m agent_readiness.lifecycle.arming status | disarm

Operator budget pool (2026-11): a SEPARATE standing authorisation, recorded once when the owner opens a budget (`hosted.budget open`), that fixes WHAT
the operator's evaluations run (frozen suite, website variants, exact manifests, model) and that they are charged to that budget. It has no launch
count and no per-launch attestation: each operator launch derives its own experiment `<budget>-l<N>` (claim, PaidAuthorization whose instruction is the
owner's pool attestation verbatim, its own ledger), and admission reserves the launch's maximum against the budget, refusing when the budget cannot
cover it. It lives in `<STAGE_B>/budget-pools/` and never reads or changes the judge arming (`armings/ACTIVE`)."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from decimal import ROUND_CEILING, Decimal
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ..evalruns import authorization as AU
from . import sites as S

SCHEMA = "hosted-arming-v1"
RECORDED_BY = "owner at an interactive terminal (agent_readiness.lifecycle.arming arm)"
ARMING_ID = AU.EXPERIMENT_ID                                      # the launch experiment ids append "-l<N>", so ids stay below the experiment-id limit
REPETITIONS = (1, 3, 5)


class ArmingRefused(PermissionError):
    def __init__(self, code: str, detail: str, status: int = 403):
        super().__init__(detail)
        self.code, self.detail, self.status = code, detail, status


class Option(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    repetitions: int
    manifest_sha256: str
    trials: int
    cap_usd: float
    worst_case_usd: float
    reservation_microusd: int


class Arming(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    schema_: Literal["hosted-arming-v1"] = Field(default=SCHEMA, alias="schema")
    arming_id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{2,50}$")
    mode: Literal["paid", "rehearsal"]
    site: str
    frozen_suite: str
    frozen_suite_sha256: str
    variants: tuple[tuple[str, str], ...]
    options: tuple[Option, ...]
    agent: dict
    max_launches: int = Field(gt=0, le=20)
    total_reservation_microusd: int = Field(gt=0)
    attestation: str
    recorded_at: str
    recorded_by: str

    def content(self) -> dict:
        return self.model_dump(mode="json", by_alias=True)

    @property
    def sha256(self) -> str:
        from ..suite.core import canonical_hash
        return canonical_hash(self.content())

    def option(self, repetitions: int) -> Option | None:
        return next((o for o in self.options if o.repetitions == repetitions), None)


# ------------------------------------------------------------------------------------------------------------------------------- locations
def set_stage_b_root(path: Path) -> None:
    """The service's Stage B root (armings, claims, authorisations, ledgers) on the data volume; the worker subprocess inherits it."""
    os.environ["AR_STAGE_B_ROOT"] = str(path)
    AU.STAGE_B = Path(path)


def open_store(path: Path):
    from ..suites.store import WriteOnceStore
    return WriteOnceStore(Path(path))


def executed_tasks(store, frozen_sha: str) -> list[dict]:
    """The frozen suite's deterministic tasks in task-id order, as the hosted workspace lists them (public fields only)."""
    from ..evalruns.manifest import suite_tasks
    _, _, ts = suite_tasks(store, frozen_sha)
    det = sorted((t for t in ts if t.spec.verifiability == "deterministic"), key=lambda t: t.task_id)
    return [{"task": i + 1, "task_id": t.task_id, "question": t.wording.executed, "capability": t.capability,
             "limits": {"max_steps": t.limits.max_steps, "timeout_seconds": t.limits.timeout_seconds, "max_model_requests": t.limits.max_model_requests}}
            for i, t in enumerate(det)]


def root() -> Path:
    return AU.STAGE_B / "armings"


def arming_path(arming_id: str) -> Path:
    if not ARMING_ID.match(arming_id or "") or len(arming_id) > 51:
        raise ArmingRefused("invalid_arming", "arming ids are 3-51 lowercase letters, digits or hyphens", 422)
    return root() / f"{arming_id}.json"


def claims_dir() -> Path:
    return AU.STAGE_B / "launches"


# ------------------------------------------------------------------------------------------------------------------------------- manifests
def select_manifest(store, frozen_sha: str, variants: list[tuple[str, str]], repetitions: int = 1) -> tuple[str, str]:
    """Chosen server-side: the existing manifest of exactly this frozen suite, these variants and this repetition count; else a regression manifest of
    a base manifest with the same repetitions (it may differ ONLY in its variants); else a new manifest with the server's defaults whose hard cap is
    its worst case."""
    from ..evalruns import manifest as MF
    from ..framework.site import get
    from ..suites import plan as PL
    same, base = [], []
    md = store.root / "objects" / "manifest"
    for p in sorted(md.glob("*.json")) if md.is_dir() else []:
        m = store.get("manifest", p.stem)
        if m.frozen_suite_sha256 != frozen_sha or m.repetitions != repetitions:
            continue
        (same if [tuple(v) for v in m.variants] == variants else base).append((m.provenance.created_at, p.stem, m))
    if same:
        return sorted(same)[0][1], "existing manifest for this frozen suite, these website variants and repetitions"
    at = time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime())
    if base:
        _, bsha, _ = sorted(base)[0]
        m, _diff = MF.regression(store, bsha, variants=variants, created_at=at, notes=f"re-evaluation of manifest {bsha} armed for the hosted evaluation")
        return store.put(m), f"regression manifest of {bsha[:12]}: same frozen suite, plan, agent, repetitions and seed; only the website variants differ"
    _, suite, tasks = MF.suite_tasks(store, frozen_sha)
    det = [t for t in tasks if t.spec.verifiability == "deterministic"]
    primary = "natural" if any(t.condition == "natural" for t in det) else "assisted"
    n = sum(t.condition == primary for t in det)
    plan = PL.make_plan(n_tasks=n, repetitions=repetitions, requested="confirmatory", allow_exploratory_fallback=True, sims=500,
                        primary_outcome=f"evidence-supported pass (official grader v1), {primary}-wording condition")
    site = get(suite.site)
    worst = MF.worst_case_usd(det, len(variants), repetitions, MF.PER_REQUEST_CAP_USD)
    m = MF.build(store, frozen_sha, variants=variants, oracle=site.oracle().label, plan=plan, repetitions=repetitions, seed=7, created_at=at,
                 hard_cap_usd=worst, notes="built for the hosted evaluation (hard cap = worst case)")
    return store.put(m), "new manifest with the server's defaults (seed 7; exploratory unless a confirmatory design is feasible; hard cap = worst case)"


def planned_trials(store, manifest) -> int:
    from ..evalruns.manifest import suite_tasks
    _, _, tasks = suite_tasks(store, manifest.frozen_suite_sha256)
    det = [t for t in tasks if t.spec.verifiability == "deterministic" and t.condition in manifest.conditions]
    return len(det) * len(manifest.variants) * manifest.repetitions


def reservation_microusd(manifest) -> int:
    """What a launch reserves against the hosted ceiling: the manifest's worst case (every trial at its request limit, each request at the per-request
    cap) plus one per-request bound, rounded up to whole microdollars. The runner's per-trial caps keep actual spend within the worst case."""
    b = manifest.budget
    total = Decimal(str(min(b["worst_case_reservation_usd"], b["hard_cap_usd"]))) + Decimal(str(b["per_request_cap_usd"]))
    return int((total * 1_000_000).to_integral_value(rounding=ROUND_CEILING))


def registered_variants(site_id: str) -> dict[str, str]:
    return {v["name"]: v["snapshot_sha256"] for v in S.site_view(site_id)["variants"]}


def attestation(a: dict) -> str:
    opts = "; ".join(f"{o['repetitions']} repetition(s): manifest {o['manifest_sha256']}, {o['trials']} trials, reserve US${o['reservation_microusd'] / 1e6:.6f}"
                     for o in a["options"])
    ag = a["agent"]
    verb = "authorise paid evaluations" if a["mode"] == "paid" else "arm zero-cost rehearsals"
    return (f"I am the owner and I {verb} under arming {a['arming_id']}: frozen suite {a['frozen_suite']} {a['frozen_suite_sha256']} on "
            f"{a['site']} ({', '.join(f'{n} {s}' for n, s in a['variants'])}), model {ag['model']} at {ag['endpoint']} (reasoning {ag['reasoning_effort']}, "
            f"{ag['max_completion_tokens']} completion tokens, profile {ag['profile']} {ag['profile_sha256'][:12]}); {opts}; at most {a['max_launches']} "
            f"launch(es) reserving at most US${a['total_reservation_microusd'] / 1e6:.6f} in total")


def plan(store, *, arming_id: str, mode: str, frozen_ref: str, variants: list[str], repetitions: list[int], launches: int, _pool: bool = False) -> dict:
    arming_path(arming_id)
    if not _pool and pool_path(arming_id).exists():
        raise ArmingRefused("id_in_use", f"{arming_id} is a budget pool; launch experiment ids must stay unique", 409)
    if mode not in ("paid", "rehearsal"):
        raise ArmingRefused("invalid_mode", "mode is paid or rehearsal", 422)
    if not repetitions or any(r not in REPETITIONS for r in repetitions) or len(set(repetitions)) != len(repetitions):
        raise ArmingRefused("invalid_repetitions", f"repetitions are a subset of {REPETITIONS}", 422)
    if not 1 <= launches <= 20:
        raise ArmingRefused("invalid_launches", "1-20 launches", 422)
    try:
        frozen_sha = store.resolve("frozen_suite", frozen_ref)
    except Exception:
        raise ArmingRefused("unknown_suite", f"no frozen suite {frozen_ref!r} in this store", 404) from None
    fz = store.get("frozen_suite", frozen_sha)
    suite = store.get("suite", fz.suite_sha256)
    approval = store.get("approval", fz.approval_sha256)
    synthetic = suite.suite_name.startswith("synthetic-") or "SYNTHETIC" in approval.notes
    if mode == "paid" and synthetic:
        raise ArmingRefused("synthetic_suite", "a synthetic fixture suite can never be evaluated with a paid model")
    reg = registered_variants(suite.site)
    if len(variants) != 2 or len(set(variants)) != 2 or any(v not in reg for v in variants):
        raise ArmingRefused("invalid_variants", f"choose two different registered variants of {suite.site}: {', '.join(reg)}", 422)
    pairs = [(v, reg[v]) for v in variants]
    options, bases = [], []
    agent = None
    for r in sorted(repetitions):
        msha, basis = select_manifest(store, frozen_sha, pairs, r)
        m = store.get("manifest", msha)
        agent = m.agent.content()
        options.append({"repetitions": r, "manifest_sha256": msha, "trials": planned_trials(store, m), "cap_usd": float(m.budget["hard_cap_usd"]),
                        "worst_case_usd": float(m.budget["worst_case_reservation_usd"]), "reservation_microusd": reservation_microusd(m)})
        bases.append(f"{r}: {basis}")
    total = max(o["reservation_microusd"] for o in options) * launches
    a = {"arming_id": arming_id, "mode": mode, "site": suite.site, "frozen_suite": frozen_ref, "frozen_suite_sha256": frozen_sha,
         "variants": [list(p) for p in pairs], "options": options, "agent": agent, "max_launches": launches, "total_reservation_microusd": total}
    return {**a, "attestation": attestation(a), "manifest_basis": bases, "approval_sha256": fz.approval_sha256, "approved_at": approval.approved_at, "synthetic": synthetic}


# ------------------------------------------------------------------------------------------------------------------------------- arm (owner, terminal)
def arm(store, *, typed: str, at: str, interactive: bool, **kw) -> Path:
    if not interactive:
        raise ArmingRefused("not_interactive", "an arming can only be recorded by the owner at an interactive terminal")
    p = plan(store, **kw)
    if typed.strip() != p["attestation"]:
        raise ArmingRefused("attestation_mismatch", "the typed attestation does not match exactly; nothing was recorded")
    path = arming_path(p["arming_id"])
    if path.exists():
        raise ArmingRefused("already_armed", f"arming {p['arming_id']} exists (write-once); use a new arming id", 409)
    rec = Arming(**{"schema": SCHEMA, **{k: p[k] for k in ("arming_id", "mode", "site", "frozen_suite", "frozen_suite_sha256", "max_launches", "total_reservation_microusd", "attestation")},
                    "variants": tuple(tuple(v) for v in p["variants"]), "options": tuple(Option(**o) for o in p["options"]), "agent": p["agent"],
                    "recorded_at": at, "recorded_by": RECORDED_BY})
    problems = verify(store, rec)
    if problems:
        raise ArmingRefused("verification_failed", "; ".join(problems))
    root().mkdir(parents=True, exist_ok=True)
    with open(path, "x") as f:
        f.write(json.dumps(rec.content(), indent=1, sort_keys=True))
    os.chmod(path, 0o444)
    _activate(rec.arming_id)
    return path


def _activate(arming_id: str | None) -> None:
    root().mkdir(parents=True, exist_ok=True)
    tmp = root() / "ACTIVE.tmp"
    tmp.write_text(json.dumps({"arming": arming_id, "at": time.time()}))
    os.replace(tmp, root() / "ACTIVE")


def disarm() -> None:
    _activate(None)


def load(arming_id: str) -> Arming:
    return Arming.model_validate(json.loads(arming_path(arming_id).read_text()))


def active() -> Arming | None:
    p = root() / "ACTIVE"
    if not p.is_file():
        return None
    aid = json.loads(p.read_text()).get("arming")
    if not aid:
        return None
    try:
        return load(aid)
    except Exception:
        return None


# ------------------------------------------------------------------------------------------------------------------------------- verify (server)
def verify(store, rec: Arming) -> list[str]:
    """Everything an arming must still satisfy (empty = ok). Run at arming, at service start, at every launch and again in the worker."""
    problems = []
    try:
        fz = store.get("frozen_suite", rec.frozen_suite_sha256)
        suite = store.get("suite", fz.suite_sha256)
        approval = store.get("approval", fz.approval_sha256)
    except Exception as exc:
        return [f"the frozen suite, its approval or suite is not readable ({type(exc).__name__})"]
    if approval.decision != "approved" or approval.suite_sha256 != fz.suite_sha256:
        problems.append("the frozen suite has no owner approval of exactly its hash")
    synthetic = suite.suite_name.startswith("synthetic-") or "SYNTHETIC" in approval.notes
    if rec.mode == "paid" and synthetic:
        problems.append("a synthetic suite can never be evaluated with a paid model")
    if suite.site != rec.site:
        problems.append("the arming's site is not the suite's site")
    reg = registered_variants(rec.site)
    if any(reg.get(n) != s for n, s in rec.variants):
        problems.append("a website variant is not a snapshot registered on this server")
    from ..evalruns.manifest import agent_config
    for o in rec.options:
        try:
            m = store.get("manifest", o.manifest_sha256)
        except Exception:
            problems.append(f"manifest {o.manifest_sha256[:12]} is not in the store")
            continue
        if m.frozen_suite_sha256 != rec.frozen_suite_sha256 or [tuple(v) for v in m.variants] != [tuple(v) for v in rec.variants] or m.repetitions != o.repetitions:
            problems.append(f"manifest {o.manifest_sha256[:12]} is not this suite, these variants and {o.repetitions} repetition(s)")
        if (planned_trials(store, m), reservation_microusd(m), float(m.budget["hard_cap_usd"])) != (o.trials, o.reservation_microusd, o.cap_usd):
            problems.append(f"manifest {o.manifest_sha256[:12]}: trials, cap or reservation differ from the arming")
        if m.agent.content() != rec.agent:
            problems.append("the manifest agent differs from the armed model configuration")
        pinned = agent_config(m.agent.profile)
        if pinned.content() != m.agent.content():
            problems.append("the armed agent is not the pinned agent configuration")
    if isinstance(rec, BudgetPool):
        if rec.attestation != pool_attestation({**rec.content(), "options": [o.model_dump() for o in rec.options], "variants": [list(v) for v in rec.variants]}) \
                or rec.recorded_by != POOL_RECORDED_BY:
            problems.append("the budget pool was not recorded by the owner's terminal confirmation of exactly these terms")
        return problems
    if rec.total_reservation_microusd < max(o.reservation_microusd for o in rec.options):
        problems.append("the total reservation does not cover one launch")
    if rec.attestation != attestation({**rec.content(), "options": [o.model_dump() for o in rec.options], "variants": [list(v) for v in rec.variants]}) or rec.recorded_by != RECORDED_BY:
        problems.append("the arming was not recorded by the owner's terminal attestation of exactly these terms")
    return problems


def claims(arming_id: str) -> list[dict]:
    d = claims_dir()
    return [json.loads(p.read_text()) for p in sorted(d.glob(f"{arming_id}-l*.json"))] if d.is_dir() else []


def launch(store, rec: Arming, *, repetitions: int, job_id: str, at: str) -> dict:
    """Derive ONE launch under the arming: claim the next launch number (exclusive create), and for paid mode write its PaidAuthorization (write-once;
    instruction = the owner's attestation verbatim). Raises ArmingRefused before anything is written if the arming does not allow it."""
    problems = verify(store, rec)
    if problems:
        raise ArmingRefused("arming_invalid", "; ".join(problems))
    opt = rec.option(repetitions)
    if opt is None:
        raise ArmingRefused("repetitions_not_armed", f"{repetitions} repetition(s) are not armed; armed: {', '.join(str(o.repetitions) for o in rec.options)}", 409)
    used = claims(rec.arming_id)
    if len(used) >= rec.max_launches:
        raise ArmingRefused("launches_exhausted", f"all {rec.max_launches} armed launch(es) are used; the owner must arm again", 409)
    if sum(c["reservation_microusd"] for c in used) + opt.reservation_microusd > rec.total_reservation_microusd:
        raise ArmingRefused("arming_total_exhausted", "this launch would exceed the arming's total reservation", 409)
    n = len(used) + 1
    experiment = f"{rec.arming_id}-l{n}"
    claims_dir().mkdir(parents=True, exist_ok=True)
    cp = claims_dir() / f"{experiment}.json"
    claim = {"arming_id": rec.arming_id, "arming_sha256": rec.sha256, "launch": n, "experiment_id": experiment, "job": job_id, "repetitions": repetitions,
             "manifest_sha256": opt.manifest_sha256, "reservation_microusd": opt.reservation_microusd, "mode": rec.mode, "claimed_at": at}
    try:
        with open(cp, "x") as f:
            f.write(json.dumps(claim, sort_keys=True))
    except FileExistsError:
        raise ArmingRefused("launch_conflict", "another launch took this launch number at the same moment; try again", 409) from None
    os.chmod(cp, 0o444)
    auth_path = None
    if rec.mode == "paid":
        led = AU.ledger_dir(experiment) / "ledger.jsonl"
        if led.exists() and led.stat().st_size:
            raise ArmingRefused("ledger_used", "the launch's experiment ledger already has entries; it is never re-run", 409)
        auth = AU.PaidAuthorization(experiment_id=experiment, frozen_suite_sha256=rec.frozen_suite_sha256, manifest_sha256=opt.manifest_sha256,
                                    max_trials=opt.trials, cap_usd=opt.cap_usd, instruction=rec.attestation, recorded_at=at,
                                    recorded_by=f"server, under owner arming {rec.arming_id} ({rec.sha256[:12]}), launch {n} of {rec.max_launches}")
        probs = AU.verify(auth, store, opt.manifest_sha256, planned_trials=opt.trials)
        if probs:
            raise ArmingRefused("verification_failed", "; ".join(probs))
        auth_path = AU.write(auth, AU.STAGE_B / "authorizations")
    return {**claim, "authorization": str(auth_path) if auth_path else None, "trials": opt.trials, "cap_usd": opt.cap_usd, "worst_case_usd": opt.worst_case_usd}


def check_launch(store, job: dict) -> dict:
    """The worker's independent re-check of a launch: its claim names this job, the arming still verifies, the manifest and reservation match, and
    (paid) the authorisation matches the claim and its ledger is unused."""
    lr = job.get("launch") or {}
    cp = claims_dir() / f"{lr.get('experiment_id', '')}.json"
    if not cp.is_file():
        raise ArmingRefused("claim_missing", "the launch has no claim")
    claim = json.loads(cp.read_text())
    if claim.get("job") != job["id"] or claim.get("manifest_sha256") != job["manifest_sha256"] or claim.get("mode") != job["mode"]:
        raise ArmingRefused("claim_mismatch", "this job does not hold the launch's claim")
    if claim.get("budget_pool"):
        rec = load_pool(claim["budget_pool"])
        if rec.sha256 != claim["pool_sha256"]:
            raise ArmingRefused("pool_changed", "the budget pool changed after the launch")
    else:
        rec = load(claim["arming_id"])
        if rec.sha256 != claim["arming_sha256"]:
            raise ArmingRefused("arming_changed", "the arming changed after the launch")
    problems = verify(store, rec)
    if problems:
        raise ArmingRefused("arming_invalid", "; ".join(problems))
    if rec.mode == "paid":
        ap = AU.STAGE_B / "authorizations" / f"{claim['experiment_id']}.json"
        auth = AU.load(ap)
        if auth.manifest_sha256 != claim["manifest_sha256"] or auth.instruction != rec.attestation:
            raise ArmingRefused("authorization_mismatch", "the launch authorisation does not match its claim and arming")
        led = AU.ledger_dir(claim["experiment_id"]) / "ledger.jsonl"
        if led.exists() and led.stat().st_size:
            raise ArmingRefused("ledger_used", "the launch's ledger already has entries; it is never re-run")
        claim["authorization"] = str(ap)
    return claim


def summary(store, rec: Arming | None, admission=None) -> dict | None:
    """Public view of the active arming (no attestation text, no authorisation records)."""
    if rec is None:
        return None
    used = claims(rec.arming_id)
    rem = None
    if admission is not None:
        t = admission.totals()
        rem = t.get("available_microusd", t["ceiling_microusd"] - t["reserved_microusd"])       # settled + outstanding against the ceiling
    try:
        fz = store.get("frozen_suite", rec.frozen_suite_sha256)
        suite = store.get("suite", fz.suite_sha256)
        name = f"{suite.suite_name} v{suite.version}"
    except Exception:
        name = rec.frozen_suite
    left = rec.max_launches - len(used)
    budget_left = rec.total_reservation_microusd - sum(c["reservation_microusd"] for c in used)
    return {"arming_id": rec.arming_id, "arming_sha256": rec.sha256, "mode": rec.mode, "site": rec.site, "suite": name, "frozen_suite": rec.frozen_suite,
            "frozen_suite_sha256": rec.frozen_suite_sha256, "variants": [n for n, _ in rec.variants], "armed_at": rec.recorded_at,
            "launches": {"max": rec.max_launches, "used": len(used), "left": left},
            # authorised launches (the owner's arming) and financial capacity (the hosted ceiling) are separate limits; a launch needs both
            "capacity": None if rem is None else {"available_usd": rem / 1e6, "launches_affordable": [rem // o.reservation_microusd if o.reservation_microusd else None for o in rec.options][0]},
            "options": [{"repetitions": o.repetitions, "trials": o.trials, "reservation_usd": o.reservation_microusd / 1e6, "manifest_sha256": o.manifest_sha256,
                         "available": left > 0 and o.reservation_microusd <= budget_left and (rem is None or o.reservation_microusd <= rem),
                         "fits_hosted_ceiling": None if rem is None else o.reservation_microusd <= rem} for o in rec.options],
            "agent": {k: rec.agent.get(k) for k in ("model", "reasoning_effort", "max_completion_tokens", "profile")}}


# ------------------------------------------------------------------------------------------------------------------------------- operator budget pool
POOL_SCHEMA = "hosted-budget-pool-v1"
POOL_RECORDED_BY = "owner at an interactive terminal (agent_readiness.hosted.budget open)"


class BudgetPool(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    schema_: Literal["hosted-budget-pool-v1"] = Field(default=POOL_SCHEMA, alias="schema")
    budget: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{2,40}$")                     # also the pool id and the launch-experiment prefix
    mode: Literal["paid", "rehearsal"]
    site: str
    frozen_suite: str
    frozen_suite_sha256: str
    variants: tuple[tuple[str, str], ...]
    options: tuple[Option, ...]
    agent: dict
    attestation: str
    recorded_at: str
    recorded_by: str

    def content(self) -> dict:
        return self.model_dump(mode="json", by_alias=True)

    @property
    def sha256(self) -> str:
        from ..suite.core import canonical_hash
        return canonical_hash(self.content())

    def option(self, repetitions: int) -> Option | None:
        return next((o for o in self.options if o.repetitions == repetitions), None)


def pools_root() -> Path:
    return AU.STAGE_B / "budget-pools"


def pool_path(budget: str) -> Path:
    if not ARMING_ID.match(budget or "") or len(budget) > 41:
        raise ArmingRefused("invalid_budget", "budget ids are 3-41 lowercase letters, digits or hyphens", 422)
    return pools_root() / f"{budget}.json"


def pool_attestation(a: dict) -> str:
    opts = "; ".join(f"{o['repetitions']} repetition(s): manifest {o['manifest_sha256']}, {o['trials']} trials, each launch reserves US${o['reservation_microusd'] / 1e6:.6f}"
                     for o in a["options"])
    ag = a["agent"]
    verb = "authorise operator-launched paid evaluations" if a["mode"] == "paid" else "allow operator-launched zero-cost rehearsals"
    return (f"I am the owner and I {verb} charged ONLY to the separate budget {a['budget']}: frozen suite {a['frozen_suite']} {a['frozen_suite_sha256']} on "
            f"{a['site']} ({', '.join(f'{n} {s}' for n, s in a['variants'])}), model {ag['model']} at {ag['endpoint']} (reasoning {ag['reasoning_effort']}, "
            f"{ag['max_completion_tokens']} completion tokens, profile {ag['profile']} {ag['profile_sha256'][:12]}); {opts}; every launch reserves its maximum "
            f"before it starts and settles at its verified actual cost; launches continue only while the budget covers a reservation (no launch count)")


def pool_terms(store, *, budget: str, mode: str, frozen_ref: str, variants: list[str], repetitions: list[int]) -> dict:
    """The pool's exact terms and confirmation text (read-only)."""
    if pool_path(budget).exists():
        raise ArmingRefused("pool_exists", f"the budget pool {budget} is already recorded (write-once)", 409)
    if (root() / f"{budget}.json").exists() or claims(budget):
        raise ArmingRefused("id_in_use", f"{budget} is already an arming id; launch experiment ids must stay unique", 409)
    p = plan(store, arming_id=budget, mode=mode, frozen_ref=frozen_ref, variants=variants, repetitions=repetitions, launches=1, _pool=True)
    a = {"budget": budget, **{k: p[k] for k in ("mode", "site", "frozen_suite", "frozen_suite_sha256", "variants", "options", "agent")}}
    return {**a, "attestation": pool_attestation(a), "manifest_basis": p["manifest_basis"], "synthetic": p["synthetic"]}


def record_pool(store, terms: dict, *, at: str) -> BudgetPool:
    """Write-once (exclusive create). Called by `hosted.budget open` after the owner's typed confirmation, which includes the pool text."""
    rec = BudgetPool(**{"schema": POOL_SCHEMA, **{k: terms[k] for k in ("budget", "mode", "site", "frozen_suite", "frozen_suite_sha256", "attestation")},
                        "variants": tuple(tuple(v) for v in terms["variants"]), "options": tuple(Option(**o) for o in terms["options"]), "agent": terms["agent"],
                        "recorded_at": at, "recorded_by": POOL_RECORDED_BY})
    problems = verify(store, rec)
    if problems:
        raise ArmingRefused("verification_failed", "; ".join(problems))
    pools_root().mkdir(parents=True, exist_ok=True)
    path = pool_path(rec.budget)
    with open(path, "x") as f:
        f.write(json.dumps(rec.content(), indent=1, sort_keys=True))
    os.chmod(path, 0o444)
    return rec


def load_pool(budget: str) -> BudgetPool:
    return BudgetPool.model_validate(json.loads(pool_path(budget).read_text()))


def pools() -> list[BudgetPool]:
    d = pools_root()
    out = []
    for p in sorted(d.glob("*.json")) if d.is_dir() else []:
        try:
            out.append(BudgetPool.model_validate(json.loads(p.read_text())))
        except Exception:
            continue
    return out


def pool_launch(store, pool: BudgetPool, *, repetitions: int, job_id: str, at: str) -> dict:
    """Derive ONE operator launch under the budget pool: the next launch number (exclusive create; no count limit) and, for paid pools, its
    PaidAuthorization (instruction = the owner's pool confirmation verbatim). The budget itself is enforced by admission, before this is called."""
    problems = verify(store, pool)
    if problems:
        raise ArmingRefused("pool_invalid", "; ".join(problems))
    opt = pool.option(repetitions)
    if opt is None:
        raise ArmingRefused("repetitions_not_armed", f"{repetitions} repetition(s) are not part of the budget evaluation", 409)
    n = len(claims(pool.budget)) + 1
    experiment = f"{pool.budget}-l{n}"
    claims_dir().mkdir(parents=True, exist_ok=True)
    cp = claims_dir() / f"{experiment}.json"
    claim = {"budget_pool": pool.budget, "pool_sha256": pool.sha256, "launch": n, "experiment_id": experiment, "job": job_id, "repetitions": repetitions,
             "manifest_sha256": opt.manifest_sha256, "reservation_microusd": opt.reservation_microusd, "mode": pool.mode, "claimed_at": at}
    try:
        with open(cp, "x") as f:
            f.write(json.dumps(claim, sort_keys=True))
    except FileExistsError:
        raise ArmingRefused("launch_conflict", "another launch took this launch number at the same moment; try again", 409) from None
    os.chmod(cp, 0o444)
    auth_path = None
    if pool.mode == "paid":
        led = AU.ledger_dir(experiment) / "ledger.jsonl"
        if led.exists() and led.stat().st_size:
            raise ArmingRefused("ledger_used", "the launch's experiment ledger already has entries; it is never re-run", 409)
        auth = AU.PaidAuthorization(experiment_id=experiment, frozen_suite_sha256=pool.frozen_suite_sha256, manifest_sha256=opt.manifest_sha256,
                                    max_trials=opt.trials, cap_usd=opt.cap_usd, instruction=pool.attestation, recorded_at=at,
                                    recorded_by=f"server, under the owner's budget pool {pool.budget} ({pool.sha256[:12]}), operator launch {n}")
        probs = AU.verify(auth, store, opt.manifest_sha256, planned_trials=opt.trials)
        if probs:
            raise ArmingRefused("verification_failed", "; ".join(probs))
        auth_path = AU.write(auth, AU.STAGE_B / "authorizations")
    return {**claim, "authorization": str(auth_path) if auth_path else None, "trials": opt.trials, "cap_usd": opt.cap_usd, "worst_case_usd": opt.worst_case_usd}


def pool_summary(store, pool: BudgetPool | None, admission=None) -> dict | None:
    """Public view of the operator budget pool: what runs, what each launch reserves, and how many the budget covers now (no launch count)."""
    if pool is None:
        return None
    room = admission.capacity_microusd(pool.budget) if admission is not None and hasattr(admission, "capacity_microusd") else None
    try:
        fz = store.get("frozen_suite", pool.frozen_suite_sha256)
        name = f"{store.get('suite', fz.suite_sha256).suite_name} v{store.get('suite', fz.suite_sha256).version}"
    except Exception:
        name = pool.frozen_suite
    return {"budget": pool.budget, "pool_sha256": pool.sha256, "mode": pool.mode, "site": pool.site, "suite": name, "frozen_suite": pool.frozen_suite,
            "variants": [n for n, _ in pool.variants], "launches_so_far": len(claims(pool.budget)),
            "available_usd": None if room is None else room / 1e6,
            "options": [{"repetitions": o.repetitions, "trials": o.trials, "reservation_usd": o.reservation_microusd / 1e6,
                         "covered": None if room is None else (room // o.reservation_microusd if o.reservation_microusd else None),
                         "available": room is None or o.reservation_microusd <= room} for o in pool.options],
            "agent": {k: pool.agent.get(k) for k in ("model", "reasoning_effort", "max_completion_tokens", "profile")}}


# ------------------------------------------------------------------------------------------------------------------------------- CLI
def _store(path):
    from ..suites.store import WriteOnceStore
    base = Path(os.environ.get("AR_HOSTED_DATA", "/data/hosted"))
    r = Path(path or os.environ.get("AR_LIFECYCLE_STORE") or base / "lifecycle" / "store")
    if not (r / "objects").is_dir():
        raise SystemExit(f"no lifecycle store at {r}")
    return WriteOnceStore(r)


def _admission(path, mode):
    from ..hosted.admission import Admission
    base = Path(os.environ.get("AR_HOSTED_DATA", "/data/hosted"))
    db = Path(path or base / ("rehearsal" if mode == "rehearsal" else "live") / "admission.sqlite")
    return Admission.open_existing(db) if db.is_file() else None


def _print(p: dict, adm) -> None:
    print(f"arming          {p['arming_id']} ({p['mode']})")
    print(f"frozen suite    {p['frozen_suite']} {p['frozen_suite_sha256']} (owner approval {p['approval_sha256'][:12]}, {p['approved_at']}){' SYNTHETIC' if p['synthetic'] else ''}")
    print(f"website         {p['site']}: " + ", ".join(f"{n} {s[:12]}" for n, s in p["variants"]))
    a = p["agent"]
    print(f"model           {a['model']} at {a['endpoint']}, reasoning {a['reasoning_effort']}, {a['max_completion_tokens']} completion tokens, profile {a['profile']}")
    for o, b in zip(p["options"], p["manifest_basis"]):
        print(f"repetitions {o['repetitions']}   manifest {o['manifest_sha256']} ({b.split(': ', 1)[1]}); {o['trials']} trials; worst case US${o['worst_case_usd']}; reserves US${o['reservation_microusd'] / 1e6:.6f}")
    print(f"launches        at most {p['max_launches']}, reserving at most US${p['total_reservation_microusd'] / 1e6:.6f}")
    if adm is not None:
        t = adm.totals()
        rem = t.get("available_microusd", t["ceiling_microusd"] - t["reserved_microusd"])
        fit = [o["repetitions"] for o in p["options"] if o["reservation_microusd"] <= rem]
        afford = min((rem // o["reservation_microusd"] for o in p["options"] if o["reservation_microusd"]), default=None)
        print(f"hosted ceiling  US${t['ceiling_microusd'] / 1e6:.6f}; settled US${t.get('settled_microusd', 0) / 1e6:.6f}; outstanding US${t.get('outstanding_microusd', t['reserved_microusd']) / 1e6:.6f}; "
              f"available US${rem / 1e6:.6f} -> " + (f"fits for repetitions {fit}" if fit else "NO option fits: launches will be refused"))
        if afford is not None:
            print(f"capacity        the hosted budget covers {afford} launch(es) of this size now; this arming authorises at most {p['max_launches']}")
    print(f"attestation     {p['attestation']}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="agent_readiness.lifecycle.arming")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("prepare", "arm"):
        s = sub.add_parser(name)
        s.add_argument("--arming", required=True)
        s.add_argument("--mode", choices=("paid", "rehearsal"), required=True)
        s.add_argument("--frozen", required=True)
        s.add_argument("--variants", nargs=2, required=True)
        s.add_argument("--repetitions", nargs="+", type=int, default=[1])
        s.add_argument("--launches", type=int, default=1)
    sub.add_parser("status")
    sub.add_parser("disarm")
    for s in sub.choices.values():
        s.add_argument("--store")
        s.add_argument("--admission")
    a = ap.parse_args(argv)
    try:
        if a.cmd == "disarm":
            disarm()
            print("disarmed: no hosted evaluation can be launched until the owner arms one")
            return 0
        store = _store(a.store)
        if a.cmd == "status":
            rec = active()
            print(json.dumps({"active": summary(store, rec, _admission(a.admission, rec.mode if rec else "live")), "problems": verify(store, rec) if rec else None}, indent=1))
            return 0
        kw = dict(arming_id=a.arming, mode=a.mode, frozen_ref=a.frozen, variants=a.variants, repetitions=a.repetitions, launches=a.launches)
        p = plan(store, **kw)
        _print(p, _admission(a.admission, a.mode))
        if a.cmd == "prepare":
            print("\nNothing was armed. To arm, run `arm` with the same arguments at an interactive terminal and type the attestation.")
            return 0
        if not sys.stdin.isatty():
            raise ArmingRefused("not_interactive", "arm needs an interactive terminal (ssh -t / docker compose exec -it)")
        typed = input("\nType the attestation exactly to arm (anything else cancels):\n> ")
        from datetime import datetime, timezone
        path = arm(store, typed=typed, at=datetime.now(timezone.utc).isoformat(timespec="seconds"), interactive=sys.stdin.isatty(), **kw)
        print(f"armed and active: {path.name} (write-once). The operator can now launch from the evaluation workspace.")
        return 0
    except ArmingRefused as exc:
        print(f"refused [{exc.code}]: {exc.detail}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
