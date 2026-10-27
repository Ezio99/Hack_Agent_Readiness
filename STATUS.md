# Hackathon Agent Readiness — status

**Date:** 2026-10-27 (Australia/Sydney)
**Repository:** `Ezio99/Hack_Agent_Readiness`
**Branch / PR:** `hackathon/task001` / [PR #1](https://github.com/Ezio99/Hack_Agent_Readiness/pull/1)
**Phase:** Requested review changes verified; awaiting final user review — do not merge

## Active approved work
The user approved the foundation subject to configuration propagation, model-call
budget controls, privacy/redaction regression coverage and fresh verification.
[Hackathon Task 001](collaboration/tasks/003-hackathon-first-agent-run.md) remains
the active specification. Do not merge PR #1; final user review is required.

## Review revision
- One effective profile is resolved once and passed explicitly to model, browser,
  agent and scripted smoke. Limit overrides and profile settings are applied, not
  merely recorded. Profile and configuration hashes are retained in artifacts.
- The sole profile advances to `natural-shopping-v2`: defaults of 10 steps,
  120 seconds, 10 model request attempts, and 2,048 completion tokens per response.
  Model/step timeouts are explicit. Setup consumes the same wall-clock budget.
- A per-run request gate blocks attempt N+1 before the provider adapter. Failed
  and cancelled invocations consume attempts; SDK retries are off. Limits and
  actual attempt counts persist through request exhaustion and timeouts.
- Credential registration/redaction covers nested headers, common key encodings,
  textual authorization, URL credentials, errors, JSON/JSONL and summaries.
  Provider errors are sanitized before framework handling. Useful observations
  and screenshots remain available; raw artifacts require inspection before publication.
- Storefront information boundaries, task truth and independent grading are unchanged.
  No dashboard, registry, score, additional site variant or behavior profile was added.

## Actual local verification of this revision
- Complete suite: **57 passed in 12.92s**;
  `artifacts/verification/pr1-review-final.xml`.
- Standalone browser suite: **4 passed, 53 deselected in 10.07s**;
  `artifacts/verification/pr1-review-browser.xml`. This includes the three boundary
  cases plus real viewport/step-limit override verification.
- CLI smoke: **completed; independent evaluation passed**;
  `runs/20261027T010440-8c0e0676c0bc/`. Recorded model request count: **0**.
- Offline tests exercise real SDK serialization with MockTransport and synthetic
  responses, or explicit framework/model stubs. Tests using the runner's live code
  path are still offline fixtures, not live experiments.
- No authenticated Meta request, live reference-agent trial or paid model call
  was made. Scripted smoke is wiring evidence, not live-agent success.

## CI and remaining work
Prior foundation CI passed, including [PR run 40427456658](https://github.com/Ezio99/Hack_Agent_Readiness/actions/runs/40427456658).
Both review-revision runs **passed** for `f253561815674efe3a4b80738e74786aa46f242b`:
[push CI](https://github.com/Ezio99/Hack_Agent_Readiness/actions/runs/40430687968)
and [PR CI](https://github.com/Ezio99/Hack_Agent_Readiness/actions/runs/40430691859).
PR CI passed 53 offline tests in 2.72s, four browser checks in 10.18s, CLI smoke
with independent evaluation, and artifact upload. The subsequent documentation
update records these results; its checks are linked from PR #1. The original runner-startup
failure and sandbox limitations remain documented in the
[evidence report](collaboration/reports/003-hackathon-first-agent-run.md).

Request/time/token controls **do not guarantee a monetary ceiling**. Meta account
access, hosted schema acceptance, model compatibility and live agent performance
remain unverified. After merge, the next milestone is separately approved Meta
authentication/compatibility validation and one controlled shopping-agent trial,
with explicit model, limits and potential expenditure approval.

Git operations and browser checks work through approval-reviewed execution.
Local user onboarding edits to `AGENTS.md` and `COLD_START.md` are preserved and
kept separate from this PR revision. Never import prototype implementation or
success claims; participant-specific event-rule verification remains pending.
