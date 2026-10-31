# Agent Readiness — Product Definition & Implementation Roadmap

**Decision date:** 2026-10-28. **Status:** Accepted product direction; implementation subject to task-specific gates.

## Positioning

**Agent Readiness: Understand how AI agents experience your website—and what to improve.**

As agents increasingly perform online tasks, owners need evidence of whether agents can discover, understand and interact with their digital services. Existing websites vary in browser, DOM, accessibility, structured data and API affordances; the direction and scale of resulting friction must be *measured*, not presumed.

**Customer:** Website developers, e-commerce engineering teams, digital experience owners.
**Product subject:** The website/digital service, not a leaderboard of agent models.
**Measurement instrument:** A fixed, versioned reference agent and task suite.
**Core loop:** Configure website + tasks → execute authorized scans → independently verify outcomes → inspect evidence and attribute friction → recommend a testable change → compare with a rescanned version.

Browser-based e-commerce is the **first supported channel/domain**, not the whole vision. Structured APIs, feeds and hybrid interactions may be preferable for some tasks; we must explicitly communicate that browser-only results do not establish general agent compatibility.

## What a useful assessment reports

**P0:** independent task success and answer accuracy; navigation actions/requests; time; run limits and failures; trace evidence; classification of website vs agent vs agent-tool vs infrastructure causes; actionable, evidence-linked proposed fixes (clearly distinguish observed facts, hypotheses and validated changes).
**P1:** calculated model cost, repeatability/variation, baseline and before/after comparisons, extraction accuracy, unnecessary effort under an explicit reference path, severity/evidence confidence, task suites and visual journey.
**P2:** API/structured-interface coverage, cross-agent results, continuous regression checks, production analytics and long-term monitoring.

Avoid a single universal readiness score, speculative revenue impact, and claims that the reference agent represents all agents. Report model/tool versions, task scope, sample size, evidence limitations and confidence.

## Reference environment: realistic electronics storefront

Build **one configurable electronics retailer**, not several unrelated toy websites. Use synthetic but coherent product data and realistic UX: home/category navigation, search, listing/filter/sort, product detail, specs, inventory, shipping/returns information, cart and safe checkout simulation. Product data and evaluator truth must be deterministic and independent of the agent's accessible observations; ensure nontrivial tasks require meaningful interactions. Never collect real payment information or place real orders.

Use independently switchable, controlled design factors while holding inventory/prices/task wording constant:
- Availability visible in listings vs only detail pages (existing Task 007 baseline).
- Structured specifications vs fragmented content.
- Semantic/descriptive controls vs ambiguous interactions.
- Clear policy and delivery access vs harder-to-find placement.
- Browser-accessible structured product data, and later a documented read-only API.

Do not assume any variant is automatically better; validate through measured scans. Keep earlier Task 007 fixture and data unchanged for reproducibility; build a new versioned environment rather than silently mutating historical experiment conditions.

## Curated, independently verifiable task suite

Tasks are versioned records with objective, allowed start state, website/capability, constraints, evaluator/oracle, evidence requirements, limits and task-specific success semantics. Keep the contract domain-extensible (D006). Initially use curated deterministic tasks; automatic generation is a future capability, and generated candidates require independent feasibility validation.

| ID | Task | Initial priority | Evaluator concept |
|---|---|---|---|
| T1 | Discover in-stock ANC headphones below a budget | P0 | Complete eligible set / valid choice, price and availability |
| T2 | Compare two laptops' RAM and advertised battery life | P0 | Correct attributes and comparison, evidence for both |
| T3 | Cheapest in-stock monitor meeting size, USB-C and refresh-rate constraints | P0 | Verify all constraints and global minimum over eligible inventory |
| T4 | Find return-policy and delivery information for a selected product | P0 | Correct policy/availability claims with supporting pages |
| T5 | Add two products to a simulated cart and confirm subtotal | P1 | Verify actual cart state, quantities and total; no checkout |
| T6 | Select a compatible charging accessory for a named laptop | P1 | Match compatibility relation and evidence |
| T7 | Recover from out-of-stock product with eligible alternative | P1 | Verify stock and explicit substitution criteria |
| T8 | Discover/use documented structured interface for product information | P2 | Independently verify API/feed path and answer; separate channel |

Examples are design targets, not guaranteed feasible fixtures. Before implementation freeze exact product inventory, prompts, feasible unique/acceptable answers, and grading; do not leak answer keys into agent tools.

## Delivery roadmap

1. **Task 010 — Product foundations (P0):** design and implement versioned realistic storefront, domain-extensible task contract, P0 task fixtures and independent evaluators. Credential-free; mock/browser smoke only. Preserve old experiment.
2. **Task 011 — Protected scanner (P0):** integrate new storefront/task suite into public configuration, invitation-only backend, bounded Meta runner and evidence-backed reports. Implement and test locally with mock provider before paid/deployment approvals.
3. **Task 012 — Realistic agent experiments (P0):** after Task 011 agent integration and mock validation, prepare a preregistered controlled pilot on electronics-v1 (T1–T4), followed only with separate paid-call approval by focused replicated comparisons of stock visibility and specification presentation. Track independently graded success, partial accuracy, actions, latency, calculated cost, evidence, failure attribution and actionable issue yield. [Task 012 spec](../collaboration/tasks/012-realistic-agent-experiments.md).\n4. **Diagnostic layer (P0):** evidence-linked issue taxonomy, attribution and suggested fixes, with uncertainty labels.
5. **Controlled remediation comparison (P1):** rerun fixed tasks across isolated site factors and compare verified changes.
6. **Structured interface channel (P1 exploration, P2 full evaluation):** API/feeds and hybrid task pathways; clearly disclose what browser scans do not cover.
7. **Later (P2):** generated tasks with feasibility checks, more agents/domains, CI and analytics integrations.

