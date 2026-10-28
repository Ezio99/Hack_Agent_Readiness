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
  --max-estimated-cost-usd 0.04 --max-cumulative-estimated-cost-usd 0.25
```
Requires the step-aware guard and cumulative cap implemented under "Implemented guard" below (offline-tested 2026-10-28; awaiting the user's review and explicit approval to run).

## Implemented guard and cap (offline; no model calls were made)
Verified by code inspection first: Browser Use's final step (`AgentStepInfo.is_last_step`) narrows the schema to `done` only and appends one context message, which the previous guard would have blocked as a violation. Changes (src/agent_readiness/capture.py, agent.py, runner.py, cli.py; tests/test_step_aware_guard.py):
1. **Step-aware check** (active when the run supplies `max_steps`; without it the legacy strict rules are unchanged). The request must contain exactly one `Step<n> maximum:<m>` label with `m == max_steps`.
   - *Intermediate step (n < max):* full-schema hash required; no last-step text; a budget warning is required **exactly** when n/max ≥ 0.75 and must be the verbatim Browser Use notice for that step as a standalone message, otherwise any budget warning is a violation.
   - *Final step (n == max, not the first request):* exactly the pinned done-only schema (`7964acb5…5dc1`, 1,274 B, tested against the installed library) plus exactly one verbatim, standalone last-step notice; any appended/edited/duplicated/missing notice, a budget warning, or the full schema is a violation. The first request can never use this exception (so `--max-steps 1` is still blocked).
   - *Forced-done-after-failure:* disabled in the frozen profile (`final_response_after_failure=False`), so its notice is always a violation.
   - All other checks (parameters, ≥20,000-char system prompt without last-step text, one screenshot, DOM state, task prompt, per-request cost ceiling) apply at every step. **Limit:** page/DOM text is data and is not scanned for injected instructions; only framework notices are validated.
2. **Cumulative estimated-cost cap** (`--max-cumulative-estimated-cost-usd`): before each request, the sum of worst-case estimates of requests already allowed onto the network plus this request's estimate (estimated input + the full `max_completion_tokens` = 4,096) must not exceed the cap; otherwise the request is blocked before the network, recorded as `estimated_cost_limit` (status `estimated_cost_limit`), distinct from fidelity violations and the request gate. The per-request ceiling and `max_model_requests` gate are unchanged.
3. **Blocked ≠ response:** every blocked invocation emits `model_request_blocked` (`reason`, `reached_provider: false`); `model_http_request` events carry `blocked_before_network`; no `model-response-NN.json` exists for them; the `step_result` of a step whose model call produced no response has `model_output: null` and `model_invocation` (`produced_response: false`, failure reasons, `stale_model_output_discarded`) instead of the previous action. `run.json` gains `estimated_cost` (per-request ceiling, cumulative cap, estimated sent, requests sent/blocked) and `cost_limit_blocks`.
4. **Single attempt:** SDK `max_retries=0` (asserted in tests), one HTTP call per model invocation (tested), no harness retry logic; the gate of 6 caps requests.

Offline results (2026-10-28): 22 new tests in `tests/test_step_aware_guard.py` (unit: intermediate, budget notice, final, early/late narrowing, notice tampering, forced-done, label tampering, other deviations, legacy rules, estimator; real Chromium + mock transport: a normal 6-step run passes with steps 1–5 full schema and step 6 done-only, cumulative cap block, per-request ceiling, request gate with stale-action discard, single attempt). Full suite: see STATUS.md.

## Cost assumptions (calculated, NOT provider-reported or guaranteed)
- Measured step-1 request: 9,443 prompt tokens; estimator input 11,131; worst case 11,131 × $1.25/M + 4,096 × $4.25/M = US$0.0313.
- Worst case if input grows to ~15k tokens for later steps: ≈ US$0.036 per request.
- Per-request ceiling `0.04` ⇒ 6 × 0.04 = **US$0.24 estimated worst case**, within the US$0.25 cumulative cap, which is checked before every request against the full 4,096-token allowance (the done-only final step is cheaper). With these values the per-request ceiling is the binding bound; the cumulative cap is a second, independent stop. Expected actual ≈ US$0.07–0.12 (reasoning is `low`; observed completions 229–257 tokens).
- Pricing is published, not account-verified; the provider reports no cost; request/time limits are not a monetary guarantee. Estimated cumulative live spend before this run ≈ US$0.08–0.09.

## Acceptance / reporting
Report three results **separately**, never merged:
1. **Raw protocol compliance** — per request: strict-JSON compliant vs non-compliant (`protocol_compliance` counters).
2. **Compatibility recovery** — recovery attempted / recovered-valid / rejected with reasons; rejected shapes are findings, not retried.
3. **Independent task outcome** — only the evaluator decides success (product, price, availability). Also report whether the agent reached the detail page and called `done`; a recovered click alone is not success.

Also document: failure classification (`model_output_error`, `request_limit`, `timeout`, `infrastructure_error`, fidelity), requests actually sent, latency, provider-reported tokens, calculated vs provider-reported cost, whether the final step was narrowed, privacy inspection of artifacts before sharing, and reproducibility information. Smoke runs and mocked runs are not live trials.

## Stop conditions and approval gate
One run only. Stop on gate, failure, timeout or fidelity violation; no retries without renewed authorization. Before any authenticated request: guard/cap diff reviewed, offline + browser tests and CLI smoke passing, `.env` mode 600, and the user's explicit approval of the final command and limits. After the run, update `STATUS.md` and write Report 005; do not merge PR #3 without review.
