"""Pipeline stage `baseline_trials`: run every frozen task K times on the frozen snapshot, one attempt each, sequentially, with durable per-trial artifacts.

Spending (`live`) is approval-gated by the pipeline: the manifest below (tasks, repeats, profile, model, caps) is what the owner approves. Every live request passes the durable
reserve-before-send gate; a halt/budget/provider stop is a VOID trial (recorded, never a website result) and ends the stage."""
from __future__ import annotations

import asyncio
from pathlib import Path

from ...agent import ModelConfig
from ...ledger import Halt, preflight
from ...spend_gate import RequestGate
from ..inspect.stage import load_snapshot
from ..pipeline import Context
from .. import allocation as alloc
from ..taskgen import freeze as freezer
from .runner import run_trial

# VOID = the harness / provider / cost guard stopped the run. An agent that hits its OWN step, request or time limit failed the task; that is data (attribution `undetermined`), not a void trial, and never halts the stage.
VOID_STATUSES = ("infrastructure_error", "estimated_cost_limit", "diagnostic_fidelity_violation", "model_output_error", "cancelled")


def arm_config(ctx: Context) -> dict:
    """What every arm (baseline AND patched) must share. Written once, at the baseline; later arms read it and refuse conflicting options, so the patched trials can never run with a different
    repeat count, model or agent profile than the baseline they are compared with."""
    o, tm = ctx.options, ctx.run.artifact("tasks-manifest")
    cfg = o.get("model_config") or ModelConfig()
    return {"repeats": o.get("repeats", 1), "mock_behavior": o.get("mock_behavior", "correct"), "model": cfg.model, "endpoint": cfg.base_url, "agent_profile": tm["agent_profile"]}


def shared_arm_config(ctx: Context) -> dict:
    """The frozen configuration for a LATER arm. Options that disagree with it are refused (not silently ignored)."""
    frozen = ctx.run.artifact("arm-config")
    o = ctx.options
    cfg = o.get("model_config") or ModelConfig()
    for key, given in (("repeats", o.get("repeats")), ("model", cfg.model if o.get("model_config") else None), ("mock_behavior", o.get("mock_behavior"))):
        if given is not None and given != frozen[key]:
            raise ValueError(f"option {key}={given!r} differs from the baseline's frozen {key}={frozen[key]!r}; every arm must use the same configuration")
    return frozen


def manifest(ctx: Context, shared: dict | None = None) -> dict:
    tm = ctx.run.artifact("tasks-manifest")
    o = ctx.options
    cfg = o.get("model_config") or ModelConfig()
    sc = shared or arm_config(ctx)
    return {"stage": "baseline_trials", "snapshot_sha256": tm["snapshot_sha256"], "tasks_manifest_sha256": freezer.canonical_hash(tm), "task_ids": [t["task_id"] for t in tm["tasks"]],
            "repeats": sc["repeats"], "agent_profile": tm["agent_profile"], "model": sc["model"], "endpoint": sc["endpoint"], "run_cap_usd": o.get("run_cap_usd", 0.50),
            "ledger_ceiling_usd": o.get("total_cap_usd", 3.0), "per_request_cap_usd": o.get("per_request_cap_usd", 0.05), "max_requests_per_trial": o.get("max_requests_per_trial", 16),
            "retries": 0, "stage_cap_usd": o.get("baseline_stage_cap_usd", alloc.BASELINE_CAP_USD), "allocation": alloc.allocation(o.get("total_cap_usd", 3.0)),
            "stage_cap_note": "enforced by the spend gate across ALL baseline trials of this stage (reserved + settled, durable across restarts); a trial that would breach it is void and halts the stage",
            "cost_basis": "calculated at published prices; not a bill", "ledger_note": "one shared spend ledger for the whole investigation (taskgen, both trial arms, investigation); this is its hard ceiling"}


