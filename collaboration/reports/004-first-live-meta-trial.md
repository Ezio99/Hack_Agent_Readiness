# Report 004 — Meta compatibility validation and first live trial

**Status: Stage A executed three times, Stages B, C and D once each, plus one diagnostic replay, all under separate authorizations (2026-10-27). Stage D FAILED (model output not parseable); no retry was made. The diagnostic replay returned valid JSON but did **not** faithfully reproduce Stage D's first request (see below).** Specification: [Task 004](../tasks/004-first-live-meta-trial.md) (proposed, unapproved).
Eight authorized authenticated requests (Stage A attempts 1–3, Stage B once, Stage C once, Stage D two requests within one run, diagnostic replay once) were made; no other paid call or live agent trial has been made.

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

## Stage C — screenshot / multimodal compatibility (separately authorized, 1 request)
Probe: `readiness probe --stage c --allow-model-calls`. Artifact `runs/20261027T040241-ffd66fad9f6f/` (`probe.json`, `stage-c-input.png`; untracked, sanitized; key and inline base64 absent). Frozen profile/adapter untouched.

Request: `POST https://api.meta.ai/v1/chat/completions`; `reasoning_effort: low`; `max_completion_tokens: 512`; one user message with a text part (`This is a synthetic product swatch. What color is the square and what digit is printed on it? Reply with exactly: color=<color>; digit=<digit>`) and an `image_url` part with a base64 PNG data URL and `detail: "high"` — the exact structure Browser Use serializes (offline test compares it to the adapter's output). One attempt, no retries, 30 s timeout.

Image: deterministic, generated by code (stdlib encoder), 160×160, 410 bytes, SHA-256 `932e9a8a2edb608826de0be0c85c2351d512a25bc454a75fc0d95fabc7f2998d` (verified against the pre-approved hash before sending); red square with a white "7"; only IHDR/IDAT/IEND chunks (no text/EXIF/time chunks); contains no private data.

| Evidence | Observed |
|---|---|
| HTTP status / request id | **200** / `f093e610-0e12-445e-a324-d7814b4b8e6e` |
| `finish_reason` | **stop** |
| Content | **`color=red; digit=7`** — strict match ✔ (lenient ✔) |
| Usage | prompt **79**, completion **261**, reasoning **245**, total 340; cached 0 |
| Reasoning share of completion | **93.9%** (245/261); 47.9% of the 512 cap — headroom flag not raised |
| Elapsed | 2.55 s |
| Provider-reported cost | none (null) |

**Result: success.** The hosted model accepted the `image_url` data URL including the `detail: "high"` field (undocumented in the image docs) and read both the color and the digit correctly.

Notes: (1) The usage object gives no image-token breakdown; 79 prompt tokens total for ~35 text tokens plus a 160 px image — the image share is **not measured** (a text-only estimate of the remainder would be an estimate only). (2) A 160 px image does not test cost/latency for the real 1280×960 screenshots Stage D sends (docs: ~1,300–1,500 tokens for a ~1280 px image); that remains unverified. (3) Reasoning again dominated completion tokens, even for a two-token answer.

Estimated cost, **calculated from published rates, not provider-reported** (assumes USD; reasoning billed as output): Stage C ≈ US$0.0012; all five live requests (187 input, 1,519 output tokens) ≈ **US$0.0067** cumulative. No further requests were made.

## natural-shopping-v3 — offline implementation (approved; no authenticated testing)
Changes (nothing else): new `profiles/natural-v3.json` = v2 with `id: natural-shopping-v3`, `reasoning_effort: "low"`, `max_completion_tokens: 4096`. `natural-v2.json` unchanged (byte-pinned by SHA-256 in a test); `profile(profile_id=None)` defaults to v3 and can still load v2; `run(profile_id=...)` selects either for reproduction. Observation method (DOM + screenshot), action schema, tools, tasks, evaluator, ground truth and step/time/request caps (10 steps / 120 s / 10 requests / 3 actions) are unchanged.

Pass-through: Browser Use's `ChatOpenAI` sends `reasoning_effort` only for model names in its `reasoning_models` list (OpenAI names only), so `create_model` now sets `reasoning_models=["muse-spark"]` and `reasoning_effort=<profile value>` **only for provider `meta` and only when the profile defines it** (v2 behaviour unchanged). The adapter then also omits `temperature`/`frequency_penalty` (already unset). Values are validated against `minimal|low|medium|high`; `none` (HTTP 400 on Spark), `max`/`xhigh`, empty, non-string are rejected before any model is constructed. `run.json` records the effective `reasoning_effort` in `model_parameters`; profile and configuration hashes change versus v2.

Verification (offline only): new `tests/test_profile_v3.py` (14 cases): v2 byte-identity; v3 differs from v2 in exactly `id`, `max_completion_tokens`, `reasoning_effort`; real-adapter wire body with the full AgentOutput schema + image shows `reasoning_effort: low`, `max_completion_tokens: 4096`, no `temperature`/`frequency_penalty`; v2 wire unchanged; non-Meta provider gets no `reasoning_effort`; invalid values rejected pre-model (runner records `setup_error`, 0 requests); distinct hashes; limits unchanged; timeout invariants. Results: **107 offline passed (6.17 s), 4 browser passed (10.92 s)**, CLI smoke passed on v3 (0 model requests). Not verified: that the hosted API accepts a v3-shaped *agent* request (Stage B/A probes covered `reasoning_effort: low`, the schema and the image separately, not combined, and not at 4,096 tokens).

### Timeout interactions and risks before Stage D
- **Latency vs model timeout (30 s):** observed generation ≈ 1.4 s + ~3.75 ms per completion token (Stage A attempt 3 vs Stage B; two points, extrapolated). A full 4,096-token response ≈ **16–17 s** → ~1.8× margin under the 30 s model timeout, extrapolated beyond the largest observed completion (994 tokens). Prompt prefill for the real ~6k-token system prompt + DOM + 1280×960 screenshot is unmeasured and adds to this. A timeout would be recorded as infrastructure error, and the timed-out request still consumes an attempt and may still be billed. The 30 s model timeout was **not** changed (outside the approved scope); raising it (e.g. 60 s, below the 60 s step timeout) is a decision for you.
- **Proposed Stage D run budget of 60 s total is likely binding:** five sequential model calls at ~2–17 s each plus browser actions and observation can exceed 60 s; the run would end `timeout` with partial evidence. The profile default is 120 s. Recommend deciding the Stage D `--timeout` explicitly (120 s suggested) rather than 60 s.
- **Reasoning budget:** reasoning was 906 tokens in the structured-output probe (Stage B). 4,096 gives ~4× the Stage B headroom, but real observations may reason more; cap exhaustion yields null content (a failed step, not a crash).
- **Cost bound for Stage D (calculated, not provider-reported):** worst case per request ≈ 15k input tokens ($1.25/M) + 4,096 output tokens ($4.25/M) ≈ US$0.036; 5 requests ≈ **US$0.18**. Assumes the 15k-token input bound (unmeasured: real screenshot/DOM/system prompt size) and published, unverified-currency pricing; the request/step/time caps are not a monetary ceiling.
- **Unverified:** combined schema + image + large-context requests; multi-step behaviour; real screenshot token cost; whether Browser Use handles a 200 with null content gracefully (it raises a parse error → recorded failure).

### Readiness for Stage D
Technically ready pending your decisions: (1) approve v3 for the trial, (2) choose `--timeout` (60 s as proposed vs 120 s default) and whether to raise `model_timeout_seconds`, (3) confirm limits (5 steps / 5 requests) and a spend authorization. No Stage D request has been made.

## Stage D — first live shopping-agent trial (separately authorized, 1 run) — FAILED
Command: `readiness run --kind discovery --seed 0 --max-steps 5 --max-model-requests 5 --timeout 120 --allow-model-calls` (defaults: provider `meta`, model `muse-spark-1.3`, profile `natural-shopping-v3`). One run, no retry, no further requests afterwards. Artifact `runs/20261027T041445-e323c1ab6cae/` (untracked; `run.json`, `trace.jsonl`, `history.json`, two screenshots, `summary.md`; sanitized; key absent).

### Offline preflight (all passed before the run; no model calls)
1. **Wire values:** `create_model` for v3 yields `reasoning_effort="low"`, `max_completion_tokens=4096` (adapter attributes + wire tests); recorded `model_parameters` confirm. The HTTP body of the live request was not separately captured; this rests on the wire tests.
2. **Limits:** a real-runner/real-Chromium/real-storefront run with a fake model hit exactly 5 steps and 5 model requests and stopped (gate + step cap); timeout and request-gate tests pass (108 offline + 4 browser tests, CLI smoke).
3. **Hidden retries:** OpenAI SDK `max_retries=0` (checked on the live client object, timeout 30 s); no fallback LLM; Browser Use message compaction triggers every 15 steps (not reachable in 5); empty-action re-asks and any extra LLM call go through the wrapped model and the request gate. Browser Use's own per-step failure handling can re-ask, bounded by the gate. Residual: a request the gate allows can still be billed if the provider processes it and the client times out.
4. **Cost:** real first-call request size measured: system prompt 23,590 chars + user state 3,627 chars + one ~83 KB 1280×960 PNG ≈ 8–10.5k input tokens/request (chars/3–4 plus ~1.5k image, per docs). Bound used: 15k input + 4,096 output per request → ≈ US$0.036 × 5 ≈ US$0.18 < US$0.25 authorized.
5. **Ground truth:** the preflight's captured prompts/DOM do not contain the private expected product id; listings show names/brands/categories/prices only (IDs and stock are detail-only). (The phrase "GROUND TRUTH" in the prompt is Browser Use's own wording about screenshots.)

