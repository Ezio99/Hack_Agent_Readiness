# Report 016j — L1a configuration and observability (after L0 attempt 3 PASS)

**Read Part A first.** Part A is the final configuration decided by the owner and implemented in this PR; Part B is the earlier proposal, kept only as history.

## PART A — FINAL APPROVED CONFIGURATION (governs; implemented in PR #47, still a draft until merged on owner approval)
Decisions: (1) taskgen = Option B: 3 batches x 4 proposals, 6,144 completion tokens per request, **no retries, no feedback round**, stage cap stays US$0.15; (2) investigator cap 4,096 with US$0.40 stage cap; (3) **enforceable baseline stage cap US$1.40**, overall ceiling US$2.05, US$0.10 unallocated; (4) keep acceptance / de-duplication / leakage gate and rule fallback; one bad batch must not discard good ones; spend-gate violations and other critical failures stop safely; (5) every batch prompt, request limit, cap and stage limit in the approval manifests, and execution must match; (6) offline regression tests.

### Also in this PR (from the first round, still in force)
- Sanitized per-call log `calls/<stage>.jsonl` (finish reason, prompt/completion/reasoning tokens, cap use, content length; provider-error category/status/summary; no prompts or model text), finish reason and reasoning tokens in the private transcript and replay, sanitized fields on successful L0 rows (L0 hash unchanged).
- Investigator cap 4,096; reasoning effort, caps and the enforced reservations listed in the taskgen and investigate manifests.

