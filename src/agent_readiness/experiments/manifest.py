"""Versioned experiment manifest: everything frozen for a run, hashed; drift is detected before every run."""
from __future__ import annotations

import importlib.metadata
import platform
import subprocess
from pathlib import Path

from ..agent import ModelConfig, profile
from ..capture import PRICE_INPUT_PER_M, PRICE_OUTPUT_PER_M
from ..suite import core, registry
from ..scanner.schema import PROFILE_ID, hashes_for
from . import design

REPO = Path(__file__).resolve().parents[3]
MANIFEST_VERSION = "task012-manifest-v1"


def git_state() -> dict:
    def run(*a):
        return subprocess.run(["git", *a], cwd=REPO, capture_output=True, text=True).stdout.strip()
    return {"commit": run("rev-parse", "HEAD"), "dirty": bool(run("status", "--porcelain", "--untracked-files=no"))}


def build_manifest(config: ModelConfig | None = None, profile_id: str = PROFILE_ID) -> dict:
    """Frozen configuration (the *hash* covers everything except execution provenance, which is compared separately)."""
    registry.load_all()
    config = config or ModelConfig()
    effective = profile(profile_id)
    limits = {t: core_limits(registry.get_instance(tid)) for t, tid in design.PRIMARY_TASKS.items()}
    first = next(iter(limits.values()))
    effective.update(max_steps=first["max_steps"], timeout_seconds=first["timeout_seconds"], max_model_requests=first["max_model_requests"])
    fixtures = {}
    for code, tid in design.PRIMARY_TASKS.items():
        inst = registry.get_instance(tid)
        fixtures[code] = {"task_id": tid, "template_id": inst.spec.template_id, "version": inst.spec.version, "spec_hash": core.canonical_hash(inst.spec.record()),
                          "evaluator": f"{inst.spec.evaluator_id}@{inst.spec.evaluator_version}", "limits": limits[code],
                          "schema_hashes": hashes_for(inst.answer_model)}
    env = core.ENVIRONMENTS[design.ENVIRONMENT]
    body = {
        "manifest_version": MANIFEST_VERSION, "experiment_id": design.EXPERIMENT_ID,
        "environment": {"id": design.ENVIRONMENT, "data_version": env.data_version},
        "variants": {c: {"variant_id": design.variant_id(c), "factors": {"availability": a, "specs": s}} for c, (a, s) in design.VARIANTS.items()},
        "fixtures": fixtures,
        "agent": {"provider": config.provider, "model": config.model, "base_url": config.base_url, "profile_id": profile_id, "profile_hash": core.canonical_hash(effective),
                  "reasoning_effort": effective["reasoning_effort"], "max_completion_tokens": effective["max_completion_tokens"], "output_parser": effective["output_parser"],
                  "observation": effective["observation_mode"], "tools": effective["allowed_tools"], "temperature": "not sent (provider default)"},
        "versions": {"python": platform.python_version(), "browser_use": importlib.metadata.version("browser-use"), "playwright": importlib.metadata.version("playwright")},
        "budget": {"programme_ceiling_usd": design.PROGRAMME_CEILING_USD, "stage_ceilings_usd": {str(k): v["stage_ceiling_usd"] for k, v in design.STAGES.items()},
                   "run_reserve_usd": design.RUN_RESERVE_USD, "prices_per_million": {"input": PRICE_INPUT_PER_M, "output": PRICE_OUTPUT_PER_M}},
        "halt_rules": {"infrastructure_errors": design.HALT_INFRA_ERRORS, "recovery_rejected_per_block": design.HALT_RECOVERY_REJECTED_PER_BLOCK, "guard_stops": sorted(design.GUARD_STOPS)},
    }
    return {**body, "manifest_hash": core.canonical_hash(body), "provenance": git_state()}


def core_limits(inst) -> dict:
    lim = inst.spec.limits
    return {"max_steps": lim.max_steps, "max_model_requests": lim.max_model_requests, "timeout_seconds": lim.timeout_seconds}


def drift(frozen: dict, current: dict, *, check_commit: bool = True) -> list[str]:
    """Human-readable differences that must halt execution."""
    out = []
    if frozen["manifest_hash"] != current["manifest_hash"]:
        for k in frozen:
            if k not in ("manifest_hash", "provenance") and frozen.get(k) != current.get(k):
                out.append(f"manifest section changed: {k}")
        out = out or ["manifest hash changed"]
    if check_commit and frozen["provenance"]["commit"] != current["provenance"]["commit"]:
        out.append(f"code commit changed: {frozen['provenance']['commit'][:9]} -> {current['provenance']['commit'][:9]}")
    if check_commit and current["provenance"]["dirty"]:
        out.append("working tree has uncommitted tracked changes")
    return out


def self_hash_ok(m: dict) -> bool:
    """The stored hash must match the stored content (a hand-edited frozen manifest is refused)."""
    return m.get("manifest_hash") == core.canonical_hash({k: v for k, v in m.items() if k not in ("manifest_hash", "provenance")})
