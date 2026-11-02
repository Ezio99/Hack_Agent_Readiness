"""Lifecycle M2b: two new criterion kinds, with independent oracle, acceptance gate, grader v1 and grader v2 support.

  ranked_subset   items of a listing that satisfy 1-3 conditions, then the one with the highest / lowest numeric fact ("the cheapest beginner
                  course"). Refused when the filter selects every item (that is an extremum) or fewer than 2, or the extreme value is tied.
  either_of       items whose text fact equals ANY of 2-4 alternatives ("on Saturday or Sunday"), optionally AND 0-2 further conditions. Refused
                  when it selects none or all, or when an alternative contributes no item (a degenerate either/or would not exercise OR).

Additive only. The shared engine (`criteria.py`, `gate.py`, `grading/key.py`, `framework/oracle.py`) is NOT modified: every function here
handles the two new kinds and DELEGATES every existing kind to the unchanged v1 code (`compile_any`, `oracle_answer`, `gate`, `build_key_any`).
So frozen experiments, the hosted path and grader v1/v2 behave byte-identically, and the v1 gate still refuses the new kinds as malformed.

Expected answers come only from the frozen snapshot (compile) and the site's source records (oracle), which must agree; an LLM never supplies one.
Grading reuses the unchanged graders: grader v1 (`criteria.grade`) grades the compiled truth (string or set style); grader v2 grades against a
key built with the same extractors (`build_key_any`)."""
from __future__ import annotations

from dataclasses import replace
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from ...framework.oracle import OracleAnswer, RecordOracle
from ...grading import key as GK
from ...grading import v2 as G2
from ...investigate.taskgen import criteria as C
from ...investigate.taskgen.gate import (DUP_JACCARD, FIRST_PAGE_TAG, MAX_HOPS, MIN_QUESTION_CHARS, YES_NO, Accepted, Draft, Rejected,
                                         _entity_tokens, _signature, _tokens, hop_distances)
from ...investigate.taskgen.gate import evaluate as gate_v1
from ...investigate.zoo.sealed import BlindnessError, assert_blind
from ...suite.core import canonical_hash

KINDS = ("ranked_subset", "either_of")
FIELD_REASON = "the question does not state every condition's field and threshold (ambiguous)"
COMPARED_REASON = "the question does not name the compared field (ambiguous)"
REL = {"lt": "below", "le": "of at most", "gt": "above", "ge": "of at least"}


