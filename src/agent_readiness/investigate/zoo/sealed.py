"""Sealed planted-issue manifests and the blindness guard. This is the ONLY module that reads `sealed/*.json`. Investigator-facing code must never import it; the live pipeline
(M3+) calls `assert_blind(text)` on every prompt/tool output before it leaves for a model, and the post-hoc scorer (L2) reads `manifest(site_id)`."""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

DIR = Path(__file__).resolve().parent / "sealed"


class BlindnessError(RuntimeError):
    pass


@lru_cache(maxsize=None)
def manifest(site_id: str) -> dict:
    return json.loads((DIR / f"{site_id}.json").read_text())


def manifests() -> dict[str, dict]:
    return {p.stem: json.loads(p.read_text()) for p in sorted(DIR.glob("site-*.json"))}


def tokens(site_id: str | None = None) -> set[str]:
    """Strings whose appearance in anything shown to a model would reveal a diagnosis: category ids, the planted summaries/descriptions, and the word 'planted'."""
    out = {"planted"}
    for sid, m in manifests().items():
        if site_id in (None, sid):
            out |= {m["category"], m["summary"], *(p["description"] for p in m["planted"]), *m.get("extra_tokens", [])}
    return {t.strip().lower() for t in out if t.strip()}


def _squash(s: str) -> str:
    return re.sub(r"[\s_-]+", " ", s.lower())


def assert_blind(text: str, site_id: str | None = None) -> None:
    hay = _squash(text)
    for t in tokens(site_id):
        if _squash(t) in hay:
            raise BlindnessError(f"text would reveal a sealed diagnosis ({t[:40]!r}...)")
