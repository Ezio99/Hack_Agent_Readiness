# Agent Readiness diagnostic dashboard (Task 008, Stage A)

A standalone, static React + TypeScript + Vite app that explains **what a Meta Muse Spark shopping agent did on a controlled storefront, why, and what a site owner could change**, using the reconciled Task 007 evidence. It has **no backend, no API key and no live model calls**; every number is computed in the browser from the committed per-run data and is labelled as *recorded experiment data*. Costs are *calculated estimates* from provider-reported tokens at published prices, not bills.

## Run it

Requires Node 20+ (developed on Node 22 / npm 10). From the repository root:

```bash
cd dashboard
npm install            # installs from package-lock.json
npm run dev            # http://localhost:5173 (hot reload)
npm run build          # type-checks (tsc --noEmit) then builds to dashboard/dist (ignored by Git)
npm run preview        # serves the production build at http://localhost:4173
npm test               # vitest: data integrity, headline reconciliation to Report 007, rendered-page checks
npm run typecheck
```

Pages: **Overview** (headline results, what was tested, three-way attribution of effort, recommendation, Meta Muse Spark's role, limits), **Scope comparison** (Kitchen, Bags, Home, Outdoors, Fern or all; arm A vs B table, charts, run-level evidence) and **Evidence & method** (findings, the run 27 case, definitions, limitations, provenance).

## Data contract

The app imports `../collaboration/reports/007-pilot-data/per-run-reconciled.json` directly (30 runs; produced by `reconcile.py` from the preserved run artifacts) and derives every figure in `src/lib/metrics.ts`. Nothing numeric is hand-maintained: the only constants in `src/data/task007.ts` are provenance strings (execution commit `969d7d4`, schedule hash, model, prices), which `src/lib/report.test.ts` checks against Report 007. Fields used per run: `id, arm, scope, rank, passed, required_visits, visits_trace, overhead (successful runs only), shortfall (failed runs only), revisits, requests, cost, elapsed, prompt/completion/reasoning, categories (raw_valid | recovered | rejected), find_elements, narrowed`.

## Integrity rules encoded in the UI and tests

- Navigation overhead = observed − oracle-required detail pages, **successful runs only**; a failed run shows its **verification shortfall** (run 27: required 3, observed 1, shortfall 2, evaluator FAIL) and is never presented as efficient.
- Required (website-induced), agent-induced and agent–tool-interface requests are shown separately; the three `find_elements` loop runs (18 calls) are attributed to the agent–tool interface, not the storefront.
- Protocol format (50 raw-valid / 132 compatibility-recovered / 0 rejected of 182) is shown separately from task correctness (independent evaluator).
- No readiness score, no claim about real websites, no simulated or live trace; trace replay is Stage B and will be labelled *Recorded experiment replay*.

## Screenshots

`screenshots/` holds desktop and mobile captures of the production build (overview, Fern scope with the run 27 failure, Kitchen control, evidence page, mobile scope view).

## Stage B (not implemented)

Recorded agent trace replay requires a reviewed, deterministic, sanitized export of selected local run traces; see the proposal in the Task 008 PR. Nothing from `runs/` is committed.
