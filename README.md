# Agent Readiness — Meta Global Hackathon

A hackathon project to investigate how reliably AI agents can interact with websites, beginning with e-commerce. Instead of guessing readiness scores in advance, we build repeatable agent tasks, capture behavior, and independently evaluate outcomes.

**Status:** Planning scaffold only. No hackathon implementation has yet been delivered or validated.

## Project documents
- [Vision and experiment hypotheses](docs/PROJECT.md)
- [Accepted research decisions](docs/DECISIONS.md)
- [Current hackathon status](STATUS.md)
- [Codex collaboration instructions](AGENTS.md)
- [Collaboration workspace](collaboration/README.md)
- [Historical Task 001 specification](collaboration/tasks/001-first-agent-run.md)
- [Historical Task 002 specification](collaboration/tasks/002-interaction-dependent-benchmark.md)

## Provenance
Planning documents and historical specifications originated in the pre-hackathon prototype [Agent_Readiness](https://github.com/Ezio99/Agent_Readiness), created before 2026-10-27. They are provided as **reference material**, not evidence that the hackathon implementation was already completed. The old repository remains separate and unchanged. Executable implementation, tests, CI and model validation must be produced afresh, with applicable hackathon rules checked first.

## Intended first vertical slice
Controlled storefront → feasible generated shopping task → one browser-agent run → recorded trace → independent evaluation. The task should require navigating beyond the initial listing to retrieve answer-bearing information. Use one reference agent profile, record configuration and model provenance, and defer public registries, composite scores and dashboards until the experiment loop works.

No installation commands are provided yet because this repository intentionally has no runnable application.
