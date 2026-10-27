# Report 004 — Meta compatibility validation and first live trial

**Status: Stage A executed three times and Stage B once, each under separate authorization (2026-10-27); Stages C–D NOT executed.** Specification: [Task 004](../tasks/004-first-live-meta-trial.md) (proposed, unapproved).
Four authorized authenticated requests (Stage A attempts 1–3, Stage B once) were made; no other paid call or live agent trial has been made.

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

## Stage A attempt 3 (separately authorized, 1 request) — visible text returned
Configuration (per authorization, informed by the official docs: [chat-completions](https://dev.meta.ai/docs/protocols/chat-completions), [reasoning](https://dev.meta.ai/docs/reasoning), [pricing](https://dev.meta.ai/docs/pricing-rate-limits)): `POST https://api.meta.ai/v1/chat/completions`, body `{"model":"muse-spark-1.3","reasoning_effort":"low","max_completion_tokens":512,"messages":[{"role":"user","content":"Reply with exactly the text: OK"}]}`; one attempt, no retries, 30 s timeout, redirects off. Artifact `runs/20261027T034519-f308b00b94c5/probe.json` (untracked, sanitized; key absent). Request id `41d8bb5f-0fec-4ed0-b0e2-0f67be80c6c6`.

| Field | Attempt 1 | Attempt 2 | **Attempt 3** |
|---|---|---|---|
| `reasoning_effort` | omitted | omitted | **low** |
| `max_completion_tokens` | 16 | 128 | **512** |
| HTTP status | 200 | 200 | **200** |
| `finish_reason` | length | length | **stop** |
| Visible `content` | null | null | **`OK`** |
| Prompt tokens | 15 | 15 | 15 |
| Completion tokens | 16 | 128 | **120** |
| Reasoning tokens | 14 | 126 | **110** |
| Total tokens | 31 | 143 | 135 |
| Elapsed | 1.47 s | 1.35 s | 1.41 s |
| Provider-reported cost | none | none | none |

Result: probe `completed`. Authentication, model access, `reasoning_effort` acceptance, `max_completion_tokens`, usage reporting, and visible-text return are confirmed for this account. Observations (three data points, not general laws):
- Even at `low`, a trivial prompt used 110 reasoning tokens (91.7% of completion tokens) for 2 visible tokens' worth of output; the 16- and 128-token caps were therefore too small, consistent with the docs' statement that reasoning counts toward the cap. Reasoning cost appears roughly fixed near 110–126 here rather than scaling with the cap (attempt 1 hit its cap at 14), which weakens the earlier "expands to fill the cap" hypothesis.
- Implication for Stage D (hypothesis): the profile's 2,048 cap likely leaves room for reasoning plus action JSON, but harder prompts will reason more; `reasoning_effort` is not yet set by our agent adapter and Browser Use's default is unchecked.

Estimated cost (calculated from published rates, assuming "$" is USD and reasoning billed as output — **not provider-reported**): attempt 3 ≈ US$0.00053; all three attempts (45 input, 264 output tokens) ≈ US$0.0012 cumulative.

No further requests were made. Stages B, C and D remain unrun and need separate approval.

## Stage B — structured-output compatibility (separately authorized, 1 request)
Probe: `readiness probe --stage b --allow-model-calls` (`src/agent_readiness/probe.py`, independent of the agent request gate; frozen `natural-shopping-v2` profile and Browser Use adapter unmodified). Artifact `runs/20261027T035443-dfa0683d5382/` (`probe.json`, `schema.json`; untracked, sanitized, key absent).

Request: `POST https://api.meta.ai/v1/chat/completions`; `reasoning_effort: low`; `max_completion_tokens: 1024`; `response_format = {type: json_schema, json_schema: {name: agent_output, strict: true, schema: <exact real AgentOutput schema from SchemaOptimizer, unmodified>}}`; the authorized synthetic prompt (one `done` action, product_id `PROBE-0`, price_cents 100, available false). One attempt, no retries, 45 s timeout, redirects off. An offline test confirms the `response_format` equals what `ChatOpenAI.ainvoke` emits for the same model class.

| Evidence | Observed |
|---|---|
| Schema SHA-256 (canonical JSON, sorted keys) | `c80ef8b813abef0b2afd79c83a6f31e857c0101ea8730952ee78d61e65f9a194` |
| Schema size | 7,915 bytes canonical; 15 action variants; browser-use 0.11.13 |
| HTTP status / request id | **200** / `c3d3dd2e-8ec9-43ce-867d-21a039346481` |
| `finish_reason` | **stop** |
| Usage | prompt **63**, completion **994**, **reasoning 906**, total 1,057 |
| Elapsed | 4.69 s |
| Provider-reported cost | none (null) |
| Parse / validation | JSON parsed ✔; `AgentOutput.model_validate_json` ✔; exactly one `done` action ✔; values exactly `PROBE-0` / `100` (int) / `false` ✔ |
| Content (synthetic) | `{"action":[{"done":{"data":{"available":false,"price_cents":100,"product_id":"PROBE-0"}}}],"current_plan_item":0,"evaluation_previous_goal":"schema test","memory":"probe","next_goal":"complete","plan_update":null,"thinking":"return schema compliant done"}` |

**Result: all pre-stated success criteria met.** The hosted API accepted the exact strict schema (the documented depth-10 concern and the undocumented `default`/`minLength`/`minimum` keywords did not cause a rejection for this schema), and the response validated against the real Browser Use model.

Observations and caveats (single request; hypotheses are marked):
- **Reasoning budget risk (important):** reasoning used **906 of 994** completion tokens for a trivial request, against 110 in Stage A attempt 3 at the same `reasoning_effort: low`. The request finished at 994 of the 1,024 cap, i.e. **~3% headroom**. Structured output with this schema appears to induce much more reasoning (hypothesis; not isolated from prompt wording). The profile's 2,048-token cap may be insufficient for real, larger observations; a cap-exhausted response would return null content, as in Stage A attempts 1–2.
- Prompt tokens were 63 although the schema is ~2,000 tokens by size, so the schema appears not to be counted (or not billed) as input (hypothesis; billing not verified).
- This proves schema acceptance and conformance for one `done` action only. It does not show the model chooses correct browser actions from real DOM/screenshot context, handles the ~23.6k-character system prompt, or works across multiple steps; those need Stages C/D.
- Estimated cost (calculated from published rates, not provider-reported; assumes USD and reasoning billed as output): Stage B ≈ US$0.0043; all four requests (108 input, 1,258 output tokens) ≈ US$0.0055 cumulative.

No further requests were made. Stages C and D remain unrun and need separate approval. Open item for review: whether to raise the agent profile's completion cap / set `reasoning_effort` (would require a new profile version, `natural-shopping-v3`, and approval).
