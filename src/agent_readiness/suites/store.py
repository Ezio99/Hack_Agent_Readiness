"""Write-once, content-addressed store for lifecycle records.

  <root>/objects/<kind>/<sha256>.json     public records, file mode 0444, written with exclusive create
  <root>/private/<sha256>.json            PrivateOutcome only; directory 0700, file 0400; never returned by a public view
  <root>/refs/<kind>/<name>.json          write-once named pointers (e.g. "larkspur-core@1" -> suite sha256); re-pointing is refused

Every read recomputes the canonical hash and refuses a mismatch (tampering). Writes re-check cross-record rules: a suite's tasks exist; a frozen
suite matches an APPROVED approval of the exact suite hash; a manifest references a frozen suite; Stage A records never reference Stage B outcomes.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from .boundary import STAGE_B_OUTCOME_KINDS
from .records import (BY_KIND, KINDS, Approval, EvaluationManifest, FrozenSuite, PrivateOutcome, Record, RunResult, SuiteRecord, TaskRecord,
                      content_hash)


class StoreError(ValueError):
    pass


class OverwriteError(StoreError):
    pass


class TamperError(StoreError):
    pass


def _bytes(record: Record) -> bytes:
    return json.dumps(record.content(), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


class WriteOnceStore:
    def __init__(self, root: Path):
        self.root = Path(root)
        (self.root / "objects").mkdir(parents=True, exist_ok=True)
        (self.root / "refs").mkdir(parents=True, exist_ok=True)
        priv = self.root / "private"
        priv.mkdir(parents=True, exist_ok=True)
        os.chmod(priv, 0o700)

    # ------------------------------------------------------------------------------------------------ paths
    def _path(self, kind: str, sha: str) -> Path:
        if kind == "private_outcome":
            return self.root / "private" / f"{sha}.json"
        return self.root / "objects" / kind / f"{sha}.json"

    def kind_of(self, sha: str) -> str | None:
        for kind in BY_KIND:
            if self._path(kind, sha).exists():
                return kind
        return None

    # ------------------------------------------------------------------------------------------------ write
    def put(self, record: Record) -> str:
        kind = KINDS.get(type(record))
        if kind is None:
            raise StoreError(f"not a lifecycle record: {type(record).__name__}")
        self._check(record)
        sha, data = content_hash(record), _bytes(record)
        path = self._path(kind, sha)
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            if path.read_bytes() != data:
                raise TamperError(f"{kind}/{sha} exists with different content (tampered store)")
            return sha                                                   # idempotent: the same record is the same object
        with open(path, "xb") as f:                                      # exclusive create: never overwrite
            f.write(data)
        os.chmod(path, 0o400 if kind == "private_outcome" else 0o444)
        return sha

    def ref(self, kind: str, name: str, sha: str) -> None:
        if kind not in BY_KIND or not name or "/" in name or name.startswith("."):
            raise StoreError("invalid reference")
        if self.kind_of(sha) != kind:
            raise StoreError(f"{sha} is not a stored {kind}")
        path = self.root / "refs" / kind / f"{name}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            if json.loads(path.read_text())["sha256"] != sha:
                raise OverwriteError(f"reference {kind}/{name} already points elsewhere; publish a new version instead")
            return
        with open(path, "x") as f:
            json.dump({"kind": kind, "name": name, "sha256": sha}, f)
        os.chmod(path, 0o444)

    # ------------------------------------------------------------------------------------------------ read
    def get(self, kind: str, sha: str) -> Record:
        path = self._path(kind, sha)
        if not path.exists():
            raise StoreError(f"no {kind} {sha}")
        data = json.loads(path.read_bytes())
        record = BY_KIND[kind].model_validate(data)
        if content_hash(record) != sha or _bytes(record) != path.read_bytes():
            raise TamperError(f"{kind}/{sha}: content does not match its hash")
        return record

    def resolve(self, kind: str, name: str) -> str:
        path = self.root / "refs" / kind / f"{name}.json"
        sha = json.loads(path.read_text())["sha256"]
        self.get(kind, sha)                                              # verifies the target
        return sha

    def public_suite_view(self, suite_sha: str) -> dict:
        """Suite plus its tasks, verified, with NO private outcomes (only their hashes, as recorded in each task)."""
        suite = self.get("suite", suite_sha)
        return {"sha256": suite_sha, **suite.content(), "tasks": [{"sha256": t, **self.get("task", t).content()} for t in suite.task_sha256s]}

    # ------------------------------------------------------------------------------------------------ cross-record rules
    def _stage_a_refs(self, record: Record) -> None:
        for i in record.provenance.inputs:
            k = self.kind_of(i.sha256)
            if k in STAGE_B_OUTCOME_KINDS:
                raise StoreError(f"Stage A record references a Stage B {k} ({i.name}); Stage A may not depend on agent outcomes")

    def _check(self, record: Record) -> None:
        if isinstance(record, TaskRecord):
            self._stage_a_refs(record)
            if record.private_sha256 is not None:
                priv = self.get("private_outcome", record.private_sha256)
                if priv.spec_sha256 != content_hash(record.spec):
                    raise StoreError("the private outcome was derived for a different task specification")
        elif isinstance(record, SuiteRecord):
            self._stage_a_refs(record)
            for t in record.task_sha256s:
                task = self.get("task", t)
                if task.site != record.site:
                    raise StoreError("a suite's tasks must belong to its site")
        elif isinstance(record, FrozenSuite):
            approval = self.get("approval", record.approval_sha256)
            self.get("suite", record.suite_sha256)
            if approval.decision != "approved" or approval.suite_sha256 != record.suite_sha256:
                raise StoreError("freezing requires an APPROVED approval of exactly this suite version")
        elif isinstance(record, Approval):
            self.get("suite", record.suite_sha256)
        elif isinstance(record, EvaluationManifest):
            self.get("frozen_suite", record.frozen_suite_sha256)
        elif isinstance(record, RunResult):
            self.get("manifest", record.manifest_sha256)
        elif isinstance(record, PrivateOutcome):
            pass
