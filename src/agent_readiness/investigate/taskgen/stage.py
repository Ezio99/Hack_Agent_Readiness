"""Pipeline stages `taskgen` and `freeze`. Candidates come from three sources, all through the same gate: owner goals, the model (any LLMClient), and — only to top up — deterministic rules."""
from __future__ import annotations

import json
import re

from ...ledger import Halt
from ...suite.core import canonical_hash
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


class AttemptMarkerMismatch(Halt):
    """An attempt marker does not belong to the request this run would send for that batch (wrong index or request hash). It is never treated as the current request; the owner must look."""


def _reserved_requests(run) -> int:
    """Taskgen requests the durable spend ledger has reserved so far (reserve-before-send: a reservation exists iff the request may have been sent). Read-only; creates nothing."""
    path = run.dir / "spend" / "ledger.jsonl"
    if not path.exists():
        return 0
    mine = re.compile(rf"{re.escape(run.state['id'])}-taskgen:req\d+")                  # exactly this stage's gate ids, not ids that merely share the prefix
    return sum(1 for line in path.read_text().splitlines() if (e := json.loads(line))["kind"] == "reserve" and mine.fullmatch(e["id"]))


def _attempt_marker(run, i: int):
    return run.dir / "private" / f"taskgen-attempt-{i}.json"


def approved_batch_hashes(run) -> list[str]:
    """The request hashes of the CURRENT approved taskgen configuration: the latest approved taskgen manifest (verified against its approved hash), or - for runs that have no taskgen approval
    (mock / scripted) - the requests the current code and site profile produce."""
    for a in reversed(run.approvals()):
        if a["stage"] == "taskgen":
            path = run.dir / "artifacts" / "manifests" / f"taskgen-{a['manifest_sha256'][:16]}.json"
            if path.exists():
                m = json.loads(path.read_text())
                if run.manifest_sha256(m) == a["manifest_sha256"]:
                    return list(m["batch_request_sha256"])
    return [request_sha256(r) for r in propose_mod.batch_requests(run.artifact("site-profile"))]


def _check_marker(marker_path, i: int, expected_hash: str) -> dict:
    m = json.loads(marker_path.read_text())
    if m.get("batch") != i or m.get("request_sha256") != expected_hash:
        raise AttemptMarkerMismatch(f"taskgen batch {i}: the attempt marker (batch {m.get('batch')}, request {str(m.get('request_sha256'))[:12]}) does not match the request this run would send "
                                    f"({expected_hash[:12]}). It is not treated as the current request and nothing is sent; inspect {marker_path.name} and the ledger.")
    return m


def recover_batch(run, i: int, *, note: str) -> dict:
    """Explicit owner recovery of an ambiguous batch: record it as `abandoned` so the stage can continue WITHOUT re-sending it. Allowed only when (1) `i` is a batch of the current approved
    configuration, (2) the attempt marker is that batch's (index and request hash match the approved manifest) and (3) the durable ledger shows a reservation made after the marker - i.e. the
    attempt really is ambiguous. The reservation stays counted (it may have been billed) and the 3-request limit still includes it, so a re-send is not possible within the approved manifest."""
    if not note.strip():
        raise ValueError("recovery needs a note saying who decided what")
    expected = approved_batch_hashes(run)
    if not isinstance(i, int) or isinstance(i, bool) or not 0 <= i < len(expected):
        raise ValueError(f"invalid batch index {i!r}: the approved taskgen configuration has batches 0..{len(expected) - 1}")
    if (run.dir / "private" / f"taskgen-batch-{i}.json").exists():
        raise ValueError(f"batch {i} already has a persisted result; nothing to recover")
    marker = _attempt_marker(run, i)
    if not marker.exists():
        raise ValueError(f"batch {i} has no attempt marker; nothing to recover")
    try:
        m = _check_marker(marker, i, expected[i])
    except AttemptMarkerMismatch as exc:
        raise ValueError(f"refusing to abandon: {exc}") from exc
    reserved = _reserved_requests(run)
    if reserved < m["reserved_before"]:
        raise ValueError(f"inconsistent ledger: {reserved} reservation(s) now, but {m['reserved_before']} when the attempt marker was written; refusing to recover")
    if reserved == m["reserved_before"]:
        raise ValueError(f"batch {i} is not ambiguous: the ledger shows no reservation after the attempt marker, so the request never left this process; re-run the stage and it will be attempted normally")
    rec = {"status": "abandoned", "drafts": [], "meta": {"error": "ambiguous attempt abandoned by the owner (request may have been sent and billed; result unknown)", "note": note.strip()[:300], "attempt": m}}
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
        before = _check_marker(marker, i, request_sha256(req))["reserved_before"]          # a marker for another batch / request is rejected, never taken for this one
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


def _key(d: Draft) -> str:
    return canonical_hash({"q": d.question, "s": d.start_path, "c": d.criterion})


