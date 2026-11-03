# Final showcase: the three-task judge suite (prepared; NOT frozen, NOT armed, NOT deployed)

**Date:** 2026-11-03 (Sydney). **Branch:** `final-showcase`. **Cost:** US$0 (no paid call; only scratch copies of the stores and databases were changed).
**Known-good release candidate:** `b81cff5` (unchanged; see `final-showcase-release.md`). **Three-task candidate:** `83be351` = `b81cff5` + judge-facing copy derived from the configured judge tasks (§6), tests and rehearsal tooling. No engine, launch, admission or grading code changed.

## 1. Decision: add v2 task 3, `gen-8334922e62-n` (class day)

| v2 task | Wording (customer = executed, unchanged) | Deciding facts | Link steps Original / Modified / Improved | Recorded paid trials (M7 run, live run `eval-e529…`) |
|---|---|---|---|---|
| 1 `gen-23f1802ee0-n` | "I need a course that costs $250 or less and still has at least 5 seats left. What qualifies?" | fee, seats | 2 / 1 / 1 | Original 12, 13 requests, not correct; Modified 3, 3, correct |
| **3 `gen-8334922e62-n`** | **"I work full-time on weekdays, so I can only do Saturday or Sunday. List Beginner courses that meet on Saturday or Sunday."** | **class day, level** | **2 / 2 / 1** | **Original 12, 13 requests; Modified 13, 13 requests; not correct in any of the 4 trials (named 1–2 of 4 courses)** |
| 4 `gen-ae6c23b20b-n` | "I want to push beyond basics. Show me Intermediate courses at Northside." | campus, level | 2 / 2 / 1 | Original 13, 13, not correct; Modified 13, 12, **correct** in both |
| 5 `gen-f090b4b9bc-n` | "I want an Intermediate course at Riverside for after work. Among those, which one has the most seats left?" | campus, level, seats | 2 / 2 / 1 | Original 13, 13, correct in both; Modified 11, 11, not correct |
| 6 `gen-f302fa8fe2-n` | "I just graduated and need a cheap, quick skill for my CV. Find courses costing $180 or less that last 6 weeks or less." | fee, duration | 2 / 1 / 1 | Original 12, 13; Modified 3, 3, correct |

**Why task 3.** It is the only campus/class-day task that failed in every recorded trial on both Original and Modified (12–13 of 14 requests each time), so its result on Improved is attributable to what only Improved adds. Modified already put **level** on the cards but not **class day**; Improved adds class day to every card, a Weekend filter (`/courses?level=Beginner&campus=&day=Weekend` → exactly the four courses), a linked `/courses/day/weekend` page and the comparison table. Tasks 4 and 5 were passed on one version or the other in the recorded runs, so they show the change less cleanly. (Its kind is `either_of`: "Saturday or Sunday" is a union, and the answer is a set of courses.)

Nothing here claims how agents will do on Improved; that is what the live judge runs measure.

## 2. Verified facts (zero cost)

| Check | Result |
|---|---|
| Immutable records | The new suite references the **same task records** as frozen `larkspur-core@v2` (`0816af7f…`, suite `172d1e71…`): `gen-23f1802ee0-n` = task `b431adea…` (private outcome `fe0126ad…`), `gen-8334922e62-n` = `6b13fdd4…` (`0b80c10b…`), `gen-f302fa8fe2-n` = `f6593d42…` (`f7325fcd…`). No record is copied or edited |
| Same correct answers | For each of the three tasks the frozen criterion re-derives the **identical** expected answer on Original, Modified and Improved (`evalruns.runner.validity`; the runner would set a task aside if it did not). Task 3 has 4 expected courses on every version. The answers stay private (not printed in this report) |
| Mechanism | Task 3's evidence on Improved is `/courses` alone (1 link step; 2 on Original and Modified); its facts (level, class day) are on every Improved card; the filter and browse routes work through the jailed mirror (`tests/test_larkspur_improved.py`) |
| **Suite hash** | **`0e46a1efe0a628ff2fb69c72ce0c0eb2323919570e4e3fbde1ac296d93460360`** (`larkspur-core` v3), produced by the owner CLI command in §5 on a copy of the **production** store and, identically, on the local research store |
| Manifest | Built by `arming prepare` and reused by `arm`. Its hash includes its creation time, so it is not known in advance (rehearsal copy: `01a7f511…`). Check its fields instead: frozen suite `larkspur-core@v3`, variants `original 2f9fd2ce09a0` and `improved 87e715d59c23`, 1 repetition, seed 7, **6 trials, cap US$3.696, reserves US$3.740000** |
| Code | **No engine change needed.** Arming, admission, launch claims, ledgers, the worker, grading, the report and the workspace are task-count agnostic (the workspace already shows "6 browser agents" and lists the three questions from the armed suite). Only two pieces of judge-facing copy named the two-task suite; they now derive from `FEATURED.judgeTasks` (§6) |

