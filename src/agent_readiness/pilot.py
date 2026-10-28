"""Task 006 Stage 2 sequential driver: a fixed, auditable, resumable schedule that never repeats a run.

The driver executes the pre-registered 24-run schedule one run at a time. All state is persisted atomically before and
after every run. A halt is persisted and blocks further execution until a human records an explicit approval with
``resume``; a started run is never repeated by the driver (an interrupted one is marked ``interrupted`` and stays so).
Live execution additionally needs --allow-model-calls and the exact schedule hash, so no approval is implied by running
``plan``/``status`` or by a smoke-mode rehearsal."""
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from .agent import profile
from .capture import FULL_AGENT_SCHEMA_SHA256
from .storefront import VARIANT_AVAIL_ID, VARIANT_B_ID, VARIANT_ID

STATE_FILE = "pilot-state.json"
ARM_VARIANT = {"A": VARIANT_ID, "B": VARIANT_B_ID}
BLOCKS = ((2, "ABBA"), (9, "BAAB"), (7, "BAAB"), (5, "ABBA"), (14, "ABBA"), (13, "BAAB"))
FROZEN = {"profile_id": "natural-shopping-v3-compat1", "provider": "meta", "model": "muse-spark-1.3", "kind": "discovery",
          "max_steps": 6, "max_model_requests": 6, "timeout_seconds": 120, "max_estimated_cost_usd": 0.04,
          "max_cumulative_estimated_cost_usd": 0.25, "expect_schema_sha256": FULL_AGENT_SCHEMA_SHA256}
LIMITS = {"pilot_estimated_cap_usd": 6.00, "review_halt_actual_usd": 2.00, "max_consecutive_model_output_errors": 2}
HALT_STATUSES = {"diagnostic_fidelity_violation": "fidelity_violation", "estimated_cost_limit": "cost_cap_block",
                 "infrastructure_error": "infrastructure_failure", "setup_error": "setup_failure"}


# ---- Task 007: availability on listing cards (A) vs detail pages only (B = the unchanged baseline) ----------------
# Deviations from the Task 005/006 configuration (identical across arms; everything else - profile text, model, parameters,
# parser, guard semantics, per-request ceiling - is unchanged): kind instock_max; 12 steps / 12 requests / 240 s instead of
# 6 / 6 / 120 s; per-run cumulative estimated cap US$0.48 instead of 0.25; pilot cap US$15.00 and review halt US$4.00.
ARM_VARIANT_007 = {"A": VARIANT_AVAIL_ID, "B": VARIANT_ID}
BLOCKS_007 = ((0, "ABBAAB"), (4, "BAABBA"), (1, "ABBAAB"), (3, "BAABBA"), (2, "ABBAAB"))   # seed -> scope Home, Kitchen*, Outdoors, Bags, Fern
FROZEN_007 = {**FROZEN, "kind": "instock_max", "max_steps": 12, "max_model_requests": 12, "timeout_seconds": 240,
              "max_cumulative_estimated_cost_usd": 0.48}
LIMITS_007 = {"pilot_estimated_cap_usd": 15.00, "review_halt_actual_usd": 4.00, "max_consecutive_model_output_errors": 2}
DEFAULT_STATE_DIR = {"006": "runs/pilot-task006", "007": "runs/pilot-task007"}


def _spec(experiment):
    """(blocks, arm->variant, frozen, limits), read at call time so tests can adjust them."""
    if experiment == "006":
        return BLOCKS, ARM_VARIANT, FROZEN, LIMITS
    if experiment == "007":
        return BLOCKS_007, ARM_VARIANT_007, FROZEN_007, LIMITS_007
    raise PilotError(f"Unknown experiment {experiment!r}")


class PilotError(RuntimeError):
    pass


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def build_schedule(experiment="006"):
    blocks, arm_variant, _, _ = _spec(experiment)
    entries = []
    for block, (seed, pattern) in enumerate(blocks, 1):
        seen = {"A": 0, "B": 0}
        for slot, arm in enumerate(pattern, 1):
            seen[arm] += 1
            entries.append({"entry_id": f"{len(entries) + 1:02d}-s{seed:02d}-{arm}{seen[arm]}", "position": len(entries) + 1,
                            "block": block, "slot": slot, "seed": seed, "arm": arm, "repetition": seen[arm],
                            "storefront_variant": arm_variant[arm]})
    return entries


