# Plan: ONE full real-provider Ironbark investigation (proposal; this full investigation has not been run)

Needs the owner's explicit authorization of this plan, this goal, this context and the spend. The numbers are estimates from measured data (Step A: 3 taskgen requests, about 12 s each; EXP-2 pilot: US$0.01435 and 3-20 requests per browsing task, 25-100 s per task) and from the approved caps.

## First full-run attempt (2026-11-01, job `live-cb37cc9849`): stopped at task generation, US$0.071032
Approved hash `3720fd83f9837be3da49106738c51dc06443e0838a04b463c6960eb0e512a8bd`. 12 proposals: 1 selected, 2 accepted but outside the goal's entity scope (whole-catalogue comparisons), 5 rejected by the start-page rule, 4 rejected because a `reach_page` target was a page title while the compiler expected a path. Coverage `insufficient`; no trial ran. Since then: `reach_page` accepts a path or a unique title, and the goal-bound prompt asks for distribution across entities/attributes and named comparison scopes. **That hash no longer applies; the hash below (`cd44f345…`) needs fresh authorization.** Nothing else changed (gate rules, relevance verifier, benchmark paths).

## Prior real spend and open exposure (record)
- **Completed real task-generation smoke test, job `live-96a6c3ab04` (2026-10-31, `muse-spark-1.3` at `api.meta.ai`, grant `taskgen` only, cap US$0.15):** 3 requests, **US$0.105844 calculated** (settles 0.036645 + 0.033298 + 0.035901; not a bill). It ran the earlier, pre-goal-binding generator; none of its tasks served the goal, which led to the current goal-bound design. The current prompts, schema and relevance verifier have **not** been run against the real model.
- **Unresolved: one stray reservation** from a test on 2026-10-31 (about 08:51 UTC): US$0.047682 upper bound reserved against `api.meta.ai` and never settled, so it is unknown whether a request left the machine (if it did, at most that bound, realistically about a cent). Not in any ledger the owner has reconciled; the provider usage page has not been checked. Now made impossible (see LIVE_SMOKE_TEST.md).
- Neither item is recorded in `collaboration/budget/programme-ledger.json` (unchanged, per the frozen-ledger rule); this document and LIVE_SMOKE_TEST.md are the record.

## What runs
Goal: *"Can a shopper compare the hire price and availability of the two cheapest cutting tools?"* Website context: `docs/sample-context-ironbark.txt` (client-supplied, unverified; guides, never evidence). One user grant, three stages, nothing else (no fix, no retest, no other site, no EXP-2).

