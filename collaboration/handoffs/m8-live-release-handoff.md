# Handoff: M8 live-evaluation release candidate (hosted evaluation on the Stage B engine)

**Written:** 2026-11-04, at the end of the Claude Code (Opus) session that built M8.
**For:** a fresh agent taking over the release.
**Release candidate:** `m8-product-integration` @ **`e080a8d`** (pushed to `origin`). The commit that adds this file sits on top of it.

**Status of this document.**
- It authorises nothing: no deployment, ceiling migration, arming, paid call, merge or production change.
- Where it and the code disagree, the code wins.
- `STATUS.md` remains the authoritative project record.
- **Production was not accessed in this session.** Production facts below come from the deploy records, the trial report and a copy of the production admission database taken 2026-11-02 06:22 UTC. Re-verify them on the VM (read-only) before acting.

**Read next:**
1. this file;
2. [`collaboration/reports/lifecycle-m8-product-integration.md`](../reports/lifecycle-m8-product-integration.md), the M8 report: architecture, reconciliation and the full runbook (§11);
3. [`STATUS.md`](../../STATUS.md);
4. [`deploy/DEPLOY.md`](../../deploy/DEPLOY.md);
5. [`AGENTS.md`](../../AGENTS.md), the rules: no paid calls without owner approval, never `git add -A`, preserve untracked owner files;
6. the earlier handoff, [`collaboration/handoffs/m8-product-integration.md`](m8-product-integration.md), for M1–M7 background.

---

## 1. Repository state