**Preflight found and fixed a credential leak (committed before the run):** importing `browser_use` calls `load_dotenv()` and finds this repository's `.env` from inside `.venv`; modules imported lazily *during* the run re-loaded the key after the scrub had removed it, so Chromium could have inherited it. `scrubbed_environment` now also makes `dotenv.load_dotenv` inert while active; verified `key_in_env == false` on every agent-side call in the preflight, with a regression test replicating the lookup. This was a risk to credential hygiene, not an observed exfiltration (Chromium has no tool access to its environment).

### Result
| Item | Observed |
|---|---|
| Task | `synthetic-v1-discovery-0-8ba7403199`: "Find the Fern product in Home costing at most $29.00 AUD. Return its product ID, price in integer cents, and whether it is available." |
| Hashes | inventory `e61614b81af8ed6f6c445e650a7d4beae942735e4ffbbf5df7cd67f5517c78b9`; profile `1bffb722f8b5a7ffee6f7f8f7d952a341c47bc2571e9352790be45610b267c45`; configuration `b363b22fdda7698887f6dc4aa1de47dacb12a56c6a26f65f8dda988ca016f66b`; code `650753cfda5a2f7fa1f32e1ed2396d0a49b7f22e8f0ab3b8dc6f6ee6a09d9eb0`; git `42a5cfdf…` (clean tree) |
| Independent evaluator | **FAIL** — "Malformed answer" (no answer was produced) |
| Recorded status | `infrastructure_error`, `stop_reason: ModelProviderError` (see misclassification note) |
| Model requests / steps / elapsed | **2** of 5 / **2** of 5 / **9.14 s** of 120 s |
| Request timings (model_request→model_error) | request 1: 2.64 s; request 2: 3.01 s |
| Browser actions executed | **none** beyond the harness's initial `navigate` to the storefront; the page never changed (the two model-input screenshots are byte-identical, 83,161 bytes) |
| Per-request tokens / finish reason | **not recorded** (see gap) |
| Provider-reported cost | none available |

