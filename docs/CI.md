# Continuous integration: sharded complete suite, merge gate, branch protection

## What runs (`.github/workflows/test.yml`)
| Job | What | Typical time |
|---|---|---|
| `logic 1/2`, `logic 2/2` | `pytest -m "not browser"` split into 2 deterministic shards (+ `readiness smoke` on shard 1) | 2.0–2.9 min |
| `browser 1/4` … `4/4` | `pytest -m browser` (real Chromium information-boundary tests) split into 4 shards | 2.7–4.1 min |
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

## Branch protection: settings the owner must configure
`main` currently has **no protection** (the API returns 404). The workflow cannot enforce the gate by itself; a repository admin must set, in *Settings → Branches → Add branch ruleset / rule for `main`*:
1. **Require a pull request before merging.**
2. **Require status checks to pass before merging** and add exactly one required check: **`gate (required check)`** (the job name). Do **not** require the individual `logic n/2` / `browser n/4` checks: the gate already depends on them, and matrix names would break if the shard count changes.
3. Optional: *Require branches to be up to date before merging* (strict; re-runs CI after each merge ahead of you).
4. Optional: block force pushes and deletions of `main`.
The check name only appears in the picker after the workflow has run once on a PR (it has, on PR #33). `test.yml` has no path filter, so the required check always reports. `dashboard.yml` is path-filtered and must **not** be made required.
After merging, the nightly `full.yml` starts running on the default branch automatically (scheduled workflows run only from the default branch).

## Changing the shard count
Edit the matrix and the `--num-shards` value in `test.yml`, and the expected counts in `scripts/ci_check_shards.py` (`SUITES`) and `tests/test_markers.py`; the guard tests fail if they disagree.

## Local development
`scripts/dev-tests.sh` (≈40 s, 534 tests; uses `./.venv` when present; `DEV_TESTS_PARALLEL=1` adds `-n auto` if `pytest-xdist` is installed locally — dev-only, not in `requirements.lock`, not used by CI). Before opening a PR run `python -m pytest -q`.
