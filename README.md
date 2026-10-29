# Agent Readiness — Meta Global Hackathon

A diagnostic platform for **how well AI agents can use a website**: *scan → find friction → recommend a change → modify the site → rescan → measure whether it helped.* Outcomes are always graded by an independent oracle, not by the agent's own claim, and evidence stays separated into **observed website properties**, **agent execution**, **proposed interventions** and **measured effects**.

Current state, budget and what is (not) authorized: [STATUS.md](STATUS.md). Architecture, execution paths, frozen artifacts and technical debt: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md). Orientation for contributors/agents: [COLD_START.md](COLD_START.md), [AGENTS.md](AGENTS.md).

## What is here
| area | where | what it does |
|---|---|---|
| Site audit + recommendations | `src/agent_readiness/remediation/` | black-box HTTP probe → findings → rule-based recommendation library → re-audit lifecycle → measured effects (derived view only) |
| Reference agent | `agent.py`, `capture.py`, `compat.py`, `profiles/` | Browser Use agent with frozen profiles, pre-send fidelity guard and sanitised model-response capture (Meta Muse Spark via an OpenAI-compatible endpoint) |
| Controlled environments + tasks | `environments/electronics/`, `suite/` | synthetic electronics store (48 products, controlled website factors) with catalogue-only oracles |
| Protected scanner service | `scanner/` | invitation-gated FastAPI/SQLite service: scans, comparisons and site audits of *registered* targets; live inference off by default |
| Experiments | `experiments/` (Task 012), `remediation/experiment.py` (Task 015), `webarena/` (Task 014) | frozen, hash-approved, budget-gated drivers (see ARCHITECTURE) |
| Safety primitives | `ledger.py`, `spend_gate.py`, `budget.py` | durable reserve-before-send ledger, per-request spend gate, A$ programme budget |
| Dashboard | `dashboard/` | static React app over committed data + the scanner/site-audit client |
| Historical single-site experiment (Tasks 003–007) | `storefront.py`, `runner.py`, `pilot.py`, … | byte-pinned for reproducibility — documented in [docs/archive/README-legacy-runner-through-2026-10-29.md](docs/archive/README-legacy-runner-through-2026-10-29.md) |

## Install
Python 3.12 on Linux and [uv](https://docs.astral.sh/uv/). The exact dependency set is pinned in `requirements.lock`.
```bash
uv venv --python 3.12
uv pip sync requirements.lock
uv pip install --no-deps --no-build-isolation -e .
uv pip check
.venv/bin/python -m playwright install --with-deps chromium
```
`pydantic-settings` is declared although this repository never imports it: the pinned `browser-use` imports it without declaring it. Browser Use uses local Chromium; cloud sync, telemetry and extension downloads are off. `uv.lock` is deliberately untracked.

## Credential-free quick start (no model call, no cost)
```bash
readiness suite list                                   # environments, variants, tasks
readiness suite smoke --all-variants                   # scripted navigator + independent oracle (NOT a model run)
readiness serve-env --variant availability=detail,specs=structured --port 8001   # in another shell
readiness audit http://127.0.0.1:8001 --allow-private --objective "every in-stock ANC headphone under A\$250"
readiness scanner invite --label me && readiness scanner serve --demo-target     # API + managed demo target
uv run python scripts/remediation_loop_demo.py         # audit -> recommend -> operator change -> independent re-audit, over the API
readiness remediation-experiment run --manifest collaboration/experiments/task015/pilot/manifest.json \
  --audit collaboration/experiments/task015/pilot/audit-baseline.json --root runs/dry --mode mock   # mock dry run only
python -m pytest -m 'not browser' -q && python -m pytest -m browser -q
```

## Live (paid) runs
Never without the owner's explicit approval of the exact plan/manifest hash. Credentials come from `META_MODEL_API_KEY` in the environment or an untracked repository-root `.env` (`.env.example`; `chmod 600`); process variables win; the value is never printed, logged or committed, and is hidden from browser child processes. Every live path is gated by `--allow-model-calls`, a durable per-request reservation (`spend_gate.py`), per-run and per-stage caps, and the A$ programme ceiling. Calculated costs use verified published prices and are **not** bills. Raw traces and screenshots can contain model/page text: keep them local and inspect before any publication.

## Provenance
Hackathon implementation starts 2026-10-27. The earlier repository `Ezio99/Agent_Readiness` is a pre-event prototype; no executable source, tests, configuration or generated artifacts were copied from it. Historical pre-event task specs (`collaboration/tasks/001`, `002`) are labelled as such. Meta integration evidence: [docs/META-INTEGRATION.md](docs/META-INTEGRATION.md).
