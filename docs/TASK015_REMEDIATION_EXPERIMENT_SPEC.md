# Task 015 — Autonomous diagnose → recommend → modify → rescan product + controlled experiment (APPROVED for offline work; no paid run authorized)

Status 2026-10-29 (updated after the owner's approval): offline implementation and tests approved; durable per-request spend guards approved; **no paid inference authorized**. The product requirements and budget policy below were added by the owner and are binding. It builds on the existing `electronics-v1` storefront, the Task 011 scanner and the Task 012 experiment infrastructure; no new storefront or architecture is proposed. WebArena/Magento is not modified.

## 0. Binding product requirement and acceptance criteria (owner, 2026-10-29)
Agent Readiness must **independently diagnose website friction and select applicable recommendations at runtime**; the demonstration must not rely on a hand-picked recommendation. A rule-based recommendation engine is acceptable (no extra LLM); the architecture must allow future trace-driven discovery of unknown problems.
| # | Acceptance criterion | Where it is met (see Report 015) |
|---|---|---|
| 1 | Given the baseline storefront, the product detects that stock availability is absent from listing cards but present on product pages | `remediation/probe.py` + `findings.py` (`attribute_detail_only:availability`, with counts and page/element evidence) |
| 2 | It selects the appropriate recommendation from its library using observed evidence | `remediation/library.py` `select()` — a template fires only if a matching finding exists |
| 3 | The recommendation carries evidence, rationale, expected benefit and an honest confidence/validation status | recommendation object: `supporting_evidence`, `rationale`, `expected_benefit`, `risks`, `confidence`, `validation = unvalidated` |
| 4 | Given the modified storefront, an independent rescan recognises the original finding as resolved | `engine.lifecycle()` compares two audit reports by finding fingerprint |
| 5 | Neither the recommendation nor the resolved status depends on baseline/modified labels, hard-coded outcomes or arm identifiers | engine inputs are probe observations only; signature + source-scan tests; works on a structurally different stub shop |
| 6 | Observed website properties, agent execution failures, proposed interventions and measured effects are distinguished | report sections `findings` / `agent_execution` / `recommendations` / `measured_effects` with a taxonomy; resolution ≠ effect |
| 7 | Executable through the real product interface/API, not only a demo script | scanner service `POST /api/audits` (+ `GET /api/targets`, admin change endpoint), `readiness audit URL` CLI, dashboard "Site audit" panel; `scripts/remediation_loop_demo.py` is only an API client |

## 0b. Budget policy (owner, 2026-10-29)
- Programme research budget **A$50** (a ceiling, **not** an authorization to spend). Tracked in **AUD**; every original **USD** record is retained in `collaboration/budget/programme-ledger.json`; conversion uses the documented assumption **1 USD = 1.50 AUD** (deliberately above the ≈1.43–1.45 early-October-2026 market quotes, so AUD figures overstate spend; override with `AGENT_READINESS_USD_TO_AUD`). All USD figures are **calculated** at published prices, not billed.
- Spent to date (calculated): **US$3.923 = A$5.88**; remaining **A$44.12** of A$50. (Task 004–005 0.11, Task 006 0.104, Task 007 2.392, Task 011 0.351, Task 012 Stage 1 0.718, Task 014 0.248.)
- Limits are explicit at four levels and enforced by the durable per-request gate (`spend_gate.RequestGate`, now also pluggable into the synthetic-suite runner): **per request** (upper-bound reservation, written to disk before the request is sent), **per run** (sum of that run's reservations), **per stage** (ledger ceiling), **programme** (A$50 checked by `budget.check_stage` before a stage is approved). Timeouts, errors and missing usage keep the full reservation counted.

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
- **Randomisation:** 6 blocks; within each block the order of B and M is randomised by a seeded permutation (ABBA-style balance over blocks), T4 control interleaved. Seed and schedule hash recorded before any run (Task 012 `schedule.py`).
- **Runs:** T1 × {B, M} × 6 blocks = 12 runs; T4 × {B, M} × 3 blocks = 6 runs; total **18**. A 1-run-per-arm **pilot gate** (T1-B, T1-M) precedes the rest (see §10). B/M are experiment-design labels used only by the experiment driver — never by the audit engine.
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
Descriptive per-arm table; paired-by-block difference of the primary metric with the Task 012 permutation test and bootstrap CI (n=6 pairs: minimum attainable exact two-sided sign-flip p = 2/64 ≈ 0.03, so we report effect size and interval and call it *consistent with* or *not detected*, never "proved"); mechanism review of traces (did stock-lookup visits fall; did the agent use the stock cue); control-task comparison; per-run attribution (website / agent reasoning / agent–tool-interface / infrastructure) from evidence only. **Negative-result interpretation:** if M does not reduce effort or errors, report "no effect detected at n=4 per arm", not equivalence; candidate explanations to check in the traces: the agent opens detail pages anyway (e.g. to verify price/SKU), the baseline agent skips verification and passes by luck/guess (ceiling), tool-visibility loops dominate (tool, not site), or variance swamps a small effect. The recommendation then stays an unvalidated hypothesis on the dashboard and the demo shows the null honestly; supporting Task 007 evidence is shown separately and labelled as a different site/task.

## 8. Product design (implemented offline; supersedes the earlier "reuse + two additions" sketch)
`src/agent_readiness/remediation/`: **probe** (black-box HTTP, same-origin, GET-only, bounded; finds listing pages/cards structurally — a repeated link template inside a repeated element that holds a price — and checks cards, sampled product pages and filter controls for attribute cues) → **findings** (`attribute_detail_only`, `attribute_partial_on_cards`, `attribute_on_cards`, `filter_absent/present`, `insufficient_coverage`; each with a `kind:attribute` fingerprint) → **library** (rule-based templates; selection requires a matching finding; rationale generated from the finding's own counts) → **execution** (agent evidence from a recorded scan, kept apart; link to a website finding is only `inferred`) → **discovery** (trace detectors emit candidate patterns with no recommendation) → **engine** (`build_report`, `lifecycle`, `attach_measured_effects`). Managed demo target (`targets.py`) lets an operator apply a library change id to a served storefront; the audit API accepts only registered target ids (no URL, variant or label fields).

## 9. Dashboard
Existing React app, "Protected scanner" tab gains a **Site audit** panel (audit a registered target, re-audit and compare with the previous audit). The report view has five labelled sections (observed properties, agent execution, proposed interventions, re-audit lifecycle, measured effects) and never claims an improvement without a measured effect. The earlier "baseline-vs-modified bars with intervals" view is deferred until measured data exist (it needs the paid experiment).

## 10. Revised paid plan with explicit limits (FOR SEPARATE APPROVAL — no spend authorized)
All figures calculated; AUD at 1.50. Limits are reservations enforced before sending; real spend is expected far lower.
| level | limit (USD / AUD) | enforcement |
|---|---|---|
| per request | US$0.05 / A$0.075 upper-bound reservation (input incl. 4,000-token screenshot allowance + full 4,096-token completion, +10 %) | `RequestGate` refuses before the network |
| per run | US$0.50 / A$0.75 (sum of reservations; ≤ 16 requests; 12 steps/240 s per the T1 contract) | gate + run marker (one attempt) |
| **Pilot stage (2 runs)** | **hard cap US$1.00 / A$1.50**; expected US$0.17–0.30 / A$0.25–0.45 | ledger ceiling for the stage |
| **Experiment stage (after pilot review; 18 runs)** | **hard cap US$5.00 / A$7.50**; expected US$1.7–2.4 / A$2.6–3.6 | ledger ceiling for the stage |
| programme | A$50; spent A$5.88; after the pilot cap at most A$7.38 spent; after both caps at most **A$14.88** (A$35.12 untouched) | `budget.check_stage` |
**Pilot (2 runs):** T1 on the modified-state site and the unmodified-state site, one run each, sequential, through the product's scan path with the gate plugged in; continue only if the unmodified run shows room for the intervention to act (≥ 4 product-page visits or a stock-related answer error); otherwise stop and report the ceiling effect.
**Experiment (after pilot review):** 6 randomized blocks: T1 × {unmodified, modified} = 12 runs, plus the stock-independent control task T4 × 2 blocks × {unmodified, modified} = 6 runs (n = 6 pairs makes a two-sided sign-flip p of 2/64 ≈ 0.03 attainable). Analysis as §7; the summary is attached to the audit report with `attach_measured_effects` (provenance, n, intervals, verdict), which is the only way a recommendation's validation can change.
**Stop conditions:** stage cap, any bound violation, two infrastructure errors, two parser rejections per block, any fidelity violation, the pilot gate failing. No retries, no replacements.
**Driver (built offline, Report 015b):** a sequential pilot/experiment driver that applies each scheduled state to the managed target, runs the live scan under the `RequestGate` and an AUD-aware stage ledger, records rows, then audits before/after and attaches the measured effect. The arm labels live only in this experiment driver (design), never in the audit engine.

## 11. What is done and what remains
| work | status |
|---|---|
| Probe, findings, library, execution evidence, discovery hook, engine/lifecycle/measured-effects | **done** (offline, tested) |
| API (`/api/targets`, `/api/audits`, admin change), CLI `readiness audit`, managed demo target | **done** |
| Dashboard Site audit panel | **done** (Vitest) |
| AUD budget module + ledger file; durable gate generalised and plugged into `execute_scan` | **done** |
| Offline demonstration through the API | **done** (`scripts/remediation_loop_demo.py`, output in `collaboration/reports/015-offline-demo-output.txt`) |
| Pilot/experiment driver with AUD stage ledger | **done** (offline, tested; [Report 015b](../collaboration/reports/015b-pilot-driver-offline.md)); frozen pilot manifest committed under `collaboration/experiments/task015/pilot/` |
| Paid pilot (2 runs), review, paid experiment (18 runs), analysis, baseline-vs-modified chart | **needs separate approval** ≈ 2–3 h + wall clock ≈ 40 min |
| 3-minute demo assets | ≈ 2–3 h |
Demo path (≈ 3 min): ① audit the unmodified site (findings with evidence, recommendation selected at runtime) → ② the owner applies the proposed change → ③ re-audit: finding recognised as **resolved** → ④ measured effect (from the experiment) or the honest "not measured yet" → ⑤ vision.

## 12. Risks and what could invalidate the result
Probe heuristics generalise only as far as tested (two markup families so far; real sites will expose gaps — `insufficient_coverage` is reported rather than guessed). Resolution is not effect. Ceiling (agent verifies everything anyway or skips verification); tool-visibility loops (v2 fix weakly observed live); small n; one model/site/task; Meta-terms limits for publishing traces (only rule-generated aggregates are shown); Task 007's evidence is from a different site and task; the audit must only be pointed at sites you operate or may test.

## 13. Decisions requested
1. Approve building the pilot/experiment driver (≈ 3–4 h, offline). 2. Approve the pilot call plan in §10 (≤ A$1.50 hard cap, 2 runs) — separately, after the driver is reported. 3. The experiment stage (≤ A$7.50) only after the pilot is reviewed. **No paid call is authorized by this document.**
