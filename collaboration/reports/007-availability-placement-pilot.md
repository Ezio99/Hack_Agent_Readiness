# Report 007 — Task 007 consolidated analysis (30 runs), reconciled against raw artifacts

Specification: [Task 007](../tasks/007-availability-information-placement.md). Reconciled 2026-10-28 by re-deriving every figure from `runs/pilot-task007/` (run.json, trace.jsonl, history.json, model-response-NN.json; untracked, Git-ignored, preserved locally) with the scripts in [`007-pilot-data/`](007-pilot-data/) (`reconcile.py`, `aggregate.py`, `attribution.py`, `check_docs.py`; outputs in `verification-output.txt` and `attribution-output.txt`; per-run data in `per-run-reconciled.json`). This replaces an earlier draft analysis; the differences are listed in [`CHANGES-from-first-analysis.md`](007-pilot-data/CHANGES-from-first-analysis.md). Per-installment reports are in [`007-installments/`](007-installments/) with a note where they were superseded. No model calls, reruns or edits to run data; execution commit `969d7d4`, code hash `1bc809ec…`, schedule `a2cf749c809e9a905d445d06b87fdb3411fda30978f01c291c74824a656f5eaa`, Chrome/145.0.7632.6, `muse-spark-1.3`. Descriptive and exploratory only; one controlled synthetic storefront, one model and framework, 3 runs per cell; costs are calculated from provider-reported tokens at published prices (the provider reports none).

## 1. Success and evidence-backed correctness
- **29 of 30 runs passed the independent evaluator** (arm A 15/15, arm B 14/15). Every pass had the answered product's page observed and verification established (A: availability on the listing; B: all higher-priced candidates' pages opened).
- **Run 27 (Fern, arm B) is classified as: an incorrect, insufficiently verified answer, caused by a tool-call loop that exhausted the step budget.** Three layers kept distinct:
  - *Mechanism:* after applying the brand filter (steps 1–2) the agent called `find_elements` seven times in a row (steps 3–9) with `attributes: ["href"]` every time. The harness's step results show the tool **did** return the product hrefs, but the model-visible history for each following request contained only the one-line summary `Found 11 elements matching "a".`; the agent concluded its calls "didn't include attributes" and repeated them. (Same pattern in Kitchen run 12 — 6 calls — and Outdoors run 15 — 5 calls; a single non-looping call in Bags run 23.) Budget warnings appeared at requests 9–11. It then opened Picnic Blanket (step 10, out of stock), went back (11) and answered at step 12.
  - *Outcome:* final answer `AR-7573, 4800 cents, available: false` (Picnic Blanket, out of stock) versus the target Trail Daypack (AR-7301). Evaluator FAIL: "Product ID does not match the task target; Product does not satisfy task constraints". Verification incomplete: 1 of 2 higher-priced candidates checked (Reading Lamp and Trail Daypack never opened). The agent's reasoning disclosed that the next candidate's ID and availability were unverified, but the answer schema has no uncertainty field, so the payload looks like a normal answer. The harness status reads `completed / agent_done` because the agent called `done`; only the evaluator establishes failure.
  - *Guard behavior:* the guard behaved as designed and was not involved in the failure: request 12 was the final step, the schema narrowed to done-only (`schema_narrowing_detected` true, expected), the verbatim last-step notice was present, and the request was accepted with no fidelity violation, cost-cap block or protocol error. The guard validates request fidelity; it does not and is not meant to prevent step-budget exhaustion.
  It is not a model-output error (the response was recovered and valid) and not an infrastructure failure. It is not evidence that hidden availability misleads the agent into confident errors, although arm B's longer required path exposes it to budget exhaustion.

