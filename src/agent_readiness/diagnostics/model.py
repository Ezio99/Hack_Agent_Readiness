"""The finding schema shared by every diagnostic layer.

Status (evidence/verification), in increasing strength:
  observed               a directly measured fact (a page property, or something a recorded agent did)
  unverified             a structural risk indicator with no behavioural evidence either way (no task touched it)
  hypothesis             a suspected contributor: a structural observation linked to behaviour on tasks that depend on it; untested
  supported_exploratory  the change was tested in a paired comparison on a real model and an exploratory (not pre-registered, or underpowered)
                         rule agreed; the pre-registered rule did not establish it
  supported              a pre-registered comparison rule established an improvement
Severity: high | medium | low | info (impact on an agent completing tasks; a risk indicator is never reported as a proven failure)."""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field

STATUSES = ("observed", "unverified", "hypothesis", "supported_exploratory", "supported")
SEVERITIES = ("high", "medium", "low", "info")
LAYERS = ("structural", "behavioral", "hypothesis")


def stable_id(prefix: str, *parts) -> str:
    """Deterministic id from the finding's identity (rule, site, page or task, subject), NOT from the version: the same issue on two versions of a
    site has the same id, so a change can be shown to resolve it."""
    return prefix + "-" + hashlib.sha256(json.dumps([str(p) for p in parts]).encode()).hexdigest()[:10]


@dataclass
class Evidence:
    type: str            # page | locator | listing_field | trial | step | finding | comparison
    ref: str
    detail: str = ""


@dataclass
class Finding:
    id: str
    layer: str
    rule: str
    title: str
    site: str
    version: str                       # site version name (original / modified / ...)
    version_sha256: str
    severity: str
    impact: str
    status: str
    evidence: list[Evidence]
    recommendation: str
    verify: str                        # how to test the recommendation
    tasks: list[str] = field(default_factory=list)
    evidence_origin: str = "page"      # page | real_model | dev_fixture | scripted
    detail: dict = field(default_factory=dict)

    def __post_init__(self):
        assert self.layer in LAYERS and self.status in STATUSES and self.severity in SEVERITIES, (self.layer, self.status, self.severity)

    def as_dict(self) -> dict:
        return asdict(self)
