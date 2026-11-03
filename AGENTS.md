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

## Testing policy (risk-based)
1. Run the tests that exercise the change first (the affected files, with `-x` and a timeout).
2. Then `scripts/critical-tests.sh` (about 40 s) for cross-cutting confidence: grants, ledger/spend gate, credentials, network isolation, cancellation, goal-bound task generation and report coverage. `scripts/dev-tests.sh` (about 2.5 min) covers all logic-level tests.
3. Run focused integration/browser tests by file when the change touches the worker, the trial runner or the report/dashboard (`pytest tests/test_context_pack.py -k end_to_end`, `cd dashboard && npx vitest run`).
4. Leave the full PR regression to sharded CI (`docs/CI.md`); a full local run takes about 33 minutes and is rarely needed.
5. Do not run resource-intensive browser tests, dashboard builds, screenshots or servers concurrently: a failure seen only during concurrent work is not a finding until it is repeated alone.
6. Use bounded timeouts (`timeout N ...`, or a background run checked a limited number of times) and never poll indefinitely; if a run is slow, inspect the process and log instead of waiting.
7. No paid model call is ever part of testing: tests are loopback-only and the dev provider is a fixture, not a model.

## Handoff protocol
Discuss → propose → approve → task → implement → report → review. Tasks saved as historical references are not automatically approved to execute. Codex can make routine technical choices but must escalate experiment-design changes. Commit work in reviewable units, record checks actually run and limitations, update `STATUS.md`, and link the relevant task/report. No unapproved spending on model calls or external actions.

## Current state
See `STATUS.md` (authoritative). Final showcase (2026-11-03): the release candidate is branch `final-showcase` (featured site Larkspur, new website version `larkspur@improved`, judge pool `larkspur-core@v3` on Original vs Improved; not deployed), see `collaboration/reports/final-showcase-release.md`. Summary as of 2026-11-04: production runs `evaluation-v2` @ `140a4e8` operator-only at https://209-38-84-72.sslip.io (US$10 hosted ceiling); the branch stack is unmerged into `main`. The lifecycle (M1–M7) lives on `research/llm-task-planning`; its product integration (M8) is the release candidate on `m8-product-integration`, not deployed. No paid model call, ceiling change or public paid access is authorized without explicit owner approval; the programme ceiling is A$50 (a limit, never an authorization). Historical Task 001/002 specs are pre-event references, and historical Task 005–007 code/config/data, frozen manifests, pilot artifacts, stored evaluation evidence and the budget ledger are never modified.

Credentials: set `META_MODEL_API_KEY` in the process environment or a repository-root `.env` (ignored by Git; `.env.example` is the template). Process variables take precedence. Never print, log or commit its value. Never use a bare `git add -A` (`uv.lock` is deliberately untracked).