## 3. Budget arithmetic (reservation-based worst case; USD calculated, not invoiced)

| Item | Value |
|---|---|
| Worst case per launch | 3 tasks × 2 versions × 14 requests × US$0.044 = **US$3.696** (hard cap) |
| Reservation per launch | US$3.696 + one-request bound US$0.044 = **US$3.740** |
| **3 launches** | **US$11.220** reserved |
| Hosted ceiling | today 10.736, all reserved (3 jobs). **Migrate 10.736 → 21.956** (= 10.736 + 11.220) |
| Programme | known spend US$18.786306 (A$28.18) + 11.220 = US$30.006306 × 1.50 = **A$45.01 ≤ A$50** (A$4.99 headroom) |
| 4 launches (not possible) | 18.786306 + 14.960 = US$33.746306 = A$50.62 > A$50 |
| Expected spend | about **US$0.65–0.85 per launch** (recorded per-trial costs: Original tasks 1, 3, 6 cost US$0.51–0.56; Modified tasks 1 and 6 US$0.08; task 3 on Improved US$0.04 if answered from the cards, up to US$0.19 if it again runs to the limit). Three launches ≈ US$2.0–2.5 (A$3.0–3.8) |

Reservations are never released; unused reserve stays held (as for every earlier launch).

## 4. Runtime per judge launch

- **Zero-cost rehearsal:** the e2e test (setup, 6 jailed trials with the scripted stand-in, report) took 150 s.
- **Paid estimate:** about **6–9 minutes**. Original tasks 1, 3 and 6 took 233–332 s in total in the two paid runs; Improved tasks 1 and 6 should take about 20 s each (Modified did); task 3 on Improved takes 20–120 s; overhead about 30 s (the six-task live run: 886 s wall for 872 s of agent time).
- **Bound:** each agent stops at 14 model requests (about 2 minutes) or 240 s, so at most about 12 minutes in practice, 24 minutes in theory. One launch runs at a time.

## 5. Production approval steps (each needs the owner; in this order)

```sh
ssh root@209.38.84.72 && cd /root/agent-readiness/deploy
SITE=209-38-84-72.sslip.io
STORE=/data/hosted/lifecycle/store
V2=172d1e712eb18871fd4f24b227a2448ec44a546347bb9874f0946c5609f7848b
V3=0e46a1efe0a628ff2fb69c72ce0c0eb2323919570e4e3fbde1ac296d93460360
```

**1. Deploy** `83be351` exactly as `final-showcase-release.md` §4 (backup, clean worktree build, `ceiling status` pre-flight, disabled smoke test on a volume copy, judge secret, new `compose.yaml`, switch, verify), with `C=83be351`. Rollback as §4. (`b81cff5` is functionally identical for this suite; only the review-step note would name "tasks 1 and 6".)

**2. Suite: revise, review, approve, freeze** (`revise` must print exactly `$V3`):
```sh
docker compose exec app python -m agent_readiness.suites.stage_a.approval revise $STORE $V2 \
  --keep gen-23f1802ee0-n gen-8334922e62-n gen-f302fa8fe2-n --context-site larkspur --at 2026-11-04T00:00:00+00:00 --by owner \
  --notes "judge live evaluation: v2 tasks gen-23f1802ee0-n, gen-8334922e62-n and gen-f302fa8fe2-n (fee and seats; weekend class day and level; fee and duration)"
docker compose exec app python -m agent_readiness.suites.stage_a.approval review $STORE $V3 --markdown    # 3 tasks, as in §1
docker compose exec -it app python -m agent_readiness.suites.stage_a.approval decide $STORE $V3 approved --notes "three-task judge live evaluation"
#   type exactly: I am the owner and I approve suite 0e46a1efe0a628ff2fb69c72ce0c0eb2323919570e4e3fbde1ac296d93460360   -> prints <APPROVAL>
docker compose exec app python -m agent_readiness.suites.stage_a.approval freeze $STORE $V3 <APPROVAL>    # -> larkspur-core@v3
```

