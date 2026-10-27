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
    for name in ["generate", "smoke", "run", "evaluate"]:
        cmd = sub.add_parser(name)
        cmd.add_argument("--seed", type=int, default=0)
        cmd.add_argument("--kind", choices=["discovery", "availability"], default="discovery")
        cmd.add_argument("--available", choices=["true", "false"])
        if name == "evaluate":
            cmd.add_argument("answer", type=Path)
        if name in {"smoke", "run"}:
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
    args = parser.parse_args()
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
            allow_model_calls=getattr(args, "allow_model_calls", False)))
        print(json.dumps({"artifact_path": str(path), "status": record["status"],
                          "evaluation": record["evaluation"], "errors": record.get("errors", [])}, indent=2))
        raise SystemExit(0 if record["evaluation"] and record["evaluation"]["passed"] and record["status"] == "completed" else 1)


if __name__ == "__main__":
    main()
