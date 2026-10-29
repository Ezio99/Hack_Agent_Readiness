"""Owner-defined goals: free-text `focus` plus optional explicit tasks (same criterion grammar). Owner tasks go through the same gate as every other task."""
from __future__ import annotations

import json
from pathlib import Path

from .gate import Draft


def load_goals(source: Path | dict | None) -> tuple[str | None, list[Draft]]:
    if source is None:
        return None, []
    data = source if isinstance(source, dict) else json.loads(Path(source).read_text())
    drafts = [Draft(t["question"], t.get("start_path", "/"), t["criterion"], "owner", t.get("rationale", "owner-defined")) for t in data.get("tasks", [])]
    return data.get("focus"), drafts
