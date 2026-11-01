# Replay Studio integration review — PR #60

Baseline: `049292e37385dd9457b55ae2991f4ed83af61234`. Source milestones: B.1 `e2273f9029df5c97c0f9402ab5b2f1868a8959c1`, B.2 `8f88046ebb3c142af592e356186290388dbc551d`. Approved cinematic reference remains `59eb161401d81cfc616b78be3fc62fe413e861db` on its separate branch.

## Comparison and integration

GitHub PR #60 was open against `main`, head `live-m1-llm-evaluation` at the exact baseline. No commits had been added to that branch since studio divergence. The studio branch contained exactly the two approved commits; neither changes backend code, frozen reports, fixture data, grading, budget, lockfile, Vite public-copy policy or the distribution guard. There were no conflicts. Integration is a fast-forward preserving both milestone SHAs, followed by this release/validation documentation and an extended browser rehearsal; no application source change beyond B.1/B.2.

Dependencies: existing React/TypeScript/Vite stack, local Geist WOFF2 and its SIL OFL license, existing sanitized public S1 fixture and private-field-rejecting export parser. No new npm dependency or external runtime/font service. The integration worktree `/tmp/agent-readiness-integration` uses isolated tracked source and production output, with only already-installed dependencies reused through a temporary node_modules symlink. That link and dist outputs are not committed. Original checkout/untracked prototype work is untouched.

## Evidence review

- Real-model labels require authoritative `evidence_origin` and recorded presentation; development/synthetic/unknown provenance never receives a real-model replay.
- Events are allowlisted source-text/status projections with `/storyboard/steps/N` references. Repeated event numbers remain distinct. Missing tasks/sequences/statuses stay unavailable; no borrowed events or reconstructed browser pages.
- B.2's sticky “Illustrative transformation — not recorded browser footage.” label, owner-selected/not-independently-verified attribution, and omitted product values remain intact. Only the explicitly selected built-in reviewed report enables its illustration; other reports require a new reviewed patch reference.
- B.2 source asset hash remains `87e3b05804ba05b692c15426142e6ec7192ca27f03f0dd4937330db13fd8156f`. Frozen `inconclusive`, exploratory `not_supported`, 2/4 versus 3/4 supported passes and 50 versus 29 contemporary requests remain unchanged. No causal/general website improvement is established. EXP-C/R1/S1 are not pooled.
- B.1's 2.2-second playback interval is explicitly presentation pacing, not recorded timing. Symbols/fades are event visualization, not mouse trajectories. Browser-tool fallback is not a verified website defect.

## Checks run on the integration candidate

- Focused studio: **10 passed**; full dashboard: **145 passed, 7 existing skips**.
- Required offline critical suite: **214 passed, 17 deselected**, 61.77 seconds.
- Existing public-export/presentation safety: **45 passed** (`tests/test_investigate_export.py`, `tests/test_presentation_export.py`). These verify public/private separation, payload exclusion, source provenance and frozen S1 verdicts/counts.
- Explicit TypeScript check, production build and unchanged mandatory distribution guard: passed. Eight files / 643,652 bytes; no replay directory, raw trace files, private truths, credentials or unapproved replay artifacts. No source maps or public-directory copying. Source fixtures and the guard are byte-identical to the PR baseline.
- Fresh Chromium at desktop 1440×1080 and narrow 390×844: play/pause, previous/next, restart, native range keyboard scrubbing, event/inspector synchronization, missing-task state, import/repeated-import reset and raw-input rejection, classic fallback/return, local font, keyboard focus and reduced motion passed.
- Added integration checks: empty-hash default entry, direct `#/studio`, desktop and 390px reloads, and post-transformation return/reload. Reload intentionally resets playback to the first entry, paused; no false resume claim. Improvements → Replay preserves the selected event and pauses. Zero page errors, external requests or horizontal page overflow. All requests except the static loopback origin were blocked. No backend or inference ran.
- Fresh screenshots inspected locally; approved milestone review images retained to minimize the integration diff. Runtime/dashboard source is identical to approved B.2; added code only extends the rehearsal script.

## Risks / remaining blockers

Only one task/arm has public archived events; other tasks are intentionally unavailable. B.2 illustrates field placement, not actual page screenshots/diffs, values, fidelity or verified recommendations. Imported reports remain in-memory and don't share classic report selection. B.3 interactive results are unimplemented; existing measured comparison is still accessible through the classic dashboard and B.2 disclosure.

Vite emits the existing benign chunking notice: S1 is eagerly bundled for studio although classic imports it dynamically. No dependency/config change is needed. Local browser checks cover Chromium; cross-browser/screen-reader/device testing is not claimed. CI status is separate from local validation and is not claimed green while pending.

The existing participant-form/rules, required video/URL/accessibility/license/team confirmations and separately authorized publication/submission remain open items in the release checklist. No submission requirements were re-verified in this integration task. No new experiment, feature, deployment, PR merge or submission was performed.
