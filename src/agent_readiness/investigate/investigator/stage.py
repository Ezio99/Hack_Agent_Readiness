"""Pipeline stages `trace`, `investigate`, `report`."""
from __future__ import annotations

from ...suite.core import canonical_hash
from .. import allocation as alloc
from ..llm import LLMRequest, RecordingClient  # noqa: F401
from ..llm.meta import DEFAULT_REASONING_EFFORT, INPUT_OVERHEAD_TOKENS, reservation_bound_usd
from ..models import now
from ..pipeline import Context
from ..report import build_report
from ..trials.trace import trace_stage  # re-exported for the flow
from .loop import STEP_MAX_TOKENS, SYSTEM, Step, first_user_message, investigate
from .tools import Workspace

DEFAULT_MAX_CALLS = 12
RUN_CAP_USD = alloc.INVESTIGATE_CAP_USD


def manifest(ctx: Context) -> dict:
    from ...agent import ModelConfig
    from ..fork import provenance_summary
    forked = provenance_summary(ctx.run)                      # None for a normal run; a fork verifies its imported evidence FIRST (fails closed) and shows its provenance, so approval binds to it
    cfg = ctx.options.get("model_config") or ModelConfig()
    ws = Workspace(ctx.run)
    n = ctx.options.get("max_calls", DEFAULT_MAX_CALLS)
    return {**({"forked_from": forked} if forked else {}), "stage": "investigate", **({"client_context_sha256": canonical_hash(ctx.options["context"])} if ctx.options.get("context") else {}), "provider": cfg.provider, "model": cfg.model, "endpoint": cfg.base_url.rstrip("/") + "/chat/completions", "max_tool_calls": n, "max_requests": 2 * (n + 1),
            "retries_per_request": 1, "run_cap_usd": ctx.options.get("investigate_cap_usd", RUN_CAP_USD), "per_request_cap_usd": alloc.PER_REQUEST_CAP_USD, "reasoning_effort": DEFAULT_REASONING_EFFORT, "max_completion_tokens": STEP_MAX_TOKENS, "input_overhead_tokens_reserved": INPUT_OVERHEAD_TOKENS,
            "first_request_reservation_usd": reservation_bound_usd(LLMRequest(messages=[{"role": "system", "content": SYSTEM}, {"role": "user", "content": first_user_message(ws, ctx.options.get("focus"), ctx.options.get("context"))}], purpose="investigate", max_tokens=STEP_MAX_TOKENS, response_schema=Step.model_json_schema())),
            "allocation": alloc.allocation(ctx.options.get("total_cap_usd", 3.0)), "reservation_note": "input grows with the conversation; every request is re-reserved and refused if it would exceed the per-request or run cap", "prompt_sha256": canonical_hash([SYSTEM, first_user_message(ws, ctx.options.get("focus"))]),
            "attribution_sha256": canonical_hash(ctx.run.artifact("attribution")), "tasks_manifest_sha256": canonical_hash(ctx.run.artifact("tasks-manifest")), "cost_basis": "calculated upper bounds at published prices; not a bill"}


def ledger_accounting(run, res: dict) -> dict:
    """Reconcile what the client meter saw with the durable spend ledger for THIS stage's gate ids (exactly `<run id>-investigate:req<N>`; other ids that merely share the prefix are ignored). `reconciled` is
    strict: every reservation settled, none outstanding, request count and settled cost equal to the meter's. A provider error keeps its full reservation unsettled by design, so such a run is reported
    as NOT reconciled with the outstanding amount and the count of requests whose send status is uncertain spelled out - never silently as clean."""
    import json as _json
    import re
    path = run.dir / "spend" / "ledger.jsonl"
    if not path.exists():
        return {"ledger": "none (mock / scripted run)", "metered_requests": res["model_requests"], "metered_cost_usd": res["cost_usd"], "reconciled": True}
    mine = re.compile(rf"{re.escape(run.state['id'])}-investigate:req\d+")
    reserved, settled = {}, {}
    for line in path.read_text().splitlines():
        e = _json.loads(line)
        if mine.fullmatch(e["id"]):
            (reserved if e["kind"] == "reserve" else settled)[e["id"]] = e["usd"]
    settled_usd = round(sum(settled.values()), 6)
    unsettled_ids = sorted(k for k in reserved if k not in settled)
    unsettled = round(sum(reserved[k] for k in unsettled_ids), 6)
    orphan_settles = sorted(k for k in settled if k not in reserved)
    checks = {"all_reservations_settled": not unsettled_ids, "no_outstanding_reservation_usd": unsettled == 0, "no_settlement_without_reservation": not orphan_settles,
              "request_count_matches": len(reserved) == res["model_requests"] == len(settled), "settled_cost_matches": abs(settled_usd - res["cost_usd"]) < 1e-6}
    ok = all(checks.values())
    why = [k for k, v in checks.items() if not v]
    return {"ledger_requests_reserved": len(reserved), "ledger_requests_settled": len(settled), "ledger_settled_usd": settled_usd, "ledger_unsettled_reservations": len(unsettled_ids),
            "ledger_unsettled_reserved_usd": unsettled, "metered_requests": res["model_requests"], "requests_confirmed": res.get("requests_confirmed"), "requests_uncertain": res.get("requests_uncertain"),
            "metered_cost_usd": res["cost_usd"], "checks": checks, "reconciled": ok,
            "note": "requests, settlements and cost equal the durable ledger; nothing outstanding" if ok else
                    f"NOT reconciled ({', '.join(why)}): {len(unsettled_ids)} reservation(s) unsettled (US${unsettled}) stay counted at their full bound; {res.get('requests_uncertain')} request(s) have an uncertain send status. Inspect spend/ledger.jsonl"}


