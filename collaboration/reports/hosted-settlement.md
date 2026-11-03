# Actual-cost settlement: release, read-only reconciliation, owner procedure and deployment record

**Date:** 2026-11-03 (Sydney). **Branch:** `final-showcase`. **Release candidate:** `dde7e22` (= the presentation fixes of `a3ad4cd` + settlement `dde7e22`).
**Production now:** `83be351` (image `f5d9ec46…`). **Cost:** US$0. Nothing was written to production; no ceiling, arming or launch change; no model call.

## 1. Accounting model (implemented)

| Quantity | Meaning | Where |
|---|---|---|
| **Reserved** | every reservation exactly as admitted (worst case + one request bound). **Never rewritten.** | `jobs.reserved` |
| **Settled** | a job's verified actual cost, from its durable request ledger(s) | new write-once table `settlements` |
| **Released** | reserved − settled, for settled jobs only | derived |
| **Outstanding** | the full reservation of every job without a settlement (active, uncertain, failed with unsettled requests, historical) | derived |
| **Committed** | settled + outstanding | derived |
| **Admission rule** | `committed + new reservation <= hosted ceiling`, in one `BEGIN IMMEDIATE` transaction (single slot, rate limit unchanged) | `Admission.reserve_amount` |

**When a job settles.** Only when (1) its admission state is terminal (`completed`, `failed`, `timed_out`, `interrupted`: the worker has exited and the state machine never re-runs it), (2) its ledger(s) can be identified (Stage B: the launch claim's experiment, cross-checked against the write-once paid authorisation; the retired engine: its repetitions' ledgers), (3) every ledger line parses, no item is reserved or settled twice, nothing is settled without a reservation, and (4) **every request is settled** and the settled total is **≤ the job's reservation**. A state such as "failed" never releases anything by itself.

