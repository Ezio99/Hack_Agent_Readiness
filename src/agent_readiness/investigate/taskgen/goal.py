"""Goal-bound task generation: (1) the schema and prompt that make the evaluation goal a BINDING objective (the model must decompose it into entities, attributes, comparisons and information gaps
BEFORE proposing tasks, and link every task to a part of it); (2) an INDEPENDENT goal-relevance verifier that never trusts those links. The verifier grounds the goal in the captured site (which
listing/items are 'the cutting tools', which fact labels are 'price', which pages are 'availability') and judges each gate-accepted task by what its criterion actually touches. Relevance is a
separate outcome from answerability (the gate, unchanged): a task can be answerable and irrelevant, and the report keeps both. The lexicon below is deliberately small and explicit; what it cannot
ground is reported as a limitation, never papered over with unrelated tasks."""
from __future__ import annotations

import re
from typing import Optional

from pydantic import BaseModel, ConfigDict

from .propose import CriterionDraft

STOP = set("the and for are how why who has had was were not you our its out any all but yet via per can could would should does will with that this have from what which when into your their there about across between each every than then them they also only some more most "
           "agent agents user users site website evaluate evaluation check whether find able shopper shoppers customer customers person people compare comparing comparison hire hiring "
           "rent rental item items product products thing things tool tools equipment kind type best good right".split())
ORDER_TERMS = {"cheapest", "cheaper", "cheap", "lowest", "highest", "most", "least", "best", "top", "biggest", "smallest", "largest"}
NUMBERS = {"one", "two", "three", "four", "five", "six"}
# Domain vocabulary (what an aspect such as a price or a stock level means on a given kind of site) is NOT here: this package stays domain-neutral. The caller injects a lexicon:
#   {aspect: {"terms": goal words that ask for it, "labels": fact-label words that carry it, "path_suffix": page-path suffix that carries it or None, "unsupported_note": text for the limitation}}


def stem(w: str) -> str:
    w = w.lower()
    for suf in ("ing", "es", "s"):
        if w.endswith(suf) and len(w) - len(suf) >= 4:
            return w[: -len(suf)]
    return w


def words(text: str) -> list[str]:
    return re.findall(r"[a-z]{3,}", (text or "").lower())


# --------------------------------------------------------------------------------------------------------------------------------------------------- model side: schema and prompt
class GoalAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid")
    entities: list[str]               # the things on this website the goal is about (items, categories, pages)
    attributes: list[str]             # the facts about them the goal needs
    comparisons: list[str]            # what has to be compared or ranked
    information_gaps: list[str]       # what must still be found on the site to answer the goal


class GoalTaskDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str
    start_path: str
    criterion: CriterionDraft
    rationale: str
    goal_link: str                    # which entity + attribute / gap of the goal this task serves


class GoalTaskProposals(BaseModel):
    model_config = ConfigDict(extra="forbid")
    goal_analysis: GoalAnalysis
    tasks: list[GoalTaskDraft]


PURPOSE = "taskgen-goal"
ANGLES = ("tasks that retrieve a labelled fact about one of the goal's entities that the goal needs (page_fact tasks)",
          "tasks that reach the page holding information the goal needs about one of its entities (reach_page tasks)",
          "tasks that compare or filter the goal's entities on an attribute the goal needs (item_set and extremum tasks)")


CONTEXT_RULE = ("CLIENT CONTEXT (a briefing written by the site owner; UNVERIFIED and NOT evidence about the website): use it ONLY to understand the business, its customers' workflows and priorities, and to choose "
                "what matters. Never treat any statement in it as a fact about the pages, never copy figures or claims from it into a question or criterion, and never rely on it for an answer: every task must "
                "be answerable from the website itself.")


def bound_text(focus: str, context: str | None = None) -> str:
    ctx = f"\n\n{CONTEXT_RULE}\n<client_context>\n{context}\n</client_context>" if context else ""
    return (ctx + f"\n\nEVALUATION GOAL (binding): {focus}\n"
            "Step 1, in `goal_analysis`: decompose the goal. `entities`: the things on THIS website it is about. `attributes`: the facts about them it needs. `comparisons`: what must be compared or ranked. "
            "`information_gaps`: what has to be found on the site to answer it.\n"
            "Step 2, in `tasks`: propose only tasks that directly advance answering the goal: each must retrieve a fact the goal needs about one of its entities, or reach the page that holds it, or compare "
            "those entities on a needed attribute. Fill `goal_link` with the entity and attribute (or gap) the task serves. Do NOT propose generic catalogue trivia or tasks about other items or attributes, "
            "even if they would be easy. If the site cannot express part of the goal in the allowed criteria, propose fewer tasks rather than unrelated ones.\n"
            "Spread the tasks over the goal's entities and attributes instead of returning to one item: when the goal concerns several items, use different items and the different facts it needs. Prefer a fact read from an "
            "item's own page (page_fact) when it can be checked independently there, and prefer facts the start page does not already show. This is a preference, not a quota: if the goal or the site does not suit one task per "
            "entity, propose what best serves the goal.\n"
            "A comparison or filter task (item_set, extremum) must name its entity scope in the question (for example 'among the <category> items', never just 'in the list'), and its `listing` should be the page that lists exactly "
            "the goal's items when the site has one; if only a broader listing exists, say so in the question rather than imply the narrower scope.\n"
            "For reach_page, `target` is a page path exactly as written in the summary (preferred) or the exact title of that page; a title shared by several pages is refused.")


