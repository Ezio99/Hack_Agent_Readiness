"""Stage A feedback synthesiser (proposal §3.5). Built ONLY from evaluator-v2 records and the coverage report of the current selection.

It contains: rejection categories with counts and wording-only examples; uncovered persona x journey cells; missing capabilities; criterion
signatures to avoid (labels, operators and thresholds, which the generator itself proposed); underspecified wordings with the standing advice; the
natural-wording share. It NEVER contains expected answers, oracle-derived values, agent results or variant outcomes: wording examples come only
from rejected or underspecified candidates, and every answer string known to the evaluator is withheld from them."""
from __future__ import annotations

import json
import re
from collections import Counter

from ...taskeval.v2 import coverage as COV

VERSION = "feedback-1"
UNDERSPECIFIED_ADVICE = "state the value in the customer's words, or keep the ambiguity and mark it"
ADVICE = {
    "intent_not_preserved": "the specification must express exactly what the customer states: no added, dropped or changed constraints",
    "natural_wording_gate": "state every constraint value in the customer's words; each value must belong to one attribute",
    "not_expressible": "use a supported task shape (lookup, filter, best, best within a filter, either/or via one_of)",
    "grounded": "use only catalogue attributes, items and values",
    "answerable": "the criterion must select some but not all items and have a unique answer (no ties)",
    "unique": "propose new intents, not repeats",
    "executable_wording_unambiguous": "never state or hint at the answer in the scenario",
    "schema_valid": "follow the schema exactly",
}
WITHHELD = "[withheld]"


def _category(reason: str) -> str:
    return reason.split(":", 1)[0].strip()


def answer_strings(records: list[dict]) -> set[str]:
    """Every expected answer the evaluator derived (v2 and the embedded v1 record), for withholding."""
    out = set()
    for r in records:
        for t in (r.get("expected_answer"), (r.get("v1") or {}).get("expected_answer")):
            for s in ([t] if isinstance(t, str) else list(t or [])):
                if isinstance(s, str) and len(s.strip()) >= 3:
                    out.add(s.strip())
    return out


LEAK_MARKERS = ("expected answer", "answer is on the start page", "answer is visible")


def _answer_related(r: dict) -> bool:
    """A rejection that cites the expected answer (a leak in the wording): its wording is never echoed back, because the rejection itself would
    confirm the answer to the generator, and the evaluator may not have derived that answer (the gate refuses before compiling it)."""
    texts = list(r.get("rejection_reasons") or []) + list((r.get("v1") or {}).get("rejection_reasons") or [])
    return any(m in t for t in texts for m in LEAK_MARKERS)


def scrub(text: str, answers: set[str]) -> str:
    for a in sorted(answers, key=len, reverse=True):
        text = re.sub(rf"(?i)(?<!\w){re.escape(a)}(?!\w)", WITHHELD, text)
    return text


def synthesise(records: list[dict], cov: dict, chosen: list[dict], context: dict, *, round_no: int, examples_per_category: int = 2) -> dict:
    answers = answer_strings(records)
    base = [r for r in records if not r.get("derived_from")]
    rejected = [r for r in base if r["admission"] == "rejected"]
    cats = Counter(_category(r["rejection_reasons"][0]) for r in rejected if r["rejection_reasons"])
    rejections = {}
    for cat, n in sorted(cats.items()):
        ex = [r["wording"]["customer"] or "" for r in rejected if r["rejection_reasons"] and _category(r["rejection_reasons"][0]) == cat
              and not _answer_related(r)][:examples_per_category]
        reasons = sorted({scrub(r["rejection_reasons"][0].split(":", 1)[-1].strip(), answers) for r in rejected if r["rejection_reasons"] and _category(r["rejection_reasons"][0]) == cat
                          and cat in ("intent_not_preserved", "natural_wording_gate", "not_expressible", "grounded")})[:3]
        rejections[cat] = {"count": n, "wording_examples": [scrub(e, answers) for e in ex if e], "advice": ADVICE.get(cat, "see the evaluator's rule"),
                           **({"reasons": reasons} if reasons else {})}
    under = [{"wording": scrub(r["wording"]["customer"], answers), "unresolved": [scrub(u, answers) for u in r["wording"]["unresolved"]], "advice": UNDERSPECIFIED_ADVICE}
             for r in base if r["admission"] == "preserved_unexecuted"]
    admitted = [r for r in records if r["admission"] in ("natural", "assisted")]
    avoid = sorted({"; ".join(sorted("|".join(map(str, s)) for s in COV.signature(r["specification"]))) for r in admitted if r["specification"]})
    doc = {"version": VERSION, "round": round_no,
           "uncovered_cells": [{"persona": c["persona"], "journey": c["journey"]} for c in COV.uncovered_cells(cov, context) if c["weight"] >= cov["targets"]["journey_min_weight"]][:10],
           "missing_capabilities": [c for c, n in cov["capabilities"].items() if not n],
           "coverage_gaps": cov["gaps"], "natural_share_of_selection": cov["natural_share"],
           "rejections": rejections, "underspecified": under, "avoid_signatures": avoid,
           "selected_so_far": len(chosen)}
    text = json.dumps(doc, sort_keys=True)
    assert not any(k in text for k in ('"expected"', '"truth"', '"expected_answer"', '"answers"')), "feedback may not carry answer fields"
    return doc
