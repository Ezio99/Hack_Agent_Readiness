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
    monkeypatch.setattr(api.exporter, "public_demo", lambda raw: fresh)
    out = api.verified_export(tmp_path, "paired-x")
    assert out["spend"]["ceiling_usd"] == 2.5 and calls == [tmp_path / "paired-x"]
    cached = tmp_path / "derived" / "public-export" / f"paired-x.{api.EXPORT_CACHE_VERSION}.json"
    assert json.loads(cached.read_text())["spend"]["remaining_usd"] == 0.509078
    assert stale.read_bytes() == before                                              # old cache untouched (not evidence, but not ours to delete)
    monkeypatch.setattr(api.exporter, "export_run", lambda d: pytest.fail("cached export must be reused"))
    assert api.verified_export(tmp_path, "paired-x") == fresh


def test_derived_names_are_validated(tmp_path):
    for ns, name in (("Grader", "a.json"), ("grader-v2", "../x.json"), ("grader-v2", "a/b.json"), ("../x", "a.json")):
        with pytest.raises(ValueError):
            api.derived_path(tmp_path, ns, name)
    assert api.derived_path(tmp_path, "grader-v2", "paired-1.abc.json").parent == tmp_path / "derived" / "grader-v2"
