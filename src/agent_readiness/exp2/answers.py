"""Typed answers and independent grading for Ironbark tasks. A task has ONE answer kind; grading is exact on a normalised form and never consults the agent's own claims.

  money      dollars to the cent                       number    a plain number (weights, depths)          integer   a whole number
  date       a calendar date (year defaults to 2026)   yesno     yes / no                                  choice    one of a fixed list of options
  product    one hire item        products   a set of hire items     accessory / accessories   the same for accessories and consumables
Hedges ("or", "either", "maybe", ranges) and answers that offer several values are never accepted as one answer."""
from __future__ import annotations

import re
from datetime import date

from ..investigate.taskgen.criteria import HEDGE_WORDS, answer_match, norm_answer

KINDS = ("money", "number", "integer", "date", "yesno", "choice", "product", "products", "accessory", "accessories")
SET_KINDS = ("products", "accessories")
MONTHS = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}
WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
YEAR = 2026
NUM = re.compile(r"(?<![\w.])-?\d[\d,]*(?:\.\d+)?")


def format_expected(kind: str, truth, names: dict[str, str] | None = None):
    """The canonical text an agent would write for the truth (also what the scripted mock agent answers)."""
    if kind == "money":
        return f"${truth:,.2f}"
    if kind in ("number", "integer"):
        return f"{truth:g}"
    if kind == "date":
        d = date.fromisoformat(truth)
        return f"{d:%a} {d.day} {d:%b} {d.year}"
    if kind == "yesno":
        return "Yes" if truth else "No"
    if kind == "choice":
        return truth
    if kind in ("product", "accessory"):
        return (names or {})[truth]
    return [(names or {})[t] for t in truth]


def _one_number(s: str) -> float | None:
    vals = {round(float(m.replace(",", "")), 6) for m in NUM.findall(s)}
    return vals.pop() if len(vals) == 1 else None


def _no_hedge(s: str) -> bool:
    return not HEDGE_WORDS.search(norm_answer(s)) and not re.search(r"\b(about|around|approximately|roughly|at least|at most|up to|between|from|range)\b", s.lower())