def frozen_config(experiment="006"):
    frozen = _spec(experiment)[2]
    return {**frozen, "profile_sha256": hashlib.sha256(json.dumps(profile(frozen["profile_id"]), sort_keys=True).encode()).hexdigest()}


def schedule_sha256(entries=None, frozen=None, limits=None, experiment="006"):
    body = {"entries": entries or build_schedule(experiment), "frozen": frozen or frozen_config(experiment),
            "limits": limits or _spec(experiment)[3]}
    if experiment != "006":
        body["experiment"] = experiment      # Task 006's published hash is unchanged
    return hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def load(state_dir):
    path = Path(state_dir) / STATE_FILE
    if not path.exists():
        raise PilotError(f"No pilot state in {state_dir}; run 'readiness pilot plan' first")
    return json.loads(path.read_text())


def save(state_dir, state):
    """Atomic: write a temporary file, flush it to disk, then rename."""
    path = Path(state_dir) / STATE_FILE
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w") as handle:
        handle.write(json.dumps(state, indent=2, sort_keys=True))
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)


def audit(state, event, **data):
    state["audit"].append({"at": now(), "event": event, **data})


def plan(state_dir, mode="live", experiment="006"):
    """Create (or verify) the persisted schedule. Idempotent; never alters an existing, different schedule."""
    if mode not in {"live", "smoke"}:
        raise PilotError("mode must be live or smoke")
    Path(state_dir).mkdir(parents=True, exist_ok=True)
    entries, frozen, limits = build_schedule(experiment), frozen_config(experiment), dict(_spec(experiment)[3])
    digest = schedule_sha256(entries, frozen, limits, experiment)
    if (Path(state_dir) / STATE_FILE).exists():
        state = load(state_dir)
        if state["schedule_sha256"] != digest or state["mode"] != mode:
            raise PilotError("Existing pilot state has a different schedule, configuration or mode; use a new state directory")
        return state
    state = {"schema": "pilot-state-v1", "task": experiment, "mode": mode, "created_at": now(), "schedule_sha256": digest,
             "frozen": frozen, "limits_approved": dict(limits), "limits": dict(limits), "halt": None, "fingerprint": None,
             "entries": [{**e, "status": "pending"} for e in entries], "audit": []}
    audit(state, "planned", mode=mode, schedule_sha256=digest)
    save(state_dir, state)
    return state


def spend(state):
    done = [e for e in state["entries"] if e["status"] == "done"]
    return {"runs_done": len(done),
            "worst_case_sent_usd": round(sum(((e.get("result") or {}).get("worst_case_sent_usd") or 0) for e in done), 5),
            "calculated_actual_usd": round(sum(((e.get("result") or {}).get("calculated_actual_usd") or 0) for e in done), 5)}


def set_halt(state, kind, detail, entry_id=None):
    state["halt"] = {"kind": kind, "detail": detail, "entry_id": entry_id, "at": now(), "resolved": False}
    audit(state, "halt", kind=kind, detail=detail, entry_id=entry_id)


def summarize(record, path):
    metrics = record.get("metrics") or {}
    prov = record.get("provenance") or {}
    return {
        "run_id": record.get("run_id"), "artifact_path": str(path), "run_status": record.get("status"),
        "stop_reason": record.get("stop_reason"), "evaluator_passed": (record.get("evaluation") or {}).get("passed"),
        "storefront_variant": record.get("storefront_variant"), "model_request_count": record.get("model_request_count"),
        "worst_case_sent_usd": (record.get("estimated_cost") or {}).get("cumulative_estimated_sent_usd"),
        "calculated_actual_usd": (metrics.get("cost") or {}).get("calculated_actual_usd"),
        "tokens": metrics.get("tokens"), "navigation": metrics.get("navigation"), "strategy": metrics.get("strategy"),
        "protocol_compliance": record.get("protocol_compliance"), "elapsed_seconds": record.get("elapsed_seconds"),
        "fingerprint": {"profile_hash": record.get("profile_hash"), "configuration_hash": record.get("configuration_hash"),
                        "browser_version": record.get("browser_version"), "inventory_hash": record.get("inventory_hash"),
                        "model": (record.get("model") or {}).get("model"), "code_hash": prov.get("code_hash"),
                        "git_commit": prov.get("git_commit"), "packages": prov.get("packages")},
    }


