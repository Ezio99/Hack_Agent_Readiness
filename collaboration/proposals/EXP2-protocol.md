# EXP-2 protocol — how well do AI agents understand and use a realistic rental business? (Ironbark Hire Co.)

**Status: PROPOSAL, nothing paid has run.** The US$20 figure is a planning ceiling, not an authorisation. EXP-B, its ledgers, snapshots, tasks and findings are untouched and not read. Site: [docs/IRONBARK_STOREFRONT.md](../../docs/IRONBARK_STOREFRONT.md). Candidate variants: [EXP2-candidate-scenarios.md](EXP2-candidate-scenarios.md). Generated, reviewable artifacts: [collaboration/experiments/EXP2/](../experiments/EXP2/) (study plan with every task question, pool summary; **no answers**).

## 1. What we are trying to learn, and what we do not assume
Primary question: on a realistic small-business site, **where do agents succeed, struggle or fail, and why?** across product discovery, dated availability, kit-versus-individual comparison, total cost, delivery and deposit reasoning, compatibility and multi-constraint planning. Secondary: *if* the baseline shows website-attributable friction of a kind a candidate change addresses, does that change move behaviour under a controlled comparison?
We do **not** assume agents struggle, that any variant helps, or that any task is hard. A clean baseline (high pass rates, few requests) is a valid and useful result: it would say Ironbark's control site is already agent-ready on these tasks.

## 2. Integration assessment (credential-free, done)
Run: `readiness exp2 assess [--variant V]` and the browser tests in `tests/test_exp2_browser.py`.

| area | result |
|---|---|
| Crawl of control + 4 variants + the all-variants build with the pipeline's own crawler | faithful: 55 pages (66 with discoverability) + 51 assets, 2,022+ references resolve, fidelity "high", deterministic snapshot hash, text/links/variant markers identical to the served site |
| **Gap found and fixed:** the pipeline's default crawl limits (`max_assets=20`) keep only 20 of 51 CSS/SVG assets, which would give a broken, unstyled mirror | explicit `exp2/snapshot.py` limits (120 pages, 100 assets); the gap is documented by a test |
| Mirror (read-only, CSP) in real Chromium | stylesheet applied, every image loads, no failed or 4xx request, no console error (control, cost and discoverability pages) |
| Trial runner, evidence check, ledger, approvals, quarantine | reused **unchanged**; a full mock run (real browser, scripted agent, independent grading) works end to end |
| **Site defect found by task verification and fixed:** the terms page says courier delivery is for items under about 25 kg, but the 22 kg core drill was classed "machine delivery" | `delivery_class` corrected; a data test now enforces the stated rule |
| **Generator bug found by the independent recomputation path:** a late-binding closure made every product-to-accessory task recompute for the wrong product | fixed; the verifier rejects any such disagreement |
| Variants | tested to change *access* only: every price, rule, specification and calendar cell read from a variant's pages equals the control's |
| Existing LLM task generation (`taskgen`) | **not used**: its four criterion kinds (page fact, reach page, item set, extremum) cannot express dated availability, totals or compatibility. Replaced for Ironbark by deterministic generation with typed answers; the existing runner and `TaskInstance` grading interface are reused |
| Not integrated in this PR | the investigator stage on an Ironbark run (protocol below), and the variant-test driver (rules and analysis are implemented and tested; the driver is a follow-up) |

## 3. Website-aware task generation and verification
Code: `src/agent_readiness/exp2/{tasks,verify,facts,answers}.py`. No model writes a task. Eight families, each derived from the site's own catalogue, booking calendars, kits, accessories, terms and rules:

| family | what a task asks (examples of the shape) |
|---|---|
| lookup | a labelled fact on one page (deposit, weight, minimum hire, "is delivery compulsory") — **negative controls** |
| discovery | a customer need in everyday words ("grind out a tree stump") or a trade synonym ("jackhammer") → the right item |
| availability | single date yes/no, next free date after a booked run, units free, which items in a category or in a named list are free for a weekend or a date range |
| kit_vs_items | kit vs separate hire for 1 or 7 days (choice, saving, total), including a case where the kit is *not* the cheaper option |
| total_cost | total for one item (period, optional waiver, optional or required delivery), the weekly-cap rule where it binds, two-item totals |
| delivery_deposit | delivery fee by item weight, which items in a category require delivery, highest deposit, combined deposits |
| compatibility | which accessory fits a machine, which items an accessory fits, yes/no fits, fuel price |
| planning | cheapest item meeting spec constraints that is also free on every day of a range (and its total), two-job renovation totals, budget sets |

