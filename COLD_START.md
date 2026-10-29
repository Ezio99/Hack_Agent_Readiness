# COLD_START.md — Agent Readiness

> **For coding agents joining or resuming this project.**
>
> Read this before proposing changes, writing code, or making architectural decisions. This document provides orientation, not a complete specification. Always inspect the current repository and relevant task documents.

## Current execution handoff — 2026-10-28 (Task 011 complete; Task 012 next — planning only)

**Product direction (user-clarified):** Agent Readiness is a **developer-facing diagnostic platform**: show website owners how AI agents experience their sites, where/why they struggle, and what to change, ending in **baseline scan → identify friction → recommend a change → modify the site → rescan → measure whether it helped**. Not primarily a benchmark or dashboard. Do not manufacture failures, assume a design change helps, or blame the website for agent/tool problems; label unvalidated recommendations as hypotheses; preserve negative findings.

**Task 014 COMPLETE (2026-10-29, PRs #17–#20 merged) — qualification: ONE successful live run establishes feasibility, not reliability or website readiness.** Real Magento environment, guarded live path (durable per-request spend ledger), schema probe and one live Muse Spark run on WebArena task 286 (official evaluator PASS, 14 steps/requests, 59.8 s, calculated US$0.2447) are documented in Reports [014](collaboration/reports/014-webarena-magento-e2e.md), [014b](collaboration/reports/014b-webarena-live-path-offline.md), [014c](collaboration/reports/014c-webarena-schema-probe.md), [014d](collaboration/reports/014d-webarena-286-live-run.md). Task 013's offline implementation is complete; its live-model behaviour is only weakly observed (read-state output reached the model in that one run). WebArena stays an experimental environment supporting the diagnostic platform. **Task 015 (owner-approved offline scope; implemented, PR open): [spec](docs/TASK015_REMEDIATION_EXPERIMENT_SPEC.md), [Report 015](collaboration/reports/015-remediation-product-offline.md)** — the product autonomously audits a site (`readiness audit URL`, `POST /api/audits`), selects recommendations from a rule library by observed evidence, and recognises resolution on re-audit; budget is tracked in AUD (A$50 ceiling, not an authorization; `collaboration/budget/programme-ledger.json`). The pilot/experiment driver is built offline ([Report 015b](collaboration/reports/015b-pilot-driver-offline.md), frozen pilot manifest in `collaboration/experiments/task015/pilot/`); the two-run paid pilot (cap A$1.50) was EXECUTED once (calculated A$0.32; modified PASS 4 requests vs unmodified FAIL 11 requests; n=1, no causal claim; frozen gate said `stop` but mislabelled — see [Report 015c](collaboration/reports/015c-pilot-results.md)); a corrected main-stage proposal (3-arm, stage cap A$6.00, gate `room-to-act-v2`, manifest `ee2f6e06…`) is prepared offline in [docs/TASK015_MAIN_STAGE_PROPOSAL.md](docs/TASK015_MAIN_STAGE_PROPOSAL.md) and needs explicit approval of its manifest hash; no paid run is authorized. PR #22 security review: [Report 015a](collaboration/reports/015a-pr22-security-integration-review.md). No paid call is authorized; the Magento container `wav-shopping` may still be running and is unmodified. Setup for WebArena: `docker.exe run -d --name wav-shopping -p 7770:80 -p 7771:8877 am1n3e/webarena-verified-shopping`; `uv run --extra webarena python scripts/webarena_validate.py direct <dir>`.

**Verified state:** `main` includes Task 010 (`1c31820`: `electronics-v1`, 4 controlled variants, 10 fixtures, independent oracles) and Task 011 (`23db19f`: protected scanner — observed-text evidence, `suite-v1-compat1` profile, mock provider personas, evidence-linked diagnostics, invitation-gated API/SQLite service, dashboard "Protected scanner" tab; live gated and off). PR #8 (`4509165`) added the guarded live-validation driver (`scanner/live.py`: persistent ledger, probe-first, no retries) and Report 011b.

**Task 011 live validation (approved, complete):** schema probe OK (US$0.003); 4 fixtures × 1 run on the baseline variant `availability-listing+specs-structured`: **4/4 independent PASS and evidence-backed**, 5–9 requests, 15–36 s, calculated US$0.348 total (not a bill; $1.25/$4.25 per M verified). Raw strict-JSON compliance **1/26** responses; 25 recovered by the fixed compat parser `muse-prose-prefix-json-v1` (it is part of the frozen agent). Extra page visits in T1/T4 are not presumed website friction. Establishes capability only — **not** reliability and **not** variant effects. Private artifacts: `runs/live-validation-011/` (ignored). See [Report 011b](collaboration/reports/011-live-validation.md).

**Task 012 Stage 1 has been executed live (8 runs, US$0.718 calculated; Report 012b): T2–T4 passed in both V0 and V3, T1 failed in both because of a tool-visibility loop plus SKU not shown on listing cards; no V0/V3 effect detected (n=1/cell). Stage 2 NOT approved; next step is a review decision (tool-visibility fix + T1 baseline repeats vs. SKU-on-listing intervention).**

**Task 012 background: [Task 012 — realistic agent experiments](collaboration/tasks/012-realistic-agent-experiments.md).** Current step: the experimental plan is approved with amendments A–C (Stage 1 = sensitivity only; evidence tiers; programme-wide US$6.00 ledger) and credential-free implementation is complete pending review (`src/agent_readiness/experiments/`, Report 012a; mock Stage 1 demonstrated, no live call) — [docs/TASK012_EXPERIMENT_PLAN.md](docs/TASK012_EXPERIMENT_PLAN.md) (matrix of 4 fixtures × variants V0–V3, 8-run Stage 1 pilot, gated 29-run Stage 2, frozen configuration, ledger ceilings, analysis, diagnostics pipeline). Watch for ceiling effects (baseline already passes); T4 is a control, not an A/B test. **Not authorized:** any paid Task 012 call, hosting/provisioning, public scanner deployment, publishing private traces/replays/credentials/truth (Meta-terms/hackathon-rules questions still open), or merging without explicit approval. Credential-free preparation starts only after the plan is approved.

**Standing constraints:** never print/commit `META_MODEL_API_KEY` or `.env`; no paid inference without a separately approved exact call plan (tasks, variants, run count, limits, max calculated cost) and the ledger; historical Task 005–007 code/config/data are byte-pinned; calculated cost ≠ billed cost; keep scripted/mock/recorded/live clearly distinct. `uv.lock` is deliberately untracked.

**Start here:** this file, `STATUS.md` (authoritative current state), [Product roadmap](docs/PRODUCT_ROADMAP.md), [Task 012 plan](docs/TASK012_EXPERIMENT_PLAN.md), [Scanner design](docs/SCANNER_DESIGN.md), [Task suite design](docs/TASK_SUITE_DESIGN.md), Reports 010/011/011b.

**Workflow:** Before EVERY new task update `COLD_START.md` and commit its spec. User reviews and explicitly approves PR merges, paid inference, paid hosting and public releases. US$10/month hosting is a planning allowance, not permission to incur charges.

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