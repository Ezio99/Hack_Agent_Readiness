# Report 015c — Task 015 two-run LIVE pilot (owner-authorized, executed once, 2026-10-29)

**Command:** exactly the authorized one (manifest SHA-256 `25a22bfdba02363b0b31eecbd1c3834b5744372dcf35ec79c2c111a1d6ae08b3`); PR #24 CI green beforehand; manifest, audit baseline and all hashed source files verified unchanged **before and after** the run. Two runs, sequential, `pilot-01` (modified site) then `pilot-02` (unmodified), `muse-spark-1.3`, `suite-v2-compat1`, `t1-anc-headphones-under-250-all`. No retry, replacement, extra probe or other paid call. Stopped after the pilot. **This is a two-run pilot: it is not evidence of a causal effect.** Raw traces, screenshots and per-request responses stay private under `runs/task015/pilot/runs/` (Git-ignored); only numeric aggregates are committed in [`collaboration/experiments/task015/pilot/results/`](../experiments/task015/pilot/results/).

## 1–2. Statuses and independent oracle verdicts
| run | website state (variant) | run status | outcome class | independent oracle | answer vs truth |
|---|---|---|---|---|---|
| `pilot-01` | modified: stock shown on cards + in-stock filter | completed, `agent_done` | completed (non-void) | **PASS**, evidence-backed | exactly {HP-1004, HP-1006, HP-1007} with catalogue prices (precision 1.0, recall 1.0) |
| `pilot-02` | unmodified: stock only on product pages | completed, `agent_done` | completed (non-void) | **FAIL**, not evidence-backed | reported only {HP-1004}: precision 1.0, **recall 0.33**, missing HP-1006, HP-1007; no ineligible item reported |
Both rows carry the frozen audit id `8770fb8a1d7a` and `recommendation_id = rec-show-availability-on-listing-cards`, finding fingerprints `attribute_detail_only:availability`, `filter_absent:availability`; the original audit report hash is unchanged. No void runs (no provider failure, budget stop, guard violation or timeout).

## 3. Effort and cost (calculated at published prices; not a bill)
| | pilot-01 modified | pilot-02 unmodified |
|---|---|---|
| model requests (HTTP 200) | 4 | 11 (limit 12) |
| agent steps / page views | 4 / 4 | 11 / 11 |
| product-page visits (distinct) | 0 | 3 |
| wall time | 15.2 s (mean 2.7 s/request) | 54.5 s (mean 3.3 s/request) |
| prompt / completion tokens | 38,632 / 1,175 | 111,821 / 5,047 |
| calculated cost | US$0.0533 | US$0.1612 |

## 4. Navigation and friction (from the private traces; paraphrased)
- **Modified (4 steps):** home → headphones category → one navigation to a filtered URL using ANC + the in-stock filter + max price → the page listed exactly the three eligible products → `done`. Zero product pages were needed.
- **Unmodified (11 steps):** home → category → applied ANC and price filter (5 candidates: HP-1004, 1005, 1006, 1007, 1008) → used `find_elements` three times to obtain product links → opened product pages to check stock one at a time (HP-1004 in stock; HP-1005 out of stock; HP-1008 out of stock), with a tab switch and a list reload (the stock filter does not exist in this state). After 11 steps the agent noted that HP-1006 and HP-1007 were **unchecked "due to step budget"** and reported only the verified item. So the unmodified-state failure is an *incomplete* answer caused by running out of its own budget while verifying candidates one by one; it did not report an out-of-stock item and did not guess.
- Consistent with the mechanism the product recommended (stock invisible on list cards ⇒ per-product lookups) — but one run per state, so this is an observation, not a demonstrated effect. Part of the unmodified effort was tool overhead (three `find_elements` calls, a tab switch), not stock lookups themselves.

## 5. Protocol compliance and parser recovery
15 HTTP-200 responses: 3 raw-valid strict JSON (20 %; run 1: 1/4, run 2: 2/11), **12 prose-prefixed and recovered** by the fixed `muse-prose-prefix-json-v1` (12 attempted, 12 valid, **0 rejected**). Same pattern as every earlier Muse run; recovery is part of the frozen agent.

