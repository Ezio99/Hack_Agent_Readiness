# Plan: ONE full real-provider Ironbark investigation (proposal; nothing here has been run)

Needs the owner's explicit authorization of this plan, this goal, this context and the spend. The numbers are estimates from measured data (Step A: 3 taskgen requests, about 12 s each; EXP-2 pilot: US$0.01435 and 3-20 requests per browsing task, 25-100 s per task) and from the approved caps.

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
#    expected taskgen manifest sha256: d8164aec4a492183d73a90b4522e44ac0902f75837a2a3edac19e986d2c20067  (context sha256 8ee42e11863e207d...)

# 2. paid (only after explicit authorization); key from the repository .env
export SCANNER_DATA_DIR=scanner-data SCANNER_LIVE_ENABLED=1 SCANNER_LIVE_BUDGET_USD=2.00
readiness live run --goal "Can a shopper compare the hire price and availability of the two cheapest cutting tools?" --context-file docs/sample-context-ironbark.txt --confirm-spend 2.00
```
The baseline and investigator manifests depend on the generated tasks, so their hashes exist only at run time; each is approved only if it stays inside the grant (stage caps 1.40 / 0.40, max 4 tasks, 1 repeat, no trial retries, per-request cap 0.05, model, endpoint, capture and context hash). Any other stage, or a changed context, is refused.

## Stop conditions (kill switch `readiness scanner kill on`; do not retry)
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
