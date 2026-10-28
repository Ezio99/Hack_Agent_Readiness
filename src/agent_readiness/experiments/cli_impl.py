from __future__ import annotations

import json
from pathlib import Path

from ..scanner.live import Halt
from . import analysis, design, driver, manifest as manifest_mod, schedule as schedule_mod
from .ledger import ExperimentLedger


def _ledger(args, mode: str, *, stage_ceiling=None, programme=None) -> ExperimentLedger:
    d = Path(args.out) / ("live" if mode == "live" else "mock")
    ceilings = {k: v["stage_ceiling_usd"] for k, v in design.STAGES.items()}
    if stage_ceiling is not None:
        ceilings[args.stage] = min(ceilings[args.stage], stage_ceiling)
    return ExperimentLedger(d, min(design.PROGRAMME_CEILING_USD, programme or design.PROGRAMME_CEILING_USD), ceilings)


def preflight(sched: dict, ledger: ExperimentLedger) -> dict:
    n = len(sched["entries"])
    lo, hi = design.EXPECTED_COST_PER_RUN_USD
    stage = sched["stage"]
    return {"stage": stage, "runs": n, "schedule_hash": sched["schedule_hash"], "purpose": sched["purpose"], "per_run_reservation_usd": design.RUN_RESERVE_USD,
            "expected_calculated_cost_usd": [round(n * lo, 2), round(n * hi, 2)], "absolute_reservation_sum_usd": round(n * design.RUN_RESERVE_USD, 2),
            "stage_ceiling_usd": ledger.stage_ceilings[stage], "programme_ceiling_usd": ledger.ceiling, "committed_usd": ledger.committed(), "stage_remaining_usd": ledger.remaining(stage),
            "note": "reservation sum exceeds the ceiling by design: the ledger halts safely before a run it cannot reserve; expected cost is far below the ceiling. Calculated, not billed."}


def main(args) -> None:
    sched = schedule_mod.build_schedule(args.stage, args.seed)
    cmd = args.experiment_command
    if cmd == "schedule":
        print(json.dumps(sched, indent=1)); return
    if cmd == "manifest":
        m = manifest_mod.build_manifest()
        Path(args.out).mkdir(parents=True, exist_ok=True)
        (Path(args.out) / "manifest.json").write_text(json.dumps(m, indent=1))
        print(json.dumps({"manifest_hash": m["manifest_hash"], "provenance": m["provenance"], "written": str(Path(args.out) / "manifest.json")}, indent=1)); return
    if cmd == "preflight":
        print(json.dumps(preflight(sched, _ledger(args, "live")), indent=1)); return
    if cmd == "status":
        led = _ledger(args, "live")
        print(json.dumps({"committed_usd": led.committed(), "stage_committed_usd": led.committed(args.stage), "unsettled": led.unsettled(), "entries": len(led.entries())}, indent=1)); return
    if cmd == "analyze":
        stage_dir = Path(args.out) / ("live" if (Path(args.out) / "live" / f"stage{args.stage}").exists() else "mock") / f"stage{args.stage}"
        res = analysis.analyze(analysis.load_rows(stage_dir / "results.jsonl"), sched)
        (stage_dir / "analysis.json").write_text(json.dumps(res, indent=1)); (stage_dir / "analysis.md").write_text(analysis.markdown(res))
        print(analysis.markdown(res)); return
    # run
    out = Path(args.out) / args.mode
    frozen_path = Path(args.out) / "manifest.json"
    if not frozen_path.exists():
        raise SystemExit("HALT: freeze a manifest first (readiness experiment manifest)")
    frozen = json.loads(frozen_path.read_text())
    plan = json.loads(args.mock_plan.read_text()) if args.mock_plan else None
    try:
        rep = driver.run_stage(args.stage, sched, frozen, _ledger(args, args.mode, stage_ceiling=args.stage_ceiling_usd, programme=args.programme_ceiling_usd), out, mode=args.mode,
                               mock_plan=plan, allow_model_calls=args.allow_model_calls, approved_schedule_hash=args.approved_schedule_hash, strict_tree=args.mode == "live")
    except Halt as exc:
        print(f"HALT: {exc}"); raise SystemExit(2)
    print(json.dumps({k: rep[k] for k in ("mode", "banner", "stage", "completed", "halted", "halt_reason", "not_started", "partial", "ledger")}, indent=1))
