import argparse
import asyncio
import json
from pathlib import Path
from .agent import ModelConfig
from .env import load_repo_env
from .evaluator import evaluate
from .runner import run
from .tasks import generate


def _groups():
    """Command groups that own their parser and handler (one module per feature). The original single-site commands below stay here because tests patch `cli.run` / `cli.load_repo_env`."""
    from .experiments import cli_impl as experiments
    from .investigate import cli as investigate
    from .remediation import cli_impl as remediation
    from .scanner import cli as scanner
    from .exp2 import cli as exp2
    from .sites import cli as sites
    from .suite import cli as suite
    return (scanner, suite, remediation, experiments, investigate, sites, exp2)


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
    groups = _groups()
    for group in groups:
        group.register(sub)
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
    for group in groups:
        if args.command in group.COMMANDS:
            return group.main(args)
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
