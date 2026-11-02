"""Run one planner batch on Larkspur, verify every proposal independently, compare with the rule-based generator, and preserve every artefact.

    python -m agent_readiness.research.taskplan.experiment --client fixture [--n 20] [--out DIR]
    python -m agent_readiness.research.taskplan.experiment --client meta --approval-note "..." --cap-usd 0.20     # paid: only after owner approval

Outputs (git-ignored, default scanner-data/research/taskplan/<run>/): request.json (prompt, prompt version, model configuration, catalogue and
context fingerprints), response.json (raw text, usage, calculated cost), proposals.json (raw items, stripped answer fields, schema errors),
decisions.private.json (criteria and oracle-derived answers; never published), decisions.public.json, metrics.json, report.md."""
from __future__ import annotations

import argparse
import json
import sys
import time
import uuid
from collections import Counter
from pathlib import Path
from statistics import mean

from ...framework import generate as G
from ...framework.site import get
from ...suite.core import canonical_hash
from . import catalogue as K
from . import context as X
from . import planner as P
from .verify import Verifier

SCHEMA = "research-taskplan-v1"
HALLUCINATION = ("unsupported_attribute", "unknown_entity", "value_not_in_domain", "value_type_mismatch")


def _attrs(crit: dict | None) -> set[str]:
    if not crit:
        return set()
    return {c["label"] for c in crit.get("conditions", [])} | ({crit["label"]} if "label" in crit else set())


def _shape(crit: dict | None, kind: str | None) -> str:
    if not crit:
        return kind or "open"
    ops = sorted({c["op"] for c in crit.get("conditions", [])})
    return f"{crit['kind']}/{len(crit.get('conditions', []))}" + (f"/{'+'.join(ops)}" if ops else "")


def metrics(rows: list[dict], n_proposals: int) -> dict:
    """rows: one per proposal or task: {eligible, cls, category, persona, journey, crit, kind, hops, evidence}."""
    elig = [r for r in rows if r["eligible"]]
    by_attr = set().union(*(X.journeys_for(_attrs(r["crit"])) for r in elig)) if elig else set()
    declared = {r["journey"] for r in elig if r.get("journey")}
    shas = [canonical_hash(r["crit"]) for r in elig]
    return {"proposals": n_proposals, "eligible_deterministic": len(elig), "acceptance_rate": round(len(elig) / n_proposals, 3) if n_proposals else None,
            "classes": dict(Counter(r["cls"] for r in rows if r["cls"])), "rejections": dict(Counter(r["category"] for r in rows if r["category"])),
            "persona_coverage": f"{len({r['persona'] for r in elig if r.get('persona')})}/{len(X.CONTEXT['personas'])}",
            "journey_coverage_by_attributes": f"{len(by_attr)}/{len(X.CONTEXT['journeys'])}", "journeys_by_attributes": sorted(by_attr),
            "journey_coverage_declared": f"{len(declared)}/{len(X.CONTEXT['journeys'])}" if any(r.get("journey") for r in rows) else "n/a (no journeys declared)",
            "distinct_task_types": sorted({_shape(r["crit"], r.get("kind")) for r in elig}),
            "attributes_used": sorted(set().union(*(_attrs(r["crit"]) for r in elig))) if elig else [],
            "duplicate_rate": round(sum(r["category"] == "duplicate" for r in rows) / n_proposals, 3) if n_proposals else 0.0,
            "unsupported_or_hallucinated": sum(r["category"] in HALLUCINATION for r in rows),
            "complexity": {"mean_conditions": round(mean(len(r["crit"].get("conditions", [])) for r in elig), 2) if elig else None,
                           "multi_condition_share": round(sum(len(r["crit"].get("conditions", [])) > 1 for r in elig) / len(elig), 3) if elig else None,
                           "mean_min_hops": round(mean(r["hops"] for r in elig), 2) if elig else None,
                           "mean_evidence_pages": round(mean(r["evidence"] for r in elig), 2) if elig else None},
            "_criterion_shas": shas}


