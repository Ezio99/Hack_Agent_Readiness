"""SYNTHETIC investigation run for offline dashboard/exporter tests (Task 016 M7). Nothing here was produced by a model, an agent or a website: every record is a hand-written fixture with
provenance mode `scripted`, and `dashboard/src/fixtures/investigation-synthetic.json` is generated from it by `python -m tests.synthetic_investigation` so the UI contract cannot drift from the exporter."""
from __future__ import annotations

import json
from pathlib import Path

from agent_readiness.investigate.evaluate import design
from agent_readiness.investigate.export import export_run
from agent_readiness.investigate.flow import STAGES
from agent_readiness.investigate.models import Hypothesis, Observation, Effect, Proposal, Provenance, Verification
from agent_readiness.investigate.run import InvestigationRun

FIXTURE = Path(__file__).resolve().parents[1] / "dashboard" / "src" / "fixtures" / "investigation-synthetic.json"
SCRIPTED = Provenance(mode="scripted", source="fixture:synthetic", created_at="2026-01-01T00:00:00+00:00")
TASKS = [("syn-t1", "investigation", "item_set", "Which listed cabins have a fireplace? List their names."), ("syn-t2", "investigation", "extremum", "Which cabin has the lowest nightly price?"),
         ("syn-t3", "investigation", "item_set", "Which cabins allow pets? List their names."), ("syn-t4", "investigation", "page_fact", "What is the check-in time for Pine Cabin?"),
         ("syn-t5", "holdout", "item_set", "Which cabins have a hot tub? List their names."), ("syn-t6", "holdout", "page_fact", "What is the cancellation window for Lake Cabin?")]
LIMITS = {"max_steps": 11, "max_model_requests": 11, "timeout_seconds": 240}
BASE = {"syn-t1": ("completed", False, 11), "syn-t2": ("completed", False, 9), "syn-t3": ("request_limit", False, 11), "syn-t4": ("completed", False, 8), "syn-t5": ("infrastructure_error", False, 2), "syn-t6": ("completed", False, 7)}
POST = {t: ("completed", True, 5) for t, *_ in TASKS}


def _trial(run, name, tid, task, repeat, arm, status, passed, requests):
    run.write_artifact(f"trials/{name}", {"task_id": task, "trial_id": tid, "repeat": repeat, "arm": arm, "outcome": {"run_status": status, "stop_reason": "synthetic"},
                                           "evaluation": {"passed": passed, "evidence_backed": passed}, "metrics": {"model_requests": requests, "page_views": requests - 1}, "trial": {"mode": "scripted"}})


