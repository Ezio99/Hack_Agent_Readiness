import asyncio
from contextlib import asynccontextmanager
from dataclasses import asdict
from copy import deepcopy
import math
import hashlib
import json
from importlib.metadata import version
import os
from pathlib import Path
import platform
import subprocess
import time
from urllib.parse import urlsplit
from .env import scrubbed_environment
from .agent import (ModelConfig, attempt, create_model, profile, validate_output_parser, validate_reasoning_effort,
                    ModelRequestLimitReached)
from .evaluator import evaluate
from .inventory import INVENTORY_HASH, INVENTORY_VERSION
from .recorder import Recorder, utcnow
from .server import local_storefront
from .smoke import smoke
from .tasks import generate
from .storefront import EXPERIMENTAL_ARMS, LISTING_TEMPLATES, VARIANT_AVAIL_ID, VARIANT_ID
from .metrics import run_metrics


@asynccontextmanager
async def target(url, variant=VARIANT_ID):
    if url:
        parsed = urlsplit(url)
        if parsed.scheme not in {"http", "https"} or parsed.hostname not in {"localhost", "127.0.0.1", "::1"} or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("Use a loopback storefront URL without credentials, query or fragment")
        yield url
    else:
        async with local_storefront(variant) as local_url:
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


def provenance_without_key(*names):
    """Version lookup spawns git; do not hand it the model credential."""
    with scrubbed_environment(*names):
        return provenance()


