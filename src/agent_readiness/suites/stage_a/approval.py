"""Human approval and immutable freezing (lifecycle M4; owner decision 7).

  review_packet(store, suite)       what the owner reviews: every task's customer and executed wording, category, condition, assumptions, unresolved
                                    values, capability, persona and journey; coverage and gaps. Public only: no expected answers.
  decide(store, suite, decision)    records an Approval (approved | rejected) of the EXACT suite hash. The owner types an attestation naming the
                                    decision and the full hash. A real (non-'synthetic-') suite can only be decided at an interactive terminal: an
                                    automated process (an agent, CI) can never approve or reject one. Synthetic fixtures are labelled as such.
  freeze(store, suite, approval)    FrozenSuite (the store requires an APPROVED approval of exactly this hash) and a write-once ref name@vN.
  revise(store, suite, ...)         a substantive edit: a NEW suite version (new hash) that references the old one; the old approval does not apply.
  clarify(...)                      the proposed capture of a human clarification of a natural_underspecified request: the customer's wording is
                                    kept, the clarified value is re-validated by evaluator v2, and the task becomes an ASSISTED task whose
                                    assumption names who clarified it and when (never a natural task).

    python -m agent_readiness.suites.stage_a.approval review STORE SUITE_SHA [--markdown]
    python -m agent_readiness.suites.stage_a.approval decide STORE SUITE_SHA approved|rejected [--notes TEXT]     # owner, interactive terminal
    python -m agent_readiness.suites.stage_a.approval freeze STORE SUITE_SHA APPROVAL_SHA
    python -m agent_readiness.suites.stage_a.approval revise STORE SUITE_SHA --keep TASK_ID [TASK_ID ...] --context-site larkspur --at ISO --by owner --notes TEXT
                                    (M9) a new suite version keeping only the named tasks (a proposal: it still needs `decide` and `freeze`; the old
                                    version is unchanged). With the same inputs and --at the new hash is reproducible, so the owner can check it
                                    before approving."""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from ...taskeval.v2 import coverage as COV
from ..records import Approval, FrozenSuite, InputRef, Provenance, SuiteRecord
from ..store import WriteOnceStore

VERSION = "approval-1"
SYNTHETIC_PREFIX = "synthetic-"


class ApprovalRefused(PermissionError):
    pass


def attestation_text(suite_sha: str, decision: str) -> str:
    return f"I am the owner and I {'approve' if decision == 'approved' else 'reject'} suite {suite_sha}"


def review_packet(store: WriteOnceStore, suite_sha: str) -> dict:
    view = store.public_suite_view(suite_sha)
    tasks = []
    for t in view["tasks"]:
        w = t["wording"]
        tasks.append({"task_id": t["task_id"], "sha256": t["sha256"], "persona": t["persona"], "journey": t["journey"], "capability": t["capability"],
                      "category": w["category"], "condition": {"natural_verifiable": "natural", "natural_judgment": "natural", "assisted_restatement": "assisted"}.get(w["category"]),
                      "verifiability": t["spec"]["verifiability"], "customer_wording": w["customer"], "executed_wording": w["executed"],
                      "interpretation_decisions": w["interpretation_decisions"], "assumptions": w["assumptions"], "unresolved": w["unresolved"],
                      "criterion": t["spec"]["criterion"], "limits": t["limits"]})
    return {"version": VERSION, "suite": {k: view[k] for k in ("sha256", "suite_name", "version", "site", "selection_rule", "gaps", "agent_evidence_consulted")},
            "synthetic": view["suite_name"].startswith(SYNTHETIC_PREFIX), "provenance": view["provenance"], "coverage": view["coverage"],
            "counts": {"tasks": len(tasks), "by_condition": dict(Counter(str(t["condition"]) for t in tasks)), "by_category": dict(Counter(t["category"] for t in tasks))},
            "tasks": tasks,
            "checklist": ["Each customer wording is something a real customer would say.", "Each natural task executes the customer's words unchanged.",
                          "Every assumption of an assisted task is acceptable and labelled; assisted results will be analysed separately.",
                          "No task wording reveals its answer.", "The coverage gaps are acceptable for this evaluation.",
                          "Approval applies to exactly this hash; any edit creates a new version that needs a new approval."],
            "attestation": {"approve": attestation_text(view["sha256"], "approved"), "reject": attestation_text(view["sha256"], "rejected")}}


