"""taskeval-2: evaluator v2 (versioned; evaluator v1 is reused unchanged and stays the reference).

Layering (never relaxing v1):
  1. evaluator v1 (`taskeval.evaluator.TaskEvaluator`) runs first, unchanged. With the v2 checks disabled, its records are returned as they are
     (exact v1 behaviour). With the checks enabled, each v2 record embeds its v1 record untouched under "v1".
  2. A candidate can be admitted only if every v1 hard gate other than `executable_wording_unambiguous` passed. That gate is about the wording that
     would be executed, and v2 decides which wording is executed:
       natural condition   the customer wording, unchanged. It must pass the v1 acceptance gate EXCEPT the literal field-name rule (length,
                           blindness, compile, stability, yes/no, reachability, start-page leak, answer-in-question and entity naming still apply),
                           which `gate-nl-1` replaces: every value stated, mapping to one attribute domain, intent preserved both ways.
       assisted condition  the v1 restated question (customer wording + a canonical statement generated from the verified criterion), which must
                           pass the full v1 gate (`executable_wording_unambiguous`), labelled assisted, with every generator assumption recorded.
  3. Wording categories (proposal §3.2): natural_verifiable | natural_underspecified | natural_judgment | assisted_restatement. An underspecified
     request is preserved as such (not executed); a labelled assisted derivative may be produced from the generator's stated assumptions.
  4. Coverage (persona x journey x capability), diversity and provisional targets are computed over the admitted tasks (`coverage.py`).

Records contain the criterion (public: labels, operators, thresholds) and, privately, the oracle-derived expected answer; `public()` strips the
answer, internal objects and every evidence page path (for set and ranking tasks those identify answer items). No model is consulted."""
from __future__ import annotations

import hashlib
import json
from contextlib import contextmanager
from pathlib import Path

from ...investigate.taskgen.gate import DUP_JACCARD, Accepted, Draft, _signature as gate_signature, _tokens, evaluate as gate_v1
from ...suite.core import canonical_hash
from .. import evaluator as V1
from . import coverage as COV
from . import lexicon as L
from . import nl as NL

VERSION = "taskeval-2"
# the only v1 acceptance-gate rejections gate-nl-1 replaces (both are the literal field-name requirement); entity naming stays a v1 rule
LITERAL_FIELD_REASONS = ("the question does not state every condition's field and threshold (ambiguous)",
                         "the question does not name the compared field (ambiguous)")
CONFIG = {"nl_gate": NL.GATE_ID, "lexicon": L.VERSION, "assisted_from_generator_assumptions": True, "new_kinds": [],
          "assumption_label": "generator assumption (labelled assisted, not the customer's words)",
          "coverage_targets": {k: (list(v) if isinstance(v, tuple) else v) for k, v in COV.TARGETS.items()}}
ADMISSIONS = ("natural", "assisted", "preserved_unexecuted", "rubric", "human_review", "rejected")
WORDING_GATE = "executable_wording_unambiguous"


def config_fingerprint(config: dict | None = None) -> str:
    h = hashlib.sha256(json.dumps({"config": config or CONFIG, "lexicon": L.snapshot()}, sort_keys=True, default=list).encode())
    here = Path(__file__).parent
    for name in sorted(p.name for p in here.glob("*.py")):
        h.update((here / name).read_bytes())
    h.update(Path(V1.__file__).read_bytes())
    return h.hexdigest()[:16]


@contextmanager
def _v1_grounding_context(context: dict):
    """Evaluator v1's verifier checks persona and journey ids against the module global `research.taskplan.context.CONTEXT` (the synthetic
    Larkspur context), whatever context it is given. v2 supplies the configured context through that global for the duration of the v1 call
    (the identity on Larkspur, so v1 parity is unaffected) and restores it. v1 code is not modified."""
    from ...research.taskplan import context as X
    saved = X.CONTEXT
    X.CONTEXT = context
    try:
        yield
    finally:
        X.CONTEXT = saved