async def run(*, mode="smoke", seed=0, kind="discovery", available=None,
              url=None, model_config=None, allow_model_calls=False,
              output=Path("runs"), max_steps=None, timeout_seconds=None,
              max_model_requests=None, profile_overrides=None, profile_id=None,
              expect_schema_sha256=None, max_estimated_cost_usd=None, max_cumulative_estimated_cost_usd=None,
              storefront_variant=VARIANT_ID):
    config = model_config or ModelConfig()
    recorder = Recorder(Path(output), (os.environ.get(config.key_env, ""),))
    started = time.monotonic()
    task = generate(seed, kind, available)
    effective = profile(profile_id)
    overrides = deepcopy(profile_overrides or {})
    unknown_settings = set(overrides) - set(effective)
    effective.update(overrides)
    if max_steps is not None:
        effective["max_steps"] = max_steps
    if timeout_seconds is not None:
        effective["timeout_seconds"] = timeout_seconds
    if max_model_requests is not None:
        effective["max_model_requests"] = max_model_requests
    record = dict(schema_version="run-v1", run_id=recorder.path.name, mode=mode,
                  task=task.public.model_dump(mode="json"), seed=seed,
                  generation={"seed": seed, "kind": kind, "availability_pool": available},
                  inventory_version=INVENTORY_VERSION, inventory_hash=INVENTORY_HASH,
                  storefront_variant=storefront_variant, browser_version=None,
                  profile=effective,
                  profile_hash=None, configuration_hash=None,
                  limits={key: effective[key] for key in ("max_steps", "timeout_seconds", "max_model_requests")},
                  model_request_count=0,
                  model=asdict(config) if mode == "live" else None,
                  model_parameters={"temperature": None, "frequency_penalty": None,
                                    "sampling": "provider defaults", "max_retries": 0,
                                    "timeout_seconds": effective["model_timeout_seconds"],
                                    "max_completion_tokens": effective["max_completion_tokens"],
                                    "reasoning_effort": effective.get("reasoning_effort") if config.provider == "meta" else None,
                                    "output_parser": effective.get("output_parser"),
                                    } if mode == "live" else None,
                  provenance=provenance_without_key(config.key_env), started_at=utcnow(), status="running", usage=None,
                  action_count=None, steps=None, answer=None, evaluation=None)
    recorder.write("run.json", record)
    recorder.event("run_started", mode=mode, task=task.public.model_dump(mode="json"))
    deadline = None
    try:
        if mode not in {"smoke", "live"}:
            raise ValueError("Mode must be smoke or live")
        if unknown_settings:
            raise ValueError("Unknown profile setting")
        if storefront_variant not in LISTING_TEMPLATES:
            raise ValueError("Unknown storefront variant")
        if mode == "live" and storefront_variant not in EXPERIMENTAL_ARMS:
            raise ValueError("Diagnostic storefront variants are offline-only and cannot be used in live trials")
        if url and storefront_variant != VARIANT_ID:
            raise ValueError("A storefront variant can only be selected for the ephemeral local storefront")
        for name in ("max_steps", "max_model_requests", "max_actions_per_step", "max_completion_tokens",
                     "model_timeout_seconds", "step_timeout_seconds"):
            if type(effective[name]) is not int or effective[name] < 1:
                raise ValueError(f"{name} must be a positive integer")
        validate_reasoning_effort(effective)
        validate_output_parser(effective)
        seconds = effective["timeout_seconds"]
        if type(seconds) not in {int, float} or not math.isfinite(seconds) or seconds <= 0:
            raise ValueError("timeout_seconds must be positive and finite")
        if effective["observation_mode"] != "dom+screenshot" or effective["use_vision"] is not True:
            raise ValueError("Only the DOM + screenshot reference profile is supported")
        viewport = effective["viewport"]
        if not isinstance(viewport, dict) or any(type(viewport.get(k)) is not int or viewport[k] < 1 for k in ("width", "height")):
            raise ValueError("Viewport width and height must be positive integers")
        record["profile_hash"] = hashlib.sha256(json.dumps(effective, sort_keys=True).encode()).hexdigest()
        record["configuration_hash"] = hashlib.sha256(json.dumps(recorder.clean({
            "profile": effective, "model": record["model"], "model_parameters": record["model_parameters"]
        }), sort_keys=True).encode()).hexdigest()
        recorder.write("run.json", record)
        if expect_schema_sha256 or max_estimated_cost_usd is not None or max_cumulative_estimated_cost_usd is not None:
            # Diagnostic experiments: block any outgoing request that departs from the experiment definition.
            recorder.expectations = {
                "schema_sha256": expect_schema_sha256, "task_prompt": task.public.prompt,
                "max_estimated_cost_usd": max_estimated_cost_usd,
                "max_cumulative_estimated_cost_usd": max_cumulative_estimated_cost_usd,
                "max_steps": effective["max_steps"],
                "parameters": {k: effective[k] for k in ("max_completion_tokens", "reasoning_effort") if k in effective}
                              | {"model": config.model}}
            record["diagnostic_expectations"] = {k: v for k, v in recorder.expectations.items() if k != "task_prompt"}
            recorder.write("run.json", record)
        llm = None
        if mode == "live":
            if not allow_model_calls:
                raise ValueError("Model calls disabled; explicit spending approval is required before using --allow-model-calls")
            llm = create_model(config, effective)
        # Setup consumes the same wall-clock budget as browser/model execution.
        remaining = max(0, effective["timeout_seconds"] - (time.monotonic() - started))
        deadline = asyncio.timeout(remaining)
        async with deadline:
            await asyncio.sleep(0)  # Deliver an expired deadline before any browser/model request.
            async with (target(url) if storefront_variant == VARIANT_ID else target(url, storefront_variant)) as actual_url:
                record["storefront_url"] = actual_url
                recorder.write("run.json", record)
                # The model client already holds the key; browser/Playwright children must not inherit it.
                # This mutates process-global os.environ, so it supports only one nonconcurrent run per process.
                with scrubbed_environment(config.key_env):
                    if mode == "smoke":
                        result = await smoke(task.public, actual_url, recorder, effective)
                    else:
                        result = await attempt(task.public, actual_url, llm, recorder, effective)
                record.update(result)
                record["evaluation"] = evaluate(record["answer"], task).model_dump()
    except ModelRequestLimitReached as exc:
        record.update(status="request_limit", stop_reason="model_request_limit", errors=[str(exc)])
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
        record["model_request_count"] = sum(e["kind"] == "model_request" for e in events)
        if any(e["kind"] == "fidelity_violation" for e in events):
            # A blocked diagnostic request outranks later retries that merely hit the request gate.
            record.update(status="diagnostic_fidelity_violation", stop_reason="request blocked before the network")
        elif any(e["kind"] == "estimated_cost_limit" for e in events):
            record.update(status="estimated_cost_limit", stop_reason="cumulative_estimated_cost_limit")
        elif any(e["kind"] == "model_request_limit" for e in events) and record["status"] != "model_output_error":
            # (an unrecovered model_output_error that preceded the designed gate stop keeps its cause)
            record.update(status="request_limit", stop_reason="model_request_limit")
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
        try:  # derived from the trace and private truth; a metrics failure must never mask the run outcome
            record["metrics"] = run_metrics(events, record, task.expected_id, task, storefront_variant == VARIANT_AVAIL_ID)
        except Exception as exc:
            record["metrics"] = {"error": type(exc).__name__}
        recorder.event("run_finished", status=record["status"], errors=record.get("errors", []))
        recorder.write("run.json", record)
        passed = record["evaluation"]["passed"] if record["evaluation"] else None
        recorder.text("summary.md",
            f"# {recorder.path.name}\n\nMode: {mode}\n\nStatus: {record['status']}\n\n"
            f"Independent evaluation: {passed}\n\nElapsed seconds: {record['elapsed_seconds']:.3f}\n\n"
            f"Model request attempts: {record['model_request_count']} / {effective['max_model_requests']}\n\n"
            + ("Scripted credential-free wiring check; not a live agent measurement.\n" if mode == "smoke" else "")
            + "\n" + "\n".join(recorder.clean(record.get("errors", []))) + "\n")
    return recorder.path, recorder.clean(record)
