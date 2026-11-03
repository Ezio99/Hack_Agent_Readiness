# Final presentation-fix release (release candidate; NOT deployed)

**Date:** 2026-11-03 (Sydney). **Branch:** `final-showcase`. **Release commit:** `a3ad4cd`. **Production now:** `83be351` (image `f5d9ec46…`), kept as the rollback.
**Cost:** US$0. No paid call, no deployment, no change to spending controls, arming or production data. Regression fixture: the real production run **`eval-c04fdb100d6b1c877de96dabe76eb052`** (copied read-only from the VM to git-ignored `scanner-data/hosted-copy-fs/`; its public report and job status, as served by the new code, are committed under `dashboard/src/fixtures/live/`).

## 1. Fixes

| # | Request | Change |
|---|---|---|
| 1 | Workspace "Agent runs" grid showed correct Improved answers as "Not passed" | The hosted job status carries, per finished agent run, the readiness report's `correct` (recorded v2 grade, else v1) and `exact_match` (official v1) beside the **unchanged** recorded `outcome` (`hosted/api.py`, `hosted/stageb.py job_status(grades=…)`). The grid shows "✓ Correct / ✕ Not correct" exactly as the report counts it, and "Exact match: yes/no" as its own line. Runs without a published report (and the retired Ironbark engine) keep the previous display |
| 2 | Evidence rule did not credit `/courses/compare` | **Investigated:** the recorded rule requires the pages derived from the catalogue profile (`/courses`), so an agent that read every fact from the comparison table was marked "required page not shown". **Change (report-time, beside the record):** `lifecycle/projection.py equivalent_pages` (`equivalent-page-1`): a visited page counts as equivalent evidence if it states, as labelled values, every deciding fact of **every** catalogue item exactly as the site's own records (the oracle) hold it. Only the Improved comparison table qualifies (tested: no page of Original or Modified, nothing for an unknown field). The trial's recorded `satisfied`, the official and v2 grades and the evidence counts are unchanged; the projection adds `evidence.equivalent` (and a per-version `evidence_satisfied_or_equivalent`) **only where it applies**, so the M7 dataset and the earlier live run re-derive unchanged. The derived cache is re-keyed (`projection-1+equivalent-page-1`) so production re-projects; the leak audit still passes. Report: a new row "…or an equivalent page that states every deciding fact for every course (e.g. a comparison table)": Original 0/3, **Improved 3/3**; the trace view says "every deciding fact shown on /courses/compare" |
| 3 | Transparent sticky header | `.site-head` is opaque (`background: var(--paper)`), so scrolled content never shows through |
| 4 | Version names run together in the journey | `.lc-vname + .lc-vname { margin-left: 14px }` |
| 5 | Runtime estimate | Re-evaluate step: "about 6–9 minutes for 6 agents" (the live run took 5 min 56 s) |
| 6 | Feature the new run | `showcase.ts` `LIVE` = `eval-c04…` (Original vs Improved); the first live run `eval-e529…` is kept as `FIRST_LIVE`. **Home:** hero card and figure (the weekend-courses task: Original 13 requests, 2 of 4 courses; Improved 2 requests, all 4), Results "Every recommendation applied. Measured live." (correct 0/3 → 3/3, requests 39 → 6, time 4:22 → 0:54, cost 55¢ → 8¢, per-task bars), the first live run kept as context with its link. **Nav "Live report"** and the footer link the new run (the first live run and the first evaluation stay linked). **Journey:** Evaluate and Recommendations stay on the first live run (that is where the recommendations came from); Re-evaluate shows the latest live result; Compare leads with the featured Original-vs-Improved panel (KPIs, side-by-side screenshots and agent memories, "Replay this task side by side"), then every live evaluation. Recorded screenshots re-exported from the product (`scripts/showcase/export_larkspur_showcase.py`) |

## 2. Tests (zero cost)

