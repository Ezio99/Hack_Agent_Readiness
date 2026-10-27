# Hackathon Agent Readiness — status

**Date:** 2026-10-27 (Australia/Sydney)
**Repository:** `Ezio99/Hack_Agent_Readiness`
**Branch / PR:** `hackathon/task004-prep` (preparation PR, open for review — do not merge automatically)
**Phase:** Foundation merged; next milestone prepared and **awaiting approval of paid-API testing**

## Completed (verified)
- The credential-free foundation is merged to `main` via [PR #1](https://github.com/Ezio99/Hack_Agent_Readiness/pull/1)
  (task [003](collaboration/tasks/003-hackathon-first-agent-run.md); evidence in the
  [foundation report](collaboration/reports/003-hackathon-first-agent-run.md)): storefront, seeded
  tasks, independent evaluator, Browser Use adapter with the single `natural-shopping-v2` profile,
  recorder with redaction, per-run model-request cap, CI.
- Preparation branch (this PR), 2026-10-27:
  - `MODEL_API_KEY` is the single credential name. A repository-root `.env` is loaded with
    `python-dotenv` (`override=False`, explicit path, no upward search; process env wins;
    `run` command only). `.env.example` corrected. Pinned `python-dotenv==1.2.4` was already in
    `requirements.lock` transitively and is now declared directly in `pyproject.toml`.
  - Browser Use starts Chromium with an inherited environment and Playwright's driver does the
    same, so the key *would* have been visible to those children. The runner now removes the
    variable while the browser/agent run and restores it afterwards; regression-tested.
  - Docs refreshed (this file, `AGENTS.md`, `COLD_START.md`, `README.md`, task index, Meta notes).
  - [Task 004](collaboration/tasks/004-first-live-meta-trial.md) specified (proposed) with a
    [report stub](collaboration/reports/004-first-live-meta-trial.md).

## Actual local verification (credential-free, this branch)
- Baseline on `main` before changes: 53 offline passed (4.95s); 4 browser passed (10.98s);
  CLI smoke completed, independent evaluation passed, model request count 0.
- After changes: **61 offline passed (3.77s)** (53 + 8 new in `tests/test_env.py`); **4 browser
  passed (9.89s)**; CLI smoke completed, evaluation passed; `uv pip check` clean.
  JUnit: `artifacts/verification/task004-*.xml` (untracked).
- `readiness run` with a dummy key and **without** `--allow-model-calls` stopped at setup with no
  model request. No authenticated Meta request, live agent trial or paid call has been made.
- Not re-run here: GitHub Actions on this branch (see PR checks).

## Next (requires explicit user approval — nothing paid is authorized)
Task 004: minimal authenticated request → structured-output probe → screenshot probe → one
browser-agent run (proposed limits 5 steps / 5 model requests / 60 s, no automatic retries) with
`muse-spark-1.3` as an unverified candidate. Pricing is unverified, so no dollar estimate exists;
the user's provisional A$30 overall budget is **not** authorization to spend.

## Unresolved
- The local `.env` has mode 644; recommend `chmod 600 .env` (a warning is printed on `run`).
- Meta account access, model availability, hosted schema acceptance, pricing and participant-specific
  event/reuse rules remain unverified.
- Request/time/token limits are not a monetary ceiling.
- `docs/PROJECT.md` and `docs/DECISIONS.md` retain pre-event wording and references to files that
  do not exist here (`Initial_prompt.md`, report 001); left unchanged as historical provenance.
