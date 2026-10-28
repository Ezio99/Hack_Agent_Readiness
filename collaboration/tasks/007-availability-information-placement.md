# Task 007 — Availability information placement (controlled A/B)

**Status: DRAFT — NOT APPROVED. No code, no inventory/task/storefront changes and no paid calls are authorized.** Drafted 2026-10-28 after the user stopped Task 006 and asked for a stronger experiment. Feasibility findings are from code inspection and enumeration over the committed inventory.

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

## Would this be more informative than Task 006?
Yes, for different reasons: (1) the manipulated information is **necessary** for the task, so it cannot be bypassed by reading adjacent card text; (2) rank gives a **predicted dose-response**, and Kitchen is a built-in **negative control**; (3) it measures **effort and cost**, which vary continuously, instead of a near-ceiling pass rate; (4) it exposes **failure modes** (unverified guesses, step exhaustion, loops). Weaknesses: the headline effect is partly mechanical (hiding information must cost navigation), five tasks share one inventory and one model, the A observation is larger, and the step-limit deviation changes the agent configuration relative to earlier tasks.

## Approval gates
Nothing here is authorized: (1) approval of the design, the new task kind and the step-limit deviation; (2) approval to implement Stage 1; (3) review of Stage 1; (4) approval of each live installment. PR #3 remains unmerged.
