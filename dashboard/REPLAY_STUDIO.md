> B.2.1 release update: Results now shows a static, source-derived archived S1 sensitivity summary: contemporary Original/Placebo 2/4 and Modified/Patched 3/4 supported passes, 50 and 29 model requests. Frozen inconclusive and exploratory not_supported are prominent; website improvement was not established. This is not full B.3 interactive exploration. Only the selected built-in reviewed report and its task IDs enable the summary; other reports/tasks are explicitly unavailable. Figures cover all four tasks, never the selected task alone. Classic investigation remains accessible with its separate report selection.

# Checkpoint B.1 — Agent Replay Studio

> B.2 is now implemented; see [current transformation notes](TRANSFORMATION.md). The following records the B.1 milestone.

Isolated branch `dashboard-replay-studio`, from PR #60 baseline `049292e37385dd9457b55ae2991f4ed83af61234`. Design reference: approved cinematic `59eb161`. The storyboard and original PR branch are unchanged. No paid inference, evaluation/decision-rule change, deployment, merge or submission.

## Preview

This checkout is **`/tmp/agent-readiness-studio`**, separate from the original project and cinematic worktree. Open it with `code -n /tmp/agent-readiness-studio`.

```sh
cd /tmp/agent-readiness-studio/dashboard
npm ci
npm run dev -- --host 127.0.0.1
```

Open Vite's printed local address, `#/studio` (also the default). No backend or credentials are required. `#/investigation` preserves the working classic dashboard; all historical routes remain accessible there. The classic dashboard has its own report selection, separate from studio imports.

Select a task → Play → Pause → Previous/Next or scrub → select a timeline event → expand Source & interpretation. Restart resets and pauses. Only the current public task/arm has an archived sequence; other tasks explicitly show unavailable. Scan provides context, Improvements shows source proposal attribution, Results preserves stored verdicts and links to the classic dashboard. Interactive transformation/results are deferred, not simulated.

At desktop widths the canvas and inspector sit side by side. At 390px the canvas, transport and inspector stack, keeping transport adjacent to the canvas. Essential actions use native buttons/selects/range controls: Tab and Enter/Space; range ArrowLeft/ArrowRight. Focus rings are visible. No autoplay; reduced-motion preference disables action entrance/hover motion. Playback pauses on tab hiding and stops at the final entry; changing report/task or leaving Insights cancels playback.

## Architecture / evidence

- `src/studio/evidence.ts`: narrow **read-only projection** of the existing sanitized public `investigation-dashboard-v1` contract, using the existing private-field rejection parser. It preserves task/arm, selected source indices (including repeated archived event numbers), event text/status, authoritative provenance, outcome booleans and stored verdicts. Unknown extra payload is not projected. It does not grade, aggregate trials or assume one trial per task.
- `ReplayStudio.tsx`: report/task/stage selection plus a keyed deterministic player. An explicit file load replaces the report, resets selection and pauses. Imports stay in memory and must be already-reviewed public exports; UI schema checks do not independently validate experimental methodology. No outcome-based automatic experiment selection.
- The initial example is the unchanged existing public S1 fixture. Dev/synthetic/unknown provenance never enables a real-model replay. Missing sequence/status/number/outcome remains unavailable, not inferred. React renders source strings as text, never HTML.
- The adapter deliberately reads the current **single public storyboard** field. A different task can be featured by a future validated export. Multiple richer sequences need a reviewed adapter extension rather than invented events. The reusable player consumes events independently of trial structure/counts. No browser pages, coordinates, durations or private responses are inferred.
- Canvas: an **event-focused visualization**, not a browser recording. The arrow/observation symbol is a categorical presentation cue, not a cursor position or trajectory. Short fade/entrance motion is presentational. The uniform 2.2-second interval is explicitly labelled editorial pacing, not measured timing. Inspector separates recorded text, browser/tool details and interpretation; scroll fallback is never a verified website defect.
- S1 remains an owner-selected sensitivity experiment. Stored frozen `inconclusive` and exploratory `not_supported` are unchanged. The original 2/4 → modified 3/4 supported passes, 50 → 29 requests remain in the classic report; this checkpoint does not reinterpret or pool results.
- `tokens.css` adapts the approved cinematic tokens under `.replay-studio`, preserving classic styles. Geist and its SIL OFL license are bundled locally, copied from the approved design reference; font provenance is in `src/studio/assets/README.md`. No new npm dependencies or remote font loading.

