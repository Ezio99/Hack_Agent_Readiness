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
  - `META_MODEL_API_KEY` is the credential name for the Meta provider (decided 2026-10-27, replacing the earlier `MODEL_API_KEY` standardization so other providers can use distinct names; override with `--key-env`). A repository-root `.env` is loaded with
    `python-dotenv` (`override=False`, explicit path, no upward search; process env wins;
    `run` command only). `.env.example` corrected. Pinned `python-dotenv==1.2.4` was already in
    `requirements.lock` transitively and is now declared directly in `pyproject.toml`.
  - Browser Use starts Chromium with an inherited environment and Playwright's driver does the
    same, so the key *would* have been visible to those children. The runner now removes the
    variable while the browser/agent (and scripted smoke) run and restores it afterwards; regression-tested.
    **Limitation:** this mutates process-global `os.environ` and is supported only for single-run,
    nonconcurrent execution; concurrent experiments need explicit sanitized subprocess environments.
    Subprocesses started before the scrub context: only `git` (code-version lookup); the ephemeral
    storefront is an in-process uvicorn server, and no browser/Playwright process starts earlier.
  - Docs refreshed (this file, `AGENTS.md`, `COLD_START.md`, `README.md`, task index, Meta notes).
  - [Task 004](collaboration/tasks/004-first-live-meta-trial.md) specified (proposed) with a
    [report stub](collaboration/reports/004-first-live-meta-trial.md).

## Actual local verification (credential-free, this branch)
- Baseline on `main` before changes: 53 offline passed (4.95s); 4 browser passed (10.98s);
  CLI smoke completed, independent evaluation passed, model request count 0.
- After refinement: **62 offline passed (4.49s)** (53 + 9 in `tests/test_env.py`); **4 browser
  passed (11.06s)**; CLI smoke completed, evaluation passed; `uv pip check` clean.
  JUnit: `artifacts/verification/task004-*.xml` (untracked).
- `readiness run` with a dummy key and **without** `--allow-model-calls` stopped at setup with no
  model request. No authenticated Meta request, live agent trial or paid call has been made.
- **Stage A live probe (authorized, 1 request, 2026-10-27):** HTTP 200, model `muse-spark-1.3`, 31 total tokens (14 reasoning), no cost reported, but `content` was null at `finish_reason: length` (16-token cap consumed by reasoning). Auth/model access verified; visible-text check not met. See report 004. Stages B–D not started.
- **Stage A retry (separately authorized, 1 request):** 128-token cap, prompt `OK` → HTTP 200, `content` still null, `finish_reason: length`, 143 tokens of which 126 reasoning. Two attempts total; no further requests made. See report 004.
- **Stage A attempt 3 (separately authorized, 1 request):** `reasoning_effort: low`, 512-token cap → HTTP 200, `finish_reason: stop`, visible content `OK`, 15 prompt / 120 completion (110 reasoning) tokens, 1.41 s. Stage A objective met after three attempts; est. cumulative cost ≈ US$0.0012 (calculated, not provider-reported). Stages B–D not started.
- Not re-run here: GitHub Actions on this branch (see PR checks).

## Next (requires explicit user approval — nothing paid is authorized)
Task 004 (Stage A done; B–D pending approval): minimal authenticated request → structured-output probe → screenshot probe → one
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
