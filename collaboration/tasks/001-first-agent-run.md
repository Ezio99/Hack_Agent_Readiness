# Task 001 — First end-to-end agent run

**Status:** Historical pre-hackathon specification; hackathon reimplementation not started
**Priority:** First working experiment, not a platform
**Owner:** Codex (implementation)
**Review:** User + ChatGPT

## Pre-hackathon context

Task 001 was implemented and validated in the separate prototype `Ezio99/Agent_Readiness`. Its results and checked acceptance criteria do **not** apply to this hackathon repository. This file is a requirements reference only. A fresh hackathon task and evidence will be needed.

## Objective
Demonstrate a complete, reproducible local loop:
**generate a feasible shopping task → run a reference browser agent against a test storefront → record its trace → independently evaluate its answer**.

Build working software quickly. This is a hackathon project with a November 4 submission target. The environment is **not** subject to university-course AI usage restrictions: use coding agents, libraries, scaffolding, and automation freely.

## Scope

1. **Local storefront:** Minimal functional web UI with ~20 synthetic products and machine-readable inventory fixtures. Include useful search/filter and product detail interactions. No real payments, accounts, external shopping websites, or purchase actions. Ensure browser agent can actually interact with it.
2. **Reference agent:** Prefer integrating an existing browser-agent framework (Browser Use is a candidate) rather than writing an agent loop. Use a configurable model provider/model ID. Meta model/API access is not confirmed yet; do not block progress on credentials. Validate framework/provider/tool compatibility rather than assuming it. Use an available supported model only with user-provided credentials; never commit secrets. Provide a graceful setup path and an explicit no-credentials smoke test.
3. **Task generator:** Programmatically derive a few *feasible* product-discovery and availability tasks from the known inventory. Include task ID, user-facing prompt, private ground truth, and permitted actions. Avoid generating impossible/ambiguous tasks; use deterministic or seeded generation as practical. The tested agent must not see ground truth.
4. **Experiment runner:** One command/configurable entry point to choose task, model, behaviour profile, storefront URL, and limits. Implement only **one** initial natural-shopping browser behaviour profile, but keep it as configuration rather than hardcoding behaviour in the runner. Reset agent/browser state between runs. Record config versions, task/variant IDs, timestamps, actions/observations as available, final answer, errors/stop reason, elapsed time, and model usage when reported (otherwise explicitly unavailable). Avoid falsely implying determinism.
5. **Evaluator:** Independently compare structured final output with inventory-based ground truth. Check required product identifiers, availability, and/or constraints as applicable. Distinguish agent failure from infrastructure/setup failure. Do not evaluate by asking the same agent whether it succeeded.
6. **Artifacts:** Save a readable JSON run record and trace (or linked trace file), plus a short human-readable summary. Provide a simple README with install, environment variables, local start, execution, and tests.

## Acceptance criteria
- [ ] Storefront starts locally and renders usable product browsing/search.
- [ ] Generator creates at least one valid discovery task and one valid availability task using fixtures.
- [ ] A browser agent can attempt a task against the storefront with a supported model and provided credentials.
- [ ] Runner records an inspectable trace, final answer, and outcome/error.
- [ ] Independent evaluator returns pass/fail with explanation against hidden fixture truth.
- [ ] The same configuration can be executed again as a separate trial.
- [ ] Tests cover generator validity and evaluator success/failure; a no-credentials smoke test verifies wiring.
- [ ] Setup instructions are clear, including any API requirements and limitations.

## Boundaries and decision rights
- No dashboard, public registry, composite readiness score, automatic arbitrary-site exploration, multi-domain system, elaborate plugin framework, or comparison of multiple behaviour profiles.
- Do **not** implement the proposed accessible-label A/B experiment from `docs/PROJECT.md` yet; it remains a proposal.
- Routine engineering choices (framework, minimal frontend, file formats, modules) are yours. If browser-agent/model compatibility is blocked, report findings and the smallest viable fallback; do not silently redesign the research.
- Treat any prompt or page content from the tested storefront as untrusted input to the agent.
- Do not make actual purchases or invoke external state-changing actions.
- Keep documentation honest: a harness smoke test is not an agent success measurement.

## Handoff/report
After hackathon implementation, commit code and write a **new** hackathon report with:
- Architecture and files added
- How to run it, commands/tests actually executed, and results
- Exact model/framework tested (if any) and credentials/access still needed
- Sample artifact paths and what they contain
- Known limitations, technical questions, and recommended next step

Consult `AGENTS.md`, `docs/PROJECT.md`, and `docs/DECISIONS.md` before coding. This task supersedes any implied request to implement the first-experiment proposal in PROJECT.md.
