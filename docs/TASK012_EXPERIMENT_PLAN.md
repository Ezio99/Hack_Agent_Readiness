# Task 012 — Proposed experimental plan (FOR REVIEW; nothing here is approved or executed)

Status: proposal. **No paid call is authorized.** Credential-free preparation (manifest, schedule, metrics, analysis, tests) can start on approval of this design; each live stage needs its own explicit approval of the exact call plan below.

## 0. What we know and what shapes the design
- Task 011 live validation: 4/4 PASS, evidence-backed, on the **baseline** variant (`listing+structured`); 5–9 requests, 15–36 s, US$0.066–0.118 per run (mean ≈ US$0.086). One run per task — no variance estimate, no failure observed.
- **Ceiling risk:** if the baseline always passes, success rate cannot move much. Effects, if any, will most likely show in *effort* (requests, page loads, time, cost) or in occasional failures in harder cells. The design therefore (a) tests the *stressed* variant first, (b) pre-registers effort metrics as co-primary, and (c) says in advance that a null is an acceptable result — we will not search for failures (no new harder tasks, no prompt tweaks) to make an effect appear.
- The compat parser handled 25/26 responses: it is part of the frozen agent and must be reported as a fixed, versioned component (`muse-prose-prefix-json-v1`), never as strict-JSON performance.
- Extra page visits in T1 (3 candidate verifications) and T4 (policy re-reads) are **not** presumed friction. Visits are classified by rule (§5.3) before any attribution.

## 1. Question and design logic
Do the two existing storefront factors measurably change agent outcome or effort on realistic tasks?
- **Availability** (`listing`: stock shown on cards + in-stock filter; `detail`: stock only on product pages, filter ignored).
- **Specifications** (`structured`: labelled table + card chips; `fragmented`: same facts as prose, no chips).

Which tasks can respond to which factor (by task text and environment design):
| Fixture | Availability | Specs | Role |
|---|---|---|---|
| `t1-anc-headphones-under-250-all` | **direct** (stock is a constraint across many products) | indirect (ANC/price reading) | primary |
| `t3-cheapest-monitor-27in-usbc-120hz` | **direct** (stock) | **direct** (size, USB-C, refresh) | primary |
| `t2-compare-air14-vs-probook15` | none (no stock) → **placebo for availability** | **direct** (RAM, battery) | primary for specs |
| `t4-policy-delivery-tessera-whisper` | none | none (policies identical in all variants) | **capability/control — not an A/B test** |
Variants: V0 = `listing+structured` (baseline), V1 = `detail+structured` (availability changed), V2 = `listing+fragmented` (specs changed), V3 = `detail+fragmented` (both; stressed corner). Other fixtures (T1 under-200/any-300, T2 slate16, T3 32in, T4 others) are reserved for a *later* generality check; they are not used here so that cells stay few and replicated.

## 2. Frozen (identical in every run; hashes recorded in the manifest and re-checked before every run, halting on drift)
Model `muse-spark-1.3` @ `https://api.meta.ai/v1`; profile `suite-v1-compat1` (profile hash from Report 011b records) incl. `reasoning_effort: low`, `max_completion_tokens 4096`, parser `muse-prose-prefix-json-v1`; Browser Use 0.11.13 / Playwright 1.58.0; observation DOM+screenshot, tool set, 12 steps / 12 requests / 240 s; per-request estimate ceiling US$0.04; environment `electronics-v1+7c4eaccbb161`; fixture task text/oracles/graders/evaluator versions (`suite-contract-v1`); price constants (1.25 / 4.25 per M, verified 2026-10-28); code commit of the execution checkout. Model sampling is not controllable (no temperature setting is sent), so behaviour is stochastic; repeated trials, not seeds, handle this. Provider-side model drift is possible and monitored by re-running V0 in each block (§3).