# --------------------------------------------------------------------------------------------------------------------------------------------------- verifier side: ground the goal in the site
def _category_items(profile: dict, listing: str) -> list[str]:
    pages = profile["pages"]
    out = []
    for g in pages[listing].get("item_groups", []):
        for i in g["items"]:
            h = i["href"]
            if h in pages and "/category/" not in h and "/sort/" not in h and h != listing and h.startswith("/hire/") and h.count("/") == 2:
                out.append(h)
    return list(dict.fromkeys(out))


def analyse(goal: str, profile: dict, lexicon: dict | None = None) -> dict:
    ASPECTS = lexicon or {}
    pages = profile["pages"]
    ws = words(goal)
    aspect_words = {a: sorted({stem(w) for w in ws if w in v["terms"]}) for a, v in ASPECTS.items()}
    asked = {a for a, w in aspect_words.items() if w}
    labels_on_site = sorted({f["label"] for p in pages.values() for f in p["facts"]})
    ordering = sorted({w for w in ws if w in ORDER_TERMS} | {w for w in ws if w in NUMBERS})
    content = [w for w in ws if w not in STOP and w not in ORDER_TERMS and w not in NUMBERS and not any(w in v["terms"] for v in ASPECTS.values())]
    heading_stems = {stem(x) for path, rec in pages.items() if "/category/" in path for x in words(rec["headings"][0]["text"] if rec["headings"] else "")}
    ent_terms = sorted({stem(w) for w in content if stem(w) in heading_stems})                      # words that name a listing/category of this site
    label_stems = {stem(x): l for l in labels_on_site for x in words(l)}
    attr_labels = sorted({label_stems[stem(w)] for w in content if stem(w) in label_stems and stem(w) not in set(ent_terms)})
    listings, items = [], []
    for path, rec in pages.items():
        h1 = (rec["headings"][0]["text"] if rec["headings"] else "") or ""
        if "/category/" in path and {stem(x) for x in words(h1)} & set(ent_terms):
            listings.append(path)
            items += _category_items(profile, path)
    for path, rec in pages.items():                                            # items named by an entity word (e.g. the goal says "saws")
        if "/category/" not in path and "/sort/" not in path and path.count("/") == 2 and {stem(x) for x in words(rec["title"].split("|")[0])} & set(ent_terms) and ent_terms:
            items.append(path)
    items = list(dict.fromkeys(items))
    support = {}
    for name, spec in ASPECTS.items():
        found_labels = sorted({l for p in (items or list(pages)) for f in pages.get(p, {"facts": []})["facts"] for l in [f["label"]] if set(words(l)) & set(spec["labels"])})
        found_pages = sorted(p for p in ({i + (spec["path_suffix"] or "") for i in items} if spec["path_suffix"] else set()) if p in pages)
        support[name] = {"supported": bool(found_labels or found_pages), "labelled_facts_found": found_labels, "pages_found": found_pages}
    limits, details = [], []
    for a in sorted(asked):
        if support[a]["supported"]:
            continue
        pat = ASPECTS[a].get("text_pattern")
        shown = bool(pat and any(re.search(pat, pages.get(p, {"text": ""})["text"]) for p in (items or [])))
        kind = "capture" if shown else "website"
        detail = ("the captured pages of the goal's entities SHOW this to a browser agent (matching text is on the page) but it was not extracted as a labelled fact or page the criteria can use" if shown
                  else "none of the captured pages of the goal's entities shows it, so no task about it can be verified")
        details.append({"aspect": a, "kind": kind, "detail": detail})
        limits.append(f"{a} [{kind} limitation]: {detail}")
    if ent_terms and not items and not listings:
        details.append({"aspect": "entity", "kind": "verifier", "detail": f"the goal's subject words {ent_terms} could not be matched to any listing or item on the site"})
        limits.append(f"entity [verifier limitation]: {details[-1]['detail']}")
    if any(w in NUMBERS for w in ordering) and any(w in ORDER_TERMS for w in ordering):
        details.append({"aspect": "ordering", "kind": "verifier", "detail": "an exact top-N ranking (e.g. 'the two cheapest') is not a criterion kind: it is covered by per-item facts and single lowest/highest comparisons, not verified as a ranking"})
        limits.append(f"ordering [verifier limitation]: {details[-1]['detail']}")
    return {"goal": goal, "asked_aspects": sorted(asked), "aspect_words": aspect_words, "attribute_labels": attr_labels, "ordering_terms": ordering, "entity_terms": ent_terms, "entity_listings": listings,
            "entity_items": items, "entity_grounded": bool(items or listings), "support": support, "limitations": limits, "limitation_details": details}


