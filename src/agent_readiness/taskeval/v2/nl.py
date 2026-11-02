"""gate-nl-1: natural-language fidelity of a customer wording against a structured task specification (evaluator v2).

Approved rule (proposal §3.3): every constraint VALUE is stated in the customer's words and maps unambiguously to one attribute domain of the
verified catalogue; field NAMES may be implied. It replaces only the acceptance gate's literal field-name rule, and only for natural wording.

Both directions are checked (intent preservation):
  specification -> wording   every value, comparator, ranking and looked-up fact of the specification is traceable to the wording
  wording -> specification   every value the customer states (outside a negative context such as "I work Monday to Friday") is represented

Per specification component the trace status is one of
  traced            stated in the customer's words (an implied field name or an inflection is recorded as an interpretation decision)
  underspecified    the customer expresses the dimension but gives no value ("a tight budget", "a few weeks"): preserved, never filled in
  ambiguous         the stated value or cue maps to several attributes, or a number has no identifiable field
  added_assumption  the specification constrains something the customer never mentioned (the generator's assumption)
  mismatch          the specification contradicts the wording (other comparator, other direction, a value stated only negatively)

Deterministic and code-only: no model is consulted. Thresholds are never invented; vague quantities are detected so they can be preserved."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from . import lexicon as L

GATE_ID = "gate-nl-1"
OP_WORDS = {"lt": "below", "le": "at most", "gt": "above", "ge": "at least", "eq": "equal to"}
TOKEN = re.compile(r"\$\d[\d,]*(?:\.\d+)?|\d[\d,]*(?:\.\d+)?|[a-z]+(?:'[a-z]+)?|\$|[.?!;:]")
BOUNDARY = frozenset(".?!;:")


# --------------------------------------------------------------------------------------------------------------------------- text utilities
def norm(text: str) -> str:
    t = (text or "").replace("’", "'").replace("‘", "'").lower()
    t = re.sub(r"(?<=[a-z])-(?=[a-z])", " ", t)
    t = re.sub(r"(?<=\$)\s+(?=\d)", "", t)
    return " ".join(t.split())


def tokens(text: str) -> list[str]:
    return TOKEN.findall(norm(text))


def forms(word: str) -> frozenset[str]:
    """Inflected forms of one word (plural / singular, -ed / -ing / base), so 'Saturdays' states 'Saturday' and 'include' states 'Included'."""
    w = word.lower()
    out = {w}
    if w.endswith("ies"):
        out.add(w[:-3] + "y")
    elif w.endswith("es") and len(w) > 4:
        out |= {w[:-2], w[:-1]}
    elif w.endswith("s") and not w.endswith("ss") and len(w) > 3:
        out.add(w[:-1])
    if w.endswith("ed") and len(w) > 4:
        base = w[:-1]                                                   # included -> include
        out |= {base, w[:-2], w[:-2] + "ing", (base[:-1] + "ing") if base.endswith("e") else base + "ing"}
    for x in list(out):
        out |= {x + "s", x + "es"}
    return frozenset(out)


def _same(a: str, b: str) -> bool:
    return a == b or bool(forms(a) & forms(b))


def find(toks: list[str], phrase: str | list[str], *, inflect: bool = False, taken: set[int] | None = None) -> list[tuple[int, int]]:
    p = tokens(phrase) if isinstance(phrase, str) else phrase
    hits = []
    for i in range(len(toks) - len(p) + 1):
        if taken and any(k in taken for k in range(i, i + len(p))):
            continue
        if all((_same(toks[i + k], p[k]) if inflect else toks[i + k] == p[k]) for k in range(len(p))):
            hits.append((i, i + len(p)))
    return hits


def number_value(tok: str) -> tuple[float, bool] | None:
    """(value, is_money) of a number token ('$250' -> (250, True), 'six' -> (6, False))."""
    if tok in L.NUMBER_WORDS:
        return float(L.NUMBER_WORDS[tok]), False
    m = re.fullmatch(r"(\$?)(\d[\d,]*(?:\.\d+)?)", tok)
    return (float(m.group(2).replace(",", "")), bool(m.group(1))) if m else None


def parse_quantity(value: str) -> tuple[float, str] | None:
    m = re.fullmatch(r"\s*(\$?)\s*(-?\d[\d,]*(?:\.\d+)?)\s*([a-zA-Z]*)\s*", value or "")
    if not m:
        return None
    return float(m.group(2).replace(",", "")), ("$" if m.group(1) else m.group(3).lower())


# --------------------------------------------------------------------------------------------------------------------------- catalogue model
def attr_class(a: dict) -> str | None:
    label, unit = a["attribute"].lower(), (a.get("unit") or "").lower().rstrip("s")
    if a["kind"] == "money":
        return "money"
    if a["kind"] == "number" and unit in ("week", "day", "hour", "month", "minute"):
        return "duration"
    if a["kind"] == "text" and a.get("values") and {v.lower() for v in a["values"]} <= set(L.WEEKDAYS):
        return "weekday"
    if any(w in label for w in ("campus", "location", "branch", "venue", "store")):
        return "location"
    if any(w in label for w in ("seat", "place", "stock", "space", "spot", "availab")):
        return "availability"
    if label in ("level", "difficulty"):
        return "level"
    return None


def label_tokens(label: str) -> list[str]:
    return [t for t in tokens(label) if t not in L.LABEL_STOPWORDS] or tokens(label)


@dataclass
class Catalogue:
    attrs: dict[str, dict]
    items: list[dict]
    classes: dict[str, str | None]

    @classmethod
    def from_view(cls, view: dict) -> "Catalogue":
        attrs = {a["attribute"]: a for a in view["attributes"]}
        return cls(attrs, view["items"], {k: attr_class(a) for k, a in attrs.items()})

    def of_class(self, c: str) -> list[str]:
        return sorted(k for k, v in self.classes.items() if v == c)

    def labels_named(self, toks: list[str], span: tuple[int, int] | None = None, window: int = 5) -> list[str]:
        """Attributes whose full (stop-word-free) label is named in the text (or within `window` tokens of `span`); the most specific labels win."""
        lo, hi = (0, len(toks)) if span is None else (max(0, span[0] - window), min(len(toks), span[1] + window))
        sub = toks[lo:hi]
        hit = [(len(label_tokens(k)), k) for k in self.attrs if find(sub, label_tokens(k), inflect=True)]
        if not hit:
            return []
        top = max(n for n, _ in hit)
        return sorted(k for n, k in hit if n == top)


# --------------------------------------------------------------------------------------------------------------------------- results
@dataclass
class Trace:
    component: str
    status: str                       # traced | underspecified | ambiguous | added_assumption | mismatch
    detail: str
    decision: str | None = None

    def as_dict(self) -> dict:
        return {"component": self.component, "status": self.status, "detail": self.detail, **({"decision": self.decision} if self.decision else {})}


@dataclass
class Analysis:
    gate: str = GATE_ID
    traces: list[Trace] = field(default_factory=list)
    unrepresented: list[str] = field(default_factory=list)      # stated by the customer, absent from the specification
    vague_unconstrained: list[str] = field(default_factory=list)  # vague wording about an attribute the specification does not constrain
    notes: list[str] = field(default_factory=list)

    @property
    def decisions(self) -> list[str]:
        return [t.decision for t in self.traces if t.decision] + self.notes

    @property
    def assumptions(self) -> list[str]:
        return [t.detail for t in self.traces if t.status in ("added_assumption", "underspecified", "ambiguous")]

    @property
    def unresolved(self) -> list[str]:
        return [t.detail for t in self.traces if t.status in ("underspecified", "ambiguous")] + self.vague_unconstrained

    @property
    def intent_violations(self) -> list[str]:
        return [t.detail for t in self.traces if t.status == "mismatch"] + self.unrepresented

    @property
    def passed(self) -> bool:
        return all(t.status == "traced" for t in self.traces) and not self.unrepresented and not self.vague_unconstrained

    def verdict(self) -> str:
        """intent_not_preserved | underspecified | assisted_only | verifiable"""
        if self.intent_violations:
            return "intent_not_preserved"
        if self.unresolved:
            return "underspecified"
        if any(t.status == "added_assumption" for t in self.traces):
            return "assisted_only"
        return "verifiable"

    def as_dict(self) -> dict:
        return {"gate": self.gate, "passed": self.passed, "verdict": self.verdict(), "traces": [t.as_dict() for t in self.traces],
                "unrepresented": self.unrepresented, "vague_unconstrained": self.vague_unconstrained, "notes": self.notes}


# --------------------------------------------------------------------------------------------------------------------------- analyser
class Analyser:
    def __init__(self, view: dict):
        self.cat = Catalogue.from_view(view)
        self.listing = view.get("listing")

    # ---------------------------------------------------------------- spans in the wording
    def _negative(self, toks: list[str], i: int) -> bool:
        """A mention is negative when a negative cue occurs within NEGATIVE_WINDOW tokens before it, in the same clause."""
        lo = max(0, i - L.NEGATIVE_WINDOW)
        window = toks[lo:i]
        cut = max((k for k, t in enumerate(window) if t in BOUNDARY), default=-1)          # a negative cue never reaches across a sentence boundary
        return any(t in L.NEGATIVE_CUES or t.endswith("n't") for t in window[cut + 1:])

    def _value_mentions(self, toks: list[str], value: str, taken: set[int]) -> list[tuple[int, int]]:
        p = tokens(value)
        p = [("your" if t in ("my", "our", "your") else t) for t in p]
        t2 = [("your" if t in ("my", "our") else t) for t in toks]
        return find(t2, p, inflect=True, taken=taken)

    def _numbers(self, toks: list[str]) -> list[dict]:
        out = []
        for i, t in enumerate(toks):
            nv = number_value(t)
            if nv is None:
                continue
            val, money = nv
            j, unit = i + 1, None
            if j < len(toks) and toks[j] in ("dollars", "dollar", "aud"):
                money, j = True, j + 1
            elif j < len(toks) and not money:
                for u in ("week", "day", "hour", "month", "minute"):
                    if _same(toks[j], u):
                        unit, j = u, j + 1
                        break
            out.append({"i": i, "j": j, "value": val, "money": money, "unit": unit, "comparator": self._comparator(toks, i, j)})
        return out

    @staticmethod
    def _comparator(toks: list[str], i: int, j: int) -> tuple[str, tuple[int, int]] | None:
        after = toks[j:j + 3]
        for phrase, op in L.SUFFIX_COMPARATORS:
            p = tokens(phrase)
            if after[:len(p)] == p:
                return op, (j, j + len(p))
        best = None
        for phrase, op in L.PREFIX_COMPARATORS:
            p = tokens(phrase)
            for s, e in find(toks[max(0, i - 4):i], p):
                s, e = s + max(0, i - 4), e + max(0, i - 4)
                if best is None or e > best[1][1] or (e == best[1][1] and e - s > best[1][1] - best[1][0]):
                    best = (op, (s, e))
        return best

    @staticmethod
    def _cue_spans(toks: list[str]) -> list[tuple[str, int, int]]:
        """(class, start, end) of every class cue; a cue nested inside a longer cue of another class is dropped ('day of the week' is a weekday
        cue, not also a duration cue for 'week')."""
        hits = [(c, s, e) for c, cues in L.CLASS_CUES.items() for cue in cues for s, e in find(toks, cue, inflect=" " not in cue)]
        return [h for h in hits if not any(o is not h and o[0] != h[0] and o[1] <= h[1] and h[2] <= o[2] and (o[2] - o[1]) > (h[2] - h[1]) for o in hits)]

    def _class_cue(self, toks: list[str], cls: str, span: tuple[int, int] | None = None, window: int = 5) -> bool:
        lo, hi = (0, len(toks)) if span is None else (max(0, span[0] - window), min(len(toks), span[1] + window))
        return any(c == cls and lo <= s and e <= hi for c, s, e in self._cue_spans(toks))

    def _vague(self, toks: list[str], cls: str, taken: set[int]) -> list[str]:
        out = []
        for phrase in L.VAGUE.get(cls, ()):
            for s, e in find(toks, phrase, taken=taken):
                if not self._negative(toks, s) or phrase in ("cost too much", "costs too much", "cost much", "too expensive", "not expensive"):
                    out.append(" ".join(toks[s:e]))
        return sorted(set(out))

    def _superlatives(self, toks: list[str]) -> list[dict]:
        out = []
        taken: set[int] = set()
        for phrase, cls, d in L.SUPERLATIVE_PHRASES:
            for s, e in find(toks, phrase, taken=taken):
                out.append({"span": (s, e), "class": cls, "labels": [], "direction": d, "text": " ".join(toks[s:e])})
                taken |= set(range(s, e))
        for i, t in enumerate(toks):
            if i in taken or t not in L.SUPERLATIVE_WORDS:
                continue
            d = L.SUPERLATIVE_WORDS[t]
            windows = [(i + 1, min(len(toks), i + 4))] + ([(max(0, i - 2), i)] if t in ("least", "most") else [])   # "most weeks", "highest fee"; "costs the least"
            for lo, hi in windows:
                sub = toks[lo:hi]
                labels = [k for k in self.cat.attrs if find(sub, label_tokens(k), inflect=True)]
                classes = [c for c in L.CLASS_CUES if any(find(sub, cue, inflect=" " not in cue) for cue in L.CLASS_CUES[c])]
                if labels or classes:
                    out.append({"span": (min(lo, i), max(hi, i + 1)), "class": classes[0] if len(classes) == 1 else None, "classes": classes,
                                "labels": labels, "direction": d, "text": " ".join(toks[min(lo, i):max(hi, i + 1)])})
                    break
        return out

    def _resolve(self, sup: dict) -> list[str]:
        if sup["labels"]:
            return sorted(set(sup["labels"]))
        classes = [sup["class"]] if sup.get("class") else sup.get("classes", [])
        return sorted({a for c in classes for a in self.cat.of_class(c)})

    # ---------------------------------------------------------------- per-component traces
    def _value_set(self, toks, label, taken):
        """A positive mention of a definitional value set ('weekends') for a weekday-class attribute: (phrase, members, span) or None."""
        if self.cat.classes.get(label) != "weekday":
            return None
        for phrase, members in L.VALUE_SETS.items():
            for s, e in find(toks, phrase, taken=taken):
                if not self._negative(toks, s):
                    return phrase, members, (s, e)
        return None

    def _trace_text_condition(self, toks, cond, taken, used) -> Trace:
        label, values, op = cond["label"], cond.get("values") or [cond["value"]], cond["op"]
        comp = f"condition: {label} {'one of ' + ' / '.join(values) if len(values) > 1 else op + ' ' + values[0]}"
        found, negative_only = {}, []
        for v in values:
            hits = self._value_mentions(toks, v, taken)
            pos = [h for h in hits if not self._negative(toks, h[0])]
            if pos:
                found[v] = pos[0]
            elif hits:
                negative_only.append(v)
        missing = [v for v in values if v not in found]
        if missing:
            vs = self._value_set(toks, label, taken)
            want = {v.lower() for v in values}
            if vs and set(vs[1]) == want:                                   # 'weekends' for exactly {Saturday, Sunday}
                used |= set(range(*vs[2]))
                return Trace(comp, "traced", f"{label}: stated", f"'{vs[0]}' names exactly {', '.join(vs[1])} (definitional value set; field '{label}' implied)")
            if vs and want < set(vs[1]):
                return Trace(comp, "mismatch", f"{label}: the customer says '{vs[0]}' ({', '.join(vs[1])}) but the specification is narrower ({', '.join(values)})")
            if negative_only and set(negative_only) & set(missing):
                return Trace(comp, "mismatch", f"{label}: '{sorted(set(negative_only) & set(missing))[0]}' appears only in a negative context (e.g. a day the customer is busy)")
            return Trace(comp, "added_assumption", f"{label} {OP_WORDS.get(op, op)} {' or '.join(missing)} is not stated by the customer")
        decisions = []
        for v, (s, e) in found.items():
            used |= set(range(s, e))
            owners = [k for k, a in self.cat.attrs.items() if a["kind"] == "text" and any(_same_phrase(v2, " ".join(toks[s:e])) for v2 in a.get("values", []))]
            if len(owners) > 1 and label not in self.cat.labels_named(toks, (s, e)):
                return Trace(comp, "ambiguous", f"'{' '.join(toks[s:e])}' is a value of several attributes ({', '.join(sorted(owners))}) and the customer does not say which")
            named = label in self.cat.labels_named(toks, (s, e), 6)
            literal = " ".join(toks[s:e]) == " ".join(tokens(v))
            decisions.append((f"field '{label}' named by the customer" if named else f"field '{label}' implied by '{' '.join(toks[s:e])}', a value only of the {label} domain")
                             + ("" if literal else f" (inflected form of '{v}')"))
        return Trace(comp, "traced", f"{label}: stated", "; ".join(decisions))

    def _trace_numeric_condition(self, toks, cond, numbers, taken, used) -> Trace:
        label, op, value = cond["label"], cond["op"], cond["value"]
        a = self.cat.attrs.get(label, {})
        comp = f"condition: {label} {op} {value}"
        q = parse_quantity(value)
        if q is None:
            return Trace(comp, "mismatch", f"{label}: the specified value {value!r} is not a quantity")
        cls = self.cat.classes.get(label)
        for n in numbers:
            if n["value"] != q[0] or n["used"]:
                continue
            if a.get("kind") == "money" and not n["money"]:
                if not self.cat.labels_named(toks, (n["i"], n["j"])) and not self._class_cue(toks, "money", (n["i"], n["j"]), 3):
                    continue
            if a.get("kind") != "money" and n["money"]:
                continue
            owners = self._owners(toks, n)
            if label not in owners:
                continue
            n["used"] = True
            used |= set(range(n["i"], n["j"]))
            for m in numbers:                                                  # the same value stated again ("a budget of $200 ... $200 or less")
                if m is not n and not m["used"] and m["value"] == n["value"] and m["money"] == n["money"] and m["comparator"] in (None,) + ((n["comparator"][0],) if n["comparator"] else ()):
                    if m["comparator"] is None or m["comparator"][0] == op:
                        m["used"] = True
            if len(owners) > 1:
                return Trace(comp, "ambiguous", f"'{' '.join(toks[n['i']:n['j']])}' could be any of {', '.join(owners)}; the customer does not say which")
            if n["comparator"] is None:
                if op == "eq":
                    return Trace(comp, "traced", f"{label}: stated", f"field '{label}' implied by '{' '.join(toks[n['i']:n['j']])}'")
                return Trace(comp, "underspecified", f"{label}: '{' '.join(toks[n['i']:n['j']])}' is stated without saying whether it is a maximum or a minimum")
            cop, cspan = n["comparator"]
            used |= set(range(*cspan))
            if cop != op:
                return Trace(comp, "mismatch", f"{label}: the customer says '{' '.join(toks[min(cspan[0], n['i']):max(cspan[1], n['j'])])}' ({OP_WORDS[cop]}) but the specification uses {OP_WORDS.get(op, op)}")
            named = label in self.cat.labels_named(toks, (n["i"], n["j"]), 6)
            return Trace(comp, "traced", f"{label}: stated",
                         f"field '{label}' named by the customer" if named else f"field '{label}' implied: the only {self._kind_word(label)} attribute in the catalogue")
        if cls == "availability" and ((op == "gt" and q[0] == 0) or (op == "ge" and q[0] == 1)):
            for idiom in L.AVAILABILITY_IDIOMS:
                for s, e in find(toks, idiom, inflect=True, taken=taken):
                    if not self._negative(toks, s):
                        used |= set(range(s, e))
                        return Trace(comp, "traced", f"{label}: stated", f"'{idiom}' read as {label} above 0 (availability idiom: definitional, no threshold invented)")
        vague = self._vague(toks, cls, taken) if cls else []
        if vague:
            return Trace(comp, "underspecified", f"{label}: '{vague[0]}' states no amount (the generator assumed {OP_WORDS.get(op, op)} {value})")
        return Trace(comp, "added_assumption", f"{label} {OP_WORDS.get(op, op)} {value} is not stated by the customer")

    def _kind_word(self, label: str) -> str:
        a = self.cat.attrs[label]
        return "money" if a["kind"] == "money" else (f"'{a.get('unit')}'" if a.get("unit") else "numeric")

    def _owners(self, toks, n) -> list[str]:
        """Attributes a stated number can belong to: by money / unit, narrowed by a named field nearby; a bare number needs a field cue nearby."""
        named = self.cat.labels_named(toks, (n["i"], n["j"]))
        if n["money"]:
            cand = [k for k, a in self.cat.attrs.items() if a["kind"] == "money"]
        elif n["unit"]:
            cand = [k for k, a in self.cat.attrs.items() if a["kind"] == "number" and _same((a.get("unit") or ""), n["unit"])]
        else:
            cand = [k for k, a in self.cat.attrs.items() if a["kind"] == "number" and not a.get("unit")
                    and (k in named or (self.cat.classes[k] and self._class_cue(toks, self.cat.classes[k], (n["i"], n["j"]), 3)))]
        if len(cand) > 1 and set(named) & set(cand):
            cand = [k for k in cand if k in named]
        return sorted(cand)

    def _trace_ranking(self, toks, label, direction, sups, used) -> Trace:
        comp = f"ranking: {'highest' if direction == 'max' else 'lowest'} {label}"
        for s in sups:
            owners = self._resolve(s)
            if label not in owners:
                continue
            used |= set(range(*s["span"]))
            if len(owners) > 1:
                return Trace(comp, "ambiguous", f"'{s['text']}' could rank by any of {', '.join(owners)}")
            if s["direction"] != direction:
                return Trace(comp, "mismatch", f"'{s['text']}' asks for the {'highest' if s['direction'] == 'max' else 'lowest'} {label}, the specification for the opposite")
            return Trace(comp, "traced", f"{label}: stated", f"'{s['text']}' ranks by {label} ({'highest' if direction == 'max' else 'lowest'})")
        judged = [c for c in L.JUDGMENT_CUES if find(toks, c)]
        if judged:
            return Trace(comp, "underspecified", f"ranking: '{judged[0]}' does not say what to rank by (the generator assumed the {'highest' if direction == 'max' else 'lowest'} {label})")
        return Trace(comp, "added_assumption", f"ranking by the {'highest' if direction == 'max' else 'lowest'} {label} is not stated by the customer")

    def _trace_entity(self, toks, page) -> tuple[Trace, set[int]]:
        item = next((it for it in self.cat.items if it["page"] == page), None)
        if item is None:
            return Trace("entity", "mismatch", f"no catalogue item at {page}"), set()
        hits = find(toks, item["name"], inflect=True)
        if hits:
            return Trace("entity", "traced", "entity named in full"), set(range(*hits[0]))
        name = [t for t in tokens(item["name"]) if len(t) > 3]
        present = [t for t in name if any(_same(t, x) for x in toks)]
        if present:
            idx = {i for i, x in enumerate(toks) if any(_same(t, x) for t in present)}
            return Trace("entity", "traced", "entity named in part", f"entity '{item['name']}' identified by '{' '.join(present)}'"), idx
        return Trace("entity", "mismatch", "the customer does not name the item asked about"), set()

    def _trace_fact(self, toks, label, taken) -> Trace:
        comp = f"fact asked: {label}"
        named = self.cat.labels_named(toks)
        if label in named and len(named) == 1:
            return Trace(comp, "traced", f"{label}: named", f"field '{label}' named by the customer")
        classes = sorted({c for c, _, _ in self._cue_spans(toks)})
        owners = sorted({a for c in classes for a in self.cat.of_class(c)} | set(named))
        if owners == [label]:
            return Trace(comp, "traced", f"{label}: implied", f"field '{label}' implied by the question ({', '.join(classes) or 'named'} cue; the only such attribute)")
        if label in owners:
            if label in named and not (set(owners) - set(named)):
                return Trace(comp, "traced", f"{label}: named", f"field '{label}' named by the customer")
            return Trace(comp, "ambiguous", f"the question could ask for any of {', '.join(owners)}")
        if owners:
            return Trace(comp, "mismatch", f"the question asks about {', '.join(owners)}, the specification about {label}")
        return Trace(comp, "underspecified", "the question does not say which fact is wanted")

    # ---------------------------------------------------------------- entry point
    def analyse(self, wording: str, crit: dict) -> Analysis:
        toks = tokens(wording)
        out = Analysis()
        kind = crit.get("kind")
        used: set[int] = set()
        if kind == "page_fact":
            t, ent = self._trace_entity(toks, crit["page"])
            out.traces.append(t)
            used |= ent
            out.traces.append(self._trace_fact(toks, crit["label"], used))
            return out
        # entity names never count as stated values ("Beginners yoga" does not state level = Beginner)
        for it in self.cat.items:
            for s, e in find(toks, it["name"], inflect=True):
                used |= set(range(s, e))
        numbers = [dict(n, used=False) for n in self._numbers(toks)]
        sups = self._superlatives(toks)
        for s in sups:
            used |= set(range(*s["span"])) if (kind in ("extremum", "ranked_subset")) else set()
        conds = list(crit.get("conditions", []))
        if kind == "either_of":
            conds = conds + [{"label": crit["label"], "op": "eq", "values": list(crit["values"]), "value": crit["values"][0]}]
        for c in conds:
            a = self.cat.attrs.get(c["label"])
            if a is None:
                out.traces.append(Trace(f"condition: {c['label']}", "mismatch", f"{c['label']!r} is not a catalogue attribute"))
            elif a["kind"] == "text":
                out.traces.append(self._trace_text_condition(toks, c, used, used))
            else:
                out.traces.append(self._trace_numeric_condition(toks, c, numbers, used, used))
        if kind in ("extremum", "ranked_subset"):
            out.traces.append(self._trace_ranking(toks, crit["label"], crit["direction"], sups, used))
        self._unrepresented(toks, crit, conds, numbers, used, out)
        return out

    def _unrepresented(self, toks, crit, conds, numbers, used, out: Analysis) -> None:
        constrained = {c["label"] for c in conds} | ({crit["label"]} if crit.get("kind") in ("extremum", "ranked_subset") else set())
        spec_values = {(c["label"], v.lower()) for c in conds for v in (c.get("values") or [c["value"]])}
        for label, a in self.cat.attrs.items():
            if a["kind"] != "text":
                continue
            for v in a.get("values", []):
                for s, e in self._value_mentions(toks, v, used):
                    if (label, v.lower()) in spec_values:
                        continue
                    if self._negative(toks, s):
                        out.notes.append(f"'{' '.join(toks[s:e])}' read as a negative mention (not a constraint)")
                        continue
                    out.unrepresented.append(f"'{' '.join(toks[s:e])}' ({label}) is stated by the customer but not in the specification")
            if self.cat.classes.get(label) == "weekday":
                for phrase, members in L.VALUE_SETS.items():
                    for s, e in find(toks, phrase, taken=used):
                        if self._negative(toks, s):
                            out.notes.append(f"'{phrase}' read as a negative mention (not a constraint)")
                        elif label not in constrained:
                            out.unrepresented.append(f"'{phrase}' ({label}: {', '.join(members)}) is stated by the customer but not in the specification")
                        else:
                            out.notes.append(f"'{phrase}' read as context; the specification constrains {label} to values the customer names")
        for n in numbers:
            if n["used"] or n["comparator"] is None:
                continue
            owners = self._owners(toks, n)
            if owners:
                s, e = min(n["comparator"][1][0], n["i"]), max(n["comparator"][1][1], n["j"])
                out.unrepresented.append(f"'{' '.join(toks[s:e])}' ({' / '.join(owners)}) is stated by the customer but not in the specification")
        if crit.get("kind") not in ("extremum", "ranked_subset"):
            for s in self._superlatives(toks):
                if self._resolve(s):
                    out.unrepresented.append(f"'{s['text']}' asks for a ranking the specification does not have")
        for cls in L.VAGUE:
            attrs = self.cat.of_class(cls)
            if not attrs or set(attrs) & constrained:
                continue
            for v in self._vague(toks, cls, used):
                out.vague_unconstrained.append(f"{' / '.join(attrs)}: the customer says '{v}' but the specification has no {' / '.join(attrs)} constraint")


def _same_phrase(a: str, b: str) -> bool:
    ta, tb = tokens(a), tokens(b)
    return len(ta) == len(tb) and all(_same(x, y) for x, y in zip(ta, tb))
