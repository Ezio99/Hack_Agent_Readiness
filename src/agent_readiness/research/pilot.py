"""Isolated Larkspur end-to-end pilot: evaluator-selected generated tasks -> frozen manifest -> jailed browser trials on Original and Modified.

    python -m agent_readiness.research.pilot prepare --proposals RUN_DIR --root DIR [--provider dev|live]
    python -m agent_readiness.research.pilot execute RUN --provider dev                 # zero-cost preflight (loopback dev provider, NOT a model)
    python -m agent_readiness.research.pilot execute RUN --provider live --approval-note "..."   # paid: Muse Spark, research ledger, US$5 hard cap
    python -m agent_readiness.research.pilot report RUN

Reuses unchanged: taskeval (evaluation and selection), freeze format, framework.evaluate (plan and results), trials.runner.run_trial, RequestGate and
Ledger, the hosted browser jail, grading.rescore, provenance, diagnostics. Nothing in production imports this module."""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import uuid
from pathlib import Path

from ..agent import ModelConfig
from ..framework import evaluate as FE
from ..framework.site import get
from ..investigate.inspect.stage import run_inspect
from ..investigate.pipeline import Context
from ..investigate.run import InvestigationRun
from ..investigate.taskgen import freeze as freezer
from ..investigate.trials.runner import run_trial
from ..investigate.trials.stage import VOID_STATUSES
from ..spend_gate import RequestGate
from ..suite.core import canonical_hash
from ..taskeval import evaluator as TE
from ..taskeval import select as TS
from .taskplan import catalogue as K
from .taskplan import context as X

SCHEMA = "research-pilot-v1"
HARD_CAP_USD = 5.0
PER_REQUEST_CAP_USD = 0.044            # >= 18 % above the highest per-request bound observed on real bodies (Larkspur 0.034984, Ironbark real model 0.037324)
JAIL_POLICY = {"hide": [str(Path.home() / "Projects"), str(Path.home() / ".ssh"), str(Path.home() / ".claude"), "/root"], "dir": "/tmp/arj"}


def _candidates(proposals_dir: Path) -> tuple[list[dict], dict]:
    req = json.loads((proposals_dir / "request.json").read_text())
    items = json.loads((proposals_dir / "proposals.json").read_text())["items"]
    prov = {"source": "llm", "run": proposals_dir.name, "prompt_version": req["prompt_version"], "schema_version": req.get("schema_version"), "model": req["model"]["model"],
            "reasoning_effort": req["model"].get("reasoning_effort"), "catalogue_fingerprint": req["catalogue_fingerprint"]}
    return [{"candidate_id": it["raw"].get("intent_id") or f"idx{it['index']}", "provenance": {**prov, "index": it["index"]}, "raw": it["raw"]} for it in items], req