## 3. Stages and run counts
**Stage 1 — feasibility pilot, 8 runs, ≈ US$0.7 expected.** Fixtures T1, T2, T3, T4 (above) × {V0, V3}, one run each, in 2 blocks of 4 (block order and within-block order randomized by a fixed recorded seed; each block contains all four tasks once, alternating which variant leads).
Purpose (not effect estimation): (a) is *any* difficulty visible in the stressed corner (ceiling check)? (b) run-to-run spread on V0 — each baseline cell now has 2 observations (Task 011 run + pilot run; the Task 011 run is reported as a prior, unblinded run and not pooled into confirmatory analysis); (c) do traces/evidence capture, page-visit classification and protocol recovery work on fragmented/detail pages; (d) real cost per cell to re-size Stage 2. 
Stage 1 → 2 decision rule (pre-registered, applied by us with user approval): 
- If V3 shows ≥1 failure, or median requests ≥ 1.5× V0 (more than the V0 spread) on ≥2 tasks → proceed to Stage 2 as designed. 
- If V3 and V0 are indistinguishable (all PASS, effort within V0 spread) → **do not escalate cost**; report a ceiling/null result for the stressed corner and propose only a small Stage 2′ (effort-only, §3 Stage 2 cells for T1/T3 availability) or stop. 
- If infrastructure/protocol problems dominate (≥2 of 8 runs) → fix and re-plan; no effect claims.

**Stage 2 — focused study, 29 runs (gated on Stage 1 review), ≈ US$2.9–3.9 expected.** Cells (runs each), block-randomized (3 blocks; each block contains one run of every cell; fixed recorded seed):
| Fixture | V0 | V1 | V2 | contrast served |
|---|---|---|---|---|
| T1 under-250-all | 3 | 3 | 3 | availability (V0 vs V1), specs (V0 vs V2) |
| T3 27in | 3 | 3 | 3 | availability, specs |
| T2 air14/probook15 | 3 | 3 | 3 | specs (V0 vs V2); V0 vs V1 = **placebo** (availability is irrelevant to this task) |
| T4 tessera (control) | 2 | – | – | pure-noise reference, not an A/B test |
Total 27 + 2 = **29**. V3 (both factors) is covered by Stage 1 only; no interaction claim is planned. The Task 011 baseline runs are excluded from confirmatory pooling (prior, pre-registration-free).
Trade-off: n=3 per arm per task (6 when T1 and T3 are pooled, task as block) can detect only *large* effects (e.g. 3/3 vs 0/3 success, or ≳1.5–2× effort) and cannot estimate small ones. Per-run cost is ≈US$0.1, so doubling replication adds ≈US$3. We choose breadth of tested contrasts *with a placebo and a control* over a powered single contrast, because the immediate need is evidence of whether any effect exists and where. If Stage 1/2 shows a clear effect, a Stage 3 (more replicates of that single contrast, ≈16–24 runs) is the proper confirmation and gets its own plan. Replacement of a provider-fault run is possible only with explicit approval and is recorded as an extra, with the original kept in the denominator.

## 4. Budget, ledger and gates
- Per-run reservation US$0.48 (12 × 0.04 estimate ceiling) before each request sequence; actuals calculated from provider tokens at verified prices (provider reports no cost; **calculated ≠ billed**).
- Persistent append-only ledger (reuse `scanner/live.py` `Ledger`; unsettled/interrupted keeps the full reservation; a recorded attempt is never repeated).
- **Ceilings:** Stage 1 US$1.50 (expected ≈ 0.7; max-run-every-time worst case 8 × 0.48 = 3.84 is impossible under the ceiling because the ledger refuses the next run once settled + reservation would exceed it). Stage 2 US$4.50 (expected 2.9–3.9 using the Task 011 mean US$0.086 × 1.0–1.5 stress factor × 29 runs; worst case blocked by the ledger). Programme total ≤ US$6.00, separately approved per stage.
- Execution: sequential; no retries; run order from the frozen schedule; the schedule hash and manifest hash are printed and checked.
- **Halt rules:** fidelity violation; estimated-cost-limit block; two infrastructure/provider errors (any) or two consecutive; a run exceeding its reservation; `recovery_rejected` ≥ 2 in any block (parser inadequacy); any hash/commit drift; ledger ceiling; kill switch file. After a halt nothing resumes without a new approval. Failed/aborted runs stay in the ledger and the denominator (reported intent-to-treat; "excluding provider faults" is reported as a secondary view with the exclusion rule fixed here: only `infrastructure_error` stop reasons).
- Results/traces stay in Git-ignored `runs/`; no publication, hosting or deployment.

