"""CLI for the Task 015 pilot/experiment driver: plan | run | status. See remediation/experiment.py for the guarantees. `run --mode live` needs the exact manifest hash approval,
--allow-model-calls and META_MODEL_API_KEY; nothing in `plan`, `status` or `run --mode mock` calls a provider or costs anything."""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from .. import budget
from ..scanner.live import Halt
from ..suite import registry
from . import experiment as ex
from .engine import build_report, report_sha256
from .probe import SiteProbe
from .targets import DEFAULT_INITIAL, ManagedTarget


def _factors(spec: str | None) -> dict:
    out = dict(DEFAULT_INITIAL)
    for part in (spec or "").split(","):
        if part.strip():
            k, v = part.split("=")
            out[k.strip()] = v.strip()
    return out


def audit_demo_target(factors: dict) -> dict:
    """Step 1 of the loop: the PRODUCT audits the (unmodified) managed target and generates the finding + recommendation ids the experiment will reference."""
    registry.load_all()
    t = ManagedTarget("demo-shop", "Managed demo electronics storefront (electronics-v1)", dict(factors), [])
    t.start()
    try:
        objective = registry.get_instance(ex.TASKS["T1"]).spec.objective
        return build_report(SiteProbe(t.base_url, allow_private_hosts=True).run(), objective=objective, target="demo-shop")
    finally:
        t.stop()


def prior_stage_from(results_dir: Path) -> dict:
    """Provenance of the pilot this main stage follows: the ORIGINAL frozen gate result is carried verbatim and never re-decided."""
    import hashlib
    results_dir = Path(results_dir)
    files = {n: hashlib.sha256((results_dir / n).read_bytes()).hexdigest() for n in ("rows.jsonl", "pilot-gate.json", "effect-record.json", "ledger.jsonl", "status.json")}
    gate = json.loads((results_dir / "pilot-gate.json").read_text())
    pm = json.loads((results_dir.parent / "manifest.json").read_text())
    return {"pilot_manifest_sha256": pm["manifest_sha256"], "pilot_results_sha256": files, "original_gate_decision": gate["decision"], "original_gate_reason": gate["reason"],
            "erratum": "The original gate said `stop` ('ceiling effect') while the unmodified pilot run FAILED on recall 0.33 after exhausting its step budget: the 'ceiling effect' interpretation was wrong. "
                       "The original result is preserved unchanged; the corrected gate (GATE_V2) applies prospectively to this stage only."}


def main(args) -> None:
    root = Path(args.root)
    try:
        if args.exp_command == "plan":
            out = root / args.stage
            report = json.loads(Path(args.audit).read_text()) if args.audit else audit_demo_target(_factors(args.initial))
            rec = next((r for r in report["recommendations"] if r["id"] == args.recommendation), None) if args.recommendation else next((r for r in report["recommendations"] if r.get("change_id") in ex.CHANGES), None)
            if rec is None:
                raise Halt("the audit produced no applicable recommendation to test")
            probe_sl = ex.StageLedger(root, args.stage, {"limits": {"usd_to_aud": budget.usd_to_aud_rate(budget.load()), "stage_cap_aud": ex.STAGES[args.stage]["stage_cap_aud"]}})
            prior = prior_stage_from(Path(args.pilot_results)) if args.stage == "main" else None
            m = ex.build_manifest(args.stage, report, rec["id"], _factors(args.initial), args.seed, committed_elsewhere_usd=probe_sl.others_committed_usd(), prior_stage=prior)
            ex.save_manifest(out / "manifest.json", m)
            (out / "audit-baseline.json").write_text(json.dumps(report, indent=1))
            cmd = (f"uv run readiness remediation-experiment run --manifest {out / 'manifest.json'} --audit {out / 'audit-baseline.json'} --root {root} --mode live "
                   f"--approve-manifest-sha256 {m['manifest_sha256']} --allow-model-calls")
            print(json.dumps({"stage": args.stage, "manifest": str(out / "manifest.json"), "manifest_sha256": m["manifest_sha256"], "audit_id": m["audit"]["audit_id"],
                              "finding_fingerprints": m["audit"]["finding_fingerprints"], "recommendation_id": m["audit"]["recommendation_id"],
                              "schedule": [(e["run_id"], e["task_code"], e["state"]) for e in m["schedule"]], "limits": m["limits"], "budget_check": m["budget_check"]}, indent=1))
            print("\nPAID COMMAND (needs the owner's explicit approval of this manifest hash; do NOT run otherwise):\n  " + cmd)
            return
        if args.exp_command == "run":
            m = ex.load_manifest(args.manifest)
            report = json.loads(Path(args.audit).read_text())
            if report_sha256(report) != m["audit"]["report_sha256"]:
                raise Halt("the audit report does not match the one the manifest references (it was modified)")
            result = asyncio.run(ex.run_stage(m, root, mode=args.mode, approved_sha=args.approve_manifest_sha256, allow_model_calls=args.allow_model_calls))
            fin = ex.finalize(m, root, report)
            print(json.dumps({**result, "finalize": fin}, indent=1, default=str))
            return
        if args.exp_command == "status":
            m = ex.load_manifest(args.manifest)
            sl = ex.StageLedger(root, m["stage"], m)
            rows = ex.read_rows(root / m["stage"] / "rows.jsonl")
            print(json.dumps({"stage": m["stage"], "manifest_sha256": m["manifest_sha256"], "attempted": len(rows), "scheduled": len(m["schedule"]), "spend": sl.summary(),
                              "rows": [(r["run_id"], r.get("outcome_class"), r.get("passed")) for r in rows]}, indent=1))
    except (Halt, ValueError) as exc:
        print(f"HALT (nothing was sent to any provider unless a run line is shown above): {exc}")
        sys.exit(2)
