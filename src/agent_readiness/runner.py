import asyncio
from contextlib import asynccontextmanager
from dataclasses import asdict
import hashlib
import json
from importlib.metadata import version
import os
from pathlib import Path
import platform
import subprocess
import time
from urllib.parse import urlsplit
from .agent import ModelConfig, attempt, create_model, profile
from .evaluator import evaluate
from .inventory import INVENTORY_HASH, INVENTORY_VERSION
from .recorder import Recorder, utcnow
from .server import local_storefront
from .smoke import smoke
from .tasks import generate
from .storefront import VARIANT_ID


@asynccontextmanager
async def target(url):
    if url:
        parsed = urlsplit(url)
        if parsed.scheme not in {"http", "https"} or parsed.hostname not in {"localhost", "127.0.0.1", "::1"} or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("Use a loopback storefront URL without credentials, query or fragment")
        yield url
    else:
        async with local_storefront() as local_url:
            yield local_url


def provenance():
    root = Path(__file__).parent
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.suffix in {".py", ".json", ".html"}:
            digest.update(str(path.relative_to(root)).encode())
            digest.update(path.read_bytes())
    commit = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True)
    dirty = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True)
    return dict(code_hash=digest.hexdigest(), git_commit=commit.stdout.strip() or None,
                git_dirty=bool(dirty.stdout.strip()), python=platform.python_version(),
                packages={name: version(name) for name in ["agent-readiness", "browser-use", "playwright", "pydantic", "fastapi"]})


async def run(*, mode="smoke", seed=0, kind="discovery", available=None,
              url=None, model_config=None, allow_model_calls=False,
              output=Path("runs"), max_steps=None, timeout_seconds=None):
    config = model_config or ModelConfig()
    recorder = Recorder(Path(output), (os.environ.get(config.key_env, ""),))
    started = time.monotonic()
    task = generate(seed, kind, available)
    effective = profile()
    if max_steps is not None:
        effective["max_steps"] = max_steps
    if timeout_seconds is not None:
        effective["timeout_seconds"] = timeout_seconds
    record = dict(schema_version="run-v1", run_id=recorder.path.name, mode=mode,
                  task=task.public.model_dump(mode="json"), seed=seed,
                  generation={"seed": seed, "kind": kind, "availability_pool": available},
                  inventory_version=INVENTORY_VERSION, inventory_hash=INVENTORY_HASH,
                  storefront_variant=VARIANT_ID, browser_version=None,
                  profile=effective,
                  profile_hash=hashlib.sha256(json.dumps(effective, sort_keys=True).encode()).hexdigest(),
                  model=asdict(config) if mode == "live" else None,
                  model_parameters={"temperature": None, "frequency_penalty": None,
                                    "sampling": "provider defaults", "max_retries": 0,
                                    "max_completion_tokens": effective["max_completion_tokens"]} if mode == "live" else None,
                  provenance=provenance(), started_at=utcnow(), status="running", usage=None,
                  action_count=None, steps=None, answer=None, evaluation=None)
    recorder.write("run.json", record)
    recorder.event("run_started", mode=mode, task=task.public.model_dump(mode="json"))
    deadline = None
    try:
        if mode not in {"smoke", "live"}:
            raise ValueError("Mode must be smoke or live")
        if effective["max_steps"] < 1 or effective["timeout_seconds"] <= 0:
            raise ValueError("Execution limits must be positive")
        llm = None
        if mode == "live":
            if not allow_model_calls:
                raise ValueError("Model calls disabled; explicit spending approval is required before using --allow-model-calls")
            llm = create_model(config)
        deadline = asyncio.timeout(effective["timeout_seconds"])
        async with deadline:
            async with target(url) as actual_url:
                record["storefront_url"] = actual_url
                recorder.write("run.json", record)
                if mode == "smoke":
                    result = await smoke(task.public, actual_url, recorder)
                else:
                    result = await attempt(task.public, actual_url, llm, recorder, effective["max_steps"])
                record.update(result)
                record["evaluation"] = evaluate(record["answer"], task).model_dump()
    except TimeoutError as exc:
        if deadline is not None and deadline.expired():
            record.update(status="timeout", stop_reason="wall_clock_limit", errors=["Run exceeded timeout"])
        else:
            record.update(status="infrastructure_error", stop_reason="operation_timeout",
                          errors=[f"Infrastructure operation timed out before the wall-clock deadline: {exc}"])
    except ValueError as exc:
        record.update(status="setup_error", stop_reason="invalid_configuration", errors=[str(exc)])
    except Exception as exc:
        record.update(status="infrastructure_error", stop_reason=type(exc).__name__, errors=[str(exc)])
    finally:
        # Retain partial evidence/usage even when the model or infrastructure fails.
        events = [json.loads(line) for line in (recorder.path / "trace.jsonl").read_text().splitlines()]
        usages = [e["usage"] for e in events if e["kind"] == "model_response" and e.get("usage")]
        if usages:
            record["usage"] = usages
        results = [e["result"] for e in events if e["kind"] == "step_result"]
        if results:
            record["steps"] = len(results)
            record["action_count"] = sum(len(r.get("result", [])) for r in results)
        versions = [e["version"] for e in events if e["kind"] == "browser_version"]
        record["browser_version"] = versions[-1] if versions else None
        record["navigation"] = [{"url": e["url"], "timestamp": e["timestamp"]}
                                for e in events if e["kind"] == "observation"]
        record.update(finished_at=utcnow(), elapsed_seconds=time.monotonic() - started)
        recorder.event("run_finished", status=record["status"], errors=record.get("errors", []))
        recorder.write("run.json", record)
        passed = record["evaluation"]["passed"] if record["evaluation"] else None
        (recorder.path / "summary.md").write_text(
            f"# {recorder.path.name}\n\nMode: {mode}\n\nStatus: {record['status']}\n\n"
            f"Independent evaluation: {passed}\n\nElapsed seconds: {record['elapsed_seconds']:.3f}\n\n"
            + ("Scripted credential-free wiring check; not a live agent measurement.\n" if mode == "smoke" else "")
            + "\n" + "\n".join(recorder.clean(record.get("errors", []))) + "\n")
    return recorder.path, recorder.clean(record)
