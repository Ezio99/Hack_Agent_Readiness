#!/usr/bin/env bash
# Critical smoke suite: fast cross-cutting confidence for the live product (UI-started jobs, grants and approvals, the spend gate and ledger, credential handling, test network isolation, cancellation,
# goal-bound task generation and coverage reporting). Offline, no real model, no browser-marked tests. Not a replacement for the full suite: sharded CI is the PR regression gate.
#   scripts/critical-tests.sh            # about one minute (see docs/CI.md for the measured time)
# Extra arguments are passed to pytest, e.g.:  scripts/critical-tests.sh -x
# Coverage boundary: the dev-provider end-to-end runs that start a real Chromium (marked `browser`) are NOT included; run them by file when you touch the worker or trial runner.
set -euo pipefail
cd "$(dirname "$0")/.."
PY=python
[ -x .venv/bin/python ] && PY=.venv/bin/python
exec "$PY" -m pytest -m "not browser and not slow" -q -p no:cacheprovider \
  tests/test_live.py tests/test_live_m1.py tests/test_live_smoke.py tests/test_live_quality.py tests/test_context_pack.py tests/test_goal_binding.py tests/test_reach_target.py \
  tests/test_scanner_live_guards.py tests/test_configuration_budget.py tests/test_env.py tests/test_investigate_llm.py tests/test_markers.py tests/test_sharding.py "$@"
