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

## Step A: taskgen-only smoke test (implemented; NOT run; needs the owner's explicit spending authorization)
What it does: the normal live path (goal-driven proposal prompts -> real Meta endpoint -> independent gate -> freeze) for **task generation only**. One grant covering `taskgen` alone, budget US$0.15, per-request cap US$0.05, **no retries**, no rule top-up. The worker runs the pipeline `until="freeze"`; a manifest for any other stage is refused. No browser trial, investigator or recommendation can run.

**Maximum provider requests: 3** (three fixed batches, one request each). Reserved upper bounds 0.04953 + 0.04953 + 0.049531 = **US$0.1486** (`worst_case_stage_usd`), each under the 0.05 per-request cap and the sum inside the 0.15 stage cap and ledger ceiling. Expected actual cost about US$0.02-0.05. Plus, in the worst case, one request's overshoot (see LIVE_M1.md). The approval manifest is bound to the goal: its hash is printed by the free `--plan` step. For the exact goal below the expected taskgen manifest SHA-256 is `adca6f571e334318a2c9a04fc23fc24ba14de8e091da283c03b7fec59ac86be4` (a different goal gives a different hash).

```
# 1. free, offline: prints the exact manifest hash, request count, caps and reservations; no key, no network
readiness live smoke --goal "Can a shopper compare the hire price and availability of the two cheapest cutting tools?" --plan

# 2. the paid step (only after explicit authorization). The model key comes from the repository .env (mode 600) or the environment; nothing else is needed
export SCANNER_DATA_DIR=scanner-data SCANNER_LIVE_ENABLED=1 SCANNER_LIVE_BUDGET_USD=0.15
readiness live smoke --goal "Can a shopper compare the hire price and availability of the two cheapest cutting tools?" --confirm-spend 0.15
```
It prints, as JSON, the job state and a smoke report: **task yield** (requests made, tasks proposed/accepted/rejected, needed 4), **independent verification** (gate rejection reasons by category with examples; accepted tasks by criterion kind; no criteria or answers), **relevance to the goal** (a lexical heuristic plus the accepted questions for a person to judge), **actual cost** (per request: reserved, settled, tokens; unsettled requests), and **provider compatibility** (per batch: status, reported model, attempts, whether usage had prompt and completion tokens, any structured-output diagnostics or provider error). Exit code 0 only if the job completed with at least 4 verified tasks.

Stop conditions: any `stopped`/`awaiting_approval` state, a provider error, a bound violation, fewer than 4 verified tasks (reported, not retried), the key in any output. Success: completed within the grant, <= 3 requests, committed spend <= US$0.15 and equal in ledger, report and job view, >= 4 gate-verified `model`-sourced tasks, `rule_topup` 0, and a human reading of the questions finds at least 2 related to the goal.

## Incident record (2026-10-31, found while testing this option)
The following is an INCIDENT, recorded separately from any authorized smoke-test spending. A CLI test with `SCANNER_LIVE_ENABLED=1` made `load_config` read the repository `.env`, so the model key became available and the default endpoint was the real one: the test started a real worker that approved `taskgen` and **reserved one request (US$0.047682 upper bound) against `api.meta.ai`** before the test cancelled it 1.6 s later (pytest temp ledger only; no settle, so it is unknown whether the request left the machine; if it did, the cost is at most that bound and realistically about a cent). Nothing else ran. Fixes: `load_repo_env()` never reads the implicit `.env` under pytest; `JobManager.create` and the worker both refuse a live job against a non-loopback endpoint from a test process; a regression test booby-traps process spawning. The owner may want to check the provider usage page for one stray request on 2026-10-31 around 08:51 UTC.
## Step B: one full evaluation through the UI (after Step A, separately authorized)
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

Further safeguards added in the final readiness check (after finding that importing Browser Use loads the operator's `.env` key into `os.environ` of ANY Python process, including pytest and mock workers): `agent_readiness/netguard.py` makes the whole pytest process, and every worker a test spawns, loopback-only (a connection to anything else raises); `tests/conftest.py` installs it and removes the model key before every test; workers neutralise `dotenv` before importing Browser Use, so a worker holds only the credential the manager gave it; the smoke-scope check happens before any run is built. Nothing about the incident's billing is inferred: an unsettled reservation is only an upper bound.

## Result of the first real Step A (2026-10-31, job live-96a6c3ab04) and the response
3 requests, US$0.105844 calculated, 12 proposed, 5 gate-rejected, 7 gate-accepted; the old stage then silently kept the first 4 by position and dropped 3 gate-passed tasks unreported. None of the tasks served the goal (the answerability gate does not check relevance). Response (goal-bound generation): the goal is a binding objective with a decomposition step in the schema; an independent relevance verifier (`taskgen/goal.py`, domain vocabulary injected from `live/lexicon.py`) judges every gate-accepted task by what its criterion touches, separately from the gate; selection ranks by relevance, never pads with unrelated tasks, and every proposal is accounted for in the report. For the exact goal the captured site supports availability (three cutting tools) but exposes no labelled price fact, so at most 3 goal-relevant verified tasks exist and the stage reports "goal coverage insufficient" instead of substituting. The approval manifest changed with the prompt and schema: the hash above is the new one; the earlier `a2ce6642...` no longer applies and any further paid run needs fresh authorization.

## Capture fix and bounded coverage (after the goal-bound run design)
Evidence from Ironbark's rendered pages: hire rates (`<b>$110</b><span>Per day</span>`), the product page's dated status ("Today, Mon 2 Nov: fully booked") and the calendar cells (`14 Nov` + `Booked`) are all VISIBLE to a browser agent (the model view in the pilot shows them) but were not extracted as facts: a CAPTURE limitation, not a website one. The inspector now records exactly those three patterns as label/value facts (`how`: amount-caption, dated-status, calendar-cell; values are the page's own text, a test asserts each appears verbatim in the rendered page). Goal coverage for goal-bound runs is now bounded and evidence-based: every aspect the goal asks for that the site can express must be covered by a selected relevant verified task (up to 4); aspects it cannot express are reported by cause (website / capture / verifier limitation) and do not block. For the exact goal the offline re-test now covers price and availability of all three cutting tools; the one remaining limit is a VERIFIER limitation (no exact top-N ranking criterion), and the gate still rejects what it must. The reservation margin under the US$0.05 per-request cap is thin (0.0495): a larger prompt would make the gate refuse (safe, no spend), not overspend. The approval hash above is the current one; earlier hashes no longer apply.
