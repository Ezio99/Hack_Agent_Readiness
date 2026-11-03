# Final showcase release: the Larkspur journey (release candidate; NOT deployed)

**Date:** 2026-11-03 (Sydney). **Branch:** `final-showcase` (from `m9-release-readiness` @ `177e477`). **Release commit:** `b81cff5` (code); the commit that adds this report changes documentation only.
**Fallback release candidate:** `3377d75` (judge launch on Original vs Modified, already rehearsed; `m9-judge-live.md`). Production still runs `f36db53`.
**Cost of this work:** US$0. No paid call, no production access, no deployment, no ceiling change, no arming, no merge.

Owner direction (2026-11-03): feature **Larkspur**; one product story Website → Generate tasks → Review → Evaluate → Recommendations → Improve → Re-evaluate → Compare; judges launch `larkspur-core@v3` live; product showcase, not research framing.

## 1. What changed

### 1.1 The Improved Larkspur website (`sites/larkspur/improved.py`)
A third, separately versioned website, `larkspur@improved`, built from the same course records. `original` and `modified` are byte-identical to before (hashes pinned by a test), so every recorded evaluation still refers to valid snapshots.

| # | Recommendation (from the live report, §10 of the handoff) | On the Improved site |
|---|---|---|
| 1–4 | Fee, duration, level, seats, **campus**, **class day**, **materials** only on course pages | All seven facts on every course card |
| 8 | Agents look for filters (`/courses?level=Intermediate&campus=Northside` returned 404 in the live run) | A GET filter form on `/courses` (level, campus, class day incl. Weekend/Weekdays). All 120 form results are captured pages; 826 hand-typed query strings (any subset, order, original or lower case) redirect to the canonical result |
| 8 | No page per attribute | Linked browse pages: `/courses/campus/<c>`, `/courses/day/<d>` (incl. weekend, weekdays), `/courses/level/<l>`, `/courses/category/<s>` and their index pages |
| 9 | Budget exhaustion, revisits, loops | One comparison table, `/courses/compare` (all courses × all facts, cheapest first) |
| 5 | No structured data | schema.org `Course` + `Offer` + `CourseInstance` JSON-LD on each course page; `ItemList` on every listing |
| 6–7 | 404 dead ends: `/courses/introduction-to-python`, `/courses/yoga-for-beginners`, `/courses/building-web-pages`, `/courses/` | 301 redirects for trailing slashes, name-based slugs, the URLs agents tried, `/course`, `/course/<slug>`, `/catalogue` |
| — | Breadcrumbs, "more like this" links | On every course and browse page |

**Snapshot/mirror:** the jailed browser sees only captured resources, so the improved snapshot is the pipeline's own crawl plus, through the same offline fetcher and capture step, the form results and redirects a crawler cannot discover (`snapshot()` refuses any redirect whose target is not a captured page). 162 pages, 870 redirects, 1 033 resources. Verified through the real `Mirror` (in-process) and in real Chromium (form submission lands exactly on a captured page; a name-based slug redirects).

**Frozen tasks:** all six `larkspur-core@v2` tasks re-derive with unchanged expected answers on Improved; five of six become answerable from `/courses` (1 link step instead of 2).

