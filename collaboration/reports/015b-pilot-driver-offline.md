# Report 015b — Task 015 pilot/experiment driver (offline) and the exact paid pilot command

**Date:** 2026-10-29. Approved scope: build the driver offline; AUD-aware stage ledger + durable per-request gate; tests; offline end-to-end dry run. **No model call, no key use, no spend.** Security/integration review of PR #22: [Report 015a](015a-pr22-security-integration-review.md).

## What was built (`src/agent_readiness/remediation/experiment.py`, `cli_impl.py`; CLI `readiness remediation-experiment plan|run|status`)
| requirement | how it is met | test |
|---|---|---|
| Audit generates the finding and recommendation **before** the experiment is scheduled | `plan` first audits the unmodified demo site with the product (or loads a stored audit) and builds the schedule only from that report's recommendation (`change_id` selects the treatment) | `test_manifest_freezes_everything…` |
| Experiment records reference the product-generated ids | manifest and every row carry `audit_id`, `finding_fingerprints`, `recommendation_id`; the effect record references them | `test_dry_run_pilot_end_to_end…`, `test_budget_and_provider_stops…` |
| Measured effects attach without changing the original observation / rewriting the recommendation | `attach_measured_effects` returns a derived view (`original_report_sha256`, `measured_validation`); original report and its `validation` are untouched; mock/dry-run results are refused | `test_live_effect_attaches_as_a_derived_view…`, `test_measured_effects_are_a_derived_view…` |
| Exact frozen task, agent profile, website variants, independent oracle | manifest freezes task ids + spec hashes, `suite-v2-compat1` + profile hash, the two states' variant ids, model/endpoint, oracle description/data version; planning verifies the unmodified state **reproduces the audited finding** (refuses a different site) | `test_planning_refuses_a_different_site…` |
| Schedule, seed, code/config hashes, stopping rules, cost ceilings recorded before execution | write-once, tamper-evident manifest (SHA-256 over all content incl. schedule, seed, code-file hashes, limits in USD **and** AUD, stopping rules); `run` re-verifies the hash and re-hashes the code | `test_manifest_is_write_once…`, `test_live_needs_the_exact_hash…` (code drift halts) |
| No automatic retry or replacement | one attempt per run id (ledger marker, survives interruption); resuming skips attempted runs; halted stages leave later runs pending | `test_two_provider_failures_halt…`, `test_interruption_is_recorded_void…` |
| Budget/provider failure is never a website failure | outcome classes `budget_stop`, `provider_failure`, `ambiguous_timeout`, `guard_violation` are **void**: recorded with an explicit "not attributable to the website" note, excluded from estimates, listed in the effect record; only `completed` / `agent_limit` rows are analysed | `test_budget_and_provider_stops_are_void…`, `test_analysis_verdicts…` |
| All stage spending counts toward A$50 | `StageLedger` = USD ledger capped at the AUD stage cap ÷ rate; every stage ledger under the run root counts; preflight runs `budget.check_stage` (plan also refuses a stage that cannot fit) | `test_every_stage_ledger_counts…`, `test_planning_refuses_a_stage_that_would_break…`, `test_stage_cap_in_aud_stops…` |
| Pilot and main need separate explicit approvals | live run needs `--approve-manifest-sha256` equal to **that stage's** manifest hash plus `--allow-model-calls`; main additionally needs a completed pilot whose gate decision is `continue` | `test_live_needs_the_exact_hash_the_flag_the_pilot_for_main…`, CLI test |
| Per-request gate | each scan runs under `RequestGate` (reserve-before-send, full-completion + screenshot bound, per-request US$0.05, per-run US$0.50, ≤12 requests) | Task 014 gate tests + `test_synthetic_suite_scan_can_use_the_same_durable_gate` |