def taskgen_stage(ctx: Context) -> dict:
    run, opts = ctx.run, ctx.options
    profile = run.artifact("site-profile")
    focus, owner = load_goals(opts.get("goals"))
    bound = bool(opts.get("goal_binding") and focus)           # the goal is a binding objective: goal-bound prompts, an independent relevance check, selection by relevance, no substitution
    accepted: list[Accepted] = []
    rejected: list[Rejected] = []
    calls = []
    proposed: list[tuple[int, Draft]] = []
    _run_gate(owner, profile, accepted, rejected)
    target = opts.get("n_tasks", DEFAULT_N)
    if ctx.llm is not None:
        for i, req in enumerate(propose_mod.batch_requests(profile, focus, bound)):
            rec, stop = _batch_result(run, i, req, ctx.llm, profile)      # Halt / gate refusal / anything unexpected propagates: critical, stops the stage; earlier batches are already persisted
            calls.append({"batch": i, "status": rec["status"], **rec["meta"]})
            batch = [Draft(**d) for d in rec["drafts"]]
            proposed += [(i, d) for d in batch]
            _run_gate(batch, profile, accepted, rejected)
            violation = getattr(ctx.llm, "violation", None)
            if violation:
                raise Halt(f"spend gate bound violation after batch {i}: {violation}; stopping the stage (completed batches are kept)")
            if stop:
                break
    topped_up = 0
    if len(accepted) < MIN_TASKS and opts.get("rule_topup", True) and not bound:
        before = len(accepted)
        _run_gate(candidates(profile), profile, accepted, rejected)
        topped_up = len(accepted) - before
    limit = max(target, MIN_TASKS)
    goal_block, assessed = None, []
    if bound:
        from . import goal as G
        lex = opts.get("goal_lexicon")
        ga = G.analyse(focus, profile, lex)
        assessed = [G.assess(ga, a, lex) for a in accepted]
        selected = [accepted[i] for i in G.rank(accepted, assessed)][:limit]
        goal_block = {"verifier": "independent goal-relevance check (taskgen/goal.py): grounds the goal in the captured site and judges each gate-accepted task by what its criterion touches; it does not read the model's own links, and it does not change the answerability gate",
                      "analysis": {k: ga[k] for k in ("asked_aspects", "attribute_labels", "ordering_terms", "entity_terms", "entity_listings", "entity_items", "entity_grounded", "support", "limitations")},
                      "model_goal_analysis": [c.get("goal_analysis") for c in calls if c.get("goal_analysis")], "assessments": assessed,
                      "relevant_tasks": sum(a["goal_relevant"] for a in assessed), "gate_accepted_tasks": len(accepted), "selected": len(selected), "needed": MIN_TASKS}
    else:
        selected = accepted[:limit]
    sel_keys = {_key(a.draft) for a in selected}
    acc_keys = {_key(a.draft) for a in accepted}
    rej_reason = {_key(r.draft): r.reason for r in rejected}
    relevant_keys = {_key(a.draft) for a, v in zip(accepted, assessed) if v["goal_relevant"]} if bound else acc_keys
    accounting_rows = []
    for batch_i, d in proposed:
        k = _key(d)
        status, why = (("selected", None) if k in sel_keys else ("accepted_not_selected", "not goal-relevant" if bound and k not in relevant_keys else "ranked below the selection limit") if k in acc_keys else ("rejected", rej_reason.get(k, "unknown")))
        accounting_rows.append({"batch": batch_i, "question": d.question[:200], "status": status, "reason": why})
    counts = {s: sum(r["status"] == s for r in accounting_rows) for s in ("rejected", "accepted_not_selected", "selected")}
    accounting = {"proposed": len(proposed), **counts, "unaccounted": len(proposed) - sum(counts.values()), "per_proposal": accounting_rows,
                  "note": "every model proposal is either rejected by the gate (with its reason), accepted but not selected (with why), or selected; owner and rule tasks are listed under accepted/rejected only"}
    accepted = selected
    run.write_artifact("taskgen-report", {"accepted": [{"question": a.draft.question, "source": a.draft.source, "kind": a.compiled.kind, "fingerprint": a.fingerprint} for a in accepted],
                                         "rejected": [{"question": r.draft.question, "source": r.draft.source, "reason": r.reason} for r in rejected], "model_calls": calls, "rule_topup": topped_up,
                                         "not_selected": [r for r in accounting_rows if r["status"] == "accepted_not_selected"], "accounting": accounting, **({"goal_binding": goal_block} if goal_block else {})})
    if len(accepted) < MIN_TASKS:
        if bound:
            raise ValueError(f"goal coverage insufficient: {len(accepted)} goal-relevant verified tasks (need {MIN_TASKS}) out of {len(goal_block['assessments'])} gate-accepted; "
                             f"limitations: {'; '.join(goal_block['analysis']['limitations']) or 'none identified'}. No unrelated tasks were substituted; see goal_binding in the taskgen-report artifact")
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
