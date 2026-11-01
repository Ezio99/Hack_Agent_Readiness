# Playback / repeated-scroll release investigation

Baseline PR #60: `5c35e53324b41a5e21b40cc1efaa703d176284a3`.

## Findings before changes

A fresh Chromium against the production build reproduced **working playback**, not a timer/state failure: selected entries 1 through 9 advanced automatically at the existing 2.2-second presentation interval. The last entry was observed around 18 seconds after Play. At each entry, the visualization text/reference, inspector, native slider, selected timeline button and counter matched. These wall-clock measurements describe a software test, not archived event durations.

The usability failure was poor differentiation/progress visibility: Play waits 2.2 seconds before the first change; several subsequent entries contain the identical word “Scrolled.” Entries 03 and 04 even have the same archive event number (17), making their canvas content identical. The active timeline can leave the visible horizontal viewport during automatic playback. No timer speed change or cosmetic motion was needed to address this.

Read-only inspection of the existing local S1 archive confirmed two separate executed `scroll` actions, each with an execution result and no error, in step-result sequence 17; sequence 24 contains another executed scroll with no error. The exporter zips action/result pairs, so these are separate selected execution entries, not duplicate copies of one action. Public references `/storyboard/steps/2`, `/3`, `/4` remain distinct. The public projection provides no destinations, coordinates, durations or reasoning to expose. No raw payload was copied into UI, tests, screenshots or this report. Archive event 31 / entry 06 is a separate browser-tool fallback and remains distinct from ordinary scrolling. No source evidence was changed, removed, grouped or merged.

## Narrow UI correction

- Canvas shows actual Playing/Paused/Complete state and selected **Entry N of total** alongside the archive event reference.
- Scroll timeline labels identify each selected entry separately; source action text stays exactly “Scrolled.” A concise note explains the public detail limit.
- Timeline follows the selected entry, including responsive resizing, without scrolling the entire page. Reduced motion uses instant positioning and retains existing motion exclusions.
- Timer, pacing, pause/restart/manual-selection semantics and all source outcomes are unchanged.

## Validation

Focused regression covers the distinct scroll identities and fallback, and retains fake-timer advancement/end/pause tests. `review/verify_playback.py` adds **real-clock** full-UI regression at 1440px and 390px (reduced motion): no autoplay; Play advancement through every entry; matching canvas reference/text, inspector action/counter, transport counter, slider and selected timeline; pause stability beyond the interval; final stop; restart during playback; keyboard range scrub and manual selection during playback; source-preserving repetitive scroll labels and separate fallback. External requests are blocked. There is no clock acceleration or model inference. Serve `dashboard/dist` on loopback 4192, then run this script using an environment with Playwright and Chromium. It is a local regression script; CI execution of it is not claimed.

[Desktop](review/playback-1440.png) · [390px](review/playback-390.png). Screenshots contain public event text only, not website captures.

The minimal Scan overview was already implemented at `5c35e53` before this request. No further Scan polish was performed. Grading, frozen reports, model calls, archived trials and distribution policy are untouched. Production behavior outside the tested Chromium foreground scenario is not inferred from these tests.

Release checks: **15 focused studio tests**, **150 complete dashboard tests passed (7 existing skips)**; **214 critical tests passed (17 deselected, 61.58s)**; TypeScript, production build and unchanged distribution guard passed (8 files; no replay artifacts/private data). Real-clock regression completed at both widths with all states synchronized. No new dependencies.