What happened: both responses returned HTTP success but the adapter's `AgentOutput.model_validate_json` rejected the content as **not JSON**: it began with prose (`Found the Fern Home item…` and `Found the match — open…`) and ended with `…click its link."}` / `…link index 174."}`. Browser Use counted two consecutive failures (`max_failures=2`) and stopped; the 5-step/5-request caps were not reached. The raw content was not retained (see gap), so the exact malformed text and whether `response_format` was ignored, wrapped, or the model leaked reasoning into `content` **cannot be determined from this artifact** (hypotheses only).

Evidence the model did read the page correctly: the visible fragments say it found the Fern Home item and to "click its link index 174"; in the DOM sent to the model, `[174]` is the `Linen Cushion · Fern · Home · $29.00` listing — the correct target for this task. So the observation (DOM + screenshot) appears sufficient to identify the product; the failure was in output conformance, not in understanding the page. The agent never reached a detail page, so ID/availability retrieval and grading of a real answer remain unobserved.

### Findings / friction
1. **Structured-output conformance failed under real conditions** although Stage B (same strict schema, trivial prompt) passed: with the full ~27k-character prompt + screenshot, `reasoning_effort: low`, the content was not schema-valid JSON in 2/2 requests. Cause unverified.
2. **Instrumentation gap:** when the adapter raises while parsing, `RecordingModel` loses the HTTP response (raw content, `usage`, `finish_reason`). Per-request token usage required by the authorization therefore could not be recorded, and `run.json.usage` is null. The harness needs a lower-level capture (e.g. HTTP response hook) that saves the sanitized raw response before parsing.
3. **Misclassification:** a model-output-format failure is labelled `infrastructure_error`; it should be a distinct class (e.g. `model_output_invalid`).
4. Browser Use's `max_failures=2` ended the run after two failed requests; we cannot tell whether a later request would have conformed.
5. Chromium version was not recorded (`browser_version: null`) because the observation callback never ran.

