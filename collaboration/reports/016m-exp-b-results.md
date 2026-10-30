# Report 016m — EXP-B results (owner-selected daily-fee listing change; live, nine trials)

Run `investigations/site-5-live-c` (private, git-ignored; raw artifacts, traces and criteria are not committed). Pre-registration: `collaboration/proposals/EXP-B-listing-fee-preregistration.md`; implementation: Report 016l. **No protocol deviation occurred**: nine trials in the fixed order, no void or quarantined trial, no retry, no cap refusal, no integrity halt, no change to the plan, tasks, rules or budgets.

## Identities
| item | value |
|---|---|
| `apply_fix` manifest (approved 2026-10-30 by the owner) | `8cf55be28e515eb2c2a392b8655443dc6a490e05f23df1ef89c708c009c50c94` |
| `post_trials` manifest (approved 2026-10-30 by the owner, exact hash) | `96d920570b9ae7cb6b116827d4ae70684e62ccc41201adea889119e6ed180f36` |
| proposal (EXPERIMENTAL, owner-selected, not an investigator-verified finding) | `prp-06082b03bb`; patch `b2efe2f747c0a8713b5f0fac0b9874cf0528a7ccf475c89b25677243c10aaf1e` |
| original snapshot / patched snapshot | `1796c2a3c8b5f957918f99f0262d84feccdb6391e13fb2f88dee189897b6d96b` / `27b2754e0f85c35b47fafc2e761978ad23e1d35ff0eac9f0c553f57997808dbd` (only `/tools` differs; local mirror only) |
| execution order hash | `824dd4f0f53091dec3a2e8446368e281f534a5d9a951b3278e4e931ed2a1e768` |
| exploratory rules (`exploratory-listing-v1`) | `f8c25e461c64eb87c0bd77c5e0a38dce0a5721ddfd471a2d2eb35efc4aa6ea99` |
| frozen rule | `paired-signflip-v1` (unchanged); tasks manifest `a5ebfbf5a945dde8e1d1fca0a93905e547bded593d3682ff2b03a474edf69658` |
| model / profile | `muse-spark-1.3` via `https://api.meta.ai/v1` / `suite-v2-compat1`; retries 0; at most 16 requests per trial |

## Observed results (model requests; page views equalled requests in every trial; all trials `completed`)
| task | role | historical baseline | unmodified repeat | patched |
|---|---|---|---|---|
| `gen-e38eac8644` (investigation) | affected (daily fee) | pass, 13 | pass, 13 | pass, **4** |
| `gen-c7c642f78c` (holdout) | affected (daily fee) | fail, 13 | fail, 13 | pass, **3** |
| `gen-0384beb35e` (holdout) | same-shape control (deposit) | fail, 13 | fail, 13 | **pass**, 12 |
| `gen-0ac84d18d3` / `gen-b05c45672f` / `gen-f2731972ed` | detail-page controls | pass 2 / 3 / 3 | not run | pass 2 / 3 / 3 |

**Frozen `paired-signflip-v1` (historical baseline vs patched, 6 pairs): `inconclusive`** (pass delta +0.333, request change -42.6 %, p_pass 0.50, p_requests 0.25). As anticipated in the pre-registration, this rule cannot return `improvement` when only two tasks can be affected. Reported unchanged.

**Exploratory `exploratory-listing-v1`: `consistent_with_h1`.** Both affected tasks: patched requests (4, 3) are far below 75 % of the unmodified repeat (13, 13); the reduction exceeds the noise estimate (0: the three unmodified repeats equalled their historical trials exactly, so no drift was observed); page views are lower; no pass was lost; controls are within request tolerance; the historical comparison agrees. This is a separate, labelled analysis; it does not replace the frozen verdict.

**`holdout_consistent = false` (frozen evaluation), from `evaluate/design.py`:** it is computed as `sign(holdout pass delta) == sign(investigation pass delta) or holdout pass delta == 0`. Here the holdout partition's pass delta is +1.00 (2 pairs: both holdout baseline failures passed when patched) and the investigation partition's is 0.00 (4 pairs, all passed before and after), so the signs differ and the flag is false. It does **not** mean the holdout got worse. The guard only withdraws an `improvement` verdict when the holdout pass delta is negative (or zero with more requests), and a `regression` when it is positive; the verdict here was already `inconclusive`, so the flag changed nothing.

**Unexpected control behaviour:** the same-shape deposit control `gen-0384beb35e` failed in the baseline and in the unmodified repeat (13 requests each) and **passed when patched** (12 requests). The exploratory rules test controls on request counts only (tolerance 3), so the verdict is unaffected, but a control task changed outcome. With one trial per arm this cannot be separated from run-to-run variation, and it must not be read as support for, or evidence against, the change. The patch exposes only the daily fee, not the deposit.

## Spend (calculated at published prices from the durable ledger; **not a bill**)
| scope | calculated US$ | cap |
|---|---|---|
| unmodified-repeat arm (3 trials) | 0.527638 | 0.55 (96 % used) |
| patched arm (6 trials) | 0.336514 | 0.80 |
| post_trials combined | **0.864152** | 1.35 |
| imported before this stage: baseline 0.603977 + task generation and investigator 0.066275 | 0.670252 | |
| **run total** | **1.534404** | ceiling 2.05; **0.515596 remaining** |
Ledger: 250 entries, all reserves settled, no open reservation, no bound violation. Per trial costs (US$): placebo e38 0.177219, c7c 0.176234, 0384 0.174185; patched e38 0.049114, c7c 0.036251, 0384 0.157873, 0ac8 0.022878, b05c 0.035253, f273 0.035145. The A$50 programme ledger file was not modified and does not yet include L0, L1a or this stage (about US$0.04 + US$0.670252 + US$0.864152, i.e. roughly A$2.4 at 1.50 AUD/USD); billed charges may differ from calculated cost.

## Limitations
n = 1 per task per arm, one site, one model, trials sequential not simultaneous; measures effort and evidence-backed correctness only; no `reach_page` task, and `condition` / `copies available` / `next available` untested; the start-page leakage check ignores navigation labels; the change was chosen by the owner after the investigator's pattern was observed and **the holdout was not blind to the owner**; the investigator never saw holdout evidence. Allowed wording: "consistent with a reduction in browsing effort for this exploratory change on this site and these tasks". Not allowed: "proved", "verified finding", any general improvement or claim about other sites. The unmodified-repeat arm used 96 % of its cap; any rerun would need a larger cap and new approval.

## Dashboard
The sanitized export (`readiness investigate export`) was validated: schema `investigation-dashboard-v1`, mode `live` only, 6 baseline + 6 patched + 3 unmodified-repeat trials, 0 void, 0 quarantined, no findings, one unverified owner-authored hypothesis, one owner-selected proposal (label preserved), both verdicts, spend by arm; no forbidden keys, local paths, credentials, answers, criteria, journeys or transcripts. The export was loaded into the PR #52 dashboard locally and rendered without errors; it is **not committed** and nothing was published.
