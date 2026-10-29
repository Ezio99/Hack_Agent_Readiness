# Report 014d — ONE live Muse Spark run on WebArena Verified shopping task 286 (owner-authorized)

**Date:** 2026-10-29 (run 02:00:45–02:01:50 UTC). Code: `main` `ef118b1`. Command: `scripts/webarena_live.py run --allow-model-calls`. **Exactly one run, no retry; no further paid call.** Private artifacts (Git-ignored): `runs/webarena-014/live/run/20261029T020045-2843af197606/` (original HAR, sanitized HAR, trace, per-request responses, screenshots, `live-result.json`) and `runs/webarena-014/live/ledger.jsonl`. One run on one task is feasibility evidence, **not** a success rate, and nothing here is a statement about website readiness.

## Result
| question | answer |
|---|---|
| **Official evaluator** | **PASS, score 1.0** — `AgentResponseEvaluator` success, `NetworkEventEvaluator` success (no failed assertions); `webarena-verified` 1.2.3, checksums `35c3385b…01db4e` / `d6527566…243d30`; run on the **original** HAR (2,115 entries, all HTTP 200) |
| Outcome | **Completed**: the agent called `done` itself (`stop_reason: agent_done`); not stopped by any limit or guard |
| Agent claim vs evaluator | **No discrepancy**: the agent claimed `NAVIGATE / SUCCESS`, the evaluator agreed. The page it ended on is the one the evaluator expects |
| Steps / requests / time | **14 steps, 14 model requests** (limits 16/16), **59.8 s** wall (limit 300 s); every response HTTP 200, no timeouts (limit 30 s/request) |
| Calculated cost | **US$0.2447** for the run (14 requests × ≈US$0.016–0.019 actual; 14 reservations of ≈US$0.037–0.040, all settled, 0 unsettled); ledger total **US$0.2483** of the US$0.60 ceiling (incl. the US$0.00362 probe). Run cap US$0.50 and the per-request cap were never hit. Calculated at published prices, not a bill |
| Guards | no fidelity violation, no bound violation (actual ≤ reserved on all 14), `guard_halt` false; pre-run leak scan empty, no system-message hits |
| Environment | container unchanged since 00:27 (image `sha256:3e8cb9b9…`), healthy at start and end, no HTTP errors in the HAR |

Note: the reserved bound exceeded US$0.04 on request 13 (US$0.0402); under the old cap that request would have been refused pre-send. The owner-approved US$0.05 cap was necessary for this run to complete.

## No access to the answer
Start URL `http://localhost:7770` (storefront root), prompt = the official intent + answer-format instruction. The expected product slug appears in **no static input and no system message**. In the recorded requests it first appears in **request 13**, inside a `<read_state_0>` block returned by the agent's own `find_elements` call on the `cat=228` result list (step 12, with `href` attributes) — i.e. it discovered the URL by reading the site.

## Navigation path (from the trace and HAR)
1. Home → typed `ssd 1TB` in the search box, submitted (504 results, mixed with desktops).
2. Sorted by Price; first view was descending, so it switched to ascending (steps 3–5).
3. `find_elements` on result links: no standalone SSD ≥1 TB on page 1 → re-searched `1TB SSD` (still mixed, step 6–7).
4. Narrowed by category filters: Electronics (`cat=11`) → Computers & Accessories (`cat=56`) → Data Storage (`cat=228`, 42 items) (steps 7–9).
5. `search_page` for "SSD" (step 10), `find_elements` titles (step 11), then `find_elements` with `href` (step 12): "first SSD ≥1 TB is Portable SSD 2TB at position 11".
6. Navigated directly to the product URL it had read (step 13) → product page → `done` (step 14).

## Significant mistakes / inefficiencies (agent behaviour; none changed the outcome)
- Initial sort direction misread once (descending) and corrected; first query too broad; three filter clicks before the list was usable. Roughly 8 of 14 requests were spent narrowing noisy search, consistent with the plan's risk R2.
- It never opened intermediate product pages to verify capacity/price; it inferred "cheapest ≥1 TB" from the price-ascending Data Storage list and result titles. The evaluator confirms the final page is right, but the run does **not** show the verification was rigorous (the answer was correct on this occasion).
- It navigated by typing the product URL rather than clicking the link (allowed; the URL came from the site).

## Protocol and tooling
- Output protocol: 14 HTTP-200 responses = **2 raw-valid + 12 recovered** by the fixed parser `muse-prose-prefix-json-v1` (12 attempted, 12 valid, 0 rejected) — same prose-prefix behaviour as every earlier Muse run (raw strict-JSON compliance 14 %).
- **Tool visibility:** after the step-11 `find_elements` (titles) the agent made a second call with `attributes: ['href']` and the `<read_state>` output (reaching the model in the `suite-v2-compat1` profile) contained the "Found 12 elements … [0] <a> "SinLoon…"" listing it then used. This is the first **live** observation that the count-only visibility gap (Task 013) did not block the agent. It is one run: it does not establish that the v2 fix is reliable or that v1 would have failed here.
- No `find_elements` loops, no infrastructure errors, no cost-limit blocks.

## Attribution
| class | finding |
|---|---|
| Environment | none observed |
| Provider/infrastructure | none |
| Browser-tool | none observed; read-state delivery worked once |
| Website | **ambiguous, not determined from one pass.** The catalogue search is noisy (504 hits for "ssd 1TB", unrelated products when sorted by price) and the agent needed 8 narrowing steps; that is a property of the Magento search/category data that cost requests (≈US$0.13), but the run passed, so it is friction, not a failure. No readiness claim |
| Agent | minor inefficiencies (direction, broad query); no consequential error; verification thin |

## What this does and does not show
Shows: the full pipeline works live end to end — Meta endpoint, schema, reserve-before-send ledger (14/14 settled, bound never exceeded), Browser Use agent, real Magento, CDP HAR, original-HAR official evaluation, sanitized copy, leak scans. Does **not** show: reliability or a success rate (n=1; the first Muse pass on a Hard WAV task is not evidence it would pass again), effect of any website change, behaviour on other WAV tasks, or the effect of `suite-v2-compat1` versus v1. The raw artifacts must stay private (third-party catalogue content; Meta-terms question still open).

## Suggested next steps (none authorized; each needs approval and an exact plan)
1. Repeat the same task a few times (e.g. 3 runs, ≈US$0.75 calculated) to estimate variance before any website-variant work — the first run may have been lucky.
2. Task 25 (read-only review lookup) as the second shortlisted task.
3. Define one reviewed website intervention (derived image) only after a baseline of ≥3 runs exists.
