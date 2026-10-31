# Live evaluation, milestone M1 (real-model path; restricted to Ironbark)

M1 turns the M0 slice into a path a real model can drive, **without any real model having been invoked yet**. Everything below has been exercised only against a loopback stand-in (the dev provider). A real paid smoke test needs the owner's explicit approval (see the end).

## What a user sees
Investigation page -> choose Ironbark and a goal -> **Live (real model, maximum US$2.00)** -> *Review and start live evaluation* -> a confirmation panel states the maximum spend, the model, the goal and that the server enforces the cap -> tick *I authorize up to US$2.00 for this one evaluation* -> *Confirm and start*. The page then shows the live/dev-provider label, stage progress, recorded cost against the cap **by stage**, the approvals the run recorded for itself, browser trace events, and, if a run stops for a reason a person must resolve, an explicit **"Stopped: waiting for an approval this evaluation may not grant"** (not "failed"). Finished runs open in the existing report view and reopen later from history with no execution.

## What the backend does
| concern | mechanism |
|---|---|
| goal-driven discovery and task generation | `worker.execute_live` passes the user's goal as `goals={"focus": goal}`; the existing task-generation stage puts it in every proposal prompt. Tasks are accepted **only** if the existing independent gate can verify them against the captured site (criteria evaluated by code, never by the model). `rule_topup=False`: no rule/benchmark tasks are substituted; too few verifiable tasks fails the stage |
| real browsing, evidence, traces, investigator, recommendations | the unchanged live branch of `investigate.flow.build` (Meta client behind the reserve-before-send spend gate; real Chromium agent; deterministic claim verifiers; recommendation stage) |
| authorization | the user's confirmation (which must equal the server's cap; the client names no budget) becomes ONE **grant** (`live/grant.py`) bound to job, owner session, run, target, goal, budget, model, endpoint, site-capture hash and an explicit stage list (`taskgen`, `baseline_trials`, `investigate`), covered by a hash |
| approval gates | each paid stage still presents its manifest. The worker records an ordinary `approvals.jsonl` line **only** via `Approver.decide`: right job/owner/run, live run, stage in scope, manifest hash matches, model + endpoint + capture match, no cap above the budget, committed + stage cap within the budget. Notes say `USER-GRANT approval ... grant <hash>` so they are distinguishable from owner CLI approvals. `apply_fix`, `post_trials` and anything unknown are refused -> job state `awaiting_approval`, nothing spent |
| budget | the run's ledger ceiling **is** the grant budget (`total_cap_usd`); stage caps and the per-request cap are the existing ones (taskgen 0.15 + trials 1.40 + investigator 0.40 = 1.95 of 2.00); a settled cost above its reservation closes the gate (bound violation) and the job ends `stopped` (budget). The server also caps total promised + committed live spend (`SCANNER_LIVE_BUDGET_USD`) |
| credentials | the model key lives in the server's environment/`.env` only. It is passed to a worker **only for an approved live job**, via environment (never argv or a file); mock workers and the browser never receive it; no response, job record, run file or log contains it (tested) |
| lifecycle | one job at a time; cancel kills the worker's whole process group (browser included) and keeps what was reserved counted; the worker enforces its own deadline (30 min for live); a restart marks orphaned jobs failed; `awaiting_approval`/`stopped` never hold the slot |
| scope | live is refused for any target except Ironbark; no URL field exists |

## Server configuration (operator only)
`SCANNER_LIVE_ENABLED=1`, `SCANNER_LIVE_BUDGET_USD=<total>`, `LIVE_JOB_CAP_USD` (default 2.0), `LIVE_MODEL_BASE_URL` (default `https://api.meta.ai/v1`; plain http is accepted only on loopback), the key in `META_MODEL_API_KEY` or the repository `.env`. Live is offered in the UI only when all are present.

## Zero-spend demonstration
```
python -m agent_readiness.live.devprovider --root scanner-data/live --port 8199      # NOT a model: fixtures built from the run's own capture
export SCANNER_LIVE_ENABLED=1 SCANNER_LIVE_BUDGET_USD=10 LIVE_MODEL_BASE_URL=http://127.0.0.1:8199/v1 META_MODEL_API_KEY=any-string
readiness scanner serve ...   # as in docs/LIVE_M0.md
```
Runs, approvals, spend and replay are real; token counts and cost are calculated from fixture output, and every screen and export says **DEV PROVIDER**. `--usage-scale` makes it bill more than reserved, to exercise the budget stop.

## Still requires a real paid smoke test (not run; needs approval)
1. A real call to `api.meta.ai` with a real key: endpoint, auth header, `response_format` json_schema acceptance for the task-proposal and investigator schemas, `reasoning_effort`, usage fields (`completion_tokens_details`).
2. The real model producing >= 4 **gate-verifiable** tasks for a free-text goal (a failing/too-few result stops the stage; that behaviour is untested against a real model).
3. The real browsing agent on Ironbark with real vision/DOM prompts: per-request upper bounds versus the US$0.05 cap, `max_requests_per_trial`, completion rate, and whether total cost for 4 tasks stays well inside US$2.
4. The real investigator: structured output validity, citations, how often hypotheses verify; recommendation quality (it is only validated structurally here).
5. End-to-end cost and duration against the 30-minute deadline; the first-request reservation and the 1.95 allocation under real token counts.
6. Behaviour of the spend gate on a real provider error/timeout mid-run (reservations stay counted; ambiguous-batch recovery path).
