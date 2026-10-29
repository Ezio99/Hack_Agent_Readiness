"""Durable append-only USD ledger and the shared `Halt` stop signal used by every guarded live path (Task 011 validation, Task 012/015 experiments, Task 014 WebArena).

Moved out of `scanner/live.py` (Task 015f): these are core safety primitives, not part of one feature. `scanner.live` re-exports them so existing imports keep working.
Semantics unchanged: amounts are reserved BEFORE any request, an unsettled/interrupted reservation counts in full, an item can be attempted once, and the ceiling is hard.
All amounts are calculated at published prices (not a bill)."""
from __future__ import annotations

import json
import os
from pathlib import Path

from .capture import PRICE_INPUT_PER_M, PRICE_OUTPUT_PER_M
from .recorder import utcnow

DEFAULT_CEILING_USD = 2.00


class Halt(Exception):
    pass


def cost_of(usage: dict | None) -> float:
    u = usage or {}
    return round((u.get("prompt_tokens") or 0) * PRICE_INPUT_PER_M / 1e6 + (u.get("completion_tokens") or 0) * PRICE_OUTPUT_PER_M / 1e6, 6)


class Ledger:
    def __init__(self, directory: Path, ceiling: float = DEFAULT_CEILING_USD):
        self.dir, self.ceiling = Path(directory), ceiling
        self.dir.mkdir(parents=True, exist_ok=True)
        self.path = self.dir / "ledger.jsonl"

    def entries(self) -> list[dict]:
        return [json.loads(l) for l in self.path.read_text().splitlines()] if self.path.exists() else []

    def _append(self, e: dict) -> None:
        with self.path.open("a") as f:
            f.write(json.dumps({"ts": utcnow(), **e}) + "\n")
            f.flush()
            os.fsync(f.fileno())

    def committed(self) -> float:
        """Per item: the settled amount if settled, else its reservation (an unsettled/interrupted item counts in full)."""
        state: dict[str, float] = {}
        for e in self.entries():
            if e["kind"] == "reserve":
                state.setdefault(e["id"], e["usd"])
            elif e["kind"] == "settle":
                state[e["id"]] = e["usd"]
        return round(sum(state.values()), 6)

    def attempted(self, item: str) -> bool:
        return any(e["id"] == item and e["kind"] == "reserve" for e in self.entries())

    def reserve(self, item: str, usd: float) -> None:
        if self.attempted(item):
            raise Halt(f"{item} was already attempted; attempts are never repeated automatically")
        if self.committed() + usd > self.ceiling + 1e-9:
            raise Halt(f"budget ceiling US${self.ceiling:.2f} would be exceeded (committed US${self.committed():.4f} + reservation US${usd:.2f})")
        self._append({"kind": "reserve", "id": item, "usd": usd})

    def settle(self, item: str, actual: float) -> None:
        self._append({"kind": "settle", "id": item, "usd": actual})

    def probe_succeeded(self) -> bool:
        return any(e["kind"] == "probe_ok" for e in self.entries())

    def mark_probe_ok(self) -> None:
        self._append({"kind": "probe_ok", "id": "probe", "usd": 0.0})
