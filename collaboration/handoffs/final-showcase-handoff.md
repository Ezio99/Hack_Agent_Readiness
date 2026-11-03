# Handoff: final showcase (Meta Global Hackathon)

**Written:** 2026-11-03 (Sydney), at the end of the M9 Claude Code session.
**For:** a fresh agent taking over the final product integration.
**Deadline:** submission Thursday **2026-11-05 13:00 AEDT**. A submitted video **and** a functioning live product are both mandatory.

**Status of this document.** It authorises nothing. Where it and the code disagree, the code wins. Production facts were read on 2026-11-03 at about 13:30 AEDT (read-only); re-check them before acting.

**Read next:**
1. this file;
2. [`AGENTS.md`](../../AGENTS.md), the rules: no paid call without the owner, never `git add -A`, `uv.lock` untracked, preserve the untracked owner files;
3. [`STATUS.md`](../../STATUS.md);
4. [`deploy/DEPLOY.md`](../../deploy/DEPLOY.md);
5. the M9 reports in `collaboration/reports/`:
   - `m9-release-readiness.md` (release verification, migration, arming, paid launch);
   - `m9-report-recovery.md` (report fix);
   - `m9-final-sprint.md` (workspace fix, ledger, demo review);
   - `m9-grading-audit.md` (24-trial audit);
   - `m9-judge-live.md` (judge launch, the latest release candidate).

---

## 1. Executive summary

Agent Readiness evaluates an existing website. Real Meta Muse Spark browser agents attempt customer tasks in an isolated browser, an independent grader checks every answer against the site's own data, and a report shows where agents struggled and what to change. Re-evaluating after a change measures the effect.

**Built and working in production (`f36db53`):**
- the full pipeline;
- one real paid six-task Larkspur evaluation (`eval-e529db2a…`, 12/12 agent runs, US$1.546226) with its report;
- two historical Ironbark evaluations;
- the pre-recorded M7 Larkspur research run;
- the Lifecycle explainer;
- a hardened hosted launch path.

**Built but not deployed** (branch `m9-release-readiness`, HEAD `3377d75`):
- a judge-facing presentation patch (`352f262`);
- **judge-triggered live evaluation** (`4841166`): a launch-only judge access code, plus owner tooling for the two-task `larkspur-core@v3`.

