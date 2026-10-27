# Task 005 — Bounded end-to-end compatibility trial

**Status: SPECIFIED — NOT YET APPROVED FOR EXECUTION. No paid calls authorized.** Limits below were chosen by the user on 2026-10-28 (6 steps, 6 model requests, 120 s, estimated budget US$0.25); execution still needs explicit approval of the final command after the preconditions below are met.

## Objective
Determine whether the opt-in Muse compatibility profile can complete the existing seed-0 discovery task through browser interaction and independent evaluation. This is an agent execution validation, not a universal website-readiness score.

## Frozen configuration
- Profile `natural-shopping-v3-compat1` (strict `natural-shopping-v2`/`v3` unchanged and not pooled), parser `muse-prose-prefix-json-v1`.
- Model `muse-spark-1.3` via `https://api.meta.ai/v1`, `reasoning_effort: low`, `max_completion_tokens: 4096`, `model_timeout_seconds: 30`, SDK `max_retries: 0`, DOM + screenshot (`detail: high`, 1280×960), `max_actions_per_step: 3`.
- Task: `--kind discovery --seed 0`. Full wire schema SHA-256 `c80ef8b813abef0b2afd79c83a6f31e857c0101ea8730952ee78d61e65f9a194`.
- Limits: `--max-steps 6 --max-model-requests 6 --timeout 120`. Single run, single attempt, no automatic retries, no fallback provider.
- Record code SHA, profile/configuration hashes, versions, task and environment before the run; git must be clean.

## Proposed command (not approved)
```
readiness run --profile natural-shopping-v3-compat1 --kind discovery --seed 0 \
  --max-steps 6 --max-model-requests 6 --timeout 120 --allow-model-calls \
  --expect-schema-sha256 c80ef8b813abef0b2afd79c83a6f31e857c0101ea8730952ee78d61e65f9a194 \
  --max-estimated-cost-usd 0.04
```
The guard flags are **only valid after the guard change below is implemented and reviewed**; do not run this command against the current guard.

## Precondition findings (verified by code inspection, 2026-10-28)
1. **Guard vs. multistep — currently NOT compatible.** `check_fidelity` (src/agent_readiness/capture.py) requires the exact full-schema hash and rejects `LAST_STEP_MARKERS` on every request. Browser Use (`AgentStepInfo.is_last_step`: `step_number >= max_steps - 1`) narrows the schema to `done` only and adds the last-step instruction on the final step (here request/step 6), and also appends a forced done-only step after `max_failures` (2) consecutive failures. The current guard would therefore block that legitimate final request as a fidelity violation and mislabel the run `diagnostic_fidelity_violation`. Other checks (one screenshot, `<browser_state>`, `Agent initialized` — retained because `max_history_items` is unset, task prompt, parameters) are expected to hold on later steps but are untested multistep.
   **Required change (needs review, offline only):** make the guard step-aware — full schema required on every non-final request; on the final step (and a forced-done-after-failure step) accept exactly the known done-only schema plus the last-step text, record it as `expected_final_step_narrowing`, and still reject any other deviation. Add offline tests: a normal multistep run whose steps 1–5 are full-schema and step 6 is done-only passes; an unexpected narrowing before the final step is blocked; a mocked run reaching `done` is evaluated.
2. **Cost estimator.** `estimate_cost_usd` is per request (input text/4 + 1,430 per screenshot + schema bytes/4, ×1.10, plus the full 4,096-token completion cap at US$1.25 / US$4.25 per M tokens). The `--max-estimated-cost-usd` ceiling is checked **per request**; there is no cumulative cap in the code. The bound below therefore relies on the request gate (6 requests) times the per-request ceiling.
3. **Single attempt.** SDK retries are off (`max_retries=0`), there is no harness retry logic, and the request gate counts every request. Browser Use's own `max_failures=2` can consume steps but cannot send a request beyond the gate of 6.

## Cost assumptions (calculated, NOT provider-reported or guaranteed)
- Measured step-1 request: 9,443 prompt tokens; estimator input 11,131; worst case 11,131 × $1.25/M + 4,096 × $4.25/M = US$0.0313.
- Worst case if input grows to ~15k tokens for later steps: ≈ US$0.036 per request.
- Per-request ceiling `0.04` ⇒ 6 × 0.04 = **US$0.24 hard estimated worst case**, within the US$0.25 budget (the done-only final step is cheaper). Expected actual ≈ US$0.07–0.12 (reasoning is `low`; observed completions 229–257 tokens).
- Pricing is published, not account-verified; the provider reports no cost; request/time limits are not a monetary guarantee. Estimated cumulative live spend before this run ≈ US$0.08–0.09.

## Acceptance / reporting
Report three results **separately**, never merged:
1. **Raw protocol compliance** — per request: strict-JSON compliant vs non-compliant (`protocol_compliance` counters).
2. **Compatibility recovery** — recovery attempted / recovered-valid / rejected with reasons; rejected shapes are findings, not retried.
3. **Independent task outcome** — only the evaluator decides success (product, price, availability). Also report whether the agent reached the detail page and called `done`; a recovered click alone is not success.

Also document: failure classification (`model_output_error`, `request_limit`, `timeout`, `infrastructure_error`, fidelity), requests actually sent, latency, provider-reported tokens, calculated vs provider-reported cost, whether the final step was narrowed, privacy inspection of artifacts before sharing, and reproducibility information. Smoke runs and mocked runs are not live trials.

## Stop conditions and approval gate
One run only. Stop on gate, failure, timeout or fidelity violation; no retries without renewed authorization. Before any authenticated request: guard change reviewed, offline + browser tests and CLI smoke passing, `.env` mode 600, and the user's explicit approval of the final command and limits. After the run, update `STATUS.md` and write Report 005; do not merge PR #3 without review.
