"""Independent ground truth: answer a task criterion from a site's SOURCE RECORDS, never from its rendered pages.

The engine derives every task's expected answer from the crawled snapshot (`criteria.compile_criterion`). For a controlled site we also hold the data
the pages were rendered from; `RecordOracle` recomputes the answer from those records and the site's declared field formats. Agreement is the
validation; disagreement means the page and the data differ (a site defect or an extractor defect) and the task is routed to human review."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from ..investigate.taskgen.criteria import norm_answer, quantity


@dataclass(frozen=True)
class Field:
    """How one labelled fact is stored and shown. kind: 'money' | 'number' | 'text'. `show` renders the raw value exactly as the site states it."""
    name: str
    kind: str
    show: Callable[[object], str]
    unit: str = ""                       # the unit a numeric value is stated in ('$' for money, 'days', 'weeks', ...)


@dataclass(frozen=True)
class Record:
    name: str                            # the entity's visible name
    path: str                            # the entity's own page
    values: dict = field(default_factory=dict)


@dataclass(frozen=True)
class OracleAnswer:
    supported: bool
    truth: object = None                 # str or sorted list[str]
    reason: str = ""


class RecordOracle:
    def __init__(self, listings: dict[str, list[Record]], fields: dict[str, Field], *, label: str):
        self.listings, self.fields, self.label = listings, {k.lower(): v for k, v in fields.items()}, label
        self.by_path = {r.path: r for rs in listings.values() for r in rs}

    def _field(self, label: str) -> Field | None:
        return self.fields.get(label.strip().lower())

    def _numeric(self, f: Field, raw) -> float | None:
        return float(raw) if f.kind in ("money", "number") and isinstance(raw, (int, float)) and not isinstance(raw, bool) else None

    def _holds(self, f: Field, raw, op: str, value: str) -> bool | None:
        if op in ("eq", "contains"):
            shown, want = norm_answer(f.show(raw)), norm_answer(value)
            return shown == want if op == "eq" else want in shown
        q, num = quantity(value), self._numeric(f, raw)
        if q is None or num is None:
            return None
        unit_ok = (q[1] == "$") if f.kind == "money" else (q[1] in ("", f.unit, f.unit.rstrip("s")))
        if not unit_ok:
            return None
        return {"lt": num < q[0], "le": num <= q[0], "gt": num > q[0], "ge": num >= q[0]}[op]

    def answer(self, criterion: dict) -> OracleAnswer:
        kind = criterion.get("kind")
        if kind == "page_fact":
            rec, f = self.by_path.get(criterion["page"]), self._field(criterion["label"])
            if rec is None or f is None or f.name not in rec.values:
                return OracleAnswer(False, reason="no source record or field for this page fact")
            return OracleAnswer(True, f.show(rec.values[f.name]))
        if kind in ("item_set", "extremum"):
            recs = self.listings.get(criterion["listing"])
            if not recs:
                return OracleAnswer(False, reason="the listing is not described by the source data")
            if kind == "extremum":
                f = self._field(criterion["label"])
                vals = [(self._numeric(f, r.values.get(f.name)), r.name) for r in recs] if f else []
                if not vals or any(v is None for v, _ in vals):
                    return OracleAnswer(False, reason="field missing or not numeric in the source data")
                ranked = sorted(vals, reverse=criterion["direction"] == "max")
                if ranked[0][0] == ranked[1][0]:
                    return OracleAnswer(False, reason="tied extreme in the source data")
                return OracleAnswer(True, ranked[0][1])
            hits = []
            for r in recs:
                ok = True
                for c in criterion["conditions"]:
                    f = self._field(c["label"])
                    if f is None or f.name not in r.values:
                        return OracleAnswer(False, reason=f"field {c['label']!r} is not in the source data")
                    h = self._holds(f, r.values[f.name], c["op"], c["value"])
                    if h is None:
                        return OracleAnswer(False, reason=f"condition on {c['label']!r} is not comparable in the source data")
                    ok = ok and h
                if ok:
                    hits.append(r.name)
            return OracleAnswer(True, sorted(hits))
        return OracleAnswer(False, reason=f"the oracle does not answer {kind!r} criteria")
