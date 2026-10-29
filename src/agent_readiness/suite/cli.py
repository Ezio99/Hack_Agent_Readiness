"""`readiness suite ...` and `readiness serve-env` — Task 010 task suite: list, show, scripted smoke, serve an environment variant. (Moved out of cli.py in Task 015f; behaviour unchanged.)"""
from __future__ import annotations

import json
from pathlib import Path

COMMANDS = ("suite", "serve-env")


def register(sub) -> None:
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


def main(args) -> None:
    from . import core as suite_core, registry as suite_registry, runner as suite_runner
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
