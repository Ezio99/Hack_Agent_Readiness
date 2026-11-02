"""Independent verification of planner proposals. The expected outcome is never taken from the LLM: each intent is translated into the existing
criterion language and checked with the UNCHANGED engine pieces (compile_criterion against the frozen snapshot, the acceptance gate, the site's
record oracle, cross-variant stability, grader_v2 keyability, evidence pages). Nothing here is relaxed to let more proposals through.

Outcome per proposal: accepted (class deterministic, rubric or human_review; only deterministic is scoring-eligible) or rejected with a category:
  schema_invalid · unknown_persona · unknown_journey · unsupported_attribute · operator_not_applicable · value_not_in_domain · value_type_mismatch ·
  unknown_entity · inconsistent_shape · not_answerable · gate_rejected · duplicate"""
from __future__ import annotations

from dataclasses import dataclass, field

from ...framework.verifiability import HUMAN_REVIEW, RUBRIC, classify, eligible_for_scoring
from ...grading import v2 as grader_v2
from ...grading.key import build_key
from ...investigate.taskgen import criteria as C
from ...investigate.taskgen.gate import Accepted, Draft, evaluate as gate
from ...suite.core import canonical_hash
from . import context as X
from .schema import Proposal

OPS = {"equals": "eq", "contains": "contains", "less_than": "lt", "at_most": "le", "greater_than": "gt", "at_least": "ge"}
NUMERIC_OPS = {"less_than", "at_most", "greater_than", "at_least"}


@dataclass
class Decision:
    index: int
    intent_id: str | None
    outcome: str                         # accepted | rejected
    cls: str | None = None               # deterministic | rubric | human_review (accepted only)
    category: str | None = None          # rejection category
    reasons: list[str] = field(default_factory=list)
    criterion: dict | None = None        # PRIVATE (with the oracle-derived truth below); never shown to an agent or published
    truth: object = None
    complexity: dict = field(default_factory=dict)
    accepted: Accepted | None = None

    @property
    def eligible(self) -> bool:
        return self.outcome == "accepted" and eligible_for_scoring(self.cls or "")

    def public(self) -> dict:
        return {"index": self.index, "intent_id": self.intent_id, "outcome": self.outcome, "class": self.cls, "category": self.category, "reasons": self.reasons,
                "eligible": self.eligible, "criterion_sha256": canonical_hash(self.criterion) if self.criterion else None, "complexity": self.complexity}


def _reject(i, p, category, *reasons):
    return Decision(i, getattr(p, "intent_id", None), "rejected", category=category, reasons=list(reasons))


FRAMINGS = ("raw", "framed")


