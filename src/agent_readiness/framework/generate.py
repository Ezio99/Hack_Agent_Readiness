"""Autonomous task generation with independent validation, for any `SiteDefinition`.

  snapshot(original) -> profile -> rule-based candidates (taskgen/candidates.py: page facts, listing filters, listing extremes; templated from the
  site's own headings and labels) -> acceptance gate (taskgen/gate.py: compiles against the snapshot; rejects answers visible on the start page,
  duplicates, trivial or ambiguous criteria) -> per task: cross-variant stability, grader_v2 keyability, independent oracle agreement ->
  verifiability class -> a frozen manifest of the SCORING-ELIGIBLE tasks in the existing tasks-manifest format, ready for the trial pipeline.
  Rubric tasks are generated from the site's tables (checklist = the table's stated values) and recorded, never scored.

Offline and free: no model call, no browser. `python -m agent_readiness.framework.generate SITE [--out FILE]`."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from bs4 import BeautifulSoup

from ..grading import v2 as grader_v2
from ..grading.key import build_key
from ..investigate.inspect.profile import build_profile
from ..investigate.taskgen import criteria as C
from ..investigate.taskgen import freeze as freezer
from ..investigate.taskgen.candidates import candidates
from ..investigate.taskgen.gate import Accepted, Rejected, evaluate as gate
from ..suite.core import canonical_hash
from .site import SiteDefinition, get
from .verifiability import CLASSES, RUBRIC, classify, eligible_for_scoring

SCHEMA = "framework-taskset-v1"
GENERATOR = {"id": "framework-rules", "version": "1", "candidates": "investigate.taskgen.candidates", "gate": "investigate.taskgen.gate"}


def _truth_on(criterion: dict, profile: dict):
    try:
        return C.compile_criterion(criterion, profile).truth
    except C.CriterionError:
        return None


def _same(a, b) -> bool:
    if isinstance(a, list) or isinstance(b, list):
        return isinstance(a, list) and isinstance(b, list) and sorted(map(str, a)) == sorted(map(str, b))
    return isinstance(a, str) and isinstance(b, str) and " ".join(a.split()) == " ".join(b.split())


MAX_RUBRIC = 6


def _restricted(profile: dict, site: SiteDefinition) -> dict:
    """The profile with its listings limited to the site's declared catalogue pages (other pages and facts are untouched)."""
    if not site.listings:
        return profile
    return {**profile, "listings": [l for l in profile["listings"] if l["listing"] in site.listings]}


def _entity_pages(profile: dict) -> set[str]:
    return {i["href"] for l in profile["listings"] for g in profile["pages"][l["listing"]]["item_groups"] for i in g["items"]}


def phrase(draft, profile: dict, site: SiteDefinition):
    """Re-phrase a rule-generated question from its criterion with the site's own entity noun (the criterion, and so the answer, is unchanged)."""
    if not site.noun:
        return draft
    one, many = site.noun
    c = draft.criterion
    if c["kind"] == "extremum":
        q = f"Which {one} has the {'highest' if c['direction'] == 'max' else 'lowest'} {c['label']}? Give its name."
    elif c["kind"] == "item_set" and len(c["conditions"]) == 1:
        cond = c["conditions"][0]
        rel = {"lt": "below", "le": "of at most", "gt": "above", "ge": "of at least"}.get(cond["op"])
        q = (f"Which {many} have a {cond['label']} {rel} {cond['value']}? List every one by name." if rel else f"Which {many} have {cond['label']} '{cond['value']}'? List every one by name.")
    elif c["kind"] == "page_fact" and c["page"] in _entity_pages(profile):
        name = next(i["name"] for l in profile["listings"] for g in profile["pages"][l["listing"]]["item_groups"] for i in g["items"] if i["href"] == c["page"])
        q = f"What is the {c['label']} for the {one} '{name}'?"
    else:
        return draft
    return type(draft)(q, draft.start_path, draft.criterion, draft.source, draft.rationale)


def rubric_tasks(snapshot, profile: dict, site: SiteDefinition) -> list[dict]:
    """One open question per captioned table on a non-entity page: 'What does the site say about <caption>?'; checklist = each row's stated value.
    RUBRIC class; at most MAX_RUBRIC per site."""
    out, seen = [], set()
    entities = _entity_pages(profile)                       # entity pages of EVERY profiled listing (detail tables repeat per item)
    for path in sorted(profile["pages"]):
        if any(path == d or path.startswith(d + "/") for d in entities):
            continue
        res = snapshot.resources.get(path)
        if not res or not res.is_html:
            continue
        for table in BeautifulSoup(res.text(), "html.parser").find_all("table"):
            cap = table.find("caption")
            rows = [[c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])] for tr in table.find_all("tr") if tr.find("td")]
            if not cap or len(rows) < 2 or cap.get_text(strip=True).lower() in seen:
                continue
            seen.add(cap.get_text(strip=True).lower())
            checklist = [{"item": r[0], "expected": r[-1]} for r in rows if len(r) >= 2]
            out.append({"task_id": "rub-" + canonical_hash([site.id, path, cap.get_text(strip=True)])[:10], "question": f"What does {site.label} say about {cap.get_text(strip=True).lower()}?",
                        "start_path": site.start_path, "kind": "rubric", "page": path, "checklist": checklist, "class": RUBRIC, "eligible": False,
                        "reasons": ["open answer judged against a checklist"]})
    return out[:MAX_RUBRIC]


