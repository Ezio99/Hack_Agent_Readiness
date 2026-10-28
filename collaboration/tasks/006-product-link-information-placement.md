# Task 006 — Product-link information placement (controlled A/B)

**Status: DRAFT — NOT APPROVED. No code changes and no paid calls are authorized.** Revised 2026-10-28 (twice: staged design; then the planning-budget update to A$30 overall and a 24-run pilot) after inspecting the storefront and Browser Use pipeline and after the user's decisions (Control A unchanged; Arm B = visible generic link text; accessible-name-only variant is an offline diagnostic only; staged design).

## Research question and hypothesis
How does the placement of product information relative to the clickable element affect a shopping agent's ability to discover and identify the correct product?
- **A (control):** the product name is the link text (name, brand · category and price are in one card; the link carries the name).
- **B:** the link text is the generic "View details"; the name moves to a plain, non-link heading; brand · category, price and every other fact remain, in the same card.
- **H1:** when the clickable element no longer carries product-identifying text, the agent more often needs extra navigation or clicks the wrong card (more navigation actions, wrong clicks, steps, tokens; possibly lower success).
- **H0:** no difference, because the agent resolves identity from adjacent card text or bypasses the listing with search/filter. A null result is informative: it would show how the reference agent grounds a click.
This is a statement about this agent, model, profile and one synthetic site; it is not a website-readiness score.

## Findings from inspecting the current system (2026-10-28)
1. Today the listing link is `<h2><a>{{ p.name }}</a></h2>`; brand · category and price are plain text in the same card; there is no `aria-label`; detail routes are opaque hashes, so a link is the only route to a detail page.
2. Browser Use's agent view (`dom_state.llm_representation()`, what the model receives) renders `[idx]<a [attributes] />` with the visible text as a child, followed by the other card text. Probed in real Chromium against scratch variants (not committed):
   - generic `aria-label` with unchanged visible name: model sees the attribute **and** the visible name; screenshot identical → informative only as a diagnostic, expected effect ≈ none;
   - visible generic link text with the name as a plain heading: model sees `Trail Daypack`, then `[88]<a />` `View details`, then `Fern · Bags`, `$39.00`; screenshot differs. This is Arm B.
3. **The discovery prompt never names the product**: "Find the {brand} product in {category} costing at most $X". The identifying facts are brand, category and price, which are *outside* the link in both arms. Arm B therefore mainly tests whether the agent can still associate a generic link with the nearby facts, not whether it can read a name. The availability task ("Locate Woven Basket") does depend on the name, so it tests the placement more directly (but search by name returns one product).
4. Benchmark scale: 20 products on one page; 12 distinct discovery targets across seeds 0–199; 20 availability targets.

## Intervention
- **Control A:** the current storefront, **completely unchanged** (byte-identical rendered HTML and existing tests, `storefront_variant` `baseline-detail-v1`).
- **Arm B:** change only the listing card markup: `<h2>{{ p.name }}</h2>` (plain) and `<a href="/products/{{ p.route }}">View details</a>`; same href, card order, brand · category, price, CSS, detail pages, title, headers and route set. No `aria-label`/`title` on the link.
- **Offline diagnostic D0 (never a paid arm):** `aria-label="View details"` on the existing name link, visible text unchanged — documents that an accessible-name-only change is perceived but non-informative.
- The variant is selected by server configuration recorded in `run.json` (`storefront_variant`), never via URL, header, title, page text or any agent-visible marker.

## Controls and confounders
Held fixed: inventory and hash, prices/availability, order, routes, detail pages, search/filter form, task generator and seeds, independent evaluator, profile `natural-shopping-v3-compat1` (hashed), model and parameters, limits (6 steps / 6 requests / 120 s), guard and cost caps, browser build, viewport.
Confounders to record or accept: B changes visible text and the screenshot (placement and label text are not separable); element indices and prompt length shift slightly (record input tokens per arm); unseeded model sampling (two runs per cell give only a rough variance estimate); time/provider drift between runs; agent bypass via search/filter; prose-prefix recovery interacts with the model (report separately); Browser Use/provider version changes invalidate pairing (record and abort on drift); the variant must not leak into prompts, titles or URLs.

