"""Accept or reject generated candidates. A candidate is accepted only when ALL of the following hold; every rejection carries its reason.

  independent   the truth recomputed from the rendered control pages equals the truth computed from the source data
  unambiguous   no ties, no `AMBIGUOUS` recomputation, sets are neither empty nor larger than 6, dates fall in the booking window, money is positive
  possible      every visit page and the start page exist in the crawled snapshot and are reachable from the home page within 4 clicks
  displayable   for EVERY arm of the site (control and each candidate variant) at least one route per fact can be satisfied from the rendered pages, so the task is winnable by evidence in every arm
  no leak       the question does not contain the answer (names, amounts or dates), and carries no hidden catalogue identifiers beyond what pages show
  gradeable     the grader accepts the canonical answer, rejects at least two plausible wrong answers, and rejects hedges that offer the right and a wrong answer
  not a repeat  no repeated fingerprint, no repeated question text, and no second task with the same family, template, truth and visit set
"""
from __future__ import annotations

import re
from collections import deque
from dataclasses import dataclass
from datetime import date, timedelta

from bs4 import BeautifulSoup

from ..sites.ironbark import data as D
from . import answers as A
from .evidence import available_in
from .facts import PageFacts
from .tasks import PRODUCT, Candidate

MAX_SET = 6
MAX_PAGES_NEEDED = 12


@dataclass
class Report:
    accepted: list[Candidate]
    rejected: list[dict]


def link_depths(pages: dict[str, str]) -> dict[str, int]:
    depth, queue = {"/": 0}, deque(["/"])
    while queue:
        p = queue.popleft()
        for a in BeautifulSoup(pages[p], "html.parser").find_all("a", href=True):
            t = a["href"].split("#")[0].rstrip("/") or "/"
            if t in pages and t not in depth:
                depth[t] = depth[p] + 1
                queue.append(t)
    return depth


def norm_truth(kind, v):
    if kind in ("money", "number"):
        return round(float(v), 2)
    if kind in A.SET_KINDS:
        return sorted(v)
    return v


def wrong_answers(c: Candidate) -> list:
    """Plausible wrong answers of the right shape (used only to prove the grader can tell them apart)."""
    t, k = c.truth, c.kind
    if k in ("money", "number", "integer"):
        return [A.format_expected(k, t + 1), A.format_expected(k, round(t * 1.1 + 0.5, 2))]
    if k == "date":
        d = date.fromisoformat(t)
        return [A.format_expected(k, (d + timedelta(days=1)).isoformat()), A.format_expected(k, (d - timedelta(days=1)).isoformat())]
    if k == "yesno":
        return ["No" if t else "Yes", "No, it is not" if t else "Yes, it is"]
    if k == "choice":
        o = [x for x in c.options if x != t]
        return [o[0], f"the {o[0]}"]
    names = c.names
    if k in ("product", "accessory"):
        other = [i for i in names if i != t]
        return [names[other[0]], names[other[3]]]
    other = [i for i in names if i not in t]
    return [[names[i] for i in t][:-1] or [names[other[0]]], [names[i] for i in t] + [names[other[0]]]]


def hedge(c: Candidate):
    if c.kind in A.SET_KINDS or c.kind in ("yesno", "choice"):
        return None
    right, wrong = A.format_expected(c.kind, c.truth, c.names), wrong_answers(c)[0]
    return f"{right} or {wrong}"


def check(c: Candidate, pf: PageFacts, depth: dict[str, int], pages: dict[str, str], arms: dict[str, dict[str, str]] | None = None) -> str | None:
    k = c.kind
    if k not in A.KINDS or c.family == "" or not c.question.strip():
        return "malformed candidate"
    if c.recompute is None:
        return "no independent recomputation"
    try:
        got = c.recompute(pf)
    except Exception as exc:                                                       # the pages cannot support the question
        return f"independent recomputation failed: {type(exc).__name__}: {exc}"
    if isinstance(got, str) and got.startswith("AMBIGUOUS"):
        return f"ambiguous on the pages: {got}"
    if norm_truth(k, got) != norm_truth(k, c.truth):
        return f"data and rendered pages disagree: data={c.truth!r} pages={got!r}"
    if k in A.SET_KINDS and not (1 <= len(c.truth) <= MAX_SET):
        return f"set size {len(c.truth)} outside 1..{MAX_SET}"
    if k == "money" and c.truth <= 0:
        return "non-positive amount"
    if k == "date" and not D.AS_OF <= date.fromisoformat(c.truth) <= D.LAST_DAY:
        return "date outside the booking window"
    if k == "choice" and c.truth not in c.options:
        return "truth not among the options"
    if c.pages_needed > MAX_PAGES_NEEDED:
        return f"needs {c.pages_needed} pages (limit {MAX_PAGES_NEEDED})"
    for p in (c.start_path, *c.visit):
        if p not in pages:
            return f"page does not exist: {p}"
        if depth.get(p, 99) > 4:
            return f"page not reachable within 4 clicks: {p}"
    if not c.facts:
        return "no evidence facts defined"
    for arm, texts in (arms or {}).items():
        missing = available_in(c.facts, texts)
        if missing:
            return f"evidence not displayable on the {arm} site: {missing[:3]}"
    q = c.question.lower()
    if k not in ("yesno", "choice") and "group" not in c.params:                    # a question that lists the candidates to choose from names its answers by design
        exp = c.expected_text
        for e in (exp if isinstance(exp, list) else [exp]):
            if e.lower() in q and not (k in ("money", "number", "integer") and len(e) <= 3):
                return f"the question contains the answer: {e!r}"
    if re.search(r"IB-[A-Z]{3}-\d{3}", c.full_question):
        return "question contains an internal catalogue code"
    if len(c.full_question) > 700:
        return "question too long"
    names = c.names
    if not A.grade(k, c.truth, c.expected_text, options=c.options, names=names):
        return "grader rejects the canonical answer"
    for w in wrong_answers(c):
        if A.grade(k, c.truth, w, options=c.options, names=names):
            return f"grader accepts a wrong answer: {w!r}"
    h = hedge(c)
    if h and A.grade(k, c.truth, h, options=c.options, names=names):
        return "grader accepts a hedged answer"
    return None


def verify(candidates: list[Candidate], pages: dict[str, str], arms: dict[str, dict[str, str]] | None = None) -> Report:
    """`pages` = the rendered CONTROL site (path -> html). `arms` = page TEXT of every arm of the site (control and each candidate variant)."""
    pf, depth = PageFacts(pages), link_depths(pages)
    accepted, rejected = [], []
    seen_fp, seen_q, seen_truth = set(), set(), set()
    for c in candidates:
        reason = check(c, pf, depth, pages, arms)
        if reason is None:
            qn = re.sub(r"\W+", " ", c.full_question.lower()).strip()
            tkey = (c.family, c.sub, repr(norm_truth(c.kind, c.truth)), tuple(sorted(c.visit)))
            if c.fingerprint in seen_fp:
                reason = "duplicate fingerprint"
            elif qn in seen_q:
                reason = "duplicate question text"
            elif tkey in seen_truth:
                reason = "same template, truth and visit set as an accepted task"
        if reason:
            rejected.append({"task_id": c.task_id, "family": c.family, "sub": c.sub, "reason": reason, "question": c.question[:140]})
            continue
        seen_fp.add(c.fingerprint); seen_q.add(qn); seen_truth.add(tkey)
        accepted.append(c)
    return Report(accepted, rejected)
