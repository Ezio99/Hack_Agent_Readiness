"""Experiment-2 cost model. Every number is a CALCULATED estimate at the published muse-spark-1.3 prices (US$1.25 / 4.25 per million input / output tokens), never a bill.

Calibration (read from the published EXP-B report; EXP-B's ledger is not touched): a trial cost about US$0.0115 to 0.0133 per model request on tiny pages (2 to 13 requests, US$0.023 to 0.177).
Ironbark pages are larger (product pages carry specification tables, calendars carry 56 cells), so the planning rate is higher and, above all, UNCERTAIN: the pilot phase exists to replace these
assumptions with measured values before the main baseline is approved. All parameters below are assumptions, shown in every manifest."""
from __future__ import annotations

from dataclasses import dataclass

CEILING_USD = 20.0                    # hard ceiling of the whole Experiment 2, enforced by its own durable ledger
RESERVE_USD = 2.5                     # never allocated to a phase; spendable only by a new, explicit owner decision
PER_REQUEST_CAP_USD = 0.05            # the spend gate refuses any single request whose upper bound exceeds this
PER_TRIAL_CAP_USD = 0.75              # the spend gate refuses any single trial that would exceed this
USD_PER_REQUEST_P50 = 0.016           # planning rate (EXP-B 0.0115-0.0133 on tiny pages + larger Ironbark pages)
USD_PER_REQUEST_P90 = 0.024
MIN_STEPS, MAX_STEPS = 10, 30


def step_limit(pages_needed: int) -> int:
    """Per-task cap on model requests (and agent steps): enough to read every needed page twice, never more than 30."""
    return max(MIN_STEPS, min(MAX_STEPS, 6 + 3 * pages_needed))


def expected_requests(pages_needed: int) -> tuple[float, float]:
    """(typical, p90) model requests for one trial; both capped by the step limit. Assumption: about 2.2 requests per needed page plus 3 for navigation and the answer."""
    lim = step_limit(pages_needed)
    return min(lim, 2.2 * pages_needed + 3), min(lim, 1.6 * (2.2 * pages_needed + 3))


def trial_cost(pages_needed: int, per_request=(USD_PER_REQUEST_P50, USD_PER_REQUEST_P90)) -> tuple[float, float]:
    e, hi = expected_requests(pages_needed)
    return round(e * per_request[0], 4), round(hi * per_request[1], 4)


@dataclass
class PhaseCost:
    trials: int
    p50_usd: float
    p90_trial_usd: float            # the largest single trial at p90 (the per-trial cap is never below it)
    cap_usd: float


CAP_MARGIN = 1.3                    # a phase may spend up to 30 % over its expected (p50) total before the spend gate stops it


def round_up_5c(x: float) -> float:
    return round(-(-x * 20 // 1) / 20, 2)


def phase_cost(pages: list[int], *, per_request=(USD_PER_REQUEST_P50, USD_PER_REQUEST_P90), margin: float = CAP_MARGIN) -> PhaseCost:
    """`pages` = pages_needed of every trial in the phase. Cap = expected total x margin (rounded up to 5 cents). A phase that costs more than that is STOPPED by the gate, not topped up."""
    p50 = sum(trial_cost(p, per_request)[0] for p in pages)
    worst = max((trial_cost(p, per_request)[1] for p in pages), default=0.0)
    return PhaseCost(len(pages), round(p50, 2), round(worst, 2), round_up_5c(p50 * margin))


def allocation(pilot: PhaseCost, main: PhaseCost, *, investigator_usd: float = 0.80, ceiling: float = CEILING_USD, reserve: float = RESERVE_USD) -> dict:
    """Hard allocation of the US$20 ceiling. Variant tests receive whatever is left after the baseline phases, the investigator and the reserve; they are sized from this, never beyond it."""
    allocatable = round(ceiling - reserve, 2)
    used = round(pilot.cap_usd + main.cap_usd + investigator_usd, 2)
    return {"ceiling_usd": ceiling, "reserve_usd": reserve, "allocatable_usd": allocatable, "baseline_pilot_cap_usd": pilot.cap_usd, "baseline_main_cap_usd": main.cap_usd, "investigator_cap_usd": investigator_usd,
            "variant_tests_cap_usd": round(allocatable - used, 2), "fits": used <= allocatable, "note": "the variant-test cap is what remains if every earlier phase spends its full cap; unspent money rolls into it only by a new owner approval"}


def trim_to_cap(pages_in_order: list[int], cap: float, per_request=(USD_PER_REQUEST_P50, USD_PER_REQUEST_P90), margin: float = CAP_MARGIN) -> int:
    """How many trials of an ordered plan fit under `cap` at the given per-request rate (used after the pilot, when the rate has been measured). The plan's order puts the most valuable trials first,
    so trimming drops the second repeats and the last tasks, never the first coverage of a family."""
    total, n = 0.0, 0
    for p in pages_in_order:
        nxt = total + trial_cost(p, per_request)[0]
        if round_up_5c(nxt * margin) > cap + 1e-9:
            break
        total, n = nxt, n + 1
    return n
