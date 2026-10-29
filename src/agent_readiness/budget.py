"""Programme budget in AUD with the original USD records preserved. The A$ ceiling is a programme-level LIMIT, never an authorization to spend: every paid run still needs
its own approval, and the per-request / per-run / stage limits (USD, enforced by the durable spend gate) are derived from AUD limits through the documented rate.
All USD amounts are calculated at published prices, not billed."""
from __future__ import annotations

import json
import os
from pathlib import Path

LEDGER_PATH = Path(__file__).resolve().parents[2] / "collaboration" / "budget" / "programme-ledger.json"
RATE_ENV = "AGENT_READINESS_USD_TO_AUD"


def load(path: Path = LEDGER_PATH) -> dict:
    return json.loads(Path(path).read_text())


def usd_to_aud_rate(ledger: dict) -> float:
    return float(os.environ.get(RATE_ENV) or ledger["assumptions"]["usd_to_aud"])


def to_aud(usd: float, rate: float) -> float:
    return round(usd * rate, 4)


def to_usd(aud: float, rate: float) -> float:
    return round(aud / rate, 6)


def summary(ledger: dict | None = None, extra_usd: float = 0.0) -> dict:
    """Spent / remaining in both currencies. `extra_usd` = spend not yet recorded in the file (e.g. an in-progress stage)."""
    ledger = ledger or load()
    rate = usd_to_aud_rate(ledger)
    spent_usd = round(sum(e["usd"] for e in ledger["entries"]) + extra_usd, 6)
    ceiling_aud = ledger["programme_ceiling_aud"]
    return {"usd_to_aud": rate, "spent_usd": spent_usd, "spent_aud": to_aud(spent_usd, rate), "ceiling_aud": ceiling_aud, "ceiling_usd_equivalent": to_usd(ceiling_aud, rate),
            "remaining_aud": round(ceiling_aud - to_aud(spent_usd, rate), 4), "remaining_usd_equivalent": round(to_usd(ceiling_aud, rate) - spent_usd, 6),
            "authorization": "none: the ceiling is a limit, each paid run needs separate approval", "basis": "calculated, not billed"}


def check_stage(stage_cap_aud: float, ledger: dict | None = None, extra_usd: float = 0.0) -> dict:
    """Would a stage with this AUD hard cap keep the programme within its ceiling even if it spent the whole cap? Raises ValueError otherwise."""
    s = summary(ledger, extra_usd)
    if stage_cap_aud > s["remaining_aud"] + 1e-9:
        raise ValueError(f"stage cap A${stage_cap_aud:.2f} exceeds the remaining programme budget A${s['remaining_aud']:.2f}")
    return {**s, "stage_cap_aud": stage_cap_aud, "stage_cap_usd": to_usd(stage_cap_aud, s["usd_to_aud"]), "remaining_after_cap_aud": round(s["remaining_aud"] - stage_cap_aud, 4)}
