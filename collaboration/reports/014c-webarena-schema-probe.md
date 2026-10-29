# Report 014c — WebArena answer-schema probe (ONE paid request, owner-authorized, ≤US$0.04)

**Date:** 2026-10-29, code at `main` `8e34c49` (PR #18 merged). Command: `scripts/webarena_live.py probe --allow-model-calls`. **Exactly one request was made; no retry; the task 286 run was NOT executed and is not authorized.**

## Result: **SUCCESS — the provider accepts the unchanged official `WAAnswer` wire schema**
| item | value |
|---|---|
| Endpoint / model | `https://api.meta.ai/v1/chat/completions`, `muse-spark-1.3`, `reasoning_effort: low`, `max_completion_tokens: 1024` (probe setting; the agent uses 4,096) |
| Schema | the exact full `AgentOutput` schema with `WAAnswer` as `done` data, sha256 `b561a275…1c7ce8bab`, 8,269 canonical bytes (same hash as the agent's wire schema), strict `json_schema`; contains the unconstrained `retrieved_data.items: {}` that was the concern (R1) |
| HTTP / finish | 200 / `stop`, request id `aa80b964-d728-46dd-8b1e-8c682457e783`, 4.5 s |
| Output | strict-JSON valid, parsed by the real `AgentOutput` model: a single `done` action with `{task_type: NAVIGATE, status: SUCCESS, retrieved_data: null, error_details: null}` — graded as success |
| Usage | 64 prompt / 833 completion tokens (740 reasoning). **Calculated cost US$0.00362** (worst-case estimate US$0.008; cap US$0.04); the provider reports no cost, so this is calculated at published prices, not a bill |
| Ledger | `runs/webarena-014/live/ledger.jsonl` (private, ignored): reserve 0.04 → settle 0.00362 → `probe_ok`; committed US$0.00362 of the US$0.60 ceiling |

**Consequences.** R1 is closed for this endpoint/model: no schema correction is needed and none is proposed. The `require_probe` precondition of `run_live` is now satisfied in the local ledger. Nothing else is known: the probe sent no page content and no screenshot, so it says nothing about live agent behaviour, Magento page token costs, or whether task 286 can be solved.

**Observations (not conclusions).** The probe's completion used 81 % of its 1,024-token cap (740 reasoning tokens) — fine for a probe, but a reminder that low-effort reasoning still consumes tokens (the agent run has 4,096). The reported prompt-token count (64) does not include the 8 KB schema in this single probe, whereas earlier agent runs showed the schema adding ~1,300 prompt tokens; the guard keeps counting it conservatively, so reservations stay upper bounds.

## State
No other paid call has been made in Task 014. Next step (needs **separate explicit authorization**): the single task 286 run with `suite-v2-compat1`, limits 16 steps / 16 requests / 300 s / 30 s per request, per-request cap US$0.05, run cap US$0.50, ledger ceiling US$0.60 (≈US$0.60 − 0.0036 available), expected to stop by budget at ~13 requests. See the [plan](../proposals/task014-live-run-plan.md) and [Report 014b](014b-webarena-live-path-offline.md).
