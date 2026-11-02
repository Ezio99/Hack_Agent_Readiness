# Report: lifecycle M8, the evaluation lifecycle as the product's evaluation engine

**Date:** 2026-11-03/04. **Branch:** `m8-product-integration` (from `research/llm-task-planning` @ `604599a`). Not merged, not deployed.
**Spending:** none. No model call was made; every run used fixtures, the recorded M7 evidence, or the loopback dev provider (a scripted stand-in,
not a model). The programme ledger is unchanged.

**Revision history.** M8.1–M8.4 integrated the lifecycle as views and an operator rehearsal launcher beside the hosted evaluation. Following the
owner's correction (one engine, one launch experience), **M8.5 replaced the hosted evaluation's engine with the lifecycle Stage B runner** and
removed the separate lifecycle launch path. This report describes the result.

**Release-candidate status:** stopped at the production deployment checkpoint. Deployment, merging, paid arming and any ceiling change need the
owner (§9, §10).

---

## 1. What the operator sees, and what runs underneath

**Operator view, as today:** open `#/run`, paste the operator token, choose repetitions, press **Run evaluation**. The request is still
`POST /api/ironbark/jobs {"repetitions": 1|3|5}` with a bearer token. The page still shows live progress, the worker banner, a live agent view with
real screenshots, a per-task grid and the history. Changes on the page:
- the website card shows the **armed frozen suite** (site, suite and version, variants, launches left);
- the repetition buttons show the number of agent runs and the reservation;
- the **Results** tab is now the **Readiness report**: the six-dimension report and trace comparison, the same component that renders the preloaded M7 dataset.

**Underneath, for every launch:**

1. The server reads the owner's **active arming** (§4):
   - the frozen suite, already approved and frozen by the owner;
   - the registered website variants;
   - the exact manifest for the chosen repetition count;
   - the model.

   The client chooses nothing but the repetition count.
2. The hosted **admission** (the same database, single evaluation slot, durable US$10 ceiling and rate limit) reserves:
   - paid: the manifest's worst case plus one per-request bound;
   - rehearsal: US$0.
3. The launch claims its **launch number** under the arming. The claim is an exclusive create, so a launch number runs once, ever. A paid launch also gets its own write-once `PaidAuthorization`, quoting the owner's attestation, and its own experiment ledger.
4. One **worker subprocess** runs, with the hosted process model: parent-death signal, hard timeout, group kill. It:
   - re-checks the claim, the arming, the manifest and the reservation;
   - loads the provider key from its secret file (paid only);
   - runs `evalruns.runner` prepare → execute → report → public leak audit. Execute uses jailed Chromium; paid mode reserves every request before it is sent, with no retries.
5. The job completes only if the lifecycle projection builds and passes the leak audit. The report at `/api/lifecycle/evaluations/<eval id>` (also `#/reports/<eval id>`) is the **same projection** as the M7 dataset.

The lifecycle pages (`#/lifecycle`) show the upstream steps:
- Website;
- Task generation (M6 recorded);
- Review (suites, exact hashes, approvals and freezes; approval at the terminal only);
- Evaluate and Re-evaluate: the armed evaluation, the SSH arming workflow, and a link to the workspace. There is **no second launch control**.

## 2. Components: retained, replaced, adapted

