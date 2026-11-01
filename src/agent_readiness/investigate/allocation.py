"""Spending allocation for one investigation (Task 016 L1a). Stage caps are enforced by the spend gate (reserve-before-send, counted in the shared ledger); the ledger ceiling
(`--total-cap-usd`) is the hard bound on everything. Every approval manifest lists this allocation so the approved numbers are the enforced ones."""
from __future__ import annotations

TASKGEN_CAP_USD = 0.15
BASELINE_CAP_USD = 1.40
INVESTIGATE_CAP_USD = 0.40
PER_REQUEST_CAP_USD = 0.05
# Post-fix retest (exploratory experiment): arm caps and their combined cap, all enforced by the durable spend gate and listed in the post_trials manifest.
PATCHED_ARM_CAP_USD = 0.80
PLACEBO_ARM_CAP_USD = 0.55
POST_TRIALS_CAP_USD = 1.35


def allocation(ledger_ceiling_usd: float) -> dict:
    allocated = round(TASKGEN_CAP_USD + BASELINE_CAP_USD + INVESTIGATE_CAP_USD, 6)
    return {"stage_caps_usd": {"taskgen": TASKGEN_CAP_USD, "baseline_trials": BASELINE_CAP_USD, "investigate": INVESTIGATE_CAP_USD}, "allocated_usd": allocated,
            "ledger_ceiling_usd": ledger_ceiling_usd, "unallocated_usd": round(ledger_ceiling_usd - allocated, 6), "allocation_fits_ceiling": ledger_ceiling_usd + 1e-9 >= allocated}


MAX_ARM_CAP_USD = 1.00      # an owner plan may raise an arm cap (e.g. one placebo trial per affected task) but never above this


def post_trials_caps(ledger_ceiling_usd: float, imported_committed_usd: float | None = None, overrides: dict | None = None) -> dict:
    """The post_trials spending limits. `fits_ceiling` is only decidable when the spend already committed (a fork's imported history) is known. `overrides` (from an owner plan, hashed in the manifest) may set
    `patched_arm` and `placebo_arm`; the combined cap is then their sum. Without overrides the numbers are exactly the constants above."""
    patched, placebo, combined = PATCHED_ARM_CAP_USD, PLACEBO_ARM_CAP_USD, POST_TRIALS_CAP_USD
    if overrides:
        unknown = set(overrides) - {"patched_arm", "placebo_arm"}
        if unknown or any(not isinstance(v, (int, float)) or not 0 < v <= MAX_ARM_CAP_USD for v in overrides.values()):
            raise ValueError(f"plan caps_usd may set patched_arm and placebo_arm, each in (0, {MAX_ARM_CAP_USD}]")
        patched, placebo = overrides.get("patched_arm", patched), overrides.get("placebo_arm", placebo)
        combined = round(patched + placebo, 6)
    out = {"patched_arm": patched, "placebo_arm": placebo, "post_trials_combined": combined, "per_request": PER_REQUEST_CAP_USD, "ledger_ceiling": ledger_ceiling_usd}
    if imported_committed_usd is not None:
        out |= {"imported_committed_usd": imported_committed_usd, "headroom_after_combined_cap_usd": round(ledger_ceiling_usd - imported_committed_usd - combined, 6),
                "combined_cap_fits_ceiling": ledger_ceiling_usd + 1e-9 >= imported_committed_usd + combined}
    return out
