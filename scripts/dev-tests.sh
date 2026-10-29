#!/usr/bin/env bash
# Fast development test loop: logic-level tests only (no real-Chromium `browser` tests, no `slow` pipeline tests). ~1 minute.
# This is NOT the CI contract: CI always runs the complete suite (`pytest -m "not browser"` then `pytest -m browser`).
# Run the full suite before opening or updating a PR:  python -m pytest -q
# Extra arguments are passed to pytest, e.g.:  scripts/dev-tests.sh --lf -x   or   scripts/dev-tests.sh tests/test_remediation.py
set -euo pipefail
cd "$(dirname "$0")/.."
exec python -m pytest -m "not browser and not slow" -q -p no:cacheprovider "$@"
