# Task 015 — Controlled diagnose → recommend → modify → rescan experiment (PROPOSED; nothing here is approved or executed)

Status 2026-10-29: specification + implementation plan for review. **No model call, no code change beyond this document.** It builds on the existing `electronics-v1` storefront, the Task 011 scanner and the Task 012 experiment infrastructure; no new storefront or architecture is proposed. WebArena/Magento is not modified.

## 1. What we want to demonstrate
**Baseline scan → identify friction → recommend a change → modify the site → rescan → measure the effect**, on one task, with an independent oracle, and with honest uncertainty. The Magento task 286 run showed the *shape* of the friction: about 8 of 14 requests went on narrowing a noisy result list because the attribute that mattered (capacity) was not visible in result cards. That run does not show Magento caused it (it passed; cause undetermined). We therefore test the same *mechanism class* — "a decision-relevant attribute is visible only after opening a page" — in an environment where we control the site and the ground truth.

## 2. Proposed intervention (one factor, existing in the codebase)
**Show stock status on listing/search cards (and keep the in-stock filter) — factor `availability: detail → listing`**, with everything else fixed.
- **Why this one:** (i) the mechanism is concrete and mirrors the 286 friction (attribute needed for the decision is only on detail pages); (ii) it already exists as a controlled, tested factor (`variants.py`), so no new storefront code; (iii) the scanner already has an evidence-linked rule for it (`diagnostics.analyze`: "Stock status was only available on product pages", with a recommendation labelled an unvalidated hypothesis and a `validate_with` pointer); (iv) there is prior descriptive evidence on the legacy storefront (Task 007, n=3 per cell: detail-only needed +2.7…+6.0 requests in rank ≥2 scopes) — which makes this a *replication on a new site/task through the productised pipeline*, not a new discovery, and we say so.
- **Fixing the SKU confound:** Task 012 Stage 1 showed T1 needs a SKU that is only on detail pages, which forces detail visits in both arms and hides the availability effect. Both arms therefore use `sku: listing` (Task 013 factor), so the only difference between arms is whether stock is visible on cards.
- **Arms:** **B (baseline)** `electronics-v1/availability-detail+specs-structured+sku-listing`; **M (modified)** `electronics-v1/availability-listing+specs-structured+sku-listing`. Same data version (`electronics-v1+7c4eaccbb161`), same task text, same agent. The variant is chosen by server config only; it appears in no URL, header or page.
- **Expected mechanism:** ANC headphones ≤ A$250 are 5 candidates (HP-1008 A$129 and HP-1005 A$229 are *out of stock*; HP-1007/1006/1004 are in stock). In B the listing shows no stock cue, so a careful agent must open each candidate page (≈5 extra page views) or guess; a careless one reports out-of-stock items (a correctness failure caused by missing information). In M the cards state stock, so the answer can be read from one filtered list.
- **Alternatives considered:** *attribute chips on cards* (closest to 286, but the `specs` factor changes chips and detail format together and filters already expose the attributes — would need a new isolated factor and likely hits a ceiling); *SKU on listing* (Task 013 Part B; peripheral story, deferred by the owner); *Magento derived image* (largest uncertainty, 4–8 h, a different risk class). Not recommended for the demo.

## 3. Task and independent oracle
`t1-anc-headphones-under-250-all` (frozen fixture): "every in-stock ANC headphone at or below A$250.00: SKU + price". Oracle = catalogue-only function (`oracle_anc_in_stock`), exact set {HP-1007, HP-1006, HP-1004} with catalogue prices; precision/recall, extra/missing reported; evidence v2 requires the SKU and price text to have been shown to the agent. Feasibility is verified by scripted navigators in all variants (existing tests); the oracle never reads the web app.
**Negative-control task:** `t4-policy-delivery-tessera-whisper` (return/delivery policy; stock-independent). Expected: no arm difference. A difference there would signal drift or noise, not a stock effect.

## 4. Agent and run configuration (frozen)
Model `muse-spark-1.3`, endpoint `https://api.meta.ai/v1`, reference agent **`suite-v2-compat1`** (tool-result visibility fix; weakly observed live in the 286 run) and its fixed parser; limits 12 steps / 12 requests / 240 s (the T1 contract); one attempt per scheduled run, no retries, no replacements; sequential; fresh browser per run; same code SHA and frozen-config hash re-checked before every run. Raw strict-JSON compliance and compatibility-recovered responses reported separately, as before.

