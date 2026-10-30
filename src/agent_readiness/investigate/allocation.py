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


def post_trials_caps(ledger_ceiling_usd: float, imported_committed_usd: float | None = None) -> dict:
    """The post_trials spending limits. `fits_ceiling` is only decidable when the spend already committed (a fork's imported history) is known."""
    out = {"patched_arm": PATCHED_ARM_CAP_USD, "placebo_arm": PLACEBO_ARM_CAP_USD, "post_trials_combined": POST_TRIALS_CAP_USD, "per_request": PER_REQUEST_CAP_USD, "ledger_ceiling": ledger_ceiling_usd}
    if imported_committed_usd is not None:
        out |= {"imported_committed_usd": imported_committed_usd, "headroom_after_combined_cap_usd": round(ledger_ceiling_usd - imported_committed_usd - POST_TRIALS_CAP_USD, 6),
                "combined_cap_fits_ceiling": ledger_ceiling_usd + 1e-9 >= imported_committed_usd + POST_TRIALS_CAP_USD}
    return out
