"""Sanitized (owner-visible) projections of private scan results. Whitelist-based: anything not listed here is never returned."""
from __future__ import annotations

from ...suite import core


def summary(scan: dict) -> dict:
    return {"scan_id": scan["id"], "task_id": scan["task_id"], "variant_id": scan["variant_id"], "mode": scan["mode"], "mock_behavior": scan["mock_behavior"], "status": scan["status"],
            "created_at": scan["created_at"], "started_at": scan["started_at"], "finished_at": scan["finished_at"], "error": scan["error"]}


def public_result(scan: dict, private: dict | None) -> dict:
    out = summary(scan)
    out["mock"] = scan["mode"] == "mock"
    out["inference_label"] = ("MOCK — scripted agent behaviour, not a model; nothing was sent to any provider" if scan["mode"] == "mock" else
                             "LIVE — Meta model inference (single run)")
    if private is None:
        return out
    t = private["task"]
    ev = private["evaluation"]
    out.update({
        "task": {"task_id": t["task_id"], "template_id": t["template_id"], "version": t["version"], "objective": t["objective"], "outcome_type": t["outcome_type"],
                 "evidence_policy": t["evidence_policy"], "limits": t["limits"], "environment_id": t["environment_id"], "data_version": t["data_version"]},
        "variant": private["variant"],
        "verdict": {"passed": ev["passed"], "evidence_backed": ev["evidence_backed"], "answer_valid": ev["answer_valid"], "reasons": ev["reasons"], "missing_evidence": ev["missing_evidence"],
                    "evaluator": f"{ev['evaluator_id']} v{ev['evaluator_version']}", "contract": ev["contract_version"]},
        "outcome": {"run_status": private["outcome"]["run_status"], "stop_reason": private["outcome"]["stop_reason"], "answer": private["outcome"]["answer"],
                    "errors": [e[:200] for e in private["outcome"]["errors"][:3]]},
        "metrics": private["metrics"],
        "journey": private["journey"],
        "diagnostics": private["diagnostics"],
        "run": {"model": private["scan"]["model"], "profile": private["scan"]["profile"], "profile_hash": private["scan"]["profile_hash"]},
    })
    return out


def registry_view(config, manager_killed: bool) -> dict:
    from ...environments.electronics.variants import DESCRIPTIONS
    from ..mock import BEHAVIORS
    envs, tasks = [], []
    for env in core.ENVIRONMENTS.values():
        envs.append({"environment_id": env.environment_id, "data_version": env.data_version,
                     "variants": [{"variant_id": v.variant_id, "factors": [list(f) for f in v.factors], "default": v == env.default_variant(),
                                   "descriptions": [DESCRIPTIONS.get((k, lvl), "") for k, lvl in v.factors]} for v in env.variants()]})
    for inst in core.all_instances():
        tasks.append({**inst.spec.public(), "template_id": inst.spec.template_id, "environment_id": inst.spec.environment_id})
    return {"environments": envs, "tasks": tasks, "providers": {"mock": True, "live": config.live_available},
            "mock_behaviors": list(BEHAVIORS) if config.allow_mock_behaviors else ["correct"], "kill_switch": manager_killed}