def v1_shape(raw):
    """A taskplan-schema-v3 wire item (strict mode sends `values: null` on plain constraints) in the v1 shape, when it has no one_of constraint.
    The identity on v1-shaped items; one_of items are left as they are (evaluator v1 refuses them; the M2b extension evaluates them)."""
    if not isinstance(raw, dict) or not isinstance(raw.get("constraints"), list):
        return raw
    cs = raw["constraints"]
    if any(isinstance(c, dict) and c.get("operator") == "one_of" for c in cs) or not any(isinstance(c, dict) and "values" in c for c in cs):
        return raw
    return {**raw, "constraints": [{k: v for k, v in c.items() if not (k == "values" and v is None)} if isinstance(c, dict) else c for c in cs]}


V1_PRIMARY_GATE = {"duplicate": "unique", "not_answerable": "answerable", "gate_rejected": "executable_wording_unambiguous", "schema_invalid": "schema_valid",
                   "inconsistent_shape": "expressible", **{c: "grounded" for c in V1.GROUNDING_CATEGORIES}}


def _primary_first(r1: dict) -> list[str]:
    """v1's rejection reasons with the gate that v1's own decision category names first (a duplicate is reported as 'unique', not as the
    downstream 'answerable: failed')."""
    reasons = list(r1["rejection_reasons"])
    gate = V1_PRIMARY_GATE.get((r1.get("decision") or {}).get("category"))
    return sorted(reasons, key=lambda x: not x.startswith(f"{gate}:")) if gate else reasons


def _attrs(crit: dict | None) -> list[str]:
    if not crit:
        return []
    out = {c["label"] for c in crit.get("conditions", [])}
    if "label" in crit:
        out.add(crit["label"])
    return sorted(out)


