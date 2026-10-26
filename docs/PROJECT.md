# Agent Readiness

> **Implementation checkpoint — 2026-10-26:** The first local loop is implemented
> and Task 001's live acceptance is verified: discovery, both availability cases,
> and a repeated discovery. See [current status](../STATUS.md),
> [Task 001](../collaboration/tasks/001-first-agent-run.md), and its
> [evidence report](../collaboration/reports/001-first-agent-run.md).
> The kickoff experiment and next-milestone discussion below are historical
> planning context. The accessible-label A/B experiment remains unapproved;
> Task 001's completion does not authorize it or another implementation task.

## Vision and problem

Investigate how efficiently, accurately, and reliably AI agents interact with
websites, starting with e-commerce. Agent-native, hybrid, and human-oriented
services may coexist. Their prevalence and commercial implications remain open.

A website may be navigable yet costly, unreliable, or difficult for an agent to
interpret or verify. The project will collect evidence about these differences
before proposing an Agent Readiness or Agent Experience (AX) score.

## Hypotheses to investigate

- Website properties can affect agent task success and resource use.
- Controlled website changes can expose specific interaction difficulties.
- Repeated measurements may support useful diagnostics and, later, metrics.
- Businesses may eventually benefit from optimizing for agent interaction; this
  commercial hypothesis is unvalidated.

## Agreed direction

- Collect raw interaction data before defining scores or weights.
- Begin with e-commerce and consider controlled mock storefronts first.
- Version and freeze the reference agent configuration within each experiment.
- Repeat trials and evaluate outcomes against independent ground truth.
- Distinguish agent limitations from website limitations. Observational
  comparisons alone do not establish causality.
- Keep the implementation small; logical components need not be separate services.
- Prioritize experimentation and diagnostics. Defer the registry and dashboard.

## Hackathon repository status

This new repository starts with planning documents only. The prior prototype is archived separately at `Ezio99/Agent_Readiness`. No application implementation or benchmark validation has been migrated.

## Proposed first experiment — pending agreement

Question: Does exposing explicit labels on product filter controls change a fixed
browser agent's ability to find a product satisfying several constraints?

Build one local mock storefront with a fixed, synthetic inventory and two variants:

- A: filter controls without explicit accessible labels.
- B: the same controls with associated accessible labels.

Keep inventory, prices, layout, filter behavior, task wording, and starting state
identical. Record the exact DOM difference. This tests one intervention rather
than comparing unrelated websites. Its effect may depend on whether the browser
  tool exposes accessibility information; capture that representation explicitly.

Use three fixed product-selection tasks, each with a unique qualifying product
and an answer containing product ID, price, and evidence for each constraint.
Validate the fixtures independently before trials. Do not expose the evaluator's
answer key through the agent's tools or context. No purchase flow is needed.

Run five fresh trials per task per variant: 30 runs total. Randomize and record
run order, reset browser and agent state each time, and use fixed execution limits.
Start with a wiring smoke test excluded from the measured run set. Five repeats
are a pilot, not evidence of statistical significance or broad generalizability.

Record:

- Task, variant, trial ID, seed/order, timestamps, and code/configuration versions.
- Model identifier, instructions, sampling settings, browser/tool versions,
  viewport, available tool observations, and execution limits.
- Model messages and tool calls/results, final answer, errors, and stop reason.
- Independently evaluated success, elapsed time, action count, and reported token
  usage; mark unavailable usage explicitly rather than estimating it as measured.

Compare task-level successes and failures, resource distributions, and trace
examples. Separate infrastructure failures from agent outcomes and report both.
Do not reduce results to a composite readiness score. A null result is useful;
any conclusion applies only to this intervention, agent, tool representation,
inventory, and task set. A pinned configuration improves repeatability but does
not guarantee deterministic model responses or immutable hosted model behavior.

## Essential choices before implementation

1. Model/provider: tool support, accessible credentials, budget, version pinning,
   and any verified hackathon requirements.
2. Browser interaction: accessibility/DOM observations, screenshots, or both;
   keep this fixed and ensure the intervention is observable through that tool.
3. Minimal stack: choose one runner language, a browser library, and a local
   storefront implementation without additional services.
4. Benchmark contract: exact inventory, tasks, answer schema, grading rules,
   action/time/token limits, and treatment of failures.
5. Run artifacts: local structured files, configuration snapshots, and browser
   evidence sufficient to inspect failures and reproduce the setup.

## Open questions and next milestone

- Is the labeling intervention the most useful first contrast, or should another
  single property be selected?
- Which model and execution budget are available? Is hackathon participation
  intended, and does it constrain technology choices?
- Which browser observation mode best matches the intended reference agent?
- What result would justify the next intervention or a second reference agent?

Historical proposal (not an approved hackathon execution plan): agree on the contrast and essential choices, then implement one
storefront, one reference agent, a small runner/recorder, and independent grading.
Research relevant existing benchmarks and standards before claiming novelty.
