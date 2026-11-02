"""Stage A stopping rule (proposal §3.1, decision 3, provisional): stop when
  targets_met          every coverage target of the current selection is met
  max_rounds           the round limit (default 3) is reached
  diminishing_returns  `patience` consecutive rounds (default 2) each added fewer than `min_useful` (default 2) useful tasks
  budget_cap           the next round's worst-case reservation would take the spend above the cap (checked before every round, including the first)
A useful task is newly admitted in the round and fills a persona x journey cell or a capability the admitted pool did not have, or is natural while
the pool's natural share is below the aspiration. Thresholds are never lowered to meet a target: unmet targets go to the gap report."""
from __future__ import annotations

from dataclasses import asdict, dataclass

from ...taskeval.v2 import coverage as COV

VERSION = "stopping-1"


@dataclass(frozen=True)
class StopRule:
    max_rounds: int = 3
    budget_cap_usd: float = 0.0
    min_useful: int = 2
    patience: int = 2

    def as_dict(self) -> dict:
        return {"version": VERSION, **asdict(self)}


def useful_additions(before: list[dict], new: list[dict], aspiration: float = COV.TARGETS["natural_share_aspiration"]) -> list[str]:
    def admitted(rs):
        return [r for r in rs if r["admission"] in ("natural", "assisted", "rubric")]
    pool = admitted(before)
    cells = {(r["persona"], r["journey"]) for r in pool if r["journey_consistent"]}
    caps = {r["capability"] for r in pool}
    det = [r for r in pool if r["verifiability"] == "deterministic"]
    share = sum(r["admission"] == "natural" for r in det) / len(det) if det else 0.0
    out = []
    for r in admitted(new):
        if (r["journey_consistent"] and (r["persona"], r["journey"]) not in cells) or r["capability"] not in caps or (r["admission"] == "natural" and share < aspiration):
            out.append(r["candidate_id"])
            cells.add((r["persona"], r["journey"]))
            caps.add(r["capability"])
    return out


def before_round(rule: StopRule, spent_usd: float, reservation_usd: float) -> str | None:
    if rule.budget_cap_usd is not None and spent_usd + reservation_usd > rule.budget_cap_usd + 1e-12:
        return "budget_cap"
    return None


def after_round(rule: StopRule, round_no: int, targets_met: bool, useful_history: list[int]) -> str | None:
    if targets_met:
        return "targets_met"
    if round_no >= rule.max_rounds:
        return "max_rounds"
    if len(useful_history) >= rule.patience and all(n < rule.min_useful for n in useful_history[-rule.patience:]):
        return "diminishing_returns"
    return None
