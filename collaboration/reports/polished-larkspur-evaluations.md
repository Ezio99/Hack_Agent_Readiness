# Polished Larkspur: v1 → evaluation → v2 → re-evaluation (2026-11-04 Sydney)

Status legend: **DONE** (committed and tested locally), **PROPOSED** (awaiting owner approval), **PENDING** (not started).

## 1. Polished v1 (DONE, commit `60c0746`)
- **Snapshot:** `larkspur@polished` = `1053ce1884a9cf718fc631c2f7c144168b9562705727b23ef2f4fae0964f9bbb` (1 042 resources; pinned in `tests/test_larkspur_polished.py`). Original `2f9fd2ce…`, Modified `edb9a5d2…`, Improved `87e715d5…` unchanged (tested).
- **What it is:** a human-centred redesign of the college site built on Improved's information architecture (`sites/larkspur/polished.py`, `art.py`):
  - its own identity (violet and sage, serif display type, larkspur logo, original SVG illustrations per subject and campus);
  - a hero with a course finder, subject tiles, "filling fast", campuses, an enrolment explainer and a full footer;
  - listing pages with a filter panel beside a card grid; cards state every fact as a labelled list plus a seats badge;
  - course pages lead with a key-facts panel and an enrolment call to action;
  - responsive from 390 px (no horizontal scroll on any checked page).
- **Kept from Improved:** the GET filter (every submission captured), browse pages, comparison table, schema.org JSON-LD and every redirect. Images are decorative (`alt=""`); every fact is real text.
- **Validity:** all 3 `larkspur-core@v3` tasks (and all 6 v2 tasks) stay valid on Polished with unchanged answers (the runner's own `validity` check). Page audit: 0 findings. Every link resolves inside the snapshot.

## 2. Single-version evaluation support (DONE, same commit)
The budget could only record a pair. The minimal, backward-compatible change:
- `lifecycle/arming.plan`: a **budget evaluation** may name one registered version; judge armings stay paired (tested).
- `hosted/budget evaluation-add --variants polished` (1 or 2 versions; `open` unchanged).
- Job status has one arm; diagnostics run per version (structural and behavioural findings; no cross-version comparison); Workspace, History, Report and Trace render one column.
- Same frozen suite, agent, manifest plan, seed and per-request cap (a regression manifest of the v3 manifest; only the variants differ). 3 trials; **per-run maximum US$1.892 = A$2.84** (pair: US$3.740).
- **Zero-cost rehearsal:** the real app, real jailed Chromium, scripted dev provider, on a copy of the production store: code → Run → live grid → 3/3 runs → report → trace replay with real screenshots of Polished v1; 0 console errors.
- **Tests:** critical 263 passed; budget/polished/improved 45 passed; hosted/settlement/stage B 40 passed; vitest 224 passed; dashboard build CHECK PASSED.

## 3. Stage 2: evaluate Polished v1 alone (PROPOSED: owner approval needed)
1. **Push** `final-showcase` (`60c0746` + this report) to origin, so the VM can fetch it.
2. **Deploy** `60c0746` image-only, following [evaluation-launch-final.md §5 A0–A5](evaluation-launch-final.md):
   - The release diff contains `src` changes, unlike the hotfix: the variant registry, single-version budget evaluations and display names.
   - No `deploy/`, compose, `.env`, secret or ledger changes.
   - A3 must show the selected evaluation is still Original vs Improved, the budget is untouched and every route renders.
3. **Owner terminal** (typed lines; the second takes effect for the next launch):
   ```sh
   docker compose exec -it app python -m agent_readiness.hosted.budget evaluation-add --db /data/hosted/live/admission.sqlite --budget ar-a20-2026-11 --id ar-a20-polished-v1 --frozen larkspur-core@v3 --variants polished
   docker compose exec -it app python -m agent_readiness.hosted.budget evaluation-use --db /data/hosted/live/admission.sqlite --budget ar-a20-2026-11 --id ar-a20-polished-v1
   ```
4. **One paid run** (3 trials, at most A$2.84, charged to the A$20 budget, auto-settled at actual cost). It is launched from the Workspace with the access code, which also gives real footage for the video.
5. **Collect:** the report, traces, requests, time and settled cost. Then export (`scripts/showcase/export_larkspur_showcase.py`) and analyse.

## 4. Stages 3–6 (PENDING)
Polished v2 changes only what the Stage 2 evidence justifies (none, if nothing is found). Stage 4 is the same procedure with `--id ar-a20-polished-v2 --variants polished2`, under separate approval.