def parse_date(s: str) -> date | None:
    """Exactly one date in the text, or None. Accepts 2026-11-13, 13 Nov, 13 November 2026, Fri 13 Nov 2026, Nov 13th; a stated weekday must match."""
    s = s.strip()
    found = set()
    for m in re.finditer(r"(20\d\d)-(\d\d)-(\d\d)", s):
        found.add(date(int(m.group(1)), int(m.group(2)), int(m.group(3))))
    low = s.lower()
    for m in re.finditer(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+(?:of\s+)?([a-z]{3})[a-z]*\.?(?:,?\s+(20\d\d))?", low):
        if m.group(2) in MONTHS:
            found.add(date(int(m.group(3) or YEAR), MONTHS[m.group(2)], int(m.group(1))))
    for m in re.finditer(r"\b([a-z]{3})[a-z]*\.?\s+(\d{1,2})(?:st|nd|rd|th)?(?:,?\s+(20\d\d))?\b", low):
        if m.group(1) in MONTHS:
            found.add(date(int(m.group(3) or YEAR), MONTHS[m.group(1)], int(m.group(2))))
    if len(found) != 1:
        return None
    d = next(iter(found))
    wd = re.search(r"\b(mon|tue|wed|thu|fri|sat|sun)[a-z]*\b", low)
    if wd and WEEKDAYS.index(wd.group(1)) != d.weekday():
        return None
    return d


def grade(kind: str, truth, answer, *, options: tuple = (), names: dict[str, str] | None = None) -> bool:
    names = names or {}
    if kind in SET_KINDS:
        if not isinstance(answer, list) or not answer or any(not isinstance(a, str) for a in answer):
            return False
        by_norm = {norm_answer(n): i for i, n in names.items()} | {norm_answer(i): i for i in names}
        got = {by_norm.get(norm_answer(a)) for a in answer}
        return None not in got and got == set(truth) and len(answer) == len(set(norm_answer(a) for a in answer))
    if not isinstance(answer, str) or not answer.strip() or len(answer) > 160:
        return False
    if kind in ("product", "accessory"):
        others = [n for i, n in names.items() if i != truth]
        return answer_match(names[truth], answer, others) or norm_answer(answer) == norm_answer(truth)
    if kind in ("money", "number", "integer"):
        v = _one_number(answer)
        if v is None or not _no_hedge(answer):
            return False
        return abs(v - truth) < (0.005 if kind == "money" else 1e-6) and (kind != "integer" or float(v).is_integer())
    if kind == "date":
        d = parse_date(answer)
        return d is not None and d.isoformat() == truth and _no_hedge(answer)
    if kind == "yesno":
        w = set(re.findall(r"\b(yes|no)\b", answer.lower()))
        return w == {"yes" if truth else "no"} and not re.search(r"\b(or|maybe|perhaps|depends)\b", answer.lower())
    if kind == "choice":
        return truth
    if kind in ("product", "accessory"):
        return (names or {})[truth]
    return [(names or {})[t] for t in truth]


def _one_number(s: str) -> float | None:
    vals = {round(float(m.replace(",", "")), 6) for m in NUM.findall(s)}
    return vals.pop() if len(vals) == 1 else None


def _no_hedge(s: str) -> bool:
    return not HEDGE_WORDS.search(norm_answer(s)) and not re.search(r"\b(about|around|approximately|roughly|at least|at most|up to|between|from|range)\b", s.lower())


def parse_date(s: str) -> date | None:
    """Exactly one date in the text, or None. Accepts 2026-11-13, 13 Nov, 13 November 2026, Fri 13 Nov 2026, Nov 13th; a stated weekday must match."""
    s = s.strip()
    found = set()
    for m in re.finditer(r"(20\d\d)-(\d\d)-(\d\d)", s):
        found.add(date(int(m.group(1)), int(m.group(2)), int(m.group(3))))
    low = s.lower()
    for m in re.finditer(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+(?:of\s+)?([a-z]{3})[a-z]*\.?(?:,?\s+(20\d\d))?", low):
        if m.group(2) in MONTHS:
            found.add(date(int(m.group(3) or YEAR), MONTHS[m.group(2)], int(m.group(1))))
    for m in re.finditer(r"\b([a-z]{3})[a-z]*\.?\s+(\d{1,2})(?:st|nd|rd|th)?(?:,?\s+(20\d\d))?\b", low):
        if m.group(1) in MONTHS:
            found.add(date(int(m.group(3) or YEAR), MONTHS[m.group(1)], int(m.group(2))))
    if len(found) != 1:
        return None
    d = next(iter(found))
    wd = re.search(r"\b(mon|tue|wed|thu|fri|sat|sun)[a-z]*\b", low)
    if wd and WEEKDAYS.index(wd.group(1)) != d.weekday():
        return None
    return d


def grade(kind: str, truth, answer, *, options: tuple = (), names: dict[str, str] | None = None) -> bool:
    names = names or {}
    if kind in SET_KINDS:
        if not isinstance(answer, list) or not answer or any(not isinstance(a, str) for a in answer):
            return False
        by_norm = {norm_answer(n): i for i, n in names.items()} | {norm_answer(i): i for i in names}
        got = {by_norm.get(norm_answer(a)) for a in answer}
        return None not in got and got == set(truth) and len(answer) == len(set(norm_answer(a) for a in answer))
    if not isinstance(answer, str) or not answer.strip() or len(answer) > 160:
        return False
    if kind in ("product", "accessory"):
        others = [n for i, n in names.items() if i != truth]
        return answer_match(names[truth], answer, others) or norm_answer(answer) == norm_answer(truth)
    if kind in ("money", "number", "integer"):
        v = _one_number(answer)
        if v is None or not _no_hedge(answer):
            return False
        return abs(v - truth) < (0.005 if kind == "money" else 1e-6) and (kind != "integer" or float(v).is_integer())
    if kind == "date":
        d = parse_date(answer)
        return d is not None and d.isoformat() == truth and _no_hedge(answer)
    if kind == "yesno":
        w = set(re.findall(r"\b(yes|no)\b", answer.lower()))
        return len(w) == 1 and w == {"yes" if truth else "no"} and _no_hedge(answer.replace("No ", "").replace("no ", "")) if False else (len(w) == 1 and w == {"yes" if truth else "no"} and not re.search(r"\b(or|maybe|perhaps|depends)\b", answer.lower()))
    if kind == "choice":
        hits = {o for o in options if re.search(rf"(?<!\w){re.escape(o.lower())}(?!\w)", answer.lower())}
        return hits == {truth} and not re.search(r"\b(or|maybe|perhaps|both|either)\b", answer.lower())
    raise ValueError(kind)


def answer_schema(kind: str) -> dict:
    if kind in SET_KINDS:
        return {"type": "object", "properties": {"answers": {"type": "array", "items": {"type": "string"}, "description": "every matching item, one string each, using the exact names shown on the site"}}, "required": ["answers"]}
    return {"type": "object", "properties": {"answer": {"type": "string", "description": "the answer, stated briefly"}}, "required": ["answer"]}


HINTS = {"money": "Give the amount in Australian dollars (for example $123.45).", "number": "Give just the number with its unit.", "integer": "Answer with a whole number.",
         "date": "Answer with a single calendar date (for example Fri 13 Nov 2026).", "yesno": "Answer Yes or No.", "product": "Give the exact name of one item as shown on the site.",
         "products": "List the exact names of every matching item as shown on the site.", "accessory": "Give the exact name of one accessory as shown on the site.",
         "accessories": "List the exact names of every matching accessory as shown on the site."}