| | |
|---|---|
| Branch | `m8-product-integration` (= `origin/m8-product-integration`) |
| HEAD | `e080a8dafd530a26e77cd1fafae16f13723f2678` (before this handoff commit) |
| Working tree | clean except two **untracked owner files**: `src/agent_readiness/investigate/prototype/` and `tests/test_termvalue_prototype.py`. Never stage, move or delete them. `uv.lock` is deliberately untracked. Use explicit `git add <paths>`; never `git add -A`. |
| Based on | `research/llm-task-planning` @ `604599a` (the M2–M7 lifecycle + the M8 handoff); HEAD is 7 commits ahead, 0 behind |
| Production branch | `evaluation-v2` @ `bf55db7`. **Deployed commit `140a4e8` is an ancestor of HEAD.** HEAD is 32 ahead of and 3 behind `evaluation-v2`. The 3 missing commits (`50e05eb`, `d542de9`, `bf55db7`) are programme-ledger appends whose 16 entries are byte-identical in HEAD's ledger (verified). HEAD's ledger additionally holds `research-stage-a-m6-1` and `research-stage-b-m7-1`. A merge would conflict only trivially in `collaboration/budget/programme-ledger.json` (keep HEAD's superset). |
| `main` | `df85106`; does not reproduce production; HEAD is 111 ahead. **Merging needs the owner.** |
| `product-experience-redesign` | `820e0ad`, frozen ("do not modify") |

M8 commits (oldest first):
1. `9b11545` M8.1: product layer, projection, dataset, lifecycle API.
2. `682d8ef` M8.2: lifecycle web UI, report, traces, diagnostics behavioral-2.
3. `e54c257` M8.3: browser e2e, datasets in the image, docs.
4. `ac47d4f` M8.4: wheel packaging fix, screenshots.
5. **`bc2e691` M8.5: the hosted evaluation runs the Stage B engine; the paired engine is retired.**
6. `b36f56b` M8.6: container release rehearsal, docs.
7. **`e080a8d` M8.7: budget reconciliation and the owner-authorised ceiling migration.**

Product-code delta against the deployed `140a4e8` (`git diff --stat 140a4e8..HEAD -- src/agent_readiness/hosted deploy dashboard/src/site/workspace pyproject.toml`):

| File | Change |
|---|---|
| `hosted/api.py` | Stage B routing; legacy start removed |
| `hosted/admission.py` | `reserve_amount` |
| `hosted/serve.py` | Stage B executor, lifecycle paths |
| `hosted/paired.py` | old execution code deleted |
| `hosted/stageb.py` | **new** |
| `hosted/ceiling.py` | **new** |
| `deploy/Dockerfile` | datasets, lifecycle env |
| `pyproject.toml` | fixture package data |
| `dashboard/src/site/workspace/*` | armed suite, report tab, frame label |

Everything else is new packages (`src/agent_readiness/lifecycle/`, `datasets/`) or research code the old image never imported.

## 2. Architecture: the hosted live workflow on the Stage B engine

The operator experience is unchanged. In `#/run`:
1. paste the operator token;
2. choose repetitions;
3. press **Run evaluation**.

The server receives `POST /api/ironbark/jobs {"repetitions": 1|3|5}` with `Authorization: Bearer <token>`. It shows live progress, the worker banner, the live agent view with real screenshots, the task grid and the history. Only the engine and the results view changed.

```
owner (SSH, TTY)   lifecycle.arming arm ──► <STAGE_B>/armings/<id>.json (write-once) + ACTIVE
operator (web)     POST /api/ironbark/jobs {"repetitions"} + bearer
  hosted/api.py start ─► StageBExecutor.admit (hosted/stageb.py)
     1 active arming verifies; its mode matches the service (live → paid, rehearsal → rehearsal); repetitions armed; launches left; total left
     2 Admission.reserve_amount(job, client, worst case + one request bound)   [same DB, single slot, US$ ceiling, rate limit; never released]
     3 arming.launch: claim <STAGE_B>/launches/<arming>-l<N>.json (exclusive create)
                      + (paid) <STAGE_B>/authorizations/<arming>-l<N>.json (write-once PaidAuthorization, instruction = the owner's attestation)
     4 job record <root>/stageb/jobs/<eval-id>.json
  thread work ─► LifecycleExecutor.run ─► subprocess `python -m agent_readiness.lifecycle.jobs` (new session, parent-death signal, 3 h timeout, group kill)
     worker run_job: arming.check_launch (claim names this job; arming, manifest, authorisation, unused ledger) + reservation == claim
       rehearsal: paired._loopback_only_sockets()   paid: paired._load_key_file()
       evalruns.runner.prepare(mode) → harden_jail (adds /app, /data, secrets, store, runs; restored afterwards)
       → runner.execute(authorization=…)   [jailed Chromium; paid: AU.verify again, reserve-before-send per request in <STAGE_B>/ledgers/<experiment>/,
                                            per-trial cap 14 × US$0.044, scope cap = authorisation cap, trials counted from the ledger, no retries,
                                            halt on a void trial or bound violation]
       → runner.report → runner.audit_public; job "completed" only if the audit is clean and nothing stopped
  api.work: completed only if lifecycle.evaluation(job) projects and passes lifecycle.audit
results            /api/lifecycle/evaluations/<eval-id> = lifecycle/projection.py (the SAME projection as the M7 dataset) → "Readiness report" tab, #/reports/<id>
```

**Hosted routes for Stage B jobs** (`hosted/api.py` + `hosted/stageb.py`):
- `status`, `trials/{arm}/{task}`, `screenshots`, `live` and `export` read Stage B trial records. `export` returns the audited evaluation document.
- `insights` returns 409; the diagnostics are in the report.
- Historical jobs of the retired paired engine (`eval-9aaac35c`, `eval-aa23e330`) keep their original read-only views.

**Boundaries:**
- `hosted/*` reaches research code only through `agent_readiness.lifecycle`. This is enforced by `tests/test_suites_m1.py`, `tests/test_evalruns_m5.py` and `tests/test_diagnostics.py`.
- Stage A code never sees Stage B outcomes (`suites/boundary.py`).
- Private oracle data leaves the server only as counts. Rehearsal views withhold the stand-in's replies.
- Official grader v1 is reported as recorded; v2 is post-hoc; v2.1-contrast and `evidence-ranked-subset-2` are prospective.

## 3. Contracts and safeguards

| Topic | Implementation | Where |
|---|---|---|
| Launch contract | body `{"repetitions"}` only (`extra=forbid`: `url`/`tasks`/`model`/`cap_usd` → 422); operator-only in operator access (403); not armed / repetitions not armed / launches used → 409; no budget or busy slot → 429; an executor without the Stage B interface → 503 | `hosted/api.py` `start` |
| Frozen-suite selection | server-side, from the active arming only: an owner-approved frozen suite (exact hash), registered variants (`lifecycle/sites.py`), one exact manifest per repetition count (`arming.select_manifest`: an existing manifest is reused, e.g. M7's `64a55c5f…`; else a regression manifest differing only in variants; else a new one with hard cap = worst case) | `lifecycle/arming.py` |
| Owner arming | `prepare` (read-only plan, fit verdict, attestation) / `arm` (needs `isatty()`, typed exact attestation, write-once 0444, sets `ACTIVE`) / `status` / `disarm`; paid armings refuse synthetic suites; `verify` checks approval, snapshots, manifests (suite, variants, repetitions, trials, cap, reservation), pinned agent (full config incl. jail-policy hash) and the re-rendered attestation, at arming, at start, at launch and in the worker | `lifecycle/arming.py` |
| Admission | `Admission.reserve_amount`: same DB, slot, ceiling and rate limit as repetitions; ids `eval-<32 hex>`; amounts > ceiling → `Refused`; the persisted policy row is untouched | `hosted/admission.py` |
| Reservation per launch | `min(worst case, hard cap) + per-request cap`, rounded up to microdollars; rehearsal = US$0 | `arming.reservation_microusd` |
| Jail | `jail.require()` + self-test before any trial; the worker adds the deployment policy's hidden paths + store, runs, Stage B roots at runtime, restored after execution | `lifecycle/jobs.py` `harden_jail`, `hosted/jail.py` |
| Ledger | per launch `<STAGE_B>/ledgers/<arming>-l<N>/ledger.jsonl`; reserve-before-send; failure keeps the reservation; never re-run | `evalruns/runner.py`, `spend_gate.py`, `ledger.py` |
| Crash recovery | `api.recover` kills surviving workers, marks the admission row and the Stage B job file `interrupted` (reservation kept); the launch number stays used | `hosted/api.py` `recover` |
| Reporting | `lifecycle/projection.py` (six dimensions, no composite score), `lifecycle/audit.py` (leak audit), the report UI `dashboard/src/site/lifecycle/{Report,Trace}.tsx`, embedded in `dashboard/src/site/workspace/HostedEvaluation.tsx` | |
| Web approval | refused (403) for everyone; suite approval, freezing and arming are terminal-only | `lifecycle/service.py` `decide` |

## 4. Production deployment state (as last verified; re-check read-only)

| Item | Value |
|---|---|
| URL | https://209-38-84-72.sslip.io (DigitalOcean, Ubuntu 24.04, 2 vCPU / 4 GB + 2 GB swap) |
| Deployed | `evaluation-v2` @ `140a4e8` (2026-11-02 07:12 UTC); image `agent-readiness-app:latest` = `evalv2-140a4e8d0bf8` |
| Rollback images on the VM | `agent-readiness-app:rollback-b3121a8`, `agent-readiness-app:rollback-60fcbc6` (step 2 below adds `rollback-140a4e8`) |
| Checkout / compose | `/root/agent-readiness`, `deploy/compose.yaml` (app + Caddy; `cap_drop ALL`, `no-new-privileges`, seccomp, AppArmor and systempaths unconfined for the jail, 4 GB, 1024 pids) |
| `deploy/.env` (VM) | `SITE_ADDRESS`, `AR_SOURCE_RUN=/srv/agent-readiness/live-2d58a80e14`, `AR_HOSTED_MODE=live`, `AR_HOSTED_ACCESS=operator`, `AR_HOSTED_CEILING_USD=10` |
| Secrets (VM) | `deploy/secrets/meta_model_api_key`, `deploy/secrets/operator_token` (uid 10001, 0400) → `/run/secrets/*` |
| Volume | `agent-readiness_data` → `/data`. Hosted root `/data/hosted/live/`: `admission.sqlite`, `client.key`, `eval-*.job.json`, `paired-*` runs, `derived/` |
| Admission DB (copy 2026-11-02 06:22 UTC, `scanner-data/hosted-copy/admission.sqlite`, sha256 `ef18cafd…`) | policy ceiling 10 000 000 µUS$, unit 1 650 000, interval 120 s; jobs `eval-9aaac35c…` and `eval-aa23e330…`, both completed, 1 650 000 each → **reserved US$3.30, remaining US$6.70** |
| New in the M8 image (Dockerfile ENV) | `AR_LIFECYCLE_DATASETS=/app/datasets/lifecycle`, `AR_LIFECYCLE_STORE=/data/hosted/lifecycle/store`, `AR_STAGE_B_ROOT=/data/hosted/lifecycle/stage-b` |
| New data after deploy | `/data/hosted/lifecycle/store/` (copied from the workstation, §9 step 2); `/data/hosted/lifecycle/stage-b/{armings,launches,authorizations,ledgers}/`; `/data/hosted/live/stageb/{jobs,evalruns,reports,derived}/` |
| Startup preconditions (new engine) | the lifecycle store (`lifecycle_store_missing`), token, key (live), ceiling == persisted policy (`budget_policy_mismatch`), jail self-test. The log line ends `engine=stage-b armed=<…>` |

## 5. Spending reconciliation

USD is **calculated** from provider-reported tokens at the verified prices (US$1.25 / US$4.25 per M); nothing is a bill.

AUD uses the programme ledger's **conservative planning assumption of 1.50 AUD/USD** (set 2026-10-29; market about 1.43–1.45, per exchange-rates.org on 2026-10-01). It is an estimate that overstates AUD.

**Authoritative records:**
- per-run **durable ledgers** (`ledger.jsonl` reserve/settle lines, settled from provider usage);
- the **hosted admission DB** (reservations);
- `collaboration/budget/programme-ledger.json` (the owner's append-only programme record; a known-spend subtotal, partially reconciled by its own statement).

**Estimates:**
- AUD conversions;
- unsettled reservations counted in full;
- "worst case" figures.

| | USD |
|---|---|
| Programme ledger, 18 entries (sum verified) | 13.418982 |
| 13 entries match their durable ledgers exactly | — |
| `task011`: recorded 0.351 vs ledger 0.347663 (recorded higher, conservative; kept) | — |
| **`task012-stage1`: recorded 0.718 vs ledger 0.718336, a correction of +0.000336** (counted at the ledger value) | +0.000336 |
| No local ledger: pre-event Tasks 004–007 (2.606) and `research-taskplan-1` (0.029054, an unsettled reservation counted in full) | as recorded |
| **Previously unrecorded event-period spend** (the ledger's own "unreconciled" list), found in local durable ledgers, forks de-duplicated by `(request id, timestamp)`: L0 probes 0.039212 + unsettled reservation 0.000950; L1a/EXP-B `investigations/site-5-live` (+b, +c increments) 1.534404; EXP-2 `investigations/exp2-pilot-1` 1.141478; live taskgen smoke/exposure (`scanner-data/live/live-{46b6ba92b8,96a6c3ab04,b6d91a8a33,bb5d48501b,cb37cc9849,d722f23670}`) 0.981919; investigator replay `scanner-data/live/replay-4bad5b1b` increment 0.122799 | **+3.820762** |
| **Reconciled known spend** | **17.240080** (= A$25.86) |
| **Remaining of the A$50 allocation** | **A$24.14** (US$16.09 at 1.50). A limit, not an authorisation. |

**Excluded as non-spend:**
- dev provider: `scanner-data/framework-runs/*`, `pilot-larkspur-dev-*`;
- mock and dry runs: `runs/*mock*`, `runs/*dry*`;
- rehearsals;
- `scanner-data/ironbark-operator/*` (copies of the source run).

**No overlap:**
- Hosted runs are counted net of the copied Ironbark source run, which is recorded once as `ironbark-source`.
- Research runs (pilot, M6, M7, taskplan) used separate experiment ledgers outside the hosted admission.
- The union of unique settle events across every real ledger (US$14.600739) reconciles with the table.

**Not yet appended to the programme ledger** (owner's decision): one entry of US$3.820762 and the +US$0.000336 correction.

**Hosted admission:** US$3.30 is reserved, backed by US$2.217065 of actual spend (hosted-live-1 + hosted-live-2). That is capacity held, never released.

**One full `larkspur-core@v2` evaluation** (Original + Modified, 1 repetition, manifest `64a55c5f3a936766627a596af233595efd7c35cd448397f32357b604e6981377`):
- 12 trials × 14 requests × US$0.044 = US$7.392 worst case;
- \+ US$0.044 request bound = **US$7.436 hosted reservation**;
- experiment cap in the authorisation US$8.00 (the manifest hard cap; spend is bounded by the per-trial caps);
- M7 actually spent US$1.520696;
- no other cost in the new path (rehearsals reserve US$0).

**Recommended ceiling: exactly US$10.736** (3.30 + 7.436). It admits one launch and nothing more. Worst case after it: US$24.676080 = A$37.01, leaving A$12.99.

## 6. Ceiling migration (`src/agent_readiness/hosted/ceiling.py`)

- `status --db …` (read-only, works on a `:ro` mount): policy, reservations by state, remaining, active jobs, migration history.
- `migrate --db … --to 10.736 --expect-ceiling 10 --expect-reserved 3.3 --reason "…"`.

**Invariants:**
- **Access:** no API route; needs a TTY and the owner's typed confirmation, which names the absolute DB path, from and to ceilings, the reserved total, the job count and the reason.
- **Refuses** if:
  - the service holds `<root>/.service.lock` (run it with the app stopped);
  - any job is reserved or running;
  - the ceiling or reserved total differs from the `--expect-*` values;
  - the schema, policy row (exactly one) or job reservations are unexpected;
  - the new ceiling is below the reservations, below the per-repetition unit, above US$33.333333 (A$50 at 1.50), not whole microdollars, or unchanged.
- **Atomic:** in one `BEGIN IMMEDIATE` transaction it re-checks the snapshot, then:
  - updates `policy.ceiling` (guarded by the old ceiling, unit and interval);
  - creates and appends `policy_migrations` (from, to, unit, interval, reserved, jobs, jobs-table SHA-256 fingerprint, reason, confirmation, actor, host, time);
  - re-verifies the jobs table, then commits.
- **Crash, concurrency, idempotence:** a crash leaves the old state; concurrent attempts apply once; re-running a completed migration is a no-op.
- **Fail-closed kept:** the service still requires `AR_HOSTED_CEILING_USD` == the persisted ceiling (`budget_policy_mismatch` otherwise).

**Expected DB state:**
- Before: `ceiling 10000000`, 2 jobs (completed, 1 650 000 each), 0 active, no `policy_migrations`.
- After: `ceiling 10736000`, the same 2 jobs (byte-identical), one audit row.
- After the launch: reserved 10 736 000 (remaining 0).

**Tests:** `tests/test_hosted_ceiling.py`, 24 tests. One of them, the exact-M7 admission test, needs the local store and is skipped elsewhere.

**Rehearsed** on a disposable copy of the production DB in the candidate image (M8 report §9):
- refusals;
- the pseudo-terminal migration;
- byte-identical jobs;
- an idempotent re-run;
- `.env` 10 → `budget_policy_mismatch`, `.env` 10.736 → enabled;
- paid arming on the copy;
- with `--network none` and a dummy key, the launch admitted at US$7.436 (total = ceiling), reserved first request, connection failure, void trial, halt with no retry, relaunch refused;
- the previous image on the migrated copy: refuses with 10, opens with 10.736, counts the Stage B reservation.

**Rollback limitations:**
- The migration is **not undone by an image rollback**. The old image opens the migrated DB and admits only with `AR_HOSTED_CEILING_USD=10.736`; with 10 it stays fail-closed.
- A later decrease is another migration, refused below the reservations held. After the launch the ceiling can never go below US$10.736.
- Restoring the pre-deploy volume backup discards later reservations and runs. **Never do this after a paid launch**: its spend would vanish from hosted accounting.

## 7. Risks and open issues

1. **No paid evaluation has run through the new hosted path.** The paid branch was exercised up to the first request, with the network disabled. The runner's paid branch is the one M7 used successfully. The first live launch is the first real test: watch it (§9 step 7).
2. **The production admission state is known from a 2-day-old copy.** `migrate --expect-*` refuses if it changed. Read `ceiling status` on the VM first.
3. **A failed or interrupted paid launch** consumes its whole reservation and its launch number. A retry needs a new arming and another ceiling migration.
4. **Inside a trial,** browser-use's step loop may issue its next request after a provider error before the trial is voided. Each request is still reserved first and capped per trial; trials are never re-run.
5. **The worker re-checks the arming.** Disarming, or a changed arming, after launch makes the worker refuse (fail-closed, reservation kept).
6. **Reconciled spend covers only ledgers on this workstation;** unrecorded spend elsewhere cannot be counted. AUD is a planning estimate.
7. **Coverage gaps:** Ironbark has no owner-approved frozen lifecycle suite; re-evaluation is limited to registered snapshots; business contexts are SYNTHETIC.
8. **Owner web authentication is undecided;** approval and arming are terminal-only.
9. **The M7 suite misses its provisional coverage targets** (disclosed in the review packet). Six tasks × 1 repetition is exploratory: no improvement claim.

## 8. Zero-cost test results at `e080a8d`, and how to reproduce them

No test calls a model. Run browser tests **alone**.

```bash
cd ~/Projects/Hack_Agent_Readiness
# lifecycle, hosted (incl. ceiling and Stage B), graders, diagnostics, framework, deployment safety — 354 passed, 5 deselected
.venv/bin/python -m pytest -q -p no:cacheprovider -m "not browser" tests/test_suites_m1.py tests/test_taskeval.py tests/test_research_taskplan.py \
  tests/test_taskeval_v2.py tests/test_kinds_m2b.py tests/test_stage_a_loop.py tests/test_lifecycle_m4.py tests/test_evalruns_m5.py tests/test_m6_stage_a_preflight.py \
  tests/test_m7_paid_guard.py tests/test_lifecycle_m8.py tests/test_hosted_stageb.py tests/test_hosted_ceiling.py tests/test_grader_v2.py tests/test_grader_v2_rescore.py \
  tests/test_hosted_api.py tests/test_hosted_admission.py tests/test_hosted_service.py tests/test_hosted_derived_cache.py tests/test_hosted_jail.py tests/test_diagnostics.py \
  tests/test_framework.py dashboard/scripts/test_deployment_safety.py dashboard/scripts/test_export_replay.py
bash scripts/critical-tests.sh                                                     # 214 passed, 17 deselected
(cd dashboard && npx vitest run)                                                   # 198 passed (18 files)
(cd dashboard && npm run build)                                                    # tsc + vite + check:dist: CHECK PASSED
.venv/bin/python -m pytest -q -p no:cacheprovider tests/test_lifecycle_m8_browser.py -m browser   # 1 passed (56–113 s): operator launch → worker → jailed Chromium → report
.venv/bin/python -m pytest -q -p no:cacheprovider tests/test_evalruns_m5.py -m browser            # 1 passed (existing M5 e2e)
.venv/bin/python -m agent_readiness.lifecycle.dataset validate datasets/lifecycle/m7-larkspur-browser-1/v1 \
  --store scanner-data/research/stage-a/store --run scanner-data/research/stage-b/paid/evalrun-paid-64a55c5f3a-natural \
  --generation scanner-data/research/stage-a/m6-larkspur-core-20261102T121242Z               # valid, rederived_from_source: true
docker build -f deploy/Dockerfile -t agent-readiness-app:m8-candidate .           # built locally as 4b526b453e2a
```

**Container rehearsals** (M8 report §7.1, §9), all on disposable copies:
- **rehearsal mode:** terminal arming, operator launch, 12/12 jailed trials of `larkspur-core@v2`, report, relaunch refused, restart-safe;
- **disabled mode:** historical jobs and M7 dataset all 200;
- **live paid path:** ceiling migration, then the paid path with `--network none` (above).

## 9. Release procedure (NOT executed; each production step needs owner approval)

`$SITE` = `209-38-84-72.sslip.io`; `<C>` = the commit to deploy (`e080a8d`, or this handoff's commit, which changes documentation only). The full annotated version is in M8 report §11.

```sh
# 1. BACKUP (VM)
mkdir -p /root/backups && docker run --rm -v agent-readiness_data:/data:ro -v /root/backups:/out alpine \
  tar czf /out/predeploy-m8-$(date -u +%Y%m%dT%H%M%SZ).tgz -C /data .
cp /root/agent-readiness/deploy/.env /root/backups/env-predeploy-m8

# 2. DEPLOY image + lifecycle store
#    workstation:
tar czf /tmp/lifecycle-store.tgz -C scanner-data/research/stage-a store && scp /tmp/lifecycle-store.tgz root@<vm>:/tmp/
#    VM:
docker run --rm -v agent-readiness_data:/data -v /tmp:/in alpine sh -c 'mkdir -p /data/hosted/lifecycle && tar xzf /in/lifecycle-store.tgz -C /data/hosted/lifecycle \
  && chown -R 10001:10001 /data/hosted/lifecycle && chmod 700 /data/hosted/lifecycle/store/private'
git -C /root/agent-readiness fetch origin m8-product-integration && git -C /root/agent-readiness worktree add --detach /root/agent-readiness-build-m8 <C>
cd /root/agent-readiness-build-m8 && docker build -f deploy/Dockerfile -t agent-readiness-app:m8-<C> .
docker run --rm -v agent-readiness_data:/data:ro agent-readiness-app:m8-<C> python -m agent_readiness.hosted.ceiling status --db /data/hosted/live/admission.sqlite
#    expect: ceiling US$10.000000, US$3.300000 reserved by 2 completed jobs, 0 active. If different: STOP and recompute the ceiling.
#    smoke test the candidate DISABLED on loopback against a COPY of the volume (DEPLOY.md), then:
docker tag agent-readiness-app:latest agent-readiness-app:rollback-140a4e8
docker tag agent-readiness-app:m8-<C> agent-readiness-app:latest
cd /root/agent-readiness/deploy && docker compose up -d --no-build --no-deps app

# 3. VERIFY the Stage B engine (still US$10, nothing armed)
docker compose logs app | grep 'hosted service'   # mode=live access=operator evaluations=enabled jail=verified engine=stage-b armed=none (not_armed)
curl -s https://$SITE/api/health ; curl -s https://$SITE/api/ironbark/config | head -c 400
curl -s -o /dev/null -w '%{http_code}\n' https://$SITE/api/ironbark/jobs/eval-aa23e33012717c4a30ca21be1239e85f   # 200
#    browse #/run (history), #/lifecycle, #/reports/m7-larkspur-browser-1

# 4. CEILING MIGRATION (owner; app stopped)
docker compose stop app
docker compose run --rm --no-deps -it app python -m agent_readiness.hosted.ceiling migrate --db /data/hosted/live/admission.sqlite \
  --to 10.736 --expect-ceiling 10 --expect-reserved 3.3 --reason "one full six-task Original-vs-Modified paid evaluation of larkspur-core@v2"
sed -i 's/^AR_HOSTED_CEILING_USD=.*/AR_HOSTED_CEILING_USD=10.736/' .env && docker compose up -d --no-build --no-deps app
docker compose logs app | grep 'hosted service'   # evaluations=enabled; budget_policy_mismatch means .env ≠ DB: fix .env, never the DB

# 5. PREPARE + ARM (owner, SSH)
docker compose exec app     python -m agent_readiness.lifecycle.arming prepare --arming larkspur-live-1 --mode paid --frozen larkspur-core@v2 --variants original modified --repetitions 1 --launches 1
#    check: manifest 64a55c5f…, 12 trials, reserves US$7.436000, "fits for repetitions [1]"
docker compose exec -it app python -m agent_readiness.lifecycle.arming arm     --arming larkspur-live-1 --mode paid --frozen larkspur-core@v2 --variants original modified --repetitions 1 --launches 1

# 6. LAUNCH (operator, PAID): https://$SITE/#/run → operator token → 1 repetition → Run evaluation

# 7. MONITOR
docker compose exec app python -m agent_readiness.hosted.admin watch <eval-id>
docker compose exec app python -m agent_readiness.hosted.ceiling status --db /data/hosted/live/admission.sqlite        # reserved US$10.736
docker compose exec app sh -c 'wc -l /data/hosted/lifecycle/stage-b/ledgers/larkspur-live-1-l1/ledger.jsonl'
docker compose exec app python -m agent_readiness.lifecycle.arming status
#    emergency stop: docker compose stop app (never resumed; the reservation stays held)
#    afterwards: append the settled total to the programme ledger (text insertion, as for M7)

# 8. ROLLBACK (image)
docker tag agent-readiness-app:rollback-140a4e8 agent-readiness-app:latest && docker compose up -d --no-build --no-deps app
#    after a migration: keep AR_HOSTED_CEILING_USD=10.736 to admit (or 10 to stay fail-closed); the ceiling, reservations and Stage B data stay on the volume
```

## 10. Decisions that require explicit owner approval

1. Deploy the M8 image and copy the lifecycle store to the VM (§9 steps 1–3).
2. The ceiling migration to **US$10.736**, with the reason (§9 step 4), and the matching `.env` change.
3. Paid arming over SSH: arming id, repetitions, launches (§9 step 5). Performed by the owner.
4. The paid launch (§9 step 6): worst case US$7.436.
5. Appending the reconciliation entry (US$3.820762) and the +US$0.000336 correction to the programme ledger.
6. Merge strategy (`m8-product-integration` → `evaluation-v2` → `main`), and any public access change.
7. Owner web authentication (still undecided), and any ceiling above US$10.736.

## 11. Local-only dependencies (git-ignored; on the owner's workstation only)

| What | Path | Needed for |
|---|---|---|
| **The lifecycle store** (owner-frozen `larkspur-core@v2`, its approval, manifests, private outcomes) | `scanner-data/research/stage-a/store/` | deployment (§9 step 2), the exact-M7 tests, dataset validation |
| M7 paid run evidence, ledger, authorisation | `scanner-data/research/stage-b/paid/evalrun-paid-64a55c5f3a-natural/`, `…/ledgers/m7-larkspur-browser-1/`, `…/authorizations/` | dataset re-derivation |
| M6 generation run | `scanner-data/research/stage-a/m6-larkspur-core-20261102T121242Z/` | dataset re-derivation |
| Production DB and fork copies (2026-11-02) | `scanner-data/hosted-copy/` | reconciliation, migration rehearsal |
| Spend ledgers used by the reconciliation | `investigations/*/spend/`, `runs/*/`, `scanner-data/live/*/spend/`, research ledgers | §5 |
| Secrets | `.env`, `deploy/.env`, `deploy/secrets/{meta_model_api_key,operator_token}` | never printed or committed |
| Local candidate image | `agent-readiness-app:m8-candidate` (`4b526b453e2a`) | local rehearsal only; build on the VM from the commit |

## 12. Pointers

**Reports:**
- [`collaboration/reports/lifecycle-m8-product-integration.md`](../reports/lifecycle-m8-product-integration.md)
- [`collaboration/reports/lifecycle-m7-browser.md`](../reports/lifecycle-m7-browser.md)
- [`collaboration/reports/hosted-production-trial-2026-11-02.md`](../reports/hosted-production-trial-2026-11-02.md)

**Project records:** [`STATUS.md`](../../STATUS.md), [`deploy/DEPLOY.md`](../../deploy/DEPLOY.md), [`collaboration/budget/programme-ledger.json`](../budget/programme-ledger.json).

**Source:**
- `src/agent_readiness/hosted/`: `api.py`, `stageb.py`, `ceiling.py`, `admission.py`, `serve.py`, `paired.py`, `jail.py`, `telemetry.py`
- `src/agent_readiness/lifecycle/`: `arming.py`, `jobs.py`, `service.py`, `projection.py`, `audit.py`, `api.py`, `dataset.py`, `sites.py`, `stage_a.py`
- `src/agent_readiness/evalruns/`: `runner.py`, `authorization.py`, `manifest.py`
- `src/agent_readiness/grading/`: `contrast.py`, `evidence_ranked.py`
- `src/agent_readiness/diagnostics/`: `hypotheses.py`, `behavioral.py`, `run.py`
- `dashboard/src/site/workspace/HostedEvaluation.tsx`, `dashboard/src/site/lifecycle/`

**Tests:**
- `tests/test_hosted_stageb.py`, `tests/test_hosted_ceiling.py`, `tests/test_hosted_api.py`, `tests/test_hosted_service.py`
- `tests/test_lifecycle_m8.py`, `tests/test_lifecycle_m8_browser.py`
- `dashboard/src/site/workspace/stageb.test.tsx`, `dashboard/src/site/lifecycle/lifecycle.test.tsx`

**Data and screenshots:** `datasets/lifecycle/m7-larkspur-browser-1/v1/` (M7 dataset), `dashboard/review/m8/` (screenshots).
