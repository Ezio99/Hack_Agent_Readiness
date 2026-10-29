# Report 014b — offline implementation of the guarded WebArena live path (no live call made)

**Date:** 2026-10-29. Approved scope: (a) offline implementation with ledger enforcement, stub tests, leak checks, HAR capture and official evaluation. **No model call, no key use, no spend occurred.** The optional ≤US$0.04 probe (b) and the single run (c) are **not** executed and (c) is not approved. Plan: [proposals/task014-live-run-plan.md](../proposals/task014-live-run-plan.md).

## What was built
| file | change |
|---|---|
| `src/agent_readiness/webarena/live.py` (new) | `RequestGate` (durable per-request reservation), `upper_bound_usd`, leak checks, `check_site`, `run_schema_probe` (WAAnswer wire schema), `run_live` (exactly one run: preflight → health → static leak scan → run marker → capped run → HAR → official evaluation → sanitized HAR → post-run request scan → result) |
| `src/agent_readiness/capture.py` (+13 lines) | optional `recorder.request_gate` hook: reserve after the fidelity/cost checks and before the network; settle in `on_response`. Default `None` ⇒ every existing run is unchanged |
| `scripts/webarena_live.py` (new) | `status` / `probe` / `run`; every live subcommand halts without `--allow-model-calls` (verified: both refuse, nothing sent) |
| `tests/test_webarena_live_gate.py` (15), `tests/test_webarena_live_run.py` (6) | stub transports only |
| frozen pieces | `suite-v2-compat1` profile file untouched; only the approved limits are overridden at run time (steps 16, requests 16, run timeout 300 s, request timeout 30 s, step timeout 60 s). Adapter, `NetworkCapture`, evaluator wrapper unchanged. SDK retries were already off (`max_retries=0`) |

## How the ledger bounds spend (and the evidence)
**Mechanism.** Every model HTTP request, before it can reach the network, (1) passes the existing fidelity/cost guard, (2) is given a conservative upper bound = estimated input (system + user text at 4 chars/token, schema at 4 bytes/token, calibrated screenshot 1,430 tokens, +10 % margin) **plus extra screenshot headroom up to 4,000 tokens per image (≈2.8× the measured value)** **plus the full 4,096-token completion allowance at US$4.25/M**, and (3) that amount is appended to the fsync'd ledger. Only then is the request sent. A refusal raises before the transport (nothing sent, nothing written). The reservation is replaced by the actual calculated cost only if the provider returns `usage` **and** that cost does not exceed the reservation; otherwise the full upper bound stays counted permanently (the ledger is a file, so restarts cannot forget it). Limits enforced at reservation time: per-request cap US$0.04, request-count cap 16, run cap US$0.50 (sum of this run's reservations/settlements), ledger ceiling US$0.60 (probe + run + anything else). A single run marker (`wa286`) makes a second attempt impossible. A response whose real cost exceeds its bound (the estimator was wrong) closes the gate and flags `guard_halt`.

