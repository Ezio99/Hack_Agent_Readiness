"""Pipeline stages `taskgen` and `freeze`. Candidates come from three sources, all through the same gate: owner goals, the model (any LLMClient), and — only to top up — deterministic rules."""
from __future__ import annotations

from ..inspect.stage import load_snapshot
from ..llm import StructuredOutputError
from ..pipeline import Context
from . import freeze as freezer
from .candidates import candidates
from .gate import Accepted, Draft, Rejected, evaluate
from .goals import load_goals
from .propose import propose

DEFAULT_N = 8
MIN_TASKS = 4


def _run_gate(drafts: list[Draft], profile: dict, accepted: list[Accepted], rejected: list[Rejected]) -> None:
    for d in drafts:
        r = evaluate(d, profile, accepted)
        (accepted if isinstance(r, Accepted) else rejected).append(r)


def taskgen_stage(ctx: Context) -> dict:
    run, opts = ctx.run, ctx.options
    profile = run.artifact("site-profile")
    focus, owner = load_goals(opts.get("goals"))
    accepted: list[Accepted] = []
    rejected: list[Rejected] = []
    calls = []
    _run_gate(owner, profile, accepted, rejected)
    target = opts.get("n_tasks", DEFAULT_N)
    if ctx.llm is not None:
        try:
            drafts, meta = propose(ctx.llm, profile, n=target + 2, focus=focus)
            calls.append(meta)
            _run_gate(drafts, profile, accepted, rejected)
            if len(accepted) < target and opts.get("feedback_round", True):
                drafts, meta = propose(ctx.llm, profile, n=target - len(accepted) + 2, focus=focus, feedback=[r.reason for r in rejected if r.draft.source == "model"])
                calls.append(meta)
                _run_gate(drafts, profile, accepted, rejected)
        except StructuredOutputError as exc:                       # unusable model output is recorded, never fatal: rules can still top up
            calls.append({"error": str(exc)[:200]})
    topped_up = 0
    if len(accepted) < MIN_TASKS and opts.get("rule_topup", True):
        before = len(accepted)
        _run_gate(candidates(profile), profile, accepted, rejected)
        topped_up = len(accepted) - before
    accepted = accepted[:max(target, MIN_TASKS)]
    run.write_artifact("taskgen-report", {"accepted": [{"question": a.draft.question, "source": a.draft.source, "kind": a.compiled.kind, "fingerprint": a.fingerprint} for a in accepted],
                                         "rejected": [{"question": r.draft.question, "source": r.draft.source, "reason": r.reason} for r in rejected], "model_calls": calls, "rule_topup": topped_up})
    if len(accepted) < MIN_TASKS:
        raise ValueError(f"only {len(accepted)} acceptable tasks (need {MIN_TASKS}); see the rejection reasons in the taskgen-report artifact")
    run.write_private("accepted-drafts", [{"question": a.draft.question, "start_path": a.draft.start_path, "criterion": a.criterion, "source": a.draft.source, "rationale": a.draft.rationale} for a in accepted])
    return {"accepted": len(accepted), "rejected": len(rejected), "model_calls": len(calls), "by_source": {s: sum(a.draft.source == s for a in accepted) for s in ("owner", "model", "rule")}}


def freeze_stage(ctx: Context) -> dict:
    run, opts = ctx.run, ctx.options
    profile = run.artifact("site-profile")
    snap = load_snapshot(run)
    accepted: list[Accepted] = []
    for d in run.private("accepted-drafts"):
        r = evaluate(Draft(d["question"], d["start_path"], d["criterion"], d["source"], d["rationale"]), profile, accepted)
        if not isinstance(r, Accepted):
            raise ValueError("a previously accepted task no longer passes the gate")
        accepted.append(r)
    rep = run.artifact("taskgen-report")
    gen = {"mode": ctx.llm.mode if ctx.llm else "none", "model": ctx.llm.model if ctx.llm else None, "calls": rep["model_calls"], "rule_topup": rep["rule_topup"]}
    m = freezer.freeze(run, accepted, snapshot_sha256=snap.sha256, generator=gen, agent_profile=opts.get("agent_profile", "suite-v2-compat1"), seed=opts.get("seed", 0),
                       rejections=[{"reason": r["reason"], "source": r["source"]} for r in rep["rejected"]])
    return {"tasks": len(m["tasks"]), **m["counts"], "manifest_sha256": freezer.canonical_hash(m)}
