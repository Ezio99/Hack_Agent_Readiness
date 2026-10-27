# Task 004 — Meta compatibility validation and first live agent trial

**Status:** PROPOSED — **not approved.** No authenticated or billable request may be made until the
user explicitly approves the model, endpoint, test sequence and limits (all fields below).
**Date drafted:** 2026-10-27 (Australia/Sydney). **Report:** [004](../reports/004-first-live-meta-trial.md)

## Objective
Determine, with evidence, whether the Meta hosted API accepts the requests our reference agent
needs, then run **one** independently evaluated shopping-agent trial. Success of the compatibility
stages is not evidence of agent capability; only the independent evaluator grades the trial.

## Candidate configuration (to be confirmed by the user)
- Provider/endpoint: Meta, `https://api.meta.ai/v1` (Chat Completions). Unverified for this account.
- Model: `muse-spark-1.3` — candidate only; availability and compatibility unverified. No silent fallback.
- Credential: `META_MODEL_API_KEY` from the process environment or repository-root `.env`; never logged.
- Budget: provisional overall A$30 (not authorization). Pricing unverified → no dollar estimate
  until the user supplies verified pricing. Limits below are not a monetary ceiling.

## Test sequence (each stage gated; stop on first failure and report)
Stages A–C run in a **small, independently bounded probe runner** (to be implemented only after
approval): its own per-probe request cap and timeout, one attempt per probe, no automatic retries,
no coupling to the agent's request gate. It reuses the existing redactor/recorder, effective
configuration snapshot and usage accounting, and writes inspectable artifacts for every attempt.

| Stage | Request | Bound | Purpose |
|---|---|---|---|
| A | Minimal text chat completion | 1 request, tiny completion cap | Auth, model access, endpoint, usage reporting |
| B | Structured output with `response_format.json_schema` using the real Browser Use action schema | 1 request | Schema acceptance (strict-subset rules in `docs/META-INTEGRATION.md`) |
| C | Single base64 `image_url` screenshot from the controlled storefront | 1 request | Image input compatibility |
| D | One browser-agent run: `readiness run --kind discovery --seed 0 --max-steps 5 --timeout 60 --max-model-requests 5 --allow-model-calls` | 5 steps / 5 model requests / 60 s | One full trial, independently evaluated |

Stage D proceeds only after A–C pass and the user approves D. A failed paid experiment is **not**
retried automatically; a retry needs new approval.

## Acceptance criteria
- Every attempted request is recorded (including failures) with sanitized errors, limits, actual
  request counts and reported usage (`null` if unreported, never estimated as measured).
- Failures are classified: authentication, model access, schema rejection, image rejection,
  infrastructure, agent failure, or website limitation.
- Stage D result comes from the independent evaluator, never the agent's own claim.
- Artifacts are inspected for private content before any publication; nothing is committed.
- Report distinguishes completed checks from planned ones and states limitations. One trial is an
  existence proof of wiring, not a measurement of agent performance.

## Out of scope
Multiple trials, additional profiles/models/site variants, scoring, dashboard, registry,
accessible-label intervention, purchases, fallback providers.

## Approval record (fill in before execution)
Model: ____  Endpoint: ____  Stages approved: ____  Limits: ____  Spend authorization: ____