def prepare(proposals_dir: Path, root: Path, *, provider: str, k: int = 4) -> InvestigationRun:
    site = get("larkspur")
    view = K.view(site)
    cands, req = _candidates(Path(proposals_dir))
    if req["catalogue_fingerprint"] != K.fingerprint(view):
        raise ValueError("the proposals were generated against a different catalogue")
    records = TE.TaskEvaluator(site, view, X.CONTEXT).evaluate(cands)
    chosen, log = TS.select(records, k)
    manifest, private = freezer.build([r["_accepted"] for r in chosen], snapshot_sha256=site.snapshot("original").sha256,
                                      generator={"id": "llm-taskplan", "prompt_version": req["prompt_version"], "schema_version": req.get("schema_version"),
                                                 "evaluator": TE.VERSION, "evaluator_config": TE.config_fingerprint(), "selection": TS.RULE_ID}, agent_profile="suite-v2-compat2")
    run = InvestigationRun.create(Path(root), f"pilot-larkspur-{provider}-{uuid.uuid4().hex[:8]}", target="larkspur", mode="live", stages=("inspect", "freeze", "trials"),
                                  config={"framework": SCHEMA, "site": "larkspur", "provider": provider, "variants": list(site.variants)})
    run_inspect(Context(run), site.snapshot("original"))
    run.write_private("criteria", private)
    run.write_artifact("tasks-manifest", manifest)
    if provider == "dev":
        run.write_artifact("dev-provider", {"loopback_stand_in": True})
    by_q = {t["question"]: t["task_id"] for t in manifest["tasks"]}
    run.write_private("taskeval-records", [{**{k_: v for k_, v in r.items() if k_ != "_accepted"}} for r in records])
    run.write_artifact("taskeval-records", [TE.public(r) | {"selected": r in chosen, "task_id": by_q.get(r["wordings"]["restated_question"])} for r in records])
    run.write_artifact("selection", {"rule": TS.RULE_ID, "rule_text": TS.__doc__, "log": log, "k": k,
                                     "selected": [{"candidate_id": r["candidate_id"], "task_id": by_q[r["wordings"]["restated_question"]], "persona": r["persona"], "journey": r["journey"],
                                                   "attributes": r["attributes"], "conditions": len(r["specification"].get("conditions", [])), "executed_wording": "restated_question",
                                                   "customer_question": r["wordings"]["customer_question"], "restated_question": r["wordings"]["restated_question"],
                                                   "natural_wording_passes_gate": r["natural_wording_passes_gate"], "unsupported_assumptions": r["unsupported_assumptions"]} for r in chosen]})
    steps, _ = FE._plan(run, site)
    worst = round(sum(st["inst"].spec.limits.max_model_requests * PER_REQUEST_CAP_USD for st in steps), 6)
    run.write_artifact("pilot-provenance", {"schema": SCHEMA, "site_versions": {v: site.snapshot(v).sha256 for v in site.variants}, "oracle": site.oracle().label,
                                            "catalogue_fingerprint": K.fingerprint(view), "context_fingerprint": X.fingerprint(), "evaluator": TE.VERSION,
                                            "evaluator_config_fingerprint": TE.config_fingerprint(), "selection_rule": TS.RULE_ID, "tasks_manifest_sha256": canonical_hash(manifest),
                                            "criteria_sha256": manifest["criteria_sha256"], "agent_profile": "suite-v2-compat2", "model": ModelConfig().model,
                                            "budget": {"hard_cap_usd": HARD_CAP_USD, "per_request_cap_usd": PER_REQUEST_CAP_USD, "trials": len(steps),
                                                       "worst_case_reservation_usd": worst, "within_cap": worst <= HARD_CAP_USD},
                                            "jail_policy": JAIL_POLICY, "proposals_run": Path(proposals_dir).name})
    run.write_artifact("framework-provenance", run.artifact("pilot-provenance"))     # framework.evaluate.results embeds the run's provenance under this name
    freezer.load(run)
    return run


def _order(steps: list[dict]) -> list[dict]:
    """Counterbalanced: tasks in manifest order; even-indexed tasks run Original first, odd-indexed Modified first."""
    tasks = sorted({s["task"]["task_id"] for s in steps})
    out = []
    for i, tid in enumerate(tasks):
        pair = sorted([s for s in steps if s["task"]["task_id"] == tid], key=lambda s: s["variant"] != ("original" if i % 2 == 0 else "modified"))
        out += pair
    return out


def _enable_jail(run: InvestigationRun) -> dict:
    from ..hosted import jail
    path = run.dir / "jail-policy.json"
    if not path.exists():
        path.write_text(json.dumps(JAIL_POLICY))
    os.environ[jail.ENV] = str(path)
    jail.require()                                                   # from now on an unjailed browser launch is an error
    result = jail.selftest()
    if not result.get("ok"):
        raise RuntimeError(f"browser jail self-test failed: {result}")
    return result


def execute(run: InvestigationRun, *, approval_note: str = "") -> dict:
    site = get("larkspur")
    provider = run.state["config"]["provider"]
    prov = run.artifact("pilot-provenance")
    if not prov["budget"]["within_cap"]:
        raise PermissionError(f"worst-case reservation US${prov['budget']['worst_case_reservation_usd']} exceeds the US${HARD_CAP_USD} cap; reduce the task count")
    steps = _order(FE._plan(run, site)[0])
    if len(steps) > 8:
        raise PermissionError("at most 8 trials")
    selftest = _enable_jail(run)
    ledger = run.ledger(HARD_CAP_USD)
    executed, stopped = [], None

    def go(cfg: ModelConfig, key: str):
        nonlocal stopped
        for st in steps:
            t, v = st["task"], st["variant"]
            name = f"{v}-{t['task_id']}-r1"
            if run.has_artifact(f"trials/{name}"):
                continue
            lim = st["inst"].spec.limits
            gate = RequestGate(ledger, name, run_cap=round(lim.max_model_requests * PER_REQUEST_CAP_USD, 6), per_request_cap=PER_REQUEST_CAP_USD, max_requests=lim.max_model_requests)
            rec = asyncio.run(run_trial(st["inst"], st["snap"], provider="live", output=run.dir / "trial-data" / name, model_config=cfg, api_key=key, request_gate=gate,
                                        label=v, profile_id="suite-v2-compat2"))
            trial_dir = str(Path(rec.pop("artifact_path")).relative_to(run.dir))
            run.write_artifact(f"trials/{name}", {**rec, "task_id": t["task_id"], "partition": t["partition"], "repeat": 1, "trial_id": f"{t['task_id']}-r1",
                                                  "trial_dir": trial_dir, "arm": v, "variant": v, "variant_sha256": st["snap"].sha256})
            executed.append(name)
            if rec["outcome"]["run_status"] in VOID_STATUSES:
                stopped = f"{name}: void ({rec['outcome']['run_status']}); remaining trials not run (no retries)"
                return
            if gate.violation:
                stopped = f"{name}: spend-gate bound violation; remaining trials not run"
                return

    if provider == "dev":
        with FE.dev_provider(run) as (_, url):
            go(ModelConfig(base_url=url), FE.DEV_KEY)
    else:
        if not approval_note.strip():
            raise PermissionError("a paid pilot needs the owner's approval note")
        from ..ledger import preflight
        cfg = ModelConfig()
        key = preflight(cfg, True)
        run.write_artifact("pilot-approval", {"note": approval_note, "hard_cap_usd": HARD_CAP_USD, "worst_case_reservation_usd": prov["budget"]["worst_case_reservation_usd"]})
        go(cfg, key)
    return {"executed": executed, "stopped": stopped, "jail_selftest": selftest, "order": [f"{s['variant']}-{s['task']['task_id']}" for s in steps]}


