# Report 012a — Task 012 credential-free experiment infrastructure

Branch `task012-experiment-infra`. Plan: [docs/TASK012_EXPERIMENT_PLAN.md](../../docs/TASK012_EXPERIMENT_PLAN.md) (approved with amendments A–C). **No real model call was made; nothing here is live evidence.**

## What exists (`src/agent_readiness/experiments/`)
| Module | Role |
|---|---|
| `design.py` | the pre-registered matrix, stage ceilings (US$1.50 / 4.50), programme ceiling US$6.00, per-run reservation US$0.48, halt thresholds |
| `manifest.py` | frozen configuration + hash: environment/data version, 4 fixtures (spec hashes, evaluator versions, limits, answer-schema hashes), 4 variants, model/base URL/profile hash/parser `muse-prose-prefix-json-v1`/tools, Browser Use + Playwright versions, prices, halt rules; execution provenance (commit, dirty) compared separately; `drift()` |
| `schedule.py` | seeded block randomization (recorded seed), exact-matrix validation, schedule hash |
| `ledger.py` | extends the Task 011 ledger: stage AND programme ceilings, reserve-before-run, settle releases unused budget, unsettled/interrupted stay counted, attempts never repeated |
| `driver.py` | sequential execution through the existing scanner `execute_scan` (mock default); drift check before every run; halt rules; resume that never repeats an attempt; explicit partial report; live needs `--allow-model-calls` + `--approved-schedule-hash` + key |
| `metrics.py` | per-run row: independent success, partial accuracy (per-field, from the evaluator's private truth, offline), evidence coverage, requests, actions by type, page loads/unique/revisits/backtracks, failed tool calls, rule-based visit taxonomy (required / re-verification / navigation), latency, tokens, calculated cost, attribution (never names the website per run; hypotheses are not attributions) |
| `analysis.py` | contrasts S1 (Stage 1), C1, C2, C2b, C0 placebo, T4 control; pooled stratified effects, bootstrap CI (only with n≥2 per arm), within-task permutation p (descriptive), evidence tiers (observed directional signal / supported exploratory effect / inconclusive-no detected effect), partial-schedule and MOCK labelling, markdown report |
| CLI | `readiness experiment manifest|schedule|preflight|run|analyze|status` |

## Stage 1 exact schedule (seed 20261028; schedule hash `96e459ad4dd88ee49753e276ac19840239f47cd164e232441bc40382cfc99fec`)
Manifest hash (configuration only, independent of the commit): `7f0ad7f2b78964e607105ed62e71503a3d2eb311b2cdb442bf0d3dc51628a11c`.
| # | block | run id | fixture | variant |
|---|---|---|---|---|
| 1 | 1 | s1-01-t2-v3 | t2-compare-air14-vs-probook15 | detail + fragmented (V3) |
| 2 | 1 | s1-02-t3-v0 | t3-cheapest-monitor-27in-usbc-120hz | listing + structured (V0) |
| 3 | 1 | s1-03-t1-v0 | t1-anc-headphones-under-250-all | V0 |
| 4 | 1 | s1-04-t4-v3 | t4-policy-delivery-tessera-whisper | V3 |
| 5 | 2 | s1-05-t4-v0 | t4 tessera | V0 |
| 6 | 2 | s1-06-t1-v3 | t1 under-250-all | V3 |
| 7 | 2 | s1-07-t2-v0 | t2 air14/probook15 | V0 |
| 8 | 2 | s1-08-t3-v3 | t3 27in | V3 |
Each block contains every task once; leading variant balanced (2 tasks lead V0, 2 lead V3). Stage 1 is a **feasibility/sensitivity** test: V0→V3 changes both factors, so no factor is ever blamed for a difference.

## Budget preflight (calculated, not billed)
8 runs × US$0.086–0.129 (Task 011 mean ×1.0–1.5) = **US$0.69–1.03 expected**; per-run reservation US$0.48; stage ceiling US$1.50; programme ceiling US$6.00 (Stage 2 expected US$2.5–3.7 for 29 runs, ceiling US$4.50). The sum of reservations (US$3.84) exceeds the ceiling by design; the ledger halts safely *before* any run it cannot reserve.

## Mock demonstration of the exact Stage 1 schedule (real Chromium + Browser Use agent + guard + evaluator; scripted model; all labelled MOCK)
Scripted degradations in V3 only for demonstration: T2 wrong answer, T3 lazy (correct but nothing shown), T1 repeated-`find_elements` loop. Result: 8/8 runs executed in schedule order, ledger US$0.526 settled, no unsettled reservation; per-run rows show T2-V3 partial accuracy 0.875 (agent_reasoning), T3-V3 correct but evidence coverage 0 (not evidence-backed), T1-V3 `agent_tool_interface` with 7 revisits; analysis tier for S1 = *observed directional signal* with the explicit note that the change must not be attributed to either factor, banner `MOCK RESULTS` on every output. These numbers demonstrate the machinery only.
Budget exhaustion demo (same schedule, stage ceiling US$0.60): 3 runs completed, halt before run 4 (`stage 1 ceiling … cannot cover the next reservation`), explicit partial report with 5 not-started runs, completed runs kept and analysed as "PARTIAL SCHEDULE". CLI live mode without the approved hash: `HALT: live execution needs --approved-schedule-hash …`.

## Tests (credential-free)
`tests/test_experiment_infra.py` (30, stub runners): matrix/seed determinism/tamper detection; manifest stability and drift (agent, fixtures, environment, budget, commit) halting before any run; stage and programme ceilings, release on settle, unsettled counted; ordered mock execution; resume never repeats and reports the interrupted run as partial; budget exhaustion partial report; programme ceiling spanning stages; infrastructure failures preserved and halting at two; guard-class, over-reservation, parser-rejection and kill-switch halts; live-mode refusals (no flag / hash / key); partial accuracy, visit taxonomy, attribution rules; analysis for effect, null (never equivalence), supported-requires-review, partial/incomplete/failed runs, placebo never "supported", MOCK banner. `tests/test_experiment_mock_e2e.py` (browser): the exact 8-run schedule end to end.

## Limitations / deviations
- `supported_exploratory_effect` can only be assigned with a recorded human trace-mechanism review (`mechanism_review`), by design; the tool never infers a website mechanism.
- Permutation p-values use 20,000 seeded Monte-Carlo permutations; intervals appear only with n≥2 per arm, so Stage 1 (n=1 per cell) is purely descriptive.
- The Task 011 baseline runs are not pooled (prior, unregistered). Mock scenarios (wrong/lazy/loop) are scripted, not evidence of how the model or sites behave.
- The mock run costs use mock token counts at real prices; they are not predictions.
- Per-run attribution deliberately never names the website; website causation can only come from the comparative analysis plus trace review.
- Live path of the new driver is exercised only with stubs (the underlying `execute_scan` live path was validated in Task 011); no live call has been made.
