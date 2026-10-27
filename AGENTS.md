# Codex collaboration — Hackathon Agent Readiness

Read `COLD_START.md` first, then `STATUS.md` (authoritative current handoff), then the active task/report. Verify the actual branch, PR and code.

## Purpose and responsibilities
User + ChatGPT own product direction, experiment design, and major architectural decisions. Codex implements explicitly approved tasks, tests its changes, and reports evidence. Discuss changes to scope or validity before implementing them. Favor small working increments and direct communication.

## Hackathon provenance (critical)
Hackathon implementation starts 2026-10-27 Australia/Sydney. The earlier repository `Ezio99/Agent_Readiness` is a **pre-event prototype**. The planning notes and historical task specifications here were prepared before the event and are labeled as such. **Do not copy executable source, tests, configuration, generated artifacts, CI success claims, or old completion checkboxes from the prototype as new hackathon work.** Consult official hackathon reuse rules before reusing any pre-existing assets. Cite pre-event material honestly; never rewrite its creation dates or misrepresent older work as new. Reimplement new code in this repository and gather fresh validation.

## Session startup
Read `AGENTS.md`, `STATUS.md`, `docs/PROJECT.md`, `docs/DECISIONS.md`, relevant `collaboration/tasks/` specifications and the current `README.md`. Verify the actual checkout rather than trusting status text. Identify the next approved task, current blockers, and exact checks.

## Implementation conventions
- Prefer a functioning narrow end-to-end system over speculative architecture.
- Start with a controlled shopping site, seeded feasible task generation, one reference browser-agent configuration, inspectable traces, and an independent evaluator.
- A successful final answer must not be possible solely from initial catalog-page observations; inspect DOM, accessibility trees, embedded data, and other accessible payloads for leakage.
- Keep the evaluator's ground truth separate from agent observations. Grade outcomes independently of agent self-assessment.
- Record model, provider, profile, run limits, timestamps, versions, failures, and model usage when available.
- Smoke runs, simulated answers, and pre-event reports do not count as successful live hackathon agent trials.
- Verify the Meta AI model/API integration instead of assuming model or endpoint compatibility.
- Never commit API keys, .env files, private truth records, raw traces with credentials, or generated run data.

## Handoff protocol
Discuss → propose → approve → task → implement → report → review. Tasks saved as historical references are not automatically approved to execute. Codex can make routine technical choices but must escalate experiment-design changes. Commit work in reviewable units, record checks actually run and limitations, update `STATUS.md`, and link the relevant task/report. No unapproved spending on model calls or external actions.

## Current state
See `STATUS.md`. The fresh credential-free foundation (storefront, seeded tasks, Browser Use adapter, independent evaluator, recorder, CI) was implemented in this repository and merged via PR #1. Authenticated Meta probes and bounded agent trials have occurred; see `STATUS.md` and Report 004. The latest opt-in compatibility trial executed one recovered click, but did not complete the task.

Task status: `001-first-agent-run.md` and `002-interaction-dependent-benchmark.md` are **historical pre-event specifications** (not approved to execute). `003-hackathon-first-agent-run.md` is the **completed foundation** (hosted Meta validation still pending). `004-first-live-meta-trial.md` documents completed and failed gated trials; see Report 004. Draft Task 005 proposes a bounded end-to-end compatibility trial and is **not approved**. PR #3 (`hackathon/task004-stage-a`) is open and unmerged. No further paid calls or merges without explicit approval.

Credentials: set `META_MODEL_API_KEY` in the process environment or a repository-root `.env` (ignored by Git; `.env.example` is the template). Process variables take precedence. Never print, log or commit its value.
