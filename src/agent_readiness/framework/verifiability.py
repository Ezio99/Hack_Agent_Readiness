"""Verifiability classes and the scoring rule.

DETERMINISTIC   a closed-form criterion (page_fact / item_set / extremum / reach_page / term_value) whose expected answer is derived from the frozen snapshot,
                which grader_v2 can key, which is stable across the site's variants, and which the site's independent oracle reproduces exactly.
RUBRIC          an open question answered in prose and judged against a checklist of facts the page states. Recorded for review and diagnostics; it
                cannot be graded deterministically, so it never contributes to a readiness score.
HUMAN_REVIEW    anything that should be deterministic but is not validated: no oracle (an uncontrolled site), the oracle disagrees with the page or
                declines, grader_v2 cannot key it, or the answer changes between variants.

Only DETERMINISTIC tasks are eligible for scoring."""
from __future__ import annotations

DETERMINISTIC, RUBRIC, HUMAN_REVIEW = "deterministic", "rubric", "human_review"
CLASSES = (DETERMINISTIC, RUBRIC, HUMAN_REVIEW)


def classify(*, rubric: bool = False, key_ok: bool = False, stable: bool = False, oracle: str = "absent") -> tuple[str, list[str]]:
    """oracle: 'agrees' | 'disagrees' | 'declined' | 'absent'. Returns (class, reasons)."""
    if rubric:
        return RUBRIC, ["open answer judged against a checklist"]
    reasons = []
    if not key_ok:
        reasons.append("grader_v2 cannot key this task")
    if not stable:
        reasons.append("expected answer differs between site variants")
    if oracle != "agrees":
        reasons.append({"disagrees": "independent oracle disagrees with the page-derived answer", "declined": "independent oracle cannot answer this criterion",
                        "absent": "no independent oracle for this site (uncontrolled)"}[oracle])
    return (DETERMINISTIC, ["page-derived answer reproduced by the independent oracle; keyable; stable across variants"]) if not reasons else (HUMAN_REVIEW, reasons)


def eligible_for_scoring(cls: str) -> bool:
    return cls == DETERMINISTIC