def _labels_of(criterion: dict) -> list[str]:
    c = criterion
    if c["kind"] == "page_fact":
        return [c["label"]]
    if c["kind"] == "extremum":
        return [c["label"]]
    if c["kind"] == "item_set":
        return [x["label"] for x in c["conditions"]]
    return []


def assess(ga: dict, accepted, lexicon: dict | None = None) -> dict:
    ASPECTS = lexicon or {}
    """Independent relevance of ONE gate-accepted task: what its criterion touches versus what the goal needs. Does not read the model's own `goal_link`."""
    c = accepted.criterion
    labels = _labels_of(c)
    lw = {stem(w) for l in labels for w in words(l)}
    paths = set(accepted.compiled.evidence_paths) | ({c["listing"]} if c.get("listing") else set())
    hit = []
    for a in ga["asked_aspects"]:
        spec = ASPECTS[a]
        if (lw & {stem(x) for x in spec["labels"]}) or (spec["path_suffix"] and any(p.endswith(spec["path_suffix"]) for p in paths)):
            hit.append(a)
    attr = sorted(l for l in labels if l in ga["attribute_labels"])
    hit += [f"attribute:{l}" for l in attr]
    entity_scope = set(ga["entity_items"]) | set(ga["entity_listings"])
    entity = None if not ga["entity_terms"] else ((any(p in entity_scope or any(p.startswith(i + "/") for i in ga["entity_items"]) for p in paths)) if ga["entity_grounded"] else None)
    touched = sorted({i for i in ga["entity_items"] for p in paths if p == i or p.startswith(i + "/")})
    relevant = bool(hit) and entity is not False and (entity is True or not ga["entity_terms"] or entity is None)
    why = ("serves the goal: touches " + ", ".join(hit) + ("" if entity is None else " of the goal's entities")) if relevant else (
        "not relevant: " + ("it touches no aspect or attribute the goal asks about" if not hit else "it is about an entity outside the goal's subject") + (f" (labels: {labels})" if labels else ""))
    return {"question": accepted.draft.question, "aspects_matched": hit, "entity_match": entity, "goal_relevant": relevant, "entities_touched": touched, "why": why, "model_goal_link": _link(accepted.draft.rationale)}


def _link(rationale: str) -> str | None:
    m = re.search(r"\|\| goal_link: (.*)$", rationale or "")
    return m.group(1) if m else None


def select(assessed: list[dict], limit: int) -> list[int]:
    """Choose up to `limit` goal-relevant tasks (indices) by marginal coverage of the goal's (aspect, entity) cells, earliest first on ties. Unrelated tasks are never used to fill."""
    cells = lambda v: {(a, e) for a in v["aspects_matched"] for e in (v["entities_touched"] or ["*"])}
    pool, chosen, covered = [i for i, v in enumerate(assessed) if v["goal_relevant"]], [], set()
    while pool and len(chosen) < limit:
        best = max(pool, key=lambda i: (len(cells(assessed[i]) - covered), -i))
        chosen.append(best)
        covered |= cells(assessed[best])
        pool.remove(best)
    return sorted(chosen)


def coverage(ga: dict, selected: list[dict]) -> dict:
    """Bounded, evidence-based goal coverage: every aspect the goal asks for AND the site can express must be covered by at least one selected relevant task, and when the goal names attributes at least
    one of them must be. Aspects the site cannot express are reported with their cause (website, capture or verifier limitation) and do not block a run that covers the rest; a run with no relevant
    task, or with a supportable aspect uncovered, fails."""
    covered = {a for v in selected for a in v["aspects_matched"]}
    needed = [a for a in ga["asked_aspects"] if ga["support"][a]["supported"]]
    missing = [a for a in needed if a not in covered]
    if ga["attribute_labels"] and not any(c.startswith("attribute:") for c in covered):
        missing.append("attribute (any of: " + ", ".join(ga["attribute_labels"]) + ")")
    ents = sorted({e for v in selected for e in v["entities_touched"]})
    unsupported = [d["aspect"] for d in ga["limitation_details"] if d["aspect"] in ga["asked_aspects"]]
    unverified = [d["aspect"] for d in ga["limitation_details"] if d["kind"] == "verifier"]
    passes = bool(selected) and not missing
    why = ([f"aspect not expressible on the site: {a}" for a in unsupported] + [f"not verifiable as asked: {a}" for a in unverified] +
           ([f"entities not covered: {len(ga['entity_items']) - len(ents)} of {len(ga['entity_items'])}"] if len(ents) < len(ga["entity_items"]) else []) + [f"aspect left uncovered: {m}" for m in missing])
    status = "insufficient" if not passes else ("partial" if why else "complete")
    return {"status": status, "partial_because": why if passes else [], "needed_aspects": needed, "covered": sorted(covered), "missing_supported": missing, "unsupported_aspects": unsupported, "unverified_aspects": unverified,
            "entities_total": len(ga["entity_items"]), "entities_covered": ents, "passes": passes}
