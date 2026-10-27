# Agent Readiness — Meta Global Hackathon

A small, freshly implemented shopping experiment:
**controlled storefront → feasible task → browser interaction → trace → independent evaluation**.

The storefront has twenty synthetic products with search, category/brand/price
filters and accessible detail pages. Listings show names, brands, categories,
prices and opaque links. Product IDs and stock availability appear on details
only. There is no checkout, account system, dashboard or composite score.

**PR review revision:** the local full suite passes **57 tests**, including four
real-browser cases. Standalone boundary checks and credential-free CLI smoke also
pass. [PR CI passed](https://github.com/Ezio99/Hack_Agent_Readiness/actions/runs/40430691859)
for this revision; previous CI evidence is retained in the report. No authenticated or paid model trial has been performed. See
[STATUS](STATUS.md), [PR #1](https://github.com/Ezio99/Hack_Agent_Readiness/pull/1),
and the [fresh task](collaboration/tasks/003-hackathon-first-agent-run.md).

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

The single versioned `natural-shopping-v2` profile uses **DOM + screenshots**,
a 1280×960 viewport, at most **10 agent steps, 120 seconds and 10 model request
attempts**, with three actions per step and 2,048 completion tokens per response.
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
experiment. Profile v2 supersedes v1 for future runs; old run artifacts are kept.

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
**authenticated Meta support is not yet verified**. Read
[Meta integration evidence](docs/META-INTEGRATION.md) before planning live trials.

After separate explicit spending approval, provide a key through the environment
and run the following candidate configuration. The command can incur charges:

```bash
# Set MODEL_API_KEY outside repository files; never commit credentials.
readiness run --provider meta --model muse-spark-1.3 \
  --base-url https://api.meta.ai/v1 --key-env MODEL_API_KEY \
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
tools never receive the model API key. Do not automatically publish live or private run artifacts or treat redaction
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
