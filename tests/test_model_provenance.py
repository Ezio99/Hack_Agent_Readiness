"""Model provenance is derived from frozen trial records and request traces, verified against the profile file, and never smooths over disagreement."""
import json

from agent_readiness.agent import profile
from agent_readiness.provenance import model_provenance
from agent_readiness.suite.core import canonical_hash

LIMITS = {"max_steps": 14, "timeout_seconds": 240, "max_model_requests": 14}


def _hash(name):
    e = profile(name)
    e.update(**LIMITS)
    return canonical_hash(e)


def _trial(run, name, *, prof="suite-v2-compat2", phash=None, sent=None, requests=3):
    d = run / "trial-data" / name / "x"
    d.mkdir(parents=True)
    sent = sent or {"model": "muse-spark-1.3", "max_completion_tokens": 4096, "reasoning_effort": "low"}
    (d / "trace.jsonl").write_text("".join(json.dumps({"kind": "model_http_request", "parameters": sent}) + "\n" + json.dumps({"kind": "model_response"}) + "\n" for _ in range(requests)))
    (run / "artifacts" / "trials").mkdir(parents=True, exist_ok=True)
    (run / "artifacts" / "trials" / f"{name}.json").write_text(json.dumps({
        "trial": {"model": "muse-spark-1.3", "profile": prof, "profile_hash": phash or _hash(prof)}, "evaluation": {"evaluator_id": "generated-criteria", "evaluator_version": "1"},
        "metrics": {"limits": LIMITS}, "trial_dir": str(d.relative_to(run))}))


def test_consistent_records_yield_the_frozen_settings(tmp_path):
    for n in ("placebo-t1-r1", "patched-t1-r1"):
        _trial(tmp_path, n)
    p = model_provenance(tmp_path)
    assert p["consistent"] and p["model"]["value"] == "muse-spark-1.3" and p["model_requests_recorded"] == 6
    assert p["reasoning_effort"] == {"value": "low", "profile": "low", "sent": "low", "consistent": True}
    assert p["max_completion_tokens"]["value"] == 4096 and p["agent_profile"] == {"name": "suite-v2-compat2", "sha256": _hash("suite-v2-compat2"), "verified_against_profile_file": True}
    assert p["graders"]["official"] == [{"id": "generated-criteria", "version": "1"}] and p["graders"]["post_hoc"]["version"] == "2"


def test_a_request_sent_with_a_different_effort_is_reported_not_hidden(tmp_path):
    _trial(tmp_path, "placebo-t1-r1")
    _trial(tmp_path, "patched-t1-r1", sent={"model": "muse-spark-1.3", "max_completion_tokens": 4096, "reasoning_effort": "high"})
    p = model_provenance(tmp_path)
    assert not p["consistent"] and p["reasoning_effort"]["consistent"] is False and p["reasoning_effort"]["sent"] == ["high", "low"]


def test_a_recorded_hash_that_does_not_match_the_profile_file_is_flagged(tmp_path):
    _trial(tmp_path, "placebo-t1-r1", phash="0" * 64)
    p = model_provenance(tmp_path)
    assert p["agent_profile"]["verified_against_profile_file"] is False and not p["consistent"] and p["reasoning_effort"]["profile"] is None


def test_imported_history_with_an_older_profile_is_separated_per_arm(tmp_path):
    _trial(tmp_path, "baseline-t1-r1", prof="suite-v2-compat1")
    _trial(tmp_path, "placebo-t1-r1")
    _trial(tmp_path, "patched-t1-r1")
    mixed = model_provenance(tmp_path)
    assert not mixed["consistent"] and sorted(mixed["agent_profile"]["name"]) == ["suite-v2-compat1", "suite-v2-compat2"]
    own = model_provenance(tmp_path, arms=("placebo", "patched"))
    assert own["consistent"] and own["trials"] == 2 and own["agent_profile"]["name"] == "suite-v2-compat2"
    assert own["by_arm"]["baseline"]["agent_profile"]["name"] == "suite-v2-compat1" and own["by_arm"]["baseline"]["consistent"]
