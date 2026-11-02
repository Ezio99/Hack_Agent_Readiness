"""Prospective evidence rule `evidence-ranked-subset-2` (lifecycle M8).

Finding (M7, task `gen-f090b4b9bc-n`, Original): the ranked_subset evidence rule (taskeval/v2/kinds.compile_ext, as for `extremum`) requires only the
WINNER's page. The agent answered correctly without opening the other qualifying candidate's page, so the run was graded evidence-backed although the
comparison the question asks for was never demonstrably made.

Rule 2: a ranked_subset answer is evidence-supported only if the agent was shown, for EVERY member of the filtered subset, the decisive facts (each
condition's value and the ranked value): the listing, plus each member's item page whenever one of its decisive values is not on its listing card.

The frozen rule, the recorded evaluation and the official grades are unchanged; this rule is evaluated separately and labelled prospective. It is
computed from the frozen snapshot profile and the private criterion SERVER-SIDE; only counts leave this module."""
from __future__ import annotations

import hashlib
from pathlib import Path

from ..investigate.taskgen import criteria as C

RULE_ID = "evidence-ranked-subset-2"
STATUS = "prospective evidence rule; the recorded (official) evidence rule is unchanged"


def code_sha256() -> str:
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def required_pages(criterion: dict, profile: dict) -> list[str] | None:
    """Pages rule 2 requires, or None when the criterion is not a ranked_subset (rule 2 does not apply)."""
    if not isinstance(criterion, dict) or criterion.get("kind") != "ranked_subset":
        return None
    conds = [C.Condition.model_validate(c) for c in criterion.get("conditions", [])]
    label = criterion["label"]
    items = C._items(profile, criterion["listing"], tuple(c.label for c in conds) + (label,))
    need = []
    for it in items:
        page = profile["pages"][it["href"]]
        seen = [C._fact(page, c.label) for c in conds]
        if any(len(v) != 1 for v in seen):
            continue
        if not all(C._op(c, v[0]) for c, v in zip(conds, seen)):
            continue
        ranked = C._fact(page, label)
        decisive = [v[0] for v in seen] + (ranked[:1] if len(ranked) == 1 else [])
        if any(C._needs_detail(it, v) for v in decisive):
            need.append(it["href"])
    return [criterion["listing"]] + sorted(set(need))


def check(required: list[str] | None, observed_paths: set[str]) -> dict:
    """Counts only (the required page paths name candidate items and stay server-side)."""
    if required is None:
        return {"rule": RULE_ID, "applies": False}
    seen = [p for p in required if p in observed_paths]
    return {"rule": RULE_ID, "applies": True, "status": STATUS, "required_pages": len(required), "shown_pages": len(seen),
            "satisfied": len(seen) == len(required)}