**Task 011 is not cancelled**, but its previously authored narrow scanner scope is sequenced after Task 010 and must be reconciled with these contracts before implementation. No broad implementation, paid inference, paid hosting, merge, or public deployment is automatically authorized by this roadmap.

## Autonomous task discovery (future architecture requirement — not implemented)

**Requirement.** Agent Readiness must eventually use an LLM to **autonomously explore an unfamiliar website, understand its business workflows, and generate realistic, independently verifiable customer tasks** for it. A site owner cannot be expected to write a task list, and a fixed catalogue of task templates does not generalise across businesses.

**What exists today is a benchmark, not the product architecture.** The Experiment-2 generator for the fictional Ironbark Hire Co. site (`src/agent_readiness/exp2/`) is a *deterministic benchmark task generator*: it derives eight task families from a site whose source-of-truth data we own, and every answer is verified by recomputing it from the rendered pages. It exists to give the experiments **independent ground truth** — the one thing a discovery agent cannot give itself. It is **not replaced** by the autonomous agent and stays as the reference oracle.

**How the two relate (design intent).**
1. The deterministic Ironbark pool is the *calibration set*: run the discovery agent on Ironbark without access to `data.py` and measure which of our verified task families it rediscovers, which it invents that we did not, and which of its tasks fail verification (wrong, ambiguous, leaking, ungradeable). Its quality is measured against known truth before it is trusted on an unfamiliar site.
2. For an unfamiliar site there is no source-of-truth file, so every discovered task still needs an **independent verification path**: recomputation from the rendered pages by a separate mechanism (as `verify.py` does), a second model plus deterministic checks, or a human spot-check; unverifiable tasks are rejected, never graded by the agent that proposed them.
3. The same rules apply as for the benchmark: no answer or privileged data reaches the agent under test, ambiguity and leaks are rejected, duplicates are removed, the evidence and efficiency measurements stay separate from correctness, and holdout tasks are kept from any investigator.

**Out of scope until the experiment infrastructure and the pilot are finished.** No design for this is frozen; it needs its own approved plan, budget and tests. This entry records the requirement so that the deterministic generator is not mistaken for the end state.

## Acceptance standard

A developer unfamiliar with the experiments can select a realistic task, see a real or explicitly labeled mock run, inspect independent correctness and the agent's actual journey, understand a grounded issue, and compare an actionable change. Product claims must remain narrower than evidence.

## Long-term platform vision — Agent Readiness Registry and API

**Product direction accepted 2026-10-28; future roadmap, not an implemented or approved build.** Beyond diagnosing and improving individual websites, Agent Readiness could become a reusable **agentic-web primitive**: a shared, independently evaluated registry of how reliably and efficiently agents can complete specific tasks on specific websites.

**Phase 1 — Measure (hackathon):** Run bounded, versioned reference-agent tasks; independently verify outcomes; report navigation effort, time, calculated cost, evidence quality, uncertainty, and failure attribution. Do not claim broad reliability from a small pilot.

**Phase 2 — Optimize (hackathon target):** Suggest evidence-linked website changes and rescan controlled variants to test whether they actually improve task outcomes or effort. Hypotheses are not validated improvements until measured.

**Phase 3 — Registry (post-hackathon):** Publish opt-in, task-specific website capability and readiness records, with evaluation dates, sample sizes, agent/tool versions, uncertainty, provenance and reproducible methodology. Explore independent rankings only once coverage and validity justify comparisons. Do not collapse heterogeneous tasks into a universal score.

**Phase 4 — Agent-facing API (post-hackathon):** Provide a compact, machine-readable query interface so shopping and other agents can estimate task success, interaction effort and expected cost before choosing a website or interaction path. An illustrative endpoint is `GET /v1/readiness?domain=example.com&task=product_search`; it is a concept, not an existing API. Agents must still weigh price, product quality, availability and user preferences; readiness is not an instruction to exclude a retailer.

**Business hypothesis, not an established effect:** If agents use readiness signals to choose among otherwise comparable websites, website owners may have a stronger incentive to improve agent accessibility and efficiency. Higher request counts can impose cumulative inference costs on agent operators, but model requests are not interchangeable in price and the current experiments cannot establish lost traffic, ranking effects or revenue impact. Validate agent adoption, choice effects and economic value in separate experiments.

**Trust and governance:** Keep evaluation/rankings independent of paid audits or optimization services; publish clear methodology and evidence limits, allow correction/retesting, resist gaming, and consider coverage, freshness and cold-start challenges. Protect private traces, model output and credentials; no publication without separate review and approval.

**Scope gate:** The Registry/API is suitable for the hackathon *vision/pitch*, clearly labeled as future work. It does **not** expand Task 012, authorize model calls or deployment, or supersede the current priority: finish the experiment, review evidence, and demonstrate a targeted intervention/rescan. A small read-only proof of concept may be considered later only after explicit prioritization.
