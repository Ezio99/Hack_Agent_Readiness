"""Derived caches (public exports, grader_v2 views) live in a versioned namespace under <root>/derived/, separate from run evidence. A stale v1
export cache (<run>.public.json, written before the enforced-ceiling fix) is never read again, and it is not modified or deleted."""
import json

import pytest

from agent_readiness.hosted import api


def test_export_cache_is_versioned_and_stale_v1_cache_is_ignored_not_touched(tmp_path, monkeypatch):
    stale = tmp_path / "paired-x.public.json"
    stale.write_text(json.dumps({"spend": {"ceiling_usd": 2.0, "remaining_usd": 0.009078}, "run": {"complete": True}, "evaluation": {"state": "evaluated"}}))
    before = stale.read_bytes()
    fresh = {"spend": {"ceiling_usd": 2.5, "ceiling_basis": "approved post_trials manifest 99f493d1558db5d9", "remaining_usd": 0.509078}, "run": {"complete": True}, "evaluation": {"state": "evaluated"}}
    calls = []
    monkeypatch.setattr(api.exporter, "export_run", lambda d: calls.append(d) or {"raw": True})
    monkeypatch.setattr(api.exporter, "public_demo", lambda raw: dict(fresh))
    monkeypatch.setattr(api, "provenance_view", lambda root, run_id: {"model": {"value": "muse-spark-1.3"}, "reasoning_effort": {"value": "low"}})
    out = api.verified_export(tmp_path, "paired-x")
    assert out["model_provenance"]["reasoning_effort"]["value"] == "low" and api.EXPORT_CACHE_VERSION == "export-v3"
    assert out["spend"]["ceiling_usd"] == 2.5 and calls == [tmp_path / "paired-x"]
    cached = tmp_path / "derived" / "public-export" / f"paired-x.{api.EXPORT_CACHE_VERSION}.json"
    assert json.loads(cached.read_text())["spend"]["remaining_usd"] == 0.509078
    assert stale.read_bytes() == before                                              # old cache untouched (not evidence, but not ours to delete)
    monkeypatch.setattr(api.exporter, "export_run", lambda d: pytest.fail("cached export must be reused"))
    assert api.verified_export(tmp_path, "paired-x") == out


def test_derived_names_are_validated(tmp_path):
    for ns, name in (("Grader", "a.json"), ("grader-v2", "../x.json"), ("grader-v2", "a/b.json"), ("../x", "a.json")):
        with pytest.raises(ValueError):
            api.derived_path(tmp_path, ns, name)
    assert api.derived_path(tmp_path, "grader-v2", "paired-1.abc.json").parent == tmp_path / "derived" / "grader-v2"


def test_provenance_view_is_derived_cached_and_labels_the_imported_baseline(tmp_path, monkeypatch):
    from agent_readiness import provenance as P
    calls = []
    monkeypatch.setattr(P, "model_provenance", lambda d, arms=None: calls.append((d, arms)) or {"consistent": True, "by_arm": {}})
    v = api.provenance_view(tmp_path, "paired-y")
    assert calls == [(tmp_path / "paired-y", ("placebo", "patched"))] and "historical baseline" in v["arm_labels"]["baseline"]
    assert api.provenance_view(tmp_path, "paired-y") == v and len(calls) == 1                      # cached under derived/model-provenance/
    assert list((tmp_path / "derived" / "model-provenance").glob("paired-y.*.json"))
