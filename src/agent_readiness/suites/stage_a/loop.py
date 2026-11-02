"""Stage A: the bounded task-generation loop (lifecycle M3; proposal §3.1).

Each round: generator (versioned prompt taskplan-v2 with the feedback slot) -> evaluator v2 (code only, cumulative over every candidate so far, so
earlier records never change) -> selection-2 -> coverage of the selection -> stopping rule -> feedback synthesiser -> next round. At most 3 rounds by
default; a budget cap is checked against each round's worst-case reservation BEFORE it is sent; a round is never retried.

Output: a suite PROPOSAL (`SuiteRecord`, Stage A, unapproved) with its `TaskRecord`s and private outcomes in the write-once store, plus a run
directory preserving everything: generation settings, prompt and schema versions, request hashes, raw responses and proposals, every evaluator
record (public and private), rejection reasons, feedback per round, coverage, the gap report and provenance. Approval and freezing are M4 and
need a human (the owner). Stage A never reads agent results: nothing here imports Stage B, and the store refuses Stage B references."""
from __future__ import annotations

import json
import os
import time
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path

from ...research.taskplan import planner_v2 as PV2
from ...suite.core import canonical_hash
from ...taskeval.v2 import coverage as COV
from ...taskeval.v2 import evaluator as E2
from ..records import InputRef, Provenance, SuiteRecord
from ..store import WriteOnceStore
from . import feedback as FB
from . import selection as SEL
from . import stopping as ST
from . import taskrecords as TR

VERSION = "stage-a-loop-1"
M2B_KINDS = ["ranked_subset", "either_of"]


@dataclass
class LoopConfig:
    suite_name: str
    version: int = 1
    n_per_round: int = 12
    max_tokens: int = 6000
    stop: ST.StopRule = field(default_factory=ST.StopRule)
    targets: dict | None = None
    evaluator_config: dict = field(default_factory=lambda: {"new_kinds": list(M2B_KINDS)})

    def as_dict(self) -> dict:
        return {**{k: v for k, v in asdict(self).items() if k != "stop"}, "stop": self.stop.as_dict(), "targets": {**{k: (list(v) if isinstance(v, tuple) else v) for k, v in COV.TARGETS.items()}, **(self.targets or {})}}


def _sha(obj) -> str:
    return canonical_hash(obj)


def _write(path: Path, obj, private: bool = False) -> None:
    path.write_text(json.dumps(obj, indent=1, sort_keys=True, default=str))
    os.chmod(path, 0o600 if private else 0o644)


def _private_view(r: dict) -> dict:
    return {k: v for k, v in r.items() if k != "_accepted"}


