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
See `STATUS.md` (authoritative) and `collaboration/TASK016_HANDOFF.md` (start here in a fresh session). Summary as of 2026-10-29: the Task 015 product, driver, executed two-run pilot, corrected main-stage proposal and the Task 015f consolidation are merged into `main`; **Task 016 (issue #28) is next and not started**; the 24-run stock main stage is **on hold**; no paid model call, hosting or deployment is authorized; the programme ceiling is A$50 (a limit, never an authorization). Historical Task 001/002 specs are pre-event references, and historical Task 005–007 code/config/data, frozen manifests, pilot artifacts and the budget ledger are never modified.

Credentials: set `META_MODEL_API_KEY` in the process environment or a repository-root `.env` (ignored by Git; `.env.example` is the template). Process variables take precedence. Never print, log or commit its value. Never use a bare `git add -A` (`uv.lock` is deliberately untracked).