## Dry-run demonstration (real mock provider through the real scanner, gate, ledger and re-audit; labelled MOCK)
Output: [015b-driver-dry-run-output.txt](015b-driver-dry-run-output.txt). With the committed pilot manifest: 2 runs attempted/complete, no halt; both rows reference audit `8770fb8a1d7a` and `rec-show-availability-on-listing-cards`; every request reserved and settled (0 unsettled); pilot gate "continue" (mock opens 5 product pages); effect record `mode: mock`, verdict `inconclusive`; the independent re-audit of the modified state reports `attribute_detail_only:availability` and `filter_absent:availability` **resolved** (no labels used); `attach_measured_effects` refuses the mock record. Mock results are not evidence about any model.

## Tests
- New: `tests/test_remediation_experiment.py` (17); 13 security cases in `tests/test_remediation_security.py` (Report 015a). Full Python suite (with the `webarena` extra): **622 passed** in 13m09s (590 before + 32 new).

## The exact two-run paid pilot (FOR YOUR APPROVAL — nothing has been run)
**Frozen manifest:** [`collaboration/experiments/task015/pilot/manifest.json`](../experiments/task015/pilot/manifest.json), audit [`audit-baseline.json`](../experiments/task015/pilot/audit-baseline.json); **manifest SHA-256 `25a22bfdba02363b0b31eecbd1c3834b5744372dcf35ec79c2c111a1d6ae08b3`**. It is valid only while the frozen source files are unchanged (the run halts on drift); any change to them requires re-planning and re-approval.
| item | value |
|---|---|
| Model / endpoint / profile | `muse-spark-1.3`, `https://api.meta.ai/v1`, `suite-v2-compat1` (frozen, with its fixed prose-prefix parser) |
| Task / oracle | `t1-anc-headphones-under-250-all` (12 steps / 12 requests / 240 s), catalogue-only independent oracle |
| Runs | 2, sequential, one per website state, order fixed by seed 20261029 in the manifest (`pilot-01` modified, `pilot-02` unmodified); no retry, no replacement |
| Per request | upper-bound reservation ≤ **US$0.05 = A$0.075** (input + 4,000-token screenshot allowance + full 4,096-token completion, +10 %), written to disk before sending |
| Per run | ≤ **US$0.50 = A$0.75** reserved; ≤ 12 requests |
| Stage hard cap | **US$1.00 = A$1.50** (ledger ceiling) |
| Expected | US$0.15–0.26 = A$0.23–0.39 calculated (unmodified ≈ US$0.10–0.17, modified ≈ US$0.05–0.09) |
| Programme | A$50 ceiling; spent A$5.885; remaining A$44.115; A$42.615 would remain even if the whole stage cap were spent |
| Stops | any budget/guard/bound stop; two void runs; stage cap; interruption (run kept, nothing retried) |
| Pilot gate | continue to the main stage only if the unmodified run is valid and shows room to act (≥ 4 product-page visits or a not-eligible item reported); one pair supports **no** inference about the effect; main needs its own manifest, hash approval and ≤ A$7.50 cap |
**Command (do not run without approval):**
```
uv run readiness remediation-experiment run \
  --manifest collaboration/experiments/task015/pilot/manifest.json \
  --audit collaboration/experiments/task015/pilot/audit-baseline.json \
  --root runs/task015 --mode live \
  --approve-manifest-sha256 25a22bfdba02363b0b31eecbd1c3834b5744372dcf35ec79c2c111a1d6ae08b3 --allow-model-calls
```
Credentials: `META_MODEL_API_KEY` from the environment or the repo `.env` (never printed). Private artifacts stay under `runs/task015/` (Git-ignored).

## Limits and caveats
Calculated costs are not bills; the provider's treatment of timed-out requests is unknown (counted in full). One pair cannot show an effect; the pilot only tests feasibility and room-to-act. The driver's arm labels (`unmodified`/`modified`) exist only in the experiment design; the audit engine never sees them. Live behaviour of `suite-v2-compat1` on `electronics-v1` is still unverified.
