"""Candidate website variants. The CONTROL site has no flags set; every flag adds clearly marked content (`data-variant="<flag>"`) and, for `discover`, new pages. Nothing else differs:
the stylesheet, images, data and all control markup are identical in every variant, which `tests/test_sites_ironbark.py` verifies mechanically."""
from __future__ import annotations

from dataclasses import dataclass

FLAGS = ("discover", "avail", "cost", "compat")
NAMES = {"discover": "discoverability", "avail": "availability", "cost": "cost", "compat": "compatibility"}
BY_NAME = {v: k for k, v in NAMES.items()}


@dataclass(frozen=True)
class Variant:
    discover: bool = False
    avail: bool = False
    cost: bool = False
    compat: bool = False

    @property
    def flags(self) -> tuple[str, ...]:
        return tuple(f for f in FLAGS if getattr(self, f))

    @property
    def name(self) -> str:
        return "+".join(NAMES[f] for f in self.flags) or "control"


CONTROL = Variant()


def parse(spec: str | None) -> Variant:
    """'control', 'cost', 'discoverability+availability', ... (long or short flag names)."""
    if not spec or spec == "control":
        return CONTROL
    flags = set()
    for part in spec.split("+"):
        key = BY_NAME.get(part, part)
        if key not in FLAGS:
            raise ValueError(f"unknown variant {part!r}; choose from control, {', '.join(NAMES.values())} (combine with '+')")
        flags.add(key)
    return Variant(**{f: True for f in flags})


def all_single() -> list[Variant]:
    return [CONTROL] + [Variant(**{f: True}) for f in FLAGS]
