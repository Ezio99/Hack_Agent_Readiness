# PR #60 CI compatibility repair — 2026-11-01

Pitch/submission drafting is paused at the owner's request. No paid calls, grading changes, historical data edits, security-check changes, merge or deployment.

## Exact failures

Latest release-head failing workflow: **Credential-free checks**, `.github/workflows/test.yml`, run [41279382935](https://github.com/Ezio99/Hack_Agent_Readiness/actions/runs/41279382935), head **7df69ce59c0c00c36b55a25d5bad832d515e306c**. Completed failed jobs were inspected directly while siblings were still pending:

| Job | Job id | Failing step | Failure |
|---|---|---|---|
| logic 1/2 | 124767984766 | Unit and offline adapter checks (shard 1/2), step 6 | Two stale programme-balance assertions |
| logic 2/2 | 124767984591 | Unit and offline adapter checks (shard 2/2), step 6 | Two stale programme-balance assertions |
| browser 3/4 | 124767984415 | Browser information boundary checks (shard 3/4), step 6 | EXP-2 mock pilot stopped before trials |

The preceding completed failed run [41278286116](https://github.com/Ezio99/Hack_Agent_Readiness/actions/runs/41278286116) at **018f9fb54f4234175db335e0d0505ce68a8bf1d6** had the same failures; the required gate correctly failed its “Every shard succeeded” step. Its browser evidence artifact exposed the exact error: `KeyError: 'agent_profile'` in shared `investigate/trials/stage.py:run_plan`, called by the unchanged EXP-2 adapter.

## Root causes and smallest correction

1. Genuine shared-interface regression from the scroll-successor wiring: `run_plan` unconditionally indexed `manifest_["agent_profile"]`. The existing EXP-2 adapter sends a legacy gate manifest without that key and previously relied on `run_trial`'s default compat1 profile. Restore the ORIGINAL runner constant when the field is absent: `manifest_.get("agent_profile", PROFILE_ID)`. Explicit S1 compat2 remains explicit and its integrity checks remain unchanged. Neither EXP-2 code nor frozen manifests need modification.
2. Incomplete test maintenance after the owner-authorized programme reconciliation: four accounting tests still expected A$6.2067 spent / A$43.7933 remaining, rather than current recorded A$12.5236 / A$37.4764. Update their exact balance and post-cap arithmetic expectations. The tests still check pilot double-count prevention, cross-stage reservations, cap subtraction and frozen artifact preservation. No assertion is removed or relaxed, and no accounting implementation, exchange assumption or ledger entry changes.

These are reproducible repository regressions/test-expectation drift, not CI-only configuration or environment failures. Node deprecation warnings in the logs are unrelated. Both budget and browser failures were reproduced locally before editing; the browser failed in 13.40 s. The original critical/fast subsets missed these cases because the affected budget plan checks are slow and the EXP-2 integration is browser-marked; this is a coverage-boundary limitation, not a reason to skip those tests.

## Validation

- Existing exact EXP-2 failing browser test alone after repair: **1 passed, 14 deselected**, 38.01 s, mock provider; no other browser/build workload ran concurrently.
- New focused regression: missing-profile legacy gate manifest uses exactly `suite-v2-compat1`. The existing explicit-successor test still checks compat2 execution. Existing S1 declaration/hash and schema checks are preserved.
- Affected non-browser files (`test_scroll_policy.py`, `test_remediation_experiment.py`, `test_remediation_main_design.py`, including slow checks): **43 passed, 2 deselected**, 89.58 s. Final CI outcome is recorded on the pushed commit/PR checks, not inferred from a pending run.
- Critical suite: **214 passed, 17 deselected**, 59.62 s.
- Dashboard **141 passed**; standard typecheck/build including required distribution guard passed; **40 deployment-safety/export-replay tests passed**.
- Historical source and S1 preservation checked against the existing inventories; no frozen criteria, verdicts, grader, private truth, archived run file or ledger changed.

Replacement CI must finish all shards and required coverage gate successfully before claiming green. PR #60 remains draft/unmerged. No tests or security controls disabled; no tolerance increased, paid run or retry introduced.
