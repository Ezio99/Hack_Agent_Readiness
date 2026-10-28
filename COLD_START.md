# COLD_START.md — Agent Readiness

> **For coding agents joining or resuming this project.**
>
> Read this before proposing changes, writing code, or making architectural decisions. This document provides orientation, not a complete specification. Always inspect the current repository and relevant task documents.

## Current execution handoff — 2026-10-28 (product foundation first)

**Current product direction:** [Product definition and roadmap](docs/PRODUCT_ROADMAP.md) is the accepted source for product scope, user value, reference storefront, task suite, metrics and sequencing. Agent Readiness evaluates **websites/digital services**, using agents as measurement instruments; it is not primarily an agent benchmark or just a report. Browser-based e-commerce is the first channel; APIs/structured interfaces and hybrid access remain in scope conceptually.

**Current verified baseline:** `main` includes Task 007 exploratory pilot (29/30 independent PASS), Task 008 dashboard, and Task 009 safe static deployment. Public dashboard: https://ezio99.github.io/Hack_Agent_Readiness/ (no private replay JSON, no live scanner). Task 009 PR #5 squash-merged as `1cde559`; manual Pages run 40639069457 passed. Historical pilot fixture/results must remain unchanged.

**Next task:** [Task 010 — Realistic Storefront and Task Suite](collaboration/tasks/010-realistic-storefront-task-suite.md). Build a new versioned realistic electronics storefront, domain-extensible task contract, four curated P0 tasks with independent evaluators, and offline/browser verification. **No paid model calls, hosting provisioning, public deployment, PR merge or private data publication.** Task 011 [protected live scanner](collaboration/tasks/011-protected-live-scanner.md) is deferred until Task 010 foundations are ready; reconcile its contracts with the product roadmap before implementing it. Do not start Task 011 in parallel by default.

**Start here:** this file, [Product roadmap](docs/PRODUCT_ROADMAP.md), [Task 010](collaboration/tasks/010-realistic-storefront-task-suite.md), [AGENTS.md](AGENTS.md), [STATUS.md](STATUS.md), and relevant code/tests. `README.md` and older top-of-file status entries contain historical milestones; inspect actual `main`. The current Claude session can continue; this is a replacement-agent handoff.

**Workflow:** Before EVERY new task update `COLD_START.md` and commit its spec, even if the coding agent remains the same. User reviews and explicitly approves PR merges, paid inference, paid hosting and public releases. US$10/month hosting is a planning allowance, not permission to incur charges.

## 1. Our intention

**Agent Readiness** investigates how effectively AI agents can interact with websites.

As AI agents increasingly discover products, compare options, and complete tasks on behalf of users, websites may vary substantially in how accessible, understandable, and usable they are to those agents.

We want to measure those differences empirically.

The long-term vision is a reusable system that can evaluate websites from an AI agent's perspective, identify interaction failures, and provide evidence-backed diagnostics. A shared registry of website readiness may eventually become useful.

**Our immediate objective is much narrower:** build a functioning, reproducible experimental system that can run an agent against a website, observe its behavior, independently evaluate task outcomes, and preserve useful evidence.

We are building an **agent benchmarking and diagnostics product**, not primarily a shopping assistant.

The shopping agent is our measurement instrument.

## 2. How we think about the problem

These principles guide architectural and experimental decisions:

1. **Evidence before scoring.** Collect outcomes, traces, errors, actions, latency, and resource usage before deciding which readiness dimensions or weights matter.
2. **Freeze the reference agent.** Within an experiment, keep model, instructions, tools, observation mode, and execution limits fixed and versioned.
3. **Evaluate independently.** An agent claiming success does not establish success. Use separately maintained ground truth wherever possible.
4. **Measure meaningful interaction.** A task should not appear successful merely because its answer was exposed in the initial page observation.
5. **Separate website and agent limitations.** A failure may result from either, or from infrastructure. Do not automatically attribute failures to website design.
6. **Prefer controlled experiments.** Make narrow, observable changes and avoid unsupported causal claims.
7. **Build before expanding.** Prioritize working vertical slices over speculative abstractions, broad feature sets, or premature infrastructure.

Do not invent a universal readiness score merely because the product's name suggests one.

Read `docs/PROJECT.md` and `docs/DECISIONS.md` for the fuller rationale.

## 3. Current context: Meta Global Hackathon

This repository is our fresh implementation for the Meta Global Hackathon.

**Repository:** `Ezio99/Hack_Agent_Readiness`

A separate repository, `Ezio99/Agent_Readiness`, contains pre-hackathon research and prototype work.

The distinction matters:

- Historical documents can inform our decisions.
- Previous implementations and experimental results must not be represented as newly completed hackathon work.
- Preserve accurate provenance, dates, and evidence.
- Check official competition requirements before making eligibility claims.
- Meta AI technology must have a meaningful, demonstrable role in the submitted system.

The experimental harness and Meta integration have been demonstrated in bounded runs; the current priority is a safe, demonstrable diagnostic dashboard and replay.

The current state is recorded in `STATUS.md` and the active task; verify repository state rather than inferring completion from older sections.

