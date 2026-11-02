# COLD_START.md — Agent Readiness

> **For coding agents joining or resuming this project.**
>
> Read this before proposing changes, writing code, or making architectural decisions. This document provides orientation, not a complete specification. Always inspect the current repository and relevant task documents.

## Latest handoff — 2026-11-03 (M8: product integration of the lifecycle)

**The M8 agent starts with [collaboration/handoffs/m8-product-integration.md](collaboration/handoffs/m8-product-integration.md)**. It is self-contained: branches, the live product, the M2–M7 lifecycle, the M6/M7 results and artefacts, integration readiness, safeguards, constraints and open decisions. The branch is `research/llm-task-planning`; production is unchanged (`evaluation-v2` @ `140a4e8`).

## Earlier handoff — 2026-11-02 (research: two-stage evaluation lifecycle)

**Research agents start with [collaboration/LIFECYCLE_HANDOFF.md](collaboration/LIFECYCLE_HANDOFF.md)** ("NEW AGENT START HERE"). It covers branch `research/llm-task-planning`, the approved two-stage lifecycle decisions and the completed milestones M1–M5 (report: [collaboration/reports/lifecycle-m2-m5.md](collaboration/reports/lifecycle-m2-m5.md)). M6 (paid validation) is next and needs separate owner approval. The research work is isolated from production and the release candidate.

## Production handoff — 2026-11-02

Production (operator-only) runs `product-experience-redesign` (hosted Ironbark evaluator + redesigned frontend) at https://209-38-84-72.sslip.io. Start with [STATUS.md](STATUS.md) and [deploy/DEPLOY.md](deploy/DEPLOY.md); the sections below are older handoffs kept for context.

## Earlier branch handoff — 2026-11-01

On `live-m1-llm-evaluation` / draft PR #60: see [STATUS.md](STATUS.md), [CODEX_HANDOFF](collaboration/CODEX_HANDOFF.md) (historical takeover context), and [Report 016n](collaboration/reports/016n-scroll-tolerance-and-exp-c-s1.md). The single authorized EXP-C-S1 stage is complete; see [Report 016o](collaboration/reports/016o-exp-c-s1-results.md). No further paid run, merge, push or deployment is authorized. Older Task 015/016 "next" statements below predate the live investigation pipeline.

## Current execution handoff — 2026-10-29 (Task 015 stack + 015f merged; Task 016 M1 implemented; plan approved)

**Read first:** [collaboration/TASK016_HANDOFF.md](collaboration/TASK016_HANDOFF.md) (fresh-session handoff, start here), [STATUS.md](STATUS.md) (authoritative current state), [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) (layers, execution paths, frozen/pinned artifacts, audit classification, debt, what Task 016 can reuse), then the active task. Earlier handoff text is archived verbatim in [docs/archive/COLD_START-handoff-through-2026-10-29.md](docs/archive/COLD_START-handoff-through-2026-10-29.md).

**Product direction (user-clarified):** Agent Readiness is a **developer-facing diagnostic platform**: *baseline scan → identify friction → recommend a change → modify the site → rescan → measure whether it helped.* Recommendations originate from the product's own observed evidence (never hand-picked), are labelled unvalidated until a controlled experiment measures them, and negative or inconclusive results are preserved. Do not manufacture failures, blame the website for agent/tool problems, or call a resolved finding an improvement.

**State in one paragraph:** `main` has everything through Task 015f (the Task 015 product, driver, executed two-run pilot, verified main-stage proposal and the consolidation were merged bottom-up). The 24-run main stage is **on hold (not approved)**. Programme budget A$50 (limit, not authorization); spent ≈ A$6.21 calculated. **No paid call is authorized.** WebArena/Magento (Task 014) is an experimental environment supporting the platform. **Next: Task 016** (issue #28) — start with a focused audit and plan, then stop for review.

**Standing constraints:** never print/commit `META_MODEL_API_KEY` or `.env`; no paid inference or merge without the owner's explicit approval of the exact plan/hash; keep scripted/mock/recorded/live evidence distinct; frozen manifests, pilot evidence, byte-pinned legacy code and the budget ledger are never rewritten; `uv.lock` is deliberately untracked.

**Workflow:** update this file and `STATUS.md` before each new task; commit specs; the owner reviews and explicitly approves PR merges, paid inference, hosting and public releases.

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

Meta integration, the experimental harness, the site-audit/recommendation product and an executed two-run pilot exist (see `STATUS.md`); the current development priority is **Task 016** (general-purpose autonomous investigation, issue #28). Verify repository state rather than inferring completion from older sections. Early milestones (Tasks 001–007) are historical: `collaboration/tasks/001`/`002` are pre-event specifications.

## 4. Where to find information

| Location | Purpose |
|---|---|
| `README.md` | Installation, commands, architecture overview, and usage |
| `STATUS.md` | Current progress, verified results, blockers, and next steps |
| `docs/ARCHITECTURE.md` | Layers, execution paths, frozen/pinned artifacts, consolidation audit, technical debt, Task 016 reuse guide |
| `docs/archive/` | Verbatim historical snapshots of STATUS / COLD_START handoff / the legacy-runner README |
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