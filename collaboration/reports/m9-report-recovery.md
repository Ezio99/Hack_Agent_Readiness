# Report: M9 follow-up: report recovery and judge-facing reliability

**Date:** 2026-11-03 (Sydney). **Branch:** `m9-release-readiness`. The code is commit `b16aed8`; the release candidate is the commit that adds this report (documentation only on top of `b16aed8`).
**Production:** not changed. It still runs `b563a33` (image `cc97e0049042`). **Spending: none.** No model call, no evaluation re-run, no arming, no launch, no ceiling change.
**Stopped at the deployment approval checkpoint.**

## 1. Root cause

The paid run `eval-e529db2aafecbfddd21e5c571eb85243` completed: 12/12 trials, 112 requests reserved and settled, and the worker's audit was clean. Then `api.work` built the readiness report (`lifecycle/projection.py`) and its leak audit (`lifecycle/audit.py`) found one problem: `evaluation.trials[6].answer[3]: loopback address with port`.

In trial `original-gen-ae6c23b20b-n-r1` (task 4, Original), the agent's own answer cites the page it read as `http://127.0.0.1:34723/…`. That is the jailed snapshot mirror's temporary local origin.

The audit exempts the agent's own fields only from the *expected-answer* check. The *pattern* checks (loopback with port, local paths, tokens) apply everywhere, so the whole document was withheld. `api.work` then moved the admission row to `failed`, and the workspace showed "This evaluation ended failed; it has no report."

Two verification stages disagreed. The runner's public-report audit checks only expected answers and passed. The projection audit, applied by the service before serving, rejected the report.

## 2. Changes (code `b16aed8`)

| Area | Change |
|---|---|
| **Sanitisation** (`projection.py`) | `fixture_origin(trial_dir)` returns the origin a trial's snapshot was served from, and only when the trial's own trace records the jailed mirror (`browser_isolation: netns-loopback-mirror-only`) and an initial navigation to exactly `http://127.0.0.1:<port>/`. No credentials, query, other path, scheme or host are accepted; anything else returns None. `site_relative()` replaces **exactly that origin** in the agent's answer with a site path (`http://127.0.0.1:34723/courses/x` → `/courses/x`). The row is disclosed as `answer_normalized: {fixture_origin_replaced, note}`. Other ports, hosts, schemes and prefixes are left as they are, and the **unchanged** audit still rejects them. Grading helpers (v2 review, contrast, coverage counts) use the raw answer |
| **Raw evidence** | never changed. Trial records and traces keep the agent's text (verified by test and by the Docker rehearsal checksums) |
| **One publication policy** (`service.project_and_audit`) | used by the service before serving and by the worker at completion. The worker records `publication_check {runner_public_report_clean, report_audit_clean, report_problems, publishable}` (counts only). The service also withholds a report whose runner audit failed (fail-closed) |
| **Execution vs publication** (`jobs.py`, `api.py`) | the job's terminal state is the **execution** outcome: every planned trial ran and nothing stopped the run. A report that fails the audit stays **withheld** (export and report return 409) but no longer turns a completed run into `failed`. A job with no results (`not_ready`) is still an execution failure |
| **Status** (`stageb.job_status`, `/api/ironbark/jobs[/id]`) | new fields `execution {state, trials_planned/completed/failed/void}`, `report_status {state: available\|withheld\|pending\|unavailable, recorded_at_completion}` and `record_note`. `state` stays the **preserved admission record**. The note appears whenever the record differs from a completed execution, which covers this job and any similarly affected one. History items carry `execution_state` and `report_state` |
| **Workspace UI** | the header shows the execution outcome ("Completed · 12/12 agent runs finished"), with "Job record: failed" beside it and the explanation below. The report tab follows report availability. A withheld report says so ("every agent run finished; only the readiness report is withheld"). The history pill shows the execution state, plus "record: failed" |
| **Report UI** | "Live run launched in this product · 02 Nov 2026 23:38 UTC" vs "Pre-recorded research run · sanitized dataset v1" (M7). Lifecycle list tags "live run in this product" and "pre-recorded". An **Agent runs: 12/12 completed · none void** line. The trace view notes a normalised answer |

Not changed:
- the audit rules;
- grades, results, ledgers, job records and the admission database;
- the M7 dataset, which re-derives byte-for-byte (`validate … → valid, rederived_from_source: true`);
- the hosted live-view telemetry. It already strips any loopback origin from timeline text (pre-existing; see §5).

## 3. Tests (all zero cost)

