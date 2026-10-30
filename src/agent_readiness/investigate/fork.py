"""Recovery fork (Task 016): continue an investigation whose PAID taskgen / baseline stages are complete, in a NEW run directory, without re-running or re-paying them.

What is imported (copied byte-for-byte, hashed in `fork.json`): the frozen tasks and their private criteria, the paid taskgen batches and transcript, the baseline trial records and trial data, the shared
arm configuration, the approved taskgen / baseline manifests (provenance only) and the FULL durable spend ledger (so the ceiling and the spending history carry over; the source's own entries are never
altered). What is NOT imported: approvals (a fork needs a fresh, exact-manifest approval for every paid stage), the evidence store, the investigator's artifacts / transcripts / reports, evaluation and
recommendations. The free, deterministic stages `inspect` and `trace` are simply run again in the fork and re-derive the same observations from the imported evidence. The source run is only read.

The investigator protocol is unchanged: the workspace shows investigation-partition tasks and trials only; holdout files are carried along solely so the later evaluation stays possible."""
from __future__ import annotations

import hashlib
import json
import re
import shutil
from pathlib import Path

from ..ledger import Halt
from ..suite.core import canonical_hash
from .models import now
from .run import InvestigationRun

SCHEMA = "investigation-fork-v1"
IMPORTED_STAGES = ("taskgen", "freeze", "baseline_trials")
REQUIRED_DONE = ("inspect", "taskgen", "freeze", "baseline_trials")
PATTERNS = ("artifacts/taskgen-report.json", "artifacts/tasks-manifest.json", "artifacts/arm-config.json", "artifacts/trials/*.json", "artifacts/manifests/taskgen-*.json",
            "artifacts/manifests/baseline_trials-*.json", "private/criteria.json", "private/accepted-drafts.json", "private/taskgen-batch-*.json", "private/taskgen-attempt-*.json",
            "private/llm-transcript.jsonl", "calls/taskgen.jsonl", "trial-data/**/*")
LEDGER = "spend/ledger.jsonl"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _files(root: Path) -> list[str]:
    out: set[str] = set()
    for pat in PATTERNS:
        out |= {str(p.relative_to(root)) for p in root.glob(pat) if p.is_file()}
    return sorted(out)


def _ledger_summary(path: Path) -> dict:
    res, settled = {}, {}
    lines = path.read_text().splitlines() if path.exists() else []
    for line in lines:
        e = json.loads(line)
        if e["kind"] == "reserve":
            res.setdefault(e["id"], e["usd"])
        elif e["kind"] == "settle":
            settled[e["id"]] = e["usd"]
    outstanding = round(sum(v for k, v in res.items() if k not in settled), 6)
    return {"entries": len(lines), "sha256": hashlib.sha256(("\n".join(lines) + "\n").encode()).hexdigest() if lines else None, "settled_usd": round(sum(settled.values()), 6),
            "outstanding_reserved_usd": outstanding, "committed_usd": round(sum(settled.values()) + outstanding, 6)}