def evaluate_halts(state, entry):
    """Post-run stopping conditions; returns (kind, detail) or None."""
    result = entry["result"]
    status = result["run_status"]
    if status in HALT_STATUSES:
        return HALT_STATUSES[status], f"run status {status} ({result.get('stop_reason')})"
    fingerprint = result["fingerprint"]
    if state["fingerprint"] is None:
        state["fingerprint"] = fingerprint
    elif fingerprint != state["fingerprint"]:
        changed = sorted(k for k in fingerprint if fingerprint[k] != state["fingerprint"].get(k))
        return "version_drift", f"fingerprint changed: {', '.join(changed)}"
    done = [e for e in state["entries"] if e["status"] == "done"]
    limit = state["limits"]["max_consecutive_model_output_errors"]
    tail = [e["result"]["run_status"] == "model_output_error" for e in done[-limit:]]
    if len(tail) == limit and all(tail):
        return "consecutive_model_output_errors", f"{limit} consecutive model_output_error runs"
    totals = spend(state)
    if totals["calculated_actual_usd"] > state["limits"]["review_halt_actual_usd"]:
        return "review_spend", f"calculated actual spend US${totals['calculated_actual_usd']} exceeds review threshold US${state['limits']['review_halt_actual_usd']}"
    return None


def preflight(state, mode, allow_model_calls, approved_sha):
    """Everything that must hold before a run (and so before any paid call) is started."""
    if state["mode"] != mode:
        raise PilotError(f"State directory is a {state['mode']} pilot; refusing to run it as {mode}")
    if schedule_sha256(entries=[{k: e[k] for k in ("entry_id", "position", "block", "slot", "seed", "arm", "repetition", "storefront_variant")}
                                for e in state["entries"]], frozen=state["frozen"], limits=state["limits_approved"],
                         experiment=state["task"]) != state["schedule_sha256"]:
        raise PilotError("Persisted schedule no longer matches its recorded hash")
    changed = {k for k in state["limits"] if state["limits"][k] != state["limits_approved"][k]}
    if changed - {"review_halt_actual_usd"}:
        raise PilotError(f"Pilot limits were altered outside the approved schedule: {sorted(changed)}")
    if "review_halt_actual_usd" in changed and not any(a["event"] == "resume_approved" and a.get("new_review_halt_usd") == state["limits"]["review_halt_actual_usd"] for a in state["audit"]):
        raise PilotError("The review threshold was changed without a recorded approval")
    if mode == "live":
        if not allow_model_calls:
            raise PilotError("Model calls disabled; explicit spending approval is required (--allow-model-calls)")
        if approved_sha != state["schedule_sha256"]:
            raise PilotError("--approved-schedule-sha256 must equal the approved schedule hash")
        if frozen_config(state["task"]) != state["frozen"]:
            raise PilotError("The frozen profile/configuration differs from the persisted schedule")
    if state["halt"] and not state["halt"]["resolved"]:
        raise PilotError(f"Pilot halted ({state['halt']['kind']}): {state['halt']['detail']}. Resuming needs explicit approval via 'readiness pilot resume'")


def recover_interrupted(state_dir, state):
    changed = False
    for entry in state["entries"]:
        if entry["status"] == "running":
            entry["status"] = "interrupted"
            entry["finished_at"] = now()
            set_halt(state, "interrupted_run", f"run {entry['entry_id']} was started but never recorded as finished; spend unknown; it will not be repeated", entry["entry_id"])
            changed = True
    if changed:
        save(state_dir, state)


def resume(state_dir, approval_note, new_review_halt_usd=None):
    """Record an explicit human approval that clears the current halt. Never re-runs anything."""
    state = load(state_dir)
    halt = state["halt"]
    if not halt or halt["resolved"]:
        raise PilotError("No unresolved halt")
    if not (approval_note or "").strip():
        raise PilotError("An approval note is required to resume")
    if halt["kind"] == "review_spend":
        current = spend(state)["calculated_actual_usd"]
        if new_review_halt_usd is None or new_review_halt_usd <= current:
            raise PilotError(f"Review halt needs a new threshold above the current calculated spend (US${current})")
        state["limits"]["review_halt_actual_usd"] = new_review_halt_usd
    elif new_review_halt_usd is not None:
        raise PilotError("--new-review-halt-usd only applies to a review_spend halt")
    halt["resolved"] = True
    halt["resolved_at"] = now()
    audit(state, "resume_approved", halt_kind=halt["kind"], note=approval_note.strip(), new_review_halt_usd=new_review_halt_usd)
    # The raised threshold is recorded in the audit trail; the schedule hash stays tied to the originally approved limits.
    save(state_dir, state)
    return state


