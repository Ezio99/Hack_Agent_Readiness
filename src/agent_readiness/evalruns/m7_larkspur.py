"""Lifecycle M7: the first paid Stage B browser-agent evaluation on Larkspur (owner instruction 2026-11-02, amended: 6 natural tasks x 2 variants x 1
repetition = 12 trials, proposed cap US$8.00, conditional on the owner approving and freezing the suite at an interactive terminal).

    python -m agent_readiness.evalruns.m7_larkspur revise          # zero cost: v1 (immutable) -> v2 proposal with the six selected tasks
    python -m agent_readiness.evalruns.m7_larkspur packet          # zero cost: review packet (no answers)
    python -m agent_readiness.evalruns.m7_larkspur rehearse-synthetic   # zero cost: the same six tasks under a synthetic name, dev provider
    --- owner: review / decide approved / freeze at an interactive terminal (commands in the review packet) ---
    python -m agent_readiness.evalruns.m7_larkspur manifest FROZEN_SHA  # zero cost: the exact manifest + worst-case check (refuses > cap)
    python -m agent_readiness.evalruns.m7_larkspur rehearse MANIFEST    # zero cost: rehearsal of the byte-identical manifest
    python -m agent_readiness.evalruns.m7_larkspur paid MANIFEST --instruction "..."   # paid, guarded by evalruns.authorization

No Stage A model call: the six tasks come from the recorded M6 proposals (the three not in the v1 proposal are re-validated offline by evaluator v2,
deterministically, exactly as in the M6 post-fix re-evaluation). Nothing here approves or freezes a real suite."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from ..framework.site import get
from ..research.taskplan import catalogue as K
from ..research.taskplan import context as X
from ..research.taskplan import planner_v2 as PV2
from ..suite.core import canonical_hash
from ..taskeval.v2 import evaluator as E2
from ..suites.records import InputRef, SuiteRecord
from ..suites.stage_a import approval as AP
from ..suites.stage_a import loop as LP
from ..suites.stage_a import taskrecords as TR
from ..suites.store import WriteOnceStore

ROOT = Path(__file__).resolve().parents[3]
STAGE_A = ROOT / "scanner-data" / "research" / "stage-a"
STORE = STAGE_A / "store"
M6_RUN = STAGE_A / "m6-larkspur-core-20261102T121242Z"
V1 = "873e07c306cafc6772706c528391ffe5ef734eb7e3ca6216e2bd780b81e8ed89"
STAGE_B = ROOT / "scanner-data" / "research" / "stage-b"
EXPERIMENT_ID = "m7-larkspur-browser-1"
CAP_USD, MAX_TRIALS, REPETITIONS, SEED = 8.0, 12, 1, 7
REVISION_AT = "2026-11-02T14:00:00+00:00"                          # fixed: the revision is deterministic and reproducible
SELECTED = [  # (candidate id, slot) - chosen for coverage, realism and persona/journey spread; never from expected agent outcomes
    ("r1-t04_affordable_short", "multi-condition filter"),
    ("r1-t03_weekend_beginner", "either/or scheduling"),
    ("r2-upskiller-riverside-most-seats", "filtered ranking"),
    ("r2-budget-life-drawing-fee", "factual lookup"),
    ("r1-t08_budget_with_seats", "availability (multi-condition; the M6 false rejection, corrected)"),
    ("r1-t06_intermediate_northside", "distinct journey: match_level"),
]
CONCERNS = {
    "r1-t01_beginner_riverside_included": "catalogue-speak: capitalised 'Beginner', 'Included'",
    "r1-t02_lookup_pottery_day": "names the field label ('what class day'); otherwise realistic",
    "r1-t03_weekend_beginner": "realistic; both alternatives contribute",
    "r1-t04_affordable_short": "realistic; the vague 'cheap, quick' is backed by explicit values",
    "r1-t05_lookup_meditation_fee": "realistic",
    "r1-t06_intermediate_northside": "terse but realistic; capitalised 'Intermediate'",
    "r1-t08_budget_with_seats": "plain; rejected AS RUN by the 'at least' lexicon bug, admitted after the fix (M6 §4.1)",
    "r1-t12_lookup_duration_spreadsheets": "redundant field label ('how long is the duration?')",
    "r2-budget-cheap-under-200": "realistic",
    "r2-upskiller-intermediate-seats": "realistic; rejected AS RUN by the 'at least' lexicon bug, admitted after the fix",
    "r2-budget-riverside-fee": "realistic",
    "r2-upskiller-thursday-intermediate": "realistic; 'busy, but Thursdays' traced only via the second 'Thursday' (negation window does not reset at 'but')",
    "r2-switcher-beginner-materials-budget": "catalogue-speak ('materials are Included')",
    "r2-recent-cheapest-beginner": "repetitive ('I'm a Beginner - what's the cheapest Beginner course?')",
    "r2-upskiller-riverside-most-seats": "realistic; ranking among a filtered subset of 2",
    "r2-switcher-watercolour-seats": "repeats the course name; otherwise realistic",
    "r2-budget-life-drawing-fee": "repeats the course name; otherwise realistic",
    "r2-switcher-webpages-materials": "FLAG: yes/no-shaped ('are materials Included?') while the graded answer is a value; recommend EXCLUDING",
    "r2-recent-saturday-courses": "realistic",
    "r2-budget-beginner-short": "FLAG: 'lasts 4 weeks' is specified as EXACTLY 4 weeks; a customer may mean 'about' or 'at most' (possible ambiguity)",
}


def _records():
    """Evaluator v2 (current code) over the recorded M6 proposals: deterministic and offline (no model call)."""
    site = get("larkspur")
    props = json.loads((M6_RUN / "proposals.json").read_text())
    recs = E2.TaskEvaluatorV2(site, K.view(site), X.CONTEXT, config={"new_kinds": LP.M2B_KINDS}).evaluate(
        [{"candidate_id": p["candidate_id"], "provenance": p["provenance"], "raw": p["raw"]} for p in props])
    return site, props, recs


def revise() -> dict:
    site, props, recs = _records()
    store = WriteOnceStore(STORE)
    v1 = store.get("suite", V1)
    v1_tasks = {store.get("task", t).wording.customer: t for t in v1.task_sha256s}
    by_id = {r["candidate_id"]: r for r in recs}
    loop = json.loads((M6_RUN / "loop.json").read_text())
    view = K.view(site)
    inputs = (InputRef(kind="catalogue", name="larkspur-catalogue-view", sha256=canonical_hash(view)),
              InputRef(kind="context", name=f"larkspur-context ({X.LABEL[:60]})", sha256=canonical_hash(X.CONTEXT)),
              InputRef(kind="snapshot", name="larkspur@original", sha256=site.snapshot("original").sha256),
              InputRef(kind="generator", name=f"meta:{PV2.PROMPT_VERSION}", sha256=canonical_hash(loop["generator"])),
              InputRef(kind="evaluator", name=f"{E2.VERSION}:{recs[0]['evaluator']['config_fingerprint']} (offline re-evaluation, M6 post-fix)", sha256=canonical_hash(recs[0]["evaluator"])),
              InputRef(kind="proposals", name=f"{len(props)} recorded M6 proposals", sha256=canonical_hash([p["raw"] for p in props])))
    chosen, added = [], []
    for cid, _ in SELECTED:
        r = by_id[cid]
        if r["admission"] != "natural":
            raise ValueError(f"{cid} is not admitted as natural_verifiable")
        sha = v1_tasks.get(r["wording"]["customer"])
        if sha is None:                                                  # not in v1: built from the offline re-evaluation (no model call)
            task, priv = TR.build(r, site="larkspur", snapshot_sha256=site.snapshot("original").sha256, oracle_label=site.oracle().label, created_at=REVISION_AT,
                                  inputs=inputs, tool_version="m7-revision")
            store.put(priv)
            sha = store.put(task)
            added.append(sha)
        chosen.append(sha)
    remove = tuple(t for t in v1.task_sha256s if t not in chosen)
    v2 = AP.revise(store, V1, X.CONTEXT, add=tuple(added), remove=remove, at=REVISION_AT, by="system",
                   notes="M7: six natural-verifiable tasks for the first paid Stage B evaluation (agent-prepared from recorded M6 proposals; "
                         "3 kept from v1, 3 re-validated offline after the M6 lexicon fix); PROPOSAL ONLY, needs the owner's approval")
    return {"v1": V1, "v2": v2, "kept_from_v1": [c for c in chosen if c not in added], "added": added, "removed": list(remove)}


def packet(rev: dict) -> str:
    site, props, recs = _records()
    store = WriteOnceStore(STORE)
    from ..investigate.inspect.profile import build_profile
    from ..investigate.taskgen import freeze as freezer
    from ..taskeval.v2 import kinds as KD
    profs = {v: build_profile(site.snapshot(v)) for v in site.variants}
    sel = {cid: slot for cid, slot in SELECTED}
    v1_words = {store.get("task", t).wording.customer for t in store.get("suite", V1).task_sha256s}
    lines = ["# M7 review packet: Larkspur Stage B suite (no expected answers)", "",
             "Source: the 24 recorded M6 Muse Spark proposals (no new model call), evaluated by evaluator v2 at the current commit (deterministic; the M6 'at least' "
             "lexicon fix included). `in v1` = part of the immutable M6 proposal `larkspur-core` v1. Detail pages = pages beyond the listing the evidence rule requires "
             "on each variant (fewer on modified when its listing cards show the decisive facts).", "",
             "## All natural-verifiable candidates", "",
             "| Candidate | Executed wording (= customer wording) | Capability | Persona / journey | In v1 | Max requests | Detail pages (orig / mod) | Notes |",
             "|---|---|---|---|---|---|---|---|"]
    for r in recs:
        if r["admission"] != "natural":
            continue
        a = r["_accepted"]
        det = [len(KD.compile_any(a.criterion, profs[v]).evidence_paths) - 1 for v in site.variants]
        mark = f"**SELECTED: {sel[r['candidate_id']]}**. " if r["candidate_id"] in sel else ""
        lines.append(f"| `{r['candidate_id']}` | {r['wording']['executed']} | {r['capability']} | {r['persona']} / {r['journey']} | {'yes' if r['wording']['customer'] in v1_words else 'no'} | "
                     f"{freezer._limits(a.hops).max_model_requests} | {det[0]} / {det[1]} | {mark}{CONCERNS.get(r['candidate_id'], '')} |")
    lines += ["", "Not natural-verifiable: `r1-t09_refund_policy` (natural_judgment, policy rubric: not scored deterministically, excluded from Stage B); "
              "`r1-t07` (spec changed 'under' to 'at most'), `r1-t10` (ranking within a filter of one item), `r1-t11` (degenerate either/or): correct rejections.", "",
              "## Selection (six natural-verifiable tasks)", ""]
    for cid, slot in SELECTED:
        r = next(x for x in recs if x["candidate_id"] == cid)
        lines.append(f"- **{slot}**: \"{r['wording']['executed']}\" ({r['persona']} / {r['journey']}; `{cid}`)")
    lines += ["", "Coverage of the six: personas recent_graduate 2, budget_learner 2, career_switcher 1, professional_upskiller 1; journeys find_affordable 2, "
              "check_availability 2, fit_schedule 1, match_level 1 (plan_commitment not covered); capabilities multi-condition filter 3, either_of 1, ranked_subset 1, lookup 1.",
              "Excluded on quality: the yes/no-shaped materials lookup (`r2-switcher-webpages-materials`) and the exact-'4 weeks' task (`r2-budget-beginner-short`); "
              "no wording was rewritten.", "",
              "**Provisional suite targets NOT met by v2** (reported, not lowered): " + "; ".join(
                  f"{k}: {v['actual']} (target {v['target']})" for k, v in store.get('suite', rev['v2']).coverage['status'].items() if not v['met'])
              + ". The six-task size is the owner's budget design for this first paid evaluation; the targets were written for 8-12-task suites.", "",
              "**Answers and this packet:** no task's wording contains its own expected answer (acceptance gate). Course names do appear in lookup wordings, and a few "
              "of those courses are among the answers of OTHER tasks (e.g. a lookup names a course that a filter task selects). That links no answer to its task; "
              "a global substring scan flags it, the per-task check does not. The agent never sees this packet.", "",
              "## Revision (v1 is preserved, immutable)", "",
              f"- v1 `larkspur-core` (13 tasks, unchanged): `{rev['v1']}`",
              f"- v2 proposal `larkspur-core` (6 tasks; prepared by the system, NOT approved): `{rev['v2']}`",
              f"- kept from v1: {len(rev['kept_from_v1'])}; added (re-validated offline): {len(rev['added'])}; removed from v1: {len(rev['removed'])}", "",
              "## Owner checkpoint: commands (run them yourself, in an interactive terminal; not through an agent)", "",
              "```bash", "cd ~/Projects/Hack_Agent_Readiness",
              f".venv/bin/python -m agent_readiness.suites.stage_a.approval review scanner-data/research/stage-a/store {rev['v2']} --markdown",
              f".venv/bin/python -m agent_readiness.suites.stage_a.approval decide scanner-data/research/stage-a/store {rev['v2']} approved --notes \"M7: six-task Larkspur suite\"",
              "#   type exactly the attestation it prints; it prints the APPROVAL hash",
              f".venv/bin/python -m agent_readiness.suites.stage_a.approval freeze scanner-data/research/stage-a/store {rev['v2']} <APPROVAL_SHA>",
              "#   it prints the FROZEN SUITE hash: send it back to continue", "```", ""]
    return "\n".join(lines) + "\n"


def synthetic_copy(rev: dict) -> str:
    """The same six tasks under a 'synthetic-' name (for a pre-freeze rehearsal; a synthetic suite can never authorise paid execution)."""
    store = WriteOnceStore(STORE)
    v2 = store.get("suite", rev["v2"])
    s = store.put(SuiteRecord(**{**v2.model_dump(), "suite_name": "synthetic-larkspur-core-m7-rehearsal"}))
    a = AP.decide(store, s, decision="approved", attestation=AP.attestation_text(s, "approved"), at=REVISION_AT, notes="pre-freeze rehearsal of the M7 tasks")
    return AP.freeze(store, s, a, at=REVISION_AT)


def build_manifest(frozen_sha: str, at: str) -> tuple[str, dict]:
    from . import manifest as MF
    from ..suites import plan as PL
    store = WriteOnceStore(STORE)
    site = get("larkspur")
    _, _, tasks = MF.suite_tasks(store, frozen_sha)
    det = [t for t in tasks if t.spec.verifiability == "deterministic"]
    plan = PL.make_plan(n_tasks=len(det), repetitions=REPETITIONS, requested="exploratory", sims=500,
                        primary_outcome="evidence-supported pass (official grader v1), natural-wording condition")
    m = MF.build(store, frozen_sha, variants=[(v, site.snapshot(v).sha256) for v in site.variants], oracle=site.oracle().label, plan=plan,
                 repetitions=REPETITIONS, seed=SEED, created_at=at, hard_cap_usd=CAP_USD)
    trials = len(det) * len(site.variants) * REPETITIONS
    detail = {"trials": trials, "worst_case_reservation_usd": m.budget["worst_case_reservation_usd"], "cap_usd": CAP_USD, "within_cap": m.budget["within_cap"],
              "per_request_cap_usd": m.budget["per_request_cap_usd"], "max_requests_per_trial": sorted({t.limits.max_model_requests for t in det})}
    if trials > MAX_TRIALS or not m.budget["within_cap"]:
        raise ValueError(f"design refused (no relaxation): {detail}")
    return store.put(m), detail


def rehearse(manifest_sha: str, label: str) -> dict:
    from . import runner as RN
    store = WriteOnceStore(STORE)
    root = STAGE_B / "rehearsals"
    runs = RN.prepare(store, manifest_sha, root, mode="rehearsal", label=label)
    ex = {c: RN.execute(r, store) for c, r in runs.items()}
    doc = RN.report(store, manifest_sha, runs, created_at=datetime.now(timezone.utc).isoformat(timespec="seconds"))
    pub = root / f"report-{label}-{manifest_sha[:10]}.public.json"
    (root / f"report-{label}-{manifest_sha[:10]}.private.json").write_text(json.dumps(doc, indent=1, default=str))
    pub.write_text(json.dumps(RN.public_report(doc), indent=1, default=str))
    audit = RN.audit_public(store, manifest_sha, runs, [pub])
    return {"executed": {c: len(e["executed"]) for c, e in ex.items()}, "stopped": {c: e["stopped"] for c, e in ex.items()}, "jail": {c: e["jail_selftest"].get("ok") for c, e in ex.items()},
            "tallies": {c: d["tallies"] for c, d in doc["exploratory"].items()}, "faithful": {c: d["rescore_faithful"] for c, d in doc["exploratory"].items()},
            "complete": {c: d["complete"] for c, d in doc["exploratory"].items()}, "invalidated": {c: d["invalidated"] for c, d in doc["exploratory"].items()},
            "audit": {k: audit[k] for k in ("checked", "answers_checked", "clean")}, "runs": {c: str(r.dir) for c, r in runs.items()}}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="agent_readiness.evalruns.m7_larkspur")
    ap.add_argument("cmd", choices=("revise", "packet", "rehearse-synthetic", "manifest", "rehearse"))
    ap.add_argument("sha", nargs="?")
    a = ap.parse_args(argv)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    if a.cmd == "revise":
        print(json.dumps(revise(), indent=1))
    elif a.cmd == "packet":
        out = ROOT / "collaboration" / "reports" / "lifecycle-m7-review-packet.md"
        out.write_text(packet(revise()))
        print(out)
    elif a.cmd == "rehearse-synthetic":
        fz = synthetic_copy(revise())
        msha, detail = build_manifest(fz, REVISION_AT)
        print(json.dumps({"synthetic_frozen": fz, "manifest": msha, "design": detail, "rehearsal": rehearse(msha, "synthetic")}, indent=1, default=str))
    elif a.cmd == "manifest":
        msha, detail = build_manifest(a.sha, now)
        print(json.dumps({"manifest": msha, "design": detail}, indent=1))
    elif a.cmd == "rehearse":
        print(json.dumps(rehearse(a.sha, "exact"), indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
