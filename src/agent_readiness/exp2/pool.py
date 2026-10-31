"""Build the verified candidate pool for Ironbark and summarise it (without any truth)."""
from __future__ import annotations

from collections import Counter
from functools import lru_cache

from ..sites.ironbark import variants as V
from ..sites.ironbark.build import build_site, is_page
from . import modelview, tasks as T
from .facts import PageFacts
from .verify import Report, verify

FACT_KEYS = ("daily", "weekend", "weekly", "deposit", "min_days", "delivery_required", "power", "weight_kg", "specs", "units", "free")


@lru_cache(maxsize=None)
def _control_pages() -> tuple:
    return tuple((p, b.decode()) for p, b in build_site(V.CONTROL).items() if is_page(p))


def control_pages() -> dict[str, str]:
    return dict(_control_pages())


def arm_texts() -> dict[str, dict[str, str]]:
    """What the model is SHOWN on every page of every arm of the site (control, each single candidate variant and the combined build): the captured `llm_representation()` of the real browser session
    (`modelview.py`), not the HTML's plain text. Evidence criteria are verified against this."""
    return modelview.all_views()


@lru_cache(maxsize=1)
def build_pool() -> tuple[Report, list[T.Candidate]]:
    """Generate and verify (cached: deterministic, and the result is treated as read-only)."""
    cands = T.generate()
    return verify(cands, control_pages(), arm_texts()), cands


def facts_invariance(variant: V.Variant | str) -> list[str]:
    return _invariance(variant if isinstance(variant, str) else variant.name)


@lru_cache(maxsize=None)
def _invariance(name: str) -> list[str]:
    """Candidate variants must only change HOW information is reached, never WHAT it says: every price, rule, specification and calendar cell read from a variant's pages equals the control's."""
    v = V.parse(name)
    base, other = PageFacts(control_pages()), PageFacts({p: b.decode() for p, b in build_site(v).items() if is_page(p)})
    diffs = []
    for pid, p in base.products.items():
        q = other.products[pid]
        diffs += [f"{pid}.{k}" for k in FACT_KEYS if getattr(p, k) != getattr(q, k)]
    diffs += [f"{k}" for k in base.accessories if (base.accessories[k].price, base.accessories[k].fits) != (other.accessories[k].price, other.accessories[k].fits)]
    diffs += [f"kit {k}" for k in base.kits if base.kits[k] != other.kits[k]]
    if base.terms != other.terms:
        diffs.append("terms")
    return diffs


def summary(report: Report, candidates: list[T.Candidate]) -> dict:
    acc = report.accepted
    return {"generated": len(candidates), "accepted": len(acc), "rejected": len(report.rejected), "rejections_by_reason": dict(Counter(r["reason"].split(":")[0] for r in report.rejected)),
            "by_family": dict(Counter(c.family for c in acc)), "by_template": dict(Counter(f"{c.family}/{c.sub}" for c in acc)), "by_difficulty": dict(Counter(c.difficulty for c in acc)),
            "by_kind": dict(Counter(c.kind for c in acc)), "sensitive_to": {v: sum(v in c.sensitive_to for c in acc) for v in T.VARIANTS}, "negative_controls": sum(not c.sensitive_to for c in acc),
            "rejected_examples": report.rejected[:12]}
