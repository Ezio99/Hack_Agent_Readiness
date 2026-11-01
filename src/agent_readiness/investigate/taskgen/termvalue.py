"""`term_value` criterion: ONE short value stated next to a NAMED TERM (a definition term, a heading, or a table row) on one page. Generic: nothing here knows any site or vocabulary.

The criterion names only {page, term, label}. The expected answer is re-derived from the page model's `term_values` (see `inspect.pagemodel._term_values`) by `compile`, so nobody supplies it and
a wrong criterion simply fails to compile. Compilation is strict. It refuses (CriterionError, reason without the answer) when:
  - the term is absent, repeated on the page, or states the label more than once                     (ambiguous)
  - the label is a one-off phrase (stated for fewer than MIN_LABEL_RECURRENCE entries site-wide)        (not a field the site states for several terms)
  - the value is long, prose-like (two sentences), boolean or empty                                    (not a short independently gradable answer)
  - the label is a closed vocabulary (at most 5 distinct values that repeat, e.g. a type)               (a guess is likely right)
  - the same term and label carry a different value on another page                                    (inconsistent)
  - the value answers more than a third of the same-label terms on the page (>= 3 of them)             (a guessable default)
Grading is the repository's existing `answer_match` (exact after normalisation, or the whole short value inside a short sentence that offers no alternative); it is unchanged."""
from __future__ import annotations

import re

from ..inspect.pagemodel import norm
from .criteria import Compiled, CriterionError, norm_answer

MAX_VALUE_CHARS, MAX_VALUE_WORDS, MAX_TERM_CHARS = 40, 5, 60
MIN_LABEL_RECURRENCE = 3
GUESSABLE_SHARE = 1 / 3
BOOLEAN = {"true", "false", "yes", "no", "on", "off"}


def short_value(raw: str) -> str | None:
    """The value if it is a short literal-like answer; None for prose, booleans and empties."""
    v = norm(raw).rstrip(".").strip().strip("`")
    if not v or len(v) > MAX_VALUE_CHARS or len(v.split()) > MAX_VALUE_WORDS or not re.search(r"\w", v):
        return None
    if re.search(r"[.!?]\s+[A-Za-z]", v) or norm_answer(v) in BOOLEAN:
        return None
    return v


def _book(profile: dict) -> dict[str, list[dict]]:
    return {p: rec.get("term_values", []) for p, rec in profile["pages"].items()}


def compile_term_value(profile: dict, c: dict, _book_cache: dict | None = None) -> Compiled:
    page, term, label = c["page"], norm_answer(c["term"]), norm(c["label"]).lower()
    if page not in profile["pages"]:
        raise CriterionError(f"page {page!r} is not part of the snapshot")
    book = _book_cache if _book_cache is not None else _book(profile)
    mine = [e for e in book[page] if norm_answer(e["term"]) == term]
    if not mine:
        raise CriterionError(f"no term {c['term']!r} on {page}")
    same = [e for e in mine if e["label"] == label]
    if not same:
        raise CriterionError(f"term {c['term']!r} on {page} has no {label!r} value")
    if len(same) > 1:
        raise CriterionError(f"term {c['term']!r} on {page} has the {label!r} value stated more than once, or the term is repeated (ambiguous)")
    site_vals = [norm_answer(e["value"]) for es in book.values() for e in es if e["label"] == label]
    if len(site_vals) < MIN_LABEL_RECURRENCE:
        raise CriterionError(f"{label!r} is a one-off phrase, not a field the site states for several terms")
    if len(set(site_vals)) < 3 or (len(set(site_vals)) < 6 and len(set(site_vals)) < len(site_vals)):          # <= 5 distinct values that repeat: a closed vocabulary
        raise CriterionError(f"{label!r} takes only a few distinct values across the site (a closed vocabulary such as a type), so a guess is likely right")
    value = short_value(same[0]["value"])
    if value is None:
        raise CriterionError("the value is long, prose-like, boolean or empty (not a short independently gradable answer)")
    if any(norm_answer(e["value"]) != norm_answer(value) for p, es in book.items() if p != page for e in es if norm_answer(e["term"]) == term and e["label"] == label):
        raise CriterionError("the same term and label carry a different value on another page (inconsistent)")
    peers = [e for e in book[page] if e["label"] == label and e["how"] == same[0]["how"]]
    share = sum(1 for e in peers if norm_answer(e["value"]) == norm_answer(value)) / len(peers)
    if len(peers) >= 3 and share > GUESSABLE_SHARE:
        raise CriterionError(f"the value answers {share:.0%} of the terms with this label on the page (guessable)")
    distractors = sorted({v for e in peers if (v := short_value(e["value"])) and norm_answer(v) != norm_answer(value)})
    return Compiled("term_value", "string", value, [page], [(page, value)], [], {"term": same[0]["term"], "label": label, "how": same[0]["how"]}, distractors)


def candidates(profile: dict, limit: int = 24, per_page: int = 6) -> list[dict]:
    """Valid {page, term, label} criteria (each compiles), spread over pages round-robin and bounded. Used for the proposer context and for rule-generated drafts. Values are NOT included."""
    book, per = _book(profile), {}
    for page in sorted(book):
        seen, ok = set(), []
        for e in book[page]:
            key = (norm_answer(e["term"]), e["label"])
            if key in seen or len(e["term"]) > MAX_TERM_CHARS:
                continue
            seen.add(key)
            crit = {"page": page, "term": e["term"], "label": e["label"]}
            try:
                compile_term_value(profile, crit, book)
            except CriterionError:
                continue
            ok.append(crit)
            if len(ok) >= per_page:
                break
        if ok:
            per[page] = ok
    out, i = [], 0
    while len(out) < limit and any(i < len(v) for v in per.values()):
        out += [v[i] for v in per.values() if i < len(v)][: limit - len(out)]
        i += 1
    return out


def drafts(profile: dict, start: str = "/", limit: int = 12) -> list:
    """Rule-generated `term_value` drafts (offline baseline / tests): every candidate with a question that names page, term and field. The gate still decides."""
    from ..inspect.pagemodel import norm as _n
    from .gate import Draft
    out = []
    for c in candidates(profile, limit):
        title = _n(profile["pages"][c["page"]]["title"].split(" — ")[0].split(" | ")[0])
        out.append(Draft(f"On the “{title}” page, what is the {c['label']} listed for {c['term']}?", start, {"kind": "term_value", **c}, "rule"))
    return out