class RankedSubset(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["ranked_subset"] = "ranked_subset"
    listing: str
    conditions: list[C.Condition] = Field(min_length=1, max_length=3)
    label: str = Field(min_length=1, max_length=40)
    direction: Literal["max", "min"]


class EitherOf(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["either_of"] = "either_of"
    listing: str
    label: str = Field(min_length=1, max_length=40)
    values: list[str] = Field(min_length=2, max_length=4)
    conditions: list[C.Condition] = Field(default_factory=list, max_length=2)

    @model_validator(mode="after")
    def _distinct(self):
        if len({C.norm_answer(v) for v in self.values}) != len(self.values):
            raise ValueError("either_of alternatives must be distinct")
        if any(c.label == self.label for c in self.conditions):
            raise ValueError("a further condition may not constrain the either/or attribute again")
        return self


# ------------------------------------------------------------------------------------------------------------------------------- compile
def _model(c: dict):
    try:
        return RankedSubset.model_validate(c) if c.get("kind") == "ranked_subset" else EitherOf.model_validate(c)
    except ValidationError as exc:
        raise C.CriterionError(f"malformed {c.get('kind')} criterion ({exc.error_count()} error(s))") from exc


def _one(profile: dict, it: dict, label: str) -> str:
    vals = C._fact(profile["pages"][it["href"]], label)
    if len(vals) != 1:
        raise C.CriterionError(f"item {it['name']!r}: fact {label!r} missing or ambiguous on its page")
    return vals[0]


def compile_ext(c: dict, profile: dict) -> C.Compiled:
    m = _model(c)
    if isinstance(m, RankedSubset):
        items = C._items(profile, m.listing, tuple(x.label for x in m.conditions) + (m.label,))
        hit = []
        for it in items:
            seen = [_one(profile, it, x.label) for x in m.conditions]
            if all(C._op(x, v) for x, v in zip(m.conditions, seen)):
                hit.append((it, seen))
        if len(hit) == len(items):
            raise C.CriterionError("the filter selects every item; that is an extremum, not a ranking within a filter")
        if len(hit) < 2:
            raise C.CriterionError(f"the filter selects {len(hit)} item(s); a ranking within a filter needs at least 2")
        vals = []
        for it, seen in hit:
            raw = _one(profile, it, m.label)
            q = C.quantity(raw)
            if q is None:
                raise C.CriterionError(f"item {it['name']!r}: fact {m.label!r} is not numeric")
            vals.append((q, it, seen + [raw]))
        if len({q[1] for q, _, _ in vals}) != 1:
            raise C.CriterionError("values are not comparable (mixed units)")
        ranked = sorted(vals, key=lambda x: x[0][0], reverse=(m.direction == "max"))
        if ranked[0][0][0] == ranked[1][0][0]:
            raise C.CriterionError("the extreme value within the filter is tied; the answer would be ambiguous")
        _, win, decisive = ranked[0]
        need = [win["href"]] if any(C._needs_detail(win, v) for v in decisive) else []
        return C.Compiled("ranked_subset", "string", win["name"], [m.listing] + need, [(None, win["name"])], [m.listing],
                          {"items": len(items), "subset": len(hit), "detail_visits_required": len(need)}, distractors=sorted({i["name"] for i in items} - {win["name"]}))
    items = C._items(profile, m.listing, (m.label,) + tuple(x.label for x in m.conditions))
    want = {C.norm_answer(v): v for v in m.values}
    present = {C.norm_answer(_one(profile, it, m.label)) for it in items}
    absent = [v for n, v in want.items() if n not in present]
    if absent:
        raise C.CriterionError(f"alternative(s) {', '.join(map(repr, absent))} are not a value of {m.label!r} on any listed item")
    hit, need, contributed = [], [], set()
    for it in items:
        v = _one(profile, it, m.label)
        seen = [v] + [_one(profile, it, x.label) for x in m.conditions]
        if C.norm_answer(v) in want and all(C._op(x, s) for x, s in zip(m.conditions, seen[1:])):
            hit.append(it)
            contributed.add(C.norm_answer(v))
            if any(C._needs_detail(it, s) for s in seen):
                need.append(it["href"])
    if not 1 <= len(hit) <= len(items) - 1:
        raise C.CriterionError(f"criterion selects {len(hit)} of {len(items)} items; it must select some but not all")
    idle = [v for n, v in want.items() if n not in contributed]
    if idle:
        raise C.CriterionError(f"alternative(s) {', '.join(map(repr, idle))} select no item under the other conditions (a degenerate either/or)")
    return C.Compiled("either_of", "set", sorted(i["name"] for i in hit), [m.listing] + need, [(None, i["name"]) for i in hit], [m.listing],
                      {"items": len(items), "selected": len(hit), "detail_visits_required": len(need)})


def compile_any(c, profile: dict) -> C.Compiled:
    """compile_criterion for every kind: the new kinds here, every existing kind through the unchanged v1 function."""
    if isinstance(c, dict) and c.get("kind") in KINDS:
        return compile_ext(c, profile)
    return C.compile_criterion(c, profile)


# ------------------------------------------------------------------------------------------------------------------------------- oracle
def oracle_answer(oracle: RecordOracle, crit: dict) -> OracleAnswer:
    """Answer from the site's SOURCE RECORDS (never its pages). The well-posedness refusals mirror compile_ext, as v1 mirrors extremum ties."""
    kind = crit.get("kind")
    if kind not in KINDS:
        return oracle.answer(crit)
    recs = oracle.listings.get(crit.get("listing"))
    if not recs:
        return OracleAnswer(False, reason="the listing is not described by the source data")

    def holds(r, c):
        f = oracle._field(c["label"])
        if f is None or f.name not in r.values:
            return None
        return oracle._holds(f, r.values[f.name], c["op"], c["value"])

    conds = crit.get("conditions", [])
    sub = []
    for r in recs:
        hs = [holds(r, c) for c in conds]
        if any(h is None for h in hs):
            return OracleAnswer(False, reason="a condition is not comparable in the source data")
        if all(hs):
            sub.append(r)
    f = oracle._field(crit["label"])
    if f is None:
        return OracleAnswer(False, reason=f"field {crit['label']!r} is not in the source data")
    if kind == "ranked_subset":
        if len(sub) == len(recs) or len(sub) < 2:
            return OracleAnswer(False, reason="the filter selects every item or fewer than 2")
        vals = [(oracle._numeric(f, r.values.get(f.name)), r.name) for r in sub]
        if any(v is None for v, _ in vals):
            return OracleAnswer(False, reason="field missing or not numeric in the source data")
        ranked = sorted(vals, key=lambda x: x[0], reverse=crit["direction"] == "max")
        if ranked[0][0] == ranked[1][0]:
            return OracleAnswer(False, reason="tied extreme within the filter in the source data")
        return OracleAnswer(True, ranked[0][1])
    alts = crit["values"]
    if any(not any(oracle._holds(f, r.values.get(f.name), "eq", v) for r in recs if f.name in r.values) for v in alts):
        return OracleAnswer(False, reason="an alternative is not a value in the source data")
    hits = [r for r in sub if f.name in r.values and any(oracle._holds(f, r.values[f.name], "eq", v) for v in alts)]
    if not 1 <= len(hits) <= len(recs) - 1 or any(not any(oracle._holds(f, r.values[f.name], "eq", v) for r in hits) for v in alts):
        return OracleAnswer(False, reason="degenerate either/or in the source data")
    return OracleAnswer(True, sorted(r.name for r in hits))


# ------------------------------------------------------------------------------------------------------------------------------- grader v2 key
def build_key_any(task_id: str, priv: dict, profile: dict) -> G2.AnswerKey:
    crit = priv["criterion"]
    if crit.get("kind") not in KINDS:
        return GK.build_key(task_id, priv, profile)
    try:
        compiled = compile_ext(crit, profile)
    except C.CriterionError as exc:
        raise G2.KeyError_(f"{task_id}: criterion no longer compiles against the frozen profile ({exc})") from exc
    if compiled.truth != priv["truth"]:
        raise G2.KeyError_(f"{task_id}: the re-derived truth differs from the frozen truth")
    labels = tuple(c["label"] for c in crit.get("conditions", [])) + (crit["label"],)
    items = C._items(profile, crit["listing"], labels)
    cands = [G2.Candidate(i["name"], GK._page_facts(profile["pages"][i["href"]])) for i in items]
    context = {(False, float(len(items)))}
    for c in crit.get("conditions", []):
        context |= G2.numbers(c["value"])
    all_labels = tuple(sorted({label for c in cands for label, _ in c.facts}))
    return G2.AnswerKey(task_id, crit["kind"], compiled.style, compiled.truth, cands, context, crit.get("direction"), all_labels)


# ------------------------------------------------------------------------------------------------------------------------------- acceptance gate
def gate(draft: Draft, profile: dict, accepted: list[Accepted], *, first_page: str = "reject") -> Accepted | Rejected:
    """The acceptance gate for every kind: existing kinds go to the UNCHANGED v1 gate; the new kinds to `gate_replica`."""
    if draft.criterion.get("kind") in KINDS:
        return gate_replica(draft, profile, accepted, first_page=first_page)
    return gate_v1(draft, profile, accepted, first_page=first_page)


def gate_replica(draft: Draft, profile: dict, accepted: list[Accepted], *, first_page: str = "reject") -> Accepted | Rejected:
    """A rule-for-rule replica of `gate.evaluate` over `compile_any`, with ambiguity rules for the new kinds. For existing kinds it must return
    exactly what the v1 gate returns (tested on a corpus); it is USED only for the new kinds."""
    from ...investigate.taskgen.criteria import norm_answer, resolve_target
    proposed = draft

    def no(reason):
        return Rejected(proposed, reason)
    q = draft.question.strip()
    if len(q) < MIN_QUESTION_CHARS or len(q) > 400:
        return no("question length is outside 20-400 characters")
    try:
        assert_blind(q)
    except BlindnessError:
        return no("question text would reveal a protected diagnosis")
    if draft.criterion.get("kind") == "reach_page" and isinstance(draft.criterion.get("target"), str):
        try:
            draft = replace(draft, criterion={**draft.criterion, "target": resolve_target(profile, draft.criterion["target"])})
        except C.CriterionError as exc:
            return no(f"criterion does not compile: {exc}")
    try:
        crit = compile_any(draft.criterion, profile)
        again = compile_any(draft.criterion, profile)
    except C.CriterionError as exc:
        return no(f"criterion does not compile: {exc}")
    except Exception as exc:
        return no(f"criterion is malformed ({type(exc).__name__})")
    if crit.truth != again.truth:
        return no("expected answer is not stable under re-extraction")
    if draft.start_path not in profile["pages"]:
        return no("start page is not part of the snapshot")
    truths = [crit.truth] if isinstance(crit.truth, str) else list(crit.truth)
    if any(norm_answer(t) in YES_NO for t in truths):
        return no("yes/no answers are not accepted (guessable)")
    dist = hop_distances(profile, draft.start_path)
    missing = [p for p in crit.evidence_paths if p not in dist]
    if missing:
        return no(f"evidence page(s) not reachable by links from the start page: {missing[:3]}")
    if any(dist[p] == 0 for p in crit.evidence_paths) and crit.kind in ("page_fact", "reach_page"):
        return no("the answer is on the start page itself (derivable from the first observation)")
    far = max((dist[p] for p in crit.evidence_paths), default=0)
    if far > MAX_HOPS:
        return no(f"evidence is {far} link steps away (limit {MAX_HOPS})")
    if far < 1:
        return no("no navigation is needed")
    qn = norm_answer(q)
    if any(norm_answer(t) in qn for t in truths if len(norm_answer(t)) >= 3):
        return no("the question contains the expected answer")
    start_text = norm_answer(profile["pages"][draft.start_path]["text"] + " " + profile["pages"][draft.start_path]["title"])
    tags: list[str] = []
    if crit.style == "string" and norm_answer(crit.truth) in start_text and crit.kind not in ("extremum", "ranked_subset"):   # naming listed items is not the answer
        if first_page != "tag":
            return no("the expected answer is visible on the start page")
        tags.append(FIRST_PAGE_TAG)
    c = draft.criterion
    if c["kind"] == "page_fact":
        ent = _entity_tokens(profile, c["page"])
        if ent and not (ent & _tokens(q)):
            return no("the question does not name the page/entity it asks about (ambiguous)")
    if c["kind"] in ("item_set", "ranked_subset", "either_of"):
        for cond in c.get("conditions", []):
            if norm_answer(cond["value"]) not in qn or not (_tokens(cond["label"]) & _tokens(q)):
                return no(FIELD_REASON)
    if c["kind"] == "either_of" and (not (_tokens(c["label"]) & _tokens(q)) or any(norm_answer(v) not in qn for v in c["values"])):
        return no(FIELD_REASON)
    if c["kind"] in ("extremum", "ranked_subset") and not (_tokens(c["label"]) & _tokens(q)):
        return no(COMPARED_REASON)
    if c["kind"] == "term_value":
        tt, lt = _tokens(c["term"]), _tokens(c["label"])
        if not tt or not tt <= _tokens(q):
            return no("the question does not name the term it asks about (ambiguous)")
        if not lt or not (lt & _tokens(q)):
            return no("the question does not name the field asked for (ambiguous)")
    if c["kind"] == "reach_page" and (_tokens(profile["pages"][c["target"]]["title"]) and _tokens(profile["pages"][c["target"]]["title"]) <= _tokens(q)):
        return no("the question contains the target page's title")
    sig = _signature(draft.criterion, draft.start_path)
    for a in accepted:
        if a.fingerprint == sig:
            return no("duplicate of an accepted task (same criterion and start page)")
        ta, tb = _tokens(a.draft.question), _tokens(q)
        if ta and tb and len(ta & tb) / len(ta | tb) >= DUP_JACCARD and a.compiled.truth == crit.truth:
            return no("near-duplicate wording of an accepted task with the same answer")
    return Accepted(proposed, crit, draft.criterion, sig, {p: dist[p] for p in crit.evidence_paths}, tags)


def canonical(crit: dict, noun: tuple[str, str] | None) -> str:
    """The restated (assisted) question generated from the verified criterion alone: it states every field, threshold and alternative."""
    one, many = noun or ("item", "items")
    parts = [(f"a {c['label']} {REL[c['op']]} {c['value']}" if c["op"] in REL else f"{c['label']} '{c['value']}'") for c in crit.get("conditions", [])]
    if crit["kind"] == "ranked_subset":
        return f"Among the {many} with {' and '.join(parts)}, which {one} has the {'highest' if crit['direction'] == 'max' else 'lowest'} {crit['label']}? Give its name."
    alts = " or ".join(f"'{v}'" for v in crit["values"])
    return f"Which {many} have {crit['label']} {alts}{' and ' + ' and '.join(parts) if parts else ''}? List every one by name."


# ------------------------------------------------------------------------------------------------------------------------------- evaluator extension
GROUNDING = ("unknown_persona", "unknown_journey", "unsupported_attribute", "operator_not_applicable", "value_not_in_domain", "value_type_mismatch")


class Extension:
    """Evaluates proposals whose intent needs a new kind (a 'best' task with constraints; a filter with one one_of constraint), with the same hard
    gates as evaluator v1 (same names), then hands them to evaluator v2's shared admission (natural / assisted / underspecified)."""

    def __init__(self, ev, v1):
        self.ev, self.site, self.view = ev, ev.site, ev.view
        self.framed = v1.framed                                   # the v1 framed verifier: profiles, base profile, oracle, accepted tasks
        self.base, self.profiles, self.oracle = v1.framed.base, v1.framed.profiles, v1.framed.oracle
        self.accepted: list[Accepted] = []
        self.seen: set[str] = set()
        self.prior: list[Accepted] = []                           # v1-accepted tasks of EARLIER candidates only (so a later candidate never changes an earlier record)
        self.enabled = set(ev.config.get("new_kinds") or ())

    def gate(self, draft: Draft):
        return gate(draft, self.base, [])

    def _criterion(self, p) -> tuple[dict | None, str | None, str]:
        listing = self.view["listing"]
        attrs = self.framed.attrs
        ones = [c for c in p.constraints if c.operator == "one_of"]
        plain = [c for c in p.constraints if c.operator != "one_of"]
        used = [c.attribute for c in p.constraints] + ([p.ranking.attribute] if p.ranking else [])
        unknown = [a for a in used if a not in attrs]
        if unknown:
            return None, "unsupported_attribute", f"not a verified catalogue attribute: {', '.join(unknown)}"
        for c in plain:
            cat, why = self.framed._value_ok(attrs[c.attribute], c.operator, c.value)
            if cat:
                return None, cat, why
        for c in ones:
            if attrs[c.attribute]["kind"] != "text":
                return None, "operator_not_applicable", f"one_of on the numeric attribute {c.attribute!r}"
            for v in c.values:
                cat, why = self.framed._value_ok(attrs[c.attribute], "equals", v)
                if cat:
                    return None, cat, why
        from ...research.taskplan.verify import OPS
        conds = [{"label": c.attribute, "op": OPS[c.operator], "value": c.value} for c in plain]
        if p.task_type == "best" and p.ranking and plain and not ones and p.answer_form == "single" and "ranked_subset" in self.enabled:
            if attrs[p.ranking.attribute]["kind"] == "text":
                return None, "operator_not_applicable", f"cannot rank by the text attribute {p.ranking.attribute!r}"
            return {"kind": "ranked_subset", "listing": listing, "conditions": conds, "label": p.ranking.attribute,
                    "direction": "max" if p.ranking.direction == "highest" else "min"}, None, ""
        if p.task_type == "filter" and len(ones) == 1 and not p.ranking and p.answer_form == "list" and "either_of" in self.enabled:
            return {"kind": "either_of", "listing": listing, "label": ones[0].attribute, "values": list(ones[0].values), "conditions": conds}, None, ""
        return None, "not_applicable", ""

    def judge(self, cand: dict, r1: dict) -> list[dict] | None:
        from ...research.taskplan.schema_v3 import parse_item_v3
        p, stripped, errors = parse_item_v3(cand["raw"])
        if p is None:
            return None
        ids = {x["id"] for x in self.ev.context["personas"]}
        crit, cat, why = self._criterion(p)
        if cat == "not_applicable":
            return None
        gates = {"schema_valid": {"pass": True, "evidence": []}}
        if p.persona not in ids or p.journey not in {j["id"] for j in self.ev.context["journeys"]}:
            cat, why = ("unknown_persona", f"{p.persona!r} is not a configured persona") if p.persona not in ids else ("unknown_journey", f"{p.journey!r} is not a configured journey")
        if cat:
            gates["grounded"] = {"pass": False, "evidence": [why]}
            return [self.ev._rejected(cand, r1, p, [f"grounded: {why}" if cat in GROUNDING else f"{cat}: {why}"], gates=gates)]
        gates["grounded"] = {"pass": True, "evidence": []}
        gates["expressible"] = {"pass": True, "evidence": [f"{crit['kind']} (M2b)"]}
        try:
            comp = compile_ext(crit, self.base)
        except C.CriterionError as exc:
            gates["answerable"] = {"pass": False, "evidence": [str(exc)]}
            return [self.ev._rejected(cand, r1, p, [f"answerable: {exc}"], crit=crit, gates=gates)]
        gates["answerable"] = {"pass": True, "evidence": []}
        h = canonical_hash(crit)
        dup = h in self.seen or h in {canonical_hash(a.criterion) for a in self.prior}
        gates["unique"] = {"pass": not dup, "evidence": ["same criterion as an earlier accepted proposal"] if dup else []}
        restated = f"{p.scenario.strip()} Precisely: {canonical(crit, self.site.noun)}"
        verdict = gate(Draft(restated, self.site.start_path, crit, "llm"), self.base, self.prior + self.accepted)
        framed = verdict if isinstance(verdict, Accepted) else None
        gates["executable_wording_unambiguous"] = {"pass": framed is not None, "evidence": [] if framed else [verdict.reason]}
        ans = oracle_answer(self.oracle, crit)
        norm = lambda x: sorted(x) if isinstance(x, list) else x
        gates["oracle_agrees"] = {"pass": ans.supported and norm(ans.truth) == norm(comp.truth), "evidence": [self.oracle.label] + ([ans.reason] if not ans.supported else [])}
        wrong = ["Nothing"] if comp.style == "set" else "Nothing"
        gates["grader_v1_compatible"] = {"pass": C.grade(comp, comp.truth)[0] and not C.grade(comp, wrong)[0], "evidence": ["generated-criteria v1"]}
        try:
            key = build_key_any("c", {"criterion": crit, "truth": comp.truth}, self.base)
            v2ok = G2.grade(key, comp.truth).passed and not G2.grade(key, wrong).passed
        except G2.KeyError_:
            v2ok = False
        gates["grader_v2_compatible"] = {"pass": v2ok, "evidence": [f"generated-criteria v2 {G2.code_sha256()[:12]} (key: kinds.build_key_any)"]}
        fair = {}
        for v, prof in self.profiles.items():
            try:
                cv = compile_ext(crit, prof)
                fair[v] = cv.truth == comp.truth and all(e in prof["pages"] for e in cv.evidence_paths)
            except C.CriterionError:
                fair[v] = False
        gates["cross_version_fair"] = {"pass": all(fair.values()), "evidence": [str(fair)]}
        gates["evidence_sufficient"] = {"pass": bool(comp.evidence_paths) and all(e in self.base["pages"] for e in comp.evidence_paths), "evidence": []}
        failed = [k for k, g in gates.items() if k != "executable_wording_unambiguous" and not g["pass"]]
        if failed:
            return [self.ev._rejected(cand, r1, p, [f"{k}: {'; '.join(gates[k]['evidence']) or 'failed'}" for k in failed], crit=crit, gates=gates)]
        if framed is not None:
            self.accepted.append(framed)
        self.seen.add(h)
        analysis = self.ev.nl.analyse(p.scenario, crit)
        return self.ev._admit(cand, r1, p, crit, comp.truth, analysis, framed, gates)


# ------------------------------------------------------------------------------------------------------------------------------- instance generation
def enumerate_instances(view: dict) -> list[dict]:
    """Systematic ranked_subset and either_of criteria from a catalogue view's attribute domains (for oracle/compile agreement checks)."""
    listing = view["listing"]
    text = [(a["attribute"], a["values"]) for a in view["attributes"] if a["kind"] == "text"]
    num = [a for a in view["attributes"] if a["kind"] != "text"]
    shown = {a["attribute"]: sorted({it[a["attribute"]] for it in view["items"] if a["attribute"] in it}, key=lambda s: C.quantity(s)[0]) for a in num}
    out = []
    for label, values in text:
        for v in values:
            for a in num:
                for d in ("max", "min"):
                    out.append({"kind": "ranked_subset", "listing": listing, "conditions": [{"label": label, "op": "eq", "value": v}], "label": a["attribute"], "direction": d})
    for a in num:
        for t in shown[a["attribute"]]:
            for b in num:
                if b is not a:
                    out.append({"kind": "ranked_subset", "listing": listing, "conditions": [{"label": a["attribute"], "op": "le", "value": t}], "label": b["attribute"], "direction": "min"})
    for label, values in text:
        pairs = [(x, y) for i, x in enumerate(values) for y in values[i + 1:]]
        for x, y in pairs:
            out.append({"kind": "either_of", "listing": listing, "label": label, "values": [x, y], "conditions": []})
            for l2, v2 in text:
                if l2 != label:
                    for w in v2:
                        out.append({"kind": "either_of", "listing": listing, "label": label, "values": [x, y], "conditions": [{"label": l2, "op": "eq", "value": w}]})
    return out
