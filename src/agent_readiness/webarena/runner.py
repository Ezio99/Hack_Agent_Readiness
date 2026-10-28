"""Run one WebArena Verified task with the existing Browser Use reference agent (default suite-v2-compat1) and a recorded HAR, then evaluate officially.
Provider mock = scripted model (no network/credentials); live is deliberately NOT wired in this spike."""
from __future__ import annotations

import time
from pathlib import Path
from urllib.parse import urlsplit

from ..agent import ModelConfig, attempt, create_model, profile
from ..recorder import Recorder, utcnow
from ..scanner import mock
from ..scanner.schema import hashes_for
from .har import NetworkCapture
from .adapter import WAAnswer, WATask, WebArenaShopping

PROFILE_ID = "suite-v2-compat1"


class _Public:
    def __init__(self, prompt: str):
        self.prompt = prompt


async def run_task(shop: WebArenaShopping, task: WATask, *, output: Path, handler_factory, profile_id: str = PROFILE_ID, max_steps: int = 12, max_requests: int = 12, timeout_s: int = 240) -> dict:
    """`handler_factory(task, base_url) -> httpx handler` supplies the scripted model (mock). Returns the private result record (never published)."""
    output = Path(output)
    effective = profile(profile_id)
    effective.update(max_steps=max_steps, max_model_requests=max_requests, timeout_seconds=timeout_s)
    output.mkdir(parents=True, exist_ok=True)
    hashes = hashes_for(WAAnswer)
    recorder = Recorder(output / "trace", ("",))
    recorder.expectations = {"schema_sha256": hashes["full"], "done_only_schema_sha256": hashes["done_only"], "task_prompt": task.prompt(), "max_estimated_cost_usd": 0.04,
                             "max_cumulative_estimated_cost_usd": round(0.04 * max_requests, 4), "max_steps": max_steps,
                             "parameters": {"max_completion_tokens": effective["max_completion_tokens"], "reasoning_effort": effective["reasoning_effort"], "model": ModelConfig().model}}
    llm = create_model(ModelConfig(), effective, api_key="mock-not-a-key")
    mock.attach_mock(llm, handler_factory(task, shop.base_url))
    started = time.monotonic()
    capture = NetworkCapture(output / "network.har")
    att = await attempt(_Public(task.prompt()), task.start_urls[0], llm, recorder, effective, WAAnswer, network_capture=capture)
    har = output / "network.har"
    verdict = shop.evaluate(task.task_id, att["answer"], har) if har.exists() and att["answer"] is not None else {"passed": False, "error": "no HAR or no answer", "evaluators": []}
    return {"mode": "mock", "task_id": task.task_id, "profile": profile_id, "run_status": att["status"], "stop_reason": att["stop_reason"], "answer": att["answer"],
            "model_requests": att.get("model_request_count"), "steps": att.get("steps"), "elapsed_seconds": round(time.monotonic() - started, 2), "official_verdict": verdict,
            "har_present": har.exists(), "har_entries": len(capture.entries), "finished_at": utcnow(), "origin": f"{urlsplit(shop.base_url).scheme}://{urlsplit(shop.base_url).netloc}"}
