# Agent Readiness — Meta Global Hackathon

A small, freshly implemented shopping experiment:
**controlled storefront → feasible task → browser interaction → trace → independent evaluation**.

The original toy storefront (Tasks 003–007, unchanged) has twenty synthetic products with search, category/brand/price
filters and accessible detail pages. Listings show names, brands, categories,
prices and opaque links. Product IDs and stock availability appear on details
only. There is no checkout, account system, dashboard or composite score.

## Current state (2026-10-28)

> Historical note: the paragraphs below this block were written for the early foundation (PR #1) and the Task 004 branch; they are kept for provenance and are **not** a description of the current repository. See [STATUS.md](STATUS.md) for the authoritative state.

- **Measured evidence (Tasks 004–007):** authenticated Meta Muse Spark trials exist; Task 007 is a 30-run exploratory pilot on the 20-product toy storefront (29/30 independent PASS; descriptive, one site, one model) with the [consolidated report](collaboration/reports/007-availability-placement-pilot.md). Task 006 was stopped as an exploratory finding.
- **Dashboard (Tasks 008–009):** a standalone, static React dashboard under [`dashboard/`](dashboard/README.md) over the committed Task 007 data, deployed (public build, no replay data) at https://ezio99.github.io/Hack_Agent_Readiness/ . Replay JSON and raw traces are private and unpublished.
- **Task 010 (in review, credential-free):** a realistic synthetic electronics store `electronics-v1` (48 products, filters, sort, pagination, search, policy pages), two controlled design factors (stock on listings vs detail only; structured vs fragmented specifications), a domain-extensible task contract and four P0 task templates (ten fixtures) with independent oracles. See [docs/TASK_SUITE_DESIGN.md](docs/TASK_SUITE_DESIGN.md) and the [Task 010 report](collaboration/reports/010-realistic-storefront-task-suite.md). `readiness suite list|show|smoke` and `readiness serve-env` run it locally; **scripted smoke is not a model run**, and no model has been run on the new environment.
- **Not built / not claimed:** no live scanner, no readiness score, no real-website results.

## Install

Use Python 3.12 on Linux and [uv](https://docs.astral.sh/uv/). The exact dependency
set is pinned in `requirements.lock`; installation needs network access or a
suitable third-party package cache. No prototype code is required.

```bash
uv venv --python 3.12
uv pip sync requirements.lock
uv pip install --no-deps --no-build-isolation -e .
uv pip check
.venv/bin/python -m playwright install --with-deps chromium
```

Commands below assume `.venv/bin` is on PATH (`source .venv/bin/activate`). Browser
Use uses local Chromium; cloud sync, telemetry and extension downloads are off.
The complete environment includes `pydantic-settings` explicitly because the
pinned Browser Use package imports it without declaring that dependency.

## Credential-free workflow

```bash
readiness serve --port 8000
# In a second terminal, or omit --url to start an ephemeral local server:
readiness generate --seed 0 --kind discovery
readiness smoke --seed 0 --kind discovery --url http://127.0.0.1:8000/
readiness smoke --seed 7 --kind availability --available true
readiness smoke --seed 7 --kind availability --available false
python -m pytest -m 'not browser' -q
python -m pytest -m browser -q
```

Smoke uses a deterministic Playwright script with public task constraints. It
searches/filters, opens a detail link, reads the answer from the rendered page,
and invokes the independent evaluator. It also captures actual Browser Use DOM
and screenshots, raw HTML, accessibility, DOM snapshots and response payloads.
It never calls a model and is **not a successful live agent measurement**.

Browser checks need local TCP sockets, Chromium and its system libraries. They
fail visibly on infrastructure errors; they are not silently skipped. The CI
workflow runs offline tests, all three browser cases, and the CLI smoke without
API credentials, preserving credential-free artifacts even on failures.

## Reference agent and model configuration

The default `natural-shopping-v3` profile (v2 is preserved unchanged for reproducing earlier runs) uses **DOM + screenshots**,
a 1280×960 viewport, at most **10 agent steps, 120 seconds and 10 model request
attempts**, with three actions per step, an explicit `reasoning_effort: low` (sent only to the `meta` provider; Muse Spark always reasons and rejects `none`) and 4,096 completion tokens per response (reasoning tokens count toward this cap).
The model request timeout is 30 seconds and the agent step timeout is 60 seconds.
Cleanup may take up to another 15 seconds. Provider sampling defaults are retained;
SDK retries, extra failure-finalization calls, cloud sync and model judging are off.
Chromium sandboxing is explicitly disabled for this isolated loopback benchmark.

The runner loads one profile snapshot and passes that effective dictionary through
model setup, browser setup, agent execution and scripted smoke. CLI overrides
`--max-steps`, `--timeout` and `--max-model-requests` are resolved once and recorded.
The Python runner also accepts `profile_overrides` for settings such as viewport,
instructions, actions per step and completion-token cap; explicit limit arguments
win over those overrides. There is one reference profile, with no new site variants.

Artifacts retain the effective profile and `profile_hash`, plus a
`configuration_hash` covering the redacted profile/model/wire-parameter snapshot.
Limit changes produce distinct configurations; freeze one configuration within an
experiment. Profile v3 supersedes v2 for future runs (changes: `reasoning_effort` and the completion cap only); old run artifacts are kept.

Every model-adapter invocation consumes one request attempt, including failed or
cancelled invocations and framework retries. The guard blocks attempt N+1 before
calling the provider adapter. `model_request_count` and the configured limits are
saved even on errors, request exhaustion and timeouts. Scripted smoke makes zero
model requests; its step limit counts observation stages. Fresh sessions and
request counters are created for every run.

**These controls are not a monetary ceiling.** Prompt size, provider pricing,
provider-side behavior and unavailable usage reporting can affect charges, and
failed/cancelled requests may still be billed. Reported usage is retained without
inventing a cost estimate. Separate approval of model, provider, limits and possible
API expenditure remains necessary before any authenticated or paid trial.

Meta's official protocol and the Browser Use adapter have been checked offline;
**authenticated Meta access, strict schema and image probes have been verified; end-to-end agent success has not**. Read
[Meta integration evidence](docs/META-INTEGRATION.md) before planning live trials.

After separate explicit spending approval, provide a key through the environment
and run the following candidate configuration. The command can incur charges:

```bash
# Provide META_MODEL_API_KEY via the process environment or an untracked repository-root .env
# (copy .env.example; chmod 600). Process variables take precedence. Never commit credentials.
readiness run --provider meta --model muse-spark-1.3 \
  --base-url https://api.meta.ai/v1 --key-env META_MODEL_API_KEY \
  --kind discovery --seed 0 --max-steps 5 --timeout 60 \
  --max-model-requests 5 --allow-model-calls
```

`--provider openai-compatible`, `--model`, `--base-url` and `--key-env` configure
another explicitly selected endpoint. No provider fallback is automatic. Omitting
`--allow-model-calls` stops before model setup. A missing key produces a recorded
setup error without making a call. `--url` accepts only controlled loopback targets.
The framework is given only browser tools and the public prompt: no inventory,
evaluator, shell, file-reading, arbitrary JavaScript or general web-search tools.

## Answers and artifacts

Answers have the strict shape:

```json
{"product_id": "<ID read from detail>", "price_cents": 2400, "available": false}
```

`readiness evaluate answer.json --seed 0 --kind discovery` regenerates private
truth and grades the supplied answer. Use the original kind, seed and optional
`--available` pool for an availability task. Prices are integer AUD cents; all
three answer fields are mandatory. Grading checks inventory truth and task
constraints independently of the agent's own success claim or chosen UI path.

Each attempt creates a unique ignored `runs/<timestamp>-<id>/` directory:

- `run.json`: public task, generation parameters, inventory/code/profile hashes,
  versions, model/provider/endpoint, configured limits, actual model request count,
  execution status, final answer and evaluation.
- `trace.jsonl`: timestamped observations, model messages/responses, proposed
  actions, executed step results, navigation, reported usage and errors.
- PNG screenshots, framework history for agent trials, and `summary.md`.
- `model-response-NN.json` and `http_captures` (live runs): the sanitized, bounded model HTTP response captured
  *before* Browser Use parses it (raw content up to 20,000 characters, `finish_reason`, request id, usage including
  reasoning tokens, and an analysis of whether the text is JSON), plus `model_http_request` trace events (parameters,
  response-format SHA-256, message structure; no message text or credentials). This survives adapter parse errors.
  **Muse compatibility profile (opt-in, separate baseline).** The default strict profile (`natural-shopping-v3`) requires
the model response to be a single JSON object from its first character. `natural-shopping-v3-compat1`
(`readiness run --profile natural-shopping-v3-compat1 …`) is identical except that it names the versioned parser
`muse-prose-prefix-json-v1`, used only when the strict parse fails: it accepts exactly one single-line prose sentence
followed by exactly one complete JSON object with nothing after it, and only if that object validates against the
unchanged `AgentOutput` schema. The normalized text is a byte-identical slice (nothing is edited, repaired or
invented); everything else (several objects, trailing text, truncated or duplicate-key JSON, a multi-line or fenced
prefix, braces/brackets in the prefix, schema-invalid content) is rejected and ends the step as `model_output_error`.
Each response records raw protocol compliance and recovered-action validity separately
(`raw_protocol_compliant`, `recovered_action_valid`, run-level `protocol_compliance`), with the original and normalized
text in a `model_output_recovery` trace event. Results from the two profiles measure different things and must not
be pooled; report the raw compliance rate next to task success.

Terminal status: an unrecovered `model_output_error` is no longer overwritten by a later `request_limit` (the gate
tripping afterwards is the designed stop). The diagnostic cost estimate now counts the response schema (4 bytes per
token) and adds a 10% margin: the full-schema step-1 request is estimated at US$0.031 (measured prompt 9,443 tokens),
so a replay needs `--max-estimated-cost-usd 0.035`.

Diagnostic runs can pass `--expect-schema-sha256 <hash>` and `--max-estimated-cost-usd <usd>`: any outgoing request whose schema, parameters, system prompt, DOM, screenshot, task prompt or cost departs from the definition (or that carries a last-step instruction) is blocked before the network (`diagnostic_fidelity_violation`). Every request records its schema hash and `schema_narrowed`. Note: with `--max-steps 1` the only step is Browser Use's *last* step, which narrows the response schema to the `done` action; it is not equivalent to step 1 of a longer run (bound cost with `--max-model-requests` instead). A 200 response that cannot become the output model ends the run as `model_output_error`
  (subtypes: `malformed_json`, `null_content`, `length_without_content`, `schema_validation`), distinct from
  `infrastructure_error` (HTTP/timeouts/other) and from task outcomes. `browser_version` is recorded from the
  Chromium executable before the first model request.

Model screenshots are separate PNG files referenced from recorded messages.
Reported token usage is retained per response; unavailable usage is `null`,
including all scripted smoke runs. Agent action count counts framework result
entries (including completion); startup navigation is recorded separately. Smoke
counts scripted browser operations. These counts are not interchangeable.
Timeouts and failures retain partial evidence. Generated private truth, credentials
and run data are never served or committed. Run files can contain model/page text;
keep them local. **Inspect all raw artifacts before publication**, including
screenshots, model messages and page content. Text redaction removes the configured
API credential (including common URL/JSON encodings), sensitive header/key fields,
recognizable authorization strings and URL credentials. Provider errors are cleaned
before reaching framework history/logging. Model endpoints cannot embed credentials
or query parameters. JSON, JSONL and the readable summary use the same redactor.

Useful observations and PNG screenshots are retained. This is not a general PII
filter or an image/OCR redactor: screenshots and arbitrary page/model content may
still contain private information unrelated to the configured credential. Browser
tools never receive the model API key: the runner removes the key variable from the process
environment while Playwright/Chromium start and run, and restores it afterwards (regression-tested). Because Browser Use calls `load_dotenv()` at import time and finds this repository's `.env` from inside `.venv`, `dotenv.load_dotenv` is also made inert for the duration, so lazily imported Browser Use modules cannot put the key back (found and fixed during Stage D preflight). This temporarily mutates process-global
`os.environ`, so it is supported only for single-run, nonconcurrent execution; concurrent
experiments would need explicit sanitized subprocess environments instead. Do not automatically publish live or private run artifacts or treat redaction
tests as a blanket guarantee that arbitrary artifacts are safe. CI uploads only
credential-free evidence from the controlled synthetic storefront; this does not
establish that live/custom run artifacts are safe to share.

## Architecture and provenance

One Python package contains storefront, source inventory, public contracts,
private generator/evaluator, Browser Use adapter, runner, recorder and CLI. No
separate services or database are needed. Templates use explicit public-field
projections. The only HTTP routes are listing and single-product detail routes.

Pre-event planning documents and historical Tasks 001/002 came from
`Ezio99/Agent_Readiness`; their results are not hackathon evidence. No executable
source, tests, configurations or generated artifacts were copied from that
prototype. The fresh evidence report records actual checks and remaining blockers.