class TaskEvaluatorV2:
    def __init__(self, site, catalogue_view: dict, context: dict, *, checks: bool = True, config: dict | None = None):
        self.site, self.view, self.context = site, catalogue_view, context
        self.checks = checks
        self.config = {**CONFIG, **(config or {})}
        self.nl = NL.Analyser(catalogue_view)
        self.journeys = {j["id"]: j for j in context["journeys"]}

    @property
    def identity(self) -> dict:
        return {"version": VERSION, "config_fingerprint": config_fingerprint(self.config), "nl_gate": NL.GATE_ID, "lexicon": L.VERSION,
                "v1": {"version": V1.VERSION, "config_fingerprint": V1.config_fingerprint()}, "advisory_llm_judge": None}

    # ------------------------------------------------------------------------------------------------------------------------------ entry
    def evaluate(self, candidates: list[dict]) -> list[dict]:
        """candidates: [{candidate_id, provenance, raw}] in a fixed order. checks=False returns evaluator v1's records exactly."""
        v1 = V1.TaskEvaluator(self.site, self.view, self.context)                   # fresh: the v1 verifiers keep per-batch state
        self.base = v1.framed.base
        self._ext = self._extension(v1)
        if not self.checks:
            return v1.evaluate(candidates)
        candidates = [{**c, "raw": v1_shape(c["raw"])} for c in candidates]
        with _v1_grounding_context(self.context):
            v1_records = v1.evaluate(candidates)
        out: list[dict] = []
        self._natural: list[Accepted] = []
        for cand, r1 in zip(candidates, v1_records):
            out += self._judge(cand, r1)
            if self._ext and r1.get("_accepted") is not None:
                self._ext.prior.append(r1["_accepted"])
        self._soft(out)
        return out

    def _extension(self, v1):
        """M2b hook: new criterion kinds (ranked_subset, either_of) when enabled in the configuration."""
        if not self.config.get("new_kinds"):
            return None
        from .kinds import Extension
        return Extension(self, v1)

    # ------------------------------------------------------------------------------------------------------------------------------ records
    def _record(self, cand, r1, p, *, crit, truth, admission, category, executed, verifiability, gates, reasons, analysis=None, accepted=None,
                assumptions=(), unresolved=(), decisions=(), derived_from=None, suffix="") -> dict:
        customer = getattr(p, "scenario", None) if p is not None else None
        persona, journey = getattr(p, "persona", None), getattr(p, "journey", None)
        attrs = set(_attrs(crit))
        cap = COV.capability(crit, verifiability)
        return {"candidate_id": cand["candidate_id"] + suffix, "derived_from": derived_from, "provenance": cand["provenance"], "index": r1["index"],
                "persona": persona, "journey": journey, "journey_consistent": COV.journey_consistent(self.journeys.get(journey), attrs, verifiability),
                "capability": cap, "kind": (crit or {}).get("kind") or (r1["complexity"] or {}).get("kind"), "attributes": sorted(attrs),
                "wording": {"customer": customer, "executed": executed, "category": category,
                            "condition": {"natural_verifiable": "natural", "natural_judgment": "natural", "assisted_restatement": "assisted"}.get(category),
                            "interpretation_decisions": list(decisions), "assumptions": list(assumptions), "unresolved": list(unresolved)},
                "admission": admission, "verifiability": verifiability, "hard_gates": gates, "rejection_reasons": list(reasons),
                "nl": analysis.as_dict() if analysis else None, "specification": crit, "specification_sha256": canonical_hash(crit) if crit else None,
                "expected_answer": truth, "_accepted": accepted, "hops": (accepted.hops if accepted else {}),
                "v1": {k: v for k, v in r1.items() if k != "_accepted"}, "evaluator": self.identity}

    def _rejected(self, cand, r1, p, reasons, *, crit=None, analysis=None, gates=None, category=None) -> dict:
        return self._record(cand, r1, p, crit=crit, truth=None, admission="rejected", category=category, executed=None, verifiability=None,
                            gates=gates or {k: {"pass": v["pass"]} for k, v in r1["hard_gates"].items()}, reasons=reasons, analysis=analysis)

    # ------------------------------------------------------------------------------------------------------------------------------ judging
    def _judge(self, cand, r1) -> list[dict]:
        from ...research.taskplan.schema import parse_item
        p, _, errors = parse_item(cand["raw"])
        if p is None and self._ext:
            ext = self._ext.judge(cand, r1)
            if ext is not None:
                return ext
        if p is None:
            return [self._rejected(cand, r1, p, r1["rejection_reasons"])]
        dec, kind = r1["decision"], (r1["complexity"] or {}).get("kind")
        customer = p.scenario
        if dec["class"] in ("rubric", "human_review") and kind == "open":
            ver = dec["class"]
            return [self._record(cand, r1, p, crit=None, truth=None, admission=ver, category="natural_judgment", executed=customer, verifiability=ver,
                                 gates={"schema_valid": {"pass": True}, "grounded": {"pass": True}}, reasons=[],
                                 decisions=["open question judged against the page's checklist" if ver == "rubric" else "open question outside stated policies: human review"])]
        if dec["class"] == "human_review" and kind == "constrained_best":
            if self._ext:
                ext = self._ext.judge(cand, r1)
                if ext is not None:
                    return ext
            return [self._rejected(cand, r1, p, ["not_expressible: a ranking within a filtered subset needs the ranked_subset kind (M2b, not enabled)"])]
        crit, truth = r1["specification"], r1["expected_answer"]
        failed = [k for k, g in r1["hard_gates"].items() if k != WORDING_GATE and not g["pass"]]
        if crit is None or failed:
            return [self._rejected(cand, r1, p, _primary_first(r1) or ["no verifiable specification"], crit=crit)]
        analysis = self.nl.analyse(customer, crit)
        return self._admit(cand, r1, p, crit, truth, analysis, r1["_accepted"], r1["hard_gates"])

    def _admit(self, cand, r1, p, crit, truth, analysis, framed: Accepted | None, gates: dict) -> list[dict]:
        """Shared by v1 kinds and the M2b kinds. `gates`: the v1-named hard gates (all non-wording gates passed); `framed`: the accepted assisted
        (restated) task, None if the restated wording failed the acceptance gate."""
        customer = p.scenario
        verdict = analysis.verdict()
        base_gates = {k: {"pass": v["pass"]} for k, v in gates.items() if k != WORDING_GATE}
        framed_pass = gates[WORDING_GATE]["pass"] and framed is not None
        intent = {"pass": not analysis.intent_violations, "evidence": analysis.intent_violations}
        if verdict == "intent_not_preserved":
            return [self._rejected(cand, r1, p, [f"intent_not_preserved: {v}" for v in analysis.intent_violations], crit=crit, analysis=analysis,
                                   gates={**base_gates, "intent_preserved": intent})]
        if verdict == "verifiable":
            ok, why, acc = self._natural_gate(customer, crit, framed)
            gates = {**base_gates, "natural_wording_gate": {"pass": ok, "evidence": why}, "intent_preserved": intent}
            if not ok:
                return [self._rejected(cand, r1, p, [f"natural_wording_gate: {w}" for w in why], crit=crit, analysis=analysis, gates=gates)]
            self._natural.append(acc)
            return [self._record(cand, r1, p, crit=crit, truth=truth, admission="natural", category="natural_verifiable", executed=customer,
                                 verifiability="deterministic", gates=gates, reasons=[], analysis=analysis, accepted=acc, decisions=analysis.decisions + why)]
        restated = framed.draft.question if framed is not None else None
        assisted_gates = {**base_gates, WORDING_GATE: {"pass": framed_pass}, "intent_preserved": intent}
        if verdict == "assisted_only":
            if not framed_pass:
                return [self._rejected(cand, r1, p, ["executable_wording_unambiguous: the restated wording fails the acceptance gate"], crit=crit, analysis=analysis,
                                       gates=assisted_gates)]
            return [self._record(cand, r1, p, crit=crit, truth=truth, admission="assisted", category="assisted_restatement", executed=restated,
                                 verifiability="deterministic", gates=assisted_gates, reasons=[], analysis=analysis, accepted=framed,
                                 assumptions=analysis.assumptions, decisions=analysis.decisions)]
        # underspecified: preserve the customer's request as it is (never executed, never given an invented value)
        out = [self._record(cand, r1, p, crit=crit, truth=None, admission="preserved_unexecuted", category="natural_underspecified", executed=None,
                            verifiability="human_review", gates={**base_gates, "intent_preserved": intent}, reasons=[], analysis=analysis,
                            unresolved=analysis.unresolved, decisions=analysis.decisions)]
        if self.config["assisted_from_generator_assumptions"] and framed_pass:
            out.append(self._record(cand, r1, p, crit=crit, truth=truth, admission="assisted", category="assisted_restatement", executed=restated,
                                    verifiability="deterministic", gates=assisted_gates, reasons=[], analysis=analysis, accepted=framed,
                                    assumptions=[f"{self.config['assumption_label']}: {a}" for a in analysis.unresolved]
                                    + [a for a in analysis.assumptions if a not in analysis.unresolved],
                                    decisions=analysis.decisions, derived_from=cand["candidate_id"], suffix="~assisted"))
        return out

    def _natural_gate(self, customer: str, crit: dict, framed: Accepted | None) -> tuple[bool, list[str], Accepted | None]:
        """The v1 acceptance gate on the CUSTOMER wording with only its literal field-name rule replaced by gate-nl-1 (already passed by the
        caller). Rejections the gate makes before that rule (leaks, length, reachability, ...) and the entity-naming rule are kept."""
        start = self.site.start_path
        draft = Draft(customer, start, crit, "llm")
        v = self._gate(draft)
        if isinstance(v, Accepted):
            acc, why = v, ["v1 acceptance gate passed on the customer wording (fields named literally)"]
        elif v.reason in LITERAL_FIELD_REASONS:
            if framed is None:
                return False, ["no verified specification to execute"], None
            acc = Accepted(draft, framed.compiled, framed.criterion, gate_signature(framed.criterion, start), dict(framed.hops), list(framed.tags))
            why = [f"v1 literal field-name rule ('{v.reason}') replaced by {NL.GATE_ID}; every other v1 gate rule passed on the customer wording"]
        else:
            return False, [v.reason], None
        for a in self._natural:
            ta, tb = _tokens(a.draft.question), _tokens(customer)
            if ta and tb and len(ta & tb) / len(ta | tb) >= DUP_JACCARD and a.compiled.truth == acc.compiled.truth:
                return False, ["near-duplicate wording of an admitted natural task with the same answer"], None
        return True, why, acc

    def _gate(self, draft: Draft):
        if self._ext:
            return self._ext.gate(draft)
        return gate_v1(draft, self.base, [])

    # ------------------------------------------------------------------------------------------------------------------------------ soft
    def _soft(self, records: list[dict]) -> None:
        admitted = [r for r in records if r["admission"] in ("natural", "assisted")]
        w = V1.CONFIG["weights"]
        for r in records:
            v1soft = dict(r["v1"].get("soft") or {})
            sims = [COV.similarity(r["specification"], o["specification"]) for o in admitted if o is not r and r["specification"] and o.get("derived_from") != r["candidate_id"]
                    and r.get("derived_from") != o["candidate_id"]]
            top = max(sims, default=0.0)
            v1soft["novelty"] = round(1 - top, 3)
            v1soft["natural_wording"] = 1.0 if r["admission"] == "natural" else 0.0
            r["soft"] = v1soft
            r["near_duplicate"] = top >= COV.TARGETS["max_pair_similarity"]
            vals = {k: (v1soft.get(k) if v1soft.get(k) is not None else 0.0) for k in w}
            r["quality"] = round(sum(w[k] * vals[k] for k in w), 3) if r in admitted else None