**Independent verification** (every candidate, `verify.py`): (1) the truth computed from the source data must equal the truth **recomputed from the rendered control pages** (parsed text, never `data.py`); (2) no ties, no empty or oversized sets, dates inside the booking window; (3) every evidence page exists and is reachable within 4 clicks; (4) the question does not contain the answer or an internal catalogue code, and does not name pages ("the Kits page"); (5) the grader accepts the canonical answer, rejects wrong answers and rejects a hedge that offers the right and a wrong answer; (6) no duplicate fingerprint, question or (family, template, truth, evidence) combination.
**Result:** 388 generated, **326 accepted, 62 rejected** — 54 as trivial repeats, 7 empty answer sets, 1 as ambiguous (two Landscaping items tie on the highest deposit). Answer kinds: money, number, integer, date, yes/no, choice, product, product set, accessory. Grading is exact on a normalised form; hedges, ranges and several values are never an answer.
**What the agent receives:** the question text (with a fixed answer-format sentence) and a one-field answer schema; nothing else. Truth, expected text and evidence pages live only in the run's private criteria (never in the public plan, never shown to the investigator). A test scans the plan for leaks.
**Evidence rule:** a pass is "evidence-backed" only if the agent visited the product (and for kit tasks kit) pages that hold the facts. Evidence pages are identical for every variant, so a variant cannot gain or lose a pass by changing which page shows the number.

## 4. Proposed baseline study
Control site only. 40 tasks, 54 trials, fixed order (`plan_sha256 115dce98…`, in `study-plan.json`). Difficulty is a *design estimate* from the number of pages a task needs on the control site (easy ≤ 2, medium 3–4, hard ≥ 5); the baseline will measure real difficulty.

| family | tasks | easy / med / hard | investigation / holdout | answer kinds | sensitive to variant |
|---|---|---|---|---|---|
| lookup | 4 | 4 / 0 / 0 | 3 / 1 | integer, money, number ×2 | — (negative controls) |
| discovery | 6 | 0 / 6 / 0 | 4 / 2 | product ×6 | discoverability 6 |
| availability | 7 | 3 / 1 / 3 | 5 / 2 | date, integer, products ×4, yes/no | availability 7 |
| kit_vs_items | 5 | 1 / 4 / 0 | 3 / 2 | choice ×2, money ×3 | compatibility 4, cost 5 |
| total_cost | 6 | 0 / 6 / 0 | 4 / 2 | money ×6 | cost 6 |
| delivery_deposit | 3 | 0 / 3 / 0 | 2 / 1 | money ×2, products | cost 2 |
| compatibility | 4 | 1 / 3 / 0 | 3 / 1 | accessory, money, products, yes/no | compatibility 4 |
| planning | 5 | 0 / 1 / 4 | 3 / 2 | money ×2, product, products ×2 | availability 4, cost 4, discoverability 1 |
| **total** | **40** | 9 / 24 / 7 | **27 / 13** | | discoverability 7, availability 11, cost 17, compatibility 8 |

* **Partition:** stratified by family; roughly a third are **holdout**. Holdout tasks are never shown to the investigator, never used to decide which variant to test, and only confirm or withdraw a later comparison.
* **Repeats:** every task once (k = 1); **14 tasks twice** (both partitions, every family), to estimate run-to-run variation, which EXP-B lacked.
* **Order:** repeat 1 of every task, interleaved by family, then the 14 repeats. The first 8 trials (the pilot) cover 8 different families.
* **Negative controls for every variant:** every task not sensitive to it (at least 23 of 40 for each) plus the 5 insensitive ones overall.
* **Per-task limits:** 10–27 model requests, 10–27 steps, 600 s, scaled to the pages a task needs.

