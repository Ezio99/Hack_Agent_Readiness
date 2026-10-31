"""Evidence sufficiency, separate from answer correctness and from browsing efficiency.   (rule version `exp2-evidence-v2`)

Three independent measurements per trial:
  correct              the answer matches the independently derived truth                     (grader)
  evidence_sufficient  the model was SHOWN the facts the answer depends on, on ANY page        (this module)
  efficiency           model requests, page views and distinct pages versus what the task needs (metrics)

A task states the FACTS its answer depends on. Each fact lists the ROUTES by which the evaluated website can show it (an alternative route is any page, in any arm, that displays the decisive text);
a fact is satisfied when ANY route is, a route when ALL its clauses are, and a clause when its needle occurs in what the model saw on a page that is about the right item. Nothing requires visiting a
particular page, and nothing requires an internal product code: the calendar, the product page, a listing card or a panel a candidate variant adds can each carry a fact.

v2 (after the first pilot): needles are compared on a canonical TOKEN form of what the model is shown (`tokens`): lower case, element markers (`*[934]<td />`, `[934]<td />`) removed, punctuation and layout
ignored, thousands separators and digit-to-unit spacing normalised (`18V` = `18 V`). v1 left the leading `*` of the live element markers in place, so a label and its value in separate table cells
("Chuck" | "30 mm hex") could never be matched, and it required `Product code IB-...` on a page, which listing cards do not show. An item is identified by its displayed NAME (`Ident`): the page is about
the item when the model is on the item's own URL path, or the item's code is shown, or (a listing card) the needle follows the item's name closely within ONE view."""
from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache

RULE_VERSION = "exp2-evidence-v2"
MARKERS = re.compile(r"\*?\[\d+\]<[^>]*/>")
_TOKEN = re.compile(r"\$|%|\d+(?:\.\d+)?|[^\W\d_]+")
CARD_WINDOW = 260                       # characters after an item's name within which a listing card's text still belongs to that item (cards are ~100-250 characters; a kit card, which lists its parts first, sets 450)


@lru_cache(maxsize=65536)
def norm(s: str) -> str:
    """Canonical form: tokens joined by single spaces (digits, '$', '%' and letter runs; everything else is layout)."""
    t = MARKERS.sub(" ", s or "").lower()
    t = re.sub(r"(?<=\d),(?=\d{3}\b)", "", t)                                      # 1,400 -> 1400
    return " ".join(_TOKEN.findall(t))


@dataclass(frozen=True)
class Ident:
    """Which item a page or a card is about: the name the site displays, the URL path of its own page (what the model actually visited) and, optionally, its code."""
    name: str
    code: str | None = None
    path: str | None = None
    window: int = CARD_WINDOW


@dataclass(frozen=True)
class Clause:
    sig: object              # None (any page) | str (a phrase the page must show, e.g. a page title) | Ident (the page is about this item)
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


def _sig_json(sig):
    return {"name": sig.name, "code": sig.code, "path": sig.path, "window": sig.window} if isinstance(sig, Ident) else sig


def _sig_load(sig):
    return Ident(sig["name"], sig.get("code"), sig.get("path"), sig.get("window", CARD_WINDOW)) if isinstance(sig, dict) else sig


def to_json(facts) -> list:
    return [{"label": f.label, "routes": [[{"sig": _sig_json(c.sig), "needle": c.needle} for c in r] for r in f.routes]} for f in facts]


def from_json(data) -> tuple:
    return tuple(Fact(f["label"], tuple(tuple(Clause(_sig_load(c["sig"]), c["needle"]) for c in r) for r in f["routes"])) for f in data)


BREAK = "\f"                                   # separates the distinct views (scroll positions, revisits) of one path; no phrase and no card window spans it


@dataclass(frozen=True)
class Page:
    path: str
    segs: tuple              # normalised text of each distinct view of this path, in order
    text: str                # all of them, joined by a token no needle contains


def _path(p: str | None) -> str:
    return ((p or "").split("?")[0].split("#")[0].rstrip("/") or "/").lower()


def page(path: str, raw: str) -> Page:
    """`raw` = one or more views joined by BREAK."""
    segs = tuple(dict.fromkeys(norm(x) for x in (raw or "").split(BREAK)))
    return Page(_path(path), segs, " zzviewbreakzz ".join(segs))


def _positions(text: str, phrase: str) -> list[int]:
    out, p, at, hay = [], f" {phrase} ", 0, f" {text} "
    while phrase:
        i = hay.find(p, at)
        if i < 0:
            return out
        out.append(i)
        at = i + 1
    return out


def about(ident: Ident, pg: Page, needle: str) -> bool:
    """Is this page about the item? The model is on the item's own path, or the item's code is shown, or inside ONE view the needle starts after the item's name and within a card's reach."""
    if ident.path and pg.path == _path(ident.path):
        return True
    if ident.code and _positions(pg.text, norm(ident.code)):
        return True
    name = norm(ident.name)
    for seg in pg.segs:
        names, needles = _positions(seg, name), _positions(seg, needle)
        if any(len(name) < n - m <= ident.window for m in names for n in needles):
            return True
    return False


def clause_met(c: Clause, pages: list[Page]) -> bool:
    needle = norm(c.needle)
    for pg in pages:
        if not _positions(pg.text, needle):
            continue
        if c.sig is None:
            return True
        if isinstance(c.sig, Ident):
            if about(c.sig, pg, needle):
                return True
        elif _positions(pg.text, norm(c.sig)):
            return True
    return False


def route_met(route, pages: list[Page]) -> bool:
    return all(clause_met(c, pages) for c in route)


def merged_pages(observations: list[dict] | None) -> list[Page]:
    """One page per distinct path: what the model was shown there across every step (the top of a page, then lower down after scrolling, or on a revisit). The model view holds only the part of a page
    near the viewport, so a fact lower on the page reaches the model through a later observation of the same path. Identical views are counted once."""
    by: dict[str, list[str]] = {}
    for o in observations or []:
        by.setdefault(_path(o.get("path")), []).append(o.get("text") or "")
    return [page(p, BREAK.join(t)) for p, t in by.items()]


def assess(facts, observations: list[dict] | None) -> dict:
    """`observations` = [{'path', 'text'}] as recorded for a trial (what the model was shown). Returns sufficiency and the facts still missing. A task with no facts is never sufficient."""
    pages = merged_pages(observations)
    missing = [f.label for f in facts if not any(route_met(r, pages) for r in f.routes)]
    return {"sufficient": bool(facts) and not missing, "missing": missing, "facts": len(facts), "pages_seen": len(pages), "rule": RULE_VERSION}


def available_in(facts, page_texts: dict[str, str]) -> list[str]:
    """Facts that NO route can satisfy on a site (path -> model-visible text of the page, views joined by BREAK). Empty list = the site (arm) can show the task's evidence."""
    pages = [page(p, t) for p, t in page_texts.items()]
    return [f.label for f in facts if not any(route_met(r, pages) for r in f.routes)]


def sufficient_from(facts, page_texts: dict[str, str]) -> bool:
    """Would the model already have been shown everything the answer depends on, from just these pages (path -> text, views joined by BREAK)?"""
    pages = [page(p, t) for p, t in page_texts.items()]
    return bool(facts) and all(any(route_met(r, pages) for r in f.routes) for f in facts)
