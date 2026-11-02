"""taskeval-1: structured evaluation records for candidate tasks.

Record per candidate: id and provenance; the three wordings kept apart (customer question, oracle-verifiable specification [private], restated
question); hard gates with evidence; soft judgments with their criteria; quality; rejection reasons; evaluator version and configuration fingerprint.

HARD GATES (deterministic; all must pass)
  schema_valid · grounded (persona, journey, attributes, entities and values exist in the configured context and verified catalogue) ·
  expressible (a closed criterion the oracle can check: not open, not a ranking inside a filtered subset) · answerable (compiles; not empty, not
  everything, no tie) · unique (no identical criterion earlier in the set) · executable_wording_unambiguous (the wording that would be executed
  passes the acceptance gate, which also rejects answer leaks) · oracle_agrees · grader_v1_compatible (v1 passes the derived answer, fails a wrong
  one) · grader_v2_compatible (v2 keys the task, passes the derived answer, fails a wrong one) · cross_version_fair (same answer on every site
  version and the evidence pages exist on each) · evidence_sufficient
SOFT JUDGMENTS (0..1, explicit criteria in CONFIG; they rank, never admit)
  persona_relevance · journey_relevance · realism · specificity (constraint values stated in the customer's own words; the rest are recorded as
  assumptions the generator introduced) · novelty (1 - highest similarity to another passing candidate)"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from ..grading import v2 as G2
from ..grading.key import build_key
from ..investigate.taskgen import criteria as C
from ..suite.core import canonical_hash

VERSION = "taskeval-1"
CONFIG = {
    "persona_attributes": {                              # SYNTHETIC, documented: which verified attributes each persona's stated needs and constraints refer to
        "career_switcher": ["level", "materials", "class day"],
        "recent_graduate": ["course fee", "duration"],
        "budget_learner": ["course fee", "seats left"],
        "professional_upskiller": ["level", "campus", "class day", "seats left"],
    },
    "realism": {"min_words": 8, "max_words": 60, "first_person": ["i", "i'm", "i've", "my", "me"]},
    "weights": {"persona_relevance": 0.3, "journey_relevance": 0.2, "realism": 0.2, "specificity": 0.2, "novelty": 0.1},
    "near_duplicate_similarity": 0.6,
}
GROUNDING_CATEGORIES = {"unknown_persona", "unknown_journey", "unsupported_attribute", "operator_not_applicable", "value_not_in_domain", "value_type_mismatch", "unknown_entity"}


def config_fingerprint() -> str:
    h = hashlib.sha256(json.dumps(CONFIG, sort_keys=True).encode())
    h.update(Path(__file__).read_bytes())
    return h.hexdigest()[:16]


def _signature(crit: dict | None) -> set:
    if not crit:
        return set()
    if crit["kind"] == "item_set":
        return {(c["label"], c["op"], C.norm_answer(c["value"])) for c in crit["conditions"]}
    if crit["kind"] == "extremum":
        return {(crit["label"], crit["direction"])}
    return {(crit["page"], crit["label"])}


def _attrs(crit: dict | None) -> set[str]:
    if not crit:
        return set()
    return {c["label"] for c in crit.get("conditions", [])} | ({crit["label"]} if "label" in crit else set())


def _realism(text: str) -> tuple[float, dict]:
    words = re.findall(r"[\w'$]+", (text or "").lower())
    cfg = CONFIG["realism"]
    checks = {"is_question": "?" in (text or ""), "customer_context": any(w in cfg["first_person"] for w in words),
              "length_ok": cfg["min_words"] <= len(words) <= cfg["max_words"], "no_quoted_field_names": not re.search(r"'[^']+'", text or "")}
    return round(sum(checks.values()) / len(checks), 3), checks


def _specificity(text: str, crit: dict | None) -> tuple[float | None, list[str]]:
    if not crit or crit["kind"] != "item_set":
        return None, []
    t = C.norm_answer(text or "")
    missing = [f"{c['label']} {c['op']} {c['value']}" for c in crit["conditions"] if C.norm_answer(c["value"]).replace("$", "") not in t.replace("$", "")]
    return round(1 - len(missing) / len(crit["conditions"]), 3), missing


class TaskEvaluator:
    def __init__(self, site, catalogue_view: dict, context: dict):
        from ..research.taskplan.verify import Verifier
        self.site, self.view, self.context = site, catalogue_view, context
        self.raw, self.framed = Verifier(site, catalogue_view, "raw"), Verifier(site, catalogue_view, "framed")
        self.profiles = self.framed.profiles

    def _grader_checks(self, crit: dict, truth) -> tuple[bool, bool, str]:
        comp = C.compile_criterion(crit, self.framed.base)
        wrong = ["Nothing"] if comp.style == "set" else "Nothing"
        v1 = C.grade(comp, truth)[0] and not C.grade(comp, wrong)[0]
        try:
            key = build_key("c", {"criterion": crit, "truth": truth}, self.framed.base)
            v2 = G2.grade(key, truth).passed and not G2.grade(key, wrong).passed
        except G2.KeyError_:
            v2 = False
        return v1, v2, comp.evidence_paths and ",".join(comp.evidence_paths[:4])

    def _fair(self, crit: dict, truth) -> tuple[bool, dict]:
        out = {}
        for v, prof in self.profiles.items():
            try:
                comp = C.compile_criterion(crit, prof)
                out[v] = comp.truth == truth and all(e in prof["pages"] for e in comp.evidence_paths)
            except C.CriterionError:
                out[v] = False
        return all(out.values()), out

    def evaluate(self, candidates: list[dict]) -> list[dict]:
        """candidates: [{candidate_id, provenance, raw (the proposal as generated)}] in a fixed order (duplicates are judged in that order)."""
        from ..research.taskplan.schema import parse_item
        records = []
        for i, cand in enumerate(candidates):
            p, stripped, errors = parse_item(cand["raw"])
            d_raw = self.raw.verify(i, p, errors)
            d_fr = self.framed.verify(i, p, errors)
            crit, truth = d_fr.criterion, d_fr.truth
            gates = {"schema_valid": {"pass": p is not None, "evidence": errors[:3]}}
            cat = d_fr.category
            gates["grounded"] = {"pass": p is not None and cat not in GROUNDING_CATEGORIES, "evidence": d_fr.reasons[:1] if cat in GROUNDING_CATEGORIES else []}
            gates["expressible"] = {"pass": d_fr.outcome == "accepted" and d_fr.cls == "deterministic" or (d_fr.outcome == "rejected" and cat not in (None,)),
                                    "evidence": d_fr.reasons[:1] if d_fr.cls in ("rubric", "human_review") else []}
            if d_fr.cls in ("rubric", "human_review"):
                gates["expressible"]["pass"] = False
            gates["answerable"] = {"pass": cat != "not_answerable" and crit is not None, "evidence": d_fr.reasons[:1] if cat == "not_answerable" else []}
            gates["unique"] = {"pass": cat != "duplicate", "evidence": d_fr.reasons[:1] if cat == "duplicate" else []}
            gates["executable_wording_unambiguous"] = {"pass": cat != "gate_rejected" and crit is not None, "evidence": d_fr.reasons[:1] if cat == "gate_rejected" else []}
            if crit is not None:
                oracle = self.framed.oracle.answer(crit)
                norm = lambda x: sorted(x) if isinstance(x, list) else x
                gates["oracle_agrees"] = {"pass": oracle.supported and norm(oracle.truth) == norm(truth), "evidence": [self.framed.oracle.label]}
                v1, v2, ev = self._grader_checks(crit, truth)
                gates["grader_v1_compatible"] = {"pass": v1, "evidence": ["generated-criteria v1"]}
                gates["grader_v2_compatible"] = {"pass": v2, "evidence": [f"generated-criteria v2 {G2.code_sha256()[:12]}"]}
                fair, per = self._fair(crit, truth)
                gates["cross_version_fair"] = {"pass": fair, "evidence": [json.dumps(per)]}
                gates["evidence_sufficient"] = {"pass": bool(d_fr.complexity.get("evidence_pages")), "evidence": [ev] if ev else []}
            else:
                for g in ("oracle_agrees", "grader_v1_compatible", "grader_v2_compatible", "cross_version_fair", "evidence_sufficient"):
                    gates[g] = {"pass": False, "evidence": ["no verifiable specification"]}
            hard_pass = all(g["pass"] for g in gates.values())
            persona = getattr(p, "persona", None)
            attrs = _attrs(crit)
            pa = set(CONFIG["persona_attributes"].get(persona, []))
            journey = next((j for j in self.context["journeys"] if j["id"] == getattr(p, "journey", None)), None)
            realism, rchecks = _realism(getattr(p, "scenario", ""))
            spec, assumptions = _specificity(getattr(p, "scenario", ""), crit)
            soft = {"persona_relevance": round(len(attrs & pa) / len(attrs), 3) if attrs else None,
                    "journey_relevance": (1.0 if journey and set(journey["attributes"]) & attrs else 0.0) if attrs else None,
                    "realism": realism, "specificity": spec}
            restated = next((r[len("agent question: "):] for r in d_fr.reasons if r.startswith("agent question: ")), None)
            records.append({"candidate_id": cand["candidate_id"], "provenance": cand["provenance"], "index": i,
                            "wordings": {"customer_question": getattr(p, "scenario", None), "restated_question": restated, "executed": None},
                            "specification": crit, "expected_answer": truth,                    # PRIVATE fields: stripped by public()
                            "specification_sha256": canonical_hash(crit) if crit else None,
                            "persona": persona, "journey": getattr(p, "journey", None), "task_type": getattr(p, "task_type", None),
                            "attributes": sorted(attrs), "natural_wording_passes_gate": d_raw.outcome == "accepted" and d_raw.cls == "deterministic",
                            "hard_gates": gates, "hard_pass": hard_pass, "soft": soft, "realism_checks": rchecks, "unsupported_assumptions": assumptions,
                            "stripped_answer_fields": stripped, "complexity": d_fr.complexity, "decision": {"outcome": d_fr.outcome, "class": d_fr.cls, "category": cat},
                            "rejection_reasons": [f"{k}: {'; '.join(v['evidence']) or 'failed'}" for k, v in gates.items() if not v["pass"]],
                            "evidence_refs": (d_fr.accepted.compiled.evidence_paths if d_fr.accepted else []),
                            "evaluator": {"version": VERSION, "config_fingerprint": config_fingerprint(), "advisory_llm_judge": None}, "_accepted": d_fr.accepted})
        passing = [r for r in records if r["hard_pass"]]
        for r in records:
            sims = [len(_signature(r["specification"]) & _signature(o["specification"])) / max(1, len(_signature(r["specification"]) | _signature(o["specification"])))
                    for o in passing if o is not r and r["specification"]]
            top = max(sims, default=0.0)
            r["soft"]["novelty"] = round(1 - top, 3)
            r["near_duplicate"] = top >= CONFIG["near_duplicate_similarity"]
            w = CONFIG["weights"]
            vals = {k: (r["soft"][k] if r["soft"][k] is not None else 0.0) for k in w}
            r["quality"] = round(sum(w[k] * vals[k] for k in w), 3) if r["hard_pass"] else None
        return records


def public(record: dict) -> dict:
    """Shareable record: no specification values tied to answers, no expected answer, no internal objects."""
    out = {k: v for k, v in record.items() if k not in ("specification", "expected_answer", "_accepted")}
    out["stripped_answer_fields"] = sorted(record.get("stripped_answer_fields") or {})      # names only: an LLM-claimed answer may coincide with the truth
    return out