**3. Hosted ceiling 10.736 → 21.956** (app stopped; the `.env` value must equal the database):
```sh
docker compose exec app python -m agent_readiness.hosted.ceiling status --db /data/hosted/live/admission.sqlite   # 10.736 / 10.736 reserved / 3 jobs / 0 active
docker compose stop app
docker compose run --rm --no-deps -it app python -m agent_readiness.hosted.ceiling migrate --db /data/hosted/live/admission.sqlite \
  --to 21.956 --expect-ceiling 10.736 --expect-reserved 10.736 --reason "three judge-triggered live runs of larkspur-core@v3, Original vs Improved"
sed -i 's/^AR_HOSTED_CEILING_USD=.*/AR_HOSTED_CEILING_USD=21.956/' .env && docker compose up -d --no-build --no-deps app
docker compose logs app | grep 'hosted service'      # evaluations=enabled jail=verified engine=stage-b (no budget_policy_mismatch)
```

**4. Paid pool: prepare, read, arm** (`prepare` must show: website larkspur `original 2f9fd2ce09a0`, `improved 87e715d59c23`; 6 trials; cap US$3.696; reserves US$3.740000; at most 3 launches reserving US$11.220000; fits for repetitions [1]):
```sh
docker compose exec app python -m agent_readiness.lifecycle.arming prepare --arming larkspur-judge-1 --mode paid --frozen larkspur-core@v3 --variants original improved --repetitions 1 --launches 3
docker compose exec -it app python -m agent_readiness.lifecycle.arming arm --arming larkspur-judge-1 --mode paid --frozen larkspur-core@v3 --variants original improved --repetitions 1 --launches 3
```

**5. Pre-flight before handing out the code** (zero cost):
```sh
docker compose exec app python -m agent_readiness.lifecycle.arming status      # larkspur-judge-1, problems [], launches 3 used 0 left 3
curl -s https://$SITE/api/ironbark/config | python3 -c "import json,sys;c=json.load(sys.stdin);print(c['judge_access'],c['launch'],c['evaluation']['variants'],len(c['tasks']))"
#   True {'authorized': True, ... 'launches_left': 3} ['original', 'improved'] 3
curl -s -o /dev/null -w '%{http_code}\n' -X POST -H 'content-type: application/json' -d '{"repetitions":1}' https://$SITE/api/ironbark/jobs   # 403 without the code
#   #/run shows "3 customer tasks · Original vs Improved site · 3 of 3 live runs left", the three questions, "Access code", "Run live evaluation"
```
Stop launches at any time: `docker compose exec app python -m agent_readiness.lifecycle.arming disarm` (no reservation; history stays).

**6. First paid judge launch** (a paid call; owner approval): about 6–9 minutes; afterwards `ceiling status` shows US$14.476 reserved by 4 jobs and US$7.480 remaining (2 launches).

## 6. Tests run (zero cost)

