# Report: M9 final hackathon sprint (reliability, ledger reconciliation, grading audit, demo readiness)

**Date:** 2026-11-03 (Sydney). Submission deadline: Thursday 2026-11-05 13:00 AEDT.
**Branch:** `m9-release-readiness`, on top of the deployed `e7e35e1` (documentation `b45f134`). **Not deployed.**
**Spending: none.** No model call, launch, arming, ceiling or admission change. The authoritative programme ledger is unchanged.

**Approval checkpoints still open:**
1. deploying this release candidate;
2. appending the programme-ledger entries (§2);
3. any grading-policy implementation (§3).

## 1. Task 1: workspace messaging (implemented; code commit `68ae88f`)

### A. The availability banner
- **Cause:**
  - `worker.state` reports service health only (`idle` whenever the service is enabled and no job is active);
  - `config.available` was `enabled() and armed`, so it stayed true after the single authorised launch was used;
  - the banner keyed only on `worker.state`, so it said "Ready to start a new evaluation".
- **Fix (server).** `/api/ironbark/config` (Stage B) now returns:
  - `service {state: operational | unavailable, reason}`: health;
  - `launch {authorized, ready, reason, detail, launches_left}`: derived from the arming summary, i.e. the same facts `StageBExecutor.admit` enforces (launches left, the arming's remaining total, the hosted ceiling).
  - `available` now means "a launch is authorised". Reasons: `service_unavailable`, `not_armed`, `arming_mode_mismatch`, `arming_invalid`, `launches_exhausted`, `arming_total_exhausted`, `budget_exhausted`.
  - Display only: every start is still checked by `admit`. There is no new admission path and no client-side guess.
- **Fix (UI).** Four distinct states, with the run note using the same server reason:

| State | Banner |
|---|---|
| Worker operational, launch authorised | **Worker available**, ready to start |
| Worker operational, no launch authorised (production now) | **Worker ready · no launch authorised**: "The authorised launch has been used. A new launch needs a new owner authorisation." (neutral dot) |
| Evaluation running | **Evaluation running** (was "Worker busy") |
| Service unavailable | **Evaluations unavailable** |

### B. Outdated Ironbark wording
The workspace introduction now reads: *"Agent Readiness evaluates an existing website: fresh browser agents attempt realistic customer tasks, an independent grader checks every answer against the site's own data, and the report shows where agents get stuck and what to change. After you change your site, re-evaluate it to measure the effect."*

It also says: *"In this demonstration, Modified is a manually prepared version of the controlled Larkspur site; Agent Readiness does not change websites itself."*
- Task and run counts appear only when a suite is armed. The "4 tasks / 8 runs" fallback is gone.
- When no engine is available, the Website card is generic, not "Ironbark Hire Co.".
- The legacy Ironbark methodology block appears only for historical Ironbark jobs.

### Tests
| Test | Covers |
|---|---|
| `tests/test_m9_launch_state.py` (5) | authorised and idle; the used launch is not "available" (`launches_exhausted`); not armed; budget exhausted and arming total exhausted; service unavailable; a running evaluation is busy, not unauthorised |
| `tests/test_hosted_stageb.py` (+1) | the **real** arming and Stage B executor: authorised before the launch; after it, `launches_exhausted` with the worker still `idle`, and the real launch path refuses a second start without reserving anything |
| Dashboard (+3) | the exhausted banner and note (no "Ready to start", neutral dot, Run disabled); "Worker available" only when authorised; the generic intro (no Ironbark, "manually prepared", "does not change websites") |
| Dashboard (updated 1) | the renamed "Evaluation running" state |

## 2. Task 2: programme-ledger reconciliation (prepared; **not appended**)

- **Authoritative ledger:** `collaboration/budget/programme-ledger.json`.
  - Schema `programme-ledger-v1`, append-only: entries are added at the end and each append gets a `reconciliation.<name>_addendum` with before/after subtotals.
  - 18 entries summing to **US$13.418982** (recomputed); last entry `research-stage-b-m7-1`.
- **No duplicates:** none of 3.820762, 0.000336 or 1.546226, and none of the unreconciled sources (L0, EXP-B `site-5-live`, `exp2-pilot-1`, `replay-4bad5b1b`, `live-46b6…`), appears in the ledger. The only "larkspur-live" match is the earlier pilot's run name (`pilot-larkspur-live-2f8108d3`, entry `research-pilot-larkspur-1`).
- **Live evaluation, from its durable ledger** (VM `/data/hosted/lifecycle/stage-b/ledgers/larkspur-live-1-l1/ledger.jsonl`, sha256 `e4675700…`, local copy):
  - 224 lines; 112 reserved and 112 settled;
  - **settled US$1.546226**; 0 unsettled; 0 above its reservation; no duplicate ids.
  - Token-level total: 1 059 177 prompt + 52 296 completion tokens = US$1.54622925. Settling each request to the microdollar sums to 1.546226.
- **Independent cross-check:**
  - The union of unique `(request id, timestamp)` events across every real local ledger (dev-provider, mock, dry-run and rehearsal ledgers excluded) is **US$16.176969**.
  - That equals proposed total 18.786306 − 2.606 (pre-event Tasks 004–007, no local ledger) − 0.003337 (task011 recorded above its ledger).
  - **Difference 0.000000.**

**Proposed append** (exact JSON: `collaboration/budget/proposals/m9-ledger-append.json`):

| New entry | USD | Basis |
|---|---|---|
| `reconciliation-event-period-1` | 3.820762 | L0 probes 0.040162 (incl. one unsettled reservation 0.000950); EXP-B `site-5-live` +b +c 1.534404; EXP-2 1.141478; live taskgen smoke/exposure 0.981919; replay increment 0.122799 |
| `correction-task012-stage1-1` | 0.000336 | ledger 0.718336 vs recorded 0.718 (original entry kept verbatim) |
| `hosted-stageb-live-1` | 1.546226 | `eval-e529db2a…`, 112 settled requests; owner authorisations of 2026-11-03 |
| **Known spend after the append** | **18.786306** | 13.418982 → 17.239744 → 17.240080 → 18.786306 |
| AUD at the conservative planning rate 1.50 | **A$28.18** (28.179459) | **A$21.82 remaining** of the A$50 planning budget |

- **Calculated vs invoiced:** all figures are *calculated* from provider-reported tokens at the published prices. None is provider-invoiced spending.
- **Kept conservative, not changed:**
  - task011 is recorded US$0.003337 above its ledger;
  - `research-taskplan-1` (0.029054) is an unconfirmed reservation counted in full.
- **Not spend:**
  - the hosted reservations (US$10.736 held);
  - the zero-cost runs, including the M9 network-blocked paid-path rehearsals with a dummy key, whose scratch ledgers hold reservations for requests refused before any connection.
- **Discrepancies:** none beyond those disclosed above. Spend outside this workstation's ledgers cannot be counted.

**Approval checkpoint:** appending these entries is the owner's decision. It is a text append exactly as in the proposal.

## 3. Task 3: grading reliability audit (read-only)

**Report:** [`collaboration/reports/m9-grading-audit.md`](m9-grading-audit.md). The private matrix is in the git-ignored `scanner-data/grading-audit-m9/`.

**Principal findings (24 trials: 6 tasks × 2 variants × 2 paid runs):**
1. **No agent stated a false fact, and no oracle answer is wrong.** 15 of 24 answers are correct.
2. **Official v1 fails 9 correct answers** (40% recall on correct answers) and has no false positives.
   - Cause: exact item names for lists, very short sentences for single answers.
   - 7 of the 9 false negatives are on Modified, so **official v1 understates Modified.** M7's apparent 2/6 → 1/6 regression is a grading artefact: correct answers went 3/6 → 5/6.
3. **9 of the 18 official failures are genuine incomplete navigation**, all but one on Original:
   - every filter task on Original needs ≥15 page loads against the 14-request limit;
   - agents decided only 2–4 of 14 courses.
   - That is the readiness signal, coupled to the request limit; task feasibility does not model it.
4. **v2 is better but not authoritative:**
   - 2 answer-level false negatives (task 5 Modified, `multiple_candidates`);
   - 1 evidence false negative: the fee was on the Modified card the model received, but the page-fact rule demands the course page;
   - 4 passes for correct answers the agent could not have verified (over-credit under strict evidence; 2 of them are also official v1 passes).
5. **`v2.1-contrast` is overfit:** it fails the live run's equivalent of the M7 answer it was designed from.
6. **`evidence-ranked-subset-2` works:** it flags the unverified task-5 passes.

**Audited view.** These counts are *not* grades:

| | Original | Modified |
|---|---|---|
| Live run, correct answers | 2/6 | 5/6 |
| Live run, correct and verified | 1/6 | 5/6 |
| M7, correct answers | 3/6 | 5/6 |
| M7, correct and verified | 1/6 | 4/6 |

**Safe before the deadline:** disclose the findings (wording only; v1 stays the grade of record, v2 stays labelled post-hoc).

**Deferred, as a versioned prospective policy, with this audit's 24 cases as golden fixtures:**
- grader v3: consistent-detail acceptance and a semantic contrast rule;
- evidence rule 3: fact-equivalent evidence per variant, plus a separate verification-coverage dimension;
- a verification-cost feasibility check in task generation.

No grading code was changed.

## 4. Task 4: demo readiness review (read-only; production at `e7e35e1`)

**Method:**
- a Chromium crawl of 48 judge-reachable pages (GET only; 0 write requests): home, demo scenes, how / trust / evidence, the lifecycle steps and suites, the workspace and both jobs, both readiness reports and all 12 task traces, and the archive pages;
- a check for console errors and failed responses;
- a phrase scan (significance, automatic site changes, pass and completion claims), with every hit read in context.

**Questions a first-time visitor should be able to answer:**

| Question | Assessment |
|---|---|
| 1. What does it evaluate? | Clear ("See your website the way an agent does … measures what analytics can't") |
| 2. How are tasks generated and approved? | Clear on the Lifecycle pages. The home page's "Frame the tasks: write the questions…" describes the older hand-written Ironbark tasks (see I3) |
| 3. How do real agents execute? | Clear: live agent view, trust section, isolation |
| 4. How are results and evidence presented? | Good: six dimensions, traces, screenshots, provenance |
| 5. What is Original vs Modified? | Home and Demo explain the *Ironbark* change. For Larkspur, the candidate's workspace intro now says Modified is manually prepared |
| 6. Why do tasks fail, and what can the owner do? | Diagnostics and recommendations exist. The report's note "Why two graders: v1 accepts only the bare expected names…" helps, but v1's measured false-negative rate is not disclosed (I2) |

**Checks:**

| Check | Result |
|---|---|
| Live paid run vs pre-recorded M7 | **Pass:** "Live run launched in this product · 02 Nov 2026 23:38 UTC" vs "Pre-recorded research run · sanitized dataset v1" |
| "12/12 completed" not confused with "12/12 passed" | **Mostly:** "Agent runs 12/12 completed · none void" sits beside "Official grader v1 · passed 1/6 / 2/6". "Finished" would be safer (C1) |
| Official and post-hoc grading identified | **Pass:** "Official grader v1", "Grader v2, post-hoc rescore", "v2.1 contrast review rule · prospective, not applied" |
| No implied statistical significance | **Lifecycle reports pass** ("Exploratory … no statistical power … none is made"). The **Demo and home headline "Four for four, in about half the requests"** comes from one repetition of 4 tasks. It is honestly qualified on the page (p above α, frozen rule inconclusive, "More repetitions settle it"), but the replication is not shown (I1) |
| Does not imply automatic site modification | **Pass:** the Demo says "An owner-selected change … not proposed by an automatic finding"; the candidate's workspace intro says so too |
| Historical publication-failure messaging truthful | **Pass** (deployed in `e7e35e1`) |
| No broken links or misleading empty states | **Two minor issues** (C2, C3). No broken report. Every link resolves |

**Issues, by severity:**

| # | Severity | Issue | Recommendation |
|---|---|---|---|
| — | **Blocking** | none found | — |
| I1 | **Important** | **The home, How, Trust and Demo headline (Ironbark, "1/4 → 4/4, 50 → 26 requests")** comes from `eval-9aaac35c` only. The replication `eval-aa23e330` scored **0/4 → 3/4** official (1/4 → 4/4 v2), 52 → 26 requests, and is not mentioned | Add one sentence or figure with the replication (it supports the direction and is more credible). Keep the honest p-value paragraph |
| I2 | **Important** | **The grading audit is not reflected in the product:** a judge sees official v1 Original 1/6 vs Modified 2/6 without knowing v1 fails correct, detailed answers (9 of 24) and is biased against Modified | Add a short, labelled audit note to the report pages (wording only; v1 stays official), or at least to the submission text |
| I3 | **Important** | **Two narratives:** home and Demo tell the Ironbark story (hand-written tasks, hire equipment), while the product workflow (Lifecycle, Workspace, reports) is the Larkspur suite with AI-generated, owner-approved tasks. The home page links the M7 Larkspur report in the footer but **never links the live paid Larkspur run** | Add a "Latest live evaluation" link on home (to `#/reports/eval-e529…`) and one sentence that the Ironbark demo is the earlier experiment. No redesign |
| I4 | **Important** | **"Run evaluation →" calls to action** (nav and home) lead to a workspace where no launch is possible (operator-only; the authorised launch is used). In production the banner still says "Worker available · Ready to start" | **Fixed in this candidate** (Task 1). Optionally relabel the call to action "Open the workspace" |
| C1 | Cosmetic | "Agent runs 12/12 completed" next to pass counts | "12/12 agent runs finished (finishing is not passing)" |
| C2 | Cosmetic | Moving directly from one report's task trace to another evaluation's same task briefly requests the previous run's screenshot names (2 transient 404 images). Cause: `lifecycle/parts.tsx` `useLoad` returns the previous key's data while the next key loads | Return data only for the current key (a one-line state change) |
| C3 | Cosmetic | `#/replay` (archive) fetches `/replays/manifest.json` → 404 (console error). The page itself says "Replay data is not included in this build" | Leave it, or skip the fetch in builds without replay data |
| C4 | Cosmetic | **A stale note in the lifecycle Website step, Ironbark site** (`lifecycle/sites.py` `HOSTED_NOTE`, shown only if a visitor selects Ironbark): "The hosted Ironbark evaluation (4 fixed tasks, paired Original/Modified) remains available in the evaluation workspace." That engine is retired, and the workspace now runs the armed Stage B suite. (The Larkspur variant descriptions are accurate: "fee, duration, level and seats left".) | Reword it to "Historical Ironbark evaluations remain viewable in the workspace history." |

## 5. Tests (all zero cost)

| Check | Result |
|---|---|
| Broad regression (lifecycle M1–M8, graders, hosted, ceiling, Stage B, diagnostics, framework, deployment-safety and export scripts, M9 ×3) | **403 passed**, 5 deselected |
| `scripts/critical-tests.sh` | 214 passed, 17 deselected |
| `tests/test_lifecycle_m8_browser.py -m browser` (real worker, jailed Chromium), run alone | 1 passed (155 s) |
| `dashboard`: `npx vitest run` | **204 passed** (18 files) |
| `npm run build` (tsc, Vite, `check:dist`) | CHECK PASSED |

## 6. Changed files

- **Code** (`68ae88f`):
  - `src/agent_readiness/hosted/api.py`;
  - `dashboard/src/site/workspace/HostedEvaluation.tsx`, `workspace.css`;
  - tests: `tests/test_m9_launch_state.py` (new), `tests/test_hosted_stageb.py`, `dashboard/src/site/workspace/stageb.test.tsx`, `hosted-evaluation.test.tsx`.
- **Documentation** (this commit): `collaboration/reports/m9-final-sprint.md`, `collaboration/reports/m9-grading-audit.md`, `collaboration/budget/proposals/m9-ledger-append.json`, `STATUS.md`.
- **Unchanged:**
  - the authoritative programme ledger;
  - grading code;
  - frozen suites, evidence and production.
- **Private (git-ignored):** `scanner-data/grading-audit-m9/`, `scanner-data/hosted-copy-m9/`.

## 7. Remaining risks

- **`config.available` semantics changed:** it is false once launches are used. Old clients with a cached page would hide the token field, which is harmless, since `admit` was already refusing. The production frontend and the API ship together.
- **Two loopback rules remain** (telemetry: any loopback stripped; report: strict). Unchanged; noted in M9 report-recovery §5.
- **The audit's "verified" measure is this audit's construct,** not an implemented rule. Showing it in the product would be a new, versioned view.
- **Deployment** of this candidate needs a container restart (no job can be active: launches are exhausted) and follows the M9 report-recovery §6 procedure. Rollback is `rollback-e7e35e1` (to be tagged at deploy).

## 8. Recommended next actions before Thursday 13:00 AEDT

1. **Approve and deploy this candidate** (Task 1 fixes; low risk; the same procedure as `e7e35e1`).
2. **Approve the ledger append** (§2).
3. **Decide I1–I3** (wording and links only, about 1 hour including tests). Recommended:
   - one replication sentence on home and Demo;
   - one "Latest live evaluation" link on home;
   - one audit note on the report pages.

   These directly answer the judges' likely questions.
4. **Submission text:** state plainly:
   - the live run's 12/12 completion and its official results (v1 1/6 → 2/6, v2 2/6 → 4/6, 68 → 44 requests, US$1.546226);
   - the audit's correct-answer view (2/6 → 5/6, no false facts);
   - that six tasks × one repetition supports no statistical claim.
5. **Defer** grader v3, evidence rule 3 and feasibility costing to after the hackathon, as versioned and pre-registered policies.