def run(site, view: dict, context: dict, generator, *, config: LoopConfig, created_at: str, out_dir: Path | None = None, store: WriteOnceStore | None = None,
        context_label: str = "synthetic") -> dict:
    ev = E2.TaskEvaluatorV2(site, view, context, config=config.evaluator_config)
    targets = config.as_dict()["targets"]
    candidates: list[dict] = []
    records: list[dict] = []
    rounds, useful_hist = [], []
    spent, feedback, stop = 0.0, None, None
    chosen, rub, cov, sel_log = [], [], None, []
    for k in range(1, config.stop.max_rounds + 1):
        request = PV2.build_request(view, context, config.n_per_round, feedback=feedback, round_no=k, targets=targets, max_tokens=config.max_tokens)
        reservation = float(generator.reservation_usd(request))
        stop = ST.before_round(config.stop, spent, reservation)
        if stop:
            rounds.append({"round": k, "sent": False, "reservation_usd": reservation, "spent_usd": round(spent, 6), "stop": stop})
            break
        t0 = time.monotonic()
        try:
            resp = generator.complete(request)                                      # exactly one call per round; never retried
        except Exception as exc:                                                    # provider error, schema rejection or a gate refusal: preserved, loop stops
            rounds.append({"round": k, "sent": True, "request": PV2.request_record(request), "reservation_usd": reservation, "error": f"{type(exc).__name__}: {str(exc)[:400]}",
                           "latency_seconds": round(time.monotonic() - t0, 2), "feedback_in": feedback, "stop": "generator_error"})
            stop = "generator_error"
            break
        latency = round(time.monotonic() - t0, 2)
        spent += float(resp.cost_usd or 0.0)
        items, batch_error = PV2.parse_batch(resp.text)
        new = []
        for it in items:
            iid = it["raw"].get("intent_id") if isinstance(it["raw"], dict) else None
            new.append({"candidate_id": f"r{k}-{iid or 'idx' + str(it['index'])}"[:80], "raw": it["raw"],
                        "provenance": {"round": k, "index": it["index"], "prompt_version": PV2.PROMPT_VERSION, "schema_version": "taskplan-schema-v3",
                                       "generator": generator.identity.get("kind"), "model": generator.identity.get("model"), "request_sha256": PV2.request_record(request)["request_sha256"]}})
        seen_ids = {c["candidate_id"] for c in candidates}
        for c in new:
            while c["candidate_id"] in seen_ids:
                c["candidate_id"] += "+"
            seen_ids.add(c["candidate_id"])
        before = records
        candidates += new
        records = ev.evaluate(candidates)
        ids = {c["candidate_id"] for c in new}
        useful = ST.useful_additions(before, [r for r in records if (r.get("derived_from") or r["candidate_id"]) in ids])
        useful_hist.append(len(useful))
        chosen, rub, sel_log = SEL.select(records, context, targets)
        cov = E2.coverage(chosen + rub, context, targets)
        stop = ST.after_round(config.stop, k, cov["targets_met"], useful_hist)
        nxt = None if stop else FB.synthesise(records, cov, chosen, context, round_no=k + 1)
        rounds.append({"round": k, "sent": True, "request": PV2.request_record(request), "reservation_usd": reservation, "cost_usd": float(resp.cost_usd or 0.0),
                       "usage": resp.usage, "response_mode": resp.mode, "response_model": resp.model, "response_text": resp.text, "batch_error": batch_error,
                       "latency_seconds": latency, "finish_reason": getattr(resp, "finish_reason", None), "reasoning_tokens": getattr(resp, "reasoning_tokens", None),
                       "candidates": [c["candidate_id"] for c in new], "admissions": dict(Counter(r["admission"] for r in records if (r.get("derived_from") or r["candidate_id"]) in ids)),
                       "useful_additions": useful, "selection_after": [r["candidate_id"] for r in chosen + rub], "targets_met": cov["targets_met"], "gaps_after": cov["gaps"],
                       "feedback_in": feedback, "feedback_out": nxt, "stop": stop})
        feedback = nxt
        if stop:
            break
    if cov is None:                                                              # stopped before the first round
        cov = E2.coverage([], context, targets)
    base = [r for r in records if not r.get("derived_from")]
    gap_report = {"stop_reason": stop, "rounds_sent": sum(r["sent"] for r in rounds), "targets_met": cov["targets_met"], "gaps": cov["gaps"],
                  "thresholds_lowered": False, "note": "acceptance thresholds and coverage targets were not lowered; unmet targets are listed here",
                  "preserved_underspecified": [{"candidate_id": r["candidate_id"], "wording": r["wording"]["customer"], "unresolved": r["wording"]["unresolved"]}
                                               for r in base if r["admission"] == "preserved_unexecuted"],
                  "rejections": dict(Counter(r["rejection_reasons"][0].split(":", 1)[0] for r in base if r["admission"] == "rejected" and r["rejection_reasons"])),
                  "uncovered_cells": [c for c in COV.uncovered_cells(cov, context) if c["weight"] >= targets["journey_min_weight"]],
                  "missing_capabilities": [c for c, n in cov["capabilities"].items() if not n], "natural_share": cov["natural_share"],
                  "conditions": dict(Counter(r["wording"]["condition"] for r in chosen))}
    summary = {"version": VERSION, "config": config.as_dict(), "generator": generator.identity, "evaluator": ev.identity, "selection_rule": SEL.RULE_ID,
               "feedback_version": FB.VERSION, "stopping": config.stop.as_dict(), "spent_usd": round(spent, 6), "rounds": rounds, "stop_reason": stop,
               "selection_log": sel_log, "selected": [r["candidate_id"] for r in chosen], "rubric": [r["candidate_id"] for r in rub], "created_at": created_at,
               "context_label": context_label}
    out = {"summary": summary, "records": records, "selected": chosen, "rubric": rub, "coverage": cov, "gap_report": gap_report, "suite_sha256": None}
    if store is not None and (chosen or rub):
        out.update(_persist(store, site, view, context, generator, ev, config, candidates, chosen + rub, cov, gap_report, created_at, summary))
    if out_dir is not None:
        _save(Path(out_dir), out, candidates)
    return out


