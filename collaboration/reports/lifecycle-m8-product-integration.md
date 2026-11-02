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
| `tests/test_hosted_api.py` (adapted to the Stage B executor; + "the retired engine cannot launch") | 7 passed |
| `tests/test_hosted_service.py` (adapted: store precondition, `engine=stage-b armed=…` log, busy feedback) | 17 passed |
| `tests/test_lifecycle_m8.py` | 20 passed |
| `tests/test_lifecycle_m8_browser.py` (rewritten): **operator launch through `/api/ironbark/jobs` → real worker subprocess → jailed Chromium → hosted progress/live/trial/screenshot/export → lifecycle report**, run alone | 1 passed (56–104 s) |
| `tests/test_evalruns_m5.py -m browser` (existing, alone) | 1 passed |
| Broad regression (lifecycle M1–M8, graders, hosted, diagnostics, framework, deployment-safety and export scripts; not browser) | 330 passed, 5 deselected |
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

## 8. Budget: why a paid launch of `larkspur-core@v2` does not fit today

A launch reserves the manifest's worst case (every trial at its 14-request limit, each request at the verified US$0.044 per-request cap) plus one request bound.

For `larkspur-core@v2` with 1 repetition, that is 6 tasks × 2 variants × 14 × US$0.044 + US$0.044 = **US$7.436**. Production has US$3.30 reserved of the US$10 ceiling, leaving **US$6.70**, so the launch is **refused (fail-closed)**. The M7 run actually spent US$1.52, but reservations are worst-case by design and are never released.

## 9. Owner decisions needed

1. **Budget for the first live Stage B evaluation:** one of the following.
   - **(a)** Raise the hosted ceiling. This needs an owner-run reconciliation of the persisted admission policy, which today disables evaluations on any env mismatch. It is not implemented; I can implement it on request.
   - **(b)** Approve and freeze a smaller suite at the terminal. 5 tasks reserve US$6.204; 4 tasks reserve US$4.972. Task selection must come from Stage A rules, not from M7 outcomes.
   - **(c)** Evaluate one variant only. 6 tasks × Modified reserves US$3.74, but there is no Original/Modified comparison.

   For the Original-vs-Modified demo on the M7 suite, (a) is the honest route; (b) keeps the US$10 ceiling.
2. **Paid arming:** to be done by you over SSH (`arming prepare` → `arming arm`). The arming id, repetitions and number of launches are yours to choose.
3. **Deploy** the candidate (§10), and whether to copy the lifecycle store onto the VM. The store is required for evaluations; without it the site serves view-only.
4. **Merge strategy** (research → `evaluation-v2` → `main`).
5. **Owner web authentication:** still undecided. Approval and arming stay terminal-only.

## 10. Deployment procedure (NOT executed; needs owner approval)

Production today:
- `evaluation-v2` @ `140a4e8`, image `agent-readiness-app:latest` = `evalv2-140a4e8d0bf8`;
- rollback images `rollback-b3121a8`, `rollback-60fcbc6`;
- live, operator access, US$10 ceiling.

```sh
# 0. on this machine: package the lifecycle store (public objects 0444, private outcomes 0400) for the VM; scp only
tar czf /tmp/lifecycle-store.tgz -C scanner-data/research/stage-a store
scp /tmp/lifecycle-store.tgz <user>@<vm>:/tmp/

# 1. on the VM: backup, store, build
docker run --rm -v agent-readiness_data:/data -v /root/backups:/out alpine tar czf /out/predeploy-m8-$(date -u +%Y%m%dT%H%M%SZ).tgz -C /data .
docker run --rm -v agent-readiness_data:/data -v /tmp:/in alpine sh -c \
  'mkdir -p /data/hosted/lifecycle && tar xzf /in/lifecycle-store.tgz -C /data/hosted/lifecycle && chown -R 10001:10001 /data/hosted/lifecycle && chmod 700 /data/hosted/lifecycle/store/private'
git -C /root/agent-readiness fetch origin m8-product-integration
git -C /root/agent-readiness worktree add --detach /root/agent-readiness-build-m8 <M8_COMMIT>
cd /root/agent-readiness-build-m8 && docker build -f deploy/Dockerfile -t agent-readiness-app:m8-<short> .

# 2. smoke test the candidate DISABLED on loopback against a COPY of the volume (as in DEPLOY.md):
#    /api/health; /api/ironbark/jobs (history incl. eval-aa23e330, eval-9aaac35c); a historical job's status/trials/export;
#    /api/lifecycle/evaluations/m7-larkspur-browser-1; #/run, #/lifecycle, #/reports/m7-larkspur-browser-1
#    optional, zero cost: the same copy in REHEARSAL mode, arm a rehearsal over `docker exec -it`, launch once with the token (§7.1)

# 3. switch
docker tag agent-readiness-app:latest agent-readiness-app:rollback-140a4e8
docker tag agent-readiness-app:m8-<short> agent-readiness-app:latest
cd /root/agent-readiness/deploy && docker compose up -d --no-build --no-deps app
docker compose logs app | grep 'hosted service'   # mode=live … evaluations=enabled jail=verified engine=stage-b armed=none (not_armed)

# 4. (owner, when decided) arm a paid evaluation, then the operator launches from #/run
docker compose exec app    python -m agent_readiness.lifecycle.arming prepare --arming <id> --mode paid --frozen <suite>@vN --variants original modified --repetitions 1 --launches 1
docker compose exec -it app python -m agent_readiness.lifecycle.arming arm     …same arguments…
```

No `.env`, secret, ceiling or access change is needed. `AR_SOURCE_RUN` is no longer required (its mount may stay). New data appears only under:
- `/data/hosted/lifecycle/` (store; `stage-b/` holds armings, claims, authorisations and ledgers);
- `/data/hosted/live/stageb/` (Stage B jobs and runs).

**Rollback:**

```sh
docker tag agent-readiness-app:rollback-140a4e8 agent-readiness-app:latest
docker compose up -d --no-build --no-deps app
```

Data compatibility:
- The old image ignores `lifecycle/` and `live/stageb/`.
- It opens the same admission DB: the policy row is unchanged.
- It counts Stage B reservations against the ceiling, which is correct: money may have been spent.
- It skips Stage B jobs in its history list.
- Stage B results stay on the volume and reappear on roll-forward.

## 11. Limitations

- **No paid Stage B launch has run in the product.** The paid branch of the runner is the one M7 used; the new code up to it is tested with stubs, and the same pipeline was exercised end to end in rehearsal mode in the container.
- **Re-evaluation** is limited to registered snapshots (Larkspur and Ironbark: original, modified). A new website release needs a registered snapshot and a new arming.
- **Ironbark has no owner-approved frozen lifecycle suite;** only Larkspur does.
- **The repetition-duration estimate** in the workspace is a fixed basis (about 50 s per trial, from M7) until Stage B jobs accumulate.
- **Prospective grading rules** are heuristics (English-only contrast markers).
- **Dataset v1** was finalised at the M8.2 commit; projection changes require a v2.
