"""Model and grader provenance of a recorded run, DERIVED from its frozen records (read-only; never from UI constants).

Sources, per trial: the trial record (`trial.model`, `trial.profile`, `trial.profile_hash`, `evaluation.evaluator_id/version`) and the private request
trace (`model_http_request.parameters`: what was actually sent). The recorded profile hash is recomputed from the named profile file plus the trial's
own limits; reasoning_effort and max_completion_tokens are reported only when the profile file and every recorded request agree. Disagreement is
reported as such (values listed, `consistent: false`), never resolved silently."""
from __future__ import annotations

import json
from pathlib import Path

SCHEMA = "model-provenance-v1"


def _profile_check(name: str, limits: dict, recorded_hash: str) -> tuple[bool, dict]:
    from .agent import profile
    from .suite.core import canonical_hash
    try:
        eff = profile(name)
    except Exception:
        return False, {}
    eff.update(max_steps=limits.get("max_steps"), timeout_seconds=limits.get("timeout_seconds"), max_model_requests=limits.get("max_model_requests"))
    return canonical_hash(eff) == recorded_hash, eff


def model_provenance(run_dir: Path, arms: tuple[str, ...] | None = None) -> dict:
    """Provenance over the trials whose artifact name starts with one of `arms` (all trials when None), plus a per-arm breakdown: a fork can hold
    imported historical trials recorded with an earlier profile beside its own trials."""
    run_dir = Path(run_dir)
    paths = sorted((run_dir / "artifacts" / "trials").glob("*.json"))
    arm_of = lambda p: p.stem.split("-")[0]
    if arms is None:
        out = _provenance(run_dir, paths)
        groups = sorted({arm_of(p) for p in paths})
    else:
        out = _provenance(run_dir, [p for p in paths if arm_of(p) in arms])
        groups = sorted({arm_of(p) for p in paths})
    out["arms"] = list(arms) if arms else groups
    out["by_arm"] = {g: {k: v for k, v in _provenance(run_dir, [p for p in paths if arm_of(p) == g]).items() if k in ("trials", "model", "reasoning_effort", "max_completion_tokens", "agent_profile", "consistent")}
                     for g in groups}
    return out


def _provenance(run_dir: Path, paths: list[Path]) -> dict:
    trials = [json.loads(p.read_text()) for p in paths]
    models, profiles, hashes, graders, wire, verified, settings = set(), set(), set(), set(), {}, [], {}
    requests = 0
    for t in trials:
        tr, ev = t.get("trial") or {}, t.get("evaluation") or {}
        models.add(tr.get("model")); profiles.add(tr.get("profile")); hashes.add(tr.get("profile_hash"))
        graders.add((ev.get("evaluator_id"), ev.get("evaluator_version")))
        ok, eff = _profile_check(tr.get("profile"), (t.get("metrics") or {}).get("limits") or {}, tr.get("profile_hash"))
        verified.append(ok)
        if ok:
            for k in ("reasoning_effort", "max_completion_tokens"):
                settings.setdefault(k, set()).add(eff.get(k))
        for trace in sorted((run_dir / t.get("trial_dir", "_missing")).glob("trace.jsonl")) if t.get("trial_dir") else []:
            for line in trace.read_text().splitlines():
                e = json.loads(line)
                if e.get("kind") == "model_http_request":
                    requests += 1
                    for k, v in (e.get("parameters") or {}).items():
                        wire.setdefault(k, set()).add(v)

    def one(values):
        vals = sorted(values, key=str)
        return vals[0] if len(vals) == 1 else vals

    agreed = {}
    for k in ("reasoning_effort", "max_completion_tokens"):
        prof, sent = settings.get(k, set()), wire.get(k, set())
        agreed[k] = {"value": one(prof | sent) if prof | sent else None, "profile": one(prof) if prof else None, "sent": one(sent) if sent else None,
                     "consistent": len(prof | sent) == 1}
    model_vals = models | wire.get("model", set())
    out = {"schema": SCHEMA, "trials": len(trials), "model_requests_recorded": requests,
           "model": {"value": one(model_vals) if model_vals else None, "consistent": len(model_vals) == 1},
           "reasoning_effort": agreed["reasoning_effort"], "max_completion_tokens": agreed["max_completion_tokens"],
           "agent_profile": {"name": one(profiles), "sha256": one(hashes), "verified_against_profile_file": bool(verified) and all(verified)},
           "graders": {"official": [{"id": i, "version": v} for i, v in sorted(graders, key=str)],
                       "post_hoc": None}}
    try:
        from .grading import rescore, v2
        out["graders"]["post_hoc"] = {"id": v2.GRADER_ID, "version": v2.GRADER_VERSION, "derivation_id": rescore.derivation_id(), "label": "post-hoc rescore; not the official grade"}
    except Exception:
        pass
    out["consistent"] = all(x["consistent"] for x in (out["model"], out["reasoning_effort"], out["max_completion_tokens"])) and len(profiles) == 1 and len(hashes) == 1 \
        and out["agent_profile"]["verified_against_profile_file"] and len(graders) == 1
    return out
