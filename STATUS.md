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
- **Stage B (separately authorized, 1 request):** exact strict `AgentOutput` schema (SHA-256 `c80ef8b8…9a194`, 7,915 bytes) accepted; HTTP 200, `stop`, output valid and values exact. Usage 63 prompt / 994 completion (906 reasoning) — only ~3% headroom under the 1,024 cap, a risk for Stage D. Est. cumulative cost ≈ US$0.0055 (calculated). Stages C–D not started.
- **Stage C (separately authorized, 1 request):** deterministic 160×160 PNG (red square, white 7; SHA-256 `932e9a8a…2998d`) via `image_url` data URL with `detail: high`: HTTP 200, `stop`, content `color=red; digit=7` (strict match), 79 prompt / 261 completion (245 reasoning) tokens, 2.55 s. Est. cumulative live cost ≈ US$0.0067 (calculated). Stage D not started.
- **`natural-shopping-v3` implemented offline (approved):** `reasoning_effort: low` (Meta provider only) and 4,096 completion tokens; v2 file unchanged (byte-pinned by test). 107 offline + 4 browser tests passed; CLI smoke passed on v3 with 0 model requests. No authenticated call was made to test v3.
- **Stage D (separately authorized, 1 run) — FAILED:** `natural-shopping-v3`, seed 0 discovery. Offline preflight passed (and found/fixed a `.env` re-load leak). Live: 2 model requests, 9.14 s; both responses were non-JSON prose that failed `AgentOutput` validation, Browser Use stopped after 2 consecutive failures; no browser actions beyond the initial navigation; independent evaluator: FAIL (no answer). The visible text did identify the correct listing (`[174]`, Fern Home $29.00). Per-request tokens not captured (instrumentation gap). Est. cost ≈ US$0.025–0.035 (calculated; bound < US$0.065). No retry. See report 004.
- **Stage D diagnostic hardening (offline only, approved):** bounded sanitized HTTP response capture before parsing (survives adapter errors), `model_output_error` classification, browser version from the executable, git provenance no longer inherits the key. Offline interception shows the real Stage D request equals Stage B's except `max_completion_tokens` (4096 vs 1024) and the messages (byte-identical strict `response_format`, SHA-256 `c80ef8b8…`). Credential check with the real `.env` key: 0 of 7 spawned processes (chrome, node, git, ldconfig) received it. 122 offline + 6 browser tests passed; CLI smoke passed. No authenticated calls were made.
- Not re-run here: GitHub Actions on this branch (see PR checks).

## Next (requires explicit user approval — nothing paid is authorized)
Task 004 (Stages A–C passed; D ran once and failed — see report): minimal authenticated request → structured-output probe → screenshot probe → one
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