| Component | Decision |
|---|---|
| Launch API contract, operator token, public/operator access, client identity, rate limit | **retained** unchanged |
| Admission DB, US$10 ceiling, persisted policy row, single slot, never-released reservations | **retained**. New method `reserve_amount` for exact amounts; the policy row is byte-identical, so the old image still opens the DB |
| Startup preconditions, jail self-test, fail-closed health reasons, crash recovery, Caddy/compose/Dockerfile | **retained**. New precondition: the lifecycle store (`lifecycle_store_missing`); the Ironbark source-run check is dropped |
| `paired.WorkerExecutor` → `ironbark_runner` → `abtest.drive` (4 fixed Ironbark tasks, US$0.80 arm caps) | **replaced** by `hosted/stageb.py` `StageBExecutor` → `lifecycle/jobs.py` worker → `evalruns.runner`. The old execution code is deleted from `paired.py`; the API refuses executors without the Stage B interface (503) |
| Hosted status, trial, screenshot, live and export routes | **adapted**: same paths and shapes, reading Stage B trial records. Export = the audited evaluation document. Insights = 409 (diagnostics live in the report) |
| Results and Insights tabs | **replaced** for new jobs by the readiness report. Historical jobs keep their original views |
| Workspace UI (`HostedEvaluation`, `LiveAgent`) | **adapted**: task count, website, suite, launches and reservation from the arming; live frame label; report tab |
| Historical jobs of the old engine (`eval-9aaac35c`, …) | **retained**, read-only (status, trials, screenshots, insights, export all 200 in the candidate) |
| Lifecycle launch route, paid panel, rehearsal launcher (M8.1–M8.4) | **removed**. The workspace is the only launch path |
| Stage A, owner review, freezing | **retained** upstream, terminal-only. The hosted evaluation consumes their frozen artefacts |

Research safeguards kept underneath: the exact suite and manifest binding (`evalruns.authorization.verify`, unchanged), the per-experiment cap and ledger, reserve-before-send, trials counted from the ledger, jailed Chromium, immutable store records, the leak audit, official v1 grades as recorded, and natural and assisted conditions never pooled.

## 3. Owner arming (paid authorisation), terminal only

`python -m agent_readiness.lifecycle.arming` (inside the container: `docker compose exec [-it] app python -m …`):

