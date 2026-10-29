"""Pipeline stages `trace`, `investigate`, `report`."""
from __future__ import annotations

from ...suite.core import canonical_hash
from ..llm import RecordingClient  # noqa: F401
from ..models import now
from ..pipeline import Context
from ..report import build_report
from ..trials.trace import trace_stage  # re-exported for the flow
from .loop import SYSTEM, first_user_message, investigate
from .tools import Workspace

DEFAULT_MAX_CALLS = 12
RUN_CAP_USD = 0.40


def manifest(ctx: Context) -> dict:
    from ...agent import ModelConfig
    cfg = ctx.options.get("model_config") or ModelConfig()
    ws = Workspace(ctx.run)
    n = ctx.options.get("max_calls", DEFAULT_MAX_CALLS)
    return {"stage": "investigate", "provider": cfg.provider, "model": cfg.model, "endpoint": cfg.base_url.rstrip("/") + "/chat/completions", "max_tool_calls": n, "max_requests": n + 3,
            "retries_per_request": 1, "run_cap_usd": ctx.options.get("investigate_cap_usd", RUN_CAP_USD), "per_request_cap_usd": 0.05, "prompt_sha256": canonical_hash([SYSTEM, first_user_message(ws, ctx.options.get("focus"))]),
            "attribution_sha256": canonical_hash(ctx.run.artifact("attribution")), "tasks_manifest_sha256": canonical_hash(ctx.run.artifact("tasks-manifest")), "cost_basis": "calculated upper bounds at published prices; not a bill"}


def investigate_stage(ctx: Context) -> dict:
    run = ctx.run
    llm = ctx.options.get("investigator_llm") or ctx.llm
    if llm is None:
        run.write_artifact("investigation", {"skipped": True, "reason": "no investigator model configured for this run", "at": now()})
        return {"skipped": True}
    ws = Workspace(run)
    res = investigate(ws, llm, max_calls=ctx.options.get("max_calls", DEFAULT_MAX_CALLS), focus=ctx.options.get("focus"))
    transcript = res.pop("transcript")
    run.write_private("investigator-transcript", transcript)
    run.write_artifact("investigation", {**res, "skipped": False, "model": llm.model, "mode": llm.mode})
    return {k: res[k] for k in ("finished", "incomplete", "tool_calls", "model_requests", "cost_usd")} | {"hypotheses": len(run.evidence.hypotheses), "findings": len(run.evidence.findings)}


def report_stage(ctx: Context) -> dict:
    run = ctx.run
    rep = build_report(run)
    inv = run.artifact("investigation") if run.has_artifact("investigation") else {"skipped": True}
    att = run.artifact("attribution") if run.has_artifact("attribution") else {}
    manifest_ = run.artifact("tasks-manifest")
    rep["investigation"] = {k: inv.get(k) for k in ("skipped", "reason", "finished", "incomplete", "tool_calls", "model_requests", "model", "mode", "cost_usd", "verification", "rejected_hypotheses", "novel_changes", "pending_trial_requests", "tool_log")}
    rep["trials"] = {"by_attribution": _count(att.values(), "primary"), "void": sum(a["void"] for a in att.values()), "investigation": sum(a["partition"] == "investigation" for a in att.values()), "holdout": sum(a["partition"] == "holdout" for a in att.values()),
                     "note": "Holdout trials were never shown to the investigator. Void trials (provider/budget/infrastructure) are excluded from website evidence."}
    rep["tasks"] = {"count": len(manifest_["tasks"]), "by_kind": _count(manifest_["tasks"], "kind"), "by_source": _count(manifest_["tasks"], "source"), "generator": manifest_["generator"]}
    run.write_artifact("report", rep)
    return {"outcome": rep["outcome"], "supported_unpromoted": len(rep["supported_unpromoted"])}


def _count(rows, key):
    out: dict = {}
    for r in rows:
        out[r[key]] = out.get(r[key], 0) + 1
    return out
