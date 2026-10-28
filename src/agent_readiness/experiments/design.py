"""The pre-registered Task 012 matrix (docs/TASK012_EXPERIMENT_PLAN.md). Changing anything here changes the schedule hash and requires re-approval."""
from __future__ import annotations

EXPERIMENT_ID = "task012-electronics-v1"
ENVIRONMENT = "electronics-v1"
PRIMARY_TASKS = {"T1": "t1-anc-headphones-under-250-all", "T2": "t2-compare-air14-vs-probook15", "T3": "t3-cheapest-monitor-27in-usbc-120hz", "T4": "t4-policy-delivery-tessera-whisper"}
VARIANTS = {"V0": ("listing", "structured"), "V1": ("detail", "structured"), "V2": ("listing", "fragmented"), "V3": ("detail", "fragmented")}


def variant_id(code: str) -> str:
    a, s = VARIANTS[code]
    return f"{ENVIRONMENT}/availability-{a}+specs-{s}"


# stage -> {task code: [(variant code, runs per cell)]}; blocks = number of randomization blocks
STAGES = {
    1: {"purpose": "feasibility + combined-change SENSITIVITY test (V0 vs V3 change both factors; NOT a causal comparison)", "blocks": 2, "stage_ceiling_usd": 4.00,
        "cells": {"T1": {"V0": 1, "V3": 1}, "T2": {"V0": 1, "V3": 1}, "T3": {"V0": 1, "V3": 1}, "T4": {"V0": 1, "V3": 1}}},
    2: {"purpose": "focused single-factor study (availability V0 vs V1; specs V0 vs V2; T2 availability = placebo; T4 = control)", "blocks": 3, "stage_ceiling_usd": 4.50,
        "cells": {"T1": {"V0": 3, "V1": 3, "V2": 3}, "T3": {"V0": 3, "V1": 3, "V2": 3}, "T2": {"V0": 3, "V1": 3, "V2": 3}, "T4": {"V0": 2}}},
}
PROGRAMME_CEILING_USD = 6.00
RUN_RESERVE_USD = 0.48           # 12 requests x US$0.04 estimate ceiling
EXPECTED_COST_PER_RUN_USD = (0.086, 0.129)       # Task 011 mean x 1.0 .. 1.5
HALT_INFRA_ERRORS = 2
HALT_RECOVERY_REJECTED_PER_BLOCK = 2
GUARD_STOPS = {"diagnostic_fidelity_violation", "estimated_cost_limit"}
INFRA_STOPS = {"infrastructure_error"}
