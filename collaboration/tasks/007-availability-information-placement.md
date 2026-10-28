# Task 007 — Availability information placement (controlled A/B)

**Status: design APPROVED and Stage 1 IMPLEMENTED OFFLINE (2026-10-28, user-approved); the live pilot is NOT approved and no paid calls are authorized.** Drafted 2026-10-28 after the user stopped Task 006 and asked for a stronger experiment. Feasibility findings are from code inspection and enumeration over the committed inventory.

## Relationship to Task 006
Task 006 was stopped by the user after block 1 (4 runs, seed 2, all passed). It remains an **exploratory finding** (A and B both 2/2, identical two-step paths, no non-target visits, ceiling effect). It must not be read as evidence that link-text placement is irrelevant; it was too small and its tasks never forced a choice that depended on the manipulated information. Entries 5–24 remain `pending` in `runs/pilot-task006/` and will not be executed; artifacts and the schedule are preserved.

## Research question and hypothesis
Does moving task-critical product information (availability) from listing cards to detail pages increase the navigation effort, latency and model cost a shopping agent needs to answer, and does it affect accuracy?
- **H1:** with availability only on detail pages, the agent opens more product pages, takes more steps and requests, and uses more latency, tokens and cost, in proportion to how many candidates must be checked; accuracy may fall (unverified guesses, step exhaustion).
- **H0:** no difference in effort or accuracy.
Prior expectation is that H1 largely follows from information being unavailable; the value of the experiment is the **magnitude, scaling with candidate rank, and failure modes** (guessing, early stopping, loops), not the existence of an effect.

## Feasibility findings
1. **Today's storefront is already the "availability on detail only" arm.** Listing cards show name, brand · category and price only; the detail page shows product ID, price and availability. Arm B can be the current baseline, unchanged (preserving its golden hashes). Arm A needs one new variant that adds an availability line to each listing card.
2. **The existing task kinds cannot separate the arms.** Both ask for `product_id`, which appears only on the detail page, so one detail visit is required in both arms. "Availability" tasks (`Locate Woven Basket…`) and discovery tasks (brand + category + price cap) both give the agent everything needed to choose the product without availability; availability merely gets read after opening the page. Listing availability would not make them trivial and would not change navigation. A new task type is therefore required.
3. **Listing-level availability does not make the new task answerable without navigation**, because the answer still needs the product ID from the detail page: A needs exactly one detail visit (the minimum), B needs as many as the candidates ranked above the answer. No product ID or route reveals stock (routes hash the name only).
4. **Inventory limits the task design.** Only one (brand, price) combination has exactly one in-stock product among ≥3 candidates, and the *cheapest* product of every category/brand group is in stock, so "cheapest in-stock" collapses to "cheapest". A rule that works on the **existing inventory unchanged**: *"the most expensive product in {scope} that is currently in stock"* (unique because prices within every scope are distinct). Rank = position of the first in-stock product when scope products are ordered by descending price = the minimum number of detail pages B needs (A needs 1):
   | Scope | Candidates | Answer (price) | Stock pattern, descending price | Rank / B minimum |
   |---|---|---|---|---|
   | Home | 5 | Woven Basket ($37) | n n Y Y Y | 3 |
   | Outdoors | 5 | Yoga Mat ($35) | n n Y Y Y | 3 |
   | Fern (brand) | 8 | Trail Daypack ($39) | n n Y Y Y n n Y | 3 |
   | Bags | 5 | Trail Daypack ($39) | n Y Y n Y | 2 |
   | Kitchen (**negative control**) | 5 | Glass Carafe ($34) | Y n Y n Y | 1 |
   Harbor (brand, rank 4 of 8) would add a dose point but needs ~9 steps in B; Ember is all in stock (rank 1); category × brand scopes have only two candidates.
   Proposed wording (identical in both arms): "Find the most expensive {category} product that is currently in stock. Return its product ID, price in integer cents, and whether it is available." (brand scope: "Find the most expensive {brand} product…").
