# Report 016j — L1a configuration and observability proposal (after L0 attempt 3 PASS)

Offline only. L0 artifacts, the programme ledger and every earlier manifest are untouched; no model call was made. L0 manifest hash is unchanged (`0ce19b49…0b86`).

## 1. Measurements that drive the proposal (L0 attempt 3, `l0-probe-3`)
Completion tokens include hidden reasoning. Visible tokens are *estimated* from raw-text length (≈3.5 chars/token, local private file), so reasoning shares are estimates, not provider counts.

| request | shape | completion tokens | est. visible | est. reasoning |
|---|---|---|---|---|
| P1 / P2 | trivial echo | 779 / 656 | ~5 | ~99 % |
| P3 / P4 | 3-ish hypotheses | 1,434 / 1,281 | ~400 | ~66-72 % |
| P5 | **3 tasks** | **3,015** | ~210 | **~93 %** |
| P6 | hypotheses + injection | 1,291 | ~290 | ~77 % |
Reasoning is large and **not proportional to visible output** (3 small tasks cost ~2,800 reasoning tokens, a 400-token hypothesis list ~1,000). Prompt tokens were 65-467. Earlier: 491 live agent responses (effort low, cap 4,096): completion median 300 / p90 447 / max 979.

## 2. Proposed configuration (this PR implements items 1-3; item 4 needs your decision)
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

## 3. Spending verification (calculated upper bounds, not bills)
- Per-request: largest reservation anywhere = US$0.0371 (option A) < US$0.05 cap; trials unchanged (<= US$0.05, <= 16 requests, US$0.50 per trial).
- Stage caps: taskgen 0.15 (see table), investigate 0.40 (binds; worst realistic ~US$0.13-0.2), baseline trials: **no stage cap of its own** - bounded only by the ledger. Because baseline runs before investigate, an overspending baseline would starve the investigator, so the documented "US$1.50 baseline allocation" is not enforced.
- Whole investigation: the explicit ledger ceiling (`--total-cap-usd 2.05`) is the hard bound on all spending. Expected total ~US$1.0 (taskgen 0.02-0.06, baseline ~0.7, investigate 0.1-0.2).
- Programme: US$2.05 = A$3.08 against A$43.79 remaining (7 %); the A$50 ceiling is a limit, not an authorization. The programme ledger is not modified.

## 4. Manifest hashes (computed in-process from the free inspect output; no gate or run was started)
- L0: `0ce19b499a243252ffbf4f0172f8e084cbd0119f3d7fad2ae3b90ca5b0490b86` (unchanged).
- Taskgen, `site-5`, `n_tasks=8`: main `d9c894cdd81421a0fd4a7a5d8ce4df71532017ae52c8293afcc55360deea44e9` -> this PR (2,500 cap listed) `a38374df3f2243563c14e41cd79517a5a81191ebaef9a6f59542e299275f577e`. It will change again once option A/A'/B is chosen.
- Investigate and baseline-trials hashes depend on run state (task manifest, attribution) and cannot be known before the earlier stages; they are printed at their gates. The investigate manifest now includes the new fields, so any hash computed earlier is superseded.

## 5. Decisions requested
1. Taskgen route: A (8,192), A' (6,144) or **B** (recommended); and for B the stage cap US$0.20 vs no batch retry.
2. Confirm investigator cap 4,096.
3. Whether to add a baseline-stage cap (e.g. US$1.50) so the investigator cannot be starved (code change to the trials manifest; not done).