## Validation / review

- Focused studio tests: **8 passed**. Playback/pause/final stop, restart, step/scrub, inspector synchronization, task reset/unavailable state, authoritative provenance, private/raw rejection, variable/missing evidence and stored verdicts.
- All dashboard tests: **143 passed, 7 skipped** (existing skips retained). Classic-route assertions retained; the earlier default-route test now explicitly checks `#/investigation`, with a new studio-default/fallback test.
- Required critical suite: **214 passed, 17 deselected**, 62.58 seconds; no browser or paid inference tests.
- `npm run build`: TypeScript + Vite + **unchanged required distribution guard pass**. Eight explicitly imported build assets, including local font/license; no replays, private truths, credentials or raw traces. Vite notes that S1 is now eagerly bundled because studio uses the same fixture that classic dynamically imports; this is a benign chunking notice.
- Fresh Chromium rehearsal: desktop 1440×1080, narrow 390×844, native keyboard stepping/scrubbing/focus, reduced motion, imported report/repeated import reset, rejected raw input, unavailable task, source/inspector synchronization, classic fallback and return, local font loaded. External requests blocked; zero external requests/page errors/horizontal page overflow. No backend ran.
- [Desktop preview](review/desktop.png), [narrow preview](review/narrow.png). These screenshots contain only existing public recorded evidence; they are review assets and are not imported into distribution.

Reproduce browser rehearsal after building: serve `dashboard/dist` with `python3 -m http.server 4192 --bind 127.0.0.1 --directory dashboard/dist` from the repository root, then run `python dashboard/review/verify_studio.py` in an environment with Playwright/Chromium installed. It only permits that loopback origin.

## Remaining limits / B.2 recommendation

The public archive exposes nine selected entries for one task/arm, no pages or exact click/scroll targets, no complete reasoning or recorded timing. Sparse entries such as “Clicked a page element” remain sparse. No exact cursor reconstruction or autonomous verified recommendation is claimed. Other tasks cannot replay until reviewed public evidence is supplied. The timeline scrolls horizontally; inspector stacks on mobile. This is a local checkpoint, not a deployment or CI-green claim.

For B.2, add a clearly labelled illustrative listing transformation in the existing Improvements stage, preserving owner selection and source provenance, with no invented rental values. Keep any future captured-page mode separate and require validated sanitized page evidence before enabling it. B.3 remains a separate report-derived comparison milestone.

## B.2.1 validation and limits

`ArchivedResults.tsx` projects the current approved source without editing it, ignoring historical baseline and refusing incomplete, void, missing-field or repeated-trial structures. Arm totals and denominators are derived from contemporary source rows; original frozen verdicts are read, not recomputed. Owner-selected attribution stays separate from independently verified recommendations. No new assets/dependencies, evaluation logic, timing or causal effects.

13 focused studio tests and 148 dashboard tests pass (7 existing skips). TypeScript, build and unchanged distribution guard pass: 8 output files, no replay directory or unapproved data. Fresh Chromium review covers desktop/390px, keyboard navigation, reduced motion, existing replay/transformation continuity, Results/source labels and totals, unavailable imported report and classic-detail navigation. [Results desktop](review/results-desktop.png), [390px](review/results-narrow.png). Source fixture, frozen verdicts, grading and experimental history are unchanged. Critical suite: 214 passed, 17 deselected (62.11s). A mixed local React dependency installation caused the first production-browser startup failure; a fresh lockfile `npm ci` rebuild resolved it without application changes. All dashboard tests and the complete browser rehearsal passed against that clean build.

This summary intentionally supports only the built-in approved S1 case. Even an imported report with an S1-like name receives unavailable; no display-name matching or favorable-run selection. Future richer/repeated-trial reports require a reviewed summary adapter. Sparse archived replay and illustrative transformation limitations remain. No full B.3, inference, merge or deployment.
