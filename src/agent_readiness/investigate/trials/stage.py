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
from ..taskgen import freeze as freezer
from .runner import run_trial

VOID_STATUSES = ("infrastructure_error", "timeout", "request_limit", "estimated_cost_limit", "diagnostic_fidelity_violation", "model_output_error", "cancelled")


def manifest(ctx: Context) -> dict:
    tm = ctx.run.artifact("tasks-manifest")
    o = ctx.options
    cfg = o.get("model_config") or ModelConfig()
    return {"stage": "baseline_trials", "snapshot_sha256": tm["snapshot_sha256"], "tasks_manifest_sha256": freezer.canonical_hash(tm), "task_ids": [t["task_id"] for t in tm["tasks"]],
            "repeats": o.get("repeats", 1), "agent_profile": tm["agent_profile"], "model": cfg.model, "endpoint": cfg.base_url, "run_cap_usd": o.get("run_cap_usd", 0.50),
            "stage_cap_usd": o.get("stage_cap_usd", 3.0), "per_request_cap_usd": o.get("per_request_cap_usd", 0.05), "max_requests_per_trial": o.get("max_requests_per_trial", 16),
            "retries": 0, "cost_basis": "calculated at published prices; not a bill"}


def baseline_trials_stage(ctx: Context) -> dict:
    run, o = ctx.run, ctx.options
    manifest_, snap = freezer.load(run)[0], load_snapshot(run)
    insts = {i.spec.task_id: i for i in freezer.instances(run)}
    live = run.mode == "live"
    cfg = o.get("model_config") or ModelConfig()
    key = preflight(cfg, o.get("allow_model_calls", False)) if live else None
    m = manifest(ctx)
    ledger = run.ledger(m["stage_cap_usd"]) if live else None
    done, void = [], []
    for rep in range(o.get("repeats", 1)):
        for t in manifest_["tasks"]:
            tid = f"{t['task_id']}-r{rep + 1}"
            if run.has_artifact(f"trials/baseline-{tid}"):
                done.append(tid)
                continue
            gate = RequestGate(ledger, tid, run_cap=m["run_cap_usd"], per_request_cap=m["per_request_cap_usd"], max_requests=m["max_requests_per_trial"]) if live else None
            out = Path(run.dir) / "trial-data" / tid
            rec = asyncio.run(run_trial(insts[t["task_id"]], snap, provider="live" if live else "mock", mock_behavior=o.get("mock_behavior", "correct"), output=out, model_config=cfg,
                                        api_key=key, request_gate=gate, label="baseline"))
            rec.pop("artifact_path", None)
            run.write_artifact(f"trials/baseline-{tid}", {**rec, "task_id": t["task_id"], "partition": t["partition"], "repeat": rep + 1})
            (void if rec["outcome"]["run_status"] in VOID_STATUSES else done).append(tid)
            if live and rec["outcome"]["run_status"] in VOID_STATUSES:
                raise Halt(f"trial {tid} ended with {rec['outcome']['run_status']}; stopping the stage (void trial, not a website result)")
    return {"trials": len(done), "void": len(void)}