5. **Required changes (for later approval; not made now):** a new task kind in the generator (existing kinds' outputs pinned and unchanged — 120-task digest `f6c5e94e…`), an evaluator rule that the expected ID is the highest-priced in-stock product in scope (answer schema unchanged), and the arm-A storefront variant. Evaluator code path for existing kinds unchanged.
6. **Step budget must change.** Frozen Task 005/006 limits (6 steps / 6 requests / 120 s) would truncate arm B (rank 3 needs ≈ click, read, back, click, read, back, click, read, done ≈ 7–9 steps). Proposed for **both** arms: 12 steps, 12 requests, 240 s, per-request estimated ceiling US$0.04 (unchanged), per-run cumulative cap US$0.48. This is a documented deviation from the frozen agent configuration and needs approval; it is identical across arms and the profile text, model and parameters are otherwise unchanged.

## Confounds in the manipulation (to quantify offline, then accept or fix)
- Arm A adds 20 short lines ("In stock"/"Out of stock") to the listing observation: more tokens (estimated ≈ +100–150 per listing view) and a taller card, so a different screenshot and possibly fewer cards visible per viewport. Use the same element/CSS class as the detail page's text style and minimal height change; report the token and screenshot deltas per observation; the DOM already holds all 20 cards.
- Element indices shift (+1 line per card); A and B differ in the number of interactive elements by 0 (no new links).
- In B each extra detail visit grows history and prompt size, so cost grows super-linearly; this is part of the effect being measured and is reported separately from the fixed observation delta.
- B permits an unverified guess (answering the top-priced product); that is a legitimate behaviour to record, and the evaluator decides correctness.
- Detail pages, inventory, prices, IDs, routes, order, filters, search, task wording, evaluator, model and parameters are identical across arms; the variant is server-configured and invisible to the agent.

## Metrics (reported separately)
- **Information retrieval success:** evaluator pass/fail; additionally `answered_product_page_visited` (was the detail page of the answered product observed — separates verified answers from guesses) and whether the final answer's availability was read from the page.
- **Navigation effort:** detail pages visited (distinct and total), non-target visits, excess over the task minimum (A: 1, B: rank), `go_back` / listing returns, steps, proposed action counts, search/filter use. Non-target visits are counted neutrally, never as errors.
- **Latency:** per request and per run. **Tokens:** prompt/completion/reasoning per request and per run, plus the listing-observation size per arm. **Cost:** calculated from provider tokens at published prices (provider reports none) and the worst-case estimate. **Protocol:** raw compliance, recoveries and rejections, reported apart from outcomes. Failure classes as in Task 006.

## Separating a design effect from model variability
Sampling is not seeded, so variability is measured, not assumed away:
1. **Replication:** 3 repetitions per (task, arm) cell give within-cell spread for every metric.
2. **Negative control:** Kitchen (rank 1) predicts *no* effort difference between arms; a difference there estimates noise/observation-size effects.
3. **Dose-response:** the design predicts B's extra detail visits grow with rank (0 for Kitchen, +1 for Bags, +2 for Home/Outdoors/Fern); a manipulation effect should track rank, noise should not.
4. **Mechanism check:** traces show what the agent saw (availability in A's listing observation) and which pages it opened, so differences can be tied to the observation rather than inferred.
5. **Pairing and order:** matched task instances in both arms, interleaved and counterbalanced (ABBA/BAAB blocks as in Task 006), run in a fixed pre-registered schedule by the same resumable driver.
6. **Analysis (pre-registered):** per-task arm means and ranges; primary statistic the paired difference (B − A) in detail pages visited and in calculated cost per task, tested with a permutation/sign test across the five tasks and reported with intervals against the Kitchen control and the within-cell spread; no pooling with Task 005/006 results.

## Offline checks (Stage 1; no model calls; needs approval to implement)
1. Arm B rendering byte-identical to the current baseline (existing golden hashes); arm A differs only by the availability line on cards; detail pages, errors, IDs, routes, order, prices identical; availability text on cards equals detail-page truth for all 20 products.
2. Task generator: existing kinds' output digest unchanged; new kind yields the five scope instances with unique expected IDs and the ranks above; evaluator accepts the target and rejects each higher-priced out-of-stock product, lower-priced in-stock products and unknown IDs.
3. Chromium + Browser Use observations per arm: availability visible in A's agent view and accessibility tree, absent from B's listing; token-size and screenshot deltas; no variant name, expected ID or stock-derived route in any agent-visible payload; the answer is not derivable from the initial observation in B and not (ID) in A.
4. Scripted navigators: an oracle solves every task in both arms with the predicted visit counts (A 1, B rank), a blind first-link / top-price-only navigator fails where predicted, and a guess-the-top-price answer fails on ranks > 1.
5. Metrics extractor on mocked traces (visited-answer-page, excess visits); driver schedule for the new pilot with the Task 006 safeguards (persisted state, no repeats, halts, approval to resume); smoke-mode rehearsal of the full schedule.

## Separately gated live pilot (not approved)
5 task instances × 2 arms × 3 repetitions = **30 runs** in ABBA/BAAB blocks per task, one at a time with frozen configuration (12 steps / 12 requests / 240 s, US$0.04 per request, US$0.48 per run), same stop rules as Task 006 (fidelity, cost-cap, infrastructure, drift, two consecutive output errors, review at US$4.00 calculated, pilot-wide estimated cap US$15). Expected cost: arm A ≈ 2–3 requests ≈ US$0.04, arm B ≈ 4–9 requests ≈ US$0.06–0.15, so ≈ US$2–3 total (calculated); the worst case, 30 × US$0.48 = US$14.40, is within the A$30 planning budget (≈ US$19 less ≈ US$0.22 spent). Run in installments (e.g. one task block of 6 runs at a time) with review between installments; each requires explicit approval. No pilot-wide or per-run spending is authorized by this draft.

## Stage 1 — implementation record (offline; no model calls were made)
- **Task kind** `instock_max` (`tasks.py`, `contracts.py`): "Find the most expensive {scope} product that is currently in stock…"; seeds 0–4 select Home, Outdoors, Fern, Bags, Kitchen (seed k mod 5); deterministic; `PrivateTask.in_stock` added. **The evaluator file is byte-identical** (SHA-256 pinned in tests; its existing `matches` logic enforces scope and stock). Existing kinds' 120-task digest `f6c5e94e…` is unchanged.
- **Storefront** (`storefront.py`, `templates/listing_avail.html`): arm A = variant `listing-availability-v1` (an `In stock` / `Out of stock` line after each price); arm B = `baseline-detail-v1`, the unchanged baseline (golden hashes still pass). Selected by server configuration only.
- **Oracle and scripted solvers** (`oracle.py`, independent of storefront/agent/pilot/runner/metrics): per scope and arm it derives the answer, the rank, `min_visits_to_find`, `min_visits_to_verify_no_higher` and `min_detail_visits`, and the stopping condition. Finding vs verifying: in arm A both need 0 detail pages and the answer's page is opened only for its product ID (minimum 1); in arm B finding needs `rank` pages, verifying that nothing higher-priced qualifies needs `rank − 1` pages, minimum `rank`. Solvers over HTTP: top-down (minimal; visits equal the oracle minimum and it stops at the first in-stock product), cheapest-first (finds *an* in-stock product, never verified — wrong for all five scopes), top-price guess (right only for Kitchen), exhaustive (correct, overhead = scope size − minimum).
- **Metrics** (`metrics.py`): `navigation_overhead` = actual detail visits − independently verified minimum (both reported, signed; negative = fewer pages than needed, i.e. unverified), plus distinct pages, `answer_is_target`, `answered_product_page_visited`, higher-priced candidates and how many were checked, `verification_complete`, and the find/verify minima. Non-target visits stay a neutral count.
- **Leakage and isolation checks:** arm B listing markup, headers, hrefs and URLs contain no stock/availability words, product IDs, `data-*`, hidden or `aria-hidden` attributes across ~110 query combinations; routes depend only on the product name (flipping stock/ID/price leaves them unchanged); arm A differs from B only by the 20 availability lines for every query (including empty and 422 pages); detail pages are byte-identical across arms. In real Chromium/Browser Use: A's agent view contains one truthful stock line per card in card order; B's listing observation, accessibility tree, HTML and URL contain no stock/availability text; link accessibility names are identical; A's extra accessible nodes are the 20 stock texts only; with the stock lines removed (and indices normalised) the agent views coincide; A's screenshot differs from B's; the card-region size delta is bounded (100–1,200 characters); no product ID or variant name in any initial observation; detail-page observations and screenshots are identical across arms; filtered scope listings match inventory truth in A and hide it in B for all five scopes.
- **Oracle vs real browsing:** scripted Chromium runs of all five scopes × both arms complete with `navigation_overhead` 0 and detail visits equal to the oracle minimum. A 30-entry smoke-mode rehearsal of the full schedule through the driver (no model) completed with evaluator pass in every entry.
- **Driver/schedule** (`pilot.py`, `readiness pilot … --experiment 007`): deterministic 30-run schedule; Task 006's hash is unchanged; all stop/resume/audit/no-repeat/drift safeguards apply to both experiments (tests). Run limits are covered by mocked-model Chromium tests: a 12-step run passes the step-aware guard (steps 1–11 full schema, budget warnings at steps 9–11, step 12 done-only), 12 requests are allowed, each request's worst-case estimate is below US$0.04 and the sum is within US$0.48 in both arms; a cumulative-cap test blocks before the network; the recorded limits are 12 / 240 s / 12.
- **Test totals:** 302 passed (261 offline + 41 browser), 38 new for Task 007.

## Frozen schedule and deviations (recorded explicitly)
Schedule SHA-256 (Task 007, includes the profile hash, limits and entries): **`a2cf749c809e9a905d445d06b87fdb3411fda30978f01c291c74824a656f5eaa`**. Order of 30 runs: scope blocks Home (seed 0) ABBAAB, Kitchen (4) BAABBA, Outdoors (1) ABBAAB, Bags (3) BAABBA, Fern (2) ABBAAB; A = `listing-availability-v1`, B = `baseline-detail-v1`; each (scope, arm) cell has 3 repetitions; A is first in three blocks and B in two.
Deviations from the Task 005/006 configuration (identical across arms; everything else — profile text, `natural-shopping-v3-compat1`, model, parameters, parser, schema/step-aware guard, per-request ceiling US$0.04 — is unchanged): task kind `instock_max`; 12 steps (was 6); 12 model requests (was 6); 240 s (was 120); per-run cumulative estimated cap US$0.48 (was 0.25); pilot-wide estimated cap US$15.00 and review halt at US$4.00 calculated spend (Task 006: 6.00 / 2.00).

## Predicted dose-response (recorded before any live run)
| Scope (seed) | Rank | Predicted minimum detail visits A / B | Predicted B − A visits | Predicted requests A / B | 
|---|---|---|---|---|
| Home (0) | 3 | 1 / 3 | +2 | 2 / 6 |
| Outdoors (1) | 3 | 1 / 3 | +2 | 2 / 6 |
| Fern (2) | 3 | 1 / 3 | +2 | 2 / 6 |
| Bags (3) | 2 | 1 / 2 | +1 | 2 / 4 |
| Kitchen (4, negative control) | 1 | 1 / 1 | 0 | 2 / 2 |
Requests assume the minimal path (each extra page costs a click and a `go_back` request); a request costs ≈ US$0.013 (≈ 9–10k prompt tokens, growing with history), so B's calculated cost should grow roughly in proportion to requests (≈ 3× for ranks 3, 2× for Bags, ≈ 1× for Kitchen) and latency by ≈ 3 s per request. Prediction for overhead: ≥ 0 and small when the agent follows the top-down strategy; negative overhead means an unverified answer. Expected failure modes: unverified guesses (answering the top-priced or first-checked product), early stopping, loops, step exhaustion.

## Analysis plan (written before live execution; all statistics are exploratory)
1. Report every run (including failures and halts) with: evaluator result; detail visits, minimum and overhead; distinct and non-target pages; verification completeness; steps, requests, latency (per request and run), tokens, calculated cost; raw protocol compliance, recovery and output errors — each separately, per task and arm, with within-cell ranges (3 runs).
2. Primary descriptive contrast: B − A per task for detail visits, requests, latency and calculated cost, set against (i) the within-cell range and (ii) the Kitchen control, where the prediction is ≈ 0 (|Δ visits| < 0.5 and |Δ requests| ≤ 1).
3. Dose-response check: whether Δ visits and Δ cost are ordered Kitchen < Bags < {Home, Outdoors, Fern} as predicted (rank correlation, five points); a sign test across the five tasks on Δ cost. Both are exploratory and descriptive, with bootstrap intervals over runs within task; no confirmatory claim, no p-value thresholds, no pooling with Tasks 005/006.
4. A design effect is supported only if the contrast exceeds within-cell variability, is absent in the control, follows the predicted order, and is explained by the traces (what the listing observation showed and which pages were opened). Otherwise the result is reported as inconclusive. Accuracy differences (guessing) are reported separately from effort.

## Proposed live commands (not approved; the second command spends money)
```
readiness pilot plan --experiment 007 --state-dir runs/pilot-task007 --mode live          # free; writes the schedule
readiness pilot run  --experiment 007 --state-dir runs/pilot-task007 --allow-model-calls \
    --approved-schedule-sha256 a2cf749c809e9a905d445d06b87fdb3411fda30978f01c291c74824a656f5eaa --max-runs 6
```
`--max-runs 6` is the first installment (the Home block). Expected cost of that block ≈ 3 × US$0.03 (A) + 3 × US$0.09 (B) ≈ US$0.35 (calculated); worst case 6 × US$0.48 = US$2.88. Full pilot: expected ≈ US$2–3, worst case US$14.40. Each installment needs separate approval; every halt needs `readiness pilot resume --experiment 007 --approval-note …`.

## Would this be more informative than Task 006?
Yes, for different reasons: (1) the manipulated information is **necessary** for the task, so it cannot be bypassed by reading adjacent card text; (2) rank gives a **predicted dose-response**, and Kitchen is a built-in **negative control**; (3) it measures **effort and cost**, which vary continuously, instead of a near-ceiling pass rate; (4) it exposes **failure modes** (unverified guesses, step exhaustion, loops). Weaknesses: the headline effect is partly mechanical (hiding information must cost navigation), five tasks share one inventory and one model, the A observation is larger, and the step-limit deviation changes the agent configuration relative to earlier tasks.

## Approval gates
Nothing here is authorized: (1) approval of the design, the new task kind and the step-limit deviation; (2) approval to implement Stage 1; (3) review of Stage 1; (4) approval of each live installment. PR #3 remains unmerged.