def rule_based(site) -> list[dict]:
    ts = G.generate(site)
    rows = []
    for t in ts["tasks"]:
        a = t["_accepted"]
        rows.append({"eligible": t["eligible"], "cls": t["class"], "category": None, "persona": None, "journey": None, "crit": a.criterion, "kind": a.compiled.kind,
                     "hops": t["min_hops"], "evidence": len(a.compiled.evidence_paths)})
    rows += [{"eligible": False, "cls": r["class"], "category": None, "persona": None, "journey": None, "crit": None, "kind": "rubric", "hops": 0, "evidence": 0} for r in ts["rubric"]]
    return rows


def run(*, client: str = "fixture", n: int = 20, out: Path | None = None, approval_note: str = "", cap_usd: float = 0.20, schema_version: str = "taskplan-schema-v1",
        preflight_run1: Path | None = None, budget_note: str = "") -> dict:
    site = get("larkspur")
    view = K.view(site)
    request = P.build_request(view, n, schema_version=schema_version)
    preflight = None
    if client == "meta" and schema_version == "taskplan-schema-v2":
        from .preflight import run_checks
        preflight = run_checks(run1_request=preflight_run1)
        if not preflight["passed"]:
            raise PermissionError("taskplan-schema-v2 preflight failed; Meta was NOT called: " + json.dumps({k: v for k, v in preflight["checks"].items() if not v["ok"]})[:400])
    run_id = f"taskplan-{time.strftime('%Y%m%dT%H%M%S')}-{client}-{uuid.uuid4().hex[:6]}"
    out = Path(out or Path("scanner-data/research/taskplan")) / run_id
    out.mkdir(parents=True, exist_ok=False)
    if preflight is not None:
        (out / "preflight.json").write_text(json.dumps(preflight, indent=1))
    if client == "fixture":
        llm = P.fixture_client()
        model = {"provider": "fixture", "model": "scripted-fixture (NOT a model)", "note": "proposals written by the developer"}
    elif client == "meta":
        llm = P.meta_client(out / "ledger", approval_note=approval_note, run_cap_usd=cap_usd, max_requests=1)
        model = {"provider": "meta", "model": llm.model, "reasoning_effort": llm.reasoning_effort, "max_completion_tokens": request.max_tokens, "approval_note": approval_note,
                 "research_ledger_cap_usd": cap_usd, "budget_note": budget_note}
    else:
        raise ValueError("client must be fixture or meta")
    (out / "request.json").write_text(json.dumps({"schema": SCHEMA, **P.request_record(request, schema_version), "model": model, "messages": request.messages, "response_schema": request.response_schema,
                                                  "catalogue_fingerprint": K.fingerprint(view), "site_versions": view["versions"], "context_fingerprint": X.fingerprint(),
                                                  "context_label": X.LABEL, "n_requested": n}, indent=1))
    started = time.time()
    t0 = time.monotonic()
    try:
        resp = llm.complete(request)                                             # exactly one call; never retried here
    except Exception as exc:                                                     # preserved, then re-raised: a failed paid request is still a result
        (out / "response.json").write_text(json.dumps({"error": type(exc).__name__, "detail": str(exc)[:300], "latency_seconds": round(time.monotonic() - t0, 2),
                                                       "started_at": started}, indent=1))
        raise
    latency = round(time.monotonic() - t0, 2)
    (out / "response.json").write_text(json.dumps({"mode": resp.mode, "model": resp.model, "text": resp.text, "usage": resp.usage, "cost_usd": resp.cost_usd,
                                                   "finish_reason": resp.finish_reason, "reasoning_tokens": resp.reasoning_tokens, "latency_seconds": latency,
                                                   "started_at": started}, indent=1))
    items, batch_error = P.parse_batch(resp.text)
    (out / "proposals.json").write_text(json.dumps({"batch_error": batch_error, "items": [{k: v for k, v in it.items() if k != "proposal"} for it in items]}, indent=1))
    base_rows = rule_based(site)
    m_rule = metrics(base_rows, len(base_rows))
    rule_shas = set(m_rule.pop("_criterion_shas"))
    by_framing, all_decisions = {}, {}
    for framing in ("raw", "framed"):
        ver = Verifier(site, view, framing)
        decisions = [ver.verify(it["index"], it["proposal"], it["schema_errors"]) for it in items]
        all_decisions[framing] = decisions
        (out / f"decisions.{framing}.private.json").write_text(json.dumps([{**d.public(), "criterion": d.criterion, "truth": d.truth} for d in decisions], indent=1, default=str))
        (out / f"decisions.{framing}.public.json").write_text(json.dumps([d.public() for d in decisions], indent=1))
        rows = [{"eligible": d.eligible, "cls": d.cls, "category": d.category, "persona": getattr(it["proposal"], "persona", None), "journey": getattr(it["proposal"], "journey", None),
                 "crit": d.criterion, "kind": (d.complexity or {}).get("kind"), "hops": (d.complexity or {}).get("min_hops", 0), "evidence": (d.complexity or {}).get("evidence_pages", 0)}
                for d, it in zip(decisions, items)]
        m = metrics(rows, len(items))
        m["overlap_with_rule_based"] = len(set(m.pop("_criterion_shas")) & rule_shas)
        by_framing[framing] = m
    decisions = all_decisions["raw"]
    doc = {"schema": SCHEMA, "run": run_id, "client": client, "model": model, "prompt_version": P.PROMPT_VERSION, "schema_version": schema_version, "catalogue_fingerprint": K.fingerprint(view),
           "context_fingerprint": X.fingerprint(), "context_label": X.LABEL, "site_versions": view["versions"], "batch_error": batch_error,
           "cost": {"usage": resp.usage, "calculated_usd": resp.cost_usd, "basis": "calculated at published prices; not a bill" if client == "meta" else "fixture: no model call",
                    "latency_seconds": latency},
           "llm": by_framing, "rule_based": m_rule,
           "stripped_answer_fields": sum(bool(it["stripped_answer_fields"]) for it in items)}
    (out / "metrics.json").write_text(json.dumps(doc, indent=1))
    examples = []
    for d, f, it in zip(all_decisions["raw"], all_decisions["framed"], items):
        p = it["proposal"]
        examples.append({"index": d.index, "intent_id": d.intent_id, "persona": getattr(p, "persona", None), "scenario": getattr(p, "scenario", None),
                         "raw": {"outcome": d.outcome, "class": d.cls, "category": d.category, "reason": (d.reasons or [""])[0]},
                         "framed": {"outcome": f.outcome, "class": f.cls, "category": f.category, "reason": (f.reasons or [""])[0]}})
    (out / "examples.public.json").write_text(json.dumps(examples, indent=1))
    return {"dir": str(out), **doc, "examples": examples}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="agent_readiness.research.taskplan.experiment")
    ap.add_argument("--client", choices=("fixture", "meta"), default="fixture")
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--approval-note", default="")
    ap.add_argument("--cap-usd", type=float, default=0.20)
    ap.add_argument("--estimate", action="store_true", help="print the request's reservation bound and exit (no call)")
    ap.add_argument("--schema-version", default="taskplan-schema-v1", choices=("taskplan-schema-v1", "taskplan-schema-v2"))
    ap.add_argument("--preflight-run1", type=Path, help="request.json of paid run 1 (the prompt must be byte-identical)")
    ap.add_argument("--budget-note", default="")
    a = ap.parse_args(argv)
    if a.estimate:
        from ...investigate.llm.meta import reservation_bound_usd
        req = P.build_request(K.view(get("larkspur")), a.n)
        print(json.dumps({"prompt_version": P.PROMPT_VERSION, "max_completion_tokens": req.max_tokens, "reservation_bound_usd": reservation_bound_usd(req),
                          "prompt_chars": sum(len(m["content"]) for m in req.messages)}))
        return 0
    r = run(client=a.client, n=a.n, out=a.out, approval_note=a.approval_note, cap_usd=a.cap_usd, schema_version=a.schema_version, preflight_run1=a.preflight_run1,
            budget_note=a.budget_note)
    print(json.dumps({k: r[k] for k in ("dir", "llm", "rule_based", "cost")}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