### What changed in round 2 (code)
- `taskgen/propose.py`: `MAX_TOKENS=6144`, `BATCHES=3`, `BATCH_SIZE=4`, three fixed batch "emphasis" lines (fact retrieval / navigation and deep pages / comparisons and filters) so **no batch depends on another's output** and all three prompts are known and hashed before approval; `batch_requests()` builds the exact requests; `propose()` gains `angle`, `retries` and `request` parameters (stage uses `retries=0`).
- `taskgen/stage.py`: `taskgen_stage` sends the three batch requests once each. Every finished batch (ok / invalid / provider error) is persisted to `private/taskgen-batch-<i>.json` *before* anything else. Per-batch **validation failure** (`StructuredOutputError`) is recorded and the other batches are unaffected. A **provider error** keeps accepted work and stops issuing requests. A **spend-gate Halt / refusal, a gate bound violation, or any unexpected exception** propagates (critical): no half-written report, completed batches are on disk, and a restart (an owner decision) never re-requests them (the gate's request counter and ledger also persist, so the 3-request limit holds across restarts). The per-draft gate (acceptance, fingerprint de-duplication across batches, leakage checks) and the rule top-up are untouched.
- `allocation.py` (new): the stage caps (0.15 / 1.40 / 0.40), per-request cap 0.05 and an `allocation(ceiling)` summary; used by the manifests and the code that enforces them.
- `spend_gate.py`: optional `scope_run_ids` + `scope_cap` give a **stage cap spanning many gates** (reserved + settled, read from the durable ledger, so it survives restarts and ignores other stages); a recorded bound violation now keeps a *new* gate instance closed after a restart. Defaults leave every other live path unchanged.
- `trials/stage.py`: baseline trials build each trial gate with the stage scope and cap taken from the manifest (`stage_cap_usd`, option `baseline_stage_cap_usd`, default 1.40). A trial that would breach it is refused, ends void, and the stage halts (existing rule); the patched-arm manifest is unchanged (the cap key is dropped there).
- `flow.py` / `investigator/stage.py`: manifests list batches, per-batch prompt and request hashes, retries 0, no feedback round, completion caps, reasoning effort, per-request reservations, worst case, failure-handling policy and the allocation; the gates are built from the same constants (a test compares).
- Test changes needed by the decisions: taskgen tests that assumed one request plus a feedback round now script three batches; the bug-hunt test that asserted "no per-stage caps" now asserts the cap exists and fits inside the one ceiling; the live-flow test expects the three-batch manifest.

### Crash / restart safety (review round)
A request can be reserved and sent, and the process killed before its result is written. To prevent a silent paid re-send: before each batch request a **durable attempt marker** (`private/taskgen-attempt-<i>.json`: request hash, number of ledger reservations at that moment) is written. A finished batch is persisted right after the response. On restart: a persisted result is reused; a marker **without** a result is resolved from the durable ledger - if no reservation was added since the marker, the request provably never left the process (reserve-before-send) and the batch is simply attempted; if a reservation exists (with or without a settlement) the attempt is **ambiguous** and the stage stops with `AmbiguousBatchAttempt` (a `Halt`), sending nothing. The owner then decides explicitly: `readiness investigate recover-batch RUN_DIR --batch i --abandon --note "<who decided what>"` records the batch as `abandoned` (drafts none, note and attempt kept; the reservation stays counted) and re-running the stage requests only the remaining batches. A re-send of the ambiguous batch is deliberately impossible inside the approved manifest: the request counter (3) includes it. The three-batch configuration, zero retries, allocations and approval gates are unchanged; the taskgen manifest now also states this policy (`on_interrupted_request`).

### Revised hashes (computed in-process from free inspect output; no gate or run started; `--total-cap-usd 2.05`, `n_tasks=8`)
- L0 `0ce19b499a243252ffbf4f0172f8e084cbd0119f3d7fad2ae3b90ca5b0490b86` (unchanged).
- Taskgen `site-5`: **`ad98b233aca962e308cc036a8b1a9840382db1f2eaba572156f958299026276c`** (supersedes `3ce7be84…`, `a38374df…` and `d9c894cd…`). `site-4` for reference: `aa41474f2a880b6a3b45cf26a05ff2a51583d2d0345010f521776d092dbf614f`.
- Baseline-trials and investigate hashes depend on the frozen tasks and the baseline attribution and are printed at their own gates; both manifests now contain the new fields, so no earlier value is valid. The hash covers `--total-cap-usd`, so L1a must be started with 2.05.

### Spending (calculated upper bounds, site-5)
| stage | requests | per-request reservation | stage worst case | stage cap |
|---|---|---|---|---|
| taskgen | 3 (no retry) | US$0.02847 / 0.02849 / 0.02846 (< 0.05) | **US$0.0854** | 0.15 |
| baseline trials (8 tasks, K = 1) | <= 16 per trial | <= 0.05 | bounded by the enforced **stage cap 1.40** (per-trial cap 0.50) | 1.40 |
| investigate (<= 12 tool calls) | <= 26 | first ~0.0195, ~0.034 at full history (< 0.05) | bounded by stage cap 0.40 | 0.40 |
Allocated 0.15 + 1.40 + 0.40 = **US$1.95**; ledger ceiling **US$2.05**; unallocated **US$0.10** (A$0.15); US$2.05 = A$3.08 against A$43.79 remaining. Expected spend remains about US$1.0. The programme ledger is not modified.

### Remaining risks
- **6,144 may still be too small for a batch** (P5: ~93 % reasoning; a real batch has a larger prompt). A truncated batch is recorded `invalid` with finish reason / reasoning tokens (new diagnostics), the other batches survive, and the rule fallback guarantees >= 4 tasks; but if all three fail, L1a would proceed on rule tasks only (visible in the report as `by_source.model = 0`).
- Three fixed "emphasis" lines reduce but do not remove duplicate proposals; duplicates are rejected by the gate, so up to 12 proposals may yield fewer than 8 distinct accepted tasks.
- Stage caps include reservations (upper bounds, including the browser path's screenshot headroom), so the baseline cap can bind earlier than actual spend would; a trial refused by the cap is void and halts the stage.
- A gate bound violation can still overshoot by one request before the gate closes; the closure now survives restarts.
- Investigator: the final `finish` step can still be truncated at 4,096; the run then ends `incomplete` and keeps the evidence gathered.
- Taskgen/investigate gates are still created per process: a restart after a halt needs a new owner approval of the (unchanged) manifest, and the investigator is not resumable mid-conversation (unchanged).


---

## PART B — HISTORICAL PROPOSAL (superseded; kept for the record)

> Everything in Part B is the first proposal written after L0 attempt 3. **It is not the approved configuration.** Where it differs (taskgen route, baseline stage cap, manifest hashes, spend numbers) Part A governs. Option A / A' / B, the "taskgen stays 2,500" statement and every hash in Part B are obsolete.

_Historical._ Offline only. L0 artifacts, the programme ledger and every earlier manifest are untouched; no model call was made. L0 manifest hash is unchanged (`0ce19b49…0b86`).

## B1. Measurements that drive the proposal (still valid as evidence) (L0 attempt 3, `l0-probe-3`)
Completion tokens include hidden reasoning. Visible tokens are *estimated* from raw-text length (≈3.5 chars/token, local private file), so reasoning shares are estimates, not provider counts.

| request | shape | completion tokens | est. visible | est. reasoning |
|---|---|---|---|---|
| P1 / P2 | trivial echo | 779 / 656 | ~5 | ~99 % |
| P3 / P4 | 3-ish hypotheses | 1,434 / 1,281 | ~400 | ~66-72 % |
| P5 | **3 tasks** | **3,015** | ~210 | **~93 %** |
| P6 | hypotheses + injection | 1,291 | ~290 | ~77 % |
Reasoning is large and **not proportional to visible output** (3 small tasks cost ~2,800 reasoning tokens, a 400-token hypothesis list ~1,000). Prompt tokens were 65-467. Earlier: 491 live agent responses (effort low, cap 4,096): completion median 300 / p90 447 / max 979.

## B2. Original proposal (HISTORICAL: item 4 was then undecided; it has since been decided as Option B - see Part A)
1. **Observability (implemented).** `RecordingClient` now writes a *sanitized* per-call log `calls/<stage>.jsonl` for every response and every classified provider error: purpose, request-hash prefix, `finish_reason`, prompt/completion/reasoning tokens, `max_completion_tokens`, `cap_used_pct`, `content_chars`, cost, mode (errors: category, HTTP status, sanitized summary). No prompts, no model text. The private transcript additionally keeps `finish_reason` and `reasoning_tokens`, and replay restores them. L0 result rows for *successful* requests now carry the same sanitized fields. L0's approved manifest does not change.
2. **Manifests explicit (implemented).** The taskgen and investigate stage manifests now list `reasoning_effort`, `max_completion_tokens`, the fixed input allowance and the **enforced** reservation per request (`per_request_reservation_usd`, `first_request_reservation_usd`), computed with the same function the gate uses. The baseline-trials manifest is unchanged (agent profile `suite-v2-compat1` already pins effort low / 4,096).
3. **Investigator cap: 4,096 (implemented, `STEP_MAX_TOKENS`).** 1,800 left no headroom (P3 used 1,434, ~70 % reasoning); 4,096 is 2.9x the largest L0 hypothesis request and the validated production cap. Reservation: ~US$0.0195 for the first request, ~US$0.034 with a full 12-round history (assumed 46k chars) - always below the US$0.05 per-request cap; the US$0.40 stage cap is unchanged and still binds. Risk: the final `finish` step carries all hypotheses; if it is cut, the run ends `incomplete` (evidence already collected is kept). The new call log will show `cap_used_pct` and `finish_reason: length`.
4. **Taskgen - decision needed (not implemented; the PR keeps the current 2,500 and lists it).** 2,500 is below P5's 3,015 for *three* simple tasks, and real taskgen asks for `n + 2 = 10` tasks with a larger site summary (~1,100 prompt tokens) and a nested criterion per task. Visible output for 10 tasks is only ~1,500-2,000 tokens, but reasoning is the unknown (P5 suggests thousands).

### Taskgen options (reservation = what the gate reserves per request, site-5, incl. 128-token allowance)
| option | requests (max, incl. 1 retry + feedback round) | cap/request | reservation/request | stage worst case | stage cap 0.15 | prompt / criteria change |
|---|---|---|---|---|---|---|
| now (2,500) | 4 | 2,500 | US$0.0129 | US$0.052 | fits | none - **likely truncates** |
| **A** single request | 4 | 8,192 | US$0.0371 | US$0.148 | fits (1 % margin) | none |
| A' single request | 4 | 6,144 | US$0.0284 | US$0.114 | fits | none |
| **B** 3 batches x 4 proposals (+retry) | 6 | 6,144 | US$0.0284 | US$0.170 | **exceeds** -> needs stage cap US$0.20 (approval) or fewer retries | per-batch "angle" lines in the prompt (all batch prompts known up front, hashed in the manifest); gate/criteria unchanged |
Common to all: every draft already passes the same independent gate (acceptance, fingerprint de-duplication, leakage checks), so **no evaluation-criteria change** is needed for either route; batching only needs a loop in `taskgen_stage`, a `max_requests` change and per-batch prompts. The rule top-up still guarantees >= 4 tasks if the model output is unusable.
- *Reliability:* A concentrates risk: one truncation costs the whole stage (and a retry at the same cap) and falls back to rule tasks, which are lower quality. B isolates failures (a truncated batch costs one request) and a 4-task batch is closer to P5's measured 3-task shape.
- *Cost:* actual billing follows actual tokens. Reasoning looks per-request, so B probably costs more in expectation (3 reasoning passes, est. US$0.04-0.06) than one successful A (est. US$0.02-0.04), but A that truncates costs two failed requests (~US$0.07) plus a bad task set. All of this is an estimate; there is no 10-task measurement.
- **Recommendation: B** (3 batches x 4 proposals, cap 6,144) because the only taskgen-shaped measurement (P5) is the one most dangerous for a single large request; it needs your approval to raise the taskgen stage cap to US$0.20 (still inside the US$2.05 ledger ceiling) or to accept "no retry on batches" (worst case 3 x 0.0284 = US$0.085). If you prefer the smallest change, choose A' with 6,144 or A with 8,192 and accept the truncation risk. Either choice will be added to this PR and the taskgen hash recomputed.

## B3. Original spending verification (HISTORICAL) (calculated upper bounds, not bills)
- Per-request: largest reservation anywhere = US$0.0371 (option A) < US$0.05 cap; trials unchanged (<= US$0.05, <= 16 requests, US$0.50 per trial).
- Stage caps: taskgen 0.15 (see table), investigate 0.40 (binds; worst realistic ~US$0.13-0.2), baseline trials: **no stage cap of its own** - bounded only by the ledger. Because baseline runs before investigate, an overspending baseline would starve the investigator, so the documented "US$1.50 baseline allocation" is not enforced.
- Whole investigation: the explicit ledger ceiling (`--total-cap-usd 2.05`) is the hard bound on all spending. Expected total ~US$1.0 (taskgen 0.02-0.06, baseline ~0.7, investigate 0.1-0.2).
- Programme: US$2.05 = A$3.08 against A$43.79 remaining (7 %); the A$50 ceiling is a limit, not an authorization. The programme ledger is not modified.

## B4. Original manifest hashes (HISTORICAL, all superseded) (computed in-process from the free inspect output; no gate or run was started)
- L0: `0ce19b499a243252ffbf4f0172f8e084cbd0119f3d7fad2ae3b90ca5b0490b86` (unchanged).
- Taskgen, `site-5`, `n_tasks=8`: main `d9c894cdd81421a0fd4a7a5d8ce4df71532017ae52c8293afcc55360deea44e9` -> this PR (2,500 cap listed) `a38374df3f2243563c14e41cd79517a5a81191ebaef9a6f59542e299275f577e`. It will change again once option A/A'/B is chosen.
- Investigate and baseline-trials hashes depend on run state (task manifest, attribution) and cannot be known before the earlier stages; they are printed at their gates. The investigate manifest now includes the new fields, so any hash computed earlier is superseded.

## B5. Original decisions requested (HISTORICAL; all answered)
1. Taskgen route: A (8,192), A' (6,144) or **B** (recommended); and for B the stage cap US$0.20 vs no batch retry.
2. Confirm investigator cap 4,096.
3. Whether to add a baseline-stage cap (e.g. US$1.50) so the investigator cannot be starved (code change to the trials manifest; not done).