As of 2026-10-27 the credential-free foundation is merged (PR #1, task `003-hackathon-first-agent-run.md`). The active milestone is authenticated Meta compatibility validation followed by one independently evaluated trial, specified in `collaboration/tasks/004-first-live-meta-trial.md` (proposed; **no model call is authorized until the user approves model, endpoint, test sequence and limits**). Tasks 001 and 002 are historical pre-event specifications. Credentials come from `META_MODEL_API_KEY` in the environment or a repository-root `.env`; never expose the value.

## 4. Where to find information

| Location | Purpose |
|---|---|
| `README.md` | Installation, commands, architecture overview, and usage |
| `STATUS.md` | Current progress, verified results, blockers, and next steps |
| `AGENTS.md` | Coding-agent responsibilities, collaboration protocol, and restrictions |
| `docs/PROJECT.md` | Vision, hypotheses, experimental direction, and open questions |
| `docs/DECISIONS.md` | Accepted architectural and research decisions |
| `docs/META-INTEGRATION.md` | Meta API assumptions, integration evidence, and remaining validation |
| `collaboration/tasks/` | Task specifications, acceptance criteria, and execution gates |
| `collaboration/reports/` | Implementation reports, test evidence, failures, and limitations |
| `collaboration/proposals/` | Proposed changes that may not yet be approved |
| `src/agent_readiness/` | Current application implementation |
| `tests/` | Automated verification and expected behavior |
| `.github/workflows/` | CI checks |

Some files may not exist in an earlier checkout or may have changed. Inspect the actual branch.

**Source-of-truth hierarchy:**

1. Current user instructions and explicit approvals.
2. Actual repository state, code, and verified test results.
3. Accepted decisions and approved task specifications.
4. Current status and implementation reports.
5. Historical specifications and exploratory proposals.

If sources disagree, identify the conflict rather than silently choosing whichever is convenient.

## 5. Cold-start procedure

At the beginning of a session:

1. Read this document and `AGENTS.md`.
2. Read `STATUS.md`.
3. Read `docs/PROJECT.md` and `docs/DECISIONS.md` as needed.
4. Identify the active task, branch, and associated report.
5. Inspect the relevant code and tests.
6. Check Git status, open changes, and available CI evidence.
7. Establish what is actually implemented, what has been tested, what remains unverified, and what has been approved.

Before proceeding, briefly communicate:

- **Current state:** What is verified?
- **Active objective:** What are we trying to accomplish?
- **Next action:** What will you do?
- **Blockers or approvals:** What requires a decision?

Do not restart architectural planning when an approved implementation task already exists.

Do not assume a previous agent's summary is accurate without checking the repository.

## 6. Collaboration and autonomy

We use a hybrid workflow:

- **User:** Product owner, priorities, major decisions, and approvals.
- **ChatGPT:** Conceptual planning, experimental design, critical review, and continuity.
- **Coding agents:** Implementation, technical investigation, testing, documentation, and reporting.
- **GitHub:** Durable source of truth across sessions and agents.

Coding agents should exercise judgment on routine implementation details without asking permission for every small decision.

However, seek approval before:

- Changing the research question or experimental methodology.
- Expanding the agreed scope substantially.
- Replacing major architectural choices.
- Performing paid model experiments or external actions not already authorized.
- Merging a pull request when review is required.
- Claiming that unverified behavior or an experiment is successful.

An approved task authorizes its stated scope, not unrelated work.

## 7. Engineering expectations

Prefer a small, coherent, maintainable system.

For experiments:

- Use versioned agent profiles and explicit configurations.
- Keep evaluator truth inaccessible to the tested agent.
- Preserve all attempted runs, including failures.
- Distinguish smoke tests, simulated model responses, and actual live agent trials.
- Record relevant model, browser, task, environment, and code versions.
- Keep infrastructure failures separate from task failures.
- Make run artifacts inspectable and reproducible where practical.
- Protect credentials, private data, and sensitive traces.
- Report limitations and uncertainty instead of overstating results.

A passing test suite establishes the behavior covered by those tests. It does not establish broad experimental validity.

A successful scripted browser smoke test is not evidence that a live AI agent can complete the same task.

## 8. Scope discipline

For the initial hackathon implementation, prioritize:

**Working agent execution → independent evaluation → useful traces → reproducible experiments → meaningful Meta integration → compelling demonstration.**

Future possibilities include multi-website benchmarking, controlled website comparisons, diagnostics, a scorecard, and a shared registry.

These are directions, not standing implementation authorizations.

When tempted to add a feature, ask:

- Does it help demonstrate the core problem?
- Does it produce useful new evidence?
- Is it necessary for the current milestone?
- Can it wait until the existing experimental loop is validated?

Avoid turning a focused hackathon project into an unfinished platform.

## 9. Communication and handoff

Be concise, technically precise, and transparent.

When completing a task, report:

- What changed and why.
- Files or components affected.
- Tests and commands actually executed.
- Observed results and supporting evidence.
- Known failures, limitations, and risks.
- What remains unverified.
- The next recommended action.

Update `STATUS.md` and the relevant implementation report so another agent can resume without relying on chat history.

Do not claim tests passed unless they were actually executed or verified through CI.

Do not hide failed attempts. They are often valuable experimental evidence.

## 10. Final operating principle

**Our goal is not to produce the most elaborate agent architecture. Our goal is to learn something defensible about how AI agents interact with websites and turn that learning into a useful, working product.**

Ship small. Measure carefully. Preserve evidence. Iterate based on what we discover.

When uncertain, favor the smallest reversible action that advances the current approved objective.