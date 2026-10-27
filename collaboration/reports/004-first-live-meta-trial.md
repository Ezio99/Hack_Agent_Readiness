# Report 004 — Meta compatibility validation and first live trial

**Status: Stage A executed twice under two separate authorizations (2026-10-27); Stages B–D NOT executed.** Specification: [Task 004](../tasks/004-first-live-meta-trial.md) (proposed, unapproved).
Two authorized authenticated requests (Stage A, attempts 1 and 2) were made; no other paid call or live agent trial has been made.

## Completed preparation (2026-10-27)
Credential-free only; see `STATUS.md` for details.

| Check | Result |
|---|---|
| Baseline `pytest -m "not browser"` on `main` | 53 passed in 4.95s |
| Baseline `pytest -m browser` | 4 passed in 10.98s |
| Baseline `readiness smoke` | completed; evaluation passed; model requests 0 |
| After changes `pytest -m "not browser"` | 61 passed in 3.77s; 62 passed in 4.49s after review refinement (9 env/credential tests) |
| After changes `pytest -m browser` | 4 passed in 9.89s |
| After changes `readiness smoke` | completed; evaluation passed |
| `readiness run` with dummy key, no `--allow-model-calls` | `setup_error`, no model request |
| `uv pip check` | all installed packages compatible |

Finding: the model key would have been inherited by Chromium and the Playwright driver; the
runner now hides it from them during the agent run (regression test in `tests/test_env.py`).
Refinement after review: the scrub context now also wraps scripted smoke. It mutates
process-global `os.environ` and is supported only for single-run, nonconcurrent execution
(documented in code, README and STATUS). Launch-order audit: before the context, the only
subprocess is `git` (version lookup); the storefront is an in-process uvicorn server; Playwright
and Chromium start only inside the context. Re-run: 62 offline passed (4.49s), 4 browser passed
(11.06s), smoke with a dummy exported key completed and passed evaluation.

Residual: a same-user process can still read other sources of the key (e.g. the `.env` file).

## Planned, not done
Stages A–D of the task; probe runner implementation; pricing verification; user approval record.

## Stage A result (live, 1 request, authorized 2026-10-27)
Command: `readiness probe --stage a --allow-model-calls` (commit `e7decdc`); artifact `runs/20261027T033615-8628a2a58e9a/probe.json` (untracked, sanitized; key not present).

| Field | Observed |
|---|---|
| Endpoint / model requested | `https://api.meta.ai/v1/chat/completions` / `muse-spark-1.3` |
| Request attempts | 1 (no retries; 30 s timeout; redirects off) |
| HTTP status | **200** |
| Model identifier returned | `muse-spark-1.3` |
| Request id | `a8205068-e7e8-4d14-9cd0-ae268c7eb4db` |
| Elapsed | 1.47 s |
| `finish_reason` | `length` |
| `choices[0].message.content` | **`null`** |
| Usage | prompt 15, completion 16 (of which **14 reasoning tokens**), total 31; cached 0 |
| Provider-reported cost | none reported (null); no cost computed |

Interpretation (evidence-based):
- Verified: the key authenticates, `muse-spark-1.3` is accessible, `max_completion_tokens` is accepted, and the response shape is Chat Completions-compatible with usage reported.
- The probe's pass criterion (text in `choices[0].message.content`) was **not met**, so the probe recorded `status: failed`. The model appears to be a reasoning model: 14 of the 16 permitted completion tokens went to hidden reasoning, leaving no visible text at the length stop.
- Consequence to verify later, not assumed: completion-token caps must leave room for reasoning; the agent profile's 2,048 per-response cap may or may not suffice for structured agent actions.
- No retry was made (per authorization). Stages B–D were not started. Whether a second Stage A with a larger cap is warranted needs new authorization.
- Known gap: pricing remains unverified; usage counts are all we have toward the A$30 provisional budget.

## Limitations / unverified
Meta account access, model availability, schema/image acceptance, pricing, event reuse rules,
and agent capability are all unverified. Request/time/token caps are not a dollar ceiling.

## Stage A retry (attempt 2, separately authorized, 1 request)
Changes from attempt 1: `max_completion_tokens` 128 (was 16); prompt `Reply with exactly the text: OK`. Everything else unchanged (one attempt, no retries, 30 s timeout, redirects off, same endpoint/model, no fallback). Artifact `runs/20261027T033754-9c3008fec96f/probe.json` (untracked, sanitized).

| Field | Observed |
|---|---|
| HTTP status | **200** |
| Model identifier returned | `muse-spark-1.3` |
| Request id | `87482414-8ba2-429b-9b7f-cb355072d8ef` |
| Elapsed | 1.35 s |
| `finish_reason` | `length` |
| `choices[0].message.content` | **`null`** (no visible text) |
| Usage | prompt 15, completion 128 (**126 reasoning tokens**), total 143 |
| Provider-reported cost | none (null) |

Result: probe `failed` again by its criterion (no visible text). The trivial request consumed almost the entire completion allowance as reasoning in both attempts (14/16, then 126/128), leaving ~2 tokens for visible output — both below what `OK` needs given the stop. So raising the cap 8× did not change the outcome; reasoning appears to expand to fill the cap rather than being fixed-size (two data points; not a proven law).

Implications, unverified: (1) the agent profile's 2,048-token cap could also be consumed by reasoning, risking empty or truncated action JSON in Stage D; (2) the API may offer a reasoning-effort/budget control or a non-reasoning model setting — not tested; check Meta's documentation before another paid request; (3) Stages B–D remain unrun. Cumulative live usage so far: 31 + 143 = 174 tokens over two requests; cost unknown (pricing unverified, none reported).
Both Stage A attempts are retained; no further request was made.