def report(run: InvestigationRun) -> dict:
    from .. import provenance as P
    from ..diagnostics import run as D
    if not run.has_artifact("framework-provenance"):
        run.write_artifact("framework-provenance", run.artifact("pilot-provenance"))
    res = FE.results(run)
    live = run.state["config"]["provider"] == "live"
    bundle = D.from_framework_run(run.dir)
    bundle["origin"] = "real_model" if live else "dev_fixture"
    diag = D.diagnose(bundle)
    entries = run.ledger(HARD_CAP_USD).entries()
    reserved = {e["id"]: e["usd"] for e in entries if e["kind"] == "reserve"}
    settled = {e["id"]: e["usd"] for e in entries if e["kind"] == "settle"}
    cost = {"requests": len(reserved), "reserved_usd": round(sum(reserved.values()), 6), "settled_calculated_usd": round(sum(settled.values()), 6),
            "unsettled": sorted(set(reserved) - set(settled)), "basis": "calculated from provider-reported usage at published prices; not a bill" if live else "dev fixture: no money"}
    trials = []
    for row in res["trials"]:
        t = run.artifact(f"trials/{row['variant']}-{row['task_id']}-r1")
        trials.append({**row, "elapsed_seconds": t["metrics"]["elapsed_seconds"], "prompt_tokens": t["metrics"]["prompt_tokens"], "completion_tokens": t["metrics"]["completion_tokens"],
                       "calculated_cost_usd": t["metrics"]["calculated_cost_usd"], "stop_reason": t["outcome"]["stop_reason"]})
    doc = {"schema": SCHEMA, "run": run.state["id"], "provider": run.state["config"]["provider"], "results": {**res, "trials": trials}, "cost": cost,
           "model_provenance": P.model_provenance(run.dir, arms=("original", "modified")), "diagnostics": diag}
    run.write_artifact(f"pilot-report-{run.state['config']['provider']}", doc) if not run.has_artifact(f"pilot-report-{run.state['config']['provider']}") else None
    return doc


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="agent_readiness.research.pilot")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("prepare"); p.add_argument("--proposals", type=Path, required=True); p.add_argument("--root", type=Path, required=True)
    p.add_argument("--provider", choices=("dev", "live"), required=True); p.add_argument("--k", type=int, default=4)
    e = sub.add_parser("execute"); e.add_argument("run", type=Path); e.add_argument("--approval-note", default="")
    r = sub.add_parser("report"); r.add_argument("run", type=Path)
    a = ap.parse_args(argv)
    if a.cmd == "prepare":
        run = prepare(a.proposals, a.root, provider=a.provider, k=a.k)
        print(json.dumps({"run": str(run.dir), "selection": [s["candidate_id"] for s in run.artifact("selection")["selected"]], "budget": run.artifact("pilot-provenance")["budget"]}, indent=1))
    elif a.cmd == "execute":
        print(json.dumps(execute(InvestigationRun(a.run), approval_note=a.approval_note), indent=1, default=str))
    else:
        d = report(InvestigationRun(a.run))
        print(json.dumps({"totals": d["results"]["totals"], "cost": d["cost"], "complete": d["results"]["complete"], "rescore_faithful": d["results"]["rescore_faithful"],
                          "diagnostics": d["diagnostics"]["summary"]}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
