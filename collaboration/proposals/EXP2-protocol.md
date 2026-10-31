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
| **Evidence rule redesigned** (this revision): the first rule required particular pages and, with the scripted agent, was both too strict (required the product page where the calendar holds the answer) and too loose (accepted a correct guess) | replaced by fact-based, page-agnostic sufficiency (section 3) |
| **Evidence rule v2 and verification on the model-visible views** (after pilot 1) | pilot 1 judged a sufficient observation insufficient and a right answer wrong, and the review found tasks answerable from the home page; the verification had checked needles against the HTML's plain text, not against what the model is shown | section 3a |
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

**Independent verification** (every candidate, `verify.py`): (1) the truth computed from the source data must equal the truth **recomputed from the rendered control pages** (parsed text, never `data.py`); (2) no ties, no empty or oversized sets, dates inside the booking window; (3) every evidence page exists and is reachable within 4 clicks; (4) the question does not contain the answer or an internal catalogue code, and does not name pages ("the Kits page"); (5) the grader accepts the canonical answer, rejects wrong answers and rejects a hedge that offers the right and a wrong answer; (6) every fact has a route satisfiable on **every arm** of the site, **checked against the text the model is actually shown** (section 3a), not the HTML's plain text; (7) **not a giveaway:** the facts are not all shown on the start page (any scroll position) on any arm; (8) no duplicate fingerprint, question or (family, template, truth, visit-set) combination.
**Result:** 388 generated, **318 accepted, 70 rejected** — 50 as trivial repeats, **12 answerable from the start page alone** (discovery tasks whose answer item's description is on the home page), 7 empty answer sets, 1 as ambiguous (two Landscaping items tie on the highest deposit). Answer kinds: money, number, integer, date, yes/no, choice, product, product set, accessory. Grading is exact on a normalised form (case, punctuation and the gap between a number and its unit are ignored: `18V` = `18 V`; the whole name must still match, rule `exp2-names-v2`); hedges, ranges and several values are never an answer.
**What the agent receives:** the question text (with a fixed answer-format sentence) and a one-field answer schema; nothing else. Truth, expected text and the evidence facts live only in the run's private criteria (never in the public plan, never shown to the investigator). A test scans the plan for leaks.

### Three separate measurements per trial (revised evidence rule)
| measurement | question it answers | how it is computed | never affected by |
|---|---|---|---|
| **correctness** | is the answer right? | the typed grader against the independently derived truth | evidence, effort |
| **evidence sufficiency** | was the model *shown* what the answer depends on? | `exp2/evidence.py`, over the observations the trial stored (what the model saw) | which page, how many steps, correctness |
| **browsing efficiency** | how much effort did it take? | model requests, page views, distinct pages, and requests ÷ (pages the task needs + 2) | correctness, evidence |

The **primary outcome** is the *supported pass*: correct **and** evidence sufficient (a correct answer the model could not have derived from what it was shown does not count, which guards against lucky guesses on yes/no and choice tasks). Raw correctness, sufficiency among correct answers, and the efficiency numbers are reported alongside it, never folded into it.
**No particular page is required.** Each task lists the *facts* its answer depends on; each fact lists every *route* by which the site can show it (the calendar, the product page, a listing card, the terms page, or a panel a candidate variant adds). A fact is satisfied by ANY of its routes; a route needs all its clauses; a clause is a decisive string (a rate, a rule, a dated cell) seen on a page that is about the right item (the model is on the item's own URL, or its code is shown, or on a listing the string follows the item's name within one card). Matching is on a canonical token form (rule `exp2-evidence-v2`, section 3a): layout, punctuation and the model-view element markers are ignored. Examples: a total-cost task is evidenced on the control by the product page *plus* the terms page, and on the cost variant by the product page alone (it shows the total); a dated-availability task by the calendar page *or* by the "Dates at a glance" panel of the availability variant, but **not** by the control's product page alone (which only says whether the item is free *today*).
**Consistent across arms:** the rule and the fact lists are identical for every arm. A variant that displays a fact somewhere new only supplies another route. Verification proves, for **every arm** (control, each variant, the combined build), that every fact has at least one route satisfiable from the rendered pages, so no task is winnable by evidence in one arm and not in another; tampering with a needle makes the pool reject the task. The pre-registered comparison additionally audits evidence symmetry: if the share of *correct answers without sufficient evidence* differs between the arms by more than 15 points, no improvement is claimed.
**Scripted (mock) agents** still need a route to walk; they take it from a `visit` hint that is used **only in mock mode**. Live trials carry no page requirement at all.

### 3a. Pilot 1 and the corrections (rules `exp2-evidence-v2`, `exp2-names-v2`)
Pilot 1 (8 trials, run `exp2-pilot-1`, manifest `29df5a28…`, US$1.1415 against a US$1.90 cap) ran without infrastructure failure. As graded then: 7 of 8 correct, 7 of 8 evidence-sufficient, **6 supported passes**. Two outcomes were wrong:
* **`ib-d9260f2d9a` (compatibility), correct but "insufficient".** The model had seen the hammer's `30 mm hex` chuck and a listing card for a chisel set "for 30 mm hex demolition hammers". Why the first check could not see it: (1) the criteria were verified against `get_text()` of the HTML, but the model is shown the browser serializer's text, which has element markers between a label and its value (`Chuck`, `*[934]<td />`, `30 mm hex`); (2) even the live matcher removed only `[n]<…/>`, leaving the leading `*` that marks newly appeared elements; (3) clauses demanded a printed `Product code IB-…`, which listing cards do not show; (4) only 6 of 330 tasks were ever walked through the real browser, none from the product-to-accessory family.
* **`ib-e3d8f94923` (discovery), right item, graded wrong.** The answer was `Cordless Drill Driver Kit 18V`; the site shows `18 V`.

Re-verification against the model-visible views then found two more defects, both invisible to the plain-text check: the model sees only the part of a page **near the viewport**, so facts lower on a page (the `cost` variant's specification table, the lower kits) reach it only after scrolling; and 12 discovery tasks were answerable from the home page alone.

**What changed (all in code, tested, and applied to the pilot only as a separate versioned re-analysis):**
| | before | after |
|---|---|---|
| verification text | HTML `get_text()` | `llm_representation()` of the production browser session, every page of every arm, captured at every scroll position (`exp2/modelview.py`; committed as `model-views.json.gz`, HTML-hash guarded, equal to a fresh capture in the browser tests) |
| evidence matching | substring, markers partly removed, literal product codes | canonical tokens (layout, markers, punctuation, thousands separators ignored; digit-to-unit spacing normalised); an item is identified by the URL the model is on, a printed code, or a listing card whose text follows its name (window 260 characters; kits 450); a name alone proves nothing; views of one path are merged, a card window never spans two views |
| alternative routes | one accessory-fit route | accessory fit: spec row **or** chuck named in prose × accessory page **or** listing card that states the fit (only where the card really does; asserted) |
| answer names | `18V` ≠ `18 V` | tolerated; a different number, unit or word is still wrong; every catalogue name keeps a distinct key (tested) |
| start-page rule | untested outside six tasks | a verification rule for every candidate on every arm |
| frozen v1 | — | `exp2/evidence_v1.py` reproduces the original verdicts from the stored artifacts; never used for new work |

**Pilot 1 under the corrected rules** (`pilot-1-corrected-analysis-v2.json`, next to the unchanged originals): 8 of 8 correct, 8 of 8 evidence-sufficient, **8 supported passes**; the two changed trials are the two above. The original run directory is byte-identical (409 files, digest `d05f0031…`, checked before and after). Cases still worth a human look: `ib-e3d8f94923` is correct only through unit-spacing normalisation (the question says "exact name as shown"); `ib-d9260f2d9a` is sufficient only through the listing-card route (a legitimate alternative, 3 requests). **Not changed:** no trial was re-run, no truth is stored in the report, the ledger and EXP-B are untouched.

**Revised plan.** Removing the 12 start-page-answerable candidates replaces 3 of the 40 planned tasks (all discovery, none run) and moves one unrun task from investigation to holdout; counts, costs and caps are unchanged. The eight executed trials are pinned first, unchanged (`study.EXECUTED_PILOT`). A run adopts the revised plan and corrected criteria only through `readiness exp2 amend <run>`, which writes **new** write-once artifacts (`study-plan-v2`, `criteria-v2`, `amendment-v2`) beside the frozen ones, refuses unless the executed trials, the snapshot and every kept task's truth are unchanged, and is required before a main-phase manifest can be produced.

### Deterministic benchmark generation versus autonomous task discovery
The Ironbark generator is a **deterministic benchmark task generator**: it derives tasks from a site whose source-of-truth data we own, so each answer can be verified independently by recomputation from the rendered pages. That is its job — to give the experiments **independent ground truth**. It is **not the product architecture** and it is **not replaced** by the future work below.
**Future requirement (roadmap, not in this PR):** Agent Readiness must eventually use an LLM to **autonomously explore an unfamiliar website, understand its business workflows and generate realistic, independently verifiable customer tasks**. The benchmark is how we will *measure* that agent: run it on Ironbark without access to the source data, and compare its tasks with the verified families (coverage, invented-but-valid tasks, tasks that fail verification). On an unfamiliar site every discovered task still needs an independent verification path; a task cannot be graded by the agent that proposed it. See [docs/PRODUCT_ROADMAP.md](../../docs/PRODUCT_ROADMAP.md#autonomous-task-discovery-future-architecture-requirement--not-implemented).

## 4. Proposed baseline study
Control site only. 40 tasks, **48 trials**, fixed order (`plan_sha256 f7d7d71f…` in `study-plan.json`; the pilot was run from `study-plan-v1.json`, `4f7056bf…`; inside a run the hash also binds the snapshot: frozen `529f7344…`, revised `09ae360a…`). Difficulty is a *design estimate* from the number of pages a task needs on the control site (easy ≤ 2, medium 3–4, hard ≥ 5); the baseline will measure real difficulty.

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
* **Repeats:** every task once (k = 1); **8 tasks twice** (4 investigation + 4 holdout, 7 families) for an early run-to-run estimate. (Reduced from 14: the variant test's own contemporaneous control runs every affected task twice and is the main noise estimate; see section 6.)
* **Order:** repeat 1 of every task, interleaved by family, then the 8 repeats. The first 8 trials (the pilot) cover 8 different families.
* **Negative controls for every variant:** every task not sensitive to it (at least 23 of 40 for each) plus the 5 insensitive ones overall.
* **Per-task limits:** 10–27 model requests, 10–27 steps, 600 s, scaled to the pages a task needs.

## 5. Cost model, allocation and gates (hard ceiling US$20 for Experiment 2)
All figures are **calculated at published prices (US$1.25 / 4.25 per million input / output tokens), not billed**. Assumption (from EXP-B's US$0.0115–0.0133 per request on tiny pages): US$0.016 per request p50, 0.024 p90 on Ironbark's larger pages; about 2.2 requests per needed page + 3. These are **assumptions the pilot replaces**.

| phase | trials | expected (p50) | hard cap | gate |
|---|---|---|---|---|
| 0. offline work, mock runs, tests | — | US$0 | — | none (this PR) |
| 1. baseline pilot (first 8 trials) | 8 | 1.44 | **1.90** | owner approves the exact manifest hash |
| checkpoint: pilot review | — | 0 | — | owner approves the measured rate and the (possibly trimmed) main plan |
| 2. baseline main | 40 (fewer if trimmed) | 6.74 | **8.80** | owner approves the exact manifest hash |
| 3. investigator (investigation partition only) | ~8 requests | ~0.04–0.3 (EXP-B's investigator cost US$0.037 on a tiny site) | **0.50** | owner approves; *driver not in this PR* |
| 4. **one** controlled variant test | 30 | **5.03–6.58** depending on the variant (cap = that × 1.3, never above what remains) | what remains: **6.30** if every earlier phase spends its cap, ≈ 9 if the baseline spends only its expected US$8.2 | owner approves the exact manifest; *driver not in this PR* |
| reserve | — | — | **2.50**, never allocated | only by a new owner decision |
| **ceiling** | | | **20.00** | Experiment 2's own ledger refuses beyond it |

**Material changes in this revision (US$20 ceiling and US$2.50 reserve unchanged; pilot unchanged at 8 trials):** (1) the baseline's second repeats fall from 14 to 8 (54 → 48 trials; main phase 46 → 40 trials, cap 9.90 → 8.80); (2) the investigator cap falls from 0.80 to 0.50; (3) a controlled variant test now costs **US$5.0–6.6 (30 trials), not the US$3–4 previously quoted**, because the pre-registered rule needs K ≥ 2 per cell in **both** arms; (4) the budget therefore supports **one** variant test, not "one to two" — a second would need roughly another US$5–6.5 and a new owner decision (for example from the reserve).
**After pilot 1 (measured):** the pilot cost **US$1.1415** (81 requests, US$0.01435 per request, 0.90× the planning rate; no re-plan trigger). At that rate the pilot review would trim nothing and propose the 40-trial main phase at a **US$7.90 cap** (expected US$6.05) instead of the planned US$8.80; that is a planning figure only. Ceiling US$20 and reserve US$2.50 are unchanged; one variant test (US$5.03–6.58) still fits.

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

**If eligible**, the controlled test is pre-registered as **`exp2-compare-v1`** (printed by `readiness exp2 rules`, hashed into every manifest) and **sized in code** by `study.variant_test_plan` so that the rule, the plan and the budget cannot disagree:
* **6 affected tasks** (3 investigation + 3 holdout where available), **K = 2 trials per task in EACH arm** (variant and a **contemporaneous control**, run in the same session with the arms alternating which goes first), plus **3 negative-control tasks, K = 1 per arm**.
* Trial count: 6 × 2 × 2 + 3 × 1 × 2 = **30 trials**; expected cost **US$5.03 (compatibility), 5.24 (discoverability), 5.31 (cost), 6.58 (availability)**; see `collaboration/experiments/EXP2/study-plan.json` → `variant_tests`.
* The comparison **excludes and lists** any affected task with fewer than 2 non-void trials in an arm (and any negative control with fewer than 1), so a cheaper design cannot slip in under the same rule.
* Verdict rules: paired sign-flip p ≤ 0.10 with a supported-pass gain ≥ +0.15, or a ≥ 25 % cut in requests without lost passes; **drift** (the contemporaneous control must stay within 25 % of the baseline's requests); **negative controls** (≥ 3 pairs; > 1/3 moving beyond 25 % or losing passes → *uninterpretable*); **evidence symmetry** (see section 3); **holdout guard**. Allowed claim: an association measured under control on this site, these tasks, this agent and model; not "proved", not a general improvement.
* The baseline's repeated tasks and the contemporaneous control together give the noise estimate EXP-B lacked.

## 7. Investigator phase (design only here)
After the baseline the existing investigator would see **investigation-partition** trials only (never holdout), propose labelled hypotheses, and any promoted finding is verified deterministically as in EXP-B. Its recommended change must map to a variant (or a new one, which would need its own approval). Not implemented in this PR: the investigator stage currently reads the EXP-B criteria format, so an Ironbark adapter is the next piece of work.

## 8. Approval requests (nothing proceeds without them)
1. **Review the corrections** (section 3a): evidence rule v2, name rule v2, the start-page rule, the revised plan and the corrected analysis of pilot 1.
2. ~~Phase 1 (pilot)~~ — **done** (manifest `29df5a28…`, 8 trials, US$1.1415).
3. **Pilot review** (a free checkpoint; its manifest, after `amend`, is `439aa69a…`), then **Phase 2 (main baseline)**: 40 trials, proposed cap **US$7.90** (expected US$6.05 at the measured US$0.01435 per request; planning cap was US$8.80), manifest `17c446aa…`. **Not authorized.**
4. Decide who/what builds the **investigator adapter and the variant-test driver** (next PR) before phases 3 and 4.
5. Confirm the **US$2.50 reserve** and the **US$20 ceiling** as Experiment 2's own, separate from the programme ledger (not touched here), and accept that **one** variant test is budgeted.

## 9. Limitations
Single site, single agent profile and model (`suite-v2-compat1`, `muse-spark-1.3`); sequential trials (time drift mitigated by contemporaneous controls, not eliminated); a "today" fixed at 2 Nov 2026 so dates are reproducible; trial counts are small and cost-limited, so results will be descriptive with wide uncertainty; difficulty labels are design estimates; the site is fictional and illustrated rather than photographed; the planning cost rate is an assumption until the pilot measures it.
