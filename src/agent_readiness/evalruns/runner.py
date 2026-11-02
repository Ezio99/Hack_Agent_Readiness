"""Stage B: a reusable runner for an approved, frozen suite manifest (lifecycle M5; proposal §4.3).

    prepare(store, manifest_sha, root)   one standard investigation run PER WORDING CONDITION (natural and assisted are never pooled), holding the base
                                         snapshot and profile, a tasks-manifest whose questions are the frozen EXECUTED wordings, the frozen private
                                         outcomes, and per variant a SNAPSHOT-SPECIFIC record: the frozen answer must re-derive on that snapshot and
                                         the executed wording must still pass its gate (gate-nl-1 rules for natural, the full v1 gate for assisted);
                                         otherwise the task is invalidated for that variant with the reason.
    execute(run, store)                  every valid (task, variant, repetition) through the unchanged trial runner (`run_trial`: real Chromium in the
                                         network jail, the snapshot served on loopback), each model request behind the reserve-before-send RequestGate
                                         with the manifest's caps; order counterbalanced from the manifest seed; no retries; halt on a void trial or a
                                         bound violation. Rehearsal = the loopback dev provider (NOT a model). Paid execution is refused (M6).
    report(store, manifest_sha, runs)    official grader v1 (as recorded), post-hoc grader v2 (`grading.rescore`, plus the M2b keys), per-task paired
                                         analysis per condition under the pre-registered plan, separate pre-registered / exploratory / diagnostics
                                         sections, RunResult records in the store, and a public view with no answers.
    audit_public(...)                    scans every public artefact for expected answers.

    python -m agent_readiness.evalruns.rehearse SITE --root DIR      # the full zero-cost chain (Stage A fixture -> synthetic approval -> Stage B)"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import random
import re
from pathlib import Path

from ..agent import ModelConfig
from ..framework import evaluate as FE
from ..framework.site import get
from ..grading import rescore
from ..grading import v2 as G2
from ..investigate.evaluate.design import RULE
from ..investigate.inspect.profile import build_profile
from ..investigate.inspect.stage import run_inspect
from ..investigate.pipeline import Context
from ..investigate.run import InvestigationRun
from ..investigate.sitemodel.snapshot import Snapshot
from ..investigate.taskgen import criteria as C
from ..investigate.taskgen import freeze as freezer
from ..investigate.taskgen.gate import Accepted, Draft, hop_distances
from ..investigate.trials.runner import run_trial
from ..investigate.trials.stage import VOID_STATUSES
from ..spend_gate import RequestGate
from ..suite.core import canonical_hash
from ..suites import plan as PL
from ..suites.records import InputRef, Provenance, RunResult
from ..suites.store import WriteOnceStore
from ..taskeval.v2 import kinds as KD
from ..taskeval.v2.evaluator import LITERAL_FIELD_REASONS
from . import manifest as MF

SCHEMA = "evalruns-v1"
MODES = ("rehearsal", "paid")
NOTICE = ("ZERO-COST REHEARSAL: the agent's replies come from the loopback dev provider, a scripted stand-in built from the frozen tasks (NOT a model; "
          "the manifest's model was not called). This proves the pipeline end to end, not agent or website performance.")


# ------------------------------------------------------------------------------------------------------------------------------- prepare
def resolve_variants(site, manifest, extra: dict[str, Snapshot] | None = None, run_dir: Path | None = None) -> dict[str, Snapshot]:
    out = {}
    for name, sha in manifest.variants:
        snap = (extra or {}).get(name)
        if snap is None and run_dir is not None and (Path(run_dir) / "variants" / name / "index.json").exists():
            snap = Snapshot.load(Path(run_dir) / "variants" / name)
        if snap is None and name in site.variants:
            snap = site.snapshot(name)
        if snap is None:
            raise ValueError(f"no snapshot available for variant {name!r}")
        if snap.sha256 != sha:
            raise ValueError(f"variant {name!r}: snapshot {snap.sha256[:12]} is not the manifest's {sha[:12]}")
        out[name] = snap
    return out


def validity(task, priv: dict, prof: dict, start: str) -> tuple[dict | None, str | None]:
    """The snapshot-specific private record of a frozen task on one variant, or the reason it is invalid there. The question and the expected answer
    never change; only the evidence requirements are re-derived (a fixed site may legitimately move the decisive facts)."""
    try:
        comp = KD.compile_any(priv["criterion"], prof)
    except C.CriterionError as exc:
        return None, f"the criterion no longer compiles on this snapshot ({exc})"
    if comp.truth != priv["truth"]:
        return None, "the expected answer changed on this snapshot"
    v = KD.gate(Draft(task.wording.executed, start, priv["criterion"], "llm"), prof, [])
    if isinstance(v, Accepted):
        hops = v.hops
    elif task.condition == "natural" and v.reason in LITERAL_FIELD_REASONS:          # replaced by gate-nl-1 for natural wording (unchanged wording, unchanged catalogue)
        dist = hop_distances(prof, start)
        hops = {p: dist[p] for p in comp.evidence_paths if p in dist}
    else:
        return None, f"the executed wording no longer passes the acceptance gate on this snapshot ({v.reason})"
    return {**priv, "evidence_paths": list(comp.evidence_paths), "evidence_texts": [list(x) for x in comp.evidence_texts], "detail": comp.detail,
            "min_hops": max(hops.values(), default=0), "distractors": list(comp.distractors)}, None


def _entry(task, priv: dict, start: str) -> dict:
    lim = task.limits
    return {"task_id": task.task_id, "question": task.wording.executed, "start_path": start, "kind": priv["kind"], "source": "frozen-suite", "partition": "holdout",
            "outcome_type": "set" if priv["style"] == "set" else "unique", "answer_schema": freezer._answer_schema(priv["style"]),
            "limits": {"max_steps": lim.max_steps, "timeout_seconds": lim.timeout_seconds, "max_model_requests": lim.max_model_requests},
            "criterion_sha256": canonical_hash(priv["criterion"])}


def prepare(store: WriteOnceStore, manifest_sha: str, root: Path, *, mode: str = "rehearsal", extra_snapshots: dict[str, Snapshot] | None = None,
            label: str = "", resume: bool = False) -> dict[str, InvestigationRun]:
    if mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}")
    manifest = store.get("manifest", manifest_sha)
    frozen, suite, tasks = MF.suite_tasks(store, manifest.frozen_suite_sha256)
    site = get(suite.site)
    snaps = resolve_variants(site, manifest, extra_snapshots)
    base = manifest.variants[0][0]
    profs = {n: build_profile(s) for n, s in snaps.items()}
    runs = {}
    for cond in manifest.conditions:
        ts = sorted((t for t in tasks if t.spec.verifiability == "deterministic" and t.condition == cond), key=lambda t: t.task_id)
        privs = {t.task_id: store.get("private_outcome", t.private_sha256).expected for t in ts}
        per_variant, snapshot_manifests = {}, {}
        for n in snaps:
            valid, excluded = {}, []
            for t in ts:
                p, why = validity(t, privs[t.task_id], profs[n], site.start_path)
                (valid.__setitem__(t.task_id, p) if p else excluded.append({"task_id": t.task_id, "reason": why}))
            per_variant[n] = valid
            snapshot_manifests[n] = {"variant": n, "snapshot_sha256": snaps[n].sha256, "valid_tasks": sorted(valid), "excluded": excluded,
                                     "snapshot_private_sha256": canonical_hash(valid)}
        tm = {"schema": freezer.SCHEMA, "snapshot_sha256": snaps[base].sha256, "agent_profile": manifest.agent.profile,
              "generator": {"id": "evalruns", "manifest_sha256": manifest_sha, "frozen_suite_sha256": manifest.frozen_suite_sha256, "condition": cond},
              "seed": manifest.seed, "tasks": [_entry(t, privs[t.task_id], site.start_path) for t in ts], "evaluation_rule": RULE,
              "counts": {"investigation": 0, "holdout": len(ts)}, "rejections": [], "criteria_sha256": canonical_hash(privs)}
        run_id = f"evalrun-{label + '-' if label else ''}{manifest_sha[:10]}-{cond}"
        if resume and (Path(root) / run_id / "run.json").exists():               # an interrupted rehearsal: reuse the prepared run and its recorded trials
            run = InvestigationRun(Path(root) / run_id)
            if run.state["config"].get("manifest_sha256") != manifest_sha or canonical_hash(run.private("variant-criteria")) != canonical_hash(per_variant):
                raise ValueError(f"{run_id} exists but was prepared for another manifest or snapshot state")
            freezer.load(run)
            runs[cond] = run
            continue
        run = InvestigationRun.create(Path(root), run_id, target=site.id, mode="live", stages=("inspect", "freeze", "trials"),
                                      config={"framework": SCHEMA, "site": site.id, "provider": "dev" if mode == "rehearsal" else "live", "mode": mode, "condition": cond,
                                              "variants": [n for n, _ in manifest.variants], "manifest_sha256": manifest_sha})
        run_inspect(Context(run), snaps[base])
        run.write_private("criteria", privs)
        run.write_private("variant-criteria", per_variant)
        run.write_artifact("tasks-manifest", tm)
        if mode == "rehearsal":
            run.write_artifact("dev-provider", {"loopback_stand_in": True})
        for n, s in snaps.items():
            if n not in site.variants:
                s.save(run.dir / "variants" / n)
        run.write_artifact("snapshot-manifests", snapshot_manifests)
        run.write_artifact("evalrun-provenance", {"schema": SCHEMA, "manifest_sha256": manifest_sha, "frozen_suite_sha256": manifest.frozen_suite_sha256,
                                                   "suite_sha256": frozen.suite_sha256, "approval_sha256": frozen.approval_sha256, "suite": f"{suite.suite_name}@v{suite.version}",
                                                   "site": site.id, "condition": cond, "variants": [list(v) for v in manifest.variants], "agent_declared": manifest.agent.content(),
                                                   "execution_provider": "loopback dev provider (NOT a model)" if mode == "rehearsal" else "manifest agent (paid)",
                                                   "graders": manifest.graders, "plan": manifest.plan.content(), "budget": manifest.budget, "repetitions": manifest.repetitions,
                                                   "seed": manifest.seed, "oracle": manifest.oracle})
        freezer.load(run)                                                  # the frozen tasks, private outcomes and base snapshot verify against each other
        runs[cond] = run
    return runs


# ------------------------------------------------------------------------------------------------------------------------------- execute
def steps(run: InvestigationRun, manifest) -> list[dict]:
    """Counterbalanced from the seed: for each repetition and task, the variant order is a seeded shuffle; only valid (task, variant) pairs run."""
    per_variant = run.private("variant-criteria")
    out = []
    for rep in range(1, manifest.repetitions + 1):
        for t in run.artifact("tasks-manifest")["tasks"]:
            order = [n for n, _ in manifest.variants]
            random.Random(f"{manifest.seed}:{t['task_id']}:{rep}").shuffle(order)
            out += [{"variant": n, "task": t, "rep": rep} for n in order if t["task_id"] in per_variant[n]]
    return out


def _jail(run: InvestigationRun) -> tuple[dict, callable]:
    from ..hosted import jail
    pol = {"hide": [str(Path(os.path.expanduser(p))) for p in MF.JAIL_POLICY["hide"]], "dir": MF.JAIL_POLICY["dir"]}
    path = run.dir / "jail-policy.json"
    path.write_text(json.dumps(pol))
    saved_env, saved_req = os.environ.get(jail.ENV), jail._REQUIRED
    os.environ[jail.ENV] = str(path)
    jail.require()                                                          # from now on an unjailed browser launch is an error

    def restore():
        jail._REQUIRED = saved_req
        if saved_env is None:
            os.environ.pop(jail.ENV, None)
        else:
            os.environ[jail.ENV] = saved_env
    result = jail.selftest()
    if not result.get("ok"):
        restore()
        raise RuntimeError(f"browser jail self-test failed: {result}")
    return result, restore


def _trial_gate_id(cond: str, name: str) -> str:
    return f"{cond}-{name}"


def attempted_trials(ledger, experiment_prefix: str = "") -> set[str]:
    """Trial gate ids with at least one reservation in the durable ledger (a trial that ever reserved counts as attempted, even if interrupted)."""
    return {e["id"].split(":req")[0] for e in ledger.entries() if e["kind"] == "reserve" and ":req" in e["id"]}


def execute(run: InvestigationRun, store: WriteOnceStore, *, extra_snapshots: dict[str, Snapshot] | None = None, authorization: Path | None = None) -> dict:
    """Rehearsal: the loopback dev provider (NOT a model). Paid: ONLY with a matching write-once `PaidAuthorization` (authorization.verify): the
    pinned agent configuration, the experiment's FIXED durable ledger (hard cap = the authorised cap), a scope cap across every trial of the
    experiment, the authorised maximum number of trials counted from that ledger (restart-safe), and no retry of any trial that ever reserved."""
    cfg = run.state["config"]
    manifest_sha = cfg["manifest_sha256"]
    manifest = store.get("manifest", manifest_sha)
    site = get(cfg["site"])
    snaps = resolve_variants(site, manifest, extra_snapshots, run.dir)
    per_variant = run.private("variant-criteria")
    freezer.load(run)
    plan = steps(run, manifest)
    budget = manifest.budget
    paid = cfg["mode"] == "paid"
    auth = None
    if paid:
        from ..ledger import Ledger, preflight
        from . import authorization as AU
        if authorization is None:
            raise PermissionError("paid Stage B execution needs a matching owner authorisation record; none was given")
        auth = AU.load(authorization)
        problems = AU.verify(auth, store, manifest_sha, planned_trials=len(plan))
        if problems:
            raise PermissionError("authorisation mismatch; nothing sent: " + "; ".join(problems))
        ledger = Ledger(AU.ledger_dir(auth.experiment_id), auth.cap_usd)
        run.write_artifact(f"authorization-check-{len(list((run.dir / 'artifacts').glob('authorization-check-*.json'))) + 1}",
                           {"authorization_sha256": auth.sha256, "experiment_id": auth.experiment_id, "planned_trials": len(plan), "verified": True,
                            "ledger_dir": str(AU.ledger_dir(auth.experiment_id))})
        model_config = ModelConfig()
        if (model_config.model, model_config.base_url) != (manifest.agent.model, manifest.agent.endpoint):
            raise PermissionError("the runtime model configuration is not the manifest's pinned agent")
        api_key = preflight(model_config, True)
    else:
        # rehearsal: the dev provider moves no money; its ledger ceiling is the worst case (the per-request and per-trial caps are the rehearsed bounds)
        ledger = run.ledger(max(budget["hard_cap_usd"], budget["worst_case_reservation_usd"]))
    scope = frozenset(_trial_gate_id(cfg["condition"], f"{s['variant']}-{s['task']['task_id']}-r{s['rep']}") for s in plan)
    executed, stopped = [], None
    selftest, restore = _jail(run)
    try:
        def go(model_cfg: ModelConfig, key: str):
            nonlocal stopped
            for st in plan:
                t, v, rep = st["task"], st["variant"], st["rep"]
                name = f"{v}-{t['task_id']}-r{rep}"
                gid = _trial_gate_id(cfg["condition"], name)
                if run.has_artifact(f"trials/{name}"):
                    continue
                if paid:
                    done = attempted_trials(ledger)
                    if gid in done:
                        stopped = f"{name}: reserved before an interruption but has no record; it is never re-run (no retries)"
                        return
                    if len(done) + 1 > auth.max_trials:
                        stopped = f"{name}: the authorised maximum of {auth.max_trials} trials is reached (counted from the durable ledger)"
                        return
                inst = freezer.instance(t, per_variant[v][t["task_id"]], snaps[v].sha256)
                lim = inst.spec.limits
                gate = RequestGate(ledger, gid, run_cap=round(lim.max_model_requests * budget["per_request_cap_usd"], 6), per_request_cap=budget["per_request_cap_usd"],
                                   max_requests=lim.max_model_requests, **({"scope_run_ids": scope, "scope_cap": auth.cap_usd} if paid else {}))
                rec = asyncio.run(run_trial(inst, snaps[v], provider="live", output=run.dir / "trial-data" / name, model_config=model_cfg,
                                            api_key=key, request_gate=gate, label=v, profile_id=manifest.agent.profile))
                trial_dir = str(Path(rec.pop("artifact_path")).relative_to(run.dir))
                run.write_artifact(f"trials/{name}", {**rec, "task_id": t["task_id"], "partition": t["partition"], "repeat": rep, "trial_id": f"{t['task_id']}-r{rep}",
                                                      "trial_dir": trial_dir, "arm": v, "variant": v, "variant_sha256": snaps[v].sha256, "condition": cfg["condition"],
                                                      "gate_id": gid})
                executed.append(name)
                if rec["outcome"]["run_status"] in VOID_STATUSES:
                    stopped = f"{name}: void ({rec['outcome']['run_status']}); remaining trials not run (no retries)"
                    return
                if gate.violation:
                    stopped = f"{name}: spend-gate bound violation; remaining trials not run"
                    return
        if paid:
            go(model_config, api_key)
        else:
            with FE.dev_provider(run) as (_, url):
                go(ModelConfig(base_url=FE._loopback(url)), FE.DEV_KEY)
    finally:
        restore()
    out = {"mode": cfg["mode"], "executed": executed, "planned": len(plan), "stopped": stopped, "jail_selftest": selftest,
           "order": [f"{s['variant']}-{s['task']['task_id']}-r{s['rep']}" for s in plan], **({"authorization_sha256": auth.sha256} if auth else {})}
    run.write_artifact(f"execution-{len(list((run.dir / 'artifacts').glob('execution-*.json'))) + 1}", out)
    return out


# ------------------------------------------------------------------------------------------------------------------------------- results
def _evidence_sha(run: InvestigationRun, trials: list[dict]) -> str | None:
    files = []
    for t in trials:
        d = run.dir / t["trial_dir"]
        if d.is_dir():
            files += [(str(p.relative_to(run.dir)), hashlib.sha256(p.read_bytes()).hexdigest()) for p in sorted(d.rglob("*")) if p.is_file()]
    return canonical_hash(files) if files else None


def condition_results(run: InvestigationRun) -> dict:
    """Official v1 grades as recorded, the v1 reproduction check and post-hoc grader v2 per trial, through `grading.rescore`'s own row grader
    (`_trial_rows`, unchanged). Keys come from `kinds.build_key_any`, which delegates every existing kind to `grading.key.build_key` and keys the
    M2b kinds (`rescore.rescore_run` itself cannot be used: v1 `compile_criterion` raises a validation error, not KeyError_, for unknown kinds)."""
    _, private = freezer.load(run)
    profile = run.artifact("site-profile")
    keys, key_errors = {}, {}
    for tid, priv in sorted(private.items()):
        try:
            keys[tid] = KD.build_key_any(tid, priv, profile)
        except G2.KeyError_ as exc:
            key_errors[tid] = str(exc)
    graded = rescore._trial_rows(run, private, keys)
    rows = []
    for name, r in sorted(graded.items()):
        t = run.artifact(f"trials/{name}")
        v2 = r["v2"]
        rows.append({"trial": name, "variant": t["variant"], "task_id": t["task_id"], "kind": private[t["task_id"]]["kind"], "repeat": t["repeat"],
                     "status": r["run_status"], "void": r["void"], "v1_passed": r["v1"]["passed"], "v1_evidence_backed": r["v1"]["evidence_backed"], "v1_reproduced": r["v1_reproduced"],
                     "v2_passed": (v2 or {}).get("passed"), "v2_evidence_backed": (v2 or {}).get("evidence_backed"), "v2_reasons": (v2 or {}).get("reasons"),
                     "model_requests": t["metrics"]["model_requests"], "page_views": t["metrics"]["page_views"], "steps": t["metrics"]["steps"]})
    return {"rescore_faithful": all(r["v1_reproduced"] for r in graded.values()), "key_errors": sorted(key_errors), "rows": rows,
            "grader_v2": {"id": G2.GRADER_ID, "version": G2.GRADER_VERSION, "code_sha256": G2.code_sha256(), "row_grader": "grading.rescore._trial_rows"}}


def _tally(rows: list[dict], variant: str) -> dict:
    rs = [r for r in rows if r["variant"] == variant and not r["void"]]
    return {"trials": len(rs), "void": sum(r["void"] for r in rows if r["variant"] == variant), "v1_passed": sum(r["v1_passed"] for r in rs),
            "v1_evidence_backed": sum(r["v1_evidence_backed"] for r in rs), "v2_passed": sum(bool(r["v2_passed"]) for r in rs),
            "v2_evidence_backed": sum(bool(r["v2_evidence_backed"]) for r in rs), "model_requests": sum(r["model_requests"] or 0 for r in rs)}


def report(store: WriteOnceStore, manifest_sha: str, runs: dict[str, InvestigationRun], *, created_at: str, diagnostics: bool = True) -> dict:
    manifest = store.get("manifest", manifest_sha)
    variants = [n for n, _ in manifest.variants]
    primary = manifest.conditions[0]
    plan = manifest.plan
    conds, results_store = {}, []
    for cond, run in runs.items():
        res = condition_results(run)
        rows = res["rows"]
        snaps = run.artifact("snapshot-manifests")
        per_task = {}
        for r in rows:
            if not r["void"]:
                per_task.setdefault(r["task_id"], {}).setdefault(r["variant"], []).append(bool(r["v1_evidence_backed"]))
        analysis = PL.analyse(plan, per_task, (variants[0], variants[1])) if len(variants) >= 2 else None
        if analysis and (cond != primary or plan.designation != "confirmatory"):
            analysis = {**analysis, "confirmatory_result": None, "label": "EXPLORATORY: no confirmatory claim may be made" + ("" if cond == primary else f" (secondary condition: {cond})")}
        tallies = {v: _tally(rows, v) for v in variants}
        conds[cond] = {"run": run.state["id"], "tasks": len(run.artifact("tasks-manifest")["tasks"]), "tallies": tallies, "analysis": analysis,
                       "rescore_faithful": res["rescore_faithful"], "unkeyed_for_v2": res["key_errors"],
                       "invalidated": {v: snaps[v]["excluded"] for v in variants if snaps[v]["excluded"]}, "rows": rows,
                       "complete": len(rows) == len(steps(run, manifest))}
        for v in variants:
            trials = [run.artifact(f"trials/{r['trial']}") for r in rows if r["variant"] == v]
            rr = RunResult(manifest_sha256=manifest_sha, variant=v, condition=cond,
                           summary={**tallies[v], "invalidated_tasks": len(snaps[v]["excluded"]), "execution_provider": run.artifact("evalrun-provenance")["execution_provider"],
                                    "official_grader": "v1", "post_hoc_grader": "v2"},
                           evidence_dir_sha256=_evidence_sha(run, trials),
                           provenance=Provenance(created_at=created_at, created_by="system", tool="agent_readiness.evalruns.runner", tool_version=SCHEMA,
                                                 inputs=(InputRef(kind="frozen_suite", name="frozen suite", sha256=manifest.frozen_suite_sha256),
                                                         InputRef(kind="snapshot", name=v, sha256=dict(manifest.variants)[v])),
                                                 notes=f"run {run.state['id']}"))
            results_store.append({"variant": v, "condition": cond, "sha256": store.put(rr)})
    diag = {}
    if diagnostics:
        for cond, run in runs.items():
            diag[cond] = _diagnostics(run, variants)
    pre = ({primary: conds[primary]["analysis"]} if plan.designation == "confirmatory" and primary in conds
           else {"none": "the pre-registered plan is EXPLORATORY (infeasible for confirmatory use under its stated assumptions); no confirmatory analysis"})
    doc = {"schema": SCHEMA, "notice": NOTICE if all(r.state["config"]["mode"] == "rehearsal" for r in runs.values()) else None, "manifest_sha256": manifest_sha,
           "frozen_suite_sha256": manifest.frozen_suite_sha256, "variants": [list(v) for v in manifest.variants], "conditions": list(manifest.conditions), "primary_condition": primary,
           "plan": {"designation": plan.designation, "alpha": plan.alpha, "n_tasks": plan.n_tasks, "repetitions": plan.repetitions, "feasibility": plan.feasibility},
           "preregistered": pre, "exploratory": {c: {k: v for k, v in d.items() if k != "rows"} for c, d in conds.items()},
           "diagnostics": diag, "run_results": results_store, "conditions_pooled": False, "trials": {c: d["rows"] for c, d in conds.items()}}
    return doc


def _diagnostics(run: InvestigationRun, variants: list[str]) -> dict:
    """Phase 4 diagnostics on the run (rehearsal: fixture behaviour, so findings stay hypotheses). Only when the variants are the site's own."""
    try:
        from ..diagnostics import run as D
        site = get(run.state["config"]["site"])
        if list(site.variants) != variants:
            return {"available": False, "reason": "diagnostics compare the site's registered variants; this manifest uses other snapshots"}
        bundle = D.from_framework_run(run.dir)
        bundle["origin"] = "dev_fixture" if run.state["config"]["mode"] == "rehearsal" else "real_model"
        d = D.diagnose(bundle)
        return {"available": True, "summary": d.get("summary"), "findings": len(d.get("findings", [])) if isinstance(d.get("findings"), list) else None}
    except Exception as exc:                                                 # diagnostics are advisory; their failure never affects grades
        return {"available": False, "reason": f"{type(exc).__name__}: {str(exc)[:200]}"}