## 5. Design
- **Randomisation:** 4 blocks; within each block the order of B and M is randomised by a seeded permutation (ABBA-style balance over blocks), T4 control interleaved. Seed and schedule hash recorded before any run (Task 012 `schedule.py`).
- **Runs:** T1 × {B, M} × 4 blocks = 8 runs; T4 × {B, M} × 2 blocks = 4 runs; total **12**. A 1-run-per-arm **pilot gate** (T1-B, T1-M) precedes the rest (see §8).
- **Controls:** same catalogue/task/profile/limits across arms; blocks absorb slow drift; the control task detects arm-independent shifts; scripted navigators prove both arms are solvable; leakage checks (no answer in task text, schema, or system messages; stock cue absent from every B page — existing isolation tests); void rules below separate agent from environment/provider effects.
- **Pre-registered prediction:** M reduces model requests per T1 run by ≥ 3 versus B and reduces product-detail visits by ≥ 3; correctness is equal or better in M; T4 differs by < 2 requests. If the prediction fails, it is reported as failed.

## 6. Metrics (per run, from the existing recorder/evaluator)
| group | metrics |
|---|---|
| success | independent PASS/FAIL, precision/recall, extra (out-of-stock) items reported, evidence-backed |
| navigation effort | model requests, steps, page views, product-detail visits, **stock-lookup visits** (detail pages of in-budget ANC candidates), revisits, reference-path excess |
| tool calls | counts by action name (navigate/click/input/find_elements/search_page/done), repeated-action runs, visibility-gap steps |
| cost / time | calculated cost (published prices; not a bill), tokens, elapsed seconds |
| errors | infrastructure errors, parser rejections (recovered vs rejected), guard stops, cost-limit blocks, timeouts, model-output errors |
Primary: **model requests per T1 run**. Secondary: product-detail visits, correctness, cost. Void rules: infrastructure/provider failure or a guard stop voids that run for effect estimates (reported, not hidden); a tool-visibility gap is labelled agent–tool-interface and kept as an analysis stratum.

## 7. Analysis (fixed before any run)
Descriptive per-arm table; paired-by-block difference of the primary metric with the Task 012 permutation test and bootstrap CI (n=4 pairs: minimum attainable exact p ≈ 0.06 two-sided, so we report effect size and interval and call it *consistent with* or *not detected*, never "proved"); mechanism review of traces (did stock-lookup visits fall; did the agent use the stock cue); control-task comparison; per-run attribution (website / agent reasoning / agent–tool-interface / infrastructure) from evidence only. **Negative-result interpretation:** if M does not reduce effort or errors, report "no effect detected at n=4 per arm", not equivalence; candidate explanations to check in the traces: the agent opens detail pages anyway (e.g. to verify price/SKU), the baseline agent skips verification and passes by luck/guess (ceiling), tool-visibility loops dominate (tool, not site), or variance swamps a small effect. The recommendation then stays an unvalidated hypothesis on the dashboard and the demo shows the null honestly; supporting Task 007 evidence is shown separately and labelled as a different site/task.

## 8. Scanner: detect and recommend (reuse + two small additions)
- **Reuse:** a baseline scan of T1-B already yields the website finding "Stock status was only available on product pages in this variant" with step/path evidence, and a recommendation (`show In stock / Out of stock on listing cards + in-stock filter`) labelled *hypothesis_unvalidated* with `validate_with {factor: availability, from: detail, to: listing}`. Verified offline in a mock scan today: the finding appears in B and not in M, and `diagnostics.compare` reports `factors_changed = {availability: [detail, listing]}`, `controlled = true` (the mock follows the scripted path, so its numbers show the mechanism, not an effect).
- **Add 1 (≈2 h):** quantify the finding — number and share of page views that were stock lookups, and the calculated cost they represent — with links to the step records.
- **Add 2 (≈1.5 h):** a multi-run aggregator that emits one sanitized `remediation-v1` JSON (arms, per-run rows, findings, recommendation, applied change, comparison, caveats) for the dashboard and the report.

