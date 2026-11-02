"""grader_v2: deterministic, key-based grading of frozen generated-criteria answers.

Why: grader_v1 (`criteria.answer_match`) accepts the expected string only when the whole answer is at most `len(truth) + 16` characters, so
"Boom crane 9 m with a refundable deposit of $600" (correct, with a correct supporting fact) fails while "Boom crane 9 m"
passes; its set grading also requires every list element to equal a name exactly ("Impact wrench kit 20V" != "... 20 V").

v2 does NOT widen that tolerance. It grades against an ANSWER KEY re-derived from the frozen snapshot (the same extractors v1 uses):
every candidate the site offers for the question, and each candidate's own labelled facts. An answer is decomposed into
  mentions   full candidate names (canonical form: case, punctuation and number/unit spacing ignored; longest match first, non-overlapping)
  residual   everything else, which must be consistent supporting detail:
             - no hedge ("or", "maybe", "/", "?", ...), no negation ("not", "no", "except", "isn't", ...)
             - every number must be a value stated on the site for the mentioned candidate, or a value the task itself states
               (a condition threshold, the listing size); anything else is unverified or contradictory
             - for extremum tasks, no superlative of the opposite direction ("cheapest" when the highest was asked)
             - bounded length (longer answers are not graded deterministically; they are routed to human review)
String tasks pass iff exactly one candidate (the truth) is mentioned and the residual is consistent. Set tasks pass iff every element maps to
candidates whose own details are consistent, nothing unrecognised is listed, and the mapped set equals the truth set.
Failures carry reason codes; `review` marks failures a human might overturn (e.g. a contrastive mention of another candidate). A review flag
never changes the score: v2 is binary and conservative. Not fuzzy: partial names ("crane") are not matched.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path

from ..investigate.inspect.pagemodel import norm

GRADER_ID, GRADER_VERSION = "generated-criteria", "2"
GRADER_V1 = {"id": "generated-criteria", "version": "1", "implementation": "investigate.taskgen.criteria.grade (answer_match: exact after normalisation, or the truth inside an answer of at most len(truth)+16 characters; sets: exact normalised equality)"}
MAX_RESIDUAL_TOKENS = 40
HEDGES = frozenset({"or", "either", "maybe", "perhaps", "possibly", "probably", "likely", "unsure", "uncertain", "might", "guess", "between", "approximately", "roughly", "around", "about"})
NEGATIONS = frozenset({"not", "no", "never", "none", "neither", "nor", "without", "except", "excluding", "unlike", "cannot", "nothing"})
CONTRACTED_NEGATION = re.compile(r"\b(?:isn|aren|wasn|weren|doesn|don|didn|can|couldn|won|wouldn|shouldn|hasn|haven|hadn|ain)\s*t\b")
SUPERLATIVES = {"max": frozenset({"lowest", "cheapest", "smallest", "least", "minimum", "min", "fewest", "shortest"}),
                "min": frozenset({"highest", "largest", "biggest", "most", "maximum", "max", "greatest", "priciest", "longest"})}
NUMBER = re.compile(r"(\$?)(\d+(?:\.\d+)?)")


def code_sha256() -> str:
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def canon(text: str) -> str:
    """Canonical comparison form: thousands separators dropped, lower case, punctuation as spaces ('$', '%' and decimal points kept), and a space
    between a number and a following/preceding word ('20V' == '20 V', '22t' == '22 t', '7.3m' == '7.3 m')."""
    s = re.sub(r"(?<=\d),(?=\d{3}\b)", "", norm(str(text)))
    s = re.sub(r"(?<!\d)\.|\.(?!\d)", " ", s.lower())
    s = re.sub(r"[^\w$%.]+", " ", s).replace("_", " ")
    s = re.sub(r"(?<=\d)(?=[a-z])|(?<=[a-z])(?=\d)", " ", s)
    s = re.sub(r"(?<=\d)\s*%", "%", s)
    return " ".join(s.split())


def numbers(text: str) -> set[tuple[bool, float]]:
    """(is_money, value) for every number in canonical text."""
    return {(bool(m.group(1)), float(m.group(2))) for m in NUMBER.finditer(canon(text))}


@dataclass(frozen=True)
class Candidate:
    name: str
    facts: tuple[tuple[str, str], ...] = ()        # (label, value) stated on the candidate's own page


@dataclass
class AnswerKey:
    """Ground truth for one frozen task, re-derived from the frozen snapshot. Private: never shown to an agent."""
    task_id: str
    kind: str
    style: str                                     # "string" | "set"
    truth: str | list[str]
    candidates: list[Candidate]
    context_numbers: set[tuple[bool, float]] = field(default_factory=set)    # numbers the task itself states (thresholds, listing size)
    direction: str | None = None                                             # extremum only
    labels: tuple[str, ...] = ()                                             # fact labels on candidate pages (excluded from superlative checks)

    def __post_init__(self):
        forms = [canon(c.name) for c in self.candidates]
        if any(not f for f in forms) or len(set(forms)) != len(forms):
            raise KeyError_(f"{self.task_id}: candidate names are not distinct in canonical form; v2 cannot grade this task deterministically")
        truths = [self.truth] if self.style == "string" else list(self.truth)
        missing = [t for t in truths if canon(t) not in forms]
        if missing:
            raise KeyError_(f"{self.task_id}: the expected answer is not among the candidates")


class KeyError_(ValueError):
    """An answer key cannot be built (the task is then not gradable by v2; v1 stays authoritative for it)."""


@dataclass
class Graded:
    passed: bool
    reasons: list[str]
    review: bool = False
    mentioned: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {"passed": self.passed, "reasons": self.reasons, "review": self.review, "mentioned": self.mentioned}


def _mentions(tokens: list[str], key: AnswerKey) -> list[tuple[int, int, Candidate]]:
    """Non-overlapping full-name mentions, longest candidate first (so 'Leaf mulcher 80 mm' wins over a candidate named 'Leaf mulcher')."""
    taken = [False] * len(tokens)
    found = []
    for cand in sorted(key.candidates, key=lambda c: -len(canon(c.name).split())):
        ct = canon(cand.name).split()
        n = len(ct)
        for i in range(len(tokens) - n + 1):
            if tokens[i:i + n] == ct and not any(taken[i:i + n]):
                found.append((i, i + n, cand))
                for j in range(i, i + n):
                    taken[j] = True
    return sorted(found, key=lambda x: x[0])


def _allowed_numbers(cand: Candidate | None, key: AnswerKey) -> set[tuple[bool, float]]:
    out = set(key.context_numbers)
    if cand is not None:
        for _, value in cand.facts:
            out |= numbers(value)
    return out


def _matches(money: bool, value: float, allowed: set[tuple[bool, float]]) -> bool:
    """'$600' must be a stated money value; a bare '600' may echo one."""
    return (money, value) in allowed if money else ((False, value) in allowed or (True, value) in allowed)


def _label_spans(tokens: list[str], facts: dict[str, str]) -> list[tuple[int, int, str]]:
    """Where the candidate's fact labels are named in the residual: the full label phrase, or its last word when that word is distinctive
    (>= 5 letters and the last word of exactly one label), e.g. 'deposit' for 'refundable deposit'."""
    phrases = {label: canon(label).split() for label in facts}
    last = [p[-1] for p in phrases.values() if p]
    spans = []
    for label, ph in phrases.items():
        forms = [ph] + ([[ph[-1]]] if ph and len(ph) > 1 and len(ph[-1]) >= 5 and last.count(ph[-1]) == 1 else [])
        for f in forms:
            for i in range(len(tokens) - len(f) + 1):
                if tokens[i:i + len(f)] == f:
                    spans.append((i, i + len(f), label))
    return spans


def _number_problems(tokens: list[str], cand: Candidate | None, key: AnswerKey) -> list[str]:
    """A number next to a fact label (within 4 tokens, before or after) whose value holds a number of the same kind (money / plain) must equal THAT
    fact of the mentioned candidate ('deposit of $210' is a contradiction when $210 is the day rate). Labels with non-numeric values never bind. A
    number with no such label nearby must be one of the candidate's stated values or a value the task (or the answer's page) states."""
    facts = dict(cand.facts) if cand else {}
    spans = _label_spans(tokens, facts)
    allowed = _allowed_numbers(cand, key)
    for i, tok in enumerate(tokens):
        m = NUMBER.fullmatch(tok)
        if not m:
            continue
        money, value = bool(m.group(1)), float(m.group(2))
        kinds = lambda label: {m for m, _ in numbers(facts[label])}
        dist = [(s - i - 1 if s > i else i - e, label) for s, e, label in spans if not s <= i < e and money in kinds(label)]   # bind money to money-valued labels, bare to bare
        near = [d for d in dist if 0 <= d[0] <= 4]
        if near:
            best = min(d for d, _ in near)
            if not any(_matches(money, value, numbers(facts[label])) for d, label in near if d == best):
                return ["contradictory_detail"]
        elif not _matches(money, value, allowed):
            return ["unverified_number"]
    return []


def _check_residual(raw_answer: str, residual: list[str], cand: Candidate | None, key: AnswerKey) -> list[str]:
    reasons = []
    text = " ".join(residual)
    words = set(residual)
    if words & HEDGES or "/" in raw_answer or "?" in raw_answer:
        reasons.append("hedged")
    if words & NEGATIONS or CONTRACTED_NEGATION.search(text):
        reasons.append("negated")
    reasons += _number_problems(residual, cand, key)
    if key.direction:
        stripped = text
        for label in key.labels:
            stripped = re.sub(rf"(?<!\w){re.escape(canon(label))}(?!\w)", " ", stripped)
        if set(stripped.split()) & SUPERLATIVES[key.direction]:
            reasons.append("contradictory_superlative")
    if len(residual) > MAX_RESIDUAL_TOKENS:
        reasons.append("too_long")
    return reasons


REVIEWABLE = frozenset({"negated", "unverified_number", "contradictory_superlative", "too_long", "unrecognised_element"})


def _reviewable(reasons: list[str]) -> bool:
    """A human might overturn these (a true fact the key does not hold, phrasing that only looks negated); a hedge is never a single answer."""
    return "hedged" not in reasons and any(r in REVIEWABLE for r in reasons)


def _grade_string(answer, key: AnswerKey) -> Graded:
    if not isinstance(answer, str) or not canon(answer):
        return Graded(False, ["no_answer"])
    tokens = canon(answer).split()
    ms = _mentions(tokens, key)
    names = [m[2].name for m in ms]
    if not ms:
        return Graded(False, ["no_candidate_named"], review=True, mentioned=[])
    distinct = {canon(n) for n in names}
    truth = canon(key.truth)
    if len(distinct) > 1:
        return Graded(False, ["multiple_candidates" if truth in distinct else "wrong_candidate"], review=truth in distinct, mentioned=names)
    if truth not in distinct:
        return Graded(False, ["wrong_candidate"], mentioned=names)
    keep = [True] * len(tokens)
    for s, e, _ in ms:
        for j in range(s, e):
            keep[j] = False
    residual = [t for t, k in zip(tokens, keep) if k]
    problems = _check_residual(answer, residual, ms[0][2], key)
    if problems:
        return Graded(False, problems, review=_reviewable(problems), mentioned=names)
    return Graded(True, ["matches_truth" if not residual else "matches_truth_with_consistent_detail"], mentioned=names)


def _grade_set(answer, key: AnswerKey) -> Graded:
    if not isinstance(answer, list) or not any(isinstance(x, str) and x.strip() for x in answer):
        return Graded(False, ["no_answer"])
    got, reasons, mentioned = set(), [], []
    for element in answer:
        if not isinstance(element, str) or not element.strip():
            continue
        tokens = canon(element).split()
        ms = _mentions(tokens, key)
        if not ms:
            reasons.append("unrecognised_element")
            continue
        # details attach to the mention they follow; text before the first mention is element-wide context
        bounds = [m[0] for m in ms] + [len(tokens)]
        prefix = tokens[:ms[0][0]]
        if prefix:
            reasons += _check_residual(element, prefix, None, key)
        for (s, e, cand), nxt in zip(ms, bounds[1:]):
            reasons += _check_residual(element, tokens[e:nxt], cand, key)
            got.add(canon(cand.name))
            mentioned.append(cand.name)
    want = {canon(t) for t in key.truth}
    if reasons:
        reasons = sorted(set(reasons))
        return Graded(False, reasons, review=_reviewable(reasons), mentioned=mentioned)
    if got != want:
        return Graded(False, ["missing_items" if got < want else "extra_items" if got > want else "wrong_items"], mentioned=mentioned)
    plain = all(canon(e) in want for e in answer if isinstance(e, str) and e.strip())
    return Graded(True, ["matches_truth" if plain else "matches_truth_with_consistent_detail"], mentioned=mentioned)


def grade(key: AnswerKey, answer) -> Graded:
    """Independent v2 grade of one answer (a string for string tasks, a list of strings for set tasks). Agent self-assessment is never consulted."""
    return _grade_set(answer, key) if key.style == "set" else _grade_string(answer, key)
