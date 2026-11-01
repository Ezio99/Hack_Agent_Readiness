# P0 recorded Ironbark demo — 2026-11-01

Scope: four approved presentation changes only. No paid call, grading/rule change, experiment, historical run modification, merge or deployment.

## Resulting experience

The default Investigation page immediately opens the reviewed recorded Ironbark S1 case, bundled as a sanitized public presentation asset. No service address, account, file picker or backend is required. The hero says “RECORDED REAL-MODEL EVIDENCE · no evaluation running”, describes the developer value, and identifies S1 as a sensitivity experiment. Contemporary original vs changed results show **2/4→3/4 evidence-supported passes**, separately labelled strict passes, **50→29 model requests**, and **improvement is not established**. Original frozen `inconclusive` and exploratory `not_supported` verdicts remain unchanged. EXP-C/R1 are explicitly separate, and the historical baseline is labelled separately. The erroneous two-affected-task sentence is replaced by a derived count.

Setup/live controls, missing-service notices, manual file loading and alternative synthetic examples remain available under the closed “Advanced” section after the report. Existing explicitly loaded reports retain tab-session persistence. Tests that exercise the older synthetic examples now select that source explicitly; a new default-opening test verifies the real recorded case.

One compact storyboard shows nine actual archived events for the highest-deposit patched task: page field-label presence, click, executed scrolls, the logged index fallback, page search, and structured submission with content withheld. Independent strict/evidence-supported outcomes follow. The storyboard does not claim why the website caused difficulty. A browser-tool fallback is explicitly separate from website observations and agent outcomes. No action without a corresponding execution result is shown. Source sequence numbers preserve inspectability without publishing trace payloads.

## Changes and safety

- `investigate/presentation.py`: read-only allowlists for evidence origin and a bounded selected-event storyboard. Existing dev-provider artifact or loopback request records identify fixtures. Real-model origin requires correlated successful HTTPS model response/request records for the exported trial records and live execution metadata. Missing/corrupt evidence is unknown; display names never determine provenance. No model/client/runner changes.
- `investigate/export.py`: adds origin/storyboard to sanitized exports; strengthens forbidden payload-key exclusions. The ordinary public alias/redaction pass applies to the storyboard too.
- `scripts/export_recorded_ironbark_demo.py`: reproduces the public asset from the exact accepted S1 manifest without executing anything. Raw data stays local; only the specifically authorized sanitized recorded presentation asset is committed. This is a narrow exception to the standing no-generated-run-data convention, as explicitly requested for this demo; no raw run artifacts or private truths are included.
- `dashboard/src/fixtures/ironbark-s1-recorded.json`: sanitized derivative of accepted evidence; original trial files remain unchanged. Synthetic test fixtures gain only provenance/null-storyboard metadata, without changing their outcomes or dates.
- Report page/contracts/styles: demo-first ordering, conservative provenance, strict vs supported counts, contemporary comparison, archived storyboard, keyboard focus and narrow-screen wrapping. Existing verdict records are never recomputed in the frontend.
- Tests: malicious payload exclusion, origin confirmation/unknown/dev behavior, actual-vs-proposed action selection, asset verdict/counter checks, default backend-free opening and existing report persistence.

## Validation actually run

- Python presentation/export tests: **45 passed** (final exclusion-hardening run, 3.01 s).
- Dashboard: **141 passed**; TypeScript/Vite build passed.
- Critical suite: **214 passed, 17 deselected**, 51.31 s on the final implementation.
- Chromium built-app check: fresh contexts at 1365×900 and 390×844; default report and reload work with no backend or external requests; no page exceptions; no horizontal overflow; Advanced initially closed and opens with Enter, then keyboard focus advances to its controls. Recorded screenshots at `/tmp/p0-desktop.png`, `/tmp/p0-narrow.png`, `/tmp/p0-story-desktop.png`, `/tmp/p0-story-narrow.png`. Later parser/provenance hardening did not change the inspected visual layout.
- Public asset passes `check_clean` and `check_public`, including no private criteria/truth, response content, raw trace/DOM/message payloads, secrets, local paths or internal IDs. Reproduction is byte-identical. Raw trace fields are rejected even inside a purported storyboard by the UI parser.
- 2,239 protected historical files and all 700 indexed S1 files remain unchanged. Decision rules, grader and programme ledger are untouched in this change.

## Packaging caveat and safe local demonstration

The first ordinary `npm run check:dist` failed because **pre-existing ignored** files in this machine's `dashboard/public/replays/` are copied to the normal output. They were not added, approved or modified by this work. The guard correctly refused their inclusion. No unsafe output was published and the guard was not weakened.

A clean, backend-free demo build excluding that unrelated ignored public directory passed the same guard:

```
cd dashboard
npm run typecheck
node --input-type=module -e "import {build} from 'vite'; await build({publicDir:false,build:{outDir:'/tmp/p0-clean-dist',emptyOutDir:true}})"
DIST_DIR=/tmp/p0-clean-dist node scripts/check-dist.mjs
npx vite preview --outDir /tmp/p0-clean-dist --host 127.0.0.1 --port 4179
```

This includes the bundled recorded S1 presentation asset and keeps legacy replay material out. Do not publish a standard local build that fails the guard. No P0 UI blocker remains for the clean recorded demo; P1/P2 audit items, fresh live-evaluation setup and historical replay publication remain outside scope.

Stop for owner review. No further paid experiment, merge or deployment authorized.
