"""Prospective grader v2.1-contrast (lifecycle M8): a REVIEW RULE for string answers that name the correct candidate and contrast it with another.

Finding (M7, task `gen-f090b4b9bc-n`, Modified): the agent answered "Spanish conversation 2 - ... with 8 seats left (vs Furniture restoration with 1
seat on Sunday); it is the ... option with the most seats." grader v2 fails it as `multiple_candidates` (and flags it for review), because a string
answer must mention exactly one candidate. A human reader accepts it: the second candidate appears only as an explicit comparison.

This module does NOT change grader v1 or grader v2 (`grading/v2.py` is unchanged and pinned by hash in the tests) and is never applied to official
or recorded post-hoc results. It answers one narrow question for a v2 `multiple_candidates` failure, and its verdict is shown separately, labelled
"prospective, review rule; not applied":

  passes iff   the FIRST mention is the expected candidate;
               every later mention is introduced by an explicit contrast marker within the 3 preceding tokens ("vs", "versus", "compared with",
               "than", "whereas", "over", "against", "ahead of", "beats", "rather than");
               every segment (the winner's detail, and each contrasted candidate's own detail) passes v2's unchanged residual checks against THAT
               candidate's own facts (no hedge, no negation, every number stated on that candidate's page or by the task, no opposite superlative);
               and no contrasted candidate is the expected answer of the task (it cannot be: a string task has one).
Anything else returns the v2 verdict unchanged. Set tasks are out of scope (a set answer listing a non-member is wrong, not contrastive)."""
from __future__ import annotations

import hashlib
from pathlib import Path

from . import v2 as G2

GRADER_ID, GRADER_VERSION = G2.GRADER_ID, "2.1-contrast"
STATUS = "prospective review rule; never applied to official (v1) or recorded post-hoc (v2) grades"
WINDOW = 3
MARKERS = (("vs",), ("versus",), ("compared", "with"), ("compared", "to"), ("than",), ("whereas",), ("over",), ("against",), ("ahead", "of"),
           ("beats",), ("rather", "than"), ("unlike",))


def code_sha256() -> str:
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def _marker_before(tokens: list[str], start: int) -> tuple[int, int] | None:
    """(marker start, marker end) of a contrast marker ending within WINDOW tokens before `start`."""
    for m in MARKERS:
        n = len(m)
        for end in range(max(0, start - WINDOW), start + 1):
            s = end - n
            if s >= 0 and tuple(tokens[s:end]) == m:
                return s, end
    return None


def grade(key: G2.AnswerKey, answer) -> dict:
    """{passed, reasons, review, applied, grader, version, status}. `applied` is True only when the contrast rule decided the verdict."""
    base = G2.grade(key, answer)
    out = {"grader": GRADER_ID, "version": GRADER_VERSION, "status": STATUS, "passed": base.passed, "reasons": list(base.reasons), "review": base.review,
           "applied": False}
    if key.style != "string" or base.passed or "multiple_candidates" not in base.reasons or not isinstance(answer, str):
        return out
    tokens = G2.canon(answer).split()
    ms = G2._mentions(tokens, key)
    truth = G2.canon(key.truth)
    if not ms or G2.canon(ms[0][2].name) != truth:
        return {**out, "reasons": out["reasons"] + ["contrast_rule: the expected candidate is not named first"]}
    segments, cut_points = [], []
    for i, (s, e, cand) in enumerate(ms[1:], start=1):
        marker = _marker_before(tokens, s)
        if marker is None:
            return {**out, "reasons": out["reasons"] + ["contrast_rule: a second candidate is named without an explicit contrast"]}
        if G2.canon(cand.name) == truth:
            return {**out, "reasons": out["reasons"] + ["contrast_rule: the expected candidate is named twice"]}
        cut_points.append((marker[0], marker[1], s, e, cand))
    # the winner's detail runs from the end of its mention to the first contrast marker; each contrasted candidate's detail from the end of its
    # mention to the next marker (or the end of the answer)
    first_end = ms[0][1]
    win_stop = cut_points[0][0]
    segments.append((tokens[first_end:win_stop], ms[0][2]))
    for j, (_, _, _, e, cand) in enumerate(cut_points):
        stop = cut_points[j + 1][0] if j + 1 < len(cut_points) else len(tokens)
        segments.append((tokens[e:stop], cand))
    problems = []
    for residual, cand in segments:
        problems += G2._check_residual(answer, residual, cand, key)
    if "/" in answer or "?" in answer:
        problems.append("hedged")
    if problems:
        return {**out, "reasons": sorted(set(problems)) + ["contrast_rule: a segment is not consistent with its candidate's own facts"]}
    return {**out, "passed": True, "reasons": ["matches_truth_with_contrasted_alternative"], "review": True, "applied": True}