def investigate_stage(ctx: Context) -> dict:
    run = ctx.run
    llm = ctx.options.get("investigator_llm") or ctx.llm
    if llm is None:
        run.write_artifact("investigation", {"skipped": True, "reason": "no investigator model configured for this run", "at": now()})
        return {"skipped": True}
    from ..fork import verify_fork
    verify_fork(run)                                           # a fork whose imported evidence or spending history changed never sends a request
    ws = Workspace(run)
    res = investigate(ws, llm, max_calls=ctx.options.get("max_calls", DEFAULT_MAX_CALLS), focus=ctx.options.get("focus"), context=ctx.options.get("context"))
    transcript = res.pop("transcript")
    run.write_private("investigator-transcript", transcript)
    res["accounting"] = ledger_accounting(run, res)
    run.write_artifact("investigation", {**res, "skipped": False, "model": llm.model, "mode": llm.mode})
    return {k: res[k] for k in ("status", "finished", "incomplete", "tool_calls", "model_requests", "cost_usd")} | {"reconciled": res["accounting"]["reconciled"], "hypotheses": len(run.evidence.hypotheses), "findings": len(run.evidence.findings)}


def report_stage(ctx: Context, *, final: bool = False) -> dict:
    run = ctx.run
    rep = build_report(run)
    inv = run.artifact("investigation") if run.has_artifact("investigation") else {"skipped": True}
    att = run.artifact("attribution") if run.has_artifact("attribution") else {}
    manifest_ = run.artifact("tasks-manifest")
    rep["investigation"] = {k: inv.get(k) for k in ("skipped", "reason", "finished", "incomplete", "tool_calls", "model_requests", "requests_confirmed", "requests_uncertain", "model", "mode", "cost_usd", "status", "prompt_tokens", "completion_tokens", "reasoning_tokens", "finish_reasons", "provider_errors", "refused_before_send", "error", "accounting", "verification", "rejected_hypotheses", "novel_changes", "pending_trial_requests", "tool_log")}
    status = inv.get("status") or ("not_run" if inv.get("skipped") else "completed" if inv.get("finished") else "incomplete_no_finish")
    rep["investigation_status"] = status
    if status != "completed" and rep["outcome"] == "no_supported_issue":
        rep["outcome"] = "not_investigated" if status == "not_run" else status           # an unrun / aborted / unfinished investigation is NOT a valid negative finding
        rep["outcome_note"] = ("No investigator ran" if status == "not_run" else f"The investigation did not complete ({status})") + ": nothing was concluded about the website. 'No supported issue' would have been a false negative."
    rep["trials"] = {"by_attribution": _count(att.values(), "primary"), "void": sum(a["void"] for a in att.values()), "investigation": sum(a["partition"] == "investigation" for a in att.values()), "holdout": sum(a["partition"] == "holdout" for a in att.values()),
                     "note": "Holdout trials were never shown to the investigator. Void trials (provider/budget/infrastructure) are excluded from website evidence."}
    rep["tasks"] = {"count": len(manifest_["tasks"]), "by_kind": _count(manifest_["tasks"], "kind"), "by_source": _count(manifest_["tasks"], "source"), "generator": manifest_["generator"]}
    if run.has_artifact("recommendations"):
        rep["recommendations"] = run.artifact("recommendations")
    if final and run.has_artifact("evaluation"):
        ev = run.artifact("evaluation")
        rep["evaluation"] = ev
        rep["evaluation_statement"] = ("Measured effects are for the pre-registered rule, these frozen tasks, this agent profile/model and this patched mirror only. 'inconclusive' means the data neither show an improvement nor a regression. "
                                       "A pattern no longer being observed (static re-check) is not an effect on agents.")
        if ev.get("exploratory"):
            rep["exploratory_statement"] = (ev["exploratory"]["label"] + ". The frozen-rule verdict above is reported unchanged and is not replaced. The proposal tested was chosen by the owner; it is not an investigator-verified finding. "
                                            f"Exploratory verdict: {ev['exploratory']['verdict']} (n = 1 trial per task per arm).")
    run.write_artifact("report-final" if final else "report", rep)
    return {"outcome": rep["outcome"], "supported_unpromoted": len(rep["supported_unpromoted"])}


def final_report_stage(ctx: Context) -> dict:
    return report_stage(ctx, final=True)


def _count(rows, key):
    out: dict = {}
    for r in rows:
        out[r[key]] = out.get(r[key], 0) + 1
    return out
