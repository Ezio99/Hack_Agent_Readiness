"""Success criteria for generated tasks: a closed set of kinds, each with a deterministic extractor and an independent grader.

A criterion names WHERE the answer lives (page / listing / label / threshold); the expected answer is never supplied by anyone — `compile_criterion` re-derives it from the
snapshot's own pages. So a model (or owner) that proposes a wrong or unverifiable criterion simply fails to compile, and a correct criterion cannot be made to disagree with the site.

  page_fact   the value of a labelled fact on one page                        (fact retrieval)
  reach_page  the title of a target page                                      (navigation)
  item_set    names of the repeated listing items whose linked pages satisfy conditions   (cross-page filtering)
  extremum    the listing item with the highest/lowest numeric value of a labelled fact   (cross-page comparison)
Grading is exact on normalised strings / sets, never fuzzy."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field

from ..inspect.pagemodel import norm

KINDS = ("page_fact", "reach_page", "item_set", "extremum")


class CriterionError(ValueError):
    """The criterion cannot be compiled against this site (reason is human-readable and contains no expected answers)."""


class Condition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    label: str = Field(min_length=1, max_length=40)
    op: Literal["eq", "contains", "lt", "le", "gt", "ge"]
    value: str = Field(min_length=1, max_length=60)


class PageFact(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["page_fact"] = "page_fact"
    page: str
    label: str


class ReachPage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["reach_page"] = "reach_page"
    target: str


class ItemSet(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["item_set"] = "item_set"
    listing: str
    conditions: list[Condition] = Field(min_length=1, max_length=3)


class Extremum(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["extremum"] = "extremum"
    listing: str
    label: str
    direction: Literal["max", "min"]


Criterion = Annotated[Union[PageFact, ReachPage, ItemSet, Extremum], Field(discriminator="kind")]


@dataclass
class Compiled:
    kind: str
    style: str                                   # "string" | "set"
    truth: str | list[str]
    evidence_paths: list[str]                    # pages whose visit is required for an evidence-backed pass
    evidence_texts: list[tuple[str | None, str]]  # (path or None=any page, text) that must have been shown to the model
    start_hint_pages: list[str] = field(default_factory=list)
    detail: dict = field(default_factory=dict)
    distractors: list[str] = field(default_factory=list)       # other answers the site offers for the same question (an answer that also names one is a hedge, not an answer)


def norm_answer(s: str) -> str:
    """Lower-case, collapse whitespace/punctuation; a '.' survives only between digits (decimals), so 'Spoon Carving.' matches 'Spoon Carving'."""
    t = re.sub(r"(?<!\d)\.|\.(?!\d)", " ", norm(str(s)).lower())
    return re.sub(r"[^\w$%.]+", " ", t).strip()


HEDGE_WORDS = re.compile(r"(?<!\w)(or|either|maybe|perhaps|possibly|probably|unsure|between|neither|nor)(?!\w)|/")


def _phrase(needle: str, hay: str):
    return re.search(rf"(?<!\w){re.escape(needle)}(?!\w)", hay)


def answer_match(truth: str, answer: str, distractors: list[str] | tuple[str, ...] = ()) -> bool:
    """Exact after normalisation, or the truth appears as a whole phrase inside a SHORT sentence (<= truth length + 16 chars) that does NOT also name another answer the site offers for
    this question (`distractors`). 'It is $45.' passes; '12 Nov or 14 Nov' and 'Silver Ring Making or Pottery Basics' do not (a hedge covers several answers, so it is not one)."""
    t, a = norm_answer(truth), norm_answer(answer)
    if not a:
        return False
    if a == t:
        return True
    if len(a) > len(t) + 16 or not _phrase(t, a):
        return False
    m = _phrase(t, a)
    rest = (a[:m.start()] + " " + a[m.end():])
    if HEDGE_WORDS.search(rest):                              # "X or something else", "either X", "maybe X", "X / Y": an answer that offers alternatives is a hedge even if the alternative is not a known candidate
        return False
    return not any((nd := norm_answer(d)) and nd != t and _phrase(nd, rest) for d in distractors)


def quantity(value: str) -> tuple[float, str] | None:
    """('$45' -> (45.0, '$')), ('2 hours' -> (2.0, 'hours')); None when there is no single leading/trailing number."""
    m = re.fullmatch(r"\s*([^\d\-]*?)\s*(-?\d[\d,]*(?:\.\d+)?)\s*([^\d]*?)\s*", value or "")
    if not m:
        return None
    unit = (m.group(1) + m.group(3)).strip().lower()
    return float(m.group(2).replace(",", "")), unit


def _page(profile: dict, path: str) -> dict:
    if path not in profile["pages"]:
        raise CriterionError(f"page {path!r} is not part of the snapshot")
    return profile["pages"][path]


def _fact(page: dict, label: str) -> list[str]:
    return sorted({f["value"] for f in page["facts"] if f["label"] == norm(label).lower()})


def _items(profile: dict, listing: str) -> list[dict]:
    groups = _page(profile, listing)["item_groups"]
    groups = [g for g in groups if sum(i["href"] in profile["pages"] for i in g["items"]) >= 3]
    if not groups:
        raise CriterionError(f"{listing!r} has no repeated items linking to captured pages")
    g = max(groups, key=lambda g: len(g["items"]))
    items = [i for i in g["items"] if i["href"] in profile["pages"]]
    names = [i["name"] for i in items]
    if any(not n for n in names) or len(set(names)) != len(names):
        raise CriterionError("listing items do not have unique visible names")
    return items


def _needs_detail(item: dict, value: str) -> bool:
    """A detail-page visit is required evidence only when the decisive value is not already on the listing item (computed from the snapshot, so it holds on any site)."""
    return norm_answer(value) not in norm_answer(item["text"])


def _op(cond: Condition, raw: str) -> bool:
    if cond.op in ("eq", "contains"):
        a, b = norm_answer(raw), norm_answer(cond.value)
        return a == b if cond.op == "eq" else b in a
    q, ref = quantity(raw), quantity(cond.value)
    if q is None or ref is None or q[1] != ref[1]:
        raise CriterionError(f"values of {cond.label!r} are not comparable numbers with one unit")
    return {"lt": q[0] < ref[0], "le": q[0] <= ref[0], "gt": q[0] > ref[0], "ge": q[0] >= ref[0]}[cond.op]


def compile_criterion(c: Criterion | dict, profile: dict) -> Compiled:
    c = c if isinstance(c, BaseModel) else _parse(c)
    if isinstance(c, PageFact):
        page = _page(profile, c.page)
        vals = _fact(page, c.label)
        if not vals:
            raise CriterionError(f"no fact labelled {c.label!r} on {c.page}")
        if len(vals) > 1:
            raise CriterionError(f"fact {c.label!r} on {c.page} has several different values (ambiguous)")
        others = sorted({f["value"] for p in profile["pages"].values() for f in p["facts"] if f["label"] == norm(c.label).lower()} - {vals[0]})
        return Compiled("page_fact", "string", vals[0], [c.page], [(c.page, vals[0])], distractors=others)
    if isinstance(c, ReachPage):
        page = _page(profile, c.target)
        title = page["title"]
        if not title or sum(1 for p in profile["pages"].values() if p["title"] == title) != 1:
            raise CriterionError("target page has no unique title")
        return Compiled("reach_page", "string", title, [c.target], [(c.target, title)], distractors=sorted({p["title"] for q, p in profile["pages"].items() if q != c.target and p["title"]} - {title}))
    if isinstance(c, ItemSet):
        items = _items(profile, c.listing)
        hit, need = [], []
        for it in items:
            ok, vals_seen = True, []
            for cond in c.conditions:
                vals = _fact(profile["pages"][it["href"]], cond.label)
                if len(vals) != 1:
                    raise CriterionError(f"item {it['name']!r}: fact {cond.label!r} missing or ambiguous on its page")
                ok = ok and _op(cond, vals[0])
                vals_seen.append(vals[0])
            if ok:
                hit.append(it)
                if any(_needs_detail(it, v) for v in vals_seen):
                    need.append(it["href"])
        if not 1 <= len(hit) <= len(items) - 1:
            raise CriterionError(f"criterion selects {len(hit)} of {len(items)} items; it must select some but not all")
        return Compiled("item_set", "set", sorted(i["name"] for i in hit), [c.listing] + need, [(None, i["name"]) for i in hit], [c.listing],
                        {"items": len(items), "selected": len(hit), "detail_visits_required": len(need)})
    items = _items(profile, c.listing)
    vals = []
    for it in items:
        v = _fact(profile["pages"][it["href"]], c.label)
        q = quantity(v[0]) if len(v) == 1 else None
        if q is None:
            raise CriterionError(f"item {it['name']!r}: fact {c.label!r} missing, ambiguous or not numeric")
        vals.append((q, it))
    if len({q[1] for q, _ in vals}) != 1 or len(vals) < 3:
        raise CriterionError("values are not comparable (mixed units) or there are fewer than 3 items")
    ranked = sorted(vals, key=lambda x: x[0][0], reverse=(c.direction == "max"))
    if ranked[0][0][0] == ranked[1][0][0]:
        raise CriterionError("the extreme value is tied; the answer would be ambiguous")
    win = ranked[0][1]
    wv = _fact(profile["pages"][win["href"]], c.label)[0]
    return Compiled("extremum", "string", win["name"], [c.listing] + ([win["href"]] if _needs_detail(win, wv) else []), [(None, win["name"])], [c.listing],
                    {"items": len(items), "detail_visits_required": int(_needs_detail(win, wv))}, distractors=sorted({i["name"] for _, i in vals} - {win["name"]}))


def _parse(c):
    from pydantic import TypeAdapter
    return TypeAdapter(Criterion).validate_python(c)


def grade(compiled: Compiled, answer) -> tuple[bool, dict]:
    """Independent grading from the compiled truth; the agent's own claims are never consulted. Returns (passed, details)."""
    if compiled.style == "string":
        a = answer if isinstance(answer, str) else ""
        ok = answer_match(compiled.truth, a, compiled.distractors)
        return ok, {"expected_kind": compiled.kind, **({} if ok or not a else {"hedged": answer_match(compiled.truth, a) and not ok})}
    got = {norm_answer(x) for x in (answer if isinstance(answer, list) else []) if isinstance(x, str) and x.strip()}
    want = {norm_answer(x) for x in compiled.truth}
    tp = len(got & want)
    return got == want, {"precision": round(tp / len(got), 3) if got else 0.0, "recall": round(tp / len(want), 3), "extra": len(got - want), "missing": len(want - got)}
