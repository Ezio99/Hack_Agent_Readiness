"""Sequential, ledger-gated, drift-checked execution of a frozen schedule (mock by default).

Never silently repeats an attempt, never retries, never replaces a run. Halts safely (before starting a run) on drift, insufficient budget, kill switch, guard-class
failures, infrastructure-error count, parser-recovery rejection or a run that exceeds its reservation, and always writes an explicit partial-completion report.
Live mode additionally needs --allow-model-calls and the approved schedule hash; it has not been run."""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

from ..agent import ModelConfig
from ..environments.electronics.variants import make_variant
from ..recorder import utcnow
from ..scanner.execute import execute_scan
from ..scanner.live import Halt, preflight
from ..suite import registry
from . import design, manifest as manifest_mod, metrics, schedule as schedule_mod
from .ledger import ExperimentLedger

MOCK_BANNER = "MOCK RESULTS — scripted agent behaviour through the real browser/guard/evaluator; no model was contacted; these say nothing about Muse Spark or any website."


def _append(path: Path, row: dict) -> None:
    with path.open("a") as f:
        f.write(json.dumps(row) + "\n")
        f.flush()
        os.fsync(f.fileno())


def run_stage(stage: int, sched: dict, frozen: dict, ledger: ExperimentLedger, out: Path, *, mode: str = "mock", runner=execute_scan, current_manifest=None,
              mock_plan: dict | None = None, allow_model_calls: bool = False, approved_schedule_hash: str | None = None, approved_manifest_hash: str | None = None, acknowledge_previous_halt: bool = False, model_config: ModelConfig | None = None,
              strict_tree: bool = False, reserve_usd: float = design.RUN_RESERVE_USD) -> dict:
    current_manifest = current_manifest or (lambda: manifest_mod.build_manifest(profile_id=frozen["agent"]["profile_id"]))
    schedule_mod.validate(sched)
    if sched["stage"] != stage:
        raise Halt("schedule stage mismatch")
    config = model_config or ModelConfig()
    api_key = None
    if not manifest_mod.self_hash_ok(frozen):
        raise Halt("the frozen manifest does not match its own hash (edited?)")
    if mode == "live":
        if approved_schedule_hash != sched["schedule_hash"]:
            raise Halt("live execution needs --approved-schedule-hash equal to this schedule's hash")
        if approved_manifest_hash != frozen["manifest_hash"]:
            raise Halt("live execution needs --approved-manifest-hash equal to the frozen manifest's hash (a configuration change invalidates the approval)")
        api_key = preflight(config, allow_model_calls)
    elif mode != "mock":
        raise ValueError("mode must be mock or live")
    registry.load_all()
    stage_dir = Path(out) / f"stage{stage}"
    stage_dir.mkdir(parents=True, exist_ok=True)
    results = stage_dir / "results.jsonl"
    kill = Path(out) / "KILL_SWITCH"
    report = {"mode": mode, "banner": MOCK_BANNER if mode == "mock" else "LIVE", "stage": stage, "schedule_hash": sched["schedule_hash"], "manifest_hash": frozen["manifest_hash"],
              "seed": sched["seed"], "planned": len(sched["entries"]), "started_at": utcnow(), "completed": [], "skipped_previously_attempted": [], "interrupted": None, "halted": False, "halt_reason": None}
    # ---- resume: reconstruct state from persisted results + ledger (never reset by a restart) ----------------------------------------------------
    prior = [json.loads(l) for l in results.read_text().splitlines()] if results.exists() else []
    have_row = {r["run_id"]: r for r in prior if r.get("run_status") != "interrupted"}
    reconciled = []
    for item in ledger.unsettled():
        row = have_row.get(item)
        if row is not None and ledger.reserved(item) is not None:             # crash between writing the result and settling: settle from the persisted result
            ledger.settle(item, row.get("calculated_cost_usd") or 0.0 if row.get("model_requests") else ledger.reserved(item), stage, note="reconciled from persisted result after interruption")
            reconciled.append(item)
    report["reconciled_settlements"] = reconciled
    infra_errors = sum(1 for r in prior if r.get("run_status") in design.INFRA_STOPS or r.get("run_status") == "interrupted")      # unresolved attempts count conservatively
    rejected_by_block: dict = {}
    for r in prior:
        if r.get("run_status") != "interrupted":
            rejected_by_block[r["block"]] = rejected_by_block.get(r["block"], 0) + ((r.get("protocol") or {}).get("recovery_rejected", 0) or 0)
    previous_halts = [r["run_id"] for r in prior if r.get("run_status") in design.GUARD_STOPS] + [i for i in have_row if (ledger.reserved(i) is not None and (have_row[i].get("calculated_cost_usd") or 0) > (ledger.reserved(i) or 0))]
    report["state_reconstructed"] = {"infrastructure_or_unresolved": infra_errors, "recovery_rejected_by_block": dict(rejected_by_block), "previous_guard_halts": previous_halts}

    def finish(reason: str | None = None) -> dict:
        rows = [json.loads(l) for l in results.read_text().splitlines()] if results.exists() else []
        have = {r["run_id"] for r in rows if r.get("run_status") != "interrupted"}
        done = set(report["completed"]) | set(report["skipped_previously_attempted"])
        if report["interrupted"]:
            done.add(report["interrupted"])
        report.update(interrupted_runs=sorted({r["run_id"] for r in rows if r.get("run_status") == "interrupted"}), results_available=len(have), halted=bool(reason), halt_reason=reason, not_started=[e["run_id"] for e in sched["entries"] if e["run_id"] not in done],
                      partial=len(have) < report["planned"],
                      ledger={"committed_usd": ledger.committed(), "stage_committed_usd": ledger.committed(stage), "stage_remaining_usd": ledger.remaining(stage), "unsettled": ledger.unsettled()},
                      finished_at=utcnow(), note="Completed runs are never discarded; partial schedules must be analysed and reported as partial; no retries or replacements were made.")
        (stage_dir / "report.json").write_text(json.dumps(report, indent=1))
        return report

    if previous_halts and not acknowledge_previous_halt:
        return finish("a previous guard-class failure or overrun is recorded (" + ", ".join(previous_halts) + "); resuming needs a new approval (--acknowledge-previous-halt)")
    for entry in sched["entries"]:
        rid = entry["run_id"]
        if ledger.attempted(rid):
            report["skipped_previously_attempted"].append(rid)       # resumability: a recorded attempt is never repeated
            continue
        if kill.exists():
            return finish("kill switch file present")
        found = manifest_mod.drift(frozen, current_manifest(), check_commit=True)
        if not strict_tree:
            found = [d for d in found if "uncommitted" not in d]
        if found:
            return finish("drift: " + "; ".join(found))
        if infra_errors >= design.HALT_INFRA_ERRORS:
            return finish(f"{infra_errors} infrastructure errors")
        try:
            ledger.reserve(rid, reserve_usd, stage)
        except Halt as exc:
            return finish(f"budget: {exc}")
        variant = make_variant(*design.VARIANTS[entry["variant_code"]])
        try:
            rec = asyncio.run(runner(entry["task_id"], variant, provider=mode, mock_behavior=(mock_plan or {}).get(rid, "correct") if mode == "mock" else None,
                                     output=stage_dir / rid, model_config=config, api_key=api_key, profile_id=frozen["agent"]["profile_id"]))
        except BaseException as exc:                                  # interruption / crash: reservation stays counted, never retried
            ledger.interrupted(rid, type(exc).__name__, stage)
            report["interrupted"] = rid
            _append(results, {"run_id": rid, "stage": stage, "mode": mode, "run_status": "interrupted", "error": type(exc).__name__, **{k: entry[k] for k in ("block", "task_code", "variant_code")}})
            if isinstance(exc, (KeyboardInterrupt, SystemExit, asyncio.CancelledError)):
                finish("interrupted: " + type(exc).__name__)
                raise
            infra_errors += 1
            continue
        inst = registry.get_instance(entry["task_id"])
        row = metrics.extract(rec, metrics.trace_events(rec["artifact_path"]), inst, run=entry)
        row["schedule_hash"], row["manifest_hash"], row["finished_at"] = sched["schedule_hash"], frozen["manifest_hash"], utcnow()
        _append(results, row)
        actual = rec["metrics"]["calculated_cost_usd"]
        unknown = rec["outcome"]["run_status"] in design.INFRA_STOPS and rec["metrics"]["model_requests"] == 0 and mode == "live"
        overrun = ledger.settle(rid, reserve_usd if unknown else actual, stage)         # the actual amount is always recorded; an overrun is returned, never clamped
        report["completed"].append(rid)
        status = rec["outcome"]["run_status"]
        if status in design.INFRA_STOPS:
            infra_errors += 1
        rej = (rec.get("protocol") or {}).get("recovery_rejected", 0)
        rejected_by_block[entry["block"]] = rejected_by_block.get(entry["block"], 0) + rej
        if status in design.GUARD_STOPS:
            return finish(f"guard-class failure in {rid}: {status}")
        if overrun > 0:
            report["overrun"] = {"run_id": rid, "reserved_usd": reserve_usd, "actual_usd": actual, "overrun_usd": overrun}
            return finish(f"{rid} exceeded its reservation (US${actual:.3f} > US${reserve_usd:.2f}); overrun US${overrun:.3f} recorded")
        if rejected_by_block[entry["block"]] >= design.HALT_RECOVERY_REJECTED_PER_BLOCK:
            return finish(f"parser recovery rejected >= {design.HALT_RECOVERY_REJECTED_PER_BLOCK} times in block {entry['block']}")
    return finish(None)
