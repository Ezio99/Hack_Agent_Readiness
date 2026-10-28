# Agent Readiness — Hackathon Pitch, Positioning & Demo Plan

**Status:** Working product pitch and hackathon execution priorities; not a claim of market validation or approval for new paid experiments.
**Updated:** 2026-10-28
**Repository:** `Ezio99/Hack_Agent_Readiness`
**Evidence baseline:** Tasks 003–007 integrated into `main` via squash merge `91933a2`; Task 007 final report: [Report 007](../reports/007-availability-placement-pilot.md).
**Rules reference:** Participant-supplied hackathon screenshots (28 October 2026); see the separate project-source reference `Meta_Global_Hackathon_2026_Reference.md`. The screenshots show **Impact 30%, Meta AI 25%, Technical Depth 20%, Demo 25%**.

## Executive pitch

> **Agent Readiness helps website developers see how AI agents actually navigate their sites, where they waste effort or fail, and what changes could make the site easier for agents to use.**

**Problem:** The web was designed primarily for humans. As people delegate more product discovery and shopping research to AI agents, retailers need evidence about whether agents can find, interpret and verify product information. Static page audits cannot directly measure the behavior of an actual browsing agent.

**Solution:** Run controlled shopping tasks with a **Meta Muse Spark-powered reference agent**, capture its observations and actions, independently evaluate correctness, quantify navigation/compute friction, and explain actionable changes through trace-backed diagnostics.

**Hackathon demo positioning:** A **developer diagnostic tool** with a longer-term vision of reusable infrastructure for the agentic web. The reference shopping agent is the measurement instrument, **not** the product. The synthetic storefront is a controlled test environment, **not** the product.

**One-sentence demo hook:** *Two websites show the same products, but one makes the AI agent work harder. Agent Readiness shows you exactly where—and why.*

## Why this matters — hypothesis, not established market fact

1. More capable personal agents may take on product research and comparison.
2. Website structure and information placement may affect what agents can verify and how much compute/navigation they require.
3. Website owners may benefit from measurable, actionable evidence rather than a generic “AI-friendly” label.
4. Longer-term adoption, commercial value and transfer to real websites remain **unproven**; agents may instead use feeds, APIs, marketplaces or search intermediaries.

**Audience:** E-commerce teams, website developers, QA teams and eventually agent-platform developers. Initial buyer/user is the website developer seeking a diagnostic report, not a shopper looking for a purchasing assistant.

## Fit to the hackathon

**Likely theme fit:** *Push the Frontier* — using Meta models to create a new diagnostic capability for software/web interaction. This is a project positioning recommendation, not a verified organizer ruling.

**Stage One gate:** Reasonable fit to a problem statement and meaningful use of Meta Model API and/or Meta open-weight models. Our Muse Spark-powered browser agent must be clearly shown as an essential component, not a superficial integration.

| Rubric | Weight | Our evidence / next priority |
|---|---:|---|
| **Impact** | **30%** | Translate trace evidence into developer-facing decisions and concrete website improvements. Do not overclaim real-world validation. |
| **Use of Meta AI Tooling** | **25%** | Muse Spark is the browsing measurement instrument. Show real model decisions, observations, actions, and model/tool interaction limitations. |
| **Technical Depth & Execution** | **20%** | Controlled A/B experiment, independent evaluator, oracle minimum paths, protocol safeguards, trace provenance and reproducible analysis. |
| **Demo** | **25%** | Build a working hybrid dashboard with recorded trace replay and clear A/B comparisons, optimized for a three-minute video. |

**Key constraints:** Public repository; maximum four participants; demo must identify only hackathon-built work; disclose any prior codebase/material; three-minute demo video; repository, video and live product accessible; everyone who contributed listed. Screenshot deadline: **November 4, 2026, 9 PM EST** (if literal UTC−5: **November 5, 1 PM AEDT**). Verify timezone and portal requirements before submission.

## What has actually been built (as of 28 October)

- Controlled synthetic e-commerce storefront, task fixtures, reference Browser Use agent and independent evaluator.
- Meta Muse Spark integration with bounded protocol compatibility recovery, model-call cost and step safeguards.
- Real end-to-end shopping runs and controlled experiments on link presentation (Task 006) and stock-availability placement (Task 007).
- Reproducible experiment schedule, raw run artifacts preserved locally, reconciled analysis and verification scripts.
- **Task 007:** 30 runs across five scopes, three per arm per scope. **29/30 independently evaluated PASS** (A 15/15; B 14/15); all passes evidence-backed. A displays stock availability on listing cards; B displays it only on product detail pages.
- **Observed means:** A 4.67 model requests and US$0.0621 calculated cost/run; B 7.47 requests and US$0.0974/run. Estimated prompt tokens per request stay around 9.4k–10.3k; costs scale mostly with request count.
- **Failure mechanism:** Three repeated `find_elements` loops occurred because hrefs returned by the tool were not retained in model-visible history; one run exhausted the step budget and returned an incorrect, insufficiently verified answer. Distinguish website friction, agent inefficiency, and **agent–tool interface failure**.

