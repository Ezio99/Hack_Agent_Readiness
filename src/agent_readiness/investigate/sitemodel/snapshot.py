"""Content-hashed, origin-independent site snapshot (plan D2). The hash covers path/status/content-type/redirect/body only — never timestamps, ports or the crawled origin — so the
same site content always yields the same `sha256`. A patched snapshot records its parent and patch hashes in `meta`, outside the hash."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

SCHEMA = "site-snapshot-v1"


@dataclass(frozen=True)
class Resource:
    path: str                       # "/p/1" or "/list?page=2" (root-relative; query kept verbatim)
    status: int
    content_type: str
    body: bytes = b""
    location: str | None = None     # redirect target (root-relative) for 3xx

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.body).hexdigest()

    @property
    def is_html(self) -> bool:
        return self.status == 200 and "html" in self.content_type

    def text(self) -> str:
        return self.body.decode("utf-8", errors="replace")


@dataclass
class Snapshot:
    resources: dict[str, Resource] = field(default_factory=dict)
    meta: dict = field(default_factory=dict)

    @property
    def sha256(self) -> str:
        core = [[r.path, r.status, r.content_type, r.location, r.sha256] for r in sorted(self.resources.values(), key=lambda r: r.path)]
        return hashlib.sha256(json.dumps(core, separators=(",", ":")).encode()).hexdigest()

    def get(self, path: str) -> Resource | None:
        return self.resources.get(path)

    def pages(self) -> list[Resource]:
        return [r for r in sorted(self.resources.values(), key=lambda r: r.path) if r.is_html]

    def derive(self, resources: dict[str, Resource], **meta) -> "Snapshot":
        return Snapshot(resources, {**self.meta, "parent_sha256": self.sha256, **meta})

    def save(self, directory: Path) -> Path:
        d = Path(directory)
        (d / "blobs").mkdir(parents=True, exist_ok=True)
        index = []
        for r in sorted(self.resources.values(), key=lambda r: r.path):
            (d / "blobs" / r.sha256).write_bytes(r.body)
            index.append({"path": r.path, "status": r.status, "content_type": r.content_type, "location": r.location, "sha256": r.sha256})
        (d / "index.json").write_text(json.dumps({"schema": SCHEMA, "snapshot_sha256": self.sha256, "meta": self.meta, "resources": index}, indent=1, sort_keys=True))
        return d

    @classmethod
    def load(cls, directory: Path) -> "Snapshot":
        d = Path(directory)
        idx = json.loads((d / "index.json").read_text())
        res = {}
        for e in idx["resources"]:
            body = (d / "blobs" / e["sha256"]).read_bytes()
            if hashlib.sha256(body).hexdigest() != e["sha256"]:
                raise ValueError(f"snapshot blob for {e['path']} does not match its recorded hash")
            res[e["path"]] = Resource(e["path"], e["status"], e["content_type"], body, e["location"])
        snap = cls(res, idx["meta"])
        if snap.sha256 != idx["snapshot_sha256"]:
            raise ValueError("snapshot hash mismatch: the index was altered")
        return snap
