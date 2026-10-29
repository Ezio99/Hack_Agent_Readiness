"""Credential-free scripted-smoke runner: executes a task instance's scripted navigator against an in-process environment app, evaluates it
independently and writes a versioned result record. Mode is always ``scripted_smoke`` - never confuse it with a model run."""
from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from ..recorder import Recorder
from . import core, registry

MODE = "scripted_smoke"


def page_text(html: str) -> str:
    import html as htmllib, re
    body = re.sub(r"<(script|style)\b.*?</\1>", " ", html, flags=re.S)
    return re.sub(r"\s+", " ", htmllib.unescape(re.sub(r"<[^>]+>", " ", body))).strip()


def run_scripted(instance: core.TaskInstance, variant: core.Variant, output: Path | None = None) -> dict:
    registry.load_all()
    from ..environments.electronics.scripted import solve
    env = core.ENVIRONMENTS[instance.spec.environment_id]
    visited: list[str] = []
    observed: list[core.Observation] = []
    client = TestClient(env.create_app(variant), base_url="http://shop.local")

    def fetch(path: str) -> str:
        visited.append(path)
        response = client.get(path)
        response.raise_for_status()
        observed.append(core.Observation(path.split("?", 1)[0], page_text(response.text)))
        return response.text
    answer = solve(instance.spec.template_id, dict(instance.spec.parameters), instance.spec.outcome_type, fetch)
    record = core.evaluate(instance, answer, variant, observed)
    result = {"mode": MODE, "note": "Scripted navigator over the real pages; not a model run and not evidence about any agent's ability.",
              "task": instance.spec.record(), "variant": {"id": variant.variant_id, "factors": dict(variant.factors)}, "answer": answer,
              "visited_paths": visited, "page_requests": len(visited), "evaluation": record.as_dict()}
    if output is not None:
        recorder = Recorder(Path(output))
        recorder.write("result.json", result)
        result["artifact_path"] = str(recorder.path)
    result["_observed"] = observed          # in-memory only (never written): the observations used for evidence checks
    return result


def parse_variant(env_id: str, spec: str | None) -> core.Variant:
    registry.load_all()
    env = core.ENVIRONMENTS[env_id]
    if not spec:
        return env.default_variant()
    wanted = dict(kv.split("=", 1) for kv in spec.split(","))
    for v in env.variants():
        if all(dict(v.factors).get(k) == val for k, val in wanted.items()) and len(wanted) == len(v.factors):
            return v
    raise ValueError(f"no variant matches {spec!r}; available: " + "; ".join(v.variant_id for v in env.variants()))