**Not built, and the owner's final requirements (§9):**
1. an improved Larkspur website implementing **all** sensible recommendations (today's "Modified" only adds four facts to the cards);
2. one consistent product story across Home, Lifecycle, Workspace and reports, featuring **one** demo website (not yet chosen);
3. product-showcase presentation without research framing;
4. judge launch of the featured site, Larkspur or Ironbark. **Ironbark has no lifecycle suite today** (§6).

**Spending:** no launch capacity is left in production. A new judge pool needs owner approvals: deploy, suite approval, judge secret, ceiling migration, paid arming.

**Recommendation** (the owner decides): feature **Larkspur**. It is the only site with the whole lifecycle (generated tasks, owner approval, frozen suite, a paid live run, a report). Featuring Ironbark needs a new Ironbark suite first.

## 2. Repository state

| Item | Value |
|---|---|
| Repository | `Ezio99/Hack_Agent_Readiness` (`origin`) |
| Branch | **`m9-release-readiness`**, HEAD **`3377d7581c1a6a155f7a4c5366d9b2327fa4cb35`**, equal to `origin` (pushed) |
| `main` | not updated: HEAD is **128 commits ahead** of `origin/main`, 0 behind. Nothing of M8/M9 is merged. Merging needs the owner |
| Open PRs | only **#60** (draft, `live-m1-llm-evaluation`, old). The M8/M9 work has no PR |
| Uncommitted | none, except two **untracked owner files** that must never be staged, moved or deleted: `src/agent_readiness/investigate/prototype/` and `tests/test_termvalue_prototype.py` |
| Rules | stage explicit paths (never `git add -A`). `uv.lock` is deliberately untracked. Private data lives in git-ignored `scanner-data/` |

**Commits since the deployed `f36db53`** (newest first):

| Commit | What | Deployed? |
|---|---|---|
| `3377d75` | judge live evaluation: report, screenshots, owner steps (documentation) | — |
| `4841166` | **judge-triggered live evaluation (code)** | **no** |
| `bbd77d3` | record of the presentation patch (documentation) | — |
| `352f262` | **presentation patch** (Ironbark replication note, retrospective audit note, "Complete live evaluation" link, wording, trace-loading race) | **no** |
| `4c56825` | deployment and ledger records (documentation) | — |
| `98d5ec6` | **programme ledger append** (owner-approved) | committed; a data file, not deployed code |
| `f36db53` / `68ae88f` | workspace launch-state fix, generic intro | **yes (production)** |

**Local-only private data** (git-ignored; never commit):
- `scanner-data/research/stage-a/store` (the lifecycle store: owner-frozen suites, private expected answers);
- `scanner-data/research/stage-b/` (M7 evidence and ledgers);
- `scanner-data/hosted-copy-m9/` (a read-only copy of production `/data/hosted`, taken after the paid run);
- `scanner-data/grading-audit-m9/` (the private audit matrix);
- `deploy/secrets/`, `.env`.

## 3. Production state (read-only, 2026-11-03)

| Item | Value |
|---|---|
| URL | https://209-38-84-72.sslip.io (DigitalOcean Sydney, 2 vCPU / 4 GB) |
| Running image | `agent-readiness-app:latest` = **`m9s-f36db53`**, `sha256:6fa8b107ea3337413f688b87224622fc8723c1537c253e0d0c3add2cc900492f`, started 2026-11-03 01:07 UTC; healthy; 0 restarts |
| Rollback images | `rollback-e7e35e1` (`20f699d2…`), `rollback-b563a33`, `rollback-140a4e8`, `rollback-b3121a8`, `rollback-60fcbc6` |
| Service log | `mode=live access=operator evaluations=enabled jail=verified engine=stage-b armed=larkspur-live-1 (paid, larkspur-core v2, launches left 0)` |
| `/api/health` | live, evaluations enabled, operator, not active |
| `/api/ironbark/config` | engine stage-b, `available false`, `launch.reason launches_exhausted`, ceiling 10.736 / reserved 10.736. No `judge_access` (that code is undeployed) |
| `deploy/.env` (VM) | `AR_HOSTED_MODE=live`, `AR_HOSTED_ACCESS=operator`, `AR_HOSTED_CEILING_USD=10.736` (+ `SITE_ADDRESS`, `AR_SOURCE_RUN`) |
| Secrets (VM) | `deploy/secrets/meta_model_api_key`, `operator_token` (uid 10001, 0400). **No `judge_token` yet** |
| Compose | runs from `/root/agent-readiness/deploy` (checkout at `140a4e8`; `compose.yaml` unchanged since then). **`4841166` changes `compose.yaml`** (the judge secret), so copy it in when deploying |
| Build worktrees | `/root/agent-readiness-build-{evalv2,m9,m9r,m9s}` |
| Backups | `/root/backups/predeploy-m9s-20261103T010520Z.tgz` (latest) and earlier `predeploy-*`, each with a `.sha256` manifest and an `env-*` copy |
| Lifecycle store (VM) | `/data/hosted/lifecycle/store`. Frozen refs: `larkspur-core@v2`, `synthetic-larkspur-core-m7-rehearsal@v2`. **No v3 yet** |
| Stage B root (VM) | `/data/hosted/lifecycle/stage-b`. Armings: `larkspur-live-1` (paid, 1/1 used; **active**), `vm-rehearsal-1` (rehearsal, used). Authorisation and ledger: `larkspur-live-1-l1` |
| Evaluations served | Stage B: `eval-e529db2aafecbfddd21e5c571eb85243` (paid six-task Larkspur). Historical Ironbark: `eval-9aaac35c…`, `eval-aa23e330…`. Dataset: `m7-larkspur-browser-1`. Rehearsal job `eval-e8ccbacf…` lives under `/data/hosted/rehearsal` and is visible only in rehearsal mode |
| VM access | `ssh root@209.38.84.72` with the owner's key `~/.ssh/readiness_key_new` (passphrase-protected; the owner loads it into an `ssh-agent`, e.g. `! eval $(ssh-agent -s) && ssh-add ~/.ssh/readiness_key_new`). Never print secrets. `deploy/DEPLOYED.txt` on the VM records every deployment |

## 4. Spending state (durable sources)

| Item | Value | Source |
|---|---|---|
| **Programme known spend** | **US$18.786306 = A$28.18** at the conservative planning rate 1.50 AUD/USD; **A$21.82 left** of the A$50 ceiling (a limit, never an authorisation) | `collaboration/budget/programme-ledger.json`, 21 entries; the M9 reconciliation appended in `98d5ec6` |
| Hosted ceiling | **US$10.736**, fully reserved (**US$0 left**). Migration #1 (10 → 10.736) on 2026-11-02 | VM `admission.sqlite`; `python -m agent_readiness.hosted.ceiling status --db /data/hosted/live/admission.sqlite` |
| Reservations | 3 jobs: 2 completed Ironbark (US$3.30) and 1 Stage B launch (US$7.436, record `failed`, see §8). Reservations are never released | same |
| Settled (calculated, not invoiced) | Ironbark hosted-live-1 US$1.090968, hosted-live-2 US$1.126097; Stage B `eval-e529…` **US$1.546226** (112 requests, 0 unsettled) | the programme ledger; the VM `ledgers/larkspur-live-1-l1/ledger.jsonl` |
| Active arming | `larkspur-live-1`, paid, 1 launch, **0 left** | `python -m agent_readiness.lifecycle.arming status` |
| Model | `muse-spark-1.3` at `https://api.meta.ai/v1`, reasoning `low`, 4096 completion tokens, profile `suite-v2-compat2` (sha256 `d18a2b7e…`); prices US$1.25 / US$4.25 per M tokens; 14 requests per task; US$0.044 per-request cap | manifest `64a55c5f…`, `evalruns/manifest.py` |

All USD figures are calculated from provider-reported usage, not invoices.

## 5. Architecture map (reuse these; do not build parallel systems)

| Concern | Where | Notes |
|---|---|---|
| **Sites and variants** | `framework/site.py` (`SITES`: `larkspur`, `ironbark`; variants `original`, `modified`); `lifecycle/sites.py` (`VARIANT_TEXT`, `site_view`, `context_for`) | A variant is a frozen, content-hashed snapshot; no URLs are fetched |
| Larkspur source | `sites/larkspur/data.py` (14 courses), `sites/larkspur/render.py` (`pages(variant)`, `snapshot(variant)`, crawled offline) | Only difference today: Modified cards add fee, duration, level and seats left |
| Ironbark source | `sites/ironbark/` (`data.py`, `render.py`, `variants.py`, templates); snapshots through `exp2/snapshot.py` | Modified cards add deposit, minimum hire and delivery |
| Snapshot mirror | `investigate/sitemodel/server.py` | Serves **exactly** the captured paths. `/courses/`, query strings and unknown slugs 404 by design, so a website improvement must be rendered into the variant |
| Oracle | `framework/oracle.py` (`RecordOracle` from `data.py`) | Independent of what agents see |
| **Task generation (Stage A)** | `suites/stage_a/` (`loop.py`, `generators.py`, `selection.py`, `taskrecords.py`); `research/taskplan/` (the paid LLM planner; M6 cost US$0.049804); `framework/generate.py` (deterministic, zero-cost templates) | The Larkspur suite came from the paid M6 generation, then owner review |
| **Approval and freezing** | `suites/stage_a/approval.py`: `review`, `decide` (interactive terminal only), `freeze`, and the M9 **`revise --keep`** (a new suite version from existing task records; reproducible hash) | Write-once store `suites/store.py`: objects are content-addressed and tamper-checked |
| Frozen suites | `larkspur-core@v2` (6 tasks; frozen `0816af7f…`, suite `172d1e71…`, approval `31f1e3aa…`) | v3 is designed (§7) but **not created** on the VM |
| **Manifests** | `evalruns/manifest.py` (`build`, `regression`, `agent_config`, `JAIL_POLICY`) | A manifest pins the agent, variants, plan and budget. `lifecycle/arming.py: select_manifest` reuses or builds one |
| **Owner arming** | `lifecycle/arming.py` (`prepare`, `arm` (interactive terminal), `status`, `disarm`, `verify`, `launch`, `check_launch`) | Each launch gets an exclusive-create claim, a write-once PaidAuthorization and its own ledger |
| **Hosted launch API** | `hosted/api.py`: `POST /api/ironbark/jobs {"repetitions"}`, operator token (and, in `4841166`, a judge code); `config`, `status`, `live`, `trials`, `screenshots`, `export`. The only write routes are launch and the always-refused web suite decision | `hosted/stageb.py` (`StageBExecutor.admit`, job status with execution, report status and record note); `hosted/serve.py` (startup preconditions, secrets) |
| **Admission and spending** | `hosted/admission.py` (single slot, ceiling, per-client rate limit 120 s, never-released reservations); `hosted/ceiling.py` (owner-only migration, audited); `spend_gate.py` (reserve-before-send per request), `ledger.py` | The fail-closed policy check: `.env` ceiling must equal the database ceiling |
| **Execution** | `lifecycle/jobs.py` (worker subprocess, re-checks, publication check); `evalruns/runner.py` (`prepare`, `execute`, `report`); `investigate/trials/runner.py` (`run_trial`); `hosted/jail.py` (network and filesystem isolation) | Paid mode loads the key from its secret file; rehearsal uses the loopback dev provider (a scripted stand-in) |
| **Reports** | `lifecycle/projection.py` (six dimensions; agent answers; fixture-origin normalisation); `lifecycle/audit.py` (leak audit); `lifecycle/service.py` (`project_and_audit`, evaluations, timelines, screenshots); `lifecycle/api.py` | Datasets: `datasets/lifecycle/m7-larkspur-browser-1/v1` (validated at startup) |
| **Diagnostics and recommendations** | `diagnostics/` (structural, behavioural, hypotheses; findings with a `recommendation`) | Shown in the report's Diagnostics section |
| Grading | `investigate/taskgen/criteria.py` (official v1); `grading/v2.py` (post-hoc); `grading/contrast.py`, `grading/evidence_ranked.py` (prospective) | See §8 on v1 false negatives |
| **Frontend** | `dashboard/src/site/`: `Home.tsx`, `demo/Demo.tsx` (Ironbark story, `evidence/eval-9aaac35c.json`), `lifecycle/Lifecycle.tsx` (steps website, tasks, review, evaluate, report, reevaluate; **has a Larkspur/Ironbark selector**), `lifecycle/Report.tsx`, `Trace.tsx`, `workspace/HostedEvaluation.tsx`, `History.tsx`, `LiveAgent.tsx`; `LatestLive.tsx` (in `352f262`) | Routes in `router.ts`. Home and Demo deliberately call no API (a test enforces this) |
| **Deployment** | `deploy/Dockerfile`, `deploy/compose.yaml`, `deploy/DEPLOY.md`; per-release procedure in `collaboration/reports/m9-*.md` | Backup → clean worktree build → `ceiling status` pre-flight → disabled smoke test on a volume copy → tag the rollback image → `docker compose up -d --no-build --no-deps app` → verify |

**Zero-cost tooling:**
- `scripts/critical-tests.sh` (about 1 min);
- the broad suite (see `m9-judge-live.md` §3);
- `scripts/m9/paid_path_rehearsal.py` and `scripts/m9/judge_paid_path_rehearsal.py`: paid path with no network, on copies; run with `M9_NO_NETWORK=1 PYTHONPATH=scripts/m9/no_network_guard`;
- `python -m agent_readiness.evalruns.rehearse` (zero-cost Stage A + B);
- running the real service locally in rehearsal mode (`AR_HOSTED_MODE=rehearsal`, scratch store; see `m9-judge-live.md`).

## 6. Feature status

| Feature | Status |
|---|---|
| Homepage | **Production:** Ironbark story ("Four for four, in about half the requests", from `eval-9aaac35c`). **`352f262` (undeployed)** adds the Ironbark replication (`eval-aa23e330`: 0/4 → 3/4 official, 1/4 → 4/4 post-hoc), an "official grader v1" label and a link to the complete Larkspur live run |
| Demo (`#/demo`) | Ironbark scroll story (`demo/Demo.tsx`) |
| Lifecycle (`#/lifecycle`) | A generic explainer with a **Larkspur/Ironbark site selector**. The steps show Larkspur's M6 generation, review, frozen suite, the armed evaluation and the M7 report. Requirement 4 asks for the featured site's journey only |
| Workspace (`#/run`) | **Production:** Stage B launch (operator token), live agent view, history, the readiness-report tab, the launch-state banner. **`4841166`:** access-code field for judges, "Run live evaluation", plain card, run summary, fixed run counts |
| Reports (`#/reports/<id>`) | Six dimensions, task matrix, traces with screenshots, diagnostics, provenance. They currently carry research labels: "Exploratory · no claim", official v1, post-hoc v2, prospective v2.1, and the `352f262` "Retrospective evidence audit" note |
| Judge launch | Implemented in `4841166` for **any** armed frozen suite (site-agnostic). **Not deployed, no secret, no v3 suite, no pool, no ceiling headroom** |
| Improved Larkspur (all recommendations) | **Not started** |
| Ironbark lifecycle suite (needed for an Ironbark judge launch) | **Does not exist.** Ironbark has only a synthetic rehearsal fixture (`suites/stage_a/fixtures/ironbark-stage-a-v1.json`). Its hosted history comes from the retired paired engine (deleted in M8). To judge-launch Ironbark: generate an Ironbark suite (paid Stage A, about US$0.05 for M6-sized; or investigate turning `framework/generate.py`'s zero-cost deterministic tasks into lifecycle TaskRecords), have the owner review, approve and freeze it, then arm |

## 7. Judge launch (implemented, awaiting approvals)

See [`collaboration/reports/m9-judge-live.md`](../reports/m9-judge-live.md) for the full detail and the owner commands.

**The judge code:**
- **How it works:** `AR_JUDGE_TOKEN_FILE` (`/run/secrets/judge_token`) is a separate secret. It is accepted only by `POST /api/ironbark/jobs` and runs through the unchanged arming, admission, claims and ledger. Each judge is rate-limited by address.
- **When it's off:** if the file is absent, shorter than 24 characters, or equal to the operator token.
- **Never exposed:** it isn't returned, logged or recorded.

**The designed `larkspur-core@v3`** (owner tooling; reproducible): v2 tasks `gen-23f1802ee0-n` ("costs $250 or less and still has at least 5 seats left") and `gen-f302fa8fe2-n` ("$180 or less that last 6 weeks or less"); suite `f45694788ea9e1f7b28c95193e25870bfe3aed2975d7f00276cdc87d7c6b09e3`.

**Cost per launch** (from the two paid runs):
- about **US$0.42–0.45** expected;
- **US$2.508** reserved;
- **about 4–6 min**.

**A 4-launch pool:**
- reserves **US$10.032** and needs a **ceiling migration 10.736 → 20.768**;
- programme worst case **A$43.23**.

**Tests:** 19 judge-access tests, a judge browser end-to-end test on v3, a no-network paid rehearsal on copies of the production data, broad regression 422, critical 214, dashboard 212.

**Note for the new requirements:**
- The judge code works for whatever pool is armed. To feature an **improved** Larkspur, arm a pool whose variants are `original` and the new variant (a new manifest is built at `prepare`).
- To feature Ironbark, an Ironbark frozen suite is required first.
- The task choice may change. Re-run `revise --keep` with the chosen ids: a new hash, and new owner approval.

## 8. Known issues and risks

1. **The live job's record reads `failed`.** Its report was withheld at completion by a leak-audit false positive, fixed and deployed in `e7e35e1`. The admission database keeps `failed` by design; the UI shows "Completed · 12/12" with an explanation. Do not rewrite the record.
2. **Official grader v1 false negatives.** v1 rejects correct answers that add detail (9 of 15 correct answers across both paid runs, mostly Modified). See `m9-grading-audit.md`. The owner chose not to change grading now. Requirement 2 asks for product framing without academic "verified/unverified" wording. The `352f262` audit note uses exactly that wording, so **revisit it before deploying `352f262`**.
3. **Not deployed:** `352f262` and `4841166`. Deploying `4841166` deploys both, and needs the new `compose.yaml` and a `judge_token` file (compose refuses to start without it; a placeholder shorter than 24 characters keeps judge access off).
4. **Single-shot launches:** a provider or VM failure consumes a launch and its reservation (no retry). One run at a time.
5. **Rehearsal mode reveals answers:** in rehearsal mode the scripted stand-in navigates straight to the expected-answer pages, so its trace path reveals the answer set. Paid runs are unaffected. Never leave a rehearsal arming active in production.
6. **Pre-existing test failures:** `tests/test_remediation.py`, `test_remediation_experiment.py` and `test_remediation_main_design.py` (5 historical Task-015 tests) pin old programme-ledger totals. They failed before the M9 ledger append too. They are not in the critical or broad suites.
7. **Not run recently:** the full 33-minute CI suite.
8. **Repository bytes:** the Geist font is duplicated (`site/fonts`, `studio/assets`), at repository cost only.
9. **Archive pages:** `#/replay` logs a 404 for `/replays/manifest.json`; the page says the replay data isn't included.

## 9. The owner's final requirements (new; verbatim intent)

1. The improved Larkspur website implements **all sensible, actionable recommendations**, not only the information-surfacing change used in Ironbark.
2. Show actual agent behaviour and results **without academic-style verified/unverified framing**.
3. Judges can launch a real evaluation of **whichever website is featured** (Larkspur or Ironbark).
4. **Lifecycle** is an end-to-end product explainer showing **only the featured demo's** customer journey.
5. Homepage, Lifecycle, Workspace and reports tell **one consistent story**.
6. A **product showcase**, not a scientific defence.
7. A submitted **video** and a functioning **live product** are both mandatory.

The featured demo website has **not been selected**. This is the owner's decision; Larkspur is recommended (§1).

## 10. Larkspur findings and recommendations

**Sources:**
- the product's diagnostics in the live report (`eval-e529…`: 44 observed findings, 6 hypotheses) and the M7 dataset (37 observed, 6 hypotheses);
- trial mirror logs and traces;
- `m9-grading-audit.md`.

**P** = recommendation **generated by the product** (diagnostics). **E** = engineering idea inferred from traces (not product output).

Facts that are on Original cards: name, category and summary only. Modified cards also show fee, duration, level and seats left. **Campus and class day are on neither.**

| # | Observed problem | Recommendation | Supporting evidence | Proposed change (improved variant) | Status | Files | Task to evaluate it |
|---|---|---|---|---|---|---|---|
| 1 | Fee, duration, seats left and level are only on course pages (Original) | **P** "State course fee / duration / seats left on each card of /courses" (`listing-fact-gap`) | Original agents use 12–13 of 14 requests on tasks #1 and #6 and decide only 2–4 of 14 courses; Modified needs 3 | Keep as in Modified | Done in **Modified** | `sites/larkspur/render.py` `_card` | `gen-23f1802ee0-n`, `gen-f302fa8fe2-n` |
| 2 | **Campus** is only on course pages (Original **and Modified**) | **P** "State campus on each card of /courses" (+ hypothesis: contributor on tasks #4, #5) | #4 "Intermediate courses at Northside": 12–13 requests on **both** variants; live Original gave up ("list page shows no Level/Campus, detail pages required") | Add campus to every card | Not done | `render.py` `_card` | `gen-ae6c23b20b-n` (#4), `gen-f090b4b9bc-n` (#5) |
| 3 | **Class day** is only on course pages (both variants) | **P** "State class day on each card" (+ hypothesis on task #3) | #3 "Saturday or Sunday … Beginner": 12–13 requests on both variants; 1–2 of 4 courses found in all four trials | Add class day to every card | Not done | `render.py` | `gen-8334922e62-n` (#3) |
| 4 | **Materials** only on course pages | **P** "State materials on each card" (a risk only: no task uses it) | structural finding | Add materials to the card (or the course table) | Not done | `render.py` | (none; optional) |
| 5 | No **structured data** on any course page | **P** "Describe each item with schema.org JSON-LD (Course/Offer) using the same values the page shows" (`no-structured-data`) | structural finding (both variants) | JSON-LD `Course` (+ `Offer` price, `courseSchedule` / `CourseInstance` for day and campus) on each course page and an `ItemList` on `/courses` | Not done | `render.py` `_page` | all tasks (machine-readable facts) |
| 6 | **404 dead ends from guessed slugs**: `/courses/introduction-to-python` (the real slug is `intro-to-python`), `/courses/yoga-for-beginners`, `/courses/building-web-pages` | **P** "Fix or remove the failing link or control" (`dead-end`) + **E** consistent, predictable slugs | live Original #1 and #3 (`introduction-to-python`), live Modified #3 (`yoga-for-beginners`), M7 Modified #4 (`building-web-pages`) | Slugs that match the course names (e.g. `introduction-to-python`), or also render alias pages. The mirror serves only captured paths, so aliases must be pages in the snapshot | Not done | `sites/larkspur/data.py` (slug), `render.py` | #1, #3, #4 |
| 7 | **`/courses/` (trailing slash) → 404** | **P** `dead-end` (where it appears) + **E** | live Modified #4 and #5; M7 Modified #4 | Render `/courses/` as the same listing (or a page linking to `/courses`). Check that the crawler captures it, since unlinked paths aren't captured | Not done | `render.py`, `investigate/inspect/crawl.py` | #4, #5 |
| 8 | **Agents try to filter by URL**: `/courses?level=Intermediate&campus=Northside` → 404 | **E** browse and filter pages | live Original #4 | Linked static filter pages, e.g. `/courses/campus/northside`, `/courses/day/saturday`, `/courses/level/beginner` (or query variants the crawler captures; `Limits.max_query_variants=2`) | Not done | `render.py` (+ crawl limits `LIMITS`) | #3, #4, #5 |
| 9 | **Budget exhaustion and loops** on Original (5 of 6 tasks near the limit; a loop on #5) | **P** "Find which pages consumed the budget … whether the needed facts could be reached in fewer steps" (`budget-exhaustion`, `loop`, `revisit`, `unnecessary-navigation`) | diagnostics on 5/6 Original trials in both runs | Addressed by #1–#3 and #8 (all deciding facts on one page). Optionally a **comparison table** on `/courses` listing every fact | Partly (Modified) | `render.py` | all six |
| 10 | Answer **format** varies (agents add details) | (grading, not the site: the `v1-format-rejection` findings) | `m9-grading-audit.md` | Not a website change. Do not change official grading without the owner | — | — | — |

**Owner intent:** implement all sensible items (1–9) in one new **improved** variant, for example `improved`. Keep `original` (the baseline) and `modified` (the historical comparison) unchanged, since recorded evaluations refer to their snapshot hashes.

**How (reuse):**
1. Add the variant to `sites/larkspur/render.py` `VARIANTS` and render it.
2. Add it to `framework/site.py` `SITES['larkspur'].variants`.
3. Add a description in `lifecycle/sites.py` `VARIANT_TEXT`.
4. Re-render the snapshot (a new hash).
5. Arm with `--variants original improved`.

**The frozen answers don't change** (same `data.py` facts). The runner re-derives evidence per variant (`evalruns/runner.validity`) and invalidates any task whose answer changed. If slugs change, the course **names** stay the same, so the expected answers still hold.

Check the Stage A boundary and the `tests/test_framework.py` / `tests/test_lifecycle_m8.py` expectations about the variant list.

## 11. Recommended implementation order (zero-cost first; each production step needs the owner)

1. **The owner chooses the featured site** (recommendation: Larkspur), and the 2–3 tasks for the judge pool. With an improved variant that also fixes campus and class day, a broader set is defensible, e.g. #1, #3 and #4: fee and seats, class day, campus. Cost: 3 tasks reserve US$3.740 per launch, so 3 launches would fit in A$21.82 at worst case; 2 tasks reserve US$2.508.
2. **Build the improved Larkspur variant** (§10), with zero-cost tests: render and snapshot; the frozen answers still re-derive on it; a rehearsal Stage B on `original` vs `improved` (`evalruns.rehearse` or the local rehearsal service).
3. **Unify the story** (requirements 4–6). Make Home, Demo, Lifecycle, Workspace and reports feature the chosen site only, removing the Lifecycle site selector or fixing it to the featured site. Replace the research framing in the judge-facing pages; do not change the recorded results or official grades. Revisit the `352f262` audit note and its Ironbark replication sentence (keep or remove consistently with the featured story).
4. **Judge launch** (already built). Re-run `revise --keep` for the chosen tasks, then a zero-cost rehearsal pool locally and on the VM.
5. **Deploy**: one release containing 2–4. Backup → build → `ceiling status` → disabled smoke test → copy the new `compose.yaml` + create `judge_token` → switch → verify.
6. **Owner terminal steps:** `revise` → `review` → `decide` → `freeze`; the ceiling migration (+ the `.env` value); the paid arming of the judge pool; the jail self-test and `arming status`.
7. **Video:** record against production (or a local rehearsal for the walk-through, labelled as such). Keep the full paid Larkspur run as the reference result.

## 12. Exact next steps for the new agent

```sh
cd ~/Projects/Hack_Agent_Readiness && git fetch origin && git status --short && git log --oneline -3     # expect HEAD 3377d75 (or later docs), only the two untracked owner files
git switch -c final-showcase                                                                          # new work on its own branch, from m9-release-readiness
.venv/bin/python -m pytest -q -p no:cacheprovider tests/test_m9_judge_access.py tests/test_hosted_stageb.py   # sanity, zero cost
bash scripts/critical-tests.sh                                                                        # ~1 min
(cd dashboard && npx vitest run)                                                                      # 212 passed at 3377d75
```

Then:
1. Ask the owner which site to feature, and which tasks.
2. Implement §10 (improved variant) and §11.3 (one story), with tests.
3. Rehearse at zero cost (local rehearsal service; judge e2e test).
4. Prepare the release report with exact owner steps.
5. Stop for deployment approval.

## 13. Owner approval checkpoints (nothing below has been done)

1. Choose the featured demo website (and the judge tasks).
2. Deploy the release (`352f262` + `4841166` + new work). This includes copying the new `compose.yaml` and creating `deploy/secrets/judge_token`.
3. Suite approval and freezing at the terminal (`approval decide` / `freeze`).
4. The hosted ceiling migration (e.g. 10.736 → 20.768 for 4 two-task launches) and the matching `.env`.
5. The paid arming of the judge pool (`arming arm`, number of launches).
6. Distributing the judge code; any public-access change.
7. Any paid model call, including the first judge launch; any merge to `main`; any grading-policy change.