| Check | Result |
|---|---|
| `tests/test_showcase_presentation.py` (new, 5; uses the production copy) | equivalent pages: only `/courses/compare`, only on Improved; the production run re-projects with `equivalent` on exactly the 3 Improved trials and is **otherwise identical** to production's cached report (both live runs; only the settled total, read from the VM's ledger path, is not reproducible locally); the leak audit is clean; `job_status` adds `correct`/`exact_match` and leaves `outcome` unchanged; the hosted status route serves Improved correct 3/3, exact 0/3 for `eval-c04…` and the earlier run's grades from its own report (6 correct, 3 exact) |
| `tests/test_showcase_judge_browser.py` (run alone) | 1 passed: judge launch of the three-task suite on Original vs Improved, 6/6 jailed trials, report audit-clean, diagnostics 7 resolved / 0 introduced, and now every grid row carries `correct` and `exact_match` |
| Backend set (`test_showcase_presentation`, `test_larkspur_improved`, `test_lifecycle_m8` incl. the **M7 byte-for-byte re-derivation**, `test_hosted_stageb`, `test_m9_judge_access`, `test_m9_report_recovery`, `test_framework`, `test_evalruns_m5`) | 122 passed |
| `scripts/critical-tests.sh` | 214 passed |
| `scripts/dev-tests.sh` | 1694 passed, 2 failed (the known Task-015 ledger-total tests, handoff §8.6) |
| Browser: `test_larkspur_improved` Chromium | 1 passed |
| Dashboard `npx vitest run` | 219 passed (new: the production grid reads Not correct ×3 / Correct ×3 with "Exact match: no" ×6; the report rows Correct 0/3 → 3/3, Exact 0/3 both, equivalent 0/3 → 3/3; the trace names `/courses/compare`; Compare and Re-evaluate feature the new run and the 6–9 minute estimate) |
| `npm run build` | CHECK PASSED |
| Local view-only service on the production copy (new backend and build), real browser | Home, journey (Compare, Re-evaluate), workspace, report: 0 console errors; header opaque |
| Production, read-only (2026-11-03, after this work) | image `f5d9ec46…` healthy; `larkspur-judge-1` 2 of 3 left, problems []; ceiling 21.956, reserved 14.476, 7.480 free; ledgers `larkspur-live-1-l1` `e4675700…`, `larkspur-judge-1-l1` `b5b1b4d0…`; jobs `eval-e529…`, `eval-c04…` |

Not run: the 33-minute CI suite.

## 3. Deployment (needs owner approval). `C=a3ad4cd`

Image-only change: **no** `compose.yaml`, secret, `.env`, ceiling, arming, store or ledger change. The app restarts once (no job may be running: check the worker is idle first). After the restart the two live reports are re-projected once (new cache key); the old cache files stay (derived, never authoritative).

```sh
ssh root@209.38.84.72 && cd /root/agent-readiness/deploy; SITE=209-38-84-72.sslip.io; C=a3ad4cd
# 0 pre-flight: worker idle, arming 2 left, ceiling 21.956 / 14.476
curl -s https://$SITE/api/ironbark/config | python3 -c "import json,sys;c=json.load(sys.stdin);print(c['worker'],c['launch'],c['ceiling'])"
# 1 backup (+ manifest, verified as before)
T=$(date -u +%Y%m%dT%H%M%SZ); docker run --rm -v agent-readiness_data:/data:ro -v /root/backups:/out alpine tar czf /out/predeploy-fp-$T.tgz -C /data .
cp .env /root/backups/env-predeploy-fp-$T
docker run --rm -v agent-readiness_data:/data:ro alpine sh -c 'cd /data && find . -type f ! -path "*/derived/*" | sort | xargs sha256sum' > /root/backups/predeploy-fp-$T.sha256
# 2 build from a clean worktree
git -C /root/agent-readiness fetch -q origin final-showcase && git -C /root/agent-readiness worktree add --detach /root/agent-readiness-build-fp $C
cd /root/agent-readiness-build-fp && docker build -f deploy/Dockerfile -t agent-readiness-app:fp-$C . && cd /root/agent-readiness/deploy
# 3 disabled smoke test on a COPY of the volume (as for 83be351): status of eval-c04 shows correct/exact_match; its report has evidence.equivalent on the 3 Improved trials
# 4 switch
docker tag agent-readiness-app:latest agent-readiness-app:rollback-83be351 && docker tag agent-readiness-app:fp-$C agent-readiness-app:latest
docker compose up -d --no-build --no-deps app
# 5 verify
docker compose logs app | grep 'hosted service'      # ... armed=larkspur-judge-1 (paid, larkspur-core v3, launches left 2) judge_access=on
curl -s https://$SITE/api/ironbark/jobs/eval-c04fdb100d6b1c877de96dabe76eb052 | python3 -c "import json,sys;print([(t['arm'],t['task'],t['correct'],t['exact_match']) for t in json.load(sys.stdin)['reps'][0]['tasks']])"
curl -s https://$SITE/api/lifecycle/evaluations/eval-c04fdb100d6b1c877de96dabe76eb052 | python3 -c "import json,sys;e=json.load(sys.stdin);print(e['dimensions']['evidence_quality']['variants'],e['cost']['settled_spend']['settled_usd'])"   # improved equivalent 3; settled 0.631751
#   POST without the code -> 403; arming status 2 left; ceiling status unchanged; evidence files byte-identical to the backup (derived caches excluded)
```

**Rollback:** `docker tag agent-readiness-app:rollback-83be351 agent-readiness-app:latest && docker compose up -d --no-build --no-deps app` (no data, secret or `.env` change in either direction; the old projection cache files are still present and are read again by `83be351`).

## 4. Notes
- Recorded data is unchanged: trial records, official v1 grades, v2 grades, the recorded evidence rule's results, ledgers and job records. The new values are derived at read time and labelled.
- `#/evidence` opens the legacy "Evidence and method" archive page (an older route that shadows the Home section anchor); unchanged in this release.
