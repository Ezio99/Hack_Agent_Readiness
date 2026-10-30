"""Spending allocation for one investigation (Task 016 L1a). Stage caps are enforced by the spend gate (reserve-before-send, counted in the shared ledger); the ledger ceiling
(`--total-cap-usd`) is the hard bound on everything. Every approval manifest lists this allocation so the approved numbers are the enforced ones."""
from __future__ import annotations

TASKGEN_CAP_USD = 0.15
BASELINE_CAP_USD = 1.40
INVESTIGATE_CAP_USD = 0.40
PER_REQUEST_CAP_USD = 0.05


def allocation(ledger_ceiling_usd: float) -> dict:
    allocated = round(TASKGEN_CAP_USD + BASELINE_CAP_USD + INVESTIGATE_CAP_USD, 6)
    return {"stage_caps_usd": {"taskgen": TASKGEN_CAP_USD, "baseline_trials": BASELINE_CAP_USD, "investigate": INVESTIGATE_CAP_USD}, "allocated_usd": allocated,
            "ledger_ceiling_usd": ledger_ceiling_usd, "unallocated_usd": round(ledger_ceiling_usd - allocated, 6), "allocation_fits_ceiling": ledger_ceiling_usd + 1e-9 >= allocated}
