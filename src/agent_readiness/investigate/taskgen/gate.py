"""The acceptance gate every candidate task passes (model-proposed, owner-defined or rule-generated alike). A rejected task is kept with its reason (no expected answers in reasons).

Checks: compiles against the snapshot; answer derived by code (never supplied); feasible (every evidence page reachable by links from the start page within MAX_HOPS); not trivial
(no evidence on the start page itself, at least one navigation step; sets select some-but-not-all; no yes/no answers); not leaking (answer not in the question, not on the start page);
not ambiguous (the question names its target entity / thresholds / field); not a duplicate (same criterion signature or near-identical wording); blind (no protected diagnosis text)."""
from __future__ import annotations

import re
from collections import deque
from dataclasses import dataclass, field, replace

from ...suite.core import canonical_hash
from ..zoo.sealed import BlindnessError, assert_blind
from .criteria import Compiled, Criterion, CriterionError, compile_criterion, norm_answer, resolve_target

MAX_HOPS = 4
MIN_QUESTION_CHARS = 20
DUP_JACCARD = 0.8
YES_NO = {"yes", "no", "true", "false"}


@dataclass
class Draft:
    question: str
    start_path: str
    criterion: dict
    source: str = "model"            # model | owner | rule
    rationale: str = ""


@dataclass
class Accepted:
    draft: Draft
    compiled: Compiled
    criterion: dict
    fingerprint: str
    hops: dict[str, int] = field(default_factory=dict)


@dataclass
class Rejected:
    draft: Draft
    reason: str


def hop_distances(profile: dict, start: str) -> dict[str, int]:
    pages = profile["pages"]
    if start not in pages:
        return {}
    dist, q = {start: 0}, deque([start])
    while q:
        cur = q.popleft()
        rec = pages[cur]
        for l in rec["links"] + rec["nav_links"]:
            if l["href"] in pages and l["href"] not in dist:
                dist[l["href"]] = dist[cur] + 1
                q.append(l["href"])
    return dist


def _tokens(s: str) -> set[str]:
    return {t for t in norm_answer(s).split() if len(t) > 2}


def _entity_tokens(profile: dict, path: str) -> set[str]:
    """Tokens that single a page out: its title/h1 words that are not common to most other titles."""
    pages = profile["pages"]
    own = _tokens(pages[path]["title"]) | _tokens(" ".join(h["text"] for h in pages[path]["headings"][:1]))
    others = [_tokens(p["title"]) for q, p in pages.items() if q != path]
    return {t for t in own if sum(t in o for o in others) <= len(others) / 2}


def _signature(criterion: dict, start: str) -> str:
    return canonical_hash({"c": criterion, "s": start})


def evaluate(draft: Draft, profile: dict, accepted: list[Accepted]) -> Accepted | Rejected:
    proposed = draft                                                       # outcomes always carry the draft AS PROPOSED (accounting keys on it); `draft` below may be the title-resolved working copy

    def no(reason):
        return Rejected(proposed, reason)
    q = draft.question.strip()
    if len(q) < MIN_QUESTION_CHARS or len(q) > 400:
        return no("question length is outside 20-400 characters")
    try:
        assert_blind(q)
    except BlindnessError:
        return no("question text would reveal a protected diagnosis")
    if draft.criterion.get("kind") == "reach_page" and isinstance(draft.criterion.get("target"), str):          # a title is resolved to its captured path first, so every later check and the stored criterion use the path
        try:
            draft = replace(draft, criterion={**draft.criterion, "target": resolve_target(profile, draft.criterion["target"])})
        except CriterionError as exc:
            return no(f"criterion does not compile: {exc}")
    try:
        crit = compile_criterion(draft.criterion, profile)
        again = compile_criterion(draft.criterion, profile)
    except CriterionError as exc:
        return no(f"criterion does not compile: {exc}")
    except Exception as exc:                                               # malformed spec (validation error) — never crash the pipeline on model output
        return no(f"criterion is malformed ({type(exc).__name__})")
    if crit.truth != again.truth:
        return no("expected answer is not stable under re-extraction")
    if draft.start_path not in profile["pages"]:
        return no("start page is not part of the snapshot")
    truths = [crit.truth] if isinstance(crit.truth, str) else list(crit.truth)
    if any(norm_answer(t) in YES_NO for t in truths):
        return no("yes/no answers are not accepted (guessable)")
    dist = hop_distances(profile, draft.start_path)
    missing = [p for p in crit.evidence_paths if p not in dist]
    if missing:
        return no(f"evidence page(s) not reachable by links from the start page: {missing[:3]}")
    if any(dist[p] == 0 for p in crit.evidence_paths) and crit.kind in ("page_fact", "reach_page"):
        return no("the answer is on the start page itself (derivable from the first observation)")
    far = max((dist[p] for p in crit.evidence_paths), default=0)
    if far > MAX_HOPS:
        return no(f"evidence is {far} link steps away (limit {MAX_HOPS})")
    if far < 1:
        return no("no navigation is needed")
    qn = norm_answer(q)
    if any(norm_answer(t) in qn for t in truths if len(norm_answer(t)) >= 3):
        return no("the question contains the expected answer")
    start_text = norm_answer(profile["pages"][draft.start_path]["text"] + " " + profile["pages"][draft.start_path]["title"])
    if crit.style == "string" and norm_answer(crit.truth) in start_text and crit.kind != "extremum":
        return no("the expected answer is visible on the start page")
    # ambiguity: the question must single out its target
    c = draft.criterion
    if c["kind"] == "page_fact":
        ent = _entity_tokens(profile, c["page"])
        if ent and not (ent & _tokens(q)):
            return no("the question does not name the page/entity it asks about (ambiguous)")
    if c["kind"] == "item_set":
        for cond in c["conditions"]:
            if norm_answer(cond["value"]) not in qn or not (_tokens(cond["label"]) & _tokens(q)):
                return no("the question does not state every condition's field and threshold (ambiguous)")
    if c["kind"] == "extremum" and not (_tokens(c["label"]) & _tokens(q)):
        return no("the question does not name the compared field (ambiguous)")
    if c["kind"] == "reach_page" and (_tokens(profile["pages"][c["target"]]["title"]) and _tokens(profile["pages"][c["target"]]["title"]) <= _tokens(q)):
        return no("the question contains the target page's title")
    sig = _signature(draft.criterion, draft.start_path)
    for a in accepted:
        if a.fingerprint == sig:
            return no("duplicate of an accepted task (same criterion and start page)")
        ta, tb = _tokens(a.draft.question), _tokens(q)
        if ta and tb and len(ta & tb) / len(ta | tb) >= DUP_JACCARD and a.compiled.truth == crit.truth:
            return no("near-duplicate wording of an accepted task with the same answer")
    return Accepted(proposed, crit, draft.criterion, sig, {p: dist[p] for p in crit.evidence_paths})
