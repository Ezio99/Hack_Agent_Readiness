# Task 005 — Proposed bounded end-to-end compatibility trial

**Status: DRAFT — NOT APPROVED. No paid calls authorized.**

## Objective
Determine whether the opt-in Muse compatibility profile can complete the existing seed-0 discovery task through browser interaction and independent evaluation. This is an agent execution validation, not a universal website-readiness score.

## Preconditions
Read STATUS.md, COLD_START.md, AGENTS.md and Report 004. Verify branch/PR, local code, prior evidence and model pricing before requesting approval. Preserve strict baseline profile and original evaluator; no model, storefront, task, prompt or parser modifications during the measurement without separate review.

## Proposed protocol (subject to user approval)
- Use `natural-shopping-v3-compat1`, Meta Muse Spark 1.3, existing seed-0 discovery task, full Browser Use schema and DOM+screenshot observation.
- Freeze and record profile/configuration/schema hashes, versions, code SHA, task and environment. Keep strict baseline distinct.
- Before execution, propose explicit model request, step, wall-time, token and estimated dollar bounds; state that estimates are not guaranteed spend ceilings. Require explicit approval for this specific run and limits.
- One run only; no retries, fallback providers or additional paid probes without renewed authorization. Stop on gate, failure or timeout.
- Preserve sanitized raw HTTP responses, raw protocol compliance, recovered-action validity, browser actions, screenshots, independent evaluator result, actual usage and calculated versus provider-reported cost separately. Inspect artifacts before sharing.

## Acceptance / reporting
- Report whether the agent reaches a detail page, extracts the correct answer and finishes; only the independent evaluator determines task success.
- Report raw protocol compliance separately from compatibility recovery and final task outcome; a recovered click alone is not success.
- Document failure classification, model attempts, latency, token usage, estimates, uncertainties, privacy checks and reproducibility information.
- Update STATUS.md and a new Report 005 after the authorized run; do not merge without review.

## Approval gate
Await user's explicit approval of the final command, model, limits, expected maximum estimated cost and risk before any authenticated request.