### Estimated cost (calculated, NOT provider-reported)
Input ≈ 8.3–10.5k tokens × 2 requests ≈ 17–21k tokens ≈ US$0.021–0.026. Output unknown; inferred from latency at the observed ~3.75 ms/token (+1.4 s base) as roughly 300–450 tokens per request, so ≈ US$0.003–0.004 (even if both used the full 4,096-token cap: ≤ US$0.035). **Stage D estimate ≈ US$0.025–0.035, bounded < US$0.065**, well under the US$0.25 authorization. Cumulative estimated live spend across all stages ≈ US$0.035–0.045. Assumes published USD pricing; provider reports no cost.

### Status
Stage D was a single bounded run and failed; it must not be retried without new authorization. No further authenticated requests were made.

## Stage D diagnostic hardening (offline only; no authenticated or billable requests)
Approved after the failed Stage D trial (an integration failure, not a website-readiness result). The schema, system prompt, storefront, evaluator, `natural-shopping-v3` configuration and token limits were **not** changed.

### Changes
1. **Response capture before parsing** (`src/agent_readiness/capture.py`): httpx event hooks on the model client write `model_http_request` / `model_http_response` trace events and `model-response-NN.json` (raw content ≤ 20,000 chars, finish reason, request id, usage with reasoning tokens, body size, elapsed time, and a content analysis: null / JSON / non-JSON, whether it starts or ends with a brace, and whether a valid JSON object is embedded after a prose prefix). Non-200 bodies are kept (≤ 2,000 chars). Everything passes through the existing redactor; request events record structure (parameters, response-format SHA-256, message part types and sizes), never message text or the credential.
2. **Works when the adapter raises:** after an exception `RecordingModel` classifies the captured response, appends its usage (marked `http_capture_after_error`, so run-level usage is no longer null), re-writes the response file with the classification, and emits `model_output_error`. Regression tests (`tests/test_capture.py`, real `ChatOpenAI` + real `AgentOutput` schema + mock transport): prose followed by JSON (Stage D-like), null content with `length` and with `stop`, valid JSON failing `AgentOutput` validation (error summary holds locations/types, not input values), HTTP 500 (one call, no SDK retry, stays infrastructure), success path, bounded size, request-event contents, credential redaction.
3. **`model_output_error` status** (`classify_outcome`): a 200 response that cannot become the output model ends as `model_output_error` with `stop_reason: model_output_error:<subtype>`; HTTP errors/timeouts remain `infrastructure_error`; task outcomes are unchanged. A later successful `done` still wins.
4. **Browser version** is recorded from `<chromium> --version` before the first model request (no new dependencies); the CDP product string still overrides it after the first observation. Offline run: `Google Chrome for Testing 145.0.7632.6` / `Chrome/145.0.7632.6`.
5. **Provenance** (`git` lookup) no longer inherits the model credential.

### Request-construction comparison (offline interception of the real runner, Chromium and storefront; mock transport)
| Field | Stage B (success) | Stage D wire request |
|---|---|---|
| Top-level keys | `model, messages, response_format, reasoning_effort, max_completion_tokens` | identical set; no extra parameters, no `temperature`/penalties/`stream` |
| `model`, `reasoning_effort` | `muse-spark-1.3`, `low` | identical |
| `response_format` | `json_schema`, name `agent_output`, `strict: true`, schema SHA-256 `c80ef8b813abef0b2afd79c83a6f31e857c0101ea8730952ee78d61e65f9a194` (7,915 B) | **byte-identical** (also identical across requests) |
| `max_completion_tokens` | 1,024 | **4,096** (v3) |
| Messages | one user text (253 chars) | `system` (23,590 chars) + `user` [text 3,233 chars (history + DOM), text 19 chars, `image_url` data URL, `detail: high`] |
| Middleware effects | — | none beyond the above; SDK `max_retries=0`; request timeout 30 s; endpoint `https://api.meta.ai/v1/chat/completions` |
Regression test: `tests/test_request_construction.py` (browser-marked). **Verified:** the only differences between the passing Stage B request and the Stage D request are the v3 token cap and the message content.

