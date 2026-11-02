"""Build grader_v2 answer keys from a frozen task's private criterion and the frozen site profile.

The key is derived with the SAME extractors grader_v1 compiled the task with (`criteria._items`, `criteria._fact`, `compile_criterion`), and is
refused unless the re-derived truth equals the frozen truth exactly, so v1 and v2 can never disagree about what the right answer is: they
differ only in how an answer's wording is judged."""
from __future__ import annotations

from ..investigate.taskgen import criteria as C
from .v2 import AnswerKey, Candidate, KeyError_, numbers


def _page_facts(page: dict) -> tuple[tuple[str, str], ...]:
    by: dict[str, set[str]] = {}
    for f in page.get("facts", []):
        by.setdefault(f["label"], set()).add(f["value"])
    return tuple(sorted((label, next(iter(vals))) for label, vals in by.items() if len(vals) == 1))


def build_key(task_id: str, priv: dict, profile: dict) -> AnswerKey:
    crit = priv["criterion"]
    try:
        compiled = C.compile_criterion(crit, profile)
    except C.CriterionError as exc:
        raise KeyError_(f"{task_id}: criterion no longer compiles against the frozen profile ({exc})") from exc
    if compiled.truth != priv["truth"]:
        raise KeyError_(f"{task_id}: the re-derived truth differs from the frozen truth")
    kind = crit["kind"]
    if kind in ("extremum", "item_set"):
        labels = (crit["label"],) if kind == "extremum" else tuple(c["label"] for c in crit["conditions"])
        items = C._items(profile, crit["listing"], labels)
        cands = [Candidate(i["name"], _page_facts(profile["pages"][i["href"]])) for i in items]
        context = {(False, float(len(items)))}
        if kind == "item_set":
            for c in crit["conditions"]:
                context |= numbers(c["value"])
        all_labels = tuple(sorted({label for c in cands for label, _ in c.facts}))
        return AnswerKey(task_id, kind, compiled.style, compiled.truth, cands, context, crit.get("direction"), all_labels)
    # page_fact / reach_page / term_value: the candidates are the truth and every other answer the site offers for the question (v1's distractors).
    # The truth carries the facts of the page the answer lives on (so 'per day $120' contradicts a $110 day rate), and numbers that page itself
    # states are allowed as context (an agent quoting "Today, Mon 2 Nov: fully booked." is not inventing the 2).
    path = C.resolve_target(profile, crit["target"]) if kind == "reach_page" else crit["page"]
    page = profile["pages"][path]
    cands = [Candidate(compiled.truth, _page_facts(page))] + [Candidate(d) for d in compiled.distractors if d != compiled.truth]
    labels = tuple(sorted({label for label, _ in cands[0].facts}))
    return AnswerKey(task_id, kind, compiled.style, compiled.truth, cands, numbers(page.get("text") or ""), None, labels)