| Check | Result |
|---|---|
| Suite hash with the owner CLI on copies of the production and research stores | both `0e46a1ef…` |
| `tests/test_showcase_judge_browser.py` (now the three-task featured configuration; run alone) | 1 passed in 150 s: v3 revised to the exact hash, approved and frozen on a store copy; 3-launch rehearsal pool on Original vs Improved (6 trials, reserves US$3.740, pool US$11.220); judge launch with the code → 6/6 jailed trials; Original vs Improved; report available, audit-clean, diagnostics: Improved resolves 7 page problems, introduces 0; 2 launches left; the code in no file |
| `scripts/m9/judge_paid_path_rehearsal.py` with `M9_JUDGE_SUITE=three M9_JUDGE_VARIANTS=original,improved` (no network, copies of production data) | judge launch at 10.736 refused (429), nothing reserved; migration 10.736 → 21.956 (audit #2 on the copy); two launches each with its own authorisation, 2 requests reserved before sending, blocked, void, halt, no retry; reserved 18.216, remaining 3.740; pool 3 → 1; the code in no file |
| The same script, default (two-task) | unchanged: reserves US$2.508, pool US$10.032, ceiling 20.768, two launches → US$15.752 reserved, 2 of 4 left, the code in no file |
| Dashboard `npx vitest run` / `npm run build` | 215 passed (the review note reads "tasks 1, 3 and 6 of this set") / CHECK PASSED |

## 7. Risks
- Task 3 is the hardest of the three (an `either_of` set of four courses). If agents still list a wrong or partial set on Improved, the report shows that faithfully; the request count and time still show whether the page change reduced navigation.
- "Exact match" (official grader v1) rejects correct answers that add details such as fees; "Correct" is the recorded v2 grade. Grading is unchanged.
- Three launches only. A provider or VM failure consumes a launch and its reservation (no retry).
- Revise **only** this suite in production. The version number is part of the hash: if the two-task suite (`f4569478…`) or any other revision were made first, this one would become v4 with a different hash and `revise` would not print `$V3`. Stop and re-check if it does not.

## 8. Deployment record (owner-approved, 2026-11-03; deployment only)

Approval covered deployment steps 1–5 and verification only: **not** the suite, the ceiling, the arming or any paid call.

| Step | Result |
|---|---|
| Read-only VM preflight | Image `m9s-f36db53` (`6fa8b107…`), healthy, 0 restarts; `.env` live/operator/10.736; ceiling 10.736 fully reserved by 3 jobs, 0 active, migration #1; arming `larkspur-live-1` 0 left, problems []; store and stage-b files **byte-identical** to the copy that produced `0e46a1ef…`; secrets 10001:10001 0400; 67 GB free |
| 1 Backup (outside the volume) | `/root/backups/predeploy-fs-20261103T040754Z.tgz` (sha256 `294d7de7…`, gzip OK), manifest `.sha256` of 2 206 files (extracted archive matches every entry), `env-predeploy-fs-…` (identical). Versus the previous deploy's manifest: only two `.service.lock` files added; 2 204 common files unchanged |
| 2 Build | clean worktree `/root/agent-readiness-build-fs` at `83be351d7ec5…`, 0 untracked; image `agent-readiness-app:fs-83be351` = **`sha256:f5d9ec46d28369b54423043d0e0437af293bde739d096d88563e4266b67e6744`**; frontend `index-CYC27dEE.js` identical to the local build; snapshots `2f9fd2ce09a0` / `edb9a5d2884a` / `87e715d59c23`; uid 10001 |
| 3 Pre-flight and smoke | `ceiling status` with the new image unchanged; disabled smoke test on a volume copy (loopback): **15/15 PASS**, 0 tracebacks; copy removed |
| 4 Judge secret, compose | `secrets/judge_token` 10001:10001 0400, 40 characters, differs from the operator token (never printed); `compose.yaml` adds only the judge secret; previous kept as `compose.yaml.pre-judge`; `docker compose config` valid |
| 5 Switch | `rollback-f36db53` = `6fa8b107…`; `latest` = `f5d9ec46…`, started 2026-11-03T04:09:50Z, healthy, 0 restarts; log `mode=live access=operator evaluations=enabled jail=verified engine=stage-b armed=larkspur-live-1 (paid, larkspur-core v2, launches left 0) judge_access=on`; 0 tracebacks |
| Verification | Public **15/15 PASS**: health; config `judge_access true`, `launches_exhausted`, ceiling 10.736/10.736; POST without a code 403, with a wrong code 403; frontend hash; HSTS, CSP, nosniff; HTTP→HTTPS 308; versions incl. `improved 87e715d59c23`; no v3 suite; `eval-e529…` report (12 trials, US$1.546226 settled), job (record `failed`, execution completed, note), export; M7 report; both Ironbark jobs; a trace screenshot. VM: ceiling and arming unchanged; **2 204 evidence files byte-identical** to the backup, no new files; the judge code in no log line or data file; container uid 10001, CapEff 0. Browser (GET only): Home, journey (deep links), workspace, live report, Ironbark archive: 0 console errors |

Recorded in `deploy/DEPLOYED.txt` on the VM. **Rollback:** `cp compose.yaml.pre-judge compose.yaml && docker tag agent-readiness-app:rollback-f36db53 agent-readiness-app:latest && docker compose up -d --no-build --no-deps app`.

**Next checkpoint (needs separate owner approval):** §5 steps 2–5: revise (must print `0e46a1ef…`), review, decide (owner types the attestation), freeze; ceiling 10.736 → 21.956 (+ `.env`); arm `larkspur-judge-1` (3 launches, Original vs Improved); pre-flight. Then, separately, the first paid launch.

## 9. Production configuration record (owner-approved, 2026-11-03 UTC; no paid launch)

| Step | Result |
|---|---|
| Revise | `revise` printed exactly `0e46a1efe0a628ff2fb69c72ce0c0eb2323919570e4e3fbde1ac296d93460360` (`larkspur-core` v3); its three records are the frozen v2 records `b431adea…` (`gen-23f1802ee0-n`), `6b13fdd4…` (`gen-8334922e62-n`), `f6593d42…` (`gen-f302fa8fe2-n`), private outcomes unchanged |
| Owner decision | typed by the owner at an interactive terminal: approval `59c866ba56c6d2e458a4bf535a1db9f343f8a7da3e31c77e4b16f2412c3ff74e`, role owner, 2026-11-03T04:17:00Z |
| Freeze | `larkspur-core@v3` → frozen `db2eb1cb64eb62448ded0168d849f8a0dad8ab6f2796db4aa4bacbe25a6fb045` → suite `0e46a1ef…`, approval `59c866ba…`; tasks exactly 1, 3, 6 |
| Ceiling | migration #2 typed by the owner: 2026-11-03T04:18:52Z, US$10.736 → **US$21.956**; reserved US$10.736 by the same 3 jobs (job-rows fingerprint `ded90f80…` unchanged); **remaining US$11.220**. `.env` `AR_HOSTED_CEILING_USD=21.956` (previous `.env` copied to `/root/backups/env-pre-ceiling-21.956-…`); app restarted 04:19:19Z on `f5d9ec46…`, healthy |
| Prepare | manifest **`c32cfc6fa1a0a6d329e57adc3197967a3317ef274162fd5a0b5e5e429f567c71`**: frozen v3, original `2f9fd2ce…` vs improved `87e715d5…`, 1 repetition, seed 7, natural condition, 3 tasks × 14 requests, per-request cap US$0.044, hard cap US$3.696, reserves US$3.740; muse-spark-1.3, low, 4096, `suite-v2-compat2` `d18a2b7e2666` |
| Arm | typed by the owner: `larkspur-judge-1`, paid, recorded 2026-11-03T04:21:54Z, max 3 launches, US$11.220 total |
| Post-arming | `arming status`: active `larkspur-judge-1`, problems [], launches 3 / used 0 / left 3, option 6 trials US$3.740 available and fits. Config: `judge_access true`, `launch.authorized true`, 3 left, variants original/improved, the 3 task questions. POST without a code, with a wrong code, with a Basic header: **403**. Ceiling 21.956 / 10.736 reserved / 11.220 remaining, 0 active. **No new launch claim, authorisation or ledger** (only `larkspur-live-1-l1` exists; its ledger sha256 `e4675700…` unchanged). Evidence: 2 202 of 2 204 backed-up files byte-identical; the 2 others are the expected `armings/ACTIVE` pointer and `admission.sqlite` (migration #2). New files: the suite, approval, frozen record, v3 ref, manifest and the `larkspur-judge-1` arming record only. Historical reports 200. Browser: workspace "3 customer tasks · Original vs Improved site · 3 of 3 live runs left", "Worker available"; journey "Ready for a live run … 3 of 3 live runs left"; 0 console errors |

Programme: known spend unchanged at US$18.786306 (A$28.18); reservation-based worst case with the pool A$45.01 of A$50.

**Next (separate owner authorisation):** the first paid judge launch from `#/run` with the access code (reserves US$3.740; expected about US$0.65–0.85 and 6–9 minutes).

Cosmetic follow-ups for any later deploy (need approval; not done): the journey's re-evaluate card says "about 4–6 minutes" (the workspace's own estimate for 6 agents reads about 8 minutes); two version names render without a space between them in the journey; the sticky header is translucent over scrolled content. The service's startup log line still names the earlier arming because it was written before arming; the live config and `arming status` show `larkspur-judge-1`.

## 10. First paid judge launch (owner-authorised: exactly one; 2026-11-03 UTC)

**Pre-launch:** `larkspur-judge-1` unchanged (arming record sha256 `800baf2a…`, manifest `c32cfc6f…`, 3 of 3 left, problems []); worker idle; ceiling US$21.956 with US$11.220 free. **Launch:** one `POST /api/ironbark/jobs {"repetitions":1}` through the public judge path with the judge code (read from the secret file into a root-only tmpfs header file, deleted after; never printed): HTTP 202 at 04:24:23Z, **`eval-c04fdb100d6b1c877de96dabe76eb052`**. No retry. Completed 6/6 at 04:30:33Z (agents 04:24:31–04:29:54; 5:56 elapsed in the workspace); report available 04:30:53Z.

| Task (suite) | Version | Correct | Exact match | Requests | Time | Cost | Path | Answer coverage |
|---|---|---|---|---|---|---|---|---|
| 1 `gen-23f1802ee0-n` fee ≤ $250, ≥ 5 seats | Original | ✕ | ✕ | 13/14 | 74.6 s | US$0.176346 | `/` → `/courses` ⇄ 3 course pages → `/courses/beginners-yoga` | 1 of 5 |
| | **Improved** | **✓** | ✕ | **2/14** | **13.0 s** | US$0.026841 | `/` → `/courses/compare` | **5 of 5**, none extra |
| 2 `gen-8334922e62-n` weekend, Beginner | Original | ✕ | ✕ | 13/14 | 82.7 s | US$0.181523 | `/` → `/courses` ⇄ 4 course pages | 2 of 4 |
| | **Improved** | **✓** | ✕ | **2/14** | **21.4 s** | US$0.027361 | `/` → `/courses/compare` | **4 of 4**, none extra |
| 3 `gen-f302fa8fe2-n` fee ≤ $180, ≤ 6 weeks | Original | ✕ | ✕ | 13/14 | 104.5 s | US$0.193060 | `/` → `/courses` ⇄ 3 course pages | 1 of 3 |
| | **Improved** | **✓** | ✕ | **2/14** | **19.3 s** | US$0.026616 | `/` → `/courses/compare` | **3 of 3**, none extra |

Totals: Original **0/3 correct, 39 requests, 262 s, US$0.550929**; Improved **3/3 correct, 6 requests, 54 s, US$0.080818**. **Settled US$0.631751** in the launch's durable ledger `larkspur-judge-1-l1` (45 requests reserved before sending, largest reservation US$0.036 < US$0.044 cap; 45 settled; 0 unsettled). No HTTP errors or dead ends on either version; 0 errors in the service log. Diagnostics: 17 observations, 6 likely causes; the Improved version resolves 7 page-audit problems and introduces none.

**After:** ceiling US$21.956, **US$14.476 reserved by 4 jobs, US$7.480 free**; `larkspur-judge-1` **2 of 3 launches left**, problems []; worker idle. Programme known spend (not yet appended to the programme ledger, which needs owner approval): US$18.786306 + 0.631751 = **US$19.418057 = A$29.13**; reservation-based worst case unchanged at A$45.01.

**Observations:**
- Every Improved agent went straight from the home page to the new comparison table (`/courses/compare`, linked from Home and every listing) and answered from it; none used the filter form or the browse pages. Original agents read the catalogue, then opened course pages one at a time and returned partial answers near the request limit.
- "Exact match" (official grader v1) is 0/3 on both versions: the Improved answers add fees, seats, days or weeks (e.g. "Beginners yoga – Beginner – Saturday"). "Correct" is the recorded v2 grade.
- The recorded evidence rule names `/courses` as the page holding the answer, so it does not credit `/courses/compare`, where the Improved agents read every fact ("Shown the pages that hold the answer 0/3", "1 required page not shown"). Grading is unchanged.
- The workspace's "Agent runs" grid uses the official grade, so after completion every cell there reads "Not passed" (with requests and time). The "Readiness report" tab, the report page, the trace replay and the journey's Compare table show Correct 0/3 → 3/3.