### Credential propagation review
Root cause of the earlier gap (recorded above): Browser Use runs `load_dotenv()` at import time and finds the repository `.env` from inside `.venv`; lazily imported modules re-added the key after the scrub. The fix keeps `dotenv.load_dotenv` inert while the scrub is active. Added: (a) a hermetic test replicating the lookup with a fake module (mutation-checked: fails without the fix); (b) a browser-marked test spying on **every** `subprocess.Popen` during a real mocked live run with a sentinel key (asserts Chromium, the Playwright `node` driver and `git` all ran and none received the key name or value; mutation-checked: fails if the scrub is removed); (c) a manual run with the **real** `.env` key loaded as the CLI does: 7 spawned processes (`chrome`, `node`, `git`, `ldconfig`), **0** with the key name in their environment, **0** with its value; the key was restored for the caller afterwards. Limits: process-global and single-run only (documented); it addresses subprocess environments, not other ways code in the same process could read `os.environ` (none are exposed as agent tools).

### Test results
122 offline tests passed (6.13 s) and 6 browser tests passed (32.07 s); CLI smoke passed (independent evaluation passed, 0 model requests). No authenticated requests were made in this phase. One CI run initially failed `test_failures_and_timeouts_preserve_records`: tests used a 0.05 s wall-clock budget that includes git/hash setup, so a slow runner expired it before the synthetic failure ran; the budgets in three timing-sensitive tests were raised (still shorter than their 1 s sleeps) and CI then passed on both runs.

### What the Stage D evidence does and does not show
**Verified facts:** the Stage D and Stage B requests differ only in token cap and messages; the strict schema reached the provider unchanged; two of two live responses were not parseable JSON (they began with prose and ended `…"}`); the adapter parses the raw `message.content` directly (`model_validate_json`), with no client-side transformation; the model's visible text identified the correct listing; the run ended by Browser Use's two-consecutive-failure rule at 2 of 5 requests/steps. **Not recorded in Stage D (now fixable):** raw content, finish reason, request id and token usage.

**Hypotheses, most likely first** (none verified):
1. *Prose preamble before an otherwise valid JSON object.* Both visible fragments end with `…"}`, and Stage B's JSON ends with the final string key (`"thinking": "…"}`); a response that is narration/reasoning-like text followed by the JSON object would fit both the beginning and the ending. If the provider emits reasoning-like text in `content` for long agentic prompts, that would be a provider/model-behaviour issue rather than a schema issue. The new capture records `embedded_json.offset` and `trailing_chars`, which would confirm or refute this directly.
2. *Structured-output enforcement not applied (or only partially) under this context size / reasoning combination,* producing free text.
3. *Non-deterministic, context-dependent failure* (Stage B passed on a trivial prompt; two failures on the real prompt do not establish a rate).
Ruled out by the offline comparison: schema mutation, response-format differences, a client-side transformation, SDK retries.

### Proposed next experiment (needs separate approval; not executed)
**One live request, no retries:** run the exact Stage D first step with capture enabled — `readiness run --kind discovery --seed 0 --max-steps 1 --max-model-requests 1 --timeout 120 --allow-model-calls` (profile v3, same prompt, DOM, screenshot, schema, `reasoning_effort: low`, 4,096 cap). Estimated cost ≈ 8–10.5k input tokens (≈US$0.010–0.013) plus ≤ 4,096 output tokens (≤ US$0.0174), so < US$0.03 worst case (calculated, not provider-reported). Record: raw content, finish reason, request id, prompt/completion/reasoning tokens, content analysis. Decision rule: (a) pure valid JSON → Stage D's failure is intermittent; plan a small repeated-request characterization; (b) prose then valid embedded JSON (`offset > 0`) → provider/model preamble leak, which would require a deliberate, approved decision on output handling (any tolerance would change what is being measured); (c) prose only → enforcement not applied, examine reasoning tokens vs cap; (d) null content/`length` → cap exhaustion. Hypothesis 1 predicts (b).

## Diagnostic replay (separately authorized, exactly 1 request) — valid JSON, but NOT a faithful replay
Command: `readiness run --kind discovery --seed 0 --max-steps 1 --max-model-requests 1 --timeout 120 --allow-model-calls` (profile v3; capture enabled). Artifact `runs/20261027T044331-4dce974fdee2/` (untracked, sanitized; key absent). Git clean at HEAD `b4ff408d`.

