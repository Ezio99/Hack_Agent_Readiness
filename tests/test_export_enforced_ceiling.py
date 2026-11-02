"""Regression: the exported spend block reports the ceiling actually ENFORCED on the shared ledger (the latest approved spending manifest's
`ledger_ceiling_usd`), not the stale `total_cap_usd` a fork copies from its source run (production trial eval-aa23e330 showed 2.0 / 0.009 remaining
while US$2.50 was enforced)."""
import json

from agent_readiness.investigate.export import _spend, enforced_ceiling
from agent_readiness.investigate.run import InvestigationRun
from agent_readiness.suite.core import canonical_hash


def _run(tmp_path, config_cap=2.0):
    return InvestigationRun.create(tmp_path, "fork-1", target="ironbark", mode="live", stages=("taskgen", "baseline_trials", "apply_fix", "post_trials"), config={"total_cap_usd": config_cap})


def _approve(run, stage, manifest):
    h = canonical_hash(manifest)
    run.write_artifact(f"manifests/{stage}-{h[:16]}", manifest)
    run.approve(stage, h, "test approval")
    return h


def _ledger(run, settled):
    (run.dir / "spend").mkdir(exist_ok=True)
    with (run.dir / "spend" / "ledger.jsonl").open("w") as f:
        for i, usd in enumerate(settled):
            f.write(json.dumps({"id": f"placebo-x:{i}", "kind": "reserve", "usd": usd + 0.01, "ts": "t"}) + "\n")
            f.write(json.dumps({"id": f"placebo-x:{i}", "kind": "settle", "usd": usd, "ts": "t"}) + "\n")


def test_fork_reports_the_enforced_post_trials_ceiling_not_the_copied_config(tmp_path):
    run = _run(tmp_path, config_cap=2.0)
    _approve(run, "baseline_trials", {"stage": "baseline_trials", "ledger_ceiling_usd": 2.0})
    _approve(run, "apply_fix", {"stage": "apply_fix"})                                  # no ceiling: skipped
    _approve(run, "post_trials", {"stage": "post_trials", "ledger_ceiling_usd": 2.5})
    _ledger(run, [0.864825, 1.126097])                                                   # the production fork's committed total
    s = _spend(run)
    assert s["ceiling_usd"] == 2.5 and s["ceiling_basis"].startswith("approved post_trials manifest")
    assert s["committed_usd"] == 1.990922 and s["remaining_usd"] == 0.509078
    assert s["open_reservations"] == 0


def test_tampered_manifest_is_not_trusted_and_falls_back(tmp_path):
    run = _run(tmp_path, config_cap=2.0)
    h = _approve(run, "post_trials", {"stage": "post_trials", "ledger_ceiling_usd": 2.5})
    path = run.dir / "artifacts" / "manifests" / f"post_trials-{h[:16]}.json"
    path.chmod(0o600)
    path.write_text(json.dumps({"stage": "post_trials", "ledger_ceiling_usd": 9.0}))     # no longer matches the approved hash
    assert enforced_ceiling(run) == (2.0, "run configuration (no approved spending manifest states a ceiling)")


def test_unapproved_manifest_is_ignored(tmp_path):
    run = _run(tmp_path, config_cap=0.15)
    run.write_artifact("manifests/post_trials-0000000000000000", {"ledger_ceiling_usd": 5.0})
    assert enforced_ceiling(run)[0] == 0.15


def test_latest_approval_wins(tmp_path):
    run = _run(tmp_path)
    _approve(run, "post_trials", {"stage": "post_trials", "ledger_ceiling_usd": 2.5})
    _approve(run, "baseline_trials", {"stage": "baseline_trials", "ledger_ceiling_usd": 3.0})
    assert enforced_ceiling(run)[0] == 3.0
