import argparse
import asyncio
import json
from pathlib import Path
from .agent import ModelConfig
from .env import load_repo_env
from .evaluator import evaluate
from .runner import run
from .tasks import generate


def main():
    parser = argparse.ArgumentParser(description="Agent Readiness shopping experiment")
    sub = parser.add_subparsers(dest="command", required=True)
    serve = sub.add_parser("serve")
    serve.add_argument("--port", type=int, default=8000)
    probe = sub.add_parser("probe", help="Independently bounded Meta API compatibility probe")
    probe.add_argument("--stage", choices=["a", "b", "c"], required=True)
    probe.add_argument("--model", default="muse-spark-1.3")
    probe.add_argument("--base-url", default="https://api.meta.ai/v1")
    probe.add_argument("--key-env", default="META_MODEL_API_KEY")
    probe.add_argument("--output", type=Path, default=Path("runs"))
    probe.add_argument("--allow-model-calls", action="store_true", help="Use only after explicit spending approval")
    suite = sub.add_parser("suite", help="Task 010 task suite (credential-free): list, describe, scripted smoke")
    ssub = suite.add_subparsers(dest="suite_command", required=True)
    ssub.add_parser("list", help="List environments, variants and task instances")
    show = ssub.add_parser("show", help="Print a task's PUBLIC spec (never its truth)")
    show.add_argument("task_id")
    smoke = ssub.add_parser("smoke", help="Run the scripted navigator + independent evaluator (NOT a model run)")
    smoke.add_argument("--task", default="all", help="task id or 'all'")
    smoke.add_argument("--variant", help="e.g. availability=detail,specs=fragmented (default: the environment's default variant)")
    smoke.add_argument("--all-variants", action="store_true")
    smoke.add_argument("--output", type=Path, help="write result.json records here (default: print only)")
    senv = sub.add_parser("serve-env", help="Serve a task-suite environment variant locally for manual browsing")
    senv.add_argument("--environment", default="electronics-v1")
    senv.add_argument("--variant", help="e.g. availability=detail,specs=fragmented")
    senv.add_argument("--port", type=int, default=8001)
    scn = sub.add_parser("scanner", help="Task 011 protected scanner (mock by default; live inference is gated and off)")
    scsub = scn.add_subparsers(dest="scanner_command", required=True)
    sserve = scsub.add_parser("serve", help="Run the scanner API (loopback by default)")
    sserve.add_argument("--host", default="127.0.0.1")
    sserve.add_argument("--port", type=int, default=8100)
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
    ex = sub.add_parser("experiment", help="Task 012 experiment infrastructure (mock by default; live needs an approved schedule hash)")
    exsub = ex.add_subparsers(dest="experiment_command", required=True)
    for name in ("manifest", "schedule", "preflight", "run", "analyze", "status"):
        c = exsub.add_parser(name)
        c.add_argument("--stage", type=int, choices=[1, 2], default=1)
        c.add_argument("--seed", type=int)
        c.add_argument("--out", type=Path, default=Path("runs/experiment-012"))
        if name == "run":
            c.add_argument("--mode", choices=["mock", "live"], default="mock")
            c.add_argument("--allow-model-calls", action="store_true")
            c.add_argument("--approved-schedule-hash")
            c.add_argument("--approved-manifest-hash")
            c.add_argument("--acknowledge-previous-halt", action="store_true")
            c.add_argument("--mock-plan", type=Path, help="JSON {run_id: mock behaviour} for mock demonstrations")
            c.add_argument("--programme-ceiling-usd", type=float)
            c.add_argument("--stage-ceiling-usd", type=float)
    pilot = sub.add_parser("pilot", help="Task 006 sequential, resumable, auditable pilot driver")
    psub = pilot.add_subparsers(dest="pilot_command", required=True)
    for pname in ("plan", "status", "run", "resume"):
        pc = psub.add_parser(pname)
        pc.add_argument("--experiment", choices=["006", "007"], default="006", help="Which pre-registered schedule (default 006)")
        pc.add_argument("--state-dir", type=Path, help="Default: runs/pilot-task<experiment>")
        if pname == "plan":
            pc.add_argument("--mode", choices=["live", "smoke"], default="live")
        if pname == "run":
            pc.add_argument("--max-runs", type=int, help="Execute at most this many pending runs")
            pc.add_argument("--allow-model-calls", action="store_true", help="Live pilots only; use only after explicit spending approval")
            pc.add_argument("--approved-schedule-sha256", help="Live pilots only; must equal the approved schedule hash")
            pc.add_argument("--key-env", default="META_MODEL_API_KEY")
        if pname == "resume":
            pc.add_argument("--approval-note", required=True, help="Record of the explicit human approval to continue after a halt")
            pc.add_argument("--new-review-halt-usd", type=float)
    for name in ["generate", "smoke", "run", "evaluate"]:
        cmd = sub.add_parser(name)
        cmd.add_argument("--seed", type=int, default=0)
        cmd.add_argument("--kind", choices=["discovery", "availability", "instock_max"], default="discovery")
        cmd.add_argument("--available", choices=["true", "false"])
        if name == "evaluate":
            cmd.add_argument("answer", type=Path)
        if name == "run":
            from .agent import PROFILE_FILES, DEFAULT_PROFILE_ID
            cmd.add_argument("--profile", choices=sorted(PROFILE_FILES), default=DEFAULT_PROFILE_ID,
                             help="Frozen reference profile (default keeps the strict output contract)")
        if name in {"smoke", "run"}:
            from .storefront import LISTING_TEMPLATES, VARIANT_ID as _BASELINE
            cmd.add_argument("--storefront-variant", choices=sorted(LISTING_TEMPLATES), default=_BASELINE,
                             help="Local storefront variant (default: unchanged baseline; diagnostic variants are offline-only)")
            cmd.add_argument("--url", help="Existing loopback storefront; otherwise start an ephemeral server")
            cmd.add_argument("--output", type=Path, default=Path("runs"))
            cmd.add_argument("--max-steps", type=int)
            cmd.add_argument("--timeout", type=float)
            cmd.add_argument("--max-model-requests", type=int)
        if name == "run":
            cmd.add_argument("--provider", choices=["meta", "openai-compatible"], default="meta")
            cmd.add_argument("--model", default="muse-spark-1.3")
            cmd.add_argument("--base-url", default="https://api.meta.ai/v1")
            cmd.add_argument("--key-env", default="META_MODEL_API_KEY")
            cmd.add_argument("--allow-model-calls", action="store_true", help="Use only after explicit spending approval")
            cmd.add_argument("--expect-schema-sha256", help="Diagnostic: block any request whose response schema differs")
            cmd.add_argument("--max-estimated-cost-usd", type=float, help="Diagnostic: block a request whose worst-case estimate reaches this")
            cmd.add_argument("--max-cumulative-estimated-cost-usd", type=float,
                             help="Diagnostic: block a request that would push the summed worst-case estimates over this")
    args = parser.parse_args()
    if args.command == "experiment":
        from .experiments import cli_impl
        cli_impl.main(args)
        return
    if args.command == "scanner":
        from .scanner.service.config import load_config
        cfg = load_config()
        if args.scanner_command == "live-validate":
            import json as _json
            from .agent import ModelConfig as LiveModelConfig
            from .scanner import live
            ledger = live.Ledger(args.dir, min(args.max_total_usd, live.CEILING_USD))
            try:
                if args.stage == "status":
                    print(_json.dumps({"committed_usd": ledger.committed(), "ceiling_usd": ledger.ceiling, "probe_ok": ledger.probe_succeeded(), "entries": ledger.entries()}, indent=1))
                elif args.stage == "probe":
                    rec = live.run_probe(LiveModelConfig(), ledger, args.dir / "probe", allow_model_calls=args.allow_model_calls)
                    print(_json.dumps({k: rec.get(k) for k in ("success", "failure_class", "http_status", "finish_reason", "usage", "calculated_cost_usd", "grading", "error")}, indent=1, default=str))
                else:
                    print(_json.dumps(live.run_fixtures(LiveModelConfig(), ledger, args.dir, allow_model_calls=args.allow_model_calls), indent=1))
            except live.Halt as exc:
                print(f"HALT: {exc}")
                raise SystemExit(2)
            return
        if args.scanner_command == "kill":
            cfg.data_dir.mkdir(parents=True, exist_ok=True)
            (cfg.kill_switch_path.write_text("on") if args.state == "on" else cfg.kill_switch_path.unlink(missing_ok=True))
            print(f"kill switch {args.state} (new scans {'blocked' if args.state == 'on' else 'allowed'})")
            return
        from .scanner.service.store import Store
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
            from .scanner.service.api import create_scanner_app
            print(f"Scanner API at http://{args.host}:{args.port}/ — live inference {'ENABLED' if cfg.live_available else 'disabled'}; data in {cfg.data_dir}")
            uvicorn.run(create_scanner_app(cfg), host=args.host, port=args.port, log_level="warning")
        return
    if args.command in {"suite", "serve-env"}:
        from .suite import core as suite_core, registry as suite_registry, runner as suite_runner
        suite_registry.load_all()
        if args.command == "serve-env":
            import uvicorn
            variant = suite_runner.parse_variant(args.environment, args.variant)
            print(f"Serving {variant.variant_id} (data {suite_core.ENVIRONMENTS[args.environment].data_version}) at http://127.0.0.1:{args.port}/")
            uvicorn.run(suite_core.ENVIRONMENTS[args.environment].create_app(variant), host="127.0.0.1", port=args.port, log_level="warning")
            return
        if args.suite_command == "list":
            for env in suite_core.ENVIRONMENTS.values():
                print(f"{env.environment_id}  data {env.data_version}")
                for v in env.variants():
                    print(f"  variant {v.variant_id}" + ("  (default)" if v == env.default_variant() else ""))
            for inst in suite_core.all_instances():
                print(f"{inst.spec.task_id:48} {inst.spec.outcome_type:10} {inst.spec.template_id} v{inst.spec.version}")
        elif args.suite_command == "show":
            print(json.dumps(suite_registry.get_instance(args.task_id).spec.public(), indent=2))
        else:
            tasks = suite_registry.instances() if args.task == "all" else [suite_registry.get_instance(args.task)]
            env = suite_core.ENVIRONMENTS["electronics-v1"]
            variants = env.variants() if args.all_variants else [suite_runner.parse_variant("electronics-v1", args.variant)]
            failed = 0
            for variant in variants:
                for inst in tasks:
                    r = suite_runner.run_scripted(inst, variant, args.output)
                    e = r["evaluation"]
                    failed += not (e["passed"] and e["evidence_backed"])
                    print(f"{'PASS' if e['passed'] else 'FAIL'} evidence={'ok' if e['evidence_backed'] else 'MISSING'} {variant.variant_id} {inst.spec.task_id} ({r['page_requests']} page requests) [scripted smoke]")
            raise SystemExit(1 if failed else 0)
        return
    if args.command == "pilot":
        from . import pilot as pilot_driver
        if args.state_dir is None:
            args.state_dir = Path(pilot_driver.DEFAULT_STATE_DIR[args.experiment])
        try:
            if args.pilot_command == "plan":
                state = pilot_driver.plan(args.state_dir, args.mode, args.experiment)
            elif args.pilot_command == "resume":
                state = pilot_driver.resume(args.state_dir, args.approval_note, args.new_review_halt_usd)
            elif args.pilot_command == "run":
                state = pilot_driver.load(args.state_dir)
                if state["mode"] == "live":
                    load_repo_env()
                from .runner import run as run_one
                config = ModelConfig("meta", "muse-spark-1.3", "https://api.meta.ai/v1", args.key_env) if state["mode"] == "live" else None
                state = asyncio.run(pilot_driver.drive(
                    args.state_dir, run_one, mode=state["mode"], allow_model_calls=args.allow_model_calls,
                    approved_schedule_sha256=args.approved_schedule_sha256, max_runs=args.max_runs, model_config=config))
            else:
                state = pilot_driver.load(args.state_dir)
        except pilot_driver.PilotError as exc:
            raise SystemExit(f"pilot: {exc}")
        print(pilot_driver.status_text(state))
        halted = state["halt"] and not state["halt"]["resolved"]
        raise SystemExit(1 if halted else 0)
    if args.command in {"run", "probe"}:
        load_repo_env()
    if args.command == "probe":
        if not args.allow_model_calls:
            raise SystemExit("Model calls disabled; explicit spending approval is required before using --allow-model-calls")
        from .probe import stage_a, stage_b, stage_c
        path, record = {"a": stage_a, "b": stage_b, "c": stage_c}[args.stage](ModelConfig("meta", args.model, args.base_url, args.key_env), args.output)
        print(json.dumps({"artifact_path": str(path), "status": record["status"], "http_status": record["http_status"]}, indent=2))
        raise SystemExit(0 if record["success"] else 1)
    if args.command == "serve":
        import uvicorn
        uvicorn.run("agent_readiness.storefront:app", host="127.0.0.1", port=args.port)
        return
    available = {"true": True, "false": False}.get(args.available)
    if args.command == "generate":
        print(generate(args.seed, args.kind, available).public.model_dump_json(indent=2))
    elif args.command == "evaluate":
        result = evaluate(json.loads(args.answer.read_text()), generate(args.seed, args.kind, available))
        print(result.model_dump_json(indent=2))
        raise SystemExit(0 if result.passed else 1)
    else:
        config = ModelConfig(args.provider, args.model, args.base_url, args.key_env) if args.command == "run" else None
        path, record = asyncio.run(run(mode="live" if args.command == "run" else "smoke",
            seed=args.seed, kind=args.kind, available=available, url=args.url, output=args.output,
            max_steps=args.max_steps, timeout_seconds=args.timeout, max_model_requests=args.max_model_requests, model_config=config,
            allow_model_calls=getattr(args, "allow_model_calls", False),
            profile_id=getattr(args, "profile", None),
            storefront_variant=args.storefront_variant,
            expect_schema_sha256=getattr(args, "expect_schema_sha256", None),
            max_estimated_cost_usd=getattr(args, "max_estimated_cost_usd", None),
            max_cumulative_estimated_cost_usd=getattr(args, "max_cumulative_estimated_cost_usd", None)))
        print(json.dumps({"artifact_path": str(path), "status": record["status"],
                          "evaluation": record["evaluation"], "errors": record.get("errors", [])}, indent=2))
        raise SystemExit(0 if record["evaluation"] and record["evaluation"]["passed"] and record["status"] == "completed" else 1)


if __name__ == "__main__":
    main()
