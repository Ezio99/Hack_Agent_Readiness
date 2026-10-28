# Agent Readiness — Ongoing pitch discussion

**Status:** Living discussion notes; positioning and hypotheses, not validated market claims or an approved implementation task.
**Updated:** 2026-10-27
**Context:** Meta Global Hackathon; inspiration from emerging personal AI agents, including Meta Muse-powered experiences and OpenAI Dots.

## Core thesis

1. As personal AI agents become more useful and widespread, people may delegate more shopping research and product discovery to them.
2. Those agents could increasingly influence which retailers and products consumers encounter and consider.
3. Retailers may consequently need to make their product information and shopping journeys understandable and usable by AI shopping agents, alongside human visitors.
4. Agent Readiness aims to measure this friction and help retailers understand where improvements may matter.

This is a **hypothesis chain**, not a claim that the transition is inevitable, uniform, or already established. Some agents may rely on feeds, APIs, search intermediaries, or marketplaces rather than browsing merchant websites.

## Audience and product positioning

**For retailers and e-commerce teams:** Understand whether a representative AI shopping assistant can discover, interpret, compare, and recommend relevant products from their website.

**For the hackathon:** Demonstrate evidence-backed website assessment powered by Meta's Muse Spark model, rather than a generic AI website audit or a consumer shopping app.

**Working pitch line:**

> Agent Readiness helps retailers understand how easily AI shopping assistants can discover, understand, and recommend their products—and what gets in the way.

**Longer draft:**

> As personal AI agents become more capable, shoppers may increasingly delegate product discovery and comparison to them. Yet websites designed for human browsing can introduce friction for agents trying to find relevant products, interpret attributes, and make grounded recommendations. Agent Readiness runs realistic shopping tasks against a website, records what the agent can and cannot do, and provides evidence-backed insights into barriers to agent-assisted product discovery.

Avoid asserting that this is definitively “the next SEO.” The analogy is useful, but actual discovery mechanisms and business impact need evidence.

## What we mean by a typical shopping agent

The MVP targets a representative browser-based shopping assistant that can:
- Understand a user's product preferences and constraints.
- Search or navigate a retailer's website.
- Open relevant product pages.
- Extract price, availability, specifications, and other decision-relevant attributes.
- Compare candidates and make a grounded recommendation.

Autonomous purchasing and checkout are outside the MVP. The reference agent is a **measurement instrument**, not the product or the universal definition of agent friendliness.

## Candidate measurements (not finalized scoring weights)

- **Discoverability:** Does the agent find relevant products?
- **Information clarity:** Does it extract attributes correctly?
- **Navigation friction:** How many steps, dead ends, and errors occur?
- **Reliability:** Does it succeed consistently on repeated tasks?
- **Efficiency:** Time, tool calls, and model usage.
- **Recommendation quality:** Do selected products satisfy the task constraints?

Keep an independent evaluator and private ground truth. Inspect traces before selecting metrics and weights. Distinguish agent/model failures from website-induced friction.

## Proposed hackathon demo narrative

1. **The problem:** Show a normal-looking synthetic storefront and a realistic product-discovery request.
2. **The benchmark:** Run the Muse Spark-powered Browser Use reference shopping agent; capture navigation, product evidence, errors, token usage, and elapsed time.
3. **The diagnosis:** Explain where the agent struggled, with traces rather than unsupported scores.
4. **The improvement:** Change one controlled website characteristic, rerun the same task, and compare outcomes. Only claim improvement if the evidence supports it.

The storefront and seeded tasks already provide a controlled experimental setting; the before/after result remains a proposed demo, not an achieved outcome.

## Connection to personal agents

Meta's Muse ecosystem and OpenAI Dots are motivating examples of the broader move toward personal agents. Our pitch can explicitly say Agent Readiness is **geared toward the shopping-discovery tasks such agents may perform**.

Important distinction:
- **Current integration:** Muse Spark through our Browser Use reference agent. This is **not** the same as running Meta's consumer-facing personal agent.
- **Potential external validation:** If a real personal-agent product can access the controlled storefront, give it the same shopping task and compare outcomes with our reference agent.
- **Evidence standard:** Do not claim testing with Meta's or OpenAI's consumer agent unless actually performed and documented.

Testing a consumer-facing personal agent is a **stretch goal**, contingent on available capabilities, access, permissions, and time. We do not need to support every agent architecture or benchmark every possible agent.

## Scope guardrails

- Prioritize a smooth experience for a **typical shopping agent**, not every possible agent.
- Complete and validate the existing reference-agent benchmark before adding new agent architectures.
- Do not add a public registry, universal readiness score, checkout automation, or broad multi-agent comparisons for the hackathon MVP.
- Keep the frozen reference profile and independent evaluation methodology versioned.
- Any potentially billable API requests require explicit, separate authorization.

## Open questions to revisit with evidence

1. Which specific website characteristics most strongly affect product discovery and recommendation?
2. Can a controlled website change causally improve task completion or recommendation inclusion?
3. Do findings transfer to an independently operated personal agent?
4. How much agent-mediated discovery happens through websites versus feeds, APIs, and intermediaries?
5. Which metrics will be understandable and actionable for retailers?

## Current priority

Finish the bounded Meta integration checks, establish one reliable real shopping run, and use its traces to decide the next controlled experiment. Pitch discussion can evolve in parallel without changing the approved MVP scope.