class Verifier:
    """framing='raw': the agent is given the LLM's scenario as written. framing='framed': the agent is given the scenario followed by a canonical
    statement GENERATED FROM THE VERIFIED CRITERION (framework.generate.phrase), so the question states every field and threshold exactly; the gate
    still checks the final text (an answer leaked in the scenario is still rejected)."""

    def __init__(self, site, catalogue_view: dict, framing: str = "raw"):
        if framing not in FRAMINGS:
            raise ValueError(framing)
        self.framing = framing
        from ...investigate.inspect.profile import build_profile
        self.site, self.view = site, catalogue_view
        self.profiles = {v: build_profile(site.snapshot(v)) for v in site.variants}
        self.base = self.profiles[site.variants[0]]
        self.oracle = site.oracle()
        self.attrs = {a["attribute"]: a for a in catalogue_view["attributes"]}
        self.items = {it["name"].casefold(): it for it in catalogue_view["items"]}
        self.accepted: list[Accepted] = []
        self.seen: set[str] = set()

    def _value_ok(self, attr: dict, op: str, value: str) -> tuple[str | None, str]:
        if attr["kind"] == "text":
            if op in NUMERIC_OPS:
                return "operator_not_applicable", f"{op} on the text attribute {attr['attribute']!r}"
            if op == "equals" and C.norm_answer(value) not in {C.norm_answer(v) for v in attr["values"]}:
                return "value_not_in_domain", f"{value!r} is not a value of {attr['attribute']!r} (known: {', '.join(attr['values'])})"
            return None, ""
        q = C.quantity(value)
        unit_ok = q is not None and ((q[1] == "$") if attr["kind"] == "money" else q[1] in ("", attr["unit"] or "", (attr["unit"] or "").rstrip("s")))
        if not unit_ok:
            return "value_type_mismatch", f"{value!r} is not a {attr['kind']} value in {attr['unit'] or 'plain numbers'}"
        if op not in NUMERIC_OPS and op != "equals":
            return "operator_not_applicable", f"{op} on the numeric attribute {attr['attribute']!r}"
        return None, ""

    def criterion_for(self, p: Proposal) -> tuple[dict | None, str | None, str]:
        listing = self.view["listing"]
        if p.task_type == "lookup":
            if p.constraints or p.ranking or not p.entity or not p.attribute or p.answer_form != "single":
                return None, "inconsistent_shape", "a lookup names one entity and one attribute, has no constraints or ranking, and has a single answer"
            item = self.items.get(p.entity.strip().casefold())
            if item is None:
                return None, "unknown_entity", f"{p.entity!r} is not an item in the catalogue"
            return {"kind": "page_fact", "page": item["page"], "label": p.attribute}, None, ""
        if p.task_type == "filter":
            if not p.constraints or p.ranking or p.answer_form != "list":
                return None, "inconsistent_shape", "a filter has 1-3 constraints, no ranking, and a list answer"
            return {"kind": "item_set", "listing": listing, "conditions": [{"label": c.attribute, "op": OPS[c.operator], "value": c.value} for c in p.constraints]}, None, ""
        if p.task_type == "best":
            if not p.ranking or p.answer_form != "single":
                return None, "inconsistent_shape", "a 'best' task has a ranking and a single answer"
            return {"kind": "extremum", "listing": listing, "label": p.ranking.attribute, "direction": "max" if p.ranking.direction == "highest" else "min"}, None, ""
        return None, None, ""

    def verify(self, index: int, p: Proposal | None, schema_errors: list[str]) -> Decision:
        if p is None:
            return _reject(index, None, "schema_invalid", *schema_errors)
        if p.persona not in {x["id"] for x in X.CONTEXT["personas"]}:
            return _reject(index, p, "unknown_persona", f"{p.persona!r} is not a configured persona")
        if p.journey not in {j["id"] for j in X.CONTEXT["journeys"]}:
            return _reject(index, p, "unknown_journey", f"{p.journey!r} is not a configured journey")
        if p.task_type == "open" or p.answer_form == "explanation":
            on_policy = p.journey == "understand_policies"
            return Decision(index, p.intent_id, "accepted", RUBRIC if on_policy else HUMAN_REVIEW,
                            reasons=["open question about a stated policy: judged against the page's checklist, never scored"] if on_policy
                            else ["open question outside the site's stated policies: needs human review"], complexity={"kind": "open"})
        used = [c.attribute for c in p.constraints] + ([p.ranking.attribute] if p.ranking else []) + ([p.attribute] if p.task_type == "lookup" and p.attribute else [])
        unknown = [a for a in used if a not in self.attrs]
        if unknown:
            return _reject(index, p, "unsupported_attribute", f"not a verified catalogue attribute: {', '.join(unknown)}")
        for c in p.constraints:
            cat, why = self._value_ok(self.attrs[c.attribute], c.operator, c.value)
            if cat:
                return _reject(index, p, cat, why)
        if p.task_type == "best" and p.ranking and self.attrs[p.ranking.attribute]["kind"] == "text":
            return _reject(index, p, "operator_not_applicable", f"cannot rank by the text attribute {p.ranking.attribute!r}")
        if p.task_type == "best" and p.constraints:
            return Decision(index, p.intent_id, "accepted", HUMAN_REVIEW, reasons=["a ranking within a filtered subset is not expressible in the criterion language "
                                                                                     "(no oracle-checked criterion): needs human review"], complexity={"kind": "constrained_best", "conditions": len(p.constraints)})
        crit, cat, why = self.criterion_for(p)
        if cat:
            return _reject(index, p, cat, why)
        try:
            compiled = C.compile_criterion(crit, self.base)
        except C.CriterionError as exc:
            return _reject(index, p, "not_answerable", str(exc))
        h = canonical_hash(crit)
        if h in self.seen:
            return _reject(index, p, "duplicate", "same criterion as an earlier accepted proposal")
        question = self.question(p, crit)
        verdict = gate(Draft(question, self.site.start_path, crit, "llm"), self.base, self.accepted)
        if not isinstance(verdict, Accepted):
            return _reject(index, p, "gate_rejected", verdict.reason)
        stable = all((lambda t: t == compiled.truth)(self._truth(crit, prof)) for prof in self.profiles.values())
        try:
            build_key("p", {"criterion": crit, "truth": compiled.truth}, self.base)
            key_ok = True
        except grader_v2.KeyError_:
            key_ok = False
        ans = self.oracle.answer(crit)
        oracle = ("agrees" if (sorted(ans.truth) if isinstance(ans.truth, list) else ans.truth) == (sorted(compiled.truth) if isinstance(compiled.truth, list) else compiled.truth)
                  else "disagrees") if ans.supported else "declined"
        evidence_ok = bool(compiled.evidence_paths) and all(e in self.base["pages"] for e in compiled.evidence_paths)
        cls, reasons = classify(key_ok=key_ok, stable=stable, oracle=oracle)
        if not evidence_ok:
            cls, reasons = HUMAN_REVIEW, reasons + ["insufficient source evidence pages"]
        self.accepted.append(verdict)
        self.seen.add(h)
        return Decision(index, p.intent_id, "accepted", cls, reasons=reasons + ([f"agent question: {question}"] if self.framing == "framed" else []), criterion=crit, truth=compiled.truth, accepted=verdict,
                        complexity={"kind": crit["kind"], "conditions": len(crit.get("conditions", [])), "min_hops": max(verdict.hops.values(), default=0),
                                    "evidence_pages": len(compiled.evidence_paths), "operators": sorted({c["op"] for c in crit.get("conditions", [])})})

    def question(self, p: Proposal, crit: dict) -> str:
        if self.framing == "raw":
            return p.scenario
        canonical = self.canonical(crit)
        return f"{p.scenario.strip()} Precisely: {canonical}" if canonical else p.scenario

    REL = {"lt": "below", "le": "of at most", "gt": "above", "ge": "of at least"}

    def canonical(self, crit: dict) -> str:
        """A question generated from the verified criterion alone (never from the LLM's wording) that states every field and threshold."""
        from ...framework import generate as G
        if crit["kind"] == "item_set" and len(crit["conditions"]) > 1 and self.site.noun:
            parts = [(f"a {c['label']} {self.REL[c['op']]} {c['value']}" if c["op"] in self.REL else f"{c['label']} '{c['value']}'") for c in crit["conditions"]]
            return f"Which {self.site.noun[1]} have {' and '.join(parts)}? List every one by name."
        return G.phrase(Draft("", self.site.start_path, crit, "llm"), G._restricted(self.base, self.site), self.site).question

    @staticmethod
    def _truth(crit, prof):
        try:
            return C.compile_criterion(crit, prof).truth
        except C.CriterionError:
            return None
