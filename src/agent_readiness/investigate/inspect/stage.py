"""Pipeline hook for the `inspect` stage: persist the snapshot, the site profile and the neutral observations in an investigation run."""
from __future__ import annotations

from pathlib import Path

from ..pipeline import Context
from ..sitemodel.snapshot import Snapshot
from .profile import build_profile, observations


def run_inspect(ctx: Context, snapshot: Snapshot) -> dict:
    run = ctx.run
    snap_dir = run.dir / "snapshot"
    if (snap_dir / "index.json").exists():
        if Snapshot.load(snap_dir).sha256 != snapshot.sha256:
            raise ValueError("this investigation already froze a different snapshot; a snapshot is write-once per investigation")
    else:
        snapshot.save(snap_dir)
    profile = build_profile(snapshot)
    run.write_artifact("site-profile", profile)
    obs = observations(profile, mode=run.mode)
    for o in obs:
        run.evidence.add_observation(o)
    return {"snapshot_sha256": snapshot.sha256, "pages": len(profile["pages"]), "observations": len(obs), "fidelity": snapshot.meta.get("fidelity", {}).get("level")}


def load_snapshot(run) -> Snapshot:
    return Snapshot.load(Path(run.dir) / "snapshot")