| Command | Effect |
|---|---|
| `prepare --arming ID --mode paid\|rehearsal --frozen NAME@vN --variants A B --repetitions 1 [3 5] --launches N` | Prints what would run: the suite hash and owner approval, variant snapshots, the manifest per repetition count (an existing manifest is reused, e.g. M7's `64a55c5f…`), the model, the trials, the worst case and reservation per launch, the hosted budget left with a fit verdict, and the exact attestation. Writes nothing except, if needed, a new system manifest (write-once) |
| `arm …same…` | Needs `sys.stdin.isatty()`. The owner types the attestation exactly. It writes `armings/<ID>.json` (write-once, 0444) and makes it active |
| `status` / `disarm` | Shows the active arming and its problems, or clears it |

The attestation names:
- the arming id;
- the frozen suite and its hash;
- the site and variant hashes;
- the model, endpoint, reasoning effort, completion tokens and profile hash;
- for every repetition count: the manifest hash, trials and reservation;
- the maximum number of launches and the total reservation.

Paid armings refuse synthetic suites. `verify` re-checks the arming:
- at arming, at service start, at every launch and in the worker;
- it requires the suite's owner approval, registered snapshots, each manifest's suite, variants and repetitions, trials, cap and reservation, the pinned agent, and the attestation re-rendered from the record.

A forged or edited arming never verifies.

The operator token can launch an armed evaluation but can never create, change or extend an arming.

## 4. Security boundaries (what a client can and cannot do)

- **Body:** `{"repetitions"}` only. Any `url`, `tasks`, `model`, `cap_usd` or other field returns 422. A repetition count that is not armed returns 409.
- **Launching** is operator-only in operator access, as today. A launch is refused before anything is reserved when:
  - nothing is armed (409);
  - the arming's mode differs from the service's (live → paid, rehearsal → rehearsal);
  - all launches are used (409);
  - the reservation does not fit the hosted ceiling (429);
  - the slot is busy (429).
- **Replay and duplicates:** launch numbers are exclusive-create claims. The PaidAuthorization and the ledger are per launch (write-once; a used ledger is refused). A failed or interrupted launch is never re-run. A restart marks running jobs interrupted, and the next launch takes the next number.
- **Web approval:** still refused (403) for everyone. New task generation is not launchable from the web.
- **Code boundary:** `hosted` reaches research code only through `agent_readiness.lifecycle` (the boundary tests were updated to say so).

## 5. Reporting

The six dimensions are unchanged from M8.1 (§1 of the M8.1–M8.4 report):
- task success (official v1, post-hoc v2, prospective rules labelled);
- navigation efficiency;
- evidence quality;
- information accessibility;
- agent reliability;
- coverage.

There is no composite score. Diagnostics separate observed facts from hypotheses. Rehearsal documents withhold the stand-in's answers and memory, because they are derived from the private outcomes.

The M7 experiment is shown as recorded:
- **exploratory:** 6 tasks × 1 repetition, no improvement claim;
- **grades:** official v1 2/6 → 1/6; post-hoc v2 3/6 → 4/6;
- **task 1:** Original named 1 of 5 in 12 requests and 67 s; Modified named 5 of 5 in 3 requests and 16 s;
- **settled spend:** US$1.520696.

Grading and diagnostics improvements (versioned, prospective, nothing retroactive):
- `hypotheses-2` (either_of/ranked_subset);
- `behavioral-2` (v1 format rejections separated from incorrect answers; v2 available for M2b kinds);
- grader `v2.1-contrast`;
- `evidence-ranked-subset-2`.

## 6. The M7 demo dataset

`datasets/lifecycle/m7-larkspur-browser-1/v1` (127 files, 4.4 MB): the projection, 12 timelines, 111 WebP screenshots and the Stage A views. It is re-derived byte-for-byte from the local source artefacts (`validate --store --run --generation` → valid, rederived). It is validated at startup; a tampered dataset is not served. Expected answers, oracle records, ledgers, authorisations and credentials are withheld.

## 7. Tests and checks (zero cost)

| Check | Result |
|---|---|
| `tests/test_hosted_stageb.py` (new): arming (TTY, exact attestation, write-once, synthetic refused, forged refused), launch (reservation = worst case + bound, claim, per-launch authorisation, relaunch refused, ceiling refusal reserves nothing, mode mismatch, rehearsal US$0), worker re-checks (authorisation handed to the runner, key loaded, no loopback guard in paid; foreign claim and wrong reservation refused), restart recovery, status before runs | 13 passed |
| `tests/test_hosted_ceiling.py` (new): status; authorised increase changes one value + one audit row, jobs byte-identical; fail-closed check still holds; exactly one full evaluation fits after migration, a larger launch or any further reservation is refused; idempotent re-run; refusals (no TTY, wrong confirmation, malformed amounts, policy and reservation mismatch, below reservations, above the programme limit, no change); decrease only down to the reservations; active job and running service block it; unexpected database state; 4 concurrent attempts apply once; simulated crash before commit leaves the old state; no API route; CLI refuses without a TTY; **the hosted launch API refuses the exact M7 manifest at US$10 and admits it (US$7.436) after migrating to US$10.736, nothing sent** (copy of the real store) | 24 passed |
| `tests/test_hosted_api.py` (adapted to the Stage B executor; + "the retired engine cannot launch") | 7 passed |
| `tests/test_hosted_service.py` (adapted: store precondition, `engine=stage-b armed=…` log, busy feedback) | 17 passed |
| `tests/test_lifecycle_m8.py` | 20 passed |
| `tests/test_lifecycle_m8_browser.py` (rewritten): **operator launch through `/api/ironbark/jobs` → real worker subprocess → jailed Chromium → hosted progress/live/trial/screenshot/export → lifecycle report**, run alone | 1 passed (56–113 s; last run after the ceiling work: 89 s) |
| `tests/test_evalruns_m5.py -m browser` (existing, alone) | 1 passed |
| Broad regression (lifecycle M1–M8, graders, hosted incl. ceiling, diagnostics, framework, deployment-safety and export scripts; not browser) | 354 passed, 5 deselected |
| `scripts/critical-tests.sh` | 214 passed, 17 deselected |
| `dashboard`: `npx vitest run` (incl. new workspace Stage B tests: armed suite shown, body `{repetitions}` + bearer only, nothing armed → Run disabled, report tab renders the real M7 projection) | 198 passed |
| `npm run build` (tsc, Vite, `check:dist`) | passed |
| Dataset re-derivation from the local source | valid, byte-equal |

Removed tests (they drove the retired engine end to end, or its deleted functions):
- `test_hosted_paired.py`;
- `tests/support/hosted_fixture_worker.py`;
- two 8-trial fixture tests in `test_hosted_api.py`.

The Stage B end-to-end test replaces them.

### 7.1 Docker release rehearsal (candidate image `agent-readiness-app:m8-candidate`)

Production's container hardening:
- `cap_drop ALL`, `no-new-privileges`;
- seccomp, AppArmor and systempaths unconfined (for the jail);
- 4 GB memory, 1024 pids.

It ran against a **copy** of the local data volume plus a copy of the lifecycle store, in **rehearsal mode** with an operator token:

1. **No store:** `evaluations disabled [lifecycle_store_missing]`, site up. With the store: `evaluations=enabled jail=verified engine=stage-b armed=none (not_armed)`.
2. **Owner CLI:**
   - `prepare` bound the exact M7 manifest `64a55c5f…` (12 trials; reserve US$7.436 if paid);
   - `arm` without a TTY was refused;
   - `arm` through a real pseudo-terminal, with the typed attestation, armed `smoke-rehearsal-1` (a zero-cost rehearsal arming on the disposable copy).
3. **Operator API:**
   - no token → 403;
   - a `url` field → 422;
   - with the token → 202.
4. **The full run inside the container:** 12/12 jailed trials of `larkspur-core@v2` in 1 min 49 s, completed, report built and audited. The workspace showed live progress, the agent view and then the readiness report. No console errors, no tracebacks.
5. **Relaunch:** 409 "All armed launches have been used".
6. **After `docker restart`:** the arming state (0 left), the job and the report all persisted.
7. **Disabled mode over the historical data:** the old engine's `eval-9aaac35c` status, insights, export and trial routes are all 200, and the M7 dataset is served.

Screenshots: `dashboard/review/m8/`. Items 13–15 are the Stage B workspace: live view, readiness report and trace.

## 8. Budget reconciliation (verified from durable records, 2026-11-04)

All USD figures are **calculated** from provider-reported tokens at the verified prices (US$1.25 / US$4.25 per M tokens). None is a bill.

AUD figures use the programme ledger's documented **conservative planning rate of 1.50 AUD per USD**, set 2026-10-29. Market quotes at the time were about 1.43–1.45 (exchange-rates.org, AUD/USD on 2026-10-01 ≈ 0.693). 1.50 deliberately overstates AUD spend. Re-check against an official rate before reporting a final figure.

### 8.1 Programme spending

| Item | USD | Evidence |
|---|---|---|
| Programme ledger, 18 entries | 13.418982 | `collaboration/budget/programme-ledger.json` (sum verified) |
| …of which matched to their durable ledgers exactly | 13 entries | `runs/*`, `scanner-data/live/*`, `hosted-copy/*`, research ledgers; fork copies of the Ironbark source run excluded (it is counted once) |
| …recorded above its ledger (conservative) | task011 0.351 vs 0.347663 | `runs/live-validation-011` |
| …recorded below its ledger (counted at the ledger value) | task012-stage1: +0.000336 | `runs/experiment-012/live` |
| …no local ledger: pre-event Tasks 004–007 (2.606), research-taskplan-1 (0.029054, an unsettled reservation, counted in full) | — | as recorded |
| **Unreconciled event-period spend found in durable ledgers** (the ledger's own "unreconciled" list) | **3.820762** | L0 probes 0.039212 (+ one unsettled reservation 0.00095, counted in full); L1a/EXP-B `site-5-live` +b +c increments 1.534404; EXP-2 `exp2-pilot-1` 1.141478; live taskgen smoke/exposure, 6 runs, 0.981919; investigator replay `replay-4bad5b1b` increment 0.122799 |
| **Reconciled known spend** | **17.240080** | = **A$25.86** at 1.50 |
| **Remaining against the A$50 allocation** | **A$24.14** (US$16.09 at 1.50) | a limit, not an authorisation |

Excluded as non-spend, because they used the dev provider, a mock, a dry run or a scripted rehearsal:
- `framework-runs/*`, `pilot-larkspur-dev-*`, `runs/*mock*`, `runs/*dry*`, all `rehearsal*` and `ironbark-operator/*` forks (they only copy the source run).

No other durable ledger on this machine records spend.

**No double counting:**
- Hosted runs are counted by their own fork ledgers, net of the copied source run.
- Research runs (pilot, M6, M7, taskplan) use separate experiment ledgers outside the hosted admission.
- The union of unique `(request id, timestamp)` settle events across every real ledger (US$14.600739) reconciles with the table above.

**Recommended append to the programme ledger** (not made; the ledger is yours): one entry `reconciliation-unreconciled-event-spend-1` = US$3.820762, plus the task012 correction of +US$0.000336.

### 8.2 Hosted admission (production)

Source: a copy of the production database taken 2026-11-02 06:22 UTC, after the paid trial (`scanner-data/hosted-copy/admission.sqlite`, sha256 `ef18cafd…`).

| | USD |
|---|---|
| Persisted policy | ceiling **10.000000**, unit 1.650000 per repetition, 120 s interval |
| Reservations (never released) | **3.300000**: 2 completed jobs (`eval-9aaac35c`, `eval-aa23e330`) × 1.650000 |
| Actual settled spend behind them | 2.217065 (1.090968 + 1.126097; both in 8.1) |
| Remaining capacity | **6.700000** |

Reserved capacity is a hold, not spend. It is never refunded or released.

The production database must be re-checked on the VM before migrating. `ceiling status` prints it, and `migrate` refuses unless the ceiling and reserved total still equal the values the owner states (`--expect-ceiling 10 --expect-reserved 3.3`).

### 8.3 One full `larkspur-core@v2` evaluation (Original + Modified, 1 repetition)

| | USD |
|---|---|
| Manifest | `64a55c5f…` (M7's, reused by the arming): 6 tasks × 2 variants = 12 trials, 14 requests each, US$0.044 per-request cap |
| Worst case (every trial at its request limit) | 12 × 14 × 0.044 = **7.392000** |
| Per-request allowance (the spend gate can settle at most one request above its reservation before it closes) | **0.044000** |
| **Hosted reservation for the launch** | **7.436000** |
| Experiment cap in the authorisation (manifest hard cap; the scope cap of the launch's own ledger) | 8.000000 (spend is bounded by the per-trial caps, at most the worst case) |
| Other costs of the new launch path | none: rehearsals reserve US$0; there is no Stage A call; the Stage B ledger and authorisation sit inside this reservation |

M7 actually spent US$1.520696 on the same manifest. Planning uses the worst case.

### 8.4 Recommended ceiling

Minimum = existing reservations 3.300000 + one launch 7.436000 = **US$10.736000. Recommendation: exactly US$10.736000.**
- It admits exactly one full six-task, two-variant evaluation and nothing more. After the launch the remaining capacity is US$0, so a second paid launch (for example after an infrastructure failure) needs another owner migration. This is by design.
- Programme check: worst case after the run, US$17.240080 + 7.436000 = US$24.676080 = **A$37.01**, inside A$50, with A$12.99 left at 1.50.

## 9. Ceiling migration (`python -m agent_readiness.hosted.ceiling`)

| Command | Behaviour |
|---|---|
| `status --db …/admission.sqlite` | read-only: policy, reservations by state, remaining, active jobs, migration history |
| `migrate --db … --to 10.736 --expect-ceiling 10 --expect-reserved 3.3 --reason "…"` | owner only, at an interactive terminal, with the app **stopped** |

**Protections:**
- **No API route:** nothing in the app can change the policy (tested). The operator token has no role.
- **Interactive and confirmed:** needs a TTY. The owner types the exact confirmation, which names the database path, the current and new ceiling, the reserved total, the job count and the reason.
- **Refuses** when:
  - the service holds the data directory (`.service.lock`);
  - any job is reserved or running;
  - the ceiling or reserved total differs from the owner's `--expect-*` values;
  - the database state is unexpected (schema, policy row count, non-integer or negative reservations);
  - the new ceiling is below the reservations held, below the per-repetition unit, above the programme limit (A$50 at 1.50 = US$33.333333), not whole microdollars, or equal to the current ceiling.
- **Atomic and audited:**
  - inside one `BEGIN IMMEDIATE` transaction it re-checks everything, updates one value (`policy.ceiling`, guarded by the old values) and appends one row to `policy_migrations` (from, to, unit, interval, reserved, jobs, a SHA-256 fingerprint of the whole jobs table, reason, typed confirmation, actor, host, time);
  - it verifies the jobs table is unchanged, then commits;
  - a crash leaves the old state (tested by a simulated crash before commit);
  - concurrent attempts apply at most once (tested with 4 threads);
  - re-running a completed migration is a no-op (`already applied`).
- **The fail-closed check is unchanged:** after migrating, a service started with the old `AR_HOSTED_CEILING_USD=10` stays disabled (`budget_policy_mismatch`). It must be started with `10.736`.

**Rehearsed** on a disposable copy of the production database in the candidate image:
1. `status` showed US$10 / US$3.30 / US$6.70.
2. Refusals: a wrong `--expect-reserved` was refused; without a TTY nothing changed.
3. The migration through a pseudo-terminal with the typed confirmation applied 10 → 10.736 (audit row #1). The jobs table is byte-identical to the original copy, and a re-run was a no-op.
4. Starting with `AR_HOSTED_CEILING_USD=10` gave `budget_policy_mismatch`; with `10.736` the service was enabled with the jail verified.
5. A paid arming of `larkspur-core@v2` was recorded through a pseudo-terminal on the copy ("fits for repetitions [1]").
6. With the container's network disabled (`--network none`, a dummy provider key, so no request can leave it), the operator API:
   - refused a launch without the token (403);
   - **admitted the launch with the token: US$7.436 reserved, total US$10.736 = the ceiling**;
   - the worker re-verified the claim, arming and authorisation, reserved the first request in the launch's own ledger before sending, failed to connect, voided the trial and halted with no retries;
   - the reservation stayed held, and a relaunch was refused ("All armed launches have been used").
7. The **previous image's admission code** on a copy of the migrated database: refused with `AR_HOSTED_CEILING_USD=10`, opened with `10.736`, counted the Stage B reservation, and admits no further repetition.

The in-process test (`test_hosted_ceiling.py`, against a copy of the real store) shows the same: at US$10 the exact M7 manifest is refused (429, nothing reserved or claimed); after the migration it is admitted at US$7.436 and nothing is sent.

**Fix found by the combined test run:** the worker's runtime jail extension (hiding `/app`, `/data`, secrets) mutated the declared jail policy
for the rest of the process, which would change the pinned agent hash that the arming verification compares. The worker re-checked before hardening
and then exits, so production was unaffected; the extension is now restored when execution ends (regression-tested).

**Observation from step 6:** after a provider connection error, browser-use's own step loop issued the trial's next request (also reserved first) before the runner recorded the trial void. Every request is still reserved before it is sent and bounded by the per-trial cap; no trial is re-run.

## 10. Owner decisions and approvals needed

1. Approve the **deployment** of the candidate (§11 steps 1–3).
2. Approve the **ceiling migration to US$10.736** (§11 step 4), with the reason stated.
3. **Arm** the paid experiment over SSH (§11 step 5). The arming id, and whether to allow 1 launch, are yours.
4. **Launch** from `#/run` with the operator token (§11 step 6). This incurs paid model calls (worst case US$7.436, M7 actual US$1.52).
5. **Optional:**
   - append the reconciliation entry to the programme ledger (§8.1);
   - owner web authentication (approval and arming stay terminal-only);
   - the merge strategy.

## 11. Deployment, migration, arming, launch, monitoring and rollback (NOT executed)

Production today:
- `evaluation-v2` @ `140a4e8`, image `agent-readiness-app:latest` = `evalv2-140a4e8d0bf8`;
- rollback images `rollback-b3121a8`, `rollback-60fcbc6`;
- live, operator access, `AR_HOSTED_CEILING_USD=10`.

`$VM` = the VM; `$SITE` = `209-38-84-72.sslip.io`; `<C>` = the M8 commit to deploy.

```sh
# 1. BACK UP (VM). The app keeps running while the volume is archived read-only.
mkdir -p /root/backups && docker run --rm -v agent-readiness_data:/data:ro -v /root/backups:/out alpine \
  tar czf /out/predeploy-m8-$(date -u +%Y%m%dT%H%M%SZ).tgz -C /data .
cp /root/agent-readiness/deploy/.env /root/backups/env-predeploy-m8

# 2. DEPLOY the image and the lifecycle store.
#    On the workstation:
tar czf /tmp/lifecycle-store.tgz -C scanner-data/research/stage-a store && scp /tmp/lifecycle-store.tgz root@$VM:/tmp/
#    On the VM:
docker run --rm -v agent-readiness_data:/data -v /tmp:/in alpine sh -c 'mkdir -p /data/hosted/lifecycle && tar xzf /in/lifecycle-store.tgz -C /data/hosted/lifecycle && chown -R 10001:10001 /data/hosted/lifecycle && chmod 700 /data/hosted/lifecycle/store/private'
git -C /root/agent-readiness fetch origin m8-product-integration && git -C /root/agent-readiness worktree add --detach /root/agent-readiness-build-m8 <C>
cd /root/agent-readiness-build-m8 && docker build -f deploy/Dockerfile -t agent-readiness-app:m8-<C> .
#    read-only budget check with the NEW image (the current image has no ceiling tool); expect US$10.000000 / US$3.300000 / 2 jobs / 0 active
docker run --rm -v agent-readiness_data:/data:ro agent-readiness-app:m8-<C> python -m agent_readiness.hosted.ceiling status --db /data/hosted/live/admission.sqlite
#    smoke test DISABLED on loopback against a COPY of the volume (as in DEPLOY.md), then switch:
docker tag agent-readiness-app:latest agent-readiness-app:rollback-140a4e8
docker tag agent-readiness-app:m8-<C> agent-readiness-app:latest
cd /root/agent-readiness/deploy && docker compose up -d --no-build --no-deps app

# 3. VERIFY the Stage B engine (still US$10; nothing armed).
docker compose logs app | grep 'hosted service'   # mode=live access=operator evaluations=enabled jail=verified engine=stage-b armed=none (not_armed)
curl -s https://$SITE/api/health; curl -s https://$SITE/api/ironbark/config | head -c 400            # engine stage-b, available false, reason not_armed
curl -s -o /dev/null -w '%{http_code}\n' https://$SITE/api/ironbark/jobs/eval-aa23e33012717c4a30ca21be1239e85f   # 200: history intact
#    browse #/run (history), #/lifecycle, #/reports/m7-larkspur-browser-1

# 4. CEILING MIGRATION (owner; app stopped; reservations unchanged).
docker compose stop app
docker compose run --rm --no-deps -it app python -m agent_readiness.hosted.ceiling migrate --db /data/hosted/live/admission.sqlite \
  --to 10.736 --expect-ceiling 10 --expect-reserved 3.3 --reason "one full six-task Original-vs-Modified paid evaluation of larkspur-core@v2"
#    type the confirmation shown; then:
sed -i 's/^AR_HOSTED_CEILING_USD=.*/AR_HOSTED_CEILING_USD=10.736/' .env && docker compose up -d --no-build --no-deps app
docker compose logs app | grep 'hosted service'   # evaluations=enabled (a mismatch would show budget_policy_mismatch: fix .env, never the database)

# 5. PREPARE AND ARM the paid experiment (owner, over SSH).
docker compose exec app     python -m agent_readiness.lifecycle.arming prepare --arming larkspur-live-1 --mode paid --frozen larkspur-core@v2 --variants original modified --repetitions 1 --launches 1
#    check: manifest 64a55c5f..., 12 trials, reserves US$7.436000, "fits for repetitions [1]"
docker compose exec -it app python -m agent_readiness.lifecycle.arming arm     --arming larkspur-live-1 --mode paid --frozen larkspur-core@v2 --variants original modified --repetitions 1 --launches 1
#    type the attestation shown

# 6. LAUNCH through the existing UI: https://$SITE/#/run -> operator token -> 1 repetition -> Run evaluation
#    (equivalently: docker compose exec app python -m agent_readiness.hosted.admin start --repetitions 1)

# 7. MONITOR spend and execution
docker compose exec app python -m agent_readiness.hosted.admin watch <eval-id>
docker compose exec app python -m agent_readiness.hosted.ceiling status --db /data/hosted/live/admission.sqlite        # reserved US$10.736
docker compose exec app sh -c 'wc -l /data/hosted/lifecycle/stage-b/ledgers/larkspur-live-1-l1/ledger.jsonl'          # reserve/settle lines
docker compose exec app python -m agent_readiness.lifecycle.arming status                                              # launches left 0
#    the workspace shows live progress, then the readiness report; the report's Spend line shows the settled ledger total
#    to stop at once: docker compose stop app (the run is never resumed; its reservation stays held)
```

After the run, append its settled total to the programme ledger, as for M7.

### 11.1 Rollback

```sh
docker tag agent-readiness-app:rollback-140a4e8 agent-readiness-app:latest
docker compose up -d --no-build --no-deps app
```

**If rolled back after the ceiling migration:**
- The previous image opens the same database. With `AR_HOSTED_CEILING_USD=10.736` in `.env` it admits normally against the migrated ceiling. With `10` it stays fail-closed (`budget_policy_mismatch`; history viewable).
- Either way **the increased ceiling and every reservation remain in the database**. Nothing is reset, and the Stage B reservation keeps counting, so the old engine cannot spend it again (verified).
- To reduce the ceiling afterwards, run another `ceiling migrate`. It is refused below the reservations held (US$10.736 after the launch), so after a launch the ceiling cannot go back below US$10.736.

**Full data restore** (only if the database itself must be returned to its pre-deploy state; this discards every later reservation and run): `docker compose stop app`, restore the step-1 archive into the volume, restore `.env` from `env-predeploy-m8`, then start the rollback image. Never do this after a paid launch: its spend would vanish from the hosted accounting (it stays in the programme ledger).

## 12. Limitations and risks

- **No paid Stage B launch has run in the product yet.** The paid path was exercised up to the first request (network disabled) and the runner's paid branch is the one M7 used.
- **A failed or interrupted paid launch consumes the whole reservation and the launch number;** a retry needs a new arming and a new ceiling migration (by design).
- **The worker re-checks the arming;** an arming edited or disarmed after launch makes the worker refuse (fail-closed).
- **The production admission state is known from the 2026-11-02 06:22 UTC copy.** `migrate --expect-*` refuses if it differs.
- **Unreconciled spend is from local ledgers;** any spend never recorded in a ledger (for example outside this machine) cannot be counted.
- **Re-evaluation** is limited to registered snapshots; Ironbark has no owner-approved frozen lifecycle suite.
- **Prospective grading rules are heuristics;** dataset v1 is immutable.