**Registration:** `SiteDefinition.releases` holds versions registered as re-evaluation targets only (never used to generate or validate tasks). `larkspur.releases = ("improved",)`. Arming, variant resolution, the lifecycle site view and the report diagnostics accept any two registered versions (the run's own pair). The M7 dataset still re-derives byte for byte.

**Page audit (the report's structural rules):** Original 7 problems, Modified 4, **Improved 0** (all 7 resolved, none introduced). To get this right the profiler now treats a page produced by a GET form on a reachable page as reachable (it previously reported all 120 form results as unreachable). The profile of every other registered snapshot (Larkspur original/modified, Ironbark original/modified, four zoo sites) is byte-identical before and after (checked).

### 1.2 One product story (frontend)
- `dashboard/src/site/showcase.ts`: the single source for the featured site, its recorded live evaluation (`eval-e529db2a…`, exported from the product's own report by `scripts/showcase/export_larkspur_showcase.py` from a view-only service on a copy of production data), the three versions, card facts, the six improvements and the page audit.
- **Home:** the Larkspur story: task 1 on Original (13 requests, out of budget after 3 of 14 courses, a guessed URL 404) vs Modified (3 requests, all five courses); 68 → 44 requests, 9 → 5 minutes, correct answers 2/6 → 4/6, US$0.96 → US$0.59; per-task bars showing tasks 3–5 still deep (class day, campus); the Improved site; "Run Original vs Improved". Calls no API.
- **`#/lifecycle` = `#/demo`:** one page, eight steps, real artefacts: business context and personas; the paid generation (24 proposals, 20 accepted, US$0.0498); the frozen suite (tasks numbered as in every report); the live evaluation with side-by-side screenshots; the report's recommendations, each marked with the change that applies it; before/after screenshots, the facts table and the page audit; re-evaluation (launch only from the workspace); a comparison table of live evaluations (shows "The Improved site has not had a live run yet" until the first judge run). No site selector, no SSH/arming commands. The Ironbark scroll story moved to the archive (`#/demo/ironbark`, labelled "Earlier case study").
- **Reports:** recommendations first; "Correct answers" (the recorded v2 grade) and "Exact match" (the official v1 grade) side by side, values unchanged; no exploratory/post-hoc/prospective labels, sign-flip tests, retrospective audit note or composite-score disclaimer. Finding text is reworded at display time; recorded data is unchanged. The rehearsal notice stays.
- **Workspace:** Original vs **Improved** names from the job's new `arm_display` (status and history); the armed tasks listed in the compose panel; plain copy. Launch flow, judge access code and all server checks unchanged from `4841166`.
- Navigation: How it works · The Larkspur journey · Live report · Workspace · Archive.

### 1.3 Backend (small, additive)
`hosted/stageb.py` `arm_display`; `hosted/api.py` history rows carry it; `diagnostics/run.py` uses the run's own version pair; `projection.py`/`runner.py` diagnostics accept any registered pair; `investigate/inspect/profile.py` GET-form reachability. Positional arm keys and routes (`trials/original|modified/<n>`) are unchanged.

## 2. Identifiers

| Item | Value |
|---|---|
| Website `larkspur@original` | `2f9fd2ce09a044547ceb728acb9b85108931d81ca6b01374198144f509fed2eb` (unchanged) |
| Website `larkspur@modified` | `edb9a5d2884a0e85fff8f9dfc6ed0e8a4bed41f9616e82678fc466864befe69f` (unchanged) |
| **Website `larkspur@improved`** | **`87e715d59c2376f82b23f33007496edf193812eb574a65a8629109bbe35e63b5`** (new) |
| Judge suite | `larkspur-core@v3` = v2 tasks `gen-23f1802ee0-n`, `gen-f302fa8fe2-n`; suite `f45694788ea9e1f7b28c95193e25870bfe3aed2975d7f00276cdc87d7c6b09e3` (unchanged; reproduced on a copy of the production store) |
| Manifest | built by `arming prepare` (a new manifest: the variants differ). On the production-store copy: 4 trials, cap US$2.464, **reserves US$2.508000 per launch**, 4 launches **US$10.032000**; variants `original 2f9fd2ce…`, `improved 87e715d5…`. Its hash includes its creation time, so read it from `prepare` |
| Arming id (suggested) | `larkspur-judge-1`, mode `paid`, `--variants original improved` |

No frozen suite, manifest, evaluation, ledger or other evidence was modified. Existing frozen suites are untouched; v3 is only built when the owner runs `revise`.

## 3. Tests (all zero cost)

| Check | Result |
|---|---|
| `tests/test_larkspur_improved.py` (new, 13 incl. real Chromium) | 13 passed: hashes pinned; every card states 7 facts; JSON-LD equals the page; dead ends redirect (and still 404 on Original); browse and hand-typed filters return exactly the matching courses; all 120 form results and every redirect captured and inside the site; every link resolves; form reachability; page audit 7/4/0 and the showcase states exactly that; all 6 frozen tasks valid with unchanged answers (5 at 1 hop); Chromium submits the form and follows a redirect |
| `tests/test_showcase_judge_browser.py` (new, run alone) | 1 passed (60 s): on a copy of the real store, v3 revised/approved/frozen, a 4-launch rehearsal pool armed on **Original vs Improved**, a judge launch with the code → 4/4 jailed trials, `arm_display` Improved, report available and audit-clean **with diagnostics**, code in no file |
| Local `hosted.serve` in rehearsal mode, real browser, built frontend, copy of production data (run twice) | Judge code → "Run evaluation" → 4/4 trials in 110 s; the report's diagnostics: Improved resolves 7 page problems, introduces 0 → "Rehearsal evaluation · Larkspur Community College · Original vs Improved" report; pool 4 → 3; 0 console errors; the code in no page, log line or data file. (Locally the jail policy cannot hide `/home`, where the venv lives; the jail self-test passed with that one path not hidden. Production uses `deploy/jail-policy.json` unchanged.) |
| `scripts/m9/judge_paid_path_rehearsal.py` with `M9_JUDGE_VARIANTS=original,improved` (no network) | As documented for `3377d75`: a judge launch at today's US$10.736 is refused, nothing reserved; after migrating the copy to US$20.768, two judge launches each get their own authorisation, reserve 2 requests **before sending**, are blocked by the network guard, void and halt with no retry; reserved US$15.752, remaining US$5.016, pool 2 of 4 left; the code in no file |
| Variant-sensitive suites (`test_framework`, `test_lifecycle_m8` incl. M7 byte-for-byte re-derivation, `test_hosted_stageb`, `test_m9_judge_access`, `test_evalruns_m5`, diagnostics, inspect) | all passed |
| `scripts/critical-tests.sh` | 214 passed |
| `scripts/dev-tests.sh` | 1689 passed, 2 failed: the known pre-existing Task-015 ledger-total tests (`test_remediation.py`, `test_remediation_main_design.py`; handoff §8.6), unrelated to this change |
| Dashboard `npx vitest run` | 215 passed (18 files) |
| `npm run build` (tsc + vite + dist check) | CHECK PASSED |
| Not run | the full 33-minute CI suite; `docker build` (Dockerfile unchanged; the image build is step 2 of the deployment) |

## 4. Deployment (needs owner approval). `<C>` = `b81cff5`

One release containing `352f262` + `4841166` + this work. No database or ceiling change at deploy time; the app restarts once; no job can start (launches 0 left).

```sh
ssh root@209.38.84.72            # owner key loaded in ssh-agent
SITE=209-38-84-72.sslip.io; C=b81cff5
# 1. BACKUP
T=$(date -u +%Y%m%dT%H%M%SZ); docker run --rm -v agent-readiness_data:/data:ro -v /root/backups:/out alpine tar czf /out/predeploy-fs-$T.tgz -C /data .
cp /root/agent-readiness/deploy/.env /root/backups/env-predeploy-fs-$T
# 2. BUILD from a clean worktree
git -C /root/agent-readiness fetch -q origin final-showcase && git -C /root/agent-readiness worktree add --detach /root/agent-readiness-build-fs $C
cd /root/agent-readiness-build-fs && docker build -f deploy/Dockerfile -t agent-readiness-app:fs-$C .
# 3. PRE-FLIGHT (read-only): expect ceiling US$10.736000; US$10.736000 held by 3 jobs (completed 2, failed 1); remaining 0; active 0; migration #1
docker run --rm -v agent-readiness_data:/data:ro agent-readiness-app:fs-$C python -m agent_readiness.hosted.ceiling status --db /data/hosted/live/admission.sqlite
#    smoke test DISABLED on loopback against a COPY of the volume (as in m9-report-recovery.md §4): Home, #/lifecycle, #/reports/eval-e529…, #/run
# 4. JUDGE SECRET + COMPOSE (compose refuses to start without the secret file; < 24 characters keeps judge access off)
umask 077; head -c 32 /dev/urandom | base64 | tr -dc 'A-Za-z0-9' | head -c 40 > /root/agent-readiness/deploy/secrets/judge_token
chown 10001:10001 /root/agent-readiness/deploy/secrets/judge_token && chmod 400 /root/agent-readiness/deploy/secrets/judge_token
cp /root/agent-readiness/deploy/compose.yaml /root/agent-readiness/deploy/compose.yaml.pre-judge && cp /root/agent-readiness-build-fs/deploy/compose.yaml /root/agent-readiness/deploy/compose.yaml
# 5. SWITCH
docker tag agent-readiness-app:latest agent-readiness-app:rollback-f36db53
docker tag agent-readiness-app:fs-$C agent-readiness-app:latest
cd /root/agent-readiness/deploy && docker compose up -d --no-build --no-deps app
# 6. VERIFY
docker compose logs app | grep 'hosted service'      # mode=live access=operator evaluations=enabled jail=verified engine=stage-b armed=larkspur-live-1 (... launches left 0) judge_access=on
curl -s https://$SITE/api/health; curl -s https://$SITE/api/ironbark/config | python3 -c "import json,sys;c=json.load(sys.stdin);print(c['judge_access'],c['launch'])"
curl -s -o /dev/null -w '%{http_code}\n' -X POST -H 'content-type: application/json' -d '{"repetitions":1}' https://$SITE/api/ironbark/jobs   # 403 (no code)
curl -s -o /dev/null -w '%{http_code}\n' https://$SITE/api/lifecycle/evaluations/eval-e529db2aafecbfddd21e5c571eb85243                  # 200
curl -s https://$SITE/api/lifecycle/sites/larkspur | python3 -c "import json,sys;print([(v['name'],v['snapshot_sha256'][:12]) for v in json.load(sys.stdin)['variants']])"  # original 2f9fd2ce09a0, modified edb9a5d2884a, improved 87e715d59c23
#    browse #/, #/lifecycle, #/reports/eval-e529…, #/run, #/demo/ironbark; Ironbark history unchanged; record the deployment in deploy/DEPLOYED.txt
```

**Rollback** (no database, `.env` or arming change is involved in the deploy itself):
```sh
cd /root/agent-readiness/deploy && cp compose.yaml.pre-judge compose.yaml \
  && docker tag agent-readiness-app:rollback-f36db53 agent-readiness-app:latest && docker compose up -d --no-build --no-deps app
```
To fall back to the known-good judge launch instead (`3377d75`, Original vs Modified): build `3377d75` the same way and arm with `--variants original modified` (the rest of §5 is identical).

## 5. Owner terminal steps for the live judge pool (each needs owner approval)

> **Superseded for the featured pool (2026-11-03):** the owner prefers the **three-task** judge suite (adds the class-day task `gen-8334922e62-n`; 3 launches; ceiling 10.736 → 21.956; worst case A$45.01). Use [final-showcase-three-task-suite.md](final-showcase-three-task-suite.md) §5. The two-task commands below remain valid as the fallback.

```sh
cd /root/agent-readiness/deploy
STORE=/data/hosted/lifecycle/store
V2=172d1e712eb18871fd4f24b227a2448ec44a546347bb9874f0946c5609f7848b
V3=f45694788ea9e1f7b28c95193e25870bfe3aed2975d7f00276cdc87d7c6b09e3
# (a) the suite: revise must print exactly $V3; review; approve at the terminal (prints APPROVAL); freeze -> larkspur-core@v3
docker compose exec app python -m agent_readiness.suites.stage_a.approval revise $STORE $V2 --keep gen-23f1802ee0-n gen-f302fa8fe2-n \
  --context-site larkspur --at 2026-11-03T12:00:00+00:00 --by owner \
  --notes "judge live evaluation: tasks gen-23f1802ee0-n and gen-f302fa8fe2-n of v2 (their deciding facts are on the Modified listing cards)"
docker compose exec app python -m agent_readiness.suites.stage_a.approval review $STORE $V3 --markdown
docker compose exec -it app python -m agent_readiness.suites.stage_a.approval decide $STORE $V3 approved --notes "judge live evaluation"
docker compose exec app python -m agent_readiness.suites.stage_a.approval freeze $STORE $V3 <APPROVAL>
# (b) the hosted ceiling (app stopped): 10.736 -> 20.768 = 10.736 already reserved + 4 x 2.508
docker compose stop app
docker compose run --rm --no-deps -it app python -m agent_readiness.hosted.ceiling migrate --db /data/hosted/live/admission.sqlite \
  --to 20.768 --expect-ceiling 10.736 --expect-reserved 10.736 --reason "four judge-triggered live runs of larkspur-core@v3, Original vs Improved"
sed -i 's/^AR_HOSTED_CEILING_USD=.*/AR_HOSTED_CEILING_USD=20.768/' .env && docker compose up -d --no-build --no-deps app
# (c) the paid pool: prepare must show website larkspur: original 2f9fd2ce09a0, improved 87e715d59c23; 4 trials; reserves US$2.508000;
#     at most 4 launches reserving US$10.032000; "fits for repetitions [1]"
docker compose exec app python -m agent_readiness.lifecycle.arming prepare --arming larkspur-judge-1 --mode paid --frozen larkspur-core@v3 --variants original improved --repetitions 1 --launches 4
docker compose exec -it app python -m agent_readiness.lifecycle.arming arm --arming larkspur-judge-1 --mode paid --frozen larkspur-core@v3 --variants original improved --repetitions 1 --launches 4
# (d) pre-flight before giving judges the code
docker compose exec app python -m agent_readiness.lifecycle.arming status          # problems [], launches 4 used 0 left 4, variants original improved
curl -s https://$SITE/api/ironbark/config | python3 -c "import json,sys;c=json.load(sys.stdin);print(c['judge_access'],c['launch'],c['evaluation']['variants'])"   # True, authorized, ['original','improved']
# To stop judge launches at once: docker compose exec app python -m agent_readiness.lifecycle.arming disarm
```

Optional zero-cost VM rehearsal before the paid arming (recommended in `m9-judge-live.md`): arm the same with `--mode rehearsal --arming vm-improved-rehearsal-1 --launches 1` on a rehearsal-mode service, run once, then disarm. Never leave a rehearsal arming active in production.

**Budget.** Programme known spend US$18.786306 = A$28.18 (A$21.82 left of the A$50 limit). A launch is expected to cost about US$0.45 (in the paid run these two tasks cost US$0.37 on Original and US$0.08 on Modified, where the cards carried the same facts Improved shows) and reserves US$2.508. Four launches reserve US$10.032 (worst case A$15.05), worst-case programme total **A$43.23**. Reservations are never released.

**Optional, not prepared:** a three-task suite with a class-day or campus task (for example v2 tasks 1, 3 and 4) would show the Improved site's extra fixes, which the two v3 tasks do not exercise (both are fee/seats/duration questions Modified already answered in 3 requests). It needs `revise --keep` with those ids, owner review and freezing, and reserves US$3.740 per launch.

## 6. Smoke tests after arming (zero cost unless a launch is made)
1. `/api/ironbark/config`: `judge_access true`, `launch.authorized true`, `launches_left 4`, `evaluation.variants ["original","improved"]`, 2 tasks.
2. `#/run`: compose shows "Larkspur Community College · 2 customer tasks · Original vs Improved site · 4 of 4 live runs left", the two task questions, an "Access code" field, "Run live evaluation".
3. A POST without the code → 403, with a wrong code → 403 (nothing reserved; `ceiling status` unchanged).
4. `#/lifecycle/reevaluate`: "Ready for a live run · 4 of 4 live runs left".
5. The first real judge launch is paid (owner approval): expect 4/4 agent runs in about 4–6 minutes, then `#/reports/<id>` and a new row in `#/lifecycle/compare`.

## 7. Video-ready demo sequence (about 3 minutes)
1. **Home** (`#/`): headline, the recorded screenshot and agent memory "Checked 3/14 fail, 11 unchecked, out of steps…"; scroll to Results (68 → 44 requests, per-task bars, tasks 3–5 still deep) and the Improved site (page audit 7 → 4 → 0).
2. **The Larkspur journey** (`#/lifecycle`), step by step with the stepper: Website (three versions) → Generate tasks (24 proposed, 20 accepted) → Review (the frozen six) → Evaluate (side-by-side screenshots; "Replay task 1 side by side" shows the trace player) → Recommendations (each marked "Applied") → Improve (before/after, the facts table) → Re-evaluate → Compare.
3. **Workspace** (`#/run`): paste the access code, "Run live evaluation", "Watch live" (screenshots, actions, the agent's goals) as the agents work on Original and Improved.
4. **Report** of the new run: correct answers, requests, time and cost for Original vs Improved; Replay a task; the recommendations section shows what the Improved site fixed.
5. Close on `#/lifecycle/compare`: the first live evaluation (Original vs Modified) and the new one (Original vs Improved) side by side.

If the live run is recorded before the video, keep it as the reference; if not, steps 1–2 and the existing live report carry the story and step 3 can be recorded against a local rehearsal, labelled as a rehearsal (the UI labels it automatically).

## 8. Risks and limitations
- **No live result for Improved yet.** The site shows only recorded results; Improved results appear after the first paid judge launch. Nothing about agent performance on Improved is claimed.
- **Single-shot launches.** A provider or VM failure consumes a launch and its reservation (no retry). One run at a time.
- **The two judge tasks** are fee/seats/duration questions; on them Improved and Modified carry the same facts on the cards, so the comparison mainly shows Original vs a site where the facts are on the cards (see the optional three-task suite in §5).
- **Grading:** "Exact match" is the official grader v1 (fails correct answers that add detail); "Correct" is the recorded v2 grade. Grading policy is unchanged.
- **Local rehearsal jail:** `/home` could not be hidden locally (the venv lives there); production's policy hides it.
- The record of `eval-e529…` still reads `failed` (preserved; the UI explains it).
- Merge to `main`, deployment, the judge secret, suite approval, the ceiling migration, the paid arming and any paid call all remain owner decisions.
