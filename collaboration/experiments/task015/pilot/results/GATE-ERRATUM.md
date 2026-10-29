# Erratum to the pilot gate interpretation (added 2026-10-29; the original pilot files are unchanged)

The frozen pilot gate evaluated to **`stop`** with the reason *"ceiling effect: 3 product-page visits, extra items []"* (`pilot-gate.json`, preserved byte-for-byte). That decision is the recorded result of the frozen rule and is not altered here.

The accompanying **"ceiling effect" interpretation was incorrect.** A ceiling effect means the baseline had nothing left to improve. In the pilot, the unmodified run **failed** the independent oracle (recall 0.33; HP-1006 and HP-1007 missing) after using 11 of its 12 requests and noting that two candidates were unchecked "due to step budget". The rule looked at the wrong signature of room to act (product-page visits ≥ 4 or a reported ineligible item) and so misdescribed a budget-exhausted, incomplete baseline as a ceiling.

What this erratum does **not** do: it does not re-decide the pilot, does not convert the pilot into evidence of an improvement (one pair, n = 1), and does not authorize anything. A corrected gate (`room-to-act-v2`) was written afterwards and applies **prospectively** to the proposed main stage only; run retrospectively on the pilot data it would have said "room to act", but that is a post-hoc illustration, not a pilot result. See `docs/TASK015_MAIN_STAGE_PROPOSAL.md`.