def run_plan(ctx: Context, steps: list[dict], *, manifest_: dict, verify=None) -> dict:
    """Run an ORDERED list of trials, one attempt each, sequential, resumable from artifacts, live requests behind the reserve-before-send gate. Each step: `label`, `prefix`, `snap`, `inst`,
    `task` (frozen task dict), `repeat`, `scopes` (list of (run ids, cap, name) enforced by the gate across several trials). `verify(rec, step)` may raise `Halt` after a trial (e.g. a control that
    is not identical to the baseline). The order given is the order executed."""
    run, o = ctx.run, ctx.options
    live = run.mode == "live"
    cfg = o.get("model_config") or ModelConfig()
    key = preflight(cfg, o.get("allow_model_calls", False)) if live else None
    ledger = run.ledger(manifest_["ledger_ceiling_usd"]) if live else None
    done, void, executed = [], [], []
    for st in steps:
        t, prefix, rep = st["task"], st["prefix"], st["repeat"]
        tid = f"{t['task_id']}-r{rep}"
        name = f"trials/{prefix}-{tid}"
        quarantine = f"trials-quarantine/{prefix}-{tid}"
        if run.has_artifact(quarantine):                                                        # an integrity-failed trial is neither accepted nor silently re-run on a restart
            raise Halt(f"trial {prefix}-{tid} failed its integrity check earlier and is quarantined (artifacts/{quarantine}.json); it is not accepted and not re-run: review it explicitly")
        if run.has_artifact(name):
            if verify is not None and run.artifact(name)["outcome"]["run_status"] not in VOID_STATUSES:
                verify(run.artifact(name), st)                                                  # re-verify on resume: an accepted trial must still be identical to its baseline
            done.append(tid)
            continue
        scopes = list(st.get("scopes") or [])
        legacy = len(scopes) == 1 and scopes[0][2] == "stage"                       # the baseline's single, unnamed-arm stage cap keeps its original wiring; named scopes go through `extra_scopes`
        gate = RequestGate(ledger, f"{prefix}-{tid}", run_cap=manifest_["run_cap_usd"], per_request_cap=manifest_["per_request_cap_usd"], max_requests=manifest_["max_requests_per_trial"],
                           scope_run_ids=scopes[0][0] if legacy else None, scope_cap=scopes[0][1] if legacy else None, extra_scopes=() if legacy else tuple(scopes)) if live else None
        out = Path(run.dir) / "trial-data" / f"{prefix}-{tid}"
        rec = asyncio.run(run_trial(st["inst"], st["snap"], provider="live" if live else "mock", mock_behavior=o.get("mock_behavior", "correct"), output=out, model_config=cfg, api_key=key,
                                    request_gate=gate, label=st["label"]))
        trial_dir = str(Path(rec.pop("artifact_path")).relative_to(run.dir))
        record = {**rec, "task_id": t["task_id"], "partition": t["partition"], "repeat": rep, "trial_id": tid, "trial_dir": trial_dir, "arm": st["label"]}
        is_void = rec["outcome"]["run_status"] in VOID_STATUSES
        if verify is not None and not is_void:
            try:
                verify(record, st)                                                              # BEFORE the trial can be accepted as evidence
            except Halt as exc:
                run.write_artifact(quarantine, {**record, "integrity_failure": str(exc)})        # diagnostic evidence preserved (full record; the trial data directory is kept too); never in trials/
                raise
        run.write_artifact(name, record)
        executed.append(f"{prefix}-{tid}")
        (void if is_void else done).append(tid)
        if live and is_void:
            raise Halt(f"trial {prefix}-{tid} ended with {rec['outcome']['run_status']}; stopping the stage (void trial, not a website result)")
        if live and gate is not None and gate.violation:                                         # a settled cost above its reservation closes THIS trial's gate; it must also stop the stage (the next trial gets a fresh gate)
            raise Halt(f"spend gate bound violation in trial {prefix}-{tid}: {gate.violation}; stopping the stage (the trial is kept)")
    return {"trials": len(done), "void": len(void), "executed": executed}


def run_arm(ctx: Context, *, label: str, snap, tasks: list[dict], insts: dict, prefix: str, manifest_: dict, repeats: int, mock_behavior: str = "correct", stage_cap: float | None = None) -> dict:
    """Run every given frozen task K times on `snap`; one attempt each, sequential, resumable from artifacts, live requests behind the reserve-before-send gate."""
    scope = frozenset(f"{prefix}-{t['task_id']}-r{r + 1}" for r in range(repeats) for t in tasks)      # every trial gate of THIS stage; the stage cap spans all of them
    steps = [{"label": label, "prefix": prefix, "snap": snap, "inst": insts[t["task_id"]], "task": t, "repeat": rep + 1, "scopes": [(scope, stage_cap, "stage")] if stage_cap is not None else []}
             for rep in range(repeats) for t in tasks]
    out = run_plan(ctx, steps, manifest_=manifest_)
    return {"trials": out["trials"], "void": out["void"]}


def baseline_trials_stage(ctx: Context) -> dict:
    run = ctx.run
    manifest_, snap = freezer.load(run)[0], load_snapshot(run)
    insts = {i.spec.task_id: i for i in freezer.instances(run)}
    sc = arm_config(ctx)
    run.write_artifact("arm-config", sc)                      # write-once: resuming the baseline with different options raises instead of mixing configurations
    return run_arm(ctx, label="baseline", snap=snap, tasks=manifest_["tasks"], insts=insts, prefix="baseline", manifest_=manifest(ctx), repeats=sc["repeats"], mock_behavior=sc["mock_behavior"],
                   stage_cap=manifest(ctx)["stage_cap_usd"])