## 6. Spending gate and budget
- Gate: 15 reservations written to the durable ledger before each request (upper bounds US$0.0348–0.0370, all ≤ the US$0.05 per-request cap), **15 settled, 0 unsettled**, no bound violation, no refusal, no halt. Actual per-request cost US$0.0124–0.0185 (35–50 % of the reserved bound).
- Pilot total (calculated): **US$0.2145 = A$0.3218** at the assumed 1 USD = 1.50 AUD, against the US$1.00 / A$1.50 stage hard cap and the US$0.50 per-run cap (run costs US$0.053 and US$0.161). Expected range was A$0.23–0.39: actual A$0.32.
- Programme: spent before A$5.885 → now **A$6.207**; **A$43.793 of A$50 remains** (calculated, not billed; the ledger file records original USD entries, runtime ledgers are counted on top).

## 7. Pilot gate decision (as frozen) — and an honest flaw in the gate
The frozen rule produced **`stop`: "ceiling effect: 3 product-page visits, extra items []"** because it required ≥ 4 product-page visits or a reported not-eligible item. I report this decision as computed; I did not alter it. **But the label "ceiling effect" is wrong for what happened**: a ceiling effect would mean the unmodified run had nothing left to improve, whereas the unmodified run *failed* (recall 0.33) by exhausting its step budget. The rule measured the wrong signature of "room to act" (visit count and extra items instead of incompleteness / budget exhaustion). Consequences: (a) by the letter of the frozen manifest the main stage is **not** supported by the pilot gate and nothing here authorizes it; (b) any future main proposal must fix the gate rule before freezing (e.g. "unmodified run did not obtain a complete correct answer, or used ≥ 75 % of its budget"), and say so openly, since fixing the rule after seeing the data is a researcher degree of freedom.

## 8. Unexpected behaviour, limitations, confounders
- n = 1 pair; agent behaviour varies run to run (the same T1 task passed or failed in earlier tasks with different tool behaviour). The unmodified run might have succeeded with a different tool path; the modified run might not repeat its 4-step solution.
- The modified-state agent used the in-stock filter through the URL — available only because the product's change adds it; the effect is "stock on cards **and** a filter" (one intervention, two components), not separable here.
- Run order was modified-first (seeded); no warm-up or order effect can be assessed with two runs.
- The unmodified run was budget-limited by the agent's own 12-step limit; a higher limit would change the outcome and cost.
- The scan record's legacy `diagnostics` (older scanner module) printed a website finding for the unmodified run using the variant label; that module is not part of the audit/recommendation engine and is **not** evidence of independence. The independent re-audit of the modified state reported both findings `resolved` (probe only); resolution is not an effect measurement.
- `effect-record.json`: `mode: live`, `n_pairs: 1`, verdict `inconclusive` as pre-registered for a pilot; no measured effect was attached to the audit (pilot stage never attaches).

## 9. Are further experiments justified, and what would they resolve?
Justified only as a *new, separately approved* proposal, because the evidence is suggestive but one-sided: the unmodified run failed in exactly the way the recommendation predicts, at ~3× the cost of the modified run, and the modified run was clean. What a main-stage experiment (≈ 6 paired blocks, ≤ A$7.50 cap) would resolve: (1) whether the difference is systematic or run-to-run variation (the single biggest uncertainty); (2) whether the gap is mostly *failure/incompleteness* (correctness) or *effort*; (3) whether the stock cue and the stock filter each matter (not separable with the current single change); (4) whether the control task shows no shift. It would **not** resolve generality (one site, one model, one task). Before any such proposal the gate rule must be corrected as in §7, the manifest regenerated, and a separate approval obtained. Stopping here is also a reasonable decision: the product's autonomous diagnose→recommend→resolve loop is already demonstrated offline, and the live evidence so far is one pair.