def render_markdown(packet: dict) -> str:
    s = packet["suite"]
    lines = [f"# Suite review: {s['suite_name']} v{s['version']} ({s['site']})", "", f"Hash: `{s['sha256']}`" + ("  **SYNTHETIC FIXTURE**" if packet["synthetic"] else ""),
             f"Selection: {s['selection_rule']}; agent evidence consulted: {s['agent_evidence_consulted']}", "", "## Tasks", ""]
    for t in packet["tasks"]:
        lines += [f"- **{t['task_id']}** [{t['condition'] or 'not executed'} / {t['category']} / {t['capability']}] persona {t['persona']}, journey {t['journey']}",
                  f"  - customer: {t['customer_wording']}"] + ([f"  - executed: {t['executed_wording']}"] if t["executed_wording"] and t["executed_wording"] != t["customer_wording"] else []) \
            + [f"  - assumption: {a}" for a in t["assumptions"]] + [f"  - unresolved: {u}" for u in t["unresolved"]]
    lines += ["", "## Gaps", ""] + [f"- {g}" for g in s["gaps"]] + ["", "## Checklist", ""] + [f"- [ ] {c}" for c in packet["checklist"]]
    lines += ["", "To approve, type exactly:", "", f"    {packet['attestation']['approve']}"]
    return "\n".join(lines) + "\n"


def decide(store: WriteOnceStore, suite_sha: str, *, decision: str, attestation: str, at: str, notes: str = "") -> str:
    suite = store.get("suite", suite_sha)
    if attestation.strip() != attestation_text(suite_sha, decision):
        raise ApprovalRefused(f"the attestation must read exactly: {attestation_text(suite_sha, decision)!r}")
    synthetic = suite.suite_name.startswith(SYNTHETIC_PREFIX)
    if not synthetic and not sys.stdin.isatty():
        raise ApprovalRefused("a real suite can only be approved or rejected by the owner at an interactive terminal (no automated approvals)")
    if synthetic:
        notes = f"[SYNTHETIC FIXTURE: test decision, not an owner decision about a real suite] {notes}".strip()
    return store.put(Approval(suite_sha256=suite_sha, decision=decision, approved_at=at, notes=notes))


def freeze(store: WriteOnceStore, suite_sha: str, approval_sha: str, *, at: str) -> str:
    suite = store.get("suite", suite_sha)
    sha = store.put(FrozenSuite(suite_sha256=suite_sha, approval_sha256=approval_sha, frozen_at=at))
    store.ref("frozen_suite", f"{suite.suite_name}@v{suite.version}", sha)
    return sha


def _coverage(store: WriteOnceStore, task_shas, context: dict) -> dict:
    tasks = []
    for sha in task_shas:
        t = store.get("task", sha)
        crit = t.spec.criterion or None
        attrs = sorted({c["label"] for c in (crit or {}).get("conditions", [])} | ({crit["label"]} if crit and "label" in crit else set()))
        if t.spec.verifiability in ("deterministic", "rubric"):
            tasks.append({"id": t.task_id, "persona": t.persona, "journey": t.journey, "capability": t.capability, "condition": t.condition,
                          "verifiability": t.spec.verifiability, "criterion": crit, "attributes": attrs})
    cov = COV.report(tasks, context)
    return {k: cov[k] for k in ("targets", "matrix", "per_persona", "per_journey", "capabilities", "multi_condition_share", "natural_share", "deterministic", "rubric", "status")}, cov["gaps"]


def revise(store: WriteOnceStore, suite_sha: str, context: dict, *, add: tuple[str, ...] = (), remove: tuple[str, ...] = (), at: str, notes: str,
           by: str = "system") -> str:
    """A substantive edit: a new version with a new hash; coverage and gaps are recomputed; the previous version is referenced (kind 'suite').
    `by` is the role that PREPARED the revision ('system' for an agent-prepared proposal): a revision is only a proposal, never an approval, and it
    must not claim owner authorship unless the owner made it."""
    old = store.get("suite", suite_sha)
    shas = tuple(t for t in old.task_sha256s if t not in set(remove)) + tuple(t for t in add if t not in old.task_sha256s)
    if shas == old.task_sha256s:
        raise ValueError("no substantive change")
    cov, gaps = _coverage(store, shas, context)
    prov = Provenance(created_at=at, created_by=by, tool="agent_readiness.suites.stage_a.approval.revise", tool_version=VERSION,
                      config_fingerprint=old.provenance.config_fingerprint, inputs=tuple(old.provenance.inputs) + (InputRef(kind="suite", name=f"{old.suite_name}@v{old.version}", sha256=suite_sha),),
                      notes=f"revision of v{old.version}: {notes}")
    return store.put(SuiteRecord(suite_name=old.suite_name, version=old.version + 1, site=old.site, task_sha256s=shas, selection_rule=old.selection_rule + "+owner-revision",
                                 coverage=cov, gaps=tuple(gaps) + tuple(g for g in old.gaps if g.startswith("preserved underspecified")), provenance=prov))