def generate(site: SiteDefinition | str, *, per_kind: int = 4) -> dict:
    site = get(site) if isinstance(site, str) else site
    snaps = {v: site.snapshot(v) for v in site.variants}
    profiles = {v: build_profile(s) for v, s in snaps.items()}
    base = site.variants[0]
    profile = profiles[base]
    scoped = _restricted(profile, site)
    drafts = [phrase(d, scoped, site) for d in candidates(scoped, site.start_path, per_kind)]
    accepted: list[Accepted] = []
    rejected = []
    for d in drafts:
        r = gate(d, profile, accepted)
        (accepted.append(r) if isinstance(r, Accepted) else rejected.append({"question": d.question, "kind": d.criterion.get("kind"), "reason": r.reason}))
    oracle = site.oracle() if site.oracle else None
    tasks = []
    for a in accepted:
        truth = a.compiled.truth
        stable = all(_same(_truth_on(a.criterion, profiles[v]), truth) for v in site.variants)
        try:
            build_key(freezer.task_id(a.fingerprint), {"criterion": a.criterion, "truth": truth}, profile)
            key_ok = True
        except grader_v2.KeyError_:
            key_ok = False
        if oracle is None:
            verdict, detail = "absent", None
        else:
            ans = oracle.answer(a.criterion)
            verdict = ("agrees" if _same(ans.truth, truth) else "disagrees") if ans.supported else "declined"
            detail = None if ans.supported else ans.reason
        cls, reasons = classify(key_ok=key_ok, stable=stable, oracle=verdict)
        tasks.append({"task_id": freezer.task_id(a.fingerprint), "question": a.draft.question, "start_path": a.draft.start_path, "kind": a.compiled.kind,
                      "criterion_sha256": canonical_hash(a.criterion), "min_hops": max(a.hops.values(), default=0), "stable_across_variants": stable, "grader_v2_keyable": key_ok,
                      "oracle": verdict, **({"oracle_note": detail} if detail else {}), "class": cls, "eligible": eligible_for_scoring(cls), "reasons": reasons, "_accepted": a})
    rubric = rubric_tasks(snaps[base], profile, site)
    counts = {c: sum(t["class"] == c for t in tasks + rubric) for c in CLASSES}
    return {"schema": SCHEMA, "site": site.id, "label": site.label, "controlled": site.controlled, "variants": {v: s.sha256 for v, s in snaps.items()},
            "generated_on": base, "generator": GENERATOR, "oracle": oracle.label if oracle else None, "drafts": len(drafts), "rejected": rejected,
            "tasks": tasks, "rubric": rubric, "counts": counts, "eligible": sum(t["eligible"] for t in tasks)}


def freeze_eligible(taskset: dict, *, agent_profile: str = "suite-v2-compat2", seed: int = 0) -> tuple[dict, dict]:
    """The scoring-eligible tasks as a standard tasks manifest + private criteria (`freeze.build`), consumable by the existing trial/grading pipeline."""
    acc = [t["_accepted"] for t in taskset["tasks"] if t["eligible"]]
    if not acc:
        raise ValueError("no scoring-eligible tasks")
    return freezer.build(acc, snapshot_sha256=taskset["variants"][taskset["generated_on"]], generator={**GENERATOR, "site": taskset["site"]}, agent_profile=agent_profile, seed=seed)


def public(taskset: dict) -> dict:
    """Shareable view: questions, classes and validation outcomes; no expected answers, no criteria, no checklist values."""
    strip = lambda t: {k: v for k, v in t.items() if not k.startswith("_")}
    return {**{k: v for k, v in taskset.items() if k not in ("tasks", "rubric")}, "tasks": [strip(t) for t in taskset["tasks"]],
            "rubric": [{k: v for k, v in r.items() if k != "checklist"} | {"checklist_items": len(r["checklist"])} for r in taskset["rubric"]]}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="agent_readiness.framework.generate")
    ap.add_argument("site")
    ap.add_argument("--per-kind", type=int, default=4)
    ap.add_argument("--out", type=Path)
    a = ap.parse_args(argv)
    ts = generate(a.site, per_kind=a.per_kind)
    doc = public(ts)
    text = json.dumps(doc, indent=1, sort_keys=True)
    (a.out.write_text(text + "\n") if a.out else None)
    print(f"{ts['site']}: {ts['drafts']} drafts, {len(ts['tasks'])} accepted, {len(ts['rejected'])} rejected, classes {ts['counts']}, scoring-eligible {ts['eligible']}")
    for t in ts["tasks"]:
        print(f"  {t['class']:<13} {t['kind']:<10} oracle={t['oracle']:<9} {t['question']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