## Seed selection: where link text is irrelevant, and which seeds to prefer
The search form offers category, brand and a maximum price, and every discovery prompt gives all three, so **an agent that applies all three filters sees exactly one product on every seed and link text is irrelevant**; this cannot be fixed by seed choice, only measured (record whether search/filter was used; analyze filter-users and browsers separately). Task 005's seed 0 is also weak: category + price alone already isolates the product (cat+price = 1), and it was already seen in Task 005. Candidate counts when an agent applies only two of the three constraints (seed: target → category+brand / brand+price / category+price remaining):
| Seed | Target (brand, category, price, available) | cat+brand | brand+price | cat+price |
|---|---|---|---|---|
| 5 | Yoga Mat (Fern, Outdoors, $35, yes) | 2 | 5 | 3 |
| 9 | Woven Basket (Harbor, Home, $37, yes) | 2 | 5 | 3 |
| 14 | Commuter Sling (Harbor, Bags, $32, yes) | 2 | 3 | 3 |
| 2 | City Tote (Fern, Bags, $24, **no**) | 2 | 2 | 2 |
| 13 | Lunch Container (Harbor, Kitchen, $22, **no**) | 2 | 2 | 2 |
| 0 | Linen Cushion (Fern, Home, $29, yes) | 2 | 4 | **1** |
Seeds 1, 3, 17, 19 and 20 (and 7, only under category+brand) collapse to one product under at least one two-filter combination and are least informative. **Proposed matched seeds for Stage 2: 2, 9, 7, 5, 14, 13** — five of them (2, 5, 9, 13, 14) leave at least two candidates under every two-filter combination; seed 7 (Bamboo Tray, Ember, Kitchen, $26, available: cat+brand 1 / brand+price 2 / cat+price 3) is the sixth because it collapses under only one combination and adds the Ember brand. Coverage: brands Fern, Harbor, Ember; categories Bags, Outdoors, Home, Kitchen; two expected-unavailable answers (2, 13). Reserves: 20, 17, 0 (0 was already used in Task 005). Computed from the committed inventory; recompute offline.

## Stage 1 — offline verification (no model calls; needs approval to implement)
1. Render A and B through the real app: A byte-identical to the current storefront; HTML diff A vs B limited to the listing link text/heading markup; detail pages, title, headers, route set and card order identical.
2. Chromium accessibility tree: A link name = product name; B = "View details"; D0 documents `aria-label` precedence.
3. Browser Use observation (`llm_representation`), screenshots and the exact request body via the mock transport: assert the expected A/B differences, that name, brand · category, price remain visible in B, and record token-length deltas.
4. Leakage: evaluator truth and variant identity absent from every agent-visible payload; the answer is not derivable from the initial observation alone (re-run per arm).
5. Scripted non-LLM navigators complete all six pilot seeds in both arms (A via name link, B via heading-adjacent link), showing B is feasible; a navigator that clicks the first "View details" must fail the evaluator.
6. Evaluator, task generator, inventory hash and profile hashes identical across arms; metrics extraction (below) tested on mocked traces.