**Evidence caveat:** This is **exploratory**, not generalizable: one synthetic 20-product storefront, one model and framework, three runs per cell, near-ceiling success. We have not shown a universal readiness score, real-world ROI, or behavior of other agents/sites. Task 006's four successful runs were stopped early for a ceiling effect; do not imply equivalence.

**Provenance:** The earlier `Ezio99/Agent_Readiness` project predates this event and contributed planning/design context. The hackathon repo's [HACKATHON-START](../reports/HACKATHON-START.md) records the transfer of historical documents, not executable implementation. Confirm the official start timestamp and disclose pre-event materials and hackathon-built features accurately. Do not describe prior work as newly built.

## The product experience to build next

**MVP: one polished hybrid diagnostic dashboard using real Task 007 evidence.** Recorded playback is explicitly labeled **recorded**, not presented as a live inference session.

### Screen 1 — Diagnostic overview

- Task success (including independent evaluator status, not merely `agent_done`).
- Model requests, navigation/detail visits, latency, calculated token costs and within-arm variation.
- A/B comparison across the five task scopes, with clear sample sizes and limitations.
- Plain-language finding: hiding availability on detail pages generally increased required navigation and model requests in this controlled task.

### Screen 2 — Side-by-side A/B comparison

- Display the two controlled storefront variants and highlight exactly what changed: stock visibility on listing cards versus detail pages.
- Select a representative successful A run and B run for the same scope; show measured action differences.
- Distinguish **oracle-required navigation** from extra revisits and tool failures. Do not claim every observed difference is caused by website design.

### Screen 3 — Recorded agent trace replay

- Step-by-step timeline of model observation, action, page state, model requests, tokens/cost and evaluator evidence.
- Include a representative clean run and **run 27** as a failure case.
- In run 27, the tool returned href attributes but model-visible history reduced the response to a count; repeated requests exhausted the budget. This is an **agent–tool interface issue**, not proof that the storefront itself was defective.
- Make trace provenance and replay/live distinction visible.

### Developer-facing recommendation

> **Finding:** Stock availability is only visible after opening a product page.  
> **Evidence:** In stock-sensitive maximum-price tasks, the detail-only arm required additional candidate visits and averaged more model requests.  
> **Suggested change:** Surface stock availability on listing cards where appropriate.  
> **Confidence and scope:** Controlled synthetic test with one agent; validate on the developer's own site before inferring production benefit.

Do not create an unsupported composite “readiness score.” Prefer a small set of interpretable measurements with links to supporting runs.

## Three-minute demo storyboard (proposed)

| Time | Content | What the viewer sees |
|---|---|---|
| **0:00–0:20** | Problem: human-readable sites may be inefficient for AI agents | Same products, different information placement |
| **0:20–1:05** | Product and Meta's central role | Working dashboard, Muse Spark agent and independent evaluator |
| **1:05–2:15** | Actual experimental evidence | A/B storefront comparison, representative recorded traces, measured requests and cost; briefly show run 27's loop |
| **2:15–2:45** | Actionable diagnostic | Trace-backed finding and recommendation for website developers |
| **2:45–3:00** | Scope and vision | Honest limitation, hackathon-built contributions, future reusable agent-readiness diagnostics |

**Video principles:** Show actual working software and code built during the event; label replays; avoid unsupported performance generalizations; explicitly distinguish pre-existing planning from newly implemented code. The video is a primary judging artifact alongside the code and live product.

## Prioritized implementation sequence

1. **Contribution/provenance audit and final rules check:** document what existed before the event, what was newly built, and verify exact submission timezone and public-link requirements.
2. **Working diagnostic overview:** load the committed reconciled Task 007 dataset and show real metrics, not placeholders.
3. **A/B storefront view and recorded trace replay:** prioritize legible, reliable playback and a strong failure diagnosis.
4. **Developer recommendation and evidence drill-down:** every diagnosis links to actual run evidence.
5. **Three-minute video, public repo and live-demo access:** rehearse and submit early.

**Out of scope until explicitly approved:** new paid experiments, multi-model benchmarks, autonomous checkout, large synthetic-store expansion, universal score, public registry/API, unsupported external-site claims, or changing the frozen experimental data. All billable model calls require explicit authorization. Participant budget note as of 28 October: **A$2.89 spent of A$30** (separate from the experiment report's calculated USD costs).

## Open questions after the demo MVP

- Can this diagnostic approach generalize to independently operated commercial websites?
- Which website properties most strongly affect grounded recommendation inclusion?
- Can we separate agent-model behavior from site-specific causes across different agents and tools?
- What evidence and confidence thresholds would justify a product-facing readiness score?
- Could a shared registry/API eventually reduce duplicated testing?

**Current priority:** Build a convincing, evidence-backed **developer tool and three-minute demo**, not another experiment. The longer-term agentic-web infrastructure thesis is the closing vision, not a claim that the present prototype already achieves it.