| Check | Result |
|---|---|
| `tests/test_m9_report_recovery.py` (new) | **31 passed. 20 fail on the pre-fix code**; the other 11 assert that real leaks stay blocked, so they must pass both before and after. They cover: fixture-origin parsing and 10 refusal cases; exact-origin normalisation (other ports, hosts, schemes and prefixes untouched); a normalised answer passes while an unknown loopback URL is rejected; credentials, API-key strings, local paths, the data directory, authorisation and ledger keys, oracle truth and the key variable stay blocked; an expected answer outside the agent's output stays blocked; a withheld report leaves the run completed while its export stays 409; a run with no results still fails; a historical `failed` record is kept and explained; the worker records the service's check (counts only) and fails closed if the report cannot be built; the service withholds a report whose runner audit failed; **the historical paid run** (local copy of production) projects with 0 problems and its evidence tree is unchanged; the raw answer keeps the origin, only that trial is normalised, all 12 completed with 0 void, v1 1/2, v2 2/4, requests 68/44, cost 1.546229, the v1 grades equal the recorded ones; the M7 dataset is unchanged |
| `tests/test_lifecycle_m8_browser.py -m browser` (real worker, jailed Chromium), run alone, with new assertions | 1 passed (83 s): `execution` 6/6 completed, `report_status` available, `recorded_at_completion` publishable |
| Broad regression (lifecycle M1–M8, graders, hosted, ceiling, Stage B, diagnostics, framework, deployment-safety and export scripts, M9 ×2) | **397 passed**, 5 deselected |
| `scripts/critical-tests.sh` | 214 passed, 17 deselected |
| `dashboard`: `npx vitest run` | **201 passed** (18 files; +3: a completed run with a preserved `failed` record is shown as completed and explained, and its report renders; a withheld report is never requested and says so; dataset vs live labels) |
| `npm run build` (tsc, Vite, `check:dist`) | CHECK PASSED |
| M7 dataset re-derivation from source | valid, byte-equal |

## 4. Zero-cost Docker rehearsal on a copy of production data

- **Data:** a read-only copy of production's `/data/hosted` (taken 2026-11-03 after the paid run, 2 215 files; local, git-ignored `scanner-data/hosted-copy-m9/`) in a fresh volume with production ownership (uid 10001).
- **Image:** `agent-readiness-app:m9r-b16aed8` = `6e32b4bf0749`, built from a clean worktree at `b16aed8`, so untracked files are excluded.
- **Mode:** **disabled** on loopback (`127.0.0.1:18081`), so nothing could start.

| Check | Result |
|---|---|
| Startup | `lifecycle: datasets=m7-larkspur-browser-1 store=yes web-approval=disabled` |
| Smoke checks (Ironbark history, insights, exports, trials, live; lifecycle views; M7 report; refusals) | PASS |
| `/api/ironbark/jobs/eval-e529…` | `state: failed` (preserved); `execution: completed, 12/12, 0 failed, 0 void`; `report_status: available`; `report: eval-e529…`; `record_note`: "Execution completed: 12/12 agent runs finished. The job record reads 'failed' because … The original record is kept unchanged." |
| `/api/lifecycle/evaluations/eval-e529…` | **200**: mode paid, source launched, 12 trials (12 completed, 0 void), 6 dimensions. v1 Original 1 / Modified 2; v2 2 / 4; requests 68 / 44; manifest `64a55c5f…`, started 2026-11-02T23:38:58Z. **Settled spend from the durable ledger: US$1.546226, 112 settled, 0 unsettled.** Only `original-gen-ae6c23b20b-n-r1` normalised; **no `127.0.0.1:<port>` anywhere in the public report** |
| Export | 200 |
| All 12 lifecycle trial timelines / all 12 workspace trial views | 200 / 200; screenshot 200 `image/png` |
| History / lifecycle list | `eval-e529db2a`: record `failed`, execution `completed`, report `available`. The lifecycle list shows the M7 dataset and the live run, both with 12 trials |
| **Evidence integrity** | 2 204 non-derived files, tree hash `8663d17e…` **identical before and after**. The only write was the disposable cache `live/stageb/derived/eval-e529….projection-1.json` |
| Browser (Chromium) | workspace job: "Completed", "Job record: failed", the note, 12 / 12, no "it has no report"; report tab and page: "Live run launched in this product", "12/12 completed · none void", 1/6, 2/6, 4/6, US$1.546226; task 4 trace: the normalisation note, no loopback; M7: "Pre-recorded research run"; lifecycle tags; history "record: failed". **0 console errors, 0 responses ≥400, 0 non-GET requests** |
| **Rollback compatibility** (the deployed `b563a33` code, from a worktree, on the post-rehearsal data) | With the candidate's cache present, the old service serves that sanitised, audited document. With the cache removed it refuses `withheld`, which is the previous behaviour. No database, `.env` or record change either way |