async def drive(state_dir, run_fn, *, mode="live", allow_model_calls=False, approved_schedule_sha256=None, max_runs=None,
                model_config=None):
    """Execute pending runs in order until done, ``max_runs`` or a halt. Returns the final state."""
    state = load(state_dir)
    recover_interrupted(state_dir, state)
    state = load(state_dir)
    preflight(state, mode, allow_model_calls, approved_schedule_sha256)
    executed = 0
    for entry in state["entries"]:
        if entry["status"] != "pending":
            continue
        if max_runs is not None and executed >= max_runs:
            break
        totals = spend(state)
        committed = totals["worst_case_sent_usd"] + state["frozen"]["max_cumulative_estimated_cost_usd"]
        if committed > state["limits"]["pilot_estimated_cap_usd"] + 1e-9:
            set_halt(state, "pilot_estimated_cap", f"worst-case committed US${round(committed, 5)} would exceed US${state['limits']['pilot_estimated_cap_usd']}", entry["entry_id"])
            save(state_dir, state)
            break
        entry["status"] = "running"
        entry["started_at"] = now()
        audit(state, "run_started", entry_id=entry["entry_id"])
        save(state_dir, state)   # persisted BEFORE the run: a crash leaves 'running', never a repeatable 'pending'
        frozen = state["frozen"]
        kwargs = dict(mode=mode, seed=entry["seed"], kind=frozen["kind"], output=Path(state_dir) / "runs",
                      storefront_variant=entry["storefront_variant"], max_steps=frozen["max_steps"],
                      timeout_seconds=frozen["timeout_seconds"], max_model_requests=frozen["max_model_requests"])
        if mode == "live":
            kwargs.update(allow_model_calls=True, profile_id=frozen["profile_id"], model_config=model_config,
                          expect_schema_sha256=frozen["expect_schema_sha256"],
                          max_estimated_cost_usd=frozen["max_estimated_cost_usd"],
                          max_cumulative_estimated_cost_usd=frozen["max_cumulative_estimated_cost_usd"])
        try:
            path, record = await run_fn(**kwargs)
        except BaseException as exc:  # the run is NOT repeated
            entry["status"] = "done"
            entry["finished_at"] = now()
            entry["result"] = {"run_status": "driver_exception", "stop_reason": type(exc).__name__, "evaluator_passed": None,
                               "worst_case_sent_usd": None, "calculated_actual_usd": None}
            set_halt(state, "driver_exception", f"{type(exc).__name__} while executing {entry['entry_id']}", entry["entry_id"])
            save(state_dir, state)
            if not isinstance(exc, Exception):
                raise
            break
        entry["status"] = "done"
        entry["finished_at"] = now()
        entry["result"] = summarize(record, path)
        executed += 1
        audit(state, "run_finished", entry_id=entry["entry_id"], run_status=record.get("status"))
        halt = evaluate_halts(state, entry)
        if halt:
            set_halt(state, halt[0], halt[1], entry["entry_id"])
        save(state_dir, state)
        if halt:
            break
    return state


def status_text(state):
    totals = spend(state)
    lines = [f"mode={state['mode']} schedule={state['schedule_sha256'][:12]}… runs_done={totals['runs_done']}/{len(state['entries'])} "
             f"worst_case_sent=US${totals['worst_case_sent_usd']} calculated_actual=US${totals['calculated_actual_usd']}"]
    halt = state["halt"]
    lines.append("halt: " + (f"{halt['kind']} ({'resolved' if halt['resolved'] else 'UNRESOLVED'}): {halt['detail']}" if halt else "none"))
    for e in state["entries"]:
        r = e.get("result") or {}
        lines.append(f"{e['entry_id']:>14} {e['storefront_variant'][:12]:<12} {e['status']:<11} {r.get('run_status', ''):<24} pass={r.get('evaluator_passed')} run={r.get('run_id', '')}")
    return "\n".join(lines)
