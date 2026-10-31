"""Spend authorization for ONE live evaluation (M1).

The investigation pipeline already gates every paid stage behind the owner's approval of that stage's exact manifest hash, recorded in the run's `approvals.jsonl`. A product user cannot run CLI
approvals, so the user's confirmation in the UI is turned into a GRANT that a worker uses to record those same approvals itself, under strict conditions:

  * the grant names ONE job, ONE owner (session), ONE run directory, ONE registered target, the exact goal, a budget (US$), a model + endpoint and an explicit list of stages;
  * `grant_sha256` covers all of that; a grant whose hash does not match its fields, or whose job/run/owner differs from the run being approved, approves nothing;
  * for each manifest the pipeline presents, `Approver.decide` checks: stage in scope, the manifest names the grant's model and endpoint and snapshot, no cap in it exceeds the budget, and
    committed spend plus the stage's own cap still fits the budget. Anything else (apply_fix, post_trials, an unknown stage, a changed manifest, a larger cap) is REFUSED and the run is
    left at `awaiting_approval` for a human; nothing is spent;
  * every approval it records is an ordinary approvals.jsonl line whose note carries the grant hash, so the existing audit trail is complete and a reader can tell user-grant approvals from owner ones;
  * the grant is a plain object created by the server after the user's confirmation; it is not a capability a client can present. The spend gate and ledger ceiling (= the budget) are enforced
    independently inside the pipeline, so even an approved stage cannot spend beyond the budget."""
from __future__ import annotations

import json
import time
from typing import Any

from ..suite.core import canonical_hash

LIVE_STAGES = ("taskgen", "baseline_trials", "investigate")          # the ONLY stages a user grant can approve (the paid stages of one evaluation, no fix, no retest)
GRANT_FIELDS = ("job_id", "owner", "run_id", "target_id", "goal", "budget_usd", "stages", "model", "endpoint", "snapshot_sha256", "limits")
CAP_KEYS = ("run_cap_usd", "stage_cap_usd", "worst_case_stage_usd", "ledger_ceiling_usd")


class GrantRefused(Exception):
    def __init__(self, reason: str, kind: str = "scope"):
        super().__init__(reason)
        self.reason, self.kind = reason, kind                       # kind: scope | budget | integrity


SMOKE_CAP_USD = 0.15                                                   # the existing task-generation allocation; a smoke job is granted exactly this and nothing else
SMOKE_STAGES = ("taskgen",)


def default_limits(n_tasks: int = 4, smoke: bool = False) -> dict:
    """The SHAPE of the run the user approved, not just its total: per-stage caps (the existing allocation), the task count, one repeat, the per-request cap. A manifest that asks for more is refused
    even when the total would still fit the budget."""
    from ..investigate import allocation as alloc
    caps = {"taskgen": alloc.TASKGEN_CAP_USD} if smoke else {"taskgen": alloc.TASKGEN_CAP_USD, "baseline_trials": alloc.BASELINE_CAP_USD, "investigate": alloc.INVESTIGATE_CAP_USD}
    return {"stage_caps_usd": caps, "max_tasks": n_tasks, "repeats": 1, "per_request_cap_usd": alloc.PER_REQUEST_CAP_USD, "max_retries_per_request": 0 if smoke else 1}


def make_grant(*, job_id: str, owner: str, target_id: str, goal: str, budget_usd: float, model: str, endpoint: str, snapshot_sha256: str, stages=LIVE_STAGES, limits: dict | None = None) -> dict:
    g = {"job_id": job_id, "owner": owner, "run_id": job_id, "target_id": target_id, "goal": goal, "budget_usd": round(float(budget_usd), 6), "stages": list(stages), "model": model,
         "endpoint": endpoint, "snapshot_sha256": snapshot_sha256, "limits": limits or default_limits()}
    return {**g, "confirmed_at": time.time(), "grant_sha256": digest(g)}


def digest(fields: dict) -> str:
    return canonical_hash({k: fields[k] for k in GRANT_FIELDS})


def verify(grant: dict, *, job_id: str, owner: str, run_id: str) -> None:
    if not isinstance(grant, dict) or any(k not in grant for k in (*GRANT_FIELDS, "grant_sha256")):
        raise GrantRefused("the grant is incomplete", "integrity")
    if digest(grant) != grant["grant_sha256"]:
        raise GrantRefused("the grant does not match its hash (altered)", "integrity")
    if (grant["job_id"], grant["owner"], grant["run_id"]) != (job_id, owner, run_id):
        raise GrantRefused("the grant belongs to a different job, owner or run", "scope")
    if not (0 < grant["budget_usd"] <= 100) or any(s not in LIVE_STAGES for s in grant["stages"]):
        raise GrantRefused("the grant lists an unsupported budget or stage", "scope")