def _persist(store, site, view, context, generator, ev, config, candidates, tasks, cov, gap_report, created_at, summary) -> dict:
    snap = site.snapshot(site.variants[0]).sha256
    inputs = (InputRef(kind="catalogue", name=f"{site.id}-catalogue-view", sha256=_sha(view)),
              InputRef(kind="context", name=f"{site.id}-context ({context.get('label', 'unlabelled')[:60]})", sha256=_sha(context)),
              InputRef(kind="snapshot", name=f"{site.id}@{site.variants[0]}", sha256=snap),
              InputRef(kind="generator", name=f"{generator.identity.get('kind')}:{PV2.PROMPT_VERSION}", sha256=_sha(generator.identity)),
              InputRef(kind="evaluator", name=f"{E2.VERSION}:{ev.identity['config_fingerprint']}", sha256=_sha(ev.identity)),
              InputRef(kind="proposals", name=f"{len(candidates)} raw proposals", sha256=_sha([c["raw"] for c in candidates])))
    shas = []
    for r in tasks:
        task, priv = TR.build(r, site=site.id, snapshot_sha256=snap, oracle_label=site.oracle().label, created_at=created_at, inputs=inputs, tool_version=VERSION)
        if priv is not None:
            store.put(priv)
        shas.append(store.put(task))
    coverage = {k: cov[k] for k in ("targets", "matrix", "per_persona", "per_journey", "capabilities", "multi_condition_share", "natural_share", "deterministic", "rubric", "status")}
    suite = SuiteRecord(suite_name=config.suite_name, version=config.version, site=site.id, task_sha256s=tuple(shas), selection_rule=SEL.RULE_ID, coverage=coverage,
                        gaps=tuple(gap_report["gaps"]) + tuple(f"preserved underspecified (needs clarification): {g['wording']}" for g in gap_report["preserved_underspecified"]),
                        provenance=Provenance(created_at=created_at, created_by="system", tool="agent_readiness.suites.stage_a.loop", tool_version=VERSION,
                                              config_fingerprint=_sha(config.as_dict())[:16], inputs=inputs,
                                              notes=f"Stage A loop: {summary['stop_reason']} after {gap_report['rounds_sent']} round(s); generator {generator.identity.get('kind')}; UNAPPROVED proposal"))
    return {"suite_sha256": store.put(suite), "task_sha256s": shas}


def _save(d: Path, out: dict, candidates: list[dict]) -> None:
    d.mkdir(parents=True, exist_ok=False)                                        # a run directory is written once
    _write(d / "loop.json", out["summary"])
    _write(d / "proposals.json", [{"candidate_id": c["candidate_id"], "provenance": c["provenance"], "raw": c["raw"]} for c in candidates])
    _write(d / "evaluation.public.json", [E2.public(r) for r in out["records"]])
    _write(d / "evaluation.private.json", [_private_view(r) for r in out["records"]], private=True)
    _write(d / "coverage.json", out["coverage"])
    _write(d / "gap-report.json", out["gap_report"])
    for r in out["summary"]["rounds"]:
        if r.get("feedback_out"):
            _write(d / f"feedback-r{r['round'] + 1}.json", r["feedback_out"])
    _write(d / "suite-proposal.json", {"suite_sha256": out["suite_sha256"], "task_sha256s": out.get("task_sha256s", []), "status": "proposal (unapproved)",
                                        "selected": out["summary"]["selected"], "rubric": out["summary"]["rubric"]})