## 5. Measurement
1. **Outcome (per run):** independent PASS/FAIL; evidence-backed; answer valid; **partial accuracy** = fraction of graded fields correct (T1: precision, recall and ineligible items; T2: product identity, RAM, battery, comparison statements; T3: eligibility, cheapest-correct, price; T4: each of the five policy fields) computed offline from the evaluator's oracle (the grader contract is unchanged); **evidence coverage** = share of the task's evidence requirements satisfied (observed-text), with the list of gaps.
2. **Effort:** model requests, steps, browser actions by type, unique and total page loads, revisits, backtracks (`go_back`), failed/repeated tool calls, limit stops, wall-clock, tokens and calculated cost.
3. **Page-visit taxonomy (pre-registered, rule-based on observed text):** *required* (a page whose facts are needed and not yet observed), *re-verification* (all needed facts on the page were already observed), *navigation/overhead* (list/filter/search pages). Only *information-seeking visits forced by the variant* (e.g., product pages opened solely to learn stock in V1) can be offered as website-related effort; re-verification is attributed to agent behaviour unless it also differs systematically between variants.
4. **Failure attribution per run:** website / agent reasoning / agent–tool interface / infrastructure / mixed / **undetermined**, each with trace spans, confidence and the strongest alternative explanation (existing `scanner/diagnostics` rules extended with revisit and partial-accuracy facts). A tool-visibility loop is never attributed to the website.
5. **Controlled contrasts:** difference in success (percentage points, exact CI), partial accuracy, requests/actions (absolute and ratio of medians), latency (median, IQR), cost; always with per-run points, n, and run-to-run spread from the V0 cells.

## 6. Analysis plan (fixed before any run)
- Unit: run. Block factors: task and execution block. Primary contrasts: C1 availability V0→V1 on T1,T3; C2 specs V0→V2 on T2,T3 (T1 secondary); C0 placebo V0→V1 on T2 (expected zero; its spread calibrates how big an apparent effect must be); T4 control gives pure-noise reference.
- Tests: exact/permutation tests stratified by task (success: stratified exact; effort: permutation on within-task standardized ranks), bootstrap/exact 95% CIs on differences; α not used as a gate — we report effect sizes with intervals and the **minimum detectable effect** at our n. No multiplicity-based claims; two primary contrasts only (C1 and C2, primary metric = evidence-backed success, co-primary = model requests).
- A contrast is called **"supported (exploratory)"** only if: direction is consistent in every task tested, the effect exceeds the C0/V0 spread, the interval excludes zero, and trace review finds a plausible website-mediated mechanism (not a tool or reasoning artifact). Otherwise **"no measurable effect at this sample size"** (a reportable negative finding with its MDE) or **"inconclusive"**. Never causal about other sites or models; never "variant X is better" from Stage 1.
- Stochasticity: all runs kept, none discarded; outliers shown; model drift checked via V0 repeats across blocks; schedule seed recorded.

## 7. From observations to recommendations (developer value)
Observation (trace-backed, per run) → **pattern** (recurs in ≥ half of a cell's runs, absent or weaker in the contrast cell) → **candidate friction** (passes the §6 "supported" test, alternatives checked) → **hypothesis-labelled recommendation** with: issue definition, observed behaviour and metric, candidate fix (e.g., "show stock on listing cards"), the single-factor before/after rescan that would test it, and its minimum detectable effect. Developer-value metric = number of issue candidates that meet all of those fields (not the count of speculative ideas). Insufficient/null evidence is stated explicitly ("no change to recommend on this evidence"). Validation of a recommendation is Task 013/014 (before/after on a modified site), not this task.

## 8. Credential-free preparation work (proposed, after approval of this plan)
Experiment manifest + schedule generator/validator (hashes, seeded block randomization, drift checks); run driver reusing `scanner/live.py` ledger with experiment/cell IDs; metrics extractor (partial accuracy, evidence coverage, visit taxonomy, action counts) tested on mock and the four Task 011 private results; analysis/report script (stratified permutation, bootstrap CIs, MDE) tested on synthetic data with known effects and null; mock end-to-end of the full schedule through the scanner (mode labelled MOCK); developer-facing evidence view/export labelling mock/live. All with no network model access.

## 9. Decisions requested
1. Approve the design (matrix, stages, analysis, decision rule) or amend it.
2. Approve credential-free preparation (§8).
3. Later, separately: approve the exact Stage 1 call plan (8 runs, US$1.50 ceiling) — this document is not that approval.
