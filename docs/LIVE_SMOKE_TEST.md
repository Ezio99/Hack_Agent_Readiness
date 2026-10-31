# Real-provider smoke test for live evaluation (proposal; nothing here has been run)

**Authorization needed before any of it runs:** the owner's explicit approval of this procedure, its cap and the run. Until then no real model is called. The numbers below are planning estimates built from measured data (EXP-2 pilot: US$0.01435 per browsing request on Ironbark, 3-20 requests per task) and the approved manifests.

## Estimated cost (calculated at published prices; not a bill)
| stage | expected | likely range | hard stage cap |
|---|---|---|---|
| task generation (3 requests) | US$0.04 | 0.02-0.08 | 0.15 (reservations 3 x 0.048) |
| browsing, 4 tasks x ~10 requests | US$0.58 | 0.25-0.95 | 1.40 |
| investigator (~5-10 requests) | US$0.15 | 0.05-0.30 | 0.40 |
| **total** | **about US$0.75** | **0.35-1.3** | **1.95 allocated of the US$2.00 grant** |
Plus, in the worst case, the overshoot of one request (see "Is US$2 a real ceiling?" in LIVE_M1.md).

## Preconditions (no spend)
1. This PR is merged (or the branch is checked out) and its CI is green; `git status` clean; EXP-2 untouched.
2. Server environment: `SCANNER_LIVE_ENABLED=1`, `SCANNER_LIVE_BUDGET_USD=2.5` (one run plus a little room), `LIVE_JOB_CAP_USD=2.0`, key in `.env` (mode 600) or the environment, **no** `LIVE_MODEL_BASE_URL` (default Meta https), **no** `LIVE_ALLOW_DEV_PROVIDER`.
3. `readiness investigate l0 plan` shows the endpoint, model and prices as expected. If the L0 probe evidence from the earlier capability probe is not current, run the L0 probe first (its own approved manifest, at most US$0.04 for all four requests); otherwise skip it.
4. Credential hygiene: the key value is never printed; `git grep` for it is empty; the dev provider is not running.
5. A second terminal ready to run `readiness scanner kill on` (kill switch: refuses new jobs and cancels the running one).

## Step A (recommended, needs a ~20-line change to be built and reviewed first): taskgen-only
Add an operator-only `LIVE_SMOKE_UNTIL=taskgen` (worker stops after the `freeze` stage). Cost <= US$0.15 worst case, about US$0.04 expected. It answers questions 2 and 3 below at one-fifth of the risk. Skip only if the owner accepts going straight to Step B.

## Step B: one full evaluation through the UI
1. Open Investigation, sign in, choose **Ironbark**, **Live**, goal: *"Can a shopper compare the hire price and availability of the two cheapest cutting tools?"* (specific, checkable, related to Ironbark's actual catalogue), read the confirmation (US$2.00), tick, confirm.
2. Watch: stage progress, spend by stage, approvals in the trace, browser trace events. Keep the kill switch ready.

### Expected outputs
- Three approvals in `approvals.jsonl`, each `USER-GRANT approval ... grant <hash>` for `taskgen`, `baseline_trials`, `investigate`; `live-grant` artifact; no approval for any other stage.
- 4 frozen tasks with `source: model`, `rule_topup: 0`, each accepted by the gate.
- 4 baseline trials with `mode: live`, evidence-graded; at most 16 requests each.
- An investigation with `mode: live`, `finished: true`; hypotheses labelled supported/unverified; proposals labelled UNVALIDATED.
- Committed spend equal to the ledger and to the export; `open_reservations: 0`; the key absent from every file in the run directory and the job record.
- Replay: reopen the finished job from history and export it: zero further requests.

### Stop conditions (stop and report; do not retry)
- Any stage's spend more than 2x its expected value, or total committed spend above US$1.30 (kill switch).
- Any refusal by the grant (`awaiting_approval`), any bound violation, any `stopped` job, any provider error that is not a clean rejection.
- Fewer than 4 gate-verifiable tasks (the stage fails by design; do not re-run with rule top-up).
- The key appears in any output, response or file.
- Wall-clock above 20 minutes.

### What counts as success (smoke test, not an evaluation of the site)
1. **Plumbing:** completed within the grant, total committed <= US$1.30 and <= the cap; ledger, export and UI agree to the cent; approvals/artifacts as above; cancel not needed.
2. **Goal dependence (observation, not proof):** at least 2 of the 4 generated tasks are recognisably about price or availability, as the goal asked; the proposal prompt hash differs from one produced with a different goal.
3. **Independent verification preserved:** every task has a gate-computed criterion; none contains its answer; evidence-backed grading ran on every trial.
4. **Honest provenance:** every recommendation is labelled; nothing in the UI describes an unvalidated proposal as a verified improvement.
5. **Findings to record, not pass/fail:** real per-request cost versus the 0.0144 planning figure; requests per trial; investigator hypotheses that verified; any model-output validation errors.

A failed criterion is a finding about the build, not a reason to spend more: report it and stop.