**Tests proving each property** (`tests/test_webarena_live_gate.py`, 15 passed; `tests/test_webarena_live_run.py`, 6 passed):
| claim | test |
|---|---|
| reservation is on disk before the provider is reached, at the full bound, and later settles lower | `test_reservation_is_durable_and_precedes_the_network` (the stub provider checks the ledger when called) |
| screenshot exposure and the full completion cap are in the bound | `test_upper_bound_includes_screenshot_headroom_and_full_completion` |
| a timeout keeps the full reservation, also in a new process | `test_timeout_keeps_the_full_reservation_even_across_restart` |
| HTTP 500 / 400 / usage-less 200 keep the full reservation | `test_error_or_usage_less_responses_keep_the_full_reservation` (3 cases) |
| a retry storm (60 failing attempts) cannot exceed the cap: exactly `floor(0.50 / bound)` reach the network, the rest are refused, committed ≤ US$0.50 | `test_retry_storm_cannot_exceed_the_run_cap` |
| the ledger ceiling binds below the run cap when other spend exists (0.34 pre-committed ⇒ the run stops at the 0.60 ceiling) | `test_ledger_ceiling_binds_below_the_run_cap` |
| request-count cap 16 (20 tiny requests ⇒ 16 sent, 4 refused) | `test_request_count_cap` |
| oversize request refused before any ledger write or network | `test_oversize_request_is_refused_before_any_ledger_write_or_network` |
| estimator violation closes the gate | `test_bound_violation_closes_the_gate` |
| one attempt per id/run | `test_one_attempt_per_request_id_and_run_marker`, `test_second_run_with_the_same_ledger_is_refused` |
| preflight refuses without `--allow-model-calls`, without the key, or with changed prices; probe/run need the flag | `test_preflight_refuses_*`, `test_run_requires_a_successful_probe_when_live`, CLI check |
| provider outage: HAR still written, official evaluation still run (verdict "no answer"), both failed requests counted at ≈US$0.035 each (US$0.069 total), `guard_halt` set | `test_provider_failure_still_captures_har_*` |
| environment unhealthy ⇒ halt before any ledger entry | `test_unhealthy_environment_halts_before_any_spend` |
| leak: expected slug planted in static inputs ⇒ halt before any ledger entry; in the system message post-run ⇒ reported | `test_static_leak_halts_*`, `test_leak_scan_and_request_scan` |
| probe: success marks `probe_ok` (cost ≤ cap); a 400 schema rejection is recorded, keeps the full US$0.04, blocks the run, and a second probe is refused | `test_schema_probe_success_rejection_and_cap` |
| full pipeline on the stub site: Chromium, HAR, **official evaluator PASS**, every request reserved+settled, nothing unsettled | `test_stub_run_passes_official_evaluation_and_accounts_every_request` |

**Numbers from the real Magento pages** (recorded guard estimates of the two requests of the scripted run, now with screenshot headroom): 0.0340 → **0.0375** and 0.0332 → **0.0368** US$ upper bound per request (≈ US$0.0174 of that is the unused completion allowance). Expected actual cost per request remains ≈ US$0.015–0.022.

**Limits of this guarantee (honest):** it bounds spend *our process initiates through the agent's model client and the probe*; it cannot see charges from other holders of the key. The USD figure is calculated at published prices, not a bill; the provider's billing of a timed-out request is unknown, hence counted in full. The bound relies on the calibrated token estimator plus the 4,000-token screenshot allowance — if the provider returns usage above the bound the gate closes and the run halts (tested), but that request will already have been paid.

## Consequences you should decide on
1. **Effective request count is ~13, not 16.** With a per-request bound ≈ US$0.037 and a US$0.50 run cap, the 14th request is refused (0.5 / 0.0375 = 13.3). The 16-step/16-request limits remain as stated, but the cap binds first, on purpose. Options: accept (conservative, recommended unless the first steps look slow), raise the run cap to US$0.60 (and the ledger ceiling to US$0.70) to allow 16, or lower `max_completion_tokens` (changes the frozen profile — not recommended).
2. **Headroom under the per-request cap is thin:** US$0.0375 vs 0.04 (≈ 7k more characters of page text). A large Magento listing page would be refused pre-send (`estimated_cost_limit`, a guard stop, not a website result) and end the run early. Recommendation: raise the per-request cap to US$0.05; the US$0.50 run cap is unaffected. Needs your decision (default left at 0.04 as approved).
3. The WAAnswer schema probe is a hard prerequisite for the live run in code (`require_probe=True`).

## Tests run
- New: `tests/test_webarena_live_gate.py` 15 passed, `tests/test_webarena_live_run.py` 6 passed (21 total, ~21 s, with `--extra webarena`).
- Full suite (with the `webarena` extra, stub tests included): **570 passed** in 11m03s (549 before + 21 new).

## Still unverified
Provider acceptance of the `items: {}` answer schema (the probe); live-model behaviour; real-screenshot token cost on Magento; whether Muse Spark can solve 286; how the provider bills timeouts. No live path has been exercised against a real provider.
