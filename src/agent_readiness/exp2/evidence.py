"""Evidence sufficiency, separate from answer correctness and from browsing efficiency.

Three independent measurements per trial:
  correct              the answer matches the independently derived truth                     (grader)
  evidence_sufficient  the model was SHOWN the facts the answer depends on, on ANY page        (this module)
  efficiency           model requests, page views and distinct pages versus what the task needs (metrics)

A task states the FACTS its answer depends on. Each fact lists the ROUTES by which the evaluated website can show it (an alternative route is any page, in any arm, that displays the decisive text);
a fact is satisfied when ANY route is, a route when ALL its clauses are, and a clause when its needle occurs in what the model saw on a page that also shows the clause's signature (which identifies
WHICH item's page it was). Nothing requires visiting a particular page: the calendar, the product page, a listing card or an added panel in a candidate variant can each carry a fact.
The rule is identical in every arm; a variant that displays a fact somewhere new simply supplies another route. Text is compared after collapsing whitespace and removing the element markers that
the model-visible page view contains."""
from __future__ import annotations

import re
from dataclasses import dataclass

MARKERS = re.compile(r"\[\d+\]<[^>]*/>")


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", MARKERS.sub(" ", s or "")).strip()


@dataclass(frozen=True)
class Clause:
    sig: str | None          # text that identifies the page (for example "Product code IB-CUT-001"); None = the needle may be on any page
    needle: str              # decisive text, e.g. "Booked" next to a date, a rate, a rule


Route = tuple          # of Clause
@dataclass(frozen=True)
class Fact:
    label: str
    routes: tuple           # of Route: ANY route suffices


def clause(sig, needle) -> Clause:
    return Clause(sig, needle)


def fact(label: str, *routes) -> Fact:
    return Fact(label, tuple(tuple(r) for r in routes))


def to_json(facts) -> list:
    return [{"label": f.label, "routes": [[{"sig": c.sig, "needle": c.needle} for c in r] for r in f.routes]} for f in facts]


def from_json(data) -> tuple:
    return tuple(Fact(f["label"], tuple(tuple(Clause(c["sig"], c["needle"]) for c in r) for r in f["routes"])) for f in data)


def clause_met(c: Clause, pages: list[str]) -> bool:
    n, s = norm(c.needle), norm(c.sig) if c.sig else None
    return any(n in p and (s is None or s in p) for p in pages)


def route_met(route, pages: list[str]) -> bool:
    return all(clause_met(c, pages) for c in route)


def assess(facts, observations: list[dict] | None) -> dict:
    """`observations` = [{'path', 'text'}] as recorded for a trial (what the model was shown). Returns sufficiency and the facts still missing. A task with no facts is never sufficient."""
    pages = [norm(o.get("text") or "") for o in (observations or [])]
    missing = [f.label for f in facts if not any(route_met(r, pages) for r in f.routes)]
    return {"sufficient": bool(facts) and not missing, "missing": missing, "facts": len(facts), "pages_seen": len(pages)}


def available_in(facts, page_texts: dict[str, str]) -> list[str]:
    """Facts that NO route can satisfy on a rendered site (path -> page text). Empty list = the site (arm) can show the task's evidence."""
    pages = [norm(t) for t in page_texts.values()]
    return [f.label for f in facts if not any(route_met(r, pages) for r in f.routes)]
