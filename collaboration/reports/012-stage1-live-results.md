# Report 012b — Task 012 Stage 1 LIVE results (Muse Spark `muse-spark-1.3`)

**LIVE results**, single execution of the approved schedule at commit `7e9bf61`, schedule hash `96e459ad…fc99fec`, manifest hash `0ef0386c…03b04`. 8/8 runs completed, no halt, no retry, no replacement. Private artifacts (traces, per-run results, ledger) are in Git-ignored `runs/experiment-012/live/`; nothing is published. Calculated cost, not billed. **Stage 1 is a feasibility/sensitivity test: V0 (listing + structured) vs V3 (detail-only availability + fragmented specs) changes both factors, n=1 per cell — no factor attribution and no statistical claim is made.**

## Ledger / execution
8 runs completed, 0 unsettled, committed **US$0.718** (expected US$0.69–1.03; stage ceiling US$4.00 → US$3.28 remaining; programme US$6.00). 53 model requests; no fidelity violations, no cost-limit blocks, no infrastructure errors, no parser rejections (all 44 non-compliant responses recovered by the fixed `muse-prose-prefix-json-v1`; raw strict-JSON compliance 9/53 = 17%).

## Per-run results
| run | task | variant | independent PASS | evidence-backed | partial acc. | evid. cov. | requests | actions | page loads (revisits) | time | calc. cost |
|---|---|---|---|---|---|---|---|---|---|---|---|
| s1-01 | T2 | V3 | **PASS** | yes | 1.00 | 1.0 | 3 | 3 | 3 (0) | 23.8 s | $0.0396 |
| s1-02 | T3 | V0 | **PASS** | yes | 1.00 | 1.0 | 5 | 9 | 5 (1) | 29.3 s | $0.0668 |
| s1-03 | T1 | V0 | **FAIL** | – | 0.00 | 1.0 | 12 | 12 | 12 (9) | 48.1 s | $0.1653 |
| s1-04 | T4 | V3 | **PASS** | yes | 1.00 | 1.0 | 5 | 7 | 5 (0) | 26.0 s | $0.0653 |
| s1-05 | T4 | V0 | **PASS** | yes | 1.00 | 1.0 | 7 | 7 | 7 (1) | 29.4 s | $0.0945 |
| s1-06 | T1 | V3 | **FAIL** | – | 0.33 | 1.0 | 11 | 12 | 11 (7) | 47.7 s | $0.1547 |
| s1-07 | T2 | V0 | **PASS** | yes | 1.00 | 1.0 | 3 | 3 | 3 (0) | 11.1 s | $0.0399 |
| s1-08 | T3 | V3 | **PASS** | yes | 1.00 | 1.0 | 7 | 11 | 7 (2) | 23.9 s | $0.0921 |

## V0 vs V3 (raw; descriptive only, n=1 per cell — no intervals computed)
| task | V0 → V3 success | requests | time | cost |
|---|---|---|---|---|
| T1 | FAIL → FAIL | 12 → 11 | 48 → 48 s | .165 → .155 |
| T2 | PASS → PASS | 3 → 3 | 11 → 24 s | .040 → .040 |
| T3 | PASS → PASS | 5 → 7 | 29 → 24 s | .067 → .092 |
| T4 | PASS → PASS | 7 → 5 | 29 → 26 s | .095 → .065 |
Analysis tier (pre-registered rules): **S1 = inconclusive / no detected effect** (success identical in every pair; effort differences go both ways and are within what one run per cell can show). This is **not** evidence of equivalence. No ceiling effect on T2–T4 was overcome and no sensitivity to the combined change was detected on them.

## T1 failures — what the traces show (both arms fail, so this is a baseline finding, not a V0/V3 effect)
- **Agent–tool interface (observed):** in both T1 runs the agent repeated `find_elements` on the same listing 9× (V0) / 5× (V3) because the tool result reached the model only as a count line ("Found 14 elements"), i.e. the known visibility gap seen in Task 007 and in the Task 011 mock `loop` persona. The agent was trying to read link targets. This consumed the step budget (V0 ended at step 12 of 12, with the final-step schema narrowing) and is **not attributable to the website**.
- **Why it kept trying (observed fact about the site, both variants):** the SKU the task asks for is **not shown on listing cards**, only on product pages (and in link slugs). In V0 the agent, unable to see SKUs, put the product *names* in the `sku` fields (names and prices were correct → partial accuracy 0 by the SKU rule); in V3 it opened one product page, answered with one correct SKU and omitted the other two eligible products (recall 1/3, precision 1/1).
- **Evidence-spec gap (limitation of our instrument):** the T1 evidence requirements demand the product names/prices, not the SKUs, so the automatic finding "required facts were shown, answer wrong ⇒ agent reasoning (inferred)" overstates: the SKUs were in fact never in the observed text. The diagnostics rule should add SKU text to T1 evidence before further T1 analysis (not changed here to keep the frozen configuration).
- **Run-to-run variance:** the same T1 fixture on V0 passed in Task 011 (9 requests, three product pages opened) and failed here — a single baseline task already varies between runs, so one failure cannot be attributed to any variant.
- Extra visits on T3/T4 (1–2 revisits) are classified re-verification/navigation by rule; no systematic V0/V3 difference.

## Candidate interventions (hypotheses only; none validated, none part of the current matrix)
1. *Website:* show the SKU on listing cards (T1 failure involved both variants and SKU absent from listings) — would test whether the harness-visibility loop is triggered by missing on-page SKUs. Needs a new controlled variant factor ("sku_on_listing") — **not in the approved matrix; requires discussion**.
2. *Agent/tool side (not a website change):* make `find_elements` output visible in model history / cap repeated identical calls. This would alter the frozen reference agent and is a harness decision, not website evidence.
Neither is claimed to help; evidence is 2 failed runs with one earlier pass.

## Recommendation (based only on what was observed)
- The pre-registered Stage 1→2 criterion ("V3 shows ≥1 failure") is *literally* met by T1-V3, but the same failure occurred in V0, so it is not differential sensitivity. T2–T4 passed in both variants with similar effort. **Do not run Stage 2 as designed** (three runs per cell of T2/T3 would most likely be uninformative; T1 is dominated by the tool-visibility loop).
- Options for review: (a) a small targeted experiment on the observed baseline friction — T1 with and without SKU on listing cards, with ≥3 baseline repeats — or a harness fix for `find_elements` visibility followed by T1 baseline repeats to separate tool from site effects; (b) a reduced Stage 2′ limited to availability on T1/T3 *after* the T1 tool loop is resolved; (c) stop experimenting and report the null Stage 1 outcome. My recommendation: (a) fix/measure the tool-visibility issue first (it contaminates every list-style task), then test one website intervention on T1. Each needs your approval and an exact call plan.
- Limits: one run per cell, one model configuration, synthetic store; the T1 SKU observation is specific to this storefront's listing design.
