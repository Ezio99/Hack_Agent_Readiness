"""Wire-schema pinning for suite tasks: the exact response_format schemas Browser Use will send for a task's answer model (no network, no model)."""
from __future__ import annotations

import functools
import tempfile
from pathlib import Path

from ..agent import ModelConfig, create_agent, create_model, prepare_browser_environment, profile
from ..capture import _sha
from ..recorder import Recorder

PROFILE_ID = "suite-v1-compat1"


class _Public:
    def __init__(self, prompt: str):
        self.prompt = prompt


def hashes_for(answer_model) -> dict:
    """{'full': sha, 'done_only': sha} of the optimized JSON schemas for Browser Use's AgentOutput / DoneAgentOutput with ``answer_model``."""
    return dict(_hashes(answer_model))


@functools.lru_cache(maxsize=None)
def _hashes(answer_model) -> tuple[tuple[str, str], ...]:
    prepare_browser_environment()
    from browser_use import Browser
    from browser_use.llm.schema import SchemaOptimizer
    effective = profile(PROFILE_ID)
    model = create_model(ModelConfig(), effective, api_key="synthetic-not-sent")
    with tempfile.TemporaryDirectory() as tmp:
        agent = create_agent(_Public("schema probe"), "http://127.0.0.1:1/", model, Browser(headless=True, enable_default_extensions=False), Recorder(Path(tmp)), effective, answer_model)
        full = SchemaOptimizer.create_optimized_json_schema(agent.AgentOutput, remove_min_items=True)
        done = SchemaOptimizer.create_optimized_json_schema(agent.DoneAgentOutput, remove_min_items=True)
    return (("full", _sha(full)), ("done_only", _sha(done)))
