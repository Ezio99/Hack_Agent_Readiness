# Report 015d — offline validation of the proposed Task 015 main stage (no live call)

**Date:** 2026-10-29. Companion to [docs/TASK015_MAIN_STAGE_PROPOSAL.md](../../docs/TASK015_MAIN_STAGE_PROPOSAL.md). **No model call, no key use, no spend.** Originally proposed manifest SHA-256 `ee2f6e062f18912e1903fc8c446bf184933de66450179479e07d93f89a1947c5 (SUPERSEDED, never approved or run — see Report 015e)` (frozen at commit `29e9312`, clean tree).

## Built (offline)
| item | where |
|---|---|
| Optional website factor `stockfilter` (labels without the in-stock filter); original variants/ids/pages byte-identical (existing 180 electronics/suite/variant tests still pass) | `environments/electronics/{variants,app}.py`, `listing.html` |
| Product recognises the intermediate state: `filter_absent` is independent of where the attribute is shown; new library template `offer-in-stock-filter` (selected only if not already covered by the bundled recommendation); change id `in-stock-filter` | `remediation/{findings,library,targets}.py` |
| Corrected prospective gate `room-to-act-v2` (R1–R5), interim check after block 2, void classes never count | `remediation/experiment.py` |
| Three-arm main stage: Latin-square block order, 6 blocks T1 + 2 blocks T4, H1/H2/H3 analysis (H1 alone gives a verdict), per-arm independent re-audits, cost envelope, `prior_stage` provenance carrying the original pilot gate result verbatim | `remediation/{experiment,cli_impl}.py`, `readiness remediation-experiment plan --stage main` |
| Programme ledger records the executed pilot (US$0.214509 = A$0.32), `recorded_runtime_stages` prevents double counting | `collaboration/budget/programme-ledger.json`, `budget` use in `StageLedger` |
| Erratum for the pilot gate interpretation (new file; original pilot files untouched) | `collaboration/experiments/task015/pilot/results/GATE-ERRATUM.md` |

## Tests
- New `tests/test_remediation_main_design.py` (21): isolation factor (labels without filter; `in_stock` parameter ignored without the filter; original variants unchanged), product recognition of the labels-only state (resolved / persisting / recommendation `offer-in-stock-filter` / applying `in-stock-filter`), **the pilot's incomplete-answer scenario** (original gate still `stop`, corrected gate shows room via R1–R3 and the modified pilot run correctly shows none), 8 gate cases, void classes, interim decisions, main-stage halts after block 2 when the baseline leaves no room, main completes without replacements when the baseline shows room, manifest contents, **byte-for-byte pins of all 8 original pilot artifacts**, programme ledger.
- Updated `tests/test_remediation_experiment.py` (17) for the three-arm design (Latin-square balance, ledger counting with the recorded pilot, verdict rule incl. control shift and void exclusion).
- Full Python suite (with the `webarena` extra): 642 passed and 1 failed — a stale expectation in `test_budget_is_tracked_in_aud…` (it still assumed pre-pilot spending); corrected to the updated ledger (A$6.2067 spent, A$43.7933 remaining) and re-run green. The final code was not otherwise changed afterwards, and the manifest was frozen after the full run.

## Dry run (real mock provider, all 24 runs, labelled MOCK)
[015d-main-dry-run-output.txt](015d-main-dry-run-output.txt): 24/24 attempted, 0 void, no halt, interim gate `continue` (the mock baseline opens 5 product pages), every request reserved and settled; effect record `mode: mock`, **never attached to the audit**. The independent re-audits behave as designed: `labels_only` → `attribute_detail_only:availability` **resolved**, `filter_absent:availability` **persisting**; `modified` → both **resolved**. Mock behaviour is scripted, so its (null) effect says nothing about any model.

## Limits
The proposal is untested on live models; labels_only cost is an assumption; the gate thresholds are post-hoc (disclosed in the proposal); `runs/task015` raw artifacts stay private. PRs #22, #24, #25 remain unmerged; this work is a further stacked PR.