- **Automatic:** only jobs admitted by this release (an `auto_settle` row is written in the same transaction as the reservation). The service settles a job when its thread ends and reconciles at start (a crash between a job's end and its settlement is settled at the next start). Anything ineligible keeps its full reservation and is logged.
- **Owner:** historical jobs, and jobs with unsettled requests, only via `python -m agent_readiness.hosted.settlement apply` at an interactive terminal, after `audit`. `--expect-settled` must equal the verified amount; the owner types a confirmation naming the job, amounts and ledger sha256. `--allow-open-requests` (recovery) commits each unsettled request at its **full reserved bound**, never at zero.
- **Idempotent, write-once:** the same settlement again is a no-op; a different amount is refused ("settlements are never changed"). The insert is atomic (no partial record; tested with an injected failure).
- **Compatibility:** the two tables are additive; `jobs`, `policy` and `policy_migrations` are untouched (`ceiling` schema checks and the jobs fingerprint are unchanged). An older image ignores `settlements`, sums `jobs.reserved` again, and is therefore **more** conservative: rollback is safe.

**Launch authority vs financial capacity.** A launch needs both: the owner's arming (`launches left`) and the hosted budget (`available`). `arming prepare`, `arming status` and the workspace now show both ("the hosted budget covers N launch(es) of this size; this arming authorises at most M"). More launches still need a new owner arming at the terminal; nothing increases the launch count automatically.

**Visibility.** `/api/ironbark/config` `spending` (ceiling, settled, outstanding, committed, available, released, counts); workspace "Budget & capacity" (actual spend, held for unsettled runs, available of the hosted budget, authorised launches and how many the budget covers, cost per completed evaluation); history "Cost" column; `ceiling status` adds a settlement line; the service logs the budget at start; `settlement audit --programme-ledger …` adds the programme view in A$ at the agreed **1.50 AUD/USD** against the **A$50** limit.

## 2. Read-only reconciliation of production (2026-11-03)

Source: a copy of `/data/hosted/live/admission.sqlite` **byte-identical to production** (sha256 `280fb9ef9e07d3bf…`, compared over SSH, read-only), the production Stage B ledgers (also byte-identical: `larkspur-live-1-l1` `e4675700…`, `larkspur-judge-1-l1` `b5b1b4d0…`) and the retired engine's ledgers from the M9 copy. Full output: [hosted-settlement-reconciliation.json](hosted-settlement-reconciliation.json). The audit opens the database read-only (its hash was unchanged afterwards; no table was created).

| Job | State (record) | Reserved | Ledger | Verdict | Commit | Release |
|---|---|---|---|---|---|---|
| `eval-9aaac35c` (Ironbark, retired engine) | completed | US$1.650000 | 139/139 settled, 0 open, sha256 `c45bd4b0…` | **kept in full** (`exceeds_reservation`): the repetition ledger is a fork that also contains the source run's entries from 1 Nov | – | – |
| `eval-aa23e330` (Ironbark, retired engine) | completed | US$1.650000 | 141/141 settled, 0 open, `ff98f05b…` | **kept in full** (same reason) | – | – |
| `eval-e529db2a` (Larkspur v2, live) | failed (preserved; execution completed) | US$7.436000 | 112/112 settled, 0 open, 0 above bound, `73045954…` | **eligible (owner)** | US$1.546226 | US$5.889774 |
| `eval-c04fdb10` (Larkspur v3, judge launch 1) | completed | US$3.740000 | 45/45 settled, 0 open, 0 above bound, `243deaca…` | **eligible (owner)** | US$0.631751 | US$3.108249 |

Totals now: ceiling US$21.956, reserved = outstanding = committed US$14.476 (4 jobs), **available US$7.480**; nothing settled.

For information only (not used by the tool): restricting each Ironbark ledger to its own job's time window gives 76 settled requests = US$1.090968 and 78 = US$1.126097, exactly the programme ledger's `hosted-live-1`/`hosted-live-2`. At most US$1.08 could be released there, and only by a time-window interpretation; **recommendation: keep both reservations** (a ledger that cannot be attributed by itself is not used to release capacity).

**Programme (A$, 1.50 AUD/USD):** known spend US$18.786306 (programme ledger, 21 entries) + `eval-c04fdb10` US$0.631751 (verified ledger; not yet appended to the programme ledger, which needs owner approval) = **US$19.418057 = A$29.13**. Worst case if the whole available hosted budget were spent: + US$7.480 = **A$40.35** of A$50.

**Important consequence of settling both live runs at today's ceiling.** Available would rise to US$16.478, and the hosted ceiling **alone** would then allow a programme worst case of US$35.896 = **A$53.84 > A$50** (the active arming would still cap real exposure at 2 launches = A$40.35, but the hard financial control should hold on its own). The owner procedure below therefore lowers the ceiling in the same window: with spend to date S, committed C and ceiling X, worst case = S + (X − C) ≤ US$33.333 (A$50) ⇔ X ≤ C + 33.333 − S = 5.477977 + 13.915276 = **19.393253**. Proposed: **US$19.380** → available US$13.902023 (3 launches of US$3.740) and worst case **A$49.98**. This invariant holds as further launches run (each settlement moves a cost from "available" to "spend to date").

## 3. Tests (zero cost)

| Check | Result |
|---|---|
| `tests/test_settlement.py` (new, 19; now in `scripts/critical-tests.sh`) | completed run releases its unused reservation exactly once; duplicate settlement is a no-op and a different one is refused; a failed run with an unsettled request keeps its reservation (owner recovery commits it at its bound); "failed" without a verifiable ledger releases nothing; running jobs never settle; malformed or over-committing ledgers never release; crash during settlement (injected) leaves no partial row and the restart reconciles; an interrupted job with a request in flight is not released at restart; historical jobs never settle automatically; the ceiling is exact (settled + outstanding; +1 microdollar refused); 8 concurrent launch attempts on separate connections admit exactly one, within the ceiling; the audit is read-only; `ceiling status` and an older image's sum stay consistent; rehearsal jobs settle at 0. **Production copies:** the audit finds exactly c04 0.631751 / e529 1.546226 and refuses the forked Ironbark ledgers; owner settlement releases US$8.998023 with job rows (fingerprint) and ledgers (sha256) unchanged; after settlement the budget covers 4 launches but the arming still admits only its 2 (a third is refused by the arming), and the failed test launches keep their reservations |
| Owner procedure rehearsed on a copy with the real CLIs (`settlement apply` ×2 with typed confirmations, `ceiling migrate` 21.956 → 19.38) | settled 2, released 8.998023, committed 5.477977, available 13.902023 (3 launches); jobs fingerprint and ledgers unchanged; the service opens with `AR_HOSTED_CEILING_USD=19.38`; audit worst case A$49.98 |
| `tests/test_showcase_judge_browser.py` (alone) | judge launch → 6/6 jailed trials → the service settles the finished (rehearsal) job automatically at US$0; `spending.settled_jobs` 1 |
| `scripts/m9/judge_paid_path_rehearsal.py` (three tasks, Original vs Improved, no network) | two judge launches reserve 2 requests each before sending, are blocked, void, halt; **their reservations are kept in full** (requests unsettled): committed 18.216, available 3.740, pool 1 left; the code in no file |
| Hosted/admission/ceiling/arming/judge/stage B/lifecycle set | 212 passed |
| `scripts/critical-tests.sh` | 233 passed |
| `scripts/dev-tests.sh` | 1713 passed, 2 failed (the known Task-015 ledger-total tests) |
| Dashboard vitest / build | 220 passed (new: Budget & capacity panel, history cost) / CHECK PASSED |
| Presentation fixes (`a3ad4cd`) | included and unchanged: grid correctness, equivalent-page evidence, opaque header, journey spacing, 6–9 minute estimate, featured Original vs Improved run (see [final-presentation-fix.md](final-presentation-fix.md)) |

## 4. Deployment and owner procedure (each step needs owner approval)

**A. Deploy `dde7e22`** exactly as [final-presentation-fix.md](final-presentation-fix.md) §3 with `C=dde7e22` (backup with manifest, clean worktree build, disabled smoke test on a volume copy, `rollback-83be351`, switch, verify). On first start the image adds the two empty tables and logs `budget: ceiling US$21.956000, settled US$0.000000, outstanding US$14.476000, available US$7.480000`. Nothing is settled automatically (all four jobs are historical). Verify additionally: `/api/ironbark/config` `spending.available` 7.48; `settlement audit` prints the table in §2.

**B. Settlement window (owner terminal; app stopped so nothing launches meanwhile):**
```sh
cd /root/agent-readiness/deploy; DB=/data/hosted/live/admission.sqlite
docker compose exec app python -m agent_readiness.hosted.settlement audit --db $DB        # expect §2 exactly (c04 0.631751, e529 1.546226 eligible)
docker compose stop app
T=$(date -u +%Y%m%dT%H%M%SZ); docker run --rm -v agent-readiness_data:/data:ro -v /root/backups:/out alpine cp /data/hosted/live/admission.sqlite /out/admission-pre-settlement-$T.sqlite
docker compose run --rm --no-deps -it app python -m agent_readiness.hosted.settlement apply --db $DB --job eval-c04fdb100d6b1c877de96dabe76eb052 --expect-settled 0.631751
docker compose run --rm --no-deps -it app python -m agent_readiness.hosted.settlement apply --db $DB --job eval-e529db2aafecbfddd21e5c571eb85243 --expect-settled 1.546226
#   each prints "I am the owner and I settle hosted job ... verified against ledger sha256 ..."; type it exactly
docker compose run --rm --no-deps -it app python -m agent_readiness.hosted.ceiling migrate --db $DB --to 19.38 --expect-ceiling 21.956 --expect-reserved 14.476 \
  --reason "keep the programme worst case within A\$50 after actual-cost settlement"
sed -i 's/^AR_HOSTED_CEILING_USD=.*/AR_HOSTED_CEILING_USD=19.38/' .env && docker compose up -d --no-build --no-deps app
docker compose exec app python -m agent_readiness.hosted.ceiling status --db $DB
#   expect: ceiling 19.380000; reserved 14.476000 (unchanged, 4 jobs); settlement: settled 2.177977 by 2 job(s) (released 8.998023); outstanding 3.300000; committed 5.477977; available 13.902023
docker compose exec app python -m agent_readiness.lifecycle.arming status    # larkspur-judge-1: 2 left (unchanged); the budget covers 3
```
Settle only c04 if preferred: then **keep the ceiling at 21.956** (available 10.588, worst case A$45.01). Settling e529 without lowering the ceiling is **not** recommended (A$53.84 ceiling-alone worst case).

**C. Optional, separate approval: one more judge launch.** With 13.902 available the budget covers 3 launches, but `larkspur-judge-1` authorises only its 2 remaining. A third requires a new owner arming at the terminal (e.g. `--arming larkspur-judge-2 --launches 3`, same suite and variants); arming makes no reservation, and each launch then reserves US$3.740 and settles automatically.

**Programme ledger:** append `eval-c04fdb10` (US$0.631751, verified ledger `larkspur-judge-1-l1`, sha256 `b5b1b4d0…`) with owner approval, as before.

**Rollback.**
- Image: `docker tag agent-readiness-app:rollback-83be351 agent-readiness-app:latest && docker compose up -d --no-build --no-deps app`. The older image ignores `settlements` and admits against all reservations as written (more conservative: at ceiling 19.38 it sees US$4.904 available, one launch). Keep `AR_HOSTED_CEILING_USD` equal to the database ceiling.
- Settlement data: settlements are additive and never change `jobs`; they are not removed in normal operation. If ever required, stop the app and restore `/root/backups/admission-pre-settlement-<T>.sqlite` (and the matching `.env` ceiling), then start.

## 5. Limits
- The Ironbark reservations (US$3.30) stay held; the tool will not attribute a forked ledger.
- Settled amounts are calculated from provider-reported usage at published prices (not invoices).
- Paid recovery with `--allow-open-requests` assumes the job can never send again (terminal state); the state machine guarantees this for hosted jobs.

## 6. Minimal-risk path: deployment record (owner-approved, 2026-11-03 UTC)

**Owner decision:** deploy `dde7e22`; take a fresh database backup; settle **only** `eval-c04fdb100d6b1c877de96dabe76eb052` at exactly US$0.631751 with the interactive owner confirmation; **keep the ceiling at US$21.956**; do not settle `eval-e529…` or the Ironbark jobs; no new arming, no paid launch.

### 6.1 Safety verification before execution (zero cost, copies of the production database and real ledgers)
Copies were byte-identical to the audited snapshot (`280fb9ef…`). The rollback image's code (`83be351`) was run from a detached worktree against the same copies.

| Check | New code `dde7e22` | Rollback code `83be351` |
|---|---|---|
| Startup on the database | adds the two empty tables; reconcile settles nothing (all 4 jobs historical); available US$7.480 | accepts the database (`.env` 21.956 = DB 21.956), ignores the new tables |
| After settling c04 only | settled 0.631751, released 3.108249, outstanding 10.736, committed 11.367751, **available 10.588249**; job rows and ledgers unchanged; same settlement again = no-op; a different amount refused | sees reserved 14.476, **available 7.480** (more conservative); settlement row untouched |
| Launches | arming `larkspur-judge-1` 2 left; budget covers 2; 2 admitted, the third refused (`launches_exhausted`); after both (kept in full until settled) available 3.108249 < 3.740: **the budget alone could not fund a third** | 2 admitted, third refused; after the new image's two launches the old image sees available 0 and admits nothing |
| Roll forward after rollback | c04 settlement still recorded; launches admitted by the old image have no `auto_settle` row and are never auto-settled (kept until owner review) | – |
| Programme (1.50 AUD/USD, A$50) | spend to date US$19.418057 (A$29.13) + available 10.588249 = **US$30.006306 = A$45.01** (≤ A$50; unchanged by the two launches: each reservation moves from available to committed) | 19.418057 + 7.480 = A$40.35 |

Focused tests: `test_settlement`, `test_showcase_presentation`, `test_hosted_ceiling`: 48 passed.

### 6.2 Deployment (`dde7e22`, 2026-11-03 09:15 UTC)
| Step | Result |
|---|---|
| Read-only preflight | **identical to the audited snapshot:** image `f5d9ec46…`, healthy; `admission.sqlite` `280fb9ef…`; ledgers `larkspur-judge-1-l1` `b5b1b4d0…`, `larkspur-live-1-l1` `e4675700…`; tables jobs/policy/policy_migrations; 4 jobs as audited; ceiling 21.956, reserved 14.476, 0 active, migrations #1–#2; `larkspur-judge-1` 2 left, problems []; `.env` live/operator/21.956; worker idle |
| Backup | `/root/backups/predeploy-st-20261103T091245Z.tgz` (sha256 `f13d6ff7…`, gzip OK), manifest of 2 421 files (archive matches every entry), `.env` copy identical. Versus the 83be351 deploy manifest: 215 files added (suite, arming, c04 run), only `armings/ACTIVE` and `admission.sqlite` changed |
| Build | clean worktree `/root/agent-readiness-build-st` at `dde7e221…`, 0 untracked; `compose.yaml` identical to production (no compose, secret or `.env` change); image `st-dde7e22` = **`sha256:d40199ef03f0cdba39a626eae65757755c97a2bcecd62595c6de5ee936f0e553`**, user `agent`; frontend `index-Blj5zxRC.js` = local build; snapshots `2f9fd2ce09a0` / `edb9a5d2884a` / `87e715d59c23` |
| New image, read-only | `ceiling status` adds the settlement line (nothing settled, available 7.480); `settlement audit` on the read-only volume reproduces §2 exactly; DB hash unchanged |
| Disabled smoke test (loopback, volume copy) | 13/15 as scripted; the 2 misses were checks I wrote wrongly (the config `spending` block exists only when evaluations are enabled; the retired Ironbark history rows keep their old format without `reserved_usd`), both then verified on the live service. c04 grid, equivalent evidence, settled spend, e529, versions, Ironbark jobs, bundle: PASS; 0 tracebacks; copy removed |
| Switch | `rollback-83be351` = `f5d9ec46…`; `latest` = `d40199ef…`, started 09:15:11Z, healthy, 0 restarts, 0 tracebacks. Log: `budget: ceiling US$21.956000, settled US$0.000000, outstanding US$14.476000, available US$7.480000`; `mode=live access=operator evaluations=enabled jail=verified engine=stage-b armed=larkspur-judge-1 (paid, larkspur-core v3, launches left 2) judge_access=on` |
| Public verification | **18/18 PASS**: health; worker idle, judge access, 2 left; `spending` ceiling 21.956 / settled 0 / outstanding 14.476 / available 7.48; ceiling block unchanged; POST without a code, with a wrong code, with a Basic header: 403; c04 grid Improved Correct 3/3 (Exact 0/3), Original 0/3, recorded outcomes unchanged; report equivalent evidence Improved 3/3, recorded evidence rule and official grades unchanged, settled US$0.631751 (45/0); e529 report 12 trials, US$1.546226; history 4 jobs; versions; both Ironbark jobs; bundle + HSTS/CSP/nosniff |
| Evidence | **2 420 of 2 421 files byte-identical** to the backup, no file added or removed (derived caches excluded); the only change is `admission.sqlite`: two new empty tables, job rows (`b337ab49…`) and `policy_migrations` (`73e7d874…`) identical to the backup. New derived caches `*.projection-1+equivalent-page-1.json` beside the kept `*.projection-1.json`. Judge code in no log line or data file; uid 10001, CapEff 0 |
| Browser (production, GET only) | Home features Original vs Improved (0/3 → 3/3); sticky header opaque; journey "6–9 minutes", version names spaced 14 px; workspace "Budget & capacity", "2 of 3 live runs left"; c04 grid "Correct" ×3 / "Not correct" ×3, "Exact match: no" ×6, no "Not passed"; report equivalent-page row 0/3 → 3/3; 0 console errors; no non-GET request. Cosmetic: at 1 440 px the history table scrolls horizontally (the new Cost column is past the right edge) |

Recorded in `deploy/DEPLOYED.txt`. **Rollback:** `docker tag agent-readiness-app:rollback-83be351 agent-readiness-app:latest && docker compose up -d --no-build --no-deps app` (no compose, secret, `.env` or ceiling change in either direction).

### 6.3 Owner settlement window (pending: owner terminal)
`/root/settle-c04.sh` (sha256 `91a2a96a…`, root-only) is a guarded wrapper; the owner runs it with `ssh -t root@209.38.84.72 /root/settle-c04.sh`:
1. read-only pre-checks; **aborts with nothing changed** unless the running image is `d40199ef…`, the worker is idle with 2 launches left, spending is 21.956 / 0 settled / 14.476 outstanding, the job rows hash to `b337ab49…`, no settlement exists, the c04 ledger is `b5b1b4d0…`, and the audit shows c04 eligible at 0.631751 / release 3.108249 (dry run `DRY=1` passed on production; without a terminal it refuses);
2. stops the app, copies `admission.sqlite` to `/root/backups/admission-pre-settlement-<T>.sqlite` and verifies the copy's sha256 against the live file (aborts and restarts if it differs);
3. runs `settlement apply --job eval-c04fdb10… --expect-settled 0.631751` at the terminal: **the owner types the printed confirmation line**; the script never supplies it;
4. restarts the app on exit, whatever the outcome.

Expected afterwards: ceiling **21.956** (unchanged); reserved 14.476 (unchanged, 4 jobs); settled **0.631751** (1 job), released 3.108249; outstanding **10.736** (e529 7.436 + Ironbark 3.300); committed 11.367751; **available 10.588249**; `larkspur-judge-1` **2 left** (the budget covers 2); programme spend to date US$19.418057 (A$29.13), **worst case A$45.01**.

### 6.4 Settlement of `eval-c04fdb10` (owner terminal, 2026-11-03 10:49 UTC) and read-only verification

The owner ran `/root/settle-c04.sh` at an interactive terminal: the pre-checks passed, the app stopped, the backup `/root/backups/admission-pre-settlement-20261103T104926Z.sqlite` (sha256 `75d9e123…`, verified against the live file; 0 settlements, job rows `b337ab49…`, migrations `73e7d874…`) was taken, the owner typed the confirmation, `settlement apply` exited 0 (settled US$0.631751, released US$3.108249, available US$10.588249), and the app restarted.

| Check (read-only, after the restart) | Result |
|---|---|
| Service | image `d40199ef…`, started 10:49:36Z, healthy, 0 restarts, 0 tracebacks; log `budget: ceiling US$21.956000, settled US$0.631751, outstanding US$10.736000, available US$10.588249`; `armed=larkspur-judge-1 (paid, larkspur-core v3, launches left 2) judge_access=on` |
| Settlement record | **exactly 1 row** in `settlements` (primary key `job_id`): `eval-c04fdb10…`, 631 751 µUSD, basis "stage-b launch larkspur-judge-1-l1: 45/45 requests settled", ledger sha256 `243deaca…`, 45 requests, 0 open, 2026-11-03T10:49:36.57Z, actor "owner terminal (uid 10001)". `auto_settle` empty (no automatic settlement) |
| Totals (`ceiling status`, audit, `/api/ironbark/config`) | ceiling **US$21.956** (unchanged; policy row and migrations #1–#2 identical); reserved US$14.476 (4 jobs, rows `b337ab49…` unchanged); settled **US$0.631751** (1 job); released US$3.108249; outstanding **US$10.736** (e529 US$7.436 + Ironbark 2 × US$1.650, still unsettled as decided); committed US$11.367751; available **US$10.588249** |
| Unsettled jobs | `eval-e529…` still eligible but **not settled** (owner decision); both Ironbark jobs kept in full (`exceeds_reservation`) |
| Arming | `larkspur-judge-1` active (`ACTIVE` pointer unchanged), record sha256 `71a26471…`, launches max 3 / used 1 / **left 2**, problems []; capacity: available 10.588249, the budget covers 2. Launch claims and ledgers: only `larkspur-live-1-l1` and `larkspur-judge-1-l1` (+ the rehearsal claim), no new claim |
| Ledgers | `larkspur-judge-1-l1` `b5b1b4d0…`, `larkspur-live-1-l1` `e4675700…`, Ironbark `paired-60c6…` `3964af4b…`, `paired-86a6…` `dd76c145…`: unchanged |
| Evidence | **2 420 of 2 421 files byte-identical** to the pre-deploy backup, none added or removed (derived caches excluded); the only change is `admission.sqlite` (the new tables and the one settlement row) |
| Public (18/18 PASS) | health; judge access on, 2 left; `spending` settled 0.631751 / outstanding 10.736 / committed 11.367751 / available 10.588249 / released 3.108249, 1 settled, 3 unsettled; `ceiling` block 21.956 / 14.476; POST without a valid code ×3: 403; c04 grid and report (equivalent evidence 3/3, recorded grades unchanged, settled 0.631751, 45/0); e529 report; history c04 cost 0.631751, others none; versions; Ironbark jobs; bundle and security headers |
| Browser (GET only) | Workspace "Budget & capacity": actual model spend US$0.63 (1 evaluation); held for unsettled runs US$10.74 (3 evaluations); available US$10.59 of US$21.96; live runs authorised 2 of 3 left, US$3.74 each, the budget covers 2; cost per completed evaluation US$0.63. History Cost column: c04 US$0.63, the others "—". Home, journey, report, Ironbark archive: 0 console errors, no non-GET request |
| Programme (1.50 AUD/USD) | programme ledger US$18.786306 + `eval-c04fdb10` US$0.631751 (verified ledger; not yet appended, needs owner approval) = **US$19.418057 = A$29.13**; + available US$10.588249 = worst case **US$30.006306 = A$45.01 ≤ A$50** |

Observation (not changed): the history's "Passed" column uses the official exact-match grade, so `eval-c04fdb10` reads "0% → 0%" there while the grid, report and journey show Correct 0/3 → 3/3. A later release could label the column "Exact match" or add the Correct rate.

**State now:** no paid call, no ceiling change, no other settlement, no arming change. Remaining owner decisions: append `eval-c04fdb10` to the programme ledger; the two remaining judge launches (each reserves US$3.740 and settles automatically when it finishes); whether ever to settle `eval-e529…` (only together with a lower ceiling, §2).
