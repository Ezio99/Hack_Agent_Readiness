# Continuous integration: sharded complete suite, merge gate, branch protection

## What runs (`.github/workflows/test.yml`)
| Job | What | Typical time |
|---|---|---|
| `logic 1/2`, `logic 2/2` | `pytest -m "not browser"` split into 2 deterministic shards (+ `readiness smoke` on shard 1) | 2.0–2.9 min |
| `browser 1/5` … `5/5` | `pytest -m browser` (real Chromium information-boundary tests) split into 5 shards (was 4 until 2026-11-05: the round-robin put about 15.5 min of long end-to-end tests in one shard, over its 15-minute limit; 5 shards measure at most about 10.5 min) | 7–11 min |
| **`gate (required check)`** | fails unless every shard succeeded **and** the union of the shards' node ids equals a fresh full collection (`scripts/ci_check_shards.py`: no test lost, none duplicated, every shard present) | 0.6–0.7 min |

`full.yml` runs the complete suite unsharded (`python -m pytest -q`) daily and on demand; it never gates a merge, it cross-checks the sharded result.

Triggers: `pull_request`, `push` to `main`, `workflow_dispatch`. Pushes to other branches no longer start a second, duplicate run; superseded runs on the same ref are cancelled (never on `main`).

Sharding lives in `tests/conftest.py` (`--num-shards N --shard-id K [--shard-ids-file F]`): the selected tests (after `-m`) are sorted by node id and dealt round-robin, so each test is in exactly one shard by construction. No dependency was added. Nothing is filtered: `slow` tests run in CI; `tests/test_markers.py` and `tests/test_sharding.py` guard this.

## Measured (GitHub-hosted `ubuntu-24.04`, public repository, PR #33)
| | Before (`main`, serial) | After (sharded) |
|---|---|---|
| Wall-clock per run | 13.2–14.7 min | **4.7, 4.8, 5.2 min** (three consecutive green runs) |
| Runs per PR commit | 2 (push + pull_request) | 1 |
| Runner-minutes per run | ≈ 13–15 | ≈ 18–19 (more parallel jobs, each repeats ~1 min of install) |
| Tests executed | 665 passed + skips | 671 passed (+6 new guard tests) + the same skips; gate: logic 587/587, browser 85/85 |
Critical path = slowest browser shard (≈4 min) + gate (≈0.7 min). Runner-minutes per run **rose**; per PR commit they fell (one run instead of two) and wall-clock fell by about two thirds. The Playwright browser cache restored on later runs on the same ref (a cache saved by a `pull_request` run is scoped to that PR; first runs are cold).

## Verified behaviour of the gate (deliberate failures, throwaway branches, since deleted)
| Scenario | Result |
|---|---|
| a test fails in a logic shard | `logic` red → **gate red** |
| one browser shard silently drops a test (all shards green) | shards green, **gate red**: `browser: full=85 selected=84 missing=1`, naming the lost test |
| a shard drops a test in the partition unit test config | `tests/test_sharding.py` fails the logic job |
| normal PR | all green, gate green |

## Branch protection (configured by the owner, 2026-10-29)
Active repository ruleset `Main_Rule` on the default branch: **pull request required** (0 approvals), **required status check `gate (required check)`** (strict "up to date" policy off), **force pushes and deletion blocked**, no bypass actors. The individual `logic n/2` / `browser n/4` checks are deliberately not required (the gate depends on them; matrix names change with the shard count). `test.yml` has no path filter, so the required check always reports; `dashboard.yml` is path-filtered and must **not** be made required. A PR whose last CI run predates the gate (e.g. a branch opened before #33) must be updated with `main` so the gate runs. Optional hardening still available: enable the strict "require branches to be up to date" policy.
The nightly `full.yml` (unsharded cross-check) runs from the default branch.

## Changing the shard count
Edit the matrix and the `--num-shards` value in `test.yml`, and the expected counts in `scripts/ci_check_shards.py` (`SUITES`) and `tests/test_markers.py`; the guard tests fail if they disagree.

## Local development
Three local commands, from cheapest to most complete (measured 2026-11-01 on the development machine; the suite keeps growing, so treat times as an order of magnitude):
| Command | What | Time |
|---|---|---|
| `scripts/critical-tests.sh` | live product correctness: grants/approvals, spend gate and ledger, credential handling, test network isolation, cancellation and kill switch, goal-bound task generation and coverage, config/budget, sharding and marker guards. 184 tests, offline, no `browser`-marked tests | **about 40 s** |
| `scripts/dev-tests.sh` | every logic-level test: `-m "not browser and not slow"` (1170 tests; `DEV_TESTS_PARALLEL=1` adds `-n auto` if `pytest-xdist` is installed locally, dev-only, not in `requirements.lock`, not used by CI) | about 2.5 min |
| `python -m pytest -q` | the complete suite (1355 tests, includes 138 real-Chromium and 47 slow tests) | about 33 min serially; prefer CI, which runs it sharded in about 6 min |
Run the tests a change affects first, then the critical suite; leave the full regression to the sharded CI of the PR. Do not run builds, screenshots or other browser work while a local browser test run is in progress.