## 2. Required navigation, overhead and verification shortfall
Definitions (unchanged for successful runs): *required* = oracle minimum detail visits (A 1; B = rank); *overhead* = actual − required, **reported only for successful runs**. For a failed run, overhead is not reported; a separate **verification shortfall** is: `detail_visit_shortfall = max(0, required − actual)` and `higher_priced_unchecked = higher-priced candidates − those opened` (arm B). Run 27: required 3, actual 1, shortfall 2, 1 of 2 higher-priced candidates unchecked (previous −2 "overhead" removed).
| Scope (rank) | Arm | Mean visits, all runs (successful only) | Required | Mean overhead (successful runs) | Runs with overhead > 0 |
|---|---|---|---|---|---|
| Kitchen (1) | A | 1.67 | 1 | +0.67 | 2 (08, 12) |
| Kitchen (1) | B | 1.00 | 1 | 0 | 0 |
| Bags (2) | A | 1.33 | 1 | +0.33 | 1 (24) |
| Bags (2) | B | 2.67 | 2 | +0.67 | 2 (19, 23) |
| Home (3) | A | 1.67 | 1 | +0.67 | 2 (04, 05) |
| Home (3) | B | 3.00 | 3 | 0 | 0 |
| Outdoors (3) | A | 1.00 | 1 | 0 | 0 |
| Outdoors (3) | B | 3.00 | 3 | 0 | 0 |
| Fern (3) | A | 3.33 | 1 | +2.33 | 3 (25, 28, 29) |
| Fern (3) | B | 2.33 (3.00 successful only, n = 2) | 3 | 0 (n = 2) | 0; run 27 shortfall 2 |
**Independent verification of counts.** Detail-page visits were derived three ways for all 30 runs — observation URLs in `trace.jsonl`, Browser Use's own `history.json` step states, and the `run.json` metrics block — and agreed on every run (no disagreement). Every run ends with a `done` action, so no final-action page went unobserved. **Positive overhead: 10 runs** — arm A (8): 04-s00-A2, 05-s00-A3, 08-s04-A1, 12-s04-A3, 24-s03-A3, 25-s02-A1, 28-s02-A2, 29-s02-A3; arm B (2): 19-s03-B1, 23-s03-B3. **Zero overhead among successful runs:** A 7, B 12 (B: Kitchen 3, Home 3, Outdoors 3, Bags 1, Fern 2). **Repeated detail-page visits:** exactly the same 10 runs — each reopened the answer page: 1 extra opening in eight runs (04, 05: Woven Basket; 08, 12: Glass Carafe; 19, 23, 24, 25: Trail Daypack) and 3 extra in 28 and 29 (Trail Daypack, 4 openings each) = 14 extra openings. In no run did a different product add to overhead; all overhead is re-opening of the same page.
**Fern runs 28–29 (verified from URLs).** Both opened `/products/304560591c6861459229` = **Trail Daypack (AR-7301, Fern, category Bags, $39.00, in stock)** four times each, from the listing between openings (28: click ×6, go_back ×1; 29: click ×4, navigate-to-root ×3). This is the correct Fern answer; Trail Daypack is also the Bags answer (same product and URL), which is why the Bags and Fern runs share the product name. No Bags-specific text was copied into the Fern results: the Bags figures belong to runs 19–24.

## 3. Requests, latency, tokens and cost (recomputed from run artifacts)
Means over 15 runs per arm; SD = sample SD.
| | Arm A | Arm B |
|---|---|---|
| Model requests (= steps) | 4.67 (SD 2.35) | 7.47 (SD 2.20) |
| Run time (s) | 22.9 | 27.2 |
| Model-request time (s); per request | 11.3; 2.42 | 16.4; 2.20 |
| Prompt tokens | 44,065 | 70,342 |
| Completion (reasoning) tokens | 1,651 (698) | 2,217 (842) |
| Cost per run (calculated) | US$0.0621 (SD 0.0321) | US$0.0974 (SD 0.0294) |
| Total calculated cost | US$0.9315 | US$1.4603 |
Pilot total **US$2.3918** (30 runs). Costs were recomputed from `run.json` `usage` (prompt × $1.25/M + completion × $4.25/M) and match the stored per-run metric to within 5 × 10⁻⁷ (the stored values are rounded to six decimals) and the driver's summary equally. **Rounding:** all means, differences and bootstrap draws use unrounded per-run values; costs are displayed to US$0.001 (means) or 0.0001 (per run), times to 0.1 s, differences are computed from unrounded means and then rounded (so a displayed difference can differ by one unit in the last place from the difference of displayed means), and the total is the unrounded sum (2.39176) rounded to the cent-fraction shown. By-scope B − A (all runs; successful-only visits in parentheses): Kitchen −0.67 visits (−0.67), −2.0 requests, −US$0.028; Bags +1.33 (+1.33), +3.0, +US$0.040; Home +1.33 (+1.33), +4.33, +US$0.055; Outdoors +2.0 (+2.0), +6.0, +US$0.078; Fern −1.0 (**−0.33**), +2.67, +US$0.031.

