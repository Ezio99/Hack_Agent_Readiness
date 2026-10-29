"""The fast development subset must never become the CI contract: CI keeps running the complete suite."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_slow_marker_is_registered_and_documented(pytestconfig):
    markers = " ".join(pytestconfig.getini("markers"))
    assert "slow:" in markers and "browser:" in markers


def _wf():
    return (ROOT / ".github" / "workflows" / "test.yml").read_text()


def test_ci_still_runs_every_test():
    """CI is sharded for speed; completeness is guaranteed by (a) no marker filter beyond browser/not-browser, (b) every shard of both suites running, (c) a gate that
    compares the union of shard node ids with a full collection (see test_ci_gate_*)."""
    wf = _wf()
    runs = re.findall(r"run:\s*(?:\|\s*)?python -m pytest ([^\n]*)", wf)
    assert any('-m "not browser"' in r and "--num-shards" in r for r in runs), "the non-browser suite must run in CI (sharded)"
    assert any("-m browser" in r and "--num-shards" in r for r in runs), "the browser suite must run in CI (sharded)"
    assert not any("slow" in r for r in runs), "CI must not filter out `slow` tests"
    assert "not slow" not in wf
    assert "-x" not in " ".join(runs).split() and "--lf" not in " ".join(runs)


def test_ci_shard_matrices_cover_every_shard():
    wf = _wf()
    for suite, count in (("logic", 2), ("browser", 4)):
        m = re.search(rf"{suite}:.*?shard:\s*\[([^\]]*)\]", wf, re.S)
        assert m, f"{suite} job needs a shard matrix"
        assert [int(x) for x in m.group(1).split(",")] == list(range(1, count + 1))
        assert f"num-shards {count}" in wf


def test_ci_gate_is_single_required_check_and_checks_coverage():
    wf = _wf()
    assert re.search(r"gate:\s*\n(?:.*\n)*?\s+needs: \[logic, browser\]", wf)
    assert "if: always()" in wf
    assert "scripts/ci_check_shards.py" in wf
    assert (ROOT / "scripts" / "ci_check_shards.py").exists()


def test_ci_does_not_run_twice_per_pull_request_commit():
    wf = _wf()
    assert "pull_request:" in wf and re.search(r"push:\s*\n\s+branches: \[main\]", wf)
    assert "cancel-in-progress" in wf


def test_full_unsharded_run_exists_as_cross_check():
    full = (ROOT / ".github" / "workflows" / "full.yml").read_text()
    assert "schedule:" in full and "workflow_dispatch" in full and "python -m pytest -q" in full


def test_dev_script_selects_only_the_fast_subset_and_says_so():
    s = (ROOT / "scripts" / "dev-tests.sh").read_text()
    assert 'pytest -m "not browser and not slow"' in s and "NOT the CI contract" in s
