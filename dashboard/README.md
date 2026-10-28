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

Pages: **Overview** (headline results, what was tested, three-way attribution of effort, recommendation, Meta Muse Spark's role, limits), **Scope comparison** (Kitchen, Bags, Home, Outdoors, Fern or all; arm A vs B table, charts, run-level evidence) **Evidence & method** (findings, the run 27 case, definitions, limitations, provenance) and **Recorded replay** (step-by-step replay of three real Fern runs; development-only data, see below).

## Data contract

The app imports `../collaboration/reports/007-pilot-data/per-run-reconciled.json` directly (30 runs; produced by `reconcile.py` from the preserved run artifacts) and derives every figure in `src/lib/metrics.ts`. Nothing numeric is hand-maintained: the only constants in `src/data/task007.ts` are provenance strings (execution commit `969d7d4`, schedule hash, model, prices), which `src/lib/report.test.ts` checks against Report 007. Fields used per run: `id, arm, scope, rank, passed, required_visits, visits_trace, overhead (successful runs only), shortfall (failed runs only), revisits, requests, cost, elapsed, prompt/completion/reasoning, categories (raw_valid | recovered | rejected), find_elements, narrowed`.

## Integrity rules encoded in the UI and tests

- Navigation overhead = observed − oracle-required detail pages, **successful runs only**; a failed run shows its **verification shortfall** (run 27: required 3, observed 1, shortfall 2, evaluator FAIL) and is never presented as efficient.
- Requests are accounted as an **assumed website-required path** (A 2; B 2 × rank) + **loop calls** (repeated `find_elements` in the three loop runs, 18 calls, attributed to the agent–tool interface, not the storefront) + a **residual agent overhead**. The residual is `total − required path − loop calls`: an *unclassified remainder*, not a per-request classification. For failed run 27 the required path was not completed, so its residual (−1) is not meaningful and the UI says so. The numbers reconcile with Report 007 (where this term is called agent-induced inefficiency).
- Mean *observed* detail pages for Fern arm B (2.33) include failed run 27 (observed 1 of 3 required pages): incomplete verification, not better efficiency. The scope page also shows the successful-runs-only comparison.
- Protocol format (50 raw-valid / 132 compatibility-recovered / 0 rejected of 182) is shown separately from task correctness (independent evaluator).
- No readiness score, no claim about real websites, no simulated or live trace; trace replay is Stage B and will be labelled *Recorded experiment replay*.

## Screenshots

`screenshots/` holds desktop and mobile captures of the production build (overview, Fern scope with the run 27 failure, Kitchen control, evidence page, mobile scope view).

## Recorded replay (Stage B, local development only)

`scripts/export_replay.py` deterministically exports a sanitized replay of three real runs (`25-s02-A1`, `26-s02-B1`, `27-s02-B2`) from the **local, uncommitted** `runs/pilot-task007/` artifacts into `public/replays/`, which is **Git-ignored**. The export is not committed or published until the exact files and fields are reviewed and approved.

```bash
python3 dashboard/scripts/export_replay.py           # build in memory -> audit (mandatory) -> write ONLY if the audit passes
python3 dashboard/scripts/export_replay.py --audit   # same, and print the field/size inventory
python3 dashboard/scripts/export_replay.py --check   # read-only: regenerate in memory and compare with the files on disk
.venv/bin/python -m pytest dashboard/scripts -q       # exporter unit tests (synthetic inputs)
cd dashboard && npm run dev                           # Recorded replay tab loads ./replays/ when present
```

**Audit-before-write:** every write first builds the export in memory and runs the sanitization checks (credential value, local paths, localhost ports, key-like tokens, emails, forbidden keys, any model-written string of 20+ characters from the local responses) and integrity checks (manifest hashes, step counts, token/cost totals, attribution rules). Any finding exits nonzero, writes nothing and leaves existing exports untouched; files are staged and moved into place only after the audit passes. `--check` never writes.

**Attribution in the export:** `required_path_requests` is an *assumed* path (A 2; B 2 × rank); `tool_loop_requests` counts repeated `find_elements` calls in loop runs (≥ 3); `residual_requests = total − required − loop` is an unclassified remainder. For a run that did not complete the required path (failed run 27: required 3 pages, observed 1) the residual is **`null`** with `required_path_completed: false` and a `residual_note`, because the difference is not an overhead measure and must never be read as efficiency; the request, loop and assumed-path counts are preserved. The underlying data and Report 007's numbers are unchanged.

Exported per run (public schema `task009-replay-v2`: the agent's self-reported `done.success`, `reasoning_tokens`, `finish_reason` and the redundant page `title` were removed in Task 009; the independent evaluator verdict is the only success signal): identifiers, scope, arm, task wording, evaluator verdict and reasons, submitted answer, required/observed visits, overhead or verification shortfall, request accounting, totals; per step: page kind and path, the model-visible DOM text, the last result shown in the model's history, allow-listed action names and parameters, sanitized tool-result excerpts (≤ 600 chars), the result as shown to the model on its next request, response-format category (raw-valid / recovered), guard state, tokens, latency and calculated cost. **Excluded:** model thinking/memory/next-goal text, prose prefixes, free-text action descriptions, system prompts and complete requests, raw HTTP bodies, request IDs, screenshots, private truth, local paths and ports. Without the export the tab shows a clearly labelled "not included in this build" message; the replay tests then run only against a clearly marked synthetic fixture.

Everything on the replay page is labelled **Recorded experiment replay — not live inference.**


## Deployment readiness (configuration only; nothing is deployed)

The build is a static site with relative asset URLs (`base: "./"`) and hash routing, so it works under a GitHub Pages project path (`https://<owner>.github.io/Hack_Agent_Readiness/`), survives refresh on any `#/…` route, and needs no backend, secrets, `runs/` directory or API key. It contains only the committed reconciled Task 007 data.

- **Safety check:** `npm run check:dist` scans `dist/` for credential names/tokens, the model API endpoint, local paths, localhost ports, trace/zip/screenshot files, sourcemaps and **any `replays/` directory** (allowed only with `ALLOW_REPLAYS=1`). CI runs it on every dashboard change.
- **Production smoke test (local, fresh browser contexts, served under `/Hack_Agent_Readiness/`):** `npm run build && python3 scripts/smoke_dist.py` tests the public configuration (no replay data → honest fallback, deep-link refresh, all requests under the base path, no page errors); `python3 scripts/smoke_dist.py --with-local-replays` additionally exercises the replay UI against the Git-ignored local export, copied into a temporary directory only.
- **Manual deployment workflow:** `.github/workflows/pages.yml` is `workflow_dispatch`-only. It builds, tests, runs `check:dist` and deploys to GitHub Pages **only if the repository owner has enabled Pages (Settings → Pages → Source: GitHub Actions) and starts the workflow**. By default it publishes the **public build without replay data**. It refuses to build if `dashboard/public/replays/` exists on the ref unless the exact approval phrase `REPLAY-FILES-APPROVED-FOR-PUBLICATION` is supplied, and refuses the phrase when no replay files exist.
- **Recommendation:** publish the dashboard without replay data first (everything on it comes from the committed, reviewed Task 007 data), keep the replay tab on its no-data fallback until the exact files and Meta/hackathon terms are approved, then add the approved JSON in a separate reviewed PR.
- **Not done:** Pages was not enabled, no workflow was run, nothing was uploaded, and no replay data or screenshots are in the repository.