| stage | provider requests | expected spend | internal hard cap |
|---|---|---|---|
| task generation (goal-bound, compact prompt) | 3 (max 3, no retries) | about US$0.06 (reservation bound 0.108; Step A actuals were 0.033-0.037 each on a prompt 3x larger) | US$0.15 |
| browser trials (4 tasks, 1 repeat, real Chromium) | about 20-35 (max 4 x 16 = 64) | about US$0.30-0.50 (0.0144 per request measured) | US$1.40 stage, 0.50 per trial, 0.05 per request |
| investigator (tools over the run's evidence) | about 5-12 (max 26, retries <= 1) | about US$0.10-0.25 | US$0.40 |
| **total** | **about 30-50 expected; 93 absolute maximum** | **about US$0.5-0.8 expected, up to about US$1.0** | **US$2.00 grant** (stage caps sum to 1.95) |
Plus, as documented, the overshoot of one request if a provider bills far above its estimate (the ledger records the truth and the stage stops).

Likely runtime: 8-12 minutes (inspect < 10 s; task generation about 40 s; trials 2-5 minutes; investigator 2-4 minutes). Worker deadline 30 minutes; the job is killed and marked timed_out at that point.

## Commands
```
# 1. free, offline: exact task-generation approval hash (binds goal, context, prompts, schema, model, endpoint, capture, caps)
readiness live run --goal "Can a shopper compare the hire price and availability of the two cheapest cutting tools?" --context-file docs/sample-context-ironbark.txt --plan
#    expected taskgen manifest sha256: cd44f345f6b26cebd6d501e90a139657094036dde278a7fc3c09e17f209331e7  (context sha256 8ee42e11863e207d...; ledger ceiling 2.00)
#    (an earlier revision of this plan printed d8164aec... : that was the hash with the SMOKE ceiling (US$0.15), computed by a plan command that did not use the full-run configuration. It never applied to this run.)
#    `--plan` now builds the manifest from the same options function (`worker.live_options`), model/endpoint settings and ceiling the worker uses; a test compares it with the options a real UI-style job passes to the pipeline.

# 2. paid (only after explicit authorization); key from the repository .env
export SCANNER_DATA_DIR=scanner-data SCANNER_LIVE_ENABLED=1 SCANNER_LIVE_BUDGET_USD=2.00
readiness live run --goal "Can a shopper compare the hire price and availability of the two cheapest cutting tools?" --context-file docs/sample-context-ironbark.txt --confirm-spend 2.00
```
The baseline and investigator manifests depend on the generated tasks, so their hashes exist only at run time; each is approved only if it stays inside the grant (stage caps 1.40 / 0.40, max 4 tasks, 1 repeat, no trial retries, per-request cap 0.05, model, endpoint, capture and context hash). Any other stage, or a changed context, is refused.

## How to stop a running job (read before launching)
`readiness scanner kill on` only writes the kill-switch file: it **blocks new jobs** and does **not** terminate an active one.
1. **Primary: the UI Cancel button** (the session that started the job). It marks the job cancelled and sends SIGTERM to the worker's whole process group (browser included).
2. **Fallback: authenticated admin cancellation**, which does not need the browser tab: start the server with `SCANNER_ADMIN_TOKEN` set, then `curl -X POST http://127.0.0.1:8100/api/admin/kill -H "x-admin-token: $SCANNER_ADMIN_TOKEN" -H 'content-type: application/json' -d '{"enabled": true}'` (sets the kill switch and cancels every running job; `{"enabled": false}` clears the switch afterwards).
3. Last resort: the worker's own 30-minute watchdog; or SIGTERM to the worker pid recorded in the job file.
A cancelled job keeps what was reserved counted in the ledger. The investigator's single retry per request (bounded by its US$0.40 stage cap) is allowed; there is no automatic restart of the whole investigation.

## Stop conditions (stop with Cancel or the admin fallback above; do not retry)
- Any state other than `completed`: `awaiting_approval`, `stopped` (budget, coverage or scope), `failed`, `timed_out`.
- Total committed above US$1.30, or any stage above 2x its expected spend, or any bound violation.
- Goal coverage `insufficient` (the run stops after task generation; nothing is spent on trials).
- A trial that is void (provider/infrastructure/fidelity), a provider error, or a model-output validation error.
- The key or the context text appearing anywhere it should not (job record, logs, observations, findings).
- Wall-clock above 20 minutes.

## Success criteria
1. **Plumbing:** `completed` within the grant; ledger, job view and export agree to the cent; exactly three USER-GRANT approvals (`taskgen`, `baseline_trials`, `investigate`) and the `live-grant`, `client-context` artifacts; `open_reservations` 0; the key absent from every file; replay reopens with zero further requests.
2. **Goal coverage:** reported as complete or PARTIAL with every unsupported/unverified aspect named (the one expected limit: no exact "top-2" ranking criterion). At least one verified task for each of price and availability; all three cutting tools touched across the set.
3. **Independent verification:** every selected task passed the unchanged gate; none contains its answer; baseline trials evidence-graded; rule top-up 0; every proposal accounted for.
4. **Provenance:** context shown only in its own labelled block; no observation, hypothesis, finding or proposal contains it; investigator hypotheses cite site evidence ids; every recommendation labelled UNVALIDATED unless a verifier supported it (and even then not a measured effect).
5. **Findings to record, not pass/fail:** real per-request cost and tokens per role; requests per trial and pass rate; whether the investigator produced verified, supported or only unverified hypotheses; task quality (do the questions read like what a shopper would ask).
A failed criterion is a finding about the build, not a reason to spend more: report and stop.