## 4. Within-arm variability and the predicted rank-based dose-response
| Scope (rank) | Predicted visits / observed | Predicted requests / observed | Observed cost B − A | Required + inefficiency difference = observed requests |
|---|---|---|---|---|
| Kitchen (1) | 0 / −0.67 | 0 / −2.0 | −US$0.028 | 0 + (−2.0) = −2.0 |
| Bags (2) | +1 / +1.33 | +2 / +3.0 | +US$0.040 | 2 + 1.0 = 3.0 |
| Home (3) | +2 / +1.33 | +4 / +4.33 | +US$0.055 | 4 + 0.33 = 4.33 |
| Outdoors (3) | +2 / +2.0 | +4 / +6.0 | +US$0.078 | 4 + 2.0 = 6.0 |
| Fern (3) | +2 / −1.0 (−0.33 successful only) | +4 / +2.67 | +US$0.031 | 4 + (−1.33) = 2.67 |
Exploratory bootstrap (5,000 resamples of runs within cell, seed 7; endpoints vary slightly with the random stream; intervals are descriptive, not tests): rank-3 pooled cost B − A US$0.055 [0.038, 0.072], requests +4.3 [3.2, 5.6], run time +5.9 s [0.3, 11.8], visits +0.78 [0.22, 1.33] (successful runs only: +1.00 [0.67, 1.44]); Bags cost +US$0.040 [0.021, 0.053]; Kitchen control cost −US$0.028 [−0.070, 0.021], requests −2.0 [−5.3, 1.7]. The Fern visit reversal is partly produced by run 27's single page lowering arm B's mean; excluding the failed run it is −0.33 (arm A's re-verification remains the main driver). Direction matches the prediction for four of five scopes and cost differences order Kitchen < Bags < Home < Outdoors with Fern between Bags and Home. Within-cell variability is large: Kitchen arm A requests 3–10 (cost US$0.039–0.134), Fern arm B 8–12, while Home arm B was exactly 8, 8, 8 and Outdoors arm A exactly 3, 3, 3. The dose-response is suggested, not established; Kitchen did not behave as a clean null.

## 5. Attribution: website-induced navigation, agent-induced inefficiency and agent–tool interface failures
Each run's model requests are split into three sources (`attribution.py`; per-run table in `attribution-output.txt`):
- **Website-induced navigation** — the deterministic path the page design forces: required requests A 2; B 2·rank (a click and a `go_back` per higher-priced candidate, then the answer click and `done`). The part attributable to *moving availability to detail pages* is B's required path minus A's: 2·(rank − 1) = 0, 2, 4, 4, 4 requests for Kitchen, Bags, Home, Outdoors, Fern (mean 2.8 per run over the 30 runs).
- **Agent–tool interface failures** — the three `find_elements` loops (12-s04-A3, 15-s01-B2, 27-s02-B2: 6 + 5 + 7 = 18 requests, 9.9% of all requests, about US$0.24 or 10% of spend by proration). The harness captured the hrefs but the model-visible history kept only a count line, so the agent re-issued the call. This is a defect in how tool output reaches the model, unrelated to the storefront design; it occurred in both arms (A 1 run, B 2 runs).
- **Agent-induced inefficiency** — every other request above the required path: re-opening a page already seen (10 runs), "thoroughness" detours to the root listing, applying the category/brand filter (two requests), backtracking, and a stray non-looping `find_elements` call (23-s03-B3). It is negative only for run 27, which was truncated by the step budget before completing the required path (12 requests < 6 required + 7 loop).
| Mean requests per run | Required (website) | Tool-interface | Agent-induced | Total |
|---|---|---|---|---|
| Arm A (n = 15) | 2.00 | 0.40 | 2.27 | 4.67 |
| Arm B (n = 15) | 4.80 | 0.80 | 1.87 | 7.47 |
| B − A | **+2.80** | +0.40 | −0.40 | +2.80 |
| Prorated cost per run, A / B | US$0.027 / 0.062 | US$0.005 / 0.011 | US$0.030 / 0.024 | US$0.062 / 0.097 |
**Accounting assumption (clarification added during Task 008 review).** The "agent-induced" column is a *residual*, not a per-request classification: `total requests − assumed required path (A 2; B 2·rank) − repeated find_elements calls in the three loop runs`. It bundles every other agent behaviour, and for a run that did not complete the required path (run 27) it is negative (−1) and not meaningful; excluding failed runs, arm B's mean residual is 2.07 (all runs 1.87). The dashboard calls it "residual agent overhead". Likewise, Fern arm B's mean *observed* detail pages (2.33) includes failed run 27 (1 of 3 required pages); this is incomplete verification, not better efficiency, and the successful-runs-only mean is 3.00.
By scope, B − A requests = website-induced + tool-interface + agent-induced: Kitchen −2.0 = 0 + (−2.0) + 0.0; Bags +3.0 = 2 + 0 + 1.0; Home +4.33 = 4 + 0 + 0.33; Outdoors +6.0 = 4 + 1.67 + 0.33; Fern +2.67 = 4 + 2.33 + (−3.67). Reading: (a) the website-induced part is deterministic and, on average, accounts for the whole mean B − A request difference (+2.80); (b) the Kitchen "negative control" anomaly (−2.0) is entirely the single arm-A tool loop, not agent behaviour; (c) Fern's shortfall relative to prediction mixes B's tool loop (adds requests) with A's repeated re-verification (adds requests in A) and run 27's truncation; (d) in arm A the agent-induced requests (2.27 per run) exceed the minimal path itself (2.00) — the agent's behaviour, not only the page design, dominates cost in several cells. Cost shares are prorated by request share and are approximate; the attribution of requests is exact. Per-request prompt size is nearly constant (9.4k–10.3k tokens in both arms: system prompt, DOM and screenshot dominate; the history adds little), so cost is close to proportional to the number of requests rather than growing super-linearly.

## 6. Tool loops, backtracking and re-verification
- **Tool loops** (≥ 3 consecutive identical `find_elements` calls): 3 of 30 runs — 12-s04-A3 (6 calls), 15-s01-B2 (5), 27-s02-B2 (7). All requested `attributes: ["href"]`; the tool output contained hrefs but the model-visible history showed only the count line (mechanism described in §1; attribution in §5). A single, non-looping call occurred in 23-s03-B3. This is a model/harness-visibility issue unrelated to the manipulation (A 1, B 2 loop runs).
- **Backtracking** (`go_back` or navigate to the root): about 1.1 per A run and 1.5 per B run.
- **Re-verification** (reopening an already-seen detail page): the 10 runs above — A 8 of 15, B 2 of 15 (both Bags). Reasoning cited "be thorough", "history claims … but I must re-verify", "exhaustive check". Average extra requests above the minimal path (2 for A; 2·rank for B) were equal across arms (2.67 each; SD 2.35 A vs 1.35 B). Supported only descriptively: arm A re-verified more often, arm B also did it, and the tendency may reflect agent caution rather than availability visibility.
- **Budget awareness:** budget warnings occurred in 4 runs (12, 14, 15, 27) and in two the reasoning shows rushing; the final-step state occurred once (run 27) and the guard accepted it.

## 7. Protocol compliance: 182 responses reconciled
Counted from every `model-response-NN.json` (182 files = 182 HTTP-200 responses = 182 model requests in the driver summaries; all `finish_reason: stop`):
| Category | All | Arm A (70) | Arm B (112) | First steps (30) | Later steps (152) |
|---|---|---|---|---|---|
| Raw-valid (strict JSON, no recovery needed) | **50** | 22 | 28 | 0 | 50 |
| Compatibility-recovered (single-line prose prefix + one valid object, parser `muse-prose-prefix-json-v1`) | **132** | 48 | 84 | 30 | 102 |
| Rejected / unrecoverable | **0** | 0 | 0 | 0 | 0 |
50 + 132 + 0 = 182; 132 / 182 = 72.5% recovered, 102 / 152 = 67% of later steps. No `model_output_error` occurred, and outcomes depend on the recovery layer: a strict-profile agent would have failed at step 1 (Task 004 Stage D). By installment, recovered/total: Home 26/35, Kitchen 25/34, Outdoors 26/36, Bags 20/29, Fern 35/48.

## 8. Limitations and alternative explanations
- One storefront (20 products, one page), one model, one agent framework and frozen prompt; five scope tasks with n = 3 per cell; one pass of the schedule; unseeded sampling.
- The arm A observation is larger (extra stock lines; different screenshot); effects are an end-to-end bundle.
- B's higher cost is largely mechanically required (more pages); the pilot measures its size and the agent's inefficiency, not whether the effect exists. Other explanations for departures from prediction: tool-loop luck, thoroughness style, budget-warning feedback, task wording, provider/time-of-day variation, block order (A first in three blocks, B in two).
- Success is near ceiling (29/30); the benchmark discriminates by effort, not accuracy. Scope size and rank are confounded for Fern (8 candidates).
- Evaluator and oracle share inventory truth by design; the oracle was checked against scripted Chromium browsing, not all possible agent strategies. The run-27 harness status (`completed`) does not encode answer sufficiency.
- No claims about real e-commerce sites, other models or agent frameworks, human users, or website-readiness scores.

## 9. Reproducibility
From the repository root with `runs/pilot-task007/` present: `PYTHONPATH=src python collaboration/reports/007-pilot-data/reconcile.py collaboration/reports/007-pilot-data/per-run-reconciled.json`, then `aggregate.py`, `attribution.py`, and `check_docs.py` (all read-only, no model calls). `per-run-reconciled.json` holds the 30 entries (run IDs, visits derived from three sources, response categories, recomputed tokens and cost). `check_docs.py` recomputes the headline figures and bootstrap intervals from the data files and fails if this report disagrees. Original data, schedule, fingerprint and raw traces are untouched; the pilot executed from commit `969d7d4` (this documentation was added afterwards and changes no executable file).
