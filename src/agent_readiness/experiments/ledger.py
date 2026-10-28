"""Programme-wide persistent ledger (extends the Task 011 live ledger): per-stage AND programme ceilings; reserve-before-run; settle releases unused budget;
unsettled/interrupted reservations stay fully counted; a recorded attempt is never repeated."""
from __future__ import annotations

from pathlib import Path

from ..scanner.live import Halt, Ledger
from . import design


class ExperimentLedger(Ledger):
    def __init__(self, directory: Path, programme_ceiling: float = design.PROGRAMME_CEILING_USD, stage_ceilings: dict[int, float] | None = None):
        super().__init__(directory, programme_ceiling)
        self.stage_ceilings = stage_ceilings or {k: v["stage_ceiling_usd"] for k, v in design.STAGES.items()}

    def _state(self, stage: int | None = None) -> dict[str, float]:
        state: dict[str, float] = {}
        for e in self.entries():
            if e["kind"] not in ("reserve", "settle") or (stage is not None and e.get("stage") != stage):
                continue
            if e["kind"] == "reserve":
                state.setdefault(e["id"], e["usd"])
            else:
                state[e["id"]] = e["usd"]
        return state

    def committed(self, stage: int | None = None) -> float:
        return round(sum(self._state(stage).values()), 6)

    def remaining(self, stage: int) -> float:
        return round(min(self.stage_ceilings[stage] - self.committed(stage), self.ceiling - self.committed()), 6)

    def reserve(self, item: str, usd: float, stage: int | None = None) -> None:        # type: ignore[override]
        if stage is None:
            raise ValueError("stage is required")
        if self.attempted(item):
            raise Halt(f"{item} was already attempted; attempts are never repeated")
        if self.committed(stage) + usd > self.stage_ceilings[stage] + 1e-9:
            raise Halt(f"stage {stage} ceiling US${self.stage_ceilings[stage]:.2f} cannot cover the next reservation (committed US${self.committed(stage):.4f} + US${usd:.2f})")
        if self.committed() + usd > self.ceiling + 1e-9:
            raise Halt(f"programme ceiling US${self.ceiling:.2f} cannot cover the next reservation (committed US${self.committed():.4f} + US${usd:.2f})")
        self._append({"kind": "reserve", "id": item, "usd": usd, "stage": stage})

    def settle(self, item: str, actual: float, stage: int | None = None) -> None:        # type: ignore[override]
        self._append({"kind": "settle", "id": item, "usd": actual, "stage": stage})

    def interrupted(self, item: str, note: str, stage: int) -> None:
        self._append({"kind": "interrupted", "id": item, "usd": 0.0, "stage": stage, "note": note})

    def attempted_ids(self) -> set[str]:
        return {e["id"] for e in self.entries() if e["kind"] == "reserve"}

    def unsettled(self) -> list[str]:
        st = {e["id"] for e in self.entries() if e["kind"] == "settle"}
        return sorted(self.attempted_ids() - st)
