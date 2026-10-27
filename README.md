# Agent Readiness — Meta Global Hackathon

A small, freshly implemented shopping experiment:
**controlled storefront → feasible task → browser interaction → trace → independent evaluation**.

The storefront has twenty synthetic products with search, category/brand/price
filters and accessible detail pages. Listings show names, brands, categories,
prices and opaque links. Product IDs and stock availability appear on details
only. There is no checkout, account system, dashboard or composite score.

**Validation:** all **24 tests pass**, including the three real-browser cases.
The credential-free CLI smoke navigates to a detail page and passes independent
evaluation. In this development environment those checks require approval-reviewed
execution outside the restricted sandbox. The first CI run exposed a browser-startup difference; a fix is being validated.
No live model trial has been performed. See [STATUS](STATUS.md) and the
[fresh task](collaboration/tasks/003-hackathon-first-agent-run.md).

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

The single versioned `natural-shopping-v1` profile uses **DOM + screenshots**,
a 1280×960 viewport, at most 30 agent steps, three actions per step, a 180-second
wall-clock budget and 4096 completion tokens per model response. Cleanup may take
up to another 15 seconds. The model's sampling defaults are retained and recorded. Chromium sandboxing is
explicitly disabled for this isolated loopback benchmark, matching the verified
local-container launch flags instead of relying on environment-dependent defaults.
Limit overrides are recorded in the effective configuration and its hash; do not
mix configurations within an experiment. Fresh sessions are created per trial.

Meta's official protocol and the Browser Use adapter have been checked offline;
**authenticated Meta support is not yet verified**. Read
[Meta integration evidence](docs/META-INTEGRATION.md) before planning live trials.

After separate explicit spending approval, provide a key through the environment
and run the following candidate configuration. The command can incur charges:

```bash
# Set MODEL_API_KEY outside repository files; never commit credentials.
readiness run --provider meta --model muse-spark-1.3 \
  --base-url https://api.meta.ai/v1 --key-env MODEL_API_KEY \
  --kind discovery --seed 0 --allow-model-calls
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
  versions, model/provider/endpoint, execution status, final answer and evaluation.
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
keep them local and review them before sharing. API keys used by the adapter are
redacted from saved text and configuration.

## Architecture and provenance

One Python package contains storefront, source inventory, public contracts,
private generator/evaluator, Browser Use adapter, runner, recorder and CLI. No
separate services or database are needed. Templates use explicit public-field
projections. The only HTTP routes are listing and single-product detail routes.

Pre-event planning documents and historical Tasks 001/002 came from
`Ezio99/Agent_Readiness`; their results are not hackathon evidence. No executable
source, tests, configurations or generated artifacts were copied from that
prototype. The fresh evidence report records actual checks and remaining blockers.