def build(root: Path, *, complete: bool = True) -> Path:
    run = InvestigationRun.create(root, "synthetic-demo", target="synthetic-cabin-site (fixture)", mode="scripted", stages=STAGES)
    ev = run.evidence
    for s in STAGES[: (len(STAGES) if complete else 4)]:
        run.set_status(s, "done", summary={"synthetic": True})
    if not complete:
        run.set_status(STAGES[4], "awaiting_approval", manifest_sha256="0" * 64)
    o1 = ev.add_observation(Observation(kind="listing_cards", summary="Listing cards show name and price, no amenity text (6 of 6 cards).", refs=["page:/cabins"], provenance=SCRIPTED))
    o2 = ev.add_observation(Observation(kind="detail_pages", summary="Amenities appear only on cabin detail pages (6 of 6).", refs=["page:/cabins/1"], provenance=SCRIPTED))
    o3 = ev.add_observation(Observation(kind="trace_pattern", summary="In 3 baseline trials the agent opened every cabin page before answering.", refs=["trial:syn-t1-r1", "trial:syn-t3-r1"], provenance=SCRIPTED))
    h1 = ev.add_hypothesis(Hypothesis(tier="verifiable", statement="Amenities are on detail pages but absent from listing cards.", claim_kind="info_absent_on_template", citations=[o1.id, o2.id], provenance=SCRIPTED))
    ev.record_verification(h1.id, Verification(verifier="fixture:info_absent_on_template", result="supported", evidence=[o1.id, o2.id], provenance=SCRIPTED))
    h2 = ev.add_hypothesis(Hypothesis(tier="novel", statement="Agents open every page because nothing on the listing suggests which cabin is worth opening.",
                                      prediction="If cards listed amenities, model requests on list-and-filter tasks would fall.", citations=[o3.id], provenance=SCRIPTED))
    h3 = ev.add_hypothesis(Hypothesis(tier="verifiable", statement="The site returns errors on some paths.", claim_kind="error_response_on_path", citations=[o1.id], provenance=SCRIPTED))
    ev.record_verification(h3.id, Verification(verifier="fixture:error_response_on_path", result="refuted", evidence=[o1.id], provenance=SCRIPTED))
    f = ev.promote(h1.id, attribution="website", support=["trial:syn-t1-r1", "trial:syn-t3-r1"])
    p1 = ev.add_proposal(Proposal(basis="verified_finding", source_id=f.id, change={"ops": [{"op": "copy_field_to_listing"}]}, expected_effect="Fewer page views on amenity-dependent tasks.", risks=["Wider cards"], provenance=SCRIPTED))
    ev.add_proposal(Proposal(basis="unverified_hypothesis", source_id=h2.id, change={"manual": "Add a one-line cue to cards and compare request counts."}, expected_effect=h2.prediction, risks=["Mechanism unverified"], provenance=SCRIPTED))
    run.write_artifact("tasks-manifest", {"schema": "tasks-manifest-v1", "tasks": [{"task_id": t, "partition": p, "kind": k, "source": "rule", "question": q, "start_path": "/", "limits": LIMITS} for t, p, k, q in TASKS]})
    att = {}
    for t, p, k, q in TASKS:
        status, passed, req = BASE[t]
        _trial(run, f"baseline-{t}-r1", f"{t}-r1", t, 1, "baseline", status, passed, req)
        primary = "infrastructure" if status == "infrastructure_error" else "success" if passed else "undetermined" if status == "request_limit" else "website"
        att[f"{t}-r1"] = {"task_id": t, "primary": primary, "void": primary == "infrastructure", "why": "synthetic fixture attribution"}
    run.write_artifact("attribution", att)
    run.write_artifact("investigation", {"skipped": False, "finished": True, "incomplete": False, "tool_calls": 7, "model_requests": 9, "model": "scripted-fixture", "mode": "scripted", "cost_usd": 0.0, "rejected_hypotheses": []})
    if complete:
        ev.approve(p1.id, manifest_sha256="1" * 64, note="synthetic approval")
        ev.mark_applied(p1.id)
        for t, *_ in TASKS:
            status, passed, req = POST[t]
            _trial(run, f"patched-{p1.id}-{t}-r1", f"{t}-r1", t, 1, "patched", status, passed, req)
        arm = lambda src: {t: [{"void": src[t][0] == "infrastructure_error", "passed": src[t][1], "evidence_backed": src[t][1], "model_requests": src[t][2], "primary": "x", "page_views": src[t][2]}] for t, *_ in TASKS}
        cmp_ = design.compare(arm(BASE), arm(POST), {t: p for t, p, *_ in TASKS}, design.RULE)           # the numbers come from the real pre-registered rule applied to the rows above, not typed in
        res = {**{k: cmp_[k] for k in ("verdict", "pairs", "pass_delta", "request_change", "p_pass", "p_requests", "holdout_consistent", "by_partition", "excluded")},
               "reason": f"ILLUSTRATIVE (synthetic data): {cmp_['reason']}", "rule_preregistered_at_freeze": True}
        ev.add_effect(Effect(proposal_id=p1.id, verdict=res["verdict"], metrics={"pass_delta": res["pass_delta"]}, n_pairs=res["pairs"], note=res["reason"], provenance=SCRIPTED))
        run.write_artifact("evaluation", {"evaluated": True, "rule": {"id": "paired-signflip-v1", "primary": "evidence_backed_pass_rate", "secondary": "model_requests", "alpha": 0.1, "min_pairs": 4, "pass_delta_floor": 0.25,
                                                                         "request_reduction_floor": 0.25, "void_policy": "a pair with any void trial in either arm is excluded and listed", "causal_scope": "these frozen tasks, this profile and this patched mirror only"},
                           "results": {p1.id: res}})
        run.write_artifact("report-final", {"statement": "SYNTHETIC FIXTURE: findings are website properties; trials show an association; a measured effect needs live trials."})
    return run.dir


def regenerate(tmp: Path) -> dict:
    import shutil
    shutil.rmtree(tmp, ignore_errors=True)
    return export_run(build(tmp))


if __name__ == "__main__":
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        data = regenerate(Path(d))
    data["synthetic"] = True
    data["exported_at"] = "2026-01-01T00:00:00+00:00"
    data["run"]["created_at"] = "2026-01-01T00:00:00+00:00"
    for s in data["stages"]:
        s["updated_at"] = None
    FIXTURE.parent.mkdir(parents=True, exist_ok=True)
    FIXTURE.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
    print(f"wrote {FIXTURE}")
