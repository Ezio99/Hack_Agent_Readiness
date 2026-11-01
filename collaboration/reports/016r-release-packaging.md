# Packaging and recorded-demo rehearsal — 2026-11-01

Small correction only: Vite's default public-directory copy ignores Git ignore rules. Local `dashboard/public/replays` is ignored by Git but was copied verbatim into dist. `publicDir: false` now disables that implicit asset channel; explicitly imported reviewed assets still bundle. `npm run build` now runs the unchanged distribution guard after typecheck/build, so standard builds fail closed. CI retains its explicit guard step as additional validation. No guard exceptions were added; no ignored replay/history files removed or modified.

Validation: ordinary build in the checkout containing ignored replay files passes, seven files, no replay directory. All 141 dashboard tests and 40 existing deployment-safety/export-replay tests pass. An isolated tracked-source archive plus candidate packaging files (no ignored data or backend config; installed dependencies symlinked only) builds the same seven files byte-for-byte and passes the same guard. No dependency download, model call, engine/grading change or deployment.

Fresh Chromium rehearsal against isolated production output passed all five report navigation buttons, main navigation away/back, recorded provenance, nine-event storyboard, S1 contemporary evidence-supported comparison, both unchanged verdicts/uncertainty and reload. Only static frontend requests, no browser exceptions; no backend started or configured. Images: `/tmp/release-opening.png`, `/tmp/release-storyboard.png`. Automated route/control rehearsal is not a narrated video or a claim that a human delivered the script in exactly 120 seconds.

2,239 protected historical files and all 700 indexed S1 files remain unchanged. No private evaluation data or raw trace payloads added. Guard implementation is byte-identical. The special build workaround from Report 016q is no longer needed.

Release checklist, confirmed official deadline, unresolved material requirements and two-minute script: [docs/RELEASE_CHECKLIST.md](../../docs/RELEASE_CHECKLIST.md). Public Meta/organizer pages confirm Nov 4 at 9 PM ET (Nov 5 at 13:00 Sydney in 2026), but do not establish the final project form's URL/video/repository requirements. Local historical proposals are not treated as official rules. Authenticated participant instructions and owner publication/submission approval remain blockers.

Stopped for review. No merge, deployment or submission performed.