The rehearsal container and volume were removed afterwards. The local production copy is unchanged (2 215 files, checksum manifest).

## 5. Remaining risks

1. **The historical admission row stays `failed`.** This is by design; it is never rewritten. Anything reading the admission DB directly (`ceiling status`, `admin list`) still shows `failed` for `eval-e529…`; the API and UI explain it.
2. **Worker semantics changed:**
   - **Before:** a run whose runner public-report audit failed ended `failed`.
   - **Now:** it ends `completed`, with publication withheld. Fail-closed publication is kept: the service refuses to serve a report if either audit failed.
3. **The cache version is unchanged (`projection-1`):**
   - Documents without a fixture URL are byte-identical (M7 re-derives exactly).
   - The only document that changes, `eval-e529…`, had no cache before.
   - After a rollback, the old code serves the cached sanitised report (see §4). Deleting that one cache file restores the exact previous behaviour.
4. **Two loopback rules exist.** The hosted live and timeline telemetry (`hosted/telemetry.py`, pre-existing) strips **any** loopback origin from step text. The report applies the strict rule. Both remove rather than expose; aligning telemetry to the strict rule would change the live view, so it was left out of scope.
5. **Cosmetic, unchanged:**
   - with nothing armed (and in disabled mode), the workspace's left column and intro use the retired Ironbark wording;
   - `config.available` stays true after the launches are used.
6. **Pending owner actions:** the programme-ledger entries (US$3.820762 reconciliation, +US$0.000336, the paid run's US$1.546226).

## 6. Deployment (NOT executed; needs owner approval). `<C>` = HEAD of `m9-release-readiness`

No `.env`, secret, ceiling, arming or database change. The app restarts once; no job is active, and none can start (launches 0 left; hosted budget US$0 remaining).

```sh
# 1. BACKUP (VM)
T=$(date -u +%Y%m%dT%H%M%SZ); docker run --rm -v agent-readiness_data:/data:ro -v /root/backups:/out alpine tar czf /out/predeploy-m9r-$T.tgz -C /data .
cp /root/agent-readiness/deploy/.env /root/backups/env-predeploy-m9r-$T
# 2. BUILD from a clean worktree
git -C /root/agent-readiness fetch -q origin m9-release-readiness && git -C /root/agent-readiness worktree add --detach /root/agent-readiness-build-m9r <C>
cd /root/agent-readiness-build-m9r && docker build -f deploy/Dockerfile -t agent-readiness-app:m9r-<C> .
# 3. PRE-FLIGHT (read-only): expect ceiling US$10.736000; US$10.736000 held by 3 jobs (completed 2, failed 1); remaining 0; active 0; migration #1
docker run --rm -v agent-readiness_data:/data:ro agent-readiness-app:m9r-<C> python -m agent_readiness.hosted.ceiling status --db /data/hosted/live/admission.sqlite
#    smoke test DISABLED on loopback against a COPY of the volume (as §4); expect /api/lifecycle/evaluations/eval-e529… 200
# 4. SWITCH
docker tag agent-readiness-app:latest agent-readiness-app:rollback-b563a33
docker tag agent-readiness-app:m9r-<C> agent-readiness-app:latest
cd /root/agent-readiness/deploy && docker compose up -d --no-build --no-deps app
# 5. VERIFY
docker compose logs app | grep 'hosted service'          # mode=live access=operator evaluations=enabled jail=verified engine=stage-b armed=larkspur-live-1 (... launches left 0)
curl -s https://$SITE/api/ironbark/jobs/eval-e529db2aafecbfddd21e5c571eb85243 | python3 -m json.tool | grep -E '"state"|report|record_note'
curl -s -o /dev/null -w '%{http_code}\n' https://$SITE/api/lifecycle/evaluations/eval-e529db2aafecbfddd21e5c571eb85243     # 200
#    browse #/run/eval-e529db2aafecbfddd21e5c571eb85243 and #/reports/eval-e529db2aafecbfddd21e5c571eb85243; Ironbark history and the M7 report unchanged;
#    authoritative files byte-identical to the backup manifest except the new derived cache
```

**Rollback:**
```sh
docker tag agent-readiness-app:rollback-b563a33 agent-readiness-app:latest && docker compose up -d --no-build --no-deps app
# optional, to restore the exact previous behaviour (report withheld again):
docker run --rm -v agent-readiness_data:/data alpine rm -f /data/hosted/live/stageb/derived/eval-e529db2aafecbfddd21e5c571eb85243.projection-1.json
```
No database or `.env` change is involved in either direction. The pre-deploy backup is only for disaster recovery: **never restore a volume backup over the paid run's records.**
