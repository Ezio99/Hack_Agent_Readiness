#!/usr/bin/env bash
# Fast development test loop: logic-level tests only (no real-Chromium `browser` tests, no `slow` pipeline tests). ~40 s.
# This is NOT the CI contract: CI runs the complete suite (sharded) and a gate verifies that no test is lost.
# Run the full suite before opening or updating a PR:  python -m pytest -q
# Extra arguments are passed to pytest, e.g.:  scripts/dev-tests.sh --lf -x   or   scripts/dev-tests.sh tests/test_remediation.py
# Uses ./.venv when present; with pytest-xdist installed (dev-only, not in requirements.lock) set DEV_TESTS_PARALLEL=1 to add `-n auto`.
set -euo pipefail
cd "$(dirname "$0")/.."
PY=python
[ -x .venv/bin/python ] && PY=.venv/bin/python
PAR=()
[ "${DEV_TESTS_PARALLEL:-}" = 1 ] && PAR=(-n auto)
exec "$PY" -m pytest -m "not browser and not slow" -q -p no:cacheprovider "${PAR[@]}" "$@"
