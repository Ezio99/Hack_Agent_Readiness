> Current Results presentation (2026-11-02): rehearse the two recorded differences first (+1 supported task; 42% fewer requests), then expand **Technical details** for unchanged inconclusive/not_supported verdicts, methodology and improvement-not-established qualification. Original/Modified counts and owner-selected attribution remain visible. This supersedes the earlier verdict-prominent layout, not its evidence or decision rules.

> B.2.1: the studio Results tab now contains a static archived S1 summary, not a redirect-only placeholder. Rehearse Insights → Improvements → Results: Original/Placebo 2/4 → Modified/Patched 3/4 evidence-supported passes; 50 → 29 model requests. Preserve frozen inconclusive, exploratory not_supported and “Website improvement was not established.” These are report-wide observations, not selected-task scores or verified owner-selected remediation. Imported/unsupported report/task selections show unavailable. Full B.3 remains deferred. See [current studio notes](../dashboard/REPLAY_STUDIO.md).

> Current demo entry is **Replay Studio** (empty hash or `#/studio`). The approved classic report remains at `#/investigation`. See [studio integration review](STUDIO_INTEGRATION_REVIEW.md). Existing packaging checks/scripts below are retained as historical evidence; their seven-file/141-test counts are not the current candidate counts.

## Studio integration release checks (current candidate)

- [x] PR #60 baseline remained `049292e`; no intervening changes/conflicts. Preserve B.1 `e2273f9` and B.2 `8f88046` by fast-forward integration. No application changes beyond those reviewed commits.
- [x] Default/direct `#/studio` entry, desktop/390px reload, playback/step/scrub, keyboard focus, reduced motion, Improvements → Replay continuity and classic dashboard fallback checked in a fresh browser without backend/external requests.
- [x] Recorded/fixture/unknown provenance stays explicit. Missing sequences are unavailable. B.2 is persistently labelled “Illustrative transformation — not recorded browser footage.” Owner-selected attribution and not-independently-verified status stay visible.
- [x] 10 focused studio tests; 145 dashboard tests (7 existing skips); 214 critical tests (17 deselected); 45 public-export safety tests pass. TypeScript, production build and the unchanged required distribution guard pass: eight files including local Geist/license, no replay directory/private truths/raw traces/credentials/unapproved artifacts.
- [x] Grading, historical artifacts, public S1 fixture, stored verdicts, ledgers, safe-export and distribution safeguards unchanged. Cinematic branch remains separate and untouched.
- [ ] Owner review of this integration; PR merge/publication/submission still need separate authorization.
- [ ] Check current-head CI after push; local passing tests do not imply green CI.
- [ ] Confirm final participant form/material requirements, judge access, video and URL requirements and contributor/license disclosures (existing unresolved matrix below remains authoritative about what is unconfirmed).

Studio rehearsal: open `#/studio`, select the first supported task, play then pause, choose a recorded click or search event, scrub, inspect its source. Open **Inspect listing change**; explain that existing rental terms are being illustrated on listing cards, not replayed as footage or independently verified remediation. Open **Patch basis & separate experimental outcomes**: 2/4 → 3/4 supported passes, 50 → 29 requests; improvement not established, frozen inconclusive / exploratory not_supported. Return to agent journey: the same event remains selected and playback is paused. Classic dashboard opens its own report selection at `#/investigation`.

Limits for presenters: one archived task/arm, no exact pages/values/cursor paths/timing; other tasks and unrelated transformations show unavailable. Playback pacing is editorial. Imported reports are in-memory; reload returns to the default paused example. B.3 is deferred. The three-minute classic script still applies only when deliberately opening `#/investigation`; do not narrate its interactions over the new default studio. This rehearsal is not a recorded video or a measured human presentation duration.

> Current pitch/submission drafts: [pitch](HACKATHON_PITCH_DRAFT.md), [three-minute script](THREE_MINUTE_DEMO_SCRIPT.md), [verified/unresolved submission checklist](SUBMISSION_PLAN.md). The current public S1 asset omits captured pages: use the new script rather than the older two-minute page-diff interaction below. Packaging/CI repair `1c66a1d` is accepted; merge/publication still require separate approval.

# Recorded demo release checklist and two-minute script

2026-11-01. Packaging/rehearsal only; no deployment, merge, paid call or experimental change is authorized.

## Checked release candidate