## Stage 2 — proposed 24-run pilot (not approved)
Design: **6 matched seeds × 2 arms × 2 repetitions = 24 runs** (seeds 2, 9, 7, 5, 14, 13; all with the identical task per seed, arm differing only by storefront variant). Counterbalancing: each seed is a block of four consecutive runs, ABBA or BAAB, so every arm holds each within-block position equally; block patterns alternate (seed 2 ABBA, 9 BAAB, 7 BAAB, 5 ABBA, 14 ABBA, 13 BAAB), giving each arm first position in three of six blocks. Because model sampling is not seeded, the second repetition per cell provides a first estimate of within-cell variability. Block order is fixed in advance, so slow drift confounds seed (not arm).
Per-run configuration is **frozen to Task 005**: profile `natural-shopping-v3-compat1`, 6 steps / 6 requests / 120 s, per-request estimated ceiling US$0.04, per-run cumulative estimated cap US$0.25, schema guard, no retries, no profile/prompt/parser/model change between runs. (Raising the step limit was considered for quality, since a wrong click costs steps, but it would change the agent configuration relative to Task 005 and is left to Stage 3.)
Budget (planning only, not authorization): the user's overall experimentation budget is **A$30** (≈ US$19–20 at an assumed ≈0.65 US$/A$; verify the rate; prior live spend ≈ US$0.12). Expected cost of 24 runs ≈ 24 × US$0.027 ≈ US$0.65–1.00 (calculated); the full worst-case estimate is 24 × US$0.24 = US$5.76, which fits the budget, so sample size is not constrained by cost. Safeguards: the per-request and per-run caps above; a **pilot-wide estimated cap of US$6.00** (≥ the full worst case, so it never prevents a faithful run); a **review halt** if cumulative calculated actual spend exceeds US$2.00 (about three times expected); and halts on any fidelity violation, cost-cap block, infrastructure failure, unexpected profile/model/browser version drift, or two consecutive `model_output_error`s. A driver that executes the pre-registered schedule sequentially (one run at a time, enforcing these halts, never retrying, never reordering) is needed; it is Stage 1 scope and must be tested offline before use. Remaining budget after the pilot stays reserved for Stage 3 and other tasks.
Analysis plan (fixed before running): per-seed and per-arm tables of every metric; primary paired comparison on evaluator pass using seed-level pass counts (0–2 per arm) and an exact sign/McNemar-style test on discordant seeds, reported with effect sizes and intervals rather than as a confirmatory claim; paired bootstrap or Wilcoxon for continuous metrics; filter-users and browsers reported separately; the two repetitions' agreement reported as variability. Twenty-four runs can detect only large effects.

## Stage 3 — expansion (only after review of Stage 2)
Decided after reading Stage 2 traces: more seeds/repeats, a higher step limit, the availability task family, or a redesigned intervention if both arms show ceiling effects or the agent always filters. No Stage 3 spending is proposed or implied.

## Metrics (tracked and reported separately, per run and per arm)
- **Task success:** independent evaluator only.
- **Navigation actions:** count of click / navigate / go_back / search / filter / scroll actions and distinct pages visited.
- **Wrong clicks:** detail pages visited whose product is not the expected one, derived by the harness from navigation URLs vs private truth (truth never reaches the agent); plus whether the first listing click was correct.
- **Strategy:** used search/filter (which controls), clicked from the unfiltered listing.
- **Latency:** per request and per run. **Tokens:** prompt/completion/reasoning per request. **Cost:** calculated estimate vs actual usage, never provider-reported unless present.
- **Raw protocol compliance:** compliant/non-compliant responses, recovery attempted/recovered/rejected — reported separately from success.
- Failure class (`model_output_error`, `request_limit`, `timeout`, infrastructure, fidelity, cost limit). Infrastructure failures are excluded from outcome comparisons but reported.
Trace evidence: `run.json`, `trace.jsonl`, per-step DOM text and screenshots, model responses, `storefront_variant`, hashes, versions.

## Acceptance criteria
- Stage 1 (when approved and implemented): all six offline checks pass as committed tests; Arm A unchanged; variant undetectable by the agent; existing suite still passes; documentation updated.
- Stage 2 (when separately approved): all 24 runs executed once each in the pre-registered order with recorded evidence, or halted per the abort rules; Report 006 gives the metrics above per arm and per seed without pooling with strict-profile or Task 005 results.

## Limitations to state in any report
One synthetic site (20 products), one model/profile/parser, six seeds with two repetitions each (24 runs), unseeded sampling, B changes visible text and layout (placement and wording confounded), discovery prompts do not name the product, filters can neutralize the intervention, compat parser in the loop. Results do not generalize to website readiness, establish a score, or support causal claims beyond this setup.

## Approval gates
Nothing in this task is authorized to implement or spend. Required separately: (1) approval to implement Stage 1; (2) review of Stage 1 results; (3) approval of the Stage 2 schedule, driver and caps (or per-run approval if preferred); (4) review before any Stage 3. PR #3 remains unmerged.
