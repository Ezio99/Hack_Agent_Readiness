"""Pipeline stages `taskgen` and `freeze`. Candidates come from three sources, all through the same gate: owner goals, the model (any LLMClient), and — only to top up — deterministic rules."""
from __future__ import annotations

import json

from ...ledger import Halt
from ..inspect.stage import load_snapshot
from ..llm import StructuredOutputError, request_sha256
from ..llm.meta import ProviderError
from ..models import now
from ..pipeline import Context
from . import freeze as freezer
from .candidates import candidates
from .gate import Accepted, Draft, Rejected, evaluate
from .goals import load_goals
from . import propose as propose_mod
from .propose import propose

DEFAULT_N = 8
MIN_TASKS = 4


def _run_gate(drafts: list[Draft], profile: dict, accepted: list[Accepted], rejected: list[Rejected]) -> None:
    for d in drafts:
        r = evaluate(d, profile, accepted)
        (accepted if isinstance(r, Accepted) else rejected).append(r)


def _draft_dict(d: Draft) -> dict:
    return {"question": d.question, "start_path": d.start_path, "criterion": d.criterion, "source": d.source, "rationale": d.rationale}


class AmbiguousBatchAttempt(Halt):
    """A batch request was reserved/sent but its result was never persisted (e.g. the process was killed in between). It is NOT re-sent automatically: whether the provider answered, and what
    it cost, is unknown to this run. The owner decides explicitly (`recover_batch`)."""


def _reserved_requests(run) -> int:
    """Taskgen requests the durable spend ledger has reserved so far (reserve-before-send: a reservation exists iff the request may have been sent). Read-only; creates nothing."""
    path = run.dir / "spend" / "ledger.jsonl"
    if not path.exists():
        return 0
    prefix = f"{run.state['id']}-taskgen:req"
    return sum(1 for line in path.read_text().splitlines() if (e := json.loads(line))["kind"] == "reserve" and e["id"].startswith(prefix))


def _attempt_marker(run, i: int):
    return run.dir / "private" / f"taskgen-attempt-{i}.json"


def recover_batch(run, i: int, *, note: str) -> dict:
    """Explicit owner recovery of an ambiguous batch: record it as `abandoned` so the stage can continue WITHOUT re-sending it. The request's reservation stays counted in the ledger (it may have
    been billed), and the 3-request limit still includes it, so a re-send is not possible within the approved manifest."""
    if not note.strip():
        raise ValueError("recovery needs a note saying who decided what")
    if (run.dir / "private" / f"taskgen-batch-{i}.json").exists():
        raise ValueError(f"batch {i} already has a persisted result; nothing to recover")
    marker = _attempt_marker(run, i)
    if not marker.exists():
        raise ValueError(f"batch {i} has no attempt marker; nothing to recover")
    rec = {"status": "abandoned", "drafts": [], "meta": {"error": "ambiguous attempt abandoned by the owner (request may have been sent and billed; result unknown)", "note": note.strip()[:300],
                                                       "attempt": json.loads(marker.read_text())}}
    run.write_private(f"taskgen-batch-{i}", rec)
    return rec


def _batch_result(run, i: int, req, llm, profile) -> tuple[dict, bool]:
    """One batch = one request, never repeated. Before the request can leave the process a durable ATTEMPT MARKER is written (with the number of requests the ledger had reserved at that point).
    A finished batch (ok / invalid / provider error) is persisted privately right after. On a restart: a persisted result is reused; a marker without a result is resolved by the ledger - if no
    reservation was added since the marker, the request provably never left (reserve-before-send) and the batch is simply attempted; if a reservation exists, the attempt is ambiguous and the stage
    STOPS (`AmbiguousBatchAttempt`) until the owner runs `recover_batch`. Returns (record, stop): `stop` after a provider failure. Gate/spend/other failures propagate (critical)."""
    name = f"taskgen-batch-{i}"
    if (run.dir / "private" / f"{name}.json").exists():
        rec = run.private(name)
        return rec, rec["status"] == "provider_error"
    marker = _attempt_marker(run, i)
    if marker.exists():
        before = json.loads(marker.read_text())["reserved_before"]
        if _reserved_requests(run) > before:
            raise AmbiguousBatchAttempt(f"taskgen batch {i}: a request was reserved/sent but no result was persisted (interrupted run?). It is NOT re-sent automatically. Inspect spend/ledger.jsonl and "
                                        f"calls/taskgen.jsonl, then decide: `readiness investigate recover-batch {run.dir} --batch {i} --abandon --note '<who decided what>'`")
        marker.unlink()                                                 # nothing was reserved after the marker: the request never left this process, so attempting it now is safe
    run.write_private(f"taskgen-attempt-{i}", {"batch": i, "request_sha256": request_sha256(req), "reserved_before": _reserved_requests(run), "at": now()})      # durable BEFORE the request
    try:
        drafts, meta = propose(llm, None, request=req, retries=0)
        rec = {"status": "ok", "drafts": [_draft_dict(d) for d in drafts], "meta": meta}
    except StructuredOutputError as exc:                           # unusable output of THIS batch: recorded, the other batches are unaffected
        rec = {"status": "invalid", "drafts": [], "meta": {"error": str(exc)[:200], "diagnostics": exc.diagnostics}}
    except ProviderError as exc:                                   # transport / HTTP / response-shape failure: keep what was paid for, stop issuing requests
        rec = {"status": "provider_error", "drafts": [], "meta": {"error": f"{exc.category} {exc.status or ''}: {exc.summary}".strip()}}
    run.write_private(name, rec)
    return rec, rec["status"] == "provider_error"


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
        for i, req in enumerate(propose_mod.batch_requests(profile, focus)):
            rec, stop = _batch_result(run, i, req, ctx.llm, profile)      # Halt / gate refusal / anything unexpected propagates: critical, stops the stage; earlier batches are already persisted
            calls.append({"batch": i, "status": rec["status"], **rec["meta"]})
            _run_gate([Draft(**d) for d in rec["drafts"]], profile, accepted, rejected)
            violation = getattr(ctx.llm, "violation", None)
            if violation:
                raise Halt(f"spend gate bound violation after batch {i}: {violation}; stopping the stage (completed batches are kept)")
            if stop:
                break
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
