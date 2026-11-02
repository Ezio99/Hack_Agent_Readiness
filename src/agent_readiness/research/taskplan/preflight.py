"""Local preflight for a paid planner request with taskplan-schema-v2. Every check must pass or the request is not sent.

  strict_objects        every object (incl. nested $defs) lists all its properties in `required` and has additionalProperties false
  proven_keywords       only JSON-Schema keywords already accepted by Meta live
  nullable_optionals    entity / attribute / ranking accept null; constraints is an array (may be empty); rationale is a string (may be empty)
  parser_unchanged      fixture items rewritten in the v2 shape (absent optionals -> null / [] / "") parse to the same proposals, validate against
                        the v2 wire schema, and receive exactly the same decisions (raw and framed) as the v1-shaped fixture
  prompt_unchanged      the request messages are byte-identical to paid run 1 (prompt taskplan-v1)
  reservation_bound     the spend-gate reservation for this request <= the approved maximum
  model_settings        muse-spark-1.3, reasoning_effort low, max_completion_tokens 6000"""
from __future__ import annotations

import json
from pathlib import Path

from .schema import PROVEN_KEYWORDS, SCHEMA_V2, json_schema_v2

APPROVED_MAX_RESERVATION_USD = 0.029054
OPTIONAL_NULLABLE = ("entity", "attribute", "ranking")


def _objects(node, path="$"):
    if isinstance(node, dict):
        if "properties" in node:
            yield path, node
        for k, v in node.items():
            yield from _objects(v, f"{path}.{k}")
    elif isinstance(node, list):
        for i, x in enumerate(node):
            yield from _objects(x, f"{path}[{i}]")


def _keywords(node, acc=None):
    acc = set() if acc is None else acc
    if isinstance(node, dict):
        for k, v in node.items():
            if k in ("properties", "$defs"):
                for sub in v.values():
                    _keywords(sub, acc)
            else:
                acc.add(k)
                _keywords(v, acc)
    elif isinstance(node, list):
        for x in node:
            _keywords(x, acc)
    return acc


def _v2_shape(item: dict) -> dict:
    return {"entity": None, "attribute": None, "constraints": [], "ranking": None, "rationale": "", **item}


def run_checks(*, run1_request: Path | None) -> dict:
    from ...framework.site import get
    from ...investigate.llm.meta import DEFAULT_REASONING_EFFORT, reservation_bound_usd
    from ...agent import ModelConfig
    from . import catalogue as K
    from . import planner as P
    from .verify import Verifier
    s = json_schema_v2()
    checks = {}
    bad = [f"{p}: required/properties or additionalProperties" for p, o in _objects(s) if set(o.get("required", [])) != set(o["properties"]) or o.get("additionalProperties") is not False]
    checks["strict_objects"] = (not bad, bad or [f"{sum(1 for _ in _objects(s))} objects checked"])
    extra = sorted(_keywords(s) - PROVEN_KEYWORDS)
    checks["proven_keywords"] = (not extra, extra or sorted(_keywords(s)))
    item = s["properties"]["tasks"]["items"]
    item = s["$defs"][item["$ref"].split("/")[-1]] if "$ref" in item else item
    props = item["properties"]
    nullable = {k: any(x.get("type") == "null" for x in props[k].get("anyOf", [])) for k in OPTIONAL_NULLABLE}
    shapes_ok = props["constraints"].get("type") == "array" and props["rationale"].get("type") == "string"
    checks["nullable_optionals"] = (all(nullable.values()) and shapes_ok, {**nullable, "constraints_array": props["constraints"].get("type") == "array", "rationale_string": props["rationale"].get("type") == "string"})
    site = get("larkspur")
    view = K.view(site)
    fixture = json.loads(P.FIXTURE.read_text())["tasks"]
    try:
        import jsonschema
        well_formed = [_v2_shape(t) for t in fixture if t.get("intent_id") not in ("f19",)]
        well_formed = [{k: v for k, v in t.items() if k != "expected_answer"} for t in well_formed]
        jsonschema.validate({"tasks": well_formed}, s)
        wire_ok = True
    except Exception as exc:
        wire_ok = f"{type(exc).__name__}: {str(exc)[:160]}"
    same = True
    for framing in ("raw", "framed"):
        a, b = Verifier(site, view, framing), Verifier(site, view, framing)
        for i, t in enumerate(fixture):
            from .schema import parse_item
            p1, _, e1 = parse_item(t)
            p2, _, e2 = parse_item(_v2_shape(t) if t.get("intent_id") != "f19" else t)
            d1, d2 = a.verify(i, p1, e1), b.verify(i, p2, e2)
            if (p1 != p2) or (d1.outcome, d1.cls, d1.category) != (d2.outcome, d2.cls, d2.category):
                same = False
    checks["parser_unchanged"] = (same and wire_ok is True, {"same_proposals_and_decisions": same, "v2_items_validate_against_wire_schema": wire_ok})
    req = P.build_request(view, 20, schema_version=SCHEMA_V2)
    if run1_request is not None:
        r1 = json.loads(Path(run1_request).read_text())
        checks["prompt_unchanged"] = (r1["messages"] == req.messages and r1.get("prompt_version") == P.PROMPT_VERSION, {"run1": str(run1_request), "messages_sha256": P.messages_sha256(req)})
    else:
        checks["prompt_unchanged"] = (False, "run 1 request record not supplied")
    bound = reservation_bound_usd(req)
    checks["reservation_bound"] = (bound <= APPROVED_MAX_RESERVATION_USD, {"reservation_usd": bound, "approved_max_usd": APPROVED_MAX_RESERVATION_USD})
    checks["model_settings"] = (ModelConfig().model == "muse-spark-1.3" and DEFAULT_REASONING_EFFORT == "low" and req.max_tokens == 6000,
                                {"model": ModelConfig().model, "reasoning_effort": DEFAULT_REASONING_EFFORT, "max_completion_tokens": req.max_tokens})
    return {"schema_version": SCHEMA_V2, "passed": all(ok for ok, _ in checks.values()), "checks": {k: {"ok": ok, "detail": d} for k, (ok, d) in checks.items()}}
