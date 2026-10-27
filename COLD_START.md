# COLD_START.md — Agent Readiness

> **For coding agents joining or resuming this project.**
>
> Read this before proposing changes, writing code, or making architectural decisions. This document provides orientation, not a complete specification. Always inspect the current repository and relevant task documents.

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

Our immediate technical priorities are a reliable experimental harness and verified Meta model integration.

The current state of the hackathon implementation is recorded in `STATUS.md`. Do not infer completion from this document.

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