def public_report(doc: dict) -> dict:
    """No answers anywhere: trial rows carry ids, statuses, grades and counts only (the agent's answers and the expected answers stay private)."""
    out = json.loads(json.dumps(doc, default=str))
    for rows in out["trials"].values():
        for r in rows:
            r.pop("v2_reasons", None)
    return out


# ------------------------------------------------------------------------------------------------------------------------------- leak audit
def _answers(store: WriteOnceStore, frozen_sha: str) -> dict[str, list[str]]:
    _, _, tasks = MF.suite_tasks(store, frozen_sha)
    out = {}
    for t in tasks:
        if t.private_sha256:
            truth = store.get("private_outcome", t.private_sha256).expected["truth"]
            out[t.task_id] = [truth] if isinstance(truth, str) else list(truth)
    return out


def _contains(text: str, answer: str) -> bool:
    return bool(re.search(rf"(?<![\w$]){re.escape(answer)}(?!\w)", text)) if len(answer) >= 4 else json.dumps(answer) in text


def audit_public(store: WriteOnceStore, manifest_sha: str, runs: dict[str, InvestigationRun], public_files: list[Path] = ()) -> dict:
    """Every PUBLIC artefact: store objects (per task: never its own answer; suites, approvals, frozen suites, manifests and run results: no answer
    at all), each run's public artifacts (tasks-manifest per task; snapshot manifests, provenance) and the given public reports (no answer at all)."""
    manifest = store.get("manifest", manifest_sha)
    answers = _answers(store, manifest.frozen_suite_sha256)
    every = sorted({a for v in answers.values() for a in v})
    violations, checked = [], 0
    for path in sorted((store.root / "objects").rglob("*.json")):
        kind, text = path.parent.name, path.read_text()
        checked += 1
        if kind == "task":
            tid = json.loads(text)["task_id"]
            bad = [a for a in answers.get(tid, []) if _contains(text, a)]
        elif kind in ("suite", "approval", "frozen_suite", "manifest", "run_result"):
            bad = [a for a in every if _contains(text, a)]
        else:
            bad = []
        violations += [f"{path.relative_to(store.root)}: {a!r}" for a in bad]
    for run in runs.values():
        tm = run.artifact("tasks-manifest")
        checked += 1
        for t in tm["tasks"]:
            violations += [f"{run.state['id']}/tasks-manifest {t['task_id']}: {a!r}" for a in answers.get(t["task_id"], []) if _contains(json.dumps(t), a)]
        for name in ("snapshot-manifests", "evalrun-provenance"):
            checked += 1
            text = json.dumps(run.artifact(name))
            violations += [f"{run.state['id']}/{name}: {a!r}" for a in every if _contains(text, a)]
    for f in public_files:
        checked += 1
        text = Path(f).read_text()
        violations += [f"{Path(f).name}: {a!r}" for a in every if _contains(text, a)]
    return {"checked": checked, "answers_checked": len(every), "violations": violations, "clean": not violations}
