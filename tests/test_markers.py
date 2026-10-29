"""The fast development subset must never become the CI contract: CI keeps running the complete suite."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_slow_marker_is_registered_and_documented(pytestconfig):
    markers = " ".join(pytestconfig.getini("markers"))
    assert "slow:" in markers and "browser:" in markers


def test_ci_still_runs_every_test():
    wf = (ROOT / ".github" / "workflows" / "test.yml").read_text()
    runs = re.findall(r"run:\s*python -m pytest ([^\n]*)", wf)
    assert 'python -m pytest -m "not browser" -q' in wf and "python -m pytest -m browser -q" in wf
    assert not any("slow" in r for r in runs), "CI must not filter out `slow` tests"
    assert "not slow" not in wf


def test_dev_script_selects_only_the_fast_subset_and_says_so():
    s = (ROOT / "scripts" / "dev-tests.sh").read_text()
    assert 'pytest -m "not browser and not slow"' in s and "NOT the CI contract" in s
