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

1. **Task 011 — Product foundations (P0):** design and implement versioned realistic storefront, domain-extensible task contract, P0 task fixtures and independent evaluators. Credential-free; mock/browser smoke only. Preserve old experiment.
2. **Task 010 (revised order) — Protected scanner (P0):** integrate new storefront/task suite into public configuration, invitation-only backend, bounded Meta runner and evidence-backed reports. Implement and test locally with mock provider before paid/deployment approvals.
3. **Diagnostic layer (P0):** evidence-linked issue taxonomy, attribution and suggested fixes, with uncertainty labels.
4. **Controlled remediation comparison (P1):** rerun fixed tasks across isolated site factors and compare verified changes.
5. **Structured interface channel (P1 exploration, P2 full evaluation):** API/feeds and hybrid task pathways; clearly disclose what browser scans do not cover.
6. **Later (P2):** generated tasks with feasibility checks, more agents/domains, CI and analytics integrations.

**Task 010 is not cancelled**, but its previously authored narrow scanner scope is sequenced after Task 011 and must be reconciled with these contracts before implementation. No broad implementation, paid inference, paid hosting, merge, or public deployment is automatically authorized by this roadmap.

## Acceptance standard

A developer unfamiliar with the experiments can select a realistic task, see a real or explicitly labeled mock run, inspect independent correctness and the agent's actual journey, understand a grounded issue, and compare an actionable change. Product claims must remain narrower than evidence.
