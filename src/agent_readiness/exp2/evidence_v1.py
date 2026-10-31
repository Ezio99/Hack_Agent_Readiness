"""FROZEN copy of the evidence matcher that was in force for the first pilot (`exp2-evidence-v1`, PR #57, commit 090bbc3). It exists only so that the pilot's ORIGINAL outcomes can be regenerated from the
stored artifacts and shown next to the corrected ones (`reanalysis.py`); it is never used to verify criteria or to assess new trials, and it must not be edited.

Known defects (the reason for v2, see evidence.py): the live element markers `*[934]<td />` were only partly removed (the leading `*` stayed, so a label and its value in separate table cells never
matched), and a page had to show a literal `Product code IB-...` string."""
from __future__ import annotations

import re

MARKERS = re.compile(r"\[\d+\]<[^>]*/>")


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", MARKERS.sub(" ", s or "")).strip()


def clause_met(c: dict, pages: list[str]) -> bool:
    n, s = norm(c["needle"]), norm(c["sig"]) if c["sig"] else None
    return any(n in p and (s is None or s in p) for p in pages)


def assess(facts: list[dict], observations: list[dict] | None) -> dict:
    """`facts` in the stored JSON shape (v1 criteria); returns the verdict the first pilot's report was based on."""
    pages = [norm(o.get("text") or "") for o in (observations or [])]
    missing = [f["label"] for f in facts if not any(all(clause_met(c, pages) for c in r) for r in f["routes"])]
    return {"sufficient": bool(facts) and not missing, "missing": missing, "facts": len(facts), "pages_seen": len(pages), "rule": "exp2-evidence-v1"}
