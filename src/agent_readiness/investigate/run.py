"""One investigation = one directory (`investigations/<id>/`, git-ignored): durable stage status, write-once artifacts, an approvals log, the evidence store and a spend ledger.

Rules (they mirror the Task 015 driver): an artifact is written once (re-writing identical content is a no-op, different content is refused); approvals bind to the SHA-256 of an
exact manifest; a spending stage in `live` mode never runs without an approval of its manifest; spending is recorded in the existing USD `Ledger` before it happens."""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

from ..ledger import Ledger
from ..suite.core import canonical_hash
from .models import Mode, now
from .store import EvidenceStore

RUN_SCHEMA = "investigation-run-v1"
STATUSES = ("pending", "running", "done", "failed", "awaiting_approval")


class ArtifactExists(Exception):
    pass


class NeedsApproval(Exception):
    def __init__(self, stage: str, manifest_sha256: str):
        super().__init__(f"stage {stage!r} needs the owner's approval of manifest sha256 {manifest_sha256}")
        self.stage, self.manifest_sha256 = stage, manifest_sha256


def _write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w") as f:
        f.write(json.dumps(obj, indent=2, sort_keys=True, default=str))
        f.flush()
        os.fsync(f.fileno())
    tmp.replace(path)


class InvestigationRun:
    def __init__(self, directory: Path):
        self.dir = Path(directory)
        self.state_path = self.dir / "run.json"
        if not self.state_path.exists():
            raise FileNotFoundError(f"{self.dir} is not an investigation run (no run.json)")
        self.evidence = EvidenceStore(self.dir / "evidence.jsonl")

    @classmethod
    def create(cls, root: Path, run_id: str, *, target: str, mode: Mode, stages: tuple[str, ...], config: dict | None = None) -> "InvestigationRun":
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", run_id):
            raise ValueError("run id must be 1-64 characters of letters, digits, '.', '_' or '-'")
        d = Path(root) / run_id
        if (d / "run.json").exists():
            raise FileExistsError(f"investigation {run_id!r} already exists; use resume")
        _write_json(d / "run.json", {"schema": RUN_SCHEMA, "id": run_id, "target": target, "mode": mode, "created_at": now(), "config": config or {},
                                     "config_sha256": canonical_hash(config or {}), "stages": {s: {"status": "pending"} for s in stages}})
        return cls(d)

    # -- state ---------------------------------------------------------------------------------------------------------
    @property
    def state(self) -> dict:
        return json.loads(self.state_path.read_text())

    @property
    def mode(self) -> str:
        return self.state["mode"]

    def _update(self, stage: str, **fields) -> None:
        s = self.state
        s["stages"][stage] = {**s["stages"][stage], **fields, "updated_at": now()}
        _write_json(self.state_path, s)

    def status(self, stage: str) -> str:
        return self.state["stages"][stage]["status"]

    def set_status(self, stage: str, status: str, **fields) -> None:
        if status not in STATUSES:
            raise ValueError(status)
        self._update(stage, status=status, **fields)

    # -- write-once artifacts ------------------------------------------------------------------------------------------
    def write_artifact(self, name: str, obj) -> Path:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]{0,100}", name) or ".." in name:
            raise ValueError("bad artifact name")
        path = self.dir / "artifacts" / (name if name.endswith(".json") else name + ".json")
        if path.exists():
            if canonical_hash(json.loads(path.read_text())) == canonical_hash(json.loads(json.dumps(obj, default=str))):
                return path
            raise ArtifactExists(f"artifact {name!r} is write-once and already exists with different content")
        _write_json(path, obj)
        return path

    def artifact(self, name: str):
        return json.loads((self.dir / "artifacts" / (name if name.endswith(".json") else name + ".json")).read_text())

    def has_artifact(self, name: str) -> bool:
        return (self.dir / "artifacts" / (name if name.endswith(".json") else name + ".json")).exists()

    # -- approvals -----------------------------------------------------------------------------------------------------
    @staticmethod
    def manifest_sha256(manifest: dict) -> str:
        return canonical_hash(manifest)

    def approvals(self) -> list[dict]:
        p = self.dir / "approvals.jsonl"
        return [json.loads(l) for l in p.read_text().splitlines()] if p.exists() else []

    def approve(self, stage: str, manifest_sha256: str, note: str) -> dict:
        if stage not in self.state["stages"]:
            raise KeyError(stage)
        if not note.strip():
            raise ValueError("an approval needs a note recording who approved what")
        rec = {"stage": stage, "manifest_sha256": manifest_sha256, "note": note, "at": now()}
        with (self.dir / "approvals.jsonl").open("a") as f:
            f.write(json.dumps(rec) + "\n")
            f.flush()
            os.fsync(f.fileno())
        return rec

    def is_approved(self, stage: str, manifest_sha256: str) -> bool:
        return any(a["stage"] == stage and a["manifest_sha256"] == manifest_sha256 for a in self.approvals())

    def require_approval(self, stage: str, manifest: dict) -> str:
        h = self.manifest_sha256(manifest)
        self.write_artifact(f"manifests/{stage}-{h[:16]}", manifest)          # one write-once file per distinct manifest; a changed manifest is a new, unapproved one
        if not self.is_approved(stage, h):
            raise NeedsApproval(stage, h)
        return h

    # -- spend ---------------------------------------------------------------------------------------------------------
    def ledger(self, ceiling_usd: float) -> Ledger:
        return Ledger(self.dir / "spend", ceiling_usd)
