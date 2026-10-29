"""`readiness scanner ...` — Task 011 protected scanner: serve the API, manage invitations, kill switch, bounded live validation. (Moved out of cli.py in Task 015f; behaviour unchanged.)"""
from __future__ import annotations

from pathlib import Path

COMMANDS = ("scanner",)


def register(sub) -> None:
    scn = sub.add_parser("scanner", help="Task 011 protected scanner (mock by default; live inference is gated and off)")
    scsub = scn.add_subparsers(dest="scanner_command", required=True)
    sserve = scsub.add_parser("serve", help="Run the scanner API (loopback by default)")
    sserve.add_argument("--host", default="127.0.0.1")
    sserve.add_argument("--port", type=int, default=8100)
    sserve.add_argument("--demo-target", action="store_true", help="also register the managed demo storefront 'demo-shop' as an audit target (initial state: stock only on product pages)")
    sinv = scsub.add_parser("invite", help="Create an invitation code (shown once; only its hash is stored)")
    sinv.add_argument("--label", required=True)
    sinv.add_argument("--days", type=float, default=7)
    sinv.add_argument("--redemptions", type=int, default=1)
    sinv.add_argument("--scans", type=int, default=5, help="scan quota per redeemed session")
    srev = scsub.add_parser("revoke", help="Revoke an invitation (and its sessions)")
    srev.add_argument("invitation_id")
    scsub.add_parser("invitations", help="List invitations (hashes never shown)")
    skill = scsub.add_parser("kill", help="Turn the kill switch on/off (blocks new scans, cancels running ones on a live server via the admin API)")
    skill.add_argument("state", choices=["on", "off"])
    lv = scsub.add_parser("live-validate", help="APPROVED bounded live Muse Spark validation (probe first, then 4 fixtures); private outputs under runs/")
    lv.add_argument("stage", choices=["status", "probe", "run"])
    lv.add_argument("--allow-model-calls", action="store_true")
    lv.add_argument("--max-total-usd", type=float, default=2.00)
    lv.add_argument("--dir", type=Path, default=Path("runs/live-validation-011"))


def main(args) -> None:
    if args.scanner_command == "live-validate":       # reads/writes only its own ledger: no scanner config, data dir or dev secret is created
        import json
        from ..agent import ModelConfig as LiveModelConfig
        from ..ledger import DEFAULT_CEILING_USD
        from . import live
        ledger = live.Ledger(args.dir, min(args.max_total_usd, DEFAULT_CEILING_USD))
        try:
            if args.stage == "status":
                print(json.dumps({"committed_usd": ledger.committed(), "ceiling_usd": ledger.ceiling, "probe_ok": ledger.probe_succeeded(), "entries": ledger.entries()}, indent=1))
            elif args.stage == "probe":
                rec = live.run_probe(LiveModelConfig(), ledger, args.dir / "probe", allow_model_calls=args.allow_model_calls)
                print(json.dumps({k: rec.get(k) for k in ("success", "failure_class", "http_status", "finish_reason", "usage", "calculated_cost_usd", "grading", "error")}, indent=1, default=str))
            else:
                print(json.dumps(live.run_fixtures(LiveModelConfig(), ledger, args.dir, allow_model_calls=args.allow_model_calls), indent=1))
        except live.Halt as exc:
            print(f"HALT: {exc}")
            raise SystemExit(2)
        return
    from .service.config import load_config
    cfg = load_config()
    if args.scanner_command == "kill":
        cfg.data_dir.mkdir(parents=True, exist_ok=True)
        (cfg.kill_switch_path.write_text("on") if args.state == "on" else cfg.kill_switch_path.unlink(missing_ok=True))
        print(f"kill switch {args.state} (new scans {'blocked' if args.state == 'on' else 'allowed'})")
        return
    from .service.store import Store
    store = Store(cfg)
    if args.scanner_command == "invite":
        inv, code = store.create_invitation(args.label, args.days, args.redemptions, args.scans)
        print(f"invitation {inv}\ncode: {code}   (shown once; give it to one person; expires in {args.days:g} days)")
    elif args.scanner_command == "revoke":
        store.revoke_invitation(args.invitation_id)
        print("revoked")
    elif args.scanner_command == "invitations":
        for i in store.list_invitations():
            print(i["id"], i["label"], f"redeemed {i['redeemed']}/{i['max_redemptions']}", "REVOKED" if i["revoked"] else "")
    else:
        import uvicorn
        from .service.api import create_scanner_app
        print(f"Scanner API at http://{args.host}:{args.port}/ — live inference {'ENABLED' if cfg.live_available else 'disabled'}; data in {cfg.data_dir}")
        from ..remediation.targets import TargetRegistry
        targets = TargetRegistry.demo().start() if args.demo_target else None
        try:
            uvicorn.run(create_scanner_app(cfg, targets=targets), host=args.host, port=args.port, log_level="warning")
        finally:
            if targets:
                targets.stop()
    return
