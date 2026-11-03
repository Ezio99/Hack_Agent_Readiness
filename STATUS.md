# Agent Readiness: status

Authoritative current handoff. Check it against the repository and production before you rely on it. The full dated history up to 2026-11-02 is preserved verbatim in [docs/archive/STATUS-2026-10-29-to-2026-11-02.md](docs/archive/STATUS-2026-10-29-to-2026-11-02.md); earlier history is in [docs/archive/STATUS-through-2026-10-29.md](docs/archive/STATUS-through-2026-10-29.md).

## Current state (2026-11-03 Sydney)

> **PRODUCTION = `final-showcase` @ `dde7e22`** (deployed with owner approval 2026-11-03 09:15 UTC, minimal-risk path; image `st-dde7e22` = `sha256:d40199ef…`; rollback `rollback-83be351` (= `f5d9ec46…`); backup `predeploy-st-20261103T091245Z` (2 421 files); presentation fixes + actual-cost settlement live; judge access on; `larkspur-judge-1` 2 of 3 launches left. **2026-11-03 10:49 UTC: owner settled ONLY `eval-c04fdb10…` at US$0.631751** (one write-once settlement row; backup `admission-pre-settlement-20261103T104926Z`): ceiling US$21.956 (unchanged), reserved US$14.476 (as written), settled US$0.631751, outstanding US$10.736 (e529 + Ironbark, not settled by decision), **available US$10.588249** (the budget covers 2 launches = the arming's 2). Programme spend to date US$19.418057 = A$29.13 (c04 not yet appended to the programme ledger); worst case A$45.01 of A$50. Ledgers and 2 420/2 421 evidence files unchanged. Record: [hosted-settlement.md §6](collaboration/reports/hosted-settlement.md)).
>
> Previous production: `83be351` (2026-11-03 04:09 UTC; `larkspur-core@v3` frozen `db2eb1cb…` → suite `0e46a1ef…`; ceiling US$21.956; `larkspur-judge-1` armed: 3 paid launches; first paid judge launch `eval-c04fdb10…`: Original 0/3 correct, 39 requests vs Improved 3/3 correct, 6 requests; settled US$0.631751; record: [three-task report §8–10](collaboration/reports/final-showcase-three-task-suite.md)).
>
> **Release `dde7e22`** (deployed 2026-11-03 09:15 UTC) = presentation fixes + **actual-cost settlement** of hosted reservations (verified ledgers only; write-once, idempotent; launch authority and financial capacity shown separately). Read-only reconciliation of production: c04 US$0.631751 and e529 US$1.546226 eligible (release US$8.998023, owner only); Ironbark reservations kept. Settling both requires lowering the ceiling to US$19.38 to keep the worst case within A$50 (A$49.98). [Report](collaboration/reports/hosted-settlement.md).
>
> **Presentation-fix release candidate `a3ad4cd`** (not deployed): grid correctness, equivalent-page evidence for the comparison table, opaque header, the live Original vs Improved run featured. [Report](collaboration/reports/final-presentation-fix.md).
>
> **Final showcase release (2026-11-03; branch `final-showcase`):** [collaboration/reports/final-showcase-release.md](collaboration/reports/final-showcase-release.md).
> - **Featured site: Larkspur** (owner decision). One story across Home, `#/lifecycle` (= `#/demo`), the workspace and reports: Website → Generate tasks → Review → Evaluate → Recommendations → Improve → Re-evaluate → Compare. Ironbark is archived at `#/demo/ironbark`.
> - **New website version `larkspur@improved`** (`87e715d5…`): every actionable recommendation (all seven facts on every card, a working GET filter, browse pages, a comparison table, schema.org JSON-LD, redirects for every dead end), captured into the snapshot so it works through the jailed mirror. `original`/`modified` unchanged byte for byte. Registered as a re-evaluation target (`SiteDefinition.releases`); all six frozen tasks keep their answers. Page audit: Original 7 → Modified 4 → Improved 0.
> - **Judge launch** unchanged from `4841166`; the featured pool is `larkspur-core@v3` on `--variants original improved` (US$2.508 per launch, 4 launches US$10.032, ceiling 10.736 → 20.768). Rehearsed at zero cost end to end (test, and the real service in rehearsal mode in a browser).
> - **Three-task judge suite prepared** (owner preference): v2 tasks `gen-23f1802ee0-n`, `gen-8334922e62-n` (weekend class day), `gen-f302fa8fe2-n`; suite `0e46a1ef…` (reproducible); 3 launches × US$3.740 = US$11.220, ceiling 10.736 → 21.956, programme worst case A$45.01. Candidate commit `83be351`. Not frozen or armed. [Report](collaboration/reports/final-showcase-three-task-suite.md).
> - **Fallback:** `b81cff5` (known-good final showcase), then `3377d75` (Original vs Modified). Owner approvals needed: deploy, judge secret, v3 approval/freeze, ceiling migration, paid arming, first paid launch, any merge.

> **Final showcase handoff (2026-11-03):** [collaboration/handoffs/final-showcase-handoff.md](collaboration/handoffs/final-showcase-handoff.md) is the entry point for the next agent: repository and production state, architecture map, Larkspur recommendation matrix, judge-launch status, budget, risks, implementation order and owner checkpoints.
> - **Production:** `f36db53`; no launch capacity left.
> - **Undeployed on `m9-release-readiness`:** `352f262` (presentation) and `4841166` (judge launch).
> - **The owner's final requirements** (handoff §9): an improved Larkspur with all recommendations, one consistent product story for a single featured site (not yet chosen), judge launch of that site, and showcase framing.


**Production:** https://209-38-84-72.sslip.io (DigitalOcean, Sydney). It serves **`m9-release-readiness` @ `b563a33`** (image `m9-b563a33` = `cc97e0049042`), deployed with owner approval on 2026-11-02 ~23:00 UTC (= 2026-11-03 Sydney). The hosted evaluation engine is now the lifecycle Stage B runner. Record: [M9 report §9](collaboration/reports/m9-release-readiness.md).

- Mode live, access **operator-only**. **Nothing is armed** (`not_armed`), so no evaluation can start until the owner arms one.
- Hosted ceiling **US$10.736** (owner-approved migration, audit row #1, 2026-11-02 23:26:49 UTC = 2026-11-03 Sydney). US$3.30 is still reserved by the two completed Ironbark jobs (unchanged); **US$7.436 remaining**, exactly one full `larkspur-core@v2` launch. `.env` `AR_HOSTED_CEILING_USD=10.736`. Rollback image: keep `AR_HOSTED_CEILING_USD=10` (fail-closed).
- Ironbark history intact: all 1 398 authoritative files are byte-identical to the pre-deploy backup.
- **Zero-cost VM rehearsal:** `eval-e8ccbacff02bb0cc4a467b441fc99bc5`, `larkspur-core@v2`, 12/12 trials in 3 min 16 s, US$0. The rehearsal arming was used up and then disarmed.
- Rollback image `agent-readiness-app:rollback-140a4e8` (the previous production image), plus `rollback-b3121a8` and `rollback-60fcbc6`. Backup: `/root/backups/predeploy-m9-20261102T224342Z.tgz`.
- Paid arming `larkspur-live-1` (now used up) (owner-approved, 2026-11-02 23:36:11 UTC): `larkspur-core@v2`, manifest `64a55c5f…`, 12 trials, reserves US$7.436, cap US$8.00, 1 launch left, problems []. Arming made no reservation, authorisation, ledger or model call. The workspace's Run button now works for operator-token holders.
- **Paid launch done (owner-approved, exactly once):** `eval-e529db2aafecbfddd21e5c571eb85243`, 23:38:55–23:53:41 UTC.
  - 12/12 trials completed, 0 void; 112 requests, all settled; **US$1.546226 calculated** from the durable ledger.
  - Official v1: Original 1/6, Modified 2/6. Post-hoc v2: 2/6 and 4/6. Requests 68 vs 44. Exploratory, no claim.
  - The product shows `failed`: the readiness-report audit withheld the projection because the agent's answer cites the jailed mirror URL `127.0.0.1:<port>` (a false positive; evidence intact; fix needs approval).
  - Ceiling fully reserved (US$0 left); launches 1/1 used.
  - Programme known spend US$18.786306 = A$28.18; A$21.82 left (not yet appended to the ledger).
  - Details: [M9 report §12](collaboration/reports/m9-release-readiness.md).

**Previous production (2026-11-02 07:12 UTC – ~23:00 UTC):** `evaluation-v2` @ `140a4e8`, which was itself the redesigned frontend plus the grader_v2 post-hoc view, the enforced-ceiling export fix and the operator-token UX.

**Verified independently on 2026-11-02 (fresh session, public endpoints only):**
- `index.html`, the entry JS/CSS and the lazy Demo/Classic chunks served by production are byte-identical (SHA-256) to a local build of the dashboard source at `b3121a8`. The dashboard source is unchanged from `b3121a8` to HEAD.
- `/api/health` returns `mode live, evaluations enabled, access operator, active false`.
- `/api/ironbark/config` returns `worker idle, model muse-spark-1.3, profile suite-v2-compat2, remaining_repetitions 5`.
- Security headers present: CSP `default-src 'self'`, HSTS, nosniff, `no-referrer`.
- In-container checks were repeated over SSH before the paid trial: jail self-test ok, image `redesign-b3121a8`, `.env` as documented, provider `/v1/models` 200. See the [trial report](collaboration/reports/hosted-production-trial-2026-11-02.md).

**Branches.** Production runs `product-experience-redesign`. It sits on top of `hosted-ironbark-evaluation`, then `ironbark-evaluation-runner`, then `live-m1-llm-evaluation` (draft PR #60), then `main`. It is **63 commits ahead of `main` and unmerged**, so `main` does not reproduce production. Merging (or a PR from `product-experience-redesign`) needs owner approval. `demo-cinematic-storyboard` holds 4 commits that are not in production: it is the earlier storyboard and is kept as history.

**Paid production trial completed (owner-approved, exactly one repetition):** `eval-aa23e330`, 8/8 in 9 min 01 s, real model. Original 0/4 (52 requests) → Modified 3/4 (26 requests). Frozen rule inconclusive; exploratory rule consistent_with_h1. **New calculated spend US$1.126097**, fully reconciled (0 open reservations, none settled above its reservation). Every production surface worked, including refresh recovery. Findings: an answer-length grading false negative on task 1; a tight Original-arm cap margin; a stale ceiling in the export; operator-token UX. Full details: [report](collaboration/reports/hosted-production-trial-2026-11-02.md). **No further paid call is authorized.**

**Branch `evaluation-v2` (deployed; see Production):**
- grader_v2 with adversarial tests, and a labelled post-hoc rescore with exact v1 reproduction checks ([design and historical results](collaboration/reports/grader-v2.md)). All 12 recorded runs rescore faithfully; 13 trials newly pass, none newly fail, and no verdict category changes.
- Hosted v2 view beside the official v1 grades.
- Export now reports the enforced ceiling.
- Operator-token field is visible and held in memory only.

grader_v1 remains the grader of record.

**Phase 3 framework (isolated; not on the hosted path):** [docs/FRAMEWORK.md](docs/FRAMEWORK.md).
- Site definitions, with independent record oracles for controlled sites.
- Verifiability classes; only deterministic, oracle-validated tasks are scoring-eligible.
- Validated autonomous task generation: Ironbark gets 5 deterministic tasks (its variants are exactly the hosted Original/Modified) and the second controlled site, Larkspur Community College, gets 7. The uncontrolled zoo site correctly gets 0.
- Eligible tasks freeze into the existing manifest format and grade through grader_v1/v2.

**Zero-cost evaluation loop (milestone met, 2026-11-02):** `framework/evaluate.py` runs prepare → execute → results through the same interface for every site. The path is site definition → independent oracle → task generation → validation → manifest freezing → agent execution (real Chromium, loopback dev provider) → evidence capture → grading (official v1 + post-hoc v2) → persisted results, with full provenance.

| Site | Trials | Correct answers | Evidence-supported |
|---|---|---|---|
| Larkspur | 14 | 14/14 | 14/14 |
| Ironbark | 10 | 10/10 | 6/10 (the scripted stand-in doesn't scroll the long listing, and the evidence rule correctly refuses to credit unseen answers) |

Fixed the shared dev provider's per-trial script reuse. Limitations and what blocks a real Larkspur run: [docs/FRAMEWORK.md](docs/FRAMEWORK.md).

**Model provenance:** derived from the frozen records into exports and the workspace methodology (on `evaluation-v2`, not deployed): muse-spark-1.3, reasoning_effort low (frozen by owner decision), 4096, profile and hash, official v1 / post-hoc v2.

**Phase 4 diagnostics (isolated, milestone met):** [docs/DIAGNOSTICS.md](docs/DIAGNOSTICS.md). Structural, behavioural and evidence-linked layers share one finding schema (stable id, context, severity, evidence, recommendation, status).
- Detects exactly the intentional Original→Modified change on both controlled sites.
- On the real paid trial: 11 structural and 16 behavioural observations (including a real 404 dead end); 3 hypotheses are `supported_exploratory` (the frozen rule was inconclusive; the three facts were changed together); 3 risks are `unverified`.
- On fixture runs, hypotheses stay `hypothesis` by rule.

Future product architecture (not implemented): [docs/FUTURE_ARCHITECTURE.md](docs/FUTURE_ARCHITECTURE.md).

**Next:** feature freeze. Demo and submission preparation for Wednesday 2026-11-04 (submission deadline 2026-11-05 13:00 Sydney).

**Research branch `research/llm-task-planning` (isolated, not deployed, not merged; pushed to origin with owner authorisation 2026-11-02):**
- LLM task planner: two paid planner runs.
- taskeval-1 and selection-1.
- Isolated Larkspur pilot: 8 paid jailed trials.
- **Two-stage evaluation lifecycle:** proposal approved with eight decisions. **M1–M5 implemented** (M2 `c721c47`, M2b `5bc7892`, M3 `11e1a59`, M4 `258ec96`, M5 in the report's final commit):
  - evaluator v2 with gate-nl-1 and the four wording categories (12–13 / 20 recorded Muse Spark proposals now execute in the customer's own words, against 6 / 20 under the v1 gate);
  - ranked_subset and either_of kinds;
  - the bounded Stage A loop;
  - human approval and freezing, the statistical plan and manifests;
  - the general Stage B runner.
  - **Zero-cost rehearsals** on Larkspur and Ironbark (real Chromium in the jail, loopback dev provider; NOT a model).
  - **No paid call.** Every approval made was of a SYNTHETIC fixture suite.
  - Report: [collaboration/reports/lifecycle-m2-m5.md](collaboration/reports/lifecycle-m2-m5.md).

**M6 Stage A (owner-authorised, cap US$0.10): done.**
- One paid generation: 2 requests, **US$0.049804 calculated**; schema v3 accepted; stopped at `targets_met` after 2 rounds.
- 18/24 proposals natural_verifiable as run; 20/24 after a zero-cost lexicon fix ("at least N" was misread as a superlative) re-evaluated offline.
- Suite proposal `larkspur-core` is UNAPPROVED, awaiting the owner's review.
- Report: [collaboration/reports/lifecycle-m6-stage-a.md](collaboration/reports/lifecycle-m6-stage-a.md).
- Stage B and further paid calls are not authorised.

**M7 Stage B done:** the first paid browser-agent evaluation of the owner-frozen `larkspur-core` v2 (6 natural tasks × Original/Modified × 1 repetition = 12 jailed trials).
- **US$1.520696 calculated** of the US$8.00 cap.
- Official v1: 2/6 Original, 1/6 Modified. Post-hoc v2: 3/6 and 4/6. Exploratory; no claim.
- Where listing cards carry the facts, Modified needed 3 requests instead of 12.
- Report: [collaboration/reports/lifecycle-m7-browser.md](collaboration/reports/lifecycle-m7-browser.md).

Handoff: [collaboration/LIFECYCLE_HANDOFF.md](collaboration/LIFECYCLE_HANDOFF.md).

**M8** (below) followed the handoff [collaboration/handoffs/m8-product-integration.md](collaboration/handoffs/m8-product-integration.md).

**M8: the lifecycle is the product's evaluation engine (branch `m8-product-integration`, release candidate; not merged, not deployed; zero cost):**
- The hosted evaluation (`#/run`, `POST /api/ironbark/jobs {"repetitions"}` + operator token, unchanged) now runs the lifecycle Stage B runner on the frozen suite the owner ARMED at a terminal (`python -m agent_readiness.lifecycle.arming`); the paired Ironbark engine is retired (historical jobs stay viewable).
- Each launch reserves its worst case + one request bound in the same admission (US$10 ceiling, one slot), claims its launch number once, and (paid) gets its own write-once PaidAuthorization and ledger; the worker re-checks everything; jailed Chromium; reserve-before-send; no retries.
- Results = the six-dimension readiness report and trace comparison (`/api/lifecycle/evaluations/<id>`), the same projection as the preloaded M7 dataset `datasets/lifecycle/m7-larkspur-browser-1/v1`.
- Verified in the candidate container (rehearsal mode, copy of the data): terminal arming, operator launch, 12/12 jailed trials, report, relaunch refused, restart-safe.
- **Budget reconciled (2026-11-04, durable records):** known spend US$17.240080 = A$25.86 at the conservative 1.50 planning rate (programme ledger US$13.418982 + US$3.820762 of event-period spend the ledger lists as unreconciled, found in local ledgers); **A$24.14 remains** of A$50. Production admission (copy of 2026-11-02 06:22 UTC): ceiling US$10, US$3.30 reserved (2 jobs), US$6.70 left.
- One full `larkspur-core@v2` evaluation (12 trials) reserves **US$7.436** (worst case 7.392 + one request bound 0.044); it does not fit US$10. **Recommended ceiling: exactly US$10.736** (one launch; worst case after it A$37.01 of A$50).
- New owner-only `python -m agent_readiness.hosted.ceiling` migration (TTY, typed confirmation, app stopped, expectations bound, one atomic value + audit row, accounting untouched, fail-closed check kept); rehearsed on a copy of the production database; the launch API then admits the exact M7 manifest (network disabled, nothing sent).
- Awaiting owner approval: deploy, ceiling migration, paid arming, launch (exact commands in the report §11).
- Report, decisions, deployment and rollback: [collaboration/reports/lifecycle-m8-product-integration.md](collaboration/reports/lifecycle-m8-product-integration.md).

**M9 release readiness (branch `m9-release-readiness` from `a6cd59c`; 2026-11-03 Sydney; zero cost; production not accessed):** independent
verification of the M8 release candidate. Report: [collaboration/reports/m9-release-readiness.md](collaboration/reports/m9-release-readiness.md).
- **Verdict:** GO to deploy `m9-release-readiness` HEAD. Conditional GO for the migration to US$10.736, the paid arming and the launch, subject to the pre-flights in report §7: VM `ceiling status` = 10/3.30/2 completed/0 active, store integrity, the jail self-test, and a recommended zero-cost VM rehearsal.
- **Verified:**
  - the operator launch runs the Stage B pipeline: rehearsal e2e, plus the paid branch through the hosted API with a dummy key behind a network guard (reserved before sending, void, halt, no retry, US$7.436 held, relaunch 409);
  - arming, pinning and validation;
  - the reconciliation reproduces US$3.820762 / US$17.240080 to the microdollar from 48 ledgers;
  - the deployed image's admission code on a migrated DB.
- **Fixed:** an idempotent re-run of the exact `ceiling migrate` command; the exact `.env` value printed by the migration; `admin watch` shows Stage B trial totals and stop reasons; the rollback guidance (roll back with `AR_HOSTED_CEILING_USD=10`). 12 new tests.
- **Main risk:** the launch is single-shot. Any failure after admission uses up US$7.436 and the only launch, even with zero spend.
- The M8 documents' "2026-11-04" dates are 2026-11-03 Sydney per the commits.

**M9 follow-up, report recovery (release candidate on `m9-release-readiness`, code `b16aed8`; NOT deployed; zero cost):** [collaboration/reports/m9-report-recovery.md](collaboration/reports/m9-report-recovery.md).
- **Root cause:** the paid run's readiness report was withheld because the agent's answer quotes the jailed mirror origin `http://127.0.0.1:34723/…`. The admission row was then set to `failed` although 12/12 trials completed.
- **Fix:**
  - only the trial's own recorded fixture origin is shown as a site path, disclosed per trial; any other loopback URL, credential, path or oracle material is still rejected;
  - raw evidence is unchanged;
  - one publication policy for the worker and the service;
  - execution, report availability and the preserved record are reported separately, with an explanation; the record is never rewritten;
  - the report labels a "Live run launched in this product" vs the "Pre-recorded research run" (M7).
- **Tests:** 31 new (20 fail without the change); broad 397; critical 214; browser e2e 1; dashboard 201; build CHECK PASSED; M7 re-derives byte-for-byte.
- **Docker rehearsal on a copy of production:** the paid report is served (12/12, US$1.546226 settled), evidence byte-identical, 0 console errors, rollback-compatible.
- **Deployed with owner approval** 2026-11-03 00:27 UTC: `e7e35e1`, image `sha256:20f699d2…`. The paid report and export are served (12/12, US$1.546226 settled, no local URLs); the record `failed` is preserved and explained. All 21 production checks PASS; 2 204 evidence files byte-identical; no paid activity. Rollback image `rollback-b563a33`.

**M9 final sprint (release candidate on `m9-release-readiness`; code `68ae88f`; NOT deployed; zero cost):** [collaboration/reports/m9-final-sprint.md](collaboration/reports/m9-final-sprint.md).
- **Workspace fixes:**
  - the config separates service health from launch authorisation (`launch.reason` from the arming summary the launch path enforces);
  - the banner reads "Worker ready · no launch authorised" when the launch is used;
  - the intro is generic (evaluate → diagnose → recommend → re-evaluate; Modified is a manually prepared demo; the product does not change websites).
- **Programme ledger:** the append is PROPOSED, not applied (`collaboration/budget/proposals/m9-ledger-append.json`): +3.820762 +0.000336 +1.546226 → **US$18.786306 = A$28.18; A$21.82 left**, reconciled exactly against every local durable ledger.
- **Grading audit** (read-only; [m9-grading-audit.md](collaboration/reports/m9-grading-audit.md)):
  - 0 false facts, 0 oracle errors;
  - official v1 fails 9 of 15 correct answers, 7 of them on Modified, so it understates Modified;
  - 9 of 18 failures are budget-limited navigation on Original;
  - v2 has 2 false negatives, 1 evidence false negative and 4 unverified passes;
  - `v2.1-contrast` does not generalise.
- **Demo review:** no blocking issue. Important: the home headline omits the Ironbark replication; the audit is not reflected in the product; home does not link the live run; the call to action vs no launch (fixed).
- **Tests:** broad 403, critical 214, browser e2e 1, dashboard 204, build CHECK PASSED.
- **Deployed with owner approval** 2026-11-03 01:07 UTC: `f36db53`, image `sha256:6fa8b107…` (rollback `rollback-e7e35e1`). Verified: launch state `launches_exhausted`, banner 'Worker ready · no launch authorised', report recovery and evidence unchanged.
- **Programme ledger appended with owner approval** (`98d5ec6`): 21 entries, **US$18.786306 = A$28.18; A$21.82 left** of A$50.
- Grading policy unchanged (official v1 stays the grade of record).
- **Presentation patch `352f262`** (I1 replication disclosure, I2 retrospective audit note, I3 latest live link, C1 wording, C2 trace race): tested (dashboard 209, build CHECK PASSED); **NOT deployed, awaiting owner approval**.

**M9 judge-triggered live evaluation (release candidate; code `4841166`; NOT deployed; zero cost):** [collaboration/reports/m9-judge-live.md](collaboration/reports/m9-judge-live.md).
- **Judge access:** a separate launch-only judge access code (`/run/secrets/judge_token`), accepted only by `POST /api/ironbark/jobs`, through the unchanged arming / admission / claim / ledger path.
- **Suite:** `larkspur-core@v3` = v2 tasks `gen-23f1802ee0-n` + `gen-f302fa8fe2-n` (suite `f45694788ea9…`, reproducible; v2 unchanged).
- **Workspace:** judge-facing ("Access code", "Run live evaluation", live runs left).
- **Cost per launch:** about US$0.42–0.45 expected, US$2.508 reserved, about 4–6 min.
- **4-launch pool:** reserves US$10.032 and needs the ceiling 10.736 → 20.768 (worst case A$43.23).
- **Tests:** judge access 19, judge browser e2e, no-network paid rehearsal on production copies, broad 422, critical 214, dashboard 212.
- **Awaiting owner approval:** deploy, owner suite approval and freeze, judge secret, ceiling migration, paid arming.

## Budget

- Hosted admission: US$10 ceiling, US$3.30 reserved, US$1.65 per repetition. Reservations are never released, even for completed jobs, so the remaining capacity is 4 repetitions.
- Programme: ceiling A$50. This is a limit, never an authorization. **Since 2026-11-03 (`98d5ec6`): 21 entries, known spend US$18.786306 = A$28.18; A$21.82 left.** The history below is as written before that append. The recorded known-spend subtotal is partial (see `collaboration/budget/programme-ledger.json` and the archive). The 2026-11-02 production trial (US$1.126097) is appended as `hosted-live-2`, making the subtotal US$10.566163. Research planner requests add US$0.024452 calculated from usage (`research-taskplan-2`) plus US$0.029054, an UNCONFIRMED conservative upper bound for a rejected request (`research-taskplan-1`). The isolated Larkspur research pilot (`research-pilot-larkspur-1`) adds US$1.228813, calculated from usage. M6 Stage A (`research-stage-a-m6-1`) adds US$0.049804 calculated, and M7 Stage B (`research-stage-b-m7-1`) adds US$1.520696 calculated. The current subtotal is **US$13.418982 / A$20.1285**. Calculated cost is not a bill.

## Deadlines

Feature freeze and demo preparation: **Wednesday 2026-11-04 (Sydney)**. The official submission deadline is 2026-11-05 13:00 Sydney (Nov 4 21:00 ET).

## Known debt and follow-ups

- Production code lives on an unmerged branch stack (see Branches above).
- Original-arm cap margin (about one request of headroom): left unchanged by owner decision. See the [trial report](collaboration/reports/hosted-production-trial-2026-11-02.md).
- After a reviewed deploy, production's cached `<run>.public.json` exports keep the old ceiling display until regenerated.
- Demo-day documents predate the redesign and still describe the Replay Studio as the default page: [docs/THREE_MINUTE_DEMO_SCRIPT.md](docs/THREE_MINUTE_DEMO_SCRIPT.md) and [docs/RELEASE_CHECKLIST.md](docs/RELEASE_CHECKLIST.md). Refresh them on demo-preparation day.
- Archive UIs remain reachable on purpose as rollback and reference paths: the Replay Studio (`#/studio`) and the classic pages (`#/investigation` and others). The Geist font and its licence exist in both `site/fonts` and `studio/assets`. Vite emits a single asset for them, so the duplication only costs repository bytes.
- Untracked owner work in the checkout is left untouched: `src/agent_readiness/investigate/prototype/termvalue.py` and `tests/test_termvalue_prototype.py`. They are a later variant of the tracked `taskgen/termvalue.py`.
- Architecture debt that was retained by decision (three experiment drivers, frozen shop-coupled files, legacy runner) is described in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Key documents

[deploy/DEPLOY.md](deploy/DEPLOY.md) (deployment, rollback, operations) · [dashboard/PRODUCT_REDESIGN.md](dashboard/PRODUCT_REDESIGN.md) (frontend design and evidence provenance) · [collaboration/reports/hosted-ironbark-wip.md](collaboration/reports/hosted-ironbark-wip.md) (hosted backend) · [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) · [COLD_START.md](COLD_START.md).

## Standing constraints

- No paid inference, ceiling change, public paid access or publication of private traces without explicit owner approval.
- Never print or commit `META_MODEL_API_KEY`, `.env` or `deploy/secrets/`.
- Keep scripted, mock, recorded and live evidence distinct.
- Historical Task 005–007 code, config and data, pilot evidence, frozen manifests and the budget ledger are never rewritten. Stored evaluation evidence is never deleted.
- `uv.lock` is deliberately untracked. Never use a bare `git add -A`.