## 5. Cost model, allocation and gates (hard ceiling US$20 for Experiment 2)
All figures are **calculated at published prices (US$1.25 / 4.25 per million input / output tokens), not billed**. Assumption (from EXP-B's US$0.0115–0.0133 per request on tiny pages): US$0.016 per request p50, 0.024 p90 on Ironbark's larger pages; about 2.2 requests per needed page + 3. These are **assumptions the pilot replaces**.

| phase | trials | expected (p50) | hard cap | gate |
|---|---|---|---|---|
| 0. offline work, mock runs, tests | — | US$0 | — | none (this PR) |
| 1. baseline pilot (first 8 trials) | 8 | 1.44 | **1.90** | owner approves the exact manifest hash |
| checkpoint: pilot review | — | 0 | — | owner approves measured rate and the (possibly trimmed) main plan |
| 2. baseline main | 46 (fewer if trimmed) | 7.59 | **9.90** | owner approves the exact manifest hash |
| 3. investigator (investigation partition only) | ~8 requests | ~0.04–0.3 (EXP-B's investigator cost US$0.037 on a tiny site) | **0.80** | owner approves; *driver not in this PR* |
| 4. controlled variant tests | after baseline | whatever remains | **4.90 minimum** (up to ~7.7 if the baseline spends only its expected US$9.0) | owner approves each variant's manifest |
| reserve | — | — | **2.50**, never allocated | only by a new owner decision |
| **ceiling** | | | **20.00** | Experiment 2's own ledger refuses beyond it |

* **Durable accounting:** a separate run directory and ledger (`investigations/<run>/spend/ledger.jsonl`, ceiling 20.0), fsync'd, append-only; the existing reserve-before-send gate reserves a conservative upper bound **before** every request and replaces it with the calculated actual only when the provider reports usage; interrupted, timed-out or usage-less requests stay counted in full, also across restarts. EXP-B's ledger and the programme ledger are never opened.
* **Limits:** per request US$0.05, per trial US$0.75, per phase as above (over a phase cap the gate refuses and the phase stops — no top-up), retries 0, ≤ 30 requests per trial.
* **Stopping conditions (listed in every manifest):** any void trial (provider, budget, infrastructure, fidelity guard); a refused request or breached cap; a bound violation (closes the gate until reviewed); an integrity mismatch (snapshot/plan/task/criteria hash), which quarantines the trial; **measured cost per request above 1.5× the plan at the pilot review → re-plan, do not run as approved**. No silent retries.
* **Approval gates:** `exp2 run` stops at `awaiting_approval` with the exact manifest SHA-256; `readiness investigate approve <run> --stage <s> --sha256 <h> --note …` records it; changing any manifest field changes the hash and voids the approval; `--allow-model-calls` is required in addition; without both nothing is sent.
* **Pilot review:** replaces the assumed rate with the measured one, drops the lowest-priority trials (second repeats first, then the last tasks) if the main phase would not fit its cap, and halts if the rate is 1.5× the assumption.

## 6. The four candidate variants: nothing assumed, the baseline decides
Which variant deserves a controlled test is decided by rule **`exp2-eligibility-v1`** from the baseline's **investigation-partition** tasks sensitive to it: a variant is eligible only if at least 3 such tasks have usable trials and at least 2 of them (and ≥ 35 %) are *troubled* (not passed evidence-backed on average, or ≥ 1.5× the requests a task needs: pages + 2). Otherwise it is **not tested** and the null baseline is reported. More than 25 % void trials → uninterpretable.

| variant | sensitive baseline tasks (inv. + holdout) | what the baseline must show to justify a test |
|---|---|---|
| discoverability | 7 | wrong or slow product choice on need and synonym tasks |
| availability | 11 | slow or wrong multi-item date answers |
| cost | 17 | arithmetic or rule errors, or many pages read for totals |
| compatibility | 8 | wrong or slow accessory and kit answers |

**If eligible**, the controlled test is pre-registered as **`exp2-compare-v1`** (the rules and their SHA-256 are printed by `readiness exp2 rules` and written into every manifest): variant arm vs a **contemporaneous** control arm on the same tasks (the EXP-B lesson: compare against a fresh control, not only an earlier baseline), at least **6 affected tasks** (both partitions), K ≥ 2 per cell; improvement requires a paired sign-flip p ≤ 0.10 with an evidence-backed-pass gain ≥ +0.15 or a ≥ 25 % cut in requests without lost passes; **drift check** (the contemporaneous control must stay within 25 % of the baseline's requests or no improvement is claimed); **negative controls** (≥ 3 tasks the variant does not address must not move > 25 % or lose passes, else *uninterpretable*); **holdout guard** (an improvement is withdrawn if the held-out tasks get worse). Allowed claim: an association measured under control on this site, these tasks, this agent and model. Not allowed: "proved", general improvement, or a claim about other sites.
**Cost of one variant test:** about 18 trials (6 affected tasks × variant K = 2 + control K = 1 + the shared baseline repeats) ≈ **US$3.0**; 24 trials (control K = 2) ≈ US$4.0. The remaining budget therefore supports roughly **one to two** variants; the order is by baseline evidence, not by our expectations.

## 7. Investigator phase (design only here)
After the baseline the existing investigator would see **investigation-partition** trials only (never holdout), propose labelled hypotheses, and any promoted finding is verified deterministically as in EXP-B. Its recommended change must map to a variant (or a new one, which would need its own approval). Not implemented in this PR: the investigator stage currently reads the EXP-B criteria format, so an Ironbark adapter is the next piece of work.

## 8. Approval requests (nothing proceeds without them)
1. **Review and approve this protocol and the plan** (`plan_sha256 115dce98…`) or ask for changes to quotas, repeats or the pilot size.
2. **Phase 1 (pilot) manifest approval** before any paid call: ≤ 8 trials, hard cap US$1.90, `--allow-model-calls`.
3. **Pilot review** approval, then **Phase 2 (main baseline)** manifest approval, hard cap ≤ US$9.90.
4. Decision on **who/what implements the investigator adapter and variant-test driver** (next PR) before phase 3 and 4.
5. Confirm the **US$2.50 reserve** and the **US$20 ceiling** as Experiment 2's own, separate from the programme ledger (which this PR does not touch).

## 9. Limitations
Single site, single agent profile and model (`suite-v2-compat1`, `muse-spark-1.3`); sequential trials (time drift mitigated by contemporaneous controls, not eliminated); a "today" fixed at 2 Nov 2026 so dates are reproducible; trial counts are small and cost-limited, so results will be descriptive with wide uncertainty; difficulty labels are design estimates; the site is fictional and illustrated rather than photographed; the planning cost rate is an assumption until the pilot measures it.
