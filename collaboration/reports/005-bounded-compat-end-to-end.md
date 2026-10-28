# Report 005 — Bounded end-to-end compatibility trial (Task 005)

**Date:** 2026-10-28 · **Code:** `5fa1e0c` (clean checkout, branch `hackathon/task004-stage-a`) · **Artifact:** `runs/20261028T001011-6b2348243a3a/` (untracked, ignored by Git; key not present in the artifact — checked by searching for the credential value)

## Authorization and command (run exactly once, no retries)
User-approved single run. Preflight: HEAD = origin, tree clean except untracked `uv.lock`, `.env` mode 600, full schema hash `c80ef8b8…9a194` equals the live schema, done-only hash `7964acb5…5dc1`.
```
readiness run --profile natural-shopping-v3-compat1 --kind discovery --seed 0 --max-steps 6 --max-model-requests 6 --timeout 120 --allow-model-calls --expect-schema-sha256 c80ef8b813abef0b2afd79c83a6f31e857c0101ea8730952ee78d61e65f9a194 --max-estimated-cost-usd 0.04 --max-cumulative-estimated-cost-usd 0.25
```
`muse-spark-1.3`, `reasoning_effort: low`, 4,096 completion cap, 30 s model timeout, Chrome 145.0.7632.6.

## Results (reported separately)
| | Result |
|---|---|
| **Independent evaluator** | **PASS** — "All required fields match inventory truth and task constraints". Answer `{"product_id":"AR-7488","price_cents":2900,"available":true}`. Run status `completed` / `agent_done`. |
| **Raw protocol compliance** | 1 of 2 HTTP-200 responses compliant. Request 1: non-compliant (102-char prose sentence + one JSON object). Request 2: pure JSON, compliant. |
| **Compatibility recovery** | 1 attempted, 1 recovered and schema-valid (`prose_prefix_single_json_object`), 0 rejected. Request 2 needed no recovery. |
| **Guard / cap** | No fidelity violations, no schema narrowing, no cost-limit block, 0 requests blocked; both requests full-schema (the final-step exception was never needed). |

Interpretation: with the compat parser, the agent completed the seed-0 discovery task end to end, in 2 of 6 allowed steps. Without recovery, the first step would have failed under the strict profile (consistent with Stage D). This is one run of one seed: it shows feasibility, not a success rate and not website readiness.

## Actions executed
1. Step 1 (recovered response): `click` index 174 → `Clicked a "Linen Cushion"`; the browser reached the product detail page.
2. Step 2 (compliant response): `done` with the answer above; independently graded PASS.
Model/browser actions beyond the initial navigation: 2. No trace step shows a blocked or stale invocation.

## Usage and time
| Request | Prompt | Completion (reasoning) | Latency | Finish | Request id |
|---|---|---|---|---|---|
| 1 | 9,445 | 279 (90) | 3.26 s | stop | `c661507d…` |
| 2 | 8,927 | 636 (422) | 3.25 s | stop | `6cad568a…` |
Total 18,372 prompt / 915 completion tokens; run 11.9 s of the 120 s limit.

## Cost (calculated, NOT provider-reported; published prices $1.25 / $4.25 per M)
Request 1 ≈ US$0.0130, request 2 ≈ US$0.0139, **run ≈ US$0.027**. The guard's worst-case estimate of what was allowed onto the network was US$0.0622 (limit US$0.25; per-request ceiling US$0.04 not reached). Cumulative live spend across all experiments ≈ US$0.105–0.115 (calculated).

## Failures and limitations
- No failures in this run. Request 2's reasoning share (422 of 636 tokens) was larger than request 1's.
- Single run, single seed, one profile; the prose-prefix behaviour appeared on step 1 (now 5 of 5 observed first steps) but not on step 2 — a sample of one for later steps.
- The compat layer sits between the provider and the agent; do not pool this with strict-profile results.
- The final-step guard exception and cumulative cap were not exercised live; they were only offline-tested.
- Cost is calculated; the provider reports none. Artifacts contain model text and screenshots: inspect before sharing.

## Next (needs separate approval; none authorized)
Options: repeat on additional seeds / the availability task to measure variance, or stop paid trials and finish documentation. No additional paid calls or PR #3 merge without approval.
