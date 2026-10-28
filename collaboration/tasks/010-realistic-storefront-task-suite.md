# Task 010 — Realistic Storefront and Diverse Task Suite

**Status:** Approved implementation direction, credential-free only. **No paid inference, paid hosting, public deployment, PR merge or private artifact publication.**
**Baseline:** Latest `main`; read [COLD_START.md](../../COLD_START.md) and [product roadmap](../../docs/PRODUCT_ROADMAP.md) first.
**Owner:** Claude implementation; user and ChatGPT product review.
**Sequence:** Implement first. Task 011 protected scanner follows and must consume the new contracts.

## Objective

Replace the toy-storefront-only product story with a realistic, versioned electronics retail reference environment and multiple independently gradable tasks. Preserve the existing Task 007 storefront/fixtures, raw artifacts, results and experiment behavior unchanged. Build on existing FastAPI/Playwright/Browser Use/evaluator abstractions; avoid an unnecessary rewrite.

## Stage 1 — Inspect and design

- Inspect current storefront, inventory, task generators, task kind routing, independent evaluator, browser guard, runner, CLI, tests and dashboard integration points.
- Draft short technical design: versioned environment ID and URLs, normalized inventory/specs/compatibility/policy/stock data, deterministic seed/state, configurable UI factors, domain-extensible task schema, oracle isolation, evaluator semantics and trace requirements.
- Highlight necessary compatibility migrations and risks; avoid breaking historical Task 007 reproduction. Keep existing evaluator byte-for-byte where feasible.
- Do not hardcode the general task schema to electronics; domain-specific graders may be pluggable.

## Stage 2 — Realistic reference store

Build one coherent synthetic electronics store with:
- Home, category navigation, search, listing with working filters and sorting, product detail pages with specs/availability, shipping and returns policy pages.
- A useful catalog with realistic variety and distractors across headphones, laptops, monitors and accessories; enough overlap that answers require navigation and multi-constraint checks. Deterministic immutable catalog fixtures and a documented inventory size; no need for hundreds of products just for appearance.
- Browser usability and semantics: responsive UI, realistic product cards, accessible controls, meaningful navigation, no placeholder controls that appear functional.
- At least two switchable **controlled** website characteristics, starting with listing-vs-detail availability and structured-vs-fragmented specifications. Keep underlying data and task wording constant when switching a factor. Provide an explicit variant ID and metadata. Don't assume either arm will outperform the other.
- No real checkout, external commerce integrations, personal data, payment details or orders. Cart simulation is optional in this task and must not block P0 tasks.

## Stage 3 — P0 curated task suite

Define and implement four deterministic task templates, with multiple feasible fixtures where practical:
- **T1 discovery:** in-stock ANC headphones under a stated budget.
- **T2 comparison:** compare named laptops by RAM and advertised battery life.
- **T3 constraint selection:** cheapest in-stock monitor meeting size, USB-C and refresh-rate criteria.
- **T4 policy/delivery:** locate and accurately report returns and delivery information for a selected product.

For each task, freeze objective, starting state, allowed outcomes, limits, required evidence, independent oracle and grading criteria. Explicitly distinguish unique-answer tasks from tasks allowing multiple eligible products. Verify feasibility programmatically; add negative controls/edge cases where meaningful. Ensure answers cannot be trivially obtained from the first page or leaked evaluator truth. Store task IDs/version, environment/variant, data version and evaluator version in results.

Use a domain-extensible contract (objective, environment, constraints, evaluator, evidence, limits) consistent with accepted D006; do not implement LLM-generated tasks yet.

## Stage 4 — Verification and product handoff

- Credential-free browser smoke checks for each P0 task, deterministic evaluator PASS and deliberately wrong FAIL, variant invariants, evaluator-truth isolation, navigation behavior, mobile/basic accessibility and historical regression tests.
- Ensure no paid provider request occurs in tests/CI by default. Clearly distinguish scripted smoke from actual model task success.
- Produce a short technical report with environment/task fixture inventory, evaluator proof, screenshots only if safe and not publicly deployed, actual test results, limitations, and what Task 011 needs to consume.
- Update `STATUS.md`, relevant docs, and misleading README current-state header without rewriting historical evidence.
- Open a PR for review. Do not merge or deploy. No live Meta trials unless separately approved later.

## Acceptance criteria

1. A human can browse a credible synthetic electronics shop with working discovery and information architecture.
2. Four varied P0 tasks are feasible, reproducible and independently evaluated; wrong answers fail.
3. At least two website design factors are independently configurable with unchanged underlying facts.
4. Prior experiments remain reproducible and old tests remain green.
5. New task/environment contracts can be consumed by the future protected scanner without an electronics-only hardcode in the core API.
6. A clear report and PR identify exactly what is implemented, tested and still unverified.

## Stop conditions

Stop at PR and handoff. No automatic merge, deployment, paid model calls, API key handling beyond existing patterns, private trace publication or unrelated product expansion. If the proposed scope demands a material architecture change, report options before implementing it.