def fork(source_dir: Path, root: Path, new_id: str) -> Path:
    """Create the fork. Reads the source only; refuses an incomplete source or an existing target."""
    from .flow import STAGES
    src = InvestigationRun(Path(source_dir))
    st = src.state
    pending = [s for s in REQUIRED_DONE if st["stages"].get(s, {}).get("status") != "done"]
    if pending:
        raise ValueError(f"the source run has not completed the paid prerequisites {pending}; nothing to fork")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", new_id):
        raise ValueError("run id must be 1-64 characters of letters, digits, '.', '_' or '-'")
    if (Path(root) / new_id).exists():
        raise FileExistsError(f"{new_id!r} already exists")
    files = _files(src.dir)
    needed = {"artifacts/tasks-manifest.json", "private/criteria.json"}
    if not needed <= set(files) or not any(f.startswith("artifacts/trials/") for f in files):
        raise ValueError("the source run lacks its frozen tasks, private criteria or baseline trials")
    new = InvestigationRun.create(Path(root), new_id, target=st["target"], mode=st["mode"], stages=STAGES, config=st.get("config") or {})
    imported = {}
    for rel in files:
        dst = new.dir / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src.dir / rel, dst)
        if rel.startswith("private/"):
            dst.chmod(0o600)
        imported[rel] = _sha(dst)
        if imported[rel] != _sha(src.dir / rel):
            raise RuntimeError(f"copy of {rel} does not match the source")
    led_src = src.dir / LEDGER
    if led_src.exists():
        (new.dir / "spend").mkdir(exist_ok=True)
        shutil.copy2(led_src, new.dir / LEDGER)
    summary = _ledger_summary(led_src)
    profile = src.artifact("site-profile") if src.has_artifact("site-profile") else {}
    inv = src.artifact("investigation") if src.has_artifact("investigation") else None
    prov = {"schema": SCHEMA, "forked_at": now(), "source_run": st["id"], "source_run_json_sha256": _sha(src.state_path), "imported_sha256": imported,
            "imported_files_sha256": canonical_hash(imported), "tasks_manifest_sha256": canonical_hash(src.artifact("tasks-manifest")), "snapshot_sha256": profile.get("snapshot_sha256") or src.artifact("tasks-manifest")["snapshot_sha256"],
            "source_ledger": summary, "source_approvals_not_inherited": [{"stage": a["stage"], "manifest_sha256": a["manifest_sha256"]} for a in src.approvals()],
            "source_investigation": ({"status": inv.get("status"), "incomplete": inv.get("incomplete"), "model_requests": inv.get("model_requests"), "cost_usd": inv.get("cost_usd")} if inv else None),
            "not_imported": ["approvals", "evidence store", "investigator artifacts / transcripts / reports", "evaluation", "recommendations"],
            "note": "paid taskgen and baseline trials were NOT re-run; their results and the full spending history were imported. Every paid stage of this fork needs a fresh exact-manifest approval."}
    (new.dir / "fork.json").write_text(json.dumps(prov, indent=2, sort_keys=True))
    for stage in IMPORTED_STAGES:
        new.set_status(stage, "done", summary={"imported_from": st["id"], "imported_files_sha256": prov["imported_files_sha256"]})
    return new.dir


def load_fork(run: InvestigationRun) -> dict | None:
    p = run.dir / "fork.json"
    return json.loads(p.read_text()) if p.exists() else None


def verify_fork(run: InvestigationRun) -> dict | None:
    """Fail closed (Halt) if anything imported has changed, the ledger history is no longer an intact prefix, or the re-derived snapshot differs. Returns the provenance, or None for a normal run."""
    prov = load_fork(run)
    if prov is None:
        return None
    bad = [rel for rel, h in prov["imported_sha256"].items() if not (run.dir / rel).exists() or _sha(run.dir / rel) != h]
    if bad:
        raise Halt(f"fork integrity: imported evidence changed or is missing: {bad[:3]}")
    n, want = prov["source_ledger"]["entries"], prov["source_ledger"]["sha256"]
    lines = (run.dir / LEDGER).read_text().splitlines() if (run.dir / LEDGER).exists() else []
    if n and (len(lines) < n or hashlib.sha256(("\n".join(lines[:n]) + "\n").encode()).hexdigest() != want):
        raise Halt("fork integrity: the imported spending history is not an intact prefix of this run's ledger")
    if run.has_artifact("site-profile") and run.artifact("site-profile")["snapshot_sha256"] != prov["snapshot_sha256"]:
        raise Halt("fork integrity: the re-derived snapshot differs from the imported one")
    return prov


def provenance_summary(run: InvestigationRun) -> dict | None:
    """What an approval manifest must show: where the evidence came from and what it carried over (no file lists)."""
    prov = verify_fork(run)
    if prov is None:
        return None
    return {"source_run": prov["source_run"], "source_run_json_sha256": prov["source_run_json_sha256"], "imported_files_sha256": prov["imported_files_sha256"], "tasks_manifest_sha256": prov["tasks_manifest_sha256"],
            "snapshot_sha256": prov["snapshot_sha256"], "imported_spend_committed_usd": prov["source_ledger"]["committed_usd"], "imported_ledger_sha256": prov["source_ledger"]["sha256"],
            "source_approvals_not_inherited": prov["source_approvals_not_inherited"], "source_investigation": prov["source_investigation"], "paid_stages_rerun": False}