# ------------------------------------------------------------------------------------------------------------------------------- views
def public(record: dict) -> dict:
    """Shareable: no expected answer, no internal objects, no evidence page paths (for set and ranking tasks they identify answer items)."""
    if "v1" not in record:                                           # a v1 record (checks disabled): the v1 public view
        return V1.public(record)
    v1 = record["v1"]
    out = {k: v for k, v in record.items() if k not in ("expected_answer", "_accepted", "v1", "hops")}
    out["hard_gates"] = {k: {"pass": g["pass"], **({"evidence": g["evidence"]} if k in ("natural_wording_gate", "intent_preserved") and g.get("evidence") else {})}
                         for k, g in record["hard_gates"].items()}
    out["v1"] = {"hard_pass": v1.get("hard_pass"), "decision": v1.get("decision"), "natural_wording_passes_gate": v1.get("natural_wording_passes_gate"),
                 "evidence_pages": len(v1.get("evidence_refs") or [])}
    out["min_hops"] = max(record["hops"].values(), default=0) if record.get("hops") else None
    return out


def distribution(records: list[dict]) -> dict:
    """Category and admission counts over the ORIGINAL candidates (derived assisted records are counted separately)."""
    base = [r for r in records if not r.get("derived_from")]
    cats: dict[str, int] = {}
    adm: dict[str, int] = {}
    for r in base:
        c = r["wording"]["category"] or "none (rejected before classification)"
        cats[c] = cats.get(c, 0) + 1
        adm[r["admission"]] = adm.get(r["admission"], 0) + 1
    derived = [r for r in records if r.get("derived_from")]
    return {"candidates": len(base), "categories": dict(sorted(cats.items())), "admissions": dict(sorted(adm.items())),
            "assisted_derivatives": len(derived), "executable_natural": adm.get("natural", 0),
            "executable_assisted": adm.get("assisted", 0) + len(derived)}


def coverage(records: list[dict], context: dict, targets: dict | None = None) -> dict:
    tasks = [{"id": r["candidate_id"], "persona": r["persona"], "journey": r["journey"], "capability": r["capability"], "condition": r["wording"]["condition"],
              "verifiability": r["verifiability"], "criterion": r["specification"], "attributes": r["attributes"]}
             for r in records if r["admission"] in ("natural", "assisted", "rubric")]
    return COV.report(tasks, context, targets)
