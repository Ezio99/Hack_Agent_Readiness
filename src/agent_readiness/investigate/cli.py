"""`readiness investigate ...` (Task 016). M1 provides only credential-free commands: a scripted end-to-end demonstration, run status, and recording an approval."""
from __future__ import annotations

import json
from pathlib import Path

COMMANDS = ("investigate",)


def register(sub) -> None:
    inv = sub.add_parser("investigate", help="Task 016 autonomous website investigator (M1: scripted demo, status, approvals; no model or network)")
    isub = inv.add_subparsers(dest="investigate_command", required=True)
    demo = isub.add_parser("demo", help="Scripted end-to-end run of the pipeline plumbing (NOT a model run, no website)")
    demo.add_argument("--root", type=Path, default=Path("investigations"))
    demo.add_argument("--id", default="scripted-demo")
    st = isub.add_parser("status", help="Show stages, outcome and pending approvals of an investigation")
    st.add_argument("run_dir", type=Path)
    ap = isub.add_parser("approve", help="Record the owner's approval of an exact stage manifest hash")
    ap.add_argument("run_dir", type=Path)
    ap.add_argument("--stage", required=True)
    ap.add_argument("--sha256", required=True, help="the manifest hash printed by `status`")
    ap.add_argument("--note", required=True)


def main(args) -> None:
    from .run import InvestigationRun
    if args.investigate_command == "demo":
        from .demo import run_demo
        run, rep = run_demo(args.root, args.id)
        print(f"scripted demo finished: {run.dir}  outcome={rep['outcome']}  (mode={run.mode}; {rep['notices'][0]})")
        return
    run = InvestigationRun(args.run_dir)
    if args.investigate_command == "approve":
        print(json.dumps(run.approve(args.stage, args.sha256, args.note), indent=2))
        return
    s = run.state
    print(f"{s['id']}  target={s['target']}  mode={s['mode']}  outcome={run.evidence.outcome()}")
    for name, st in s["stages"].items():
        print(f"  {name:16} {st['status']}" + (f"  needs approval of sha256 {st['manifest_sha256']}" if st["status"] == "awaiting_approval" else ""))