def clarify(site, view: dict, context: dict, raw: dict, values: dict[str, str], *, store: WriteOnceStore, at: str, by: str = "owner", candidate_id: str = "clarified") -> str:
    """Re-validate an underspecified request with the clarified constraint values; returns the stored ASSISTED TaskRecord's hash."""
    from ...taskeval.v2 import evaluator as E2
    from .loop import M2B_KINDS
    from .taskrecords import build
    missing = [a for a in values if a not in {c.get("attribute") for c in raw.get("constraints", [])}]
    if missing:
        raise ValueError(f"no constraint on {missing} to clarify")
    raw2 = {**raw, "constraints": [{**c, "value": values.get(c["attribute"], c.get("value"))} for c in raw["constraints"]]}
    label = f"clarification recorded by the {by} at {at}"
    ev = E2.TaskEvaluatorV2(site, view, context, config={"new_kinds": list(M2B_KINDS), "assumption_label": label})
    recs = ev.evaluate([{"candidate_id": candidate_id, "provenance": {"source": "clarification", "by": by, "at": at, "values": values}, "raw": raw2}])
    derived = [r for r in recs if r.get("derived_from") and r["admission"] == "assisted"]
    if not derived:
        raise ValueError(f"the clarified request does not pass evaluator v2: {[r['rejection_reasons'] for r in recs if r['admission'] == 'rejected']}")
    r = derived[0]
    inputs = (InputRef(kind="catalogue", name=f"{site.id}-catalogue-view", sha256=_sha(view)), InputRef(kind="context", name=f"{site.id}-context", sha256=_sha(context)))
    task, priv = build(r, site=site.id, snapshot_sha256=site.snapshot(site.variants[0]).sha256, oracle_label=site.oracle().label, created_at=at, inputs=inputs, tool_version=VERSION)
    store.put(priv)
    return store.put(task)


def _sha(obj) -> str:
    from ...suite.core import canonical_hash
    return canonical_hash(obj)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="agent_readiness.suites.stage_a.approval")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("review"); r.add_argument("store", type=Path); r.add_argument("suite"); r.add_argument("--markdown", action="store_true")
    d = sub.add_parser("decide"); d.add_argument("store", type=Path); d.add_argument("suite"); d.add_argument("decision", choices=("approved", "rejected")); d.add_argument("--notes", default="")
    f = sub.add_parser("freeze"); f.add_argument("store", type=Path); f.add_argument("suite"); f.add_argument("approval")
    v = sub.add_parser("revise"); v.add_argument("store", type=Path); v.add_argument("suite"); v.add_argument("--keep", nargs="+", required=True, metavar="TASK_ID")
    ctx = v.add_mutually_exclusive_group(required=True); ctx.add_argument("--context-site", choices=("larkspur",)); ctx.add_argument("--context", type=Path)
    v.add_argument("--at", required=True); v.add_argument("--by", default="system", choices=("system", "owner")); v.add_argument("--notes", required=True)
    a = ap.parse_args(argv)
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    store = WriteOnceStore(a.store)
    if a.cmd == "review":
        p = review_packet(store, a.suite)
        print(render_markdown(p) if a.markdown else json.dumps(p, indent=1))
    elif a.cmd == "decide":
        if not sys.stdin.isatty():
            print("refused: decisions are typed by the owner at an interactive terminal", file=sys.stderr)
            return 2
        print(f"Type exactly: {attestation_text(a.suite, a.decision)}")
        print(decide(store, a.suite, decision=a.decision, attestation=input("> "), at=now, notes=a.notes))
    elif a.cmd == "revise":
        print(revise_keep(store, a.suite, keep=a.keep, context=_context(a), at=a.at, by=a.by, notes=a.notes))
    else:
        print(freeze(store, a.suite, a.approval, at=now))
    return 0


def _context(a) -> dict:
    if a.context:
        return json.loads(Path(a.context).read_text())
    from ...research.taskplan.context import CONTEXT          # the Larkspur business context the suite was generated against (Stage A input)
    return json.loads(json.dumps(CONTEXT))


def revise_keep(store: WriteOnceStore, suite_sha: str, *, keep: list[str], context: dict, at: str, by: str, notes: str) -> str:
    """(M9) `revise` that KEEPS the named tasks (by task id) and removes the rest. Every named id must be a task of the suite."""
    old = store.get("suite", suite_sha)
    ids = {store.get("task", sha).task_id: sha for sha in old.task_sha256s}
    unknown = sorted(set(keep) - set(ids))
    if unknown or not keep:
        raise ValueError(f"not tasks of suite {suite_sha[:12]}: {', '.join(unknown) or '(none named)'}")
    return revise(store, suite_sha, context, remove=tuple(sha for tid, sha in ids.items() if tid not in set(keep)), at=at, notes=notes, by=by)


if __name__ == "__main__":
    sys.exit(main())