## 9. Dashboard (existing React app, one new tab)
"Remediation loop" tab fed by `dashboard/public/remediation/task015.json` (synthetic-store aggregates and rule-generated text only — no model text, no third-party content): ① task + oracle; ② baseline scan (outcome, requests, findings with evidence links); ③ recommendation (hypothesis badge); ④ the change (factor flip, before/after card screenshot of our own storefront); ⑤ rescan results; ⑥ baseline-vs-modified bars (requests, product visits, cost, correctness) with per-run dots and interval; ⑦ control-task panel; ⑧ verdict banner generated from the pre-registered rule (supported / not detected / contradicted) and caveats. Reuses `components/ui.tsx`, the metrics helpers and the Task 007 supporting panel; CI-safe synthetic fixture exactly like Task 008. A clearly marked **MOCK** dataset is used for development and as the demo fallback.

## 10. Budget and ledger
Calculated cost per run (Task 011/012 history): T1-B ≈ US$0.10–0.17 (more requests), T1-M ≈ US$0.05–0.09, T4 ≈ US$0.06–0.09. Expected total ≈ **US$0.9–1.3**; hard stage ceiling **US$1.60**. Calculated programme spend so far ≈ US$3.9 of the US$6.00 programme ledger, so ≈ US$2.1 remains; this experiment would use ≤ 76 % of it at the ceiling. Enforcement: the Task 012 ledger (per-run reservation) is sufficient; optionally plug the Task 014 durable per-request `RequestGate` into `execute_scan` (≈1.5 h) for the stricter reserve-before-send guarantee — recommended because the pilot is the last big spend. Stop conditions: ceiling, two infrastructure errors, two parser rejections per block, any fidelity violation, pilot-gate failure.
**Pilot gate (2 runs, ≈US$0.15–0.25):** run T1-B and T1-M once. Continue only if the baseline run is not already trivial (B ≥ 4 stock-lookup visits or a stock-related error) — if B passes with no lookup behaviour, the intervention has no room to act; stop and report the ceiling instead of spending the rest.

## 11. Implementation plan and estimate
| work | reuse | hours |
|---|---|---|
| Experiment config `task015` (arms with `sku=listing`, schedule, hashes, void/halt rules, analysis config) | `experiments/{design,schedule,manifest,analysis,driver,ledger}.py`, `make_variant` | 2.5–3.5 |
| Scanner additions (quantified finding, aggregator → `remediation-v1`) | `scanner/diagnostics.py`, `execute.py` | 3–3.5 |
| Optional durable per-request gate in `execute_scan` | `webarena/live.py` `RequestGate`, `capture.py` hook | 1.5 |
| Mock rehearsal + tests (schedule, void rules, aggregator, finding on B only, isolation checks) | existing mock personas, 570-test suite | 2–2.5 |
| Dashboard "Remediation loop" tab + tests + synthetic fixture | `dashboard/` components, Vitest | 5–6 |
| Live runs: 2-run pilot then 10 runs, ≈25–35 min wall clock, analysis, report | `readiness` driver | 2–3 |
| Demo assets (script, screenshots/recording), docs, PR hygiene | — | 2–3 |
| **Total** | | **≈18–23 h** |
**Smallest convincing path (≈11–13 h):** config + aggregator + dashboard tab (mock-fed first) + pilot + 8 T1 runs (skip the optional gate and the T4 control only if time forces it; control strongly preferred) + a 3-minute walkthrough. The 3-minute demo (hackathon deadline 2026-11-04, 9 PM EST per the organiser note — timezone still to be confirmed): 0:00 the question and the 286 friction in one sentence; 0:30 baseline scan, finding with evidence links; 1:15 recommendation and the one-line change; 1:45 rescan and baseline-vs-modified bars; 2:30 honest verdict banner, control task, caveats; 2:50 registry/API vision as future work.

## 12. Risks and what could invalidate the result
Ceiling (agent verifies everything anyway or skips verification); tool-visibility loops (v2 fix only weakly observed live); parser/format variance; small n (4 pairs); one model/site/task — no generalisation; Meta-terms and publication limits for any traces (only rule-generated aggregates are shown publicly); Task 007's earlier evidence tempts over-interpretation; budget headroom is limited.

## 13. Decisions requested
1. Approve the intervention (stock on cards, `sku=listing` fixed in both arms), the T1 task and the T4 control. 2. Approve credential-free implementation (config, scanner additions, dashboard tab, tests) — ≈11–13 h smallest path. 3. Decide on the optional durable per-request gate. 4. Later, separately: approve the exact call plan (pilot 2 runs, then 10), ceiling US$1.60. **No paid call is authorized by this document.**