- [x] Ordinary `cd dashboard && npm run build` typechecks, builds and invokes `check:dist`; a failed guard fails the build.
- [x] Vite `publicDir: false` prevents unconditional copying of ignored local replay files. Only explicitly imported source assets enter this build. The pre-existing replay files remain local and untouched. The distribution guard and its exclusions/exceptions are unchanged.
- [x] Seven generated files; no replays, source maps, raw traces, local paths or credential-like content found by the existing guard. The reviewed recorded S1 asset already passes exporter private-field/public-data checks.
- [x] Isolated tracked-source snapshot: archive of reviewed HEAD plus the two candidate packaging files, no ignored public assets, credentials, runtime data or backend configuration. Reused only installed dependencies through a node_modules symlink. Built source/output were isolated. Its seven output files match the ordinary build byte-for-byte.
- [x] 141 dashboard tests and 40 deployment-safety/export-replay tests passed; TypeScript and ordinary build guard passed.
- [x] Fresh Chromium session against isolated production output: all five report-navigation buttons, main Historical/Investigation navigation and return, nine-event storyboard, recorded evidence label, contemporary 2/4→3/4 supported passes / 50→29 requests, unchanged inconclusive/not_supported verdicts, uncertainty language and reload passed. No browser exceptions and no backend/external requests. No backend service was started or configured. This was a software/navigation rehearsal, not a recorded narrated video or evidence of human presentation duration.
- [x] 2,239 protected historical files and 700 indexed S1 files unchanged. Evaluator, frozen truths, rules and runtime ledgers untouched.
- [ ] Owner review of packaging candidate; merge/release remains unauthorized.
- [ ] Final submission form and accepted-participant instructions verified; complete the materials matrix below.
- [ ] Record/review a narrated video if required. Check any required duration, visibility, captions and link access in a signed-out session.
- [ ] Confirm repository access/visibility, any required license and provenance disclosure; do not expose ignored data or credentials.
- [ ] Public hosting only if required/desired AND separately authorized. No public demo URL was created here.
- [ ] Final browser and distribution guard on the exact release commit, then owner-authorized submission.

Local rehearsal (no backend, no model):

```
cd dashboard
npm run build
npm run preview -- --host 127.0.0.1 --port 4179 --strictPort
```

Open a fresh browser at `http://127.0.0.1:4179/`. Keep Advanced closed. Use the report navigation buttons; captured site links are intentionally inert. If the required build guard fails, stop rather than bypassing it. The earlier special clean-build workaround in Report 016q is superseded by this standard safe build.

## Submission requirements: confirmed versus unresolved

Checked official public sources on 2026-11-01:

- [Meta event page](https://dev.meta.ai/events/global-hackathon) lists the project deadline as November 4 at 9 PM ET.
- [Organizer event page](https://cerebralvalley.ai/e/meta-ai-developer-hackathon) corroborates that deadline and labels the event timezone EST. In 2026 this converts to **November 5, 13:00 Australia/Sydney (AEDT)** using America/New_York and Australia/Sydney zoneinfo. Dates may change; check the participant portal again before submission. Internal target remains November 4, 23:59 Sydney.
- Both public pages still refer to official rules being published before kickoff; the fetched pages do not provide the final project-submission fields. Their statement that GitHub/shipped-product links are optional concerns APPLICATION review, not project submission. It is not evidence that submission links are optional.

| Material | Verified requirement? | Current readiness / needed decision |
|---|---|---|
| Public hosted application URL | Unresolved | Local static demo ready; no deployment authorized or performed |
| Demo video / maximum duration | Unresolved | Two-minute local script below; no video produced or uploaded |
| Repository URL / public visibility / license | Unresolved | Repository and PR exist; verify judge access and required visibility/license |
| Description, track, team, Meta technology disclosure | Exact fields unresolved | Prepare from truthful project evidence; select/confirm in the actual form |
| Pre-existing work / asset reuse disclosures | Exact rules unresolved | Preserve pre-event planning/prototype provenance; review accepted official rules |
| Submission portal and successful receipt | Unresolved | Owner must inspect authenticated accepted-participant instructions/form and retain receipt |

Local pitch documents mention a three-minute video and public links, but these are historical proposals, not verified submission requirements. No requirement was inferred from another hackathon. Remaining submission blockers are the actual participant rules/form, any required video/link production, access checks and owner authorization for publication/submission.

## Two-minute recorded Ironbark script

| Time | Screen action | Narration |
|---|---|---|
| 0:00–0:15 | Default hero; keep recorded provenance visible | “Agent Readiness helps developers see where AI agents struggle on their website, inspect the evidence, and test proposed changes. This is a recorded Ironbark evaluation, not a live run.” |
| 0:15–0:30 | Website section; show captured listing | “We evaluate a controlled copy of the site. Tasks are frozen, and code grades the answers independently of the agent’s own success claim.” |
| 0:30–0:55 | Agent analysis; nine-event storyboard | “Here is one actual recorded task. The agent clicked, scrolled and searched the page. A missing scroll index triggered a logged page fallback. That is browser-tool behavior, not a website defect. Response contents and raw traces are withheld.” |
| 0:55–1:15 | Recommendations, then website changes | “The owner selected this experimental change: show existing deposit, minimum-hire and delivery facts on listing cards. It is not an investigator-verified finding. The side-by-side view shows the controlled change.” |
| 1:15–1:40 | Measured impact or hero contemporary card | “Using the same agent configuration in both new arms, evidence-supported passes were two of four versus three of four, with fifty versus twenty-nine model requests. These are descriptive differences. Improvement is not established: the frozen result is inconclusive and the exploratory hypothesis is not supported.” |
| 1:40–2:00 | Return to hero / provenance | “Meta’s model made the recorded browser decisions. The value is the developer’s evidence trail: task, observed behavior, proposed change and honest retest. S1 is a sensitivity experiment; we do not pool it with earlier runs or turn this small result into a universal score.” |

Rehearse spoken timing before recording; shorten narration rather than hiding uncertainty or provenance. Do not start evaluations or use the unrelated historical replay pages during this two-minute story.