def _caps(manifest: dict) -> list[float]:
    out = [float(manifest[k]) for k in CAP_KEYS if isinstance(manifest.get(k), (int, float))]
    alloc = manifest.get("allocation") or {}
    if isinstance(alloc.get("ledger_ceiling_usd"), (int, float)):
        out.append(float(alloc["ledger_ceiling_usd"]))
    return out


class Approver:
    def __init__(self, grant: dict, *, job_id: str, owner: str, run_id: str):
        verify(grant, job_id=job_id, owner=owner, run_id=run_id)
        self.grant, self.ids = grant, (job_id, owner, run_id)

    def decide(self, run, stage: str, manifest_sha256: str, manifest: dict, committed_usd: float) -> dict:
        """Record the approval of exactly this stage manifest, or raise GrantRefused. Never approves a stage or a hash it was not shown by THIS run."""
        g = self.grant
        verify(g, job_id=self.ids[0], owner=self.ids[1], run_id=self.ids[2])
        if run.dir.name != g["run_id"] or run.state["id"] != g["run_id"]:
            raise GrantRefused("this run is not the run the grant was issued for", "scope")
        if run.mode != "live":
            raise GrantRefused("only a live run needs or may receive a spend approval", "scope")
        if stage not in g["stages"] or manifest.get("stage") != stage:
            raise GrantRefused(f"stage {stage!r} is outside what the user approved ({', '.join(g['stages'])})", "scope")
        if run.manifest_sha256(manifest) != manifest_sha256:
            raise GrantRefused("the manifest hash does not match the manifest presented", "integrity")
        if manifest.get("model") != g["model"] or str(manifest.get("endpoint", "")).rstrip("/").removesuffix("/chat/completions") != g["endpoint"].rstrip("/"):
            raise GrantRefused("the manifest names a different model or endpoint than the one approved", "scope")
        if manifest.get("snapshot_sha256") not in (None, g["snapshot_sha256"]):
            raise GrantRefused("the manifest is for a different website capture than the one approved", "scope")
        lim = g["limits"]
        stage_limit = lim["stage_caps_usd"].get(stage)
        own = manifest.get("stage_cap_usd") if stage == "baseline_trials" else manifest.get("run_cap_usd")          # the cap the spend gate actually enforces for that stage
        if stage_limit is None or not isinstance(own, (int, float)) or float(own) > stage_limit + 1e-9:
            raise GrantRefused(f"the {stage} manifest's stage cap (US${own}) exceeds what the user approved for it (US${stage_limit})", "budget")
        if isinstance(manifest.get("per_request_cap_usd"), (int, float)) and manifest["per_request_cap_usd"] > lim["per_request_cap_usd"] + 1e-9:
            raise GrantRefused("the manifest raises the per-request cap above the approved one", "budget")
        if stage == "baseline_trials" and (manifest.get("repeats", 1) > lim["repeats"] or len(manifest.get("task_ids", [])) > lim["max_tasks"] or manifest.get("retries", 0) != 0):
            raise GrantRefused("the baseline manifest runs more tasks, repeats or retries than the user approved", "scope")
        if stage == "taskgen" and (manifest.get("target_tasks", lim["max_tasks"]) > lim["max_tasks"] or manifest.get("retries_per_request", 0) > lim["max_retries_per_request"]):
            raise GrantRefused("the taskgen manifest asks for more tasks or retries than the user approved", "scope")
        if stage == "investigate" and manifest.get("retries_per_request", 0) > lim["max_retries_per_request"]:
            raise GrantRefused("the investigate manifest asks for more retries than the user approved", "scope")
        caps = _caps(manifest)
        if not caps or any(c > g["budget_usd"] + 1e-9 for c in caps):
            raise GrantRefused(f"a cap in the {stage} manifest (US${max(caps or [0]):.2f}) exceeds the approved budget (US${g['budget_usd']:.2f})", "budget")
        stage_cap = next((float(manifest[k]) for k in ("stage_cap_usd", "worst_case_stage_usd", "run_cap_usd") if isinstance(manifest.get(k), (int, float))), None)
        if stage_cap is None or committed_usd + stage_cap > g["budget_usd"] + 1e-9:
            raise GrantRefused(f"committed US${committed_usd:.4f} plus the {stage} cap would exceed the approved budget US${g['budget_usd']:.2f}", "budget")
        note = (f"USER-GRANT approval (not an owner CLI approval): grant {g['grant_sha256'][:16]} job {g['job_id']} owner-session {g['owner'][:8]} target {g['target_id']} "
                f"budget US${g['budget_usd']:.2f} stages {','.join(g['stages'])}; confirmed in the UI at {int(g['confirmed_at'])}; stage {stage} within caps")
        return run.approve(stage, manifest_sha256, note)