**Preflight (offline, passed before the request):** capture and redaction tests (credential in content and errors redacted); the gate stays effective when parsing raises (limit 1: the first call raises a parse error, the next invocation is blocked before the transport — exactly one HTTP call, `request_limit`); a mocked run with this exact command line made exactly 1 call, executed nothing from a malformed response, and recorded the response file; 123 offline + 7 browser tests passed.

### Result
| Item | Observed |
|---|---|
| Model requests / steps / elapsed | **1** of 1 / 1 / 8.73 s total run |
| HTTP status / request id | **200** / `c9c795d5-0a1c-46e0-8ad2-a9824178bfe9` |
| `finish_reason` | **stop** |
| Request latency | 4.96 s |
| Usage (provider-reported, captured) | prompt **8,128**, completion **519**, **reasoning 341** (65.7% of completion), cached 0 |
| Provider-reported cost | none |
| **Parse classification** | **(1) Valid JSON from the beginning** (655 chars, `kind: json`); passed `AgentOutput` validation; no `model_output_error` |
| Answer produced | `{"product_id": "linen-cushion", "price_cents": 2900, "available": true}` |
| Independent evaluator | **FAIL** — "Unknown product ID" |
| Sanitized raw response | `model-response-01.json` (content, finish reason, request id, usage, analysis) |

Content (verbatim fields): a single `done` action with the answer above; `thinking`: "Need product detail for ID and availability but max_steps reached. Candidate is Linen Cushion at $29.00 = 2900c. Provide guess ID and mark incomplete."; `memory`: "…product_id and availability not verified due to step limit."

Classes 2–5 (prose + JSON, prose only, null/truncated, other) were **not** observed.

### Why this is not a faithful replay (my design error, now verified)
With `--max-steps 1` the single step is Browser Use's **last** step: `_force_done_after_last_step` narrows the response schema to the `done` action only and adds a last-step instruction to the context. Evidence from this run's own capture: wire `response_format` schema SHA-256 `7964acb55bed223f00dc3de611c026b455f264a00c21cabf5e127b8e10025dc1`, **1,274 bytes**, versus the Stage D / Stage B schema `c80ef8b813abef0b2afd79c83a6f31e857c0101ea8730952ee78d61e65f9a194`, **7,915 bytes** (15 action variants); the recorded output schema lists only `DoneActionModel`; the model said it was at the step limit. I proposed `--max-steps 1` without checking this, so the request differed from Stage D's step 1 in schema and in context. (Prompt was 8,128 tokens, consistent with my 8–10.5k estimate.) A regression test now asserts the narrowing.

### What this does and does not show
**Verified:** a done-only-schema request with the same prompt, DOM, screenshot, model and v3 settings returned valid JSON immediately; the capture/classification/gate machinery works against the live API; the model, forced to finish, fabricated a plausible product ID (`linen-cushion`) instead of reading it from a detail page (IDs are detail-only), which the independent evaluator correctly rejected. This is **not** a shopping-trial result (the step budget forbade navigation) and says nothing about website readiness.
**Not verified:** why Stage D's two full-schema responses were non-JSON. The replay does not test hypotheses 1–3: it used a different, much smaller schema. Evidence is consistent with — but does not show — the failure being related to the full 15-variant schema or to the earlier steps' context; it is equally consistent with intermittency.
**Latency note:** 519 completion tokens took 4.96 s at an 8.1k-token prompt (~9.5 ms/token including prefill), slower per token than my Stage A–B extrapolation (~3.75 ms/token); a full 4,096-token completion could therefore take ~15–40 s against the 30 s model timeout. The earlier "~1.8× margin" statement should be treated as optimistic.

### Estimated cost (calculated, NOT provider-reported)
8,128 input × $1.25/M + 519 output × $4.25/M ≈ **US$0.0124**. Cumulative estimated live spend across all requests ≈ US$0.05–0.06 (assumes published USD pricing; the provider reports no cost).

### Smallest justified next change
Replay at the **same step budget as the failed trial**, bounding cost with the request gate instead of the step cap: `--max-steps 5 --max-model-requests 1` (same profile, same full schema at step 1, same prompt/DOM/screenshot, one request; the gate then blocks any second request before the provider, ending as `request_limit`). If the response is valid JSON the adapter will execute that one action as it normally would (nothing is extracted or altered). Expected cost < US$0.03 worst case. This needs separate authorization. As a harness change (offline, no approval needed beyond review): flag in `run.json` when a request's response-format schema hash differs from the profile's full-schema hash, so a last-step narrowing cannot silently confound a diagnostic again.
