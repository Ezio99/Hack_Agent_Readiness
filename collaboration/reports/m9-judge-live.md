# Report: judge-triggered live Larkspur evaluation (release candidate)

**Date:** 2026-11-03 (Sydney). **Branch:** `m9-release-readiness`. The code is commit **`4841166`**; the release candidate is the commit that adds this report (documentation and screenshots only on top of it).
**Not deployed.** No paid call, no production change, no arming, no ceiling migration. All suite preparation and rehearsals used scratch copies.
**Includes** the earlier presentation patch `352f262` (still awaiting its own deployment approval): deploying this candidate deploys both.

## 1. The two tasks and the suite (verified from `larkspur-core@v2`)

| | Task id | Task record sha256 | Customer wording (executed unchanged) |
|---|---|---|---|
| 1 | `gen-23f1802ee0-n` | `b431adeaf5d9274e6959bcbffd261283b601262b61498a48601b95e84883a57a` | "I need a course that costs $250 or less and still has at least 5 seats left. What qualifies?" |
| 2 | `gen-f302fa8fe2-n` | `f6593d423804f826acea40a6ec7080cdbab0f8aec73c031e31aa3638e66710dd` | "I just graduated and need a cheap, quick skill for my CV. Find courses costing $180 or less that last 6 weeks or less." |

These are v2's tasks #1 and #6 in task-id order; the feasibility proposal used the same two.
- **Why these two:** they are the only tasks where Modified needed **3 requests in both paid runs** against 12–13 on Original. Their deciding facts (fee, seats, duration) are on the Modified listing cards.
- **The other four** (by task id: #2 the Life drawing fee lookup, 2–3 requests on both sites; #3 weekend Beginner courses, #4 Intermediate at Northside, #5 the Riverside seats ranking, 11–13 requests on both) show no request difference.

**`larkspur-core@v3`:**
- built by the existing owner tooling: the new `revise` subcommand, then the existing `decide` and `freeze`;
- from the **same immutable task records**: suite `f45694788ea9e1f7b28c95193e25870bfe3aed2975d7f00276cdc87d7c6b09e3`, reproduced byte-identically from both the local store and the production-data copy with the arguments in §6;
- v2 (frozen `0816af7f…`, suite `172d1e71…`, approval `31f1e3aa…`) is unchanged; a test checks every existing store file byte for byte;
- the approval and freeze hashes depend on when the owner types them, so they are produced on the VM.

## 2. Architecture (reuses the existing launch path)

`POST /api/ironbark/jobs {"repetitions": 1}` with `Authorization: Bearer <judge code>` goes through the **unchanged**:
- `StageBExecutor.admit`: the active arming must verify; checks repetitions armed, launches left and the arming total;
- `Admission.reserve_amount`: single slot, ceiling, per-client rate limit, never released;
- an exclusive-create launch claim, then a per-launch write-once PaidAuthorization and ledger;
- the worker subprocess, which re-checks everything;
- the runner: jailed Chromium; pinned muse-spark-1.3 / low / 4096 / `suite-v2-compat2`; reserve-before-send per request; per-trial caps; no retries;
- the audited lifecycle report, trace, screenshot and export routes.

No new engine, spending control or limit.

**The judge access code:**
- **Storage:** a separate secret, `deploy/secrets/judge_token`, mounted at `/run/secrets/judge_token` (`AR_JUDGE_TOKEN_FILE`).
- **Where it's accepted:** compared in constant time and consulted **only** by `start`. Lifecycle routes know only the operator check, and web suite decisions are refused for everyone.
- **Identity:** each judge is identified by address, so the existing 120 s per-client rate limit applies per judge. The operator stays one client.
- **When it's off:** if the file is absent, shorter than 24 characters, or equal to the operator token.
- **Never exposed:** it is not returned, logged or written anywhere; tests scan job files, claims, authorisations and the admission database. The config exposes only `judge_access: true/false`. The frontend holds it in page memory (never in storage or URLs) and sends it only as the authorisation header.
- **The operator token is unchanged.**

**Workspace (judge-facing):**
- "Access code" field; "Run live evaluation" (paid arming);
- a plain website card: "2 customer tasks · Original vs Modified site · N of 4 live runs left";
- a one-line run summary instead of a single-option repetitions picker ("4 browser agents, one per task on each site · about 5 min");
- the intro: "This live evaluation gives 2 customer tasks to browser agents on the Original and the Modified version of the site.";
- busy: "Evaluation running … Watch it live →";
- exhausted: "All live runs available for this demonstration have been used.";
- a wrong code: "That access code was not accepted. Check it and try again.";
- correct agent-run totals in the banner and in history. This fixes a pre-existing bug: Stage B jobs showed "1 × 8".

New jobs are titled "Live evaluation · Larkspur Community College · Original vs Modified". The home and demo card links the full 12-trial run as "Complete live evaluation · all six tasks".

Screenshots (local rehearsal mode, scripted stand-in, zero cost) are in `dashboard/review/m9-judge/`:
1. the ready state with the access-code field;
2. a refused code;
3. live progress;
4. a second visitor seeing "Evaluation running";
5. the readiness report;
6. a task trace.

In production (paid) the button reads "Run live evaluation" and there is no rehearsal banner.

## 3. Tests (all zero cost)

| Check | Result |
|---|---|
| `tests/test_m9_judge_access.py` (new, 19) | **Launch only:** the code launches through the normal path (claim, reservation, per-launch authorisation). **Refusals:** no code, a wrong code, a raw or `Basic` header, or a different header → 403, nothing reserved. **Nothing else:** the only write routes are launch and the always-refused web decision; there are no arming, ceiling, admin or file routes; reads are identical with or without the code. **Never recorded:** the code is in no response and no file. **Operator:** works, with a distinct client identity. **Judge access off** for a short code, a reused operator token or no code. **Public mode:** no judge code is advertised. **4-launch pool:** then 409 and nothing more reserved, config `launches_exhausted`. **6 concurrent launches:** exactly one admitted. **Restart:** the run is interrupted and its launch never reused; the next launch is #2. **A failed run** consumes its launch and keeps its reservation. **Service start:** reads the code file, logs only `judge_access=on/off`. **v3:** `revise` gives the exact hash, keeps exactly the two task records, leaves the store unchanged, and is only a proposal (not frozen) |
| `tests/test_m9_judge_browser.py` (new; run alone) | 1 passed (about 75–125 s): on a copy of the real store, v3 is revised, approved and frozen, a 4-launch **rehearsal** pool is armed, a judge launch with the code runs **4 trials in jailed Chromium**. Execution 4/4; report available and audit-clean; trial, screenshot and export routes work; pool 3 left; the code is in no file |
| `scripts/m9/judge_paid_path_rehearsal.py` (no network: socket/DNS guard, dead proxy, dummy key; copy of production data) | Paid pool: v3 manifest, 4 trials, cap US$2.464, **reservation US$2.508**, pool **US$10.032**. At today's US$10.736 the judge launch is **refused (429)**, nothing reserved or claimed. After migrating the copy to US$20.768, **two judge launches** each get their own authorisation and ledger, reserve 2 requests **before sending**, are refused by the network block, voided and halted with no retry. Reserved 10.736 + 2 × 2.508 = **US$15.752**; remaining US$5.016 (exactly 2 more); pool 2 of 4 left; the code is in no file |
| Broad regression (lifecycle, graders, hosted, ceiling, Stage B, diagnostics, framework, M9 ×4, deployment-safety and export scripts) | **422 passed**, 5 deselected |
| `scripts/critical-tests.sh` | 214 passed |
| `tests/test_lifecycle_m8_browser.py` (existing operator path; alone) | 1 passed |
| `dashboard`: `npx vitest run` | **212 passed** (+6: access code and Run-live-evaluation post; refused code; exhausted pool; history run counts; updated card, banner and link) |
| `npm run build` | CHECK PASSED |
| Local service in rehearsal mode (real `hosted.serve`, real jail, judge code) | Two judge runs completed 4/4 (1:37 each); a second browser saw "Evaluation running"; the pool went 4 → 3 → 2. The service log never contained the code |

Two boundary tests caught my first draft (`hosted` importing `framework`, and the word "research" in a hosted file). Both were fixed before the commit.

## 4. Runtime and cost per launch

From the two paid 12-trial runs (the same pinned model and these exact tasks):
- **Runtime:** agent time 177–260 s for these 4 trials, plus about 15 s per trial for browser start, plus about 30 s for preparation and the report → **about 4–6 minutes**. One evaluation runs at a time; others watch it live.
- **Expected cost:** **US$0.42–0.45 per launch** (Original 12–13 requests per task, Modified 3; about US$0.0134 per request). A realistic maximum is about US$0.85 (all 4 trials at the 14-request limit).
- **Reserved worst case:** **US$2.508 per launch** (4 × 14 × US$0.044 + one request bound), hard cap US$2.464 per launch ledger.

## 5. Four-launch pool: reservation and ceiling

| | USD |
|---|---|
| Pool reservation (arming total) | 4 × 2.508 = **10.032** |
| Hosted ceiling now | 10.736, fully reserved |
| **Required migration** | **10.736 → 20.768** (`--expect-ceiling 10.736 --expect-reserved 10.736`) |
| Programme, worst case after the pool | 18.786306 + 10.032 = 28.818306 = **A$43.23** (A$6.77 margin of A$50 at 1.50) |
| Programme, expected after the pool | about 18.79 + 1.8 = **about A$31** |

## 6. Owner steps on the VM (each is an approval checkpoint; run as `docker compose exec [-it] app …` in `/root/agent-readiness/deploy`)

```sh
STORE=/data/hosted/lifecycle/store
V2=172d1e712eb18871fd4f24b227a2448ec44a546347bb9874f0946c5609f7848b
V3=f45694788ea9e1f7b28c95193e25870bfe3aed2975d7f00276cdc87d7c6b09e3
# (a) the suite: revise must print exactly $V3; review it; approve at the terminal; freeze
docker compose exec app python -m agent_readiness.suites.stage_a.approval revise $STORE $V2 --keep gen-23f1802ee0-n gen-f302fa8fe2-n \
  --context-site larkspur --at 2026-11-03T12:00:00+00:00 --by owner \
  --notes "judge live evaluation: tasks gen-23f1802ee0-n and gen-f302fa8fe2-n of v2 (their deciding facts are on the Modified listing cards)"
docker compose exec app python -m agent_readiness.suites.stage_a.approval review $STORE $V3 --markdown
docker compose exec -it app python -m agent_readiness.suites.stage_a.approval decide $STORE $V3 approved --notes "judge live evaluation"   # type the attestation; prints APPROVAL
docker compose exec app python -m agent_readiness.suites.stage_a.approval freeze $STORE $V3 <APPROVAL>                                     # -> larkspur-core@v3
# (b) the judge secret: done before deploying (see §7); to rotate: write a new value, docker compose up -d --no-build --no-deps app
# (c) the ceiling (app stopped)
docker compose stop app
docker compose run --rm --no-deps -it app python -m agent_readiness.hosted.ceiling migrate --db /data/hosted/live/admission.sqlite \
  --to 20.768 --expect-ceiling 10.736 --expect-reserved 10.736 --reason "four judge-triggered live runs of larkspur-core@v3"
sed -i 's/^AR_HOSTED_CEILING_USD=.*/AR_HOSTED_CEILING_USD=20.768/' .env && docker compose up -d --no-build --no-deps app
# (d) the paid pool: prepare must show 4 trials, reserves US$2.508000, at most 4 launches reserving US$10.032000, "fits for repetitions [1]"
docker compose exec app python -m agent_readiness.lifecycle.arming prepare --arming larkspur-judge-1 --mode paid --frozen larkspur-core@v3 --variants original modified --repetitions 1 --launches 4
docker compose exec -it app python -m agent_readiness.lifecycle.arming arm --arming larkspur-judge-1 --mode paid --frozen larkspur-core@v3 --variants original modified --repetitions 1 --launches 4
# (e) pre-flight before giving judges the code: jail self-test ok; arming status: problems [], launches 4/0/4; config launch.authorized true
# To stop judge launches at once: docker compose exec app python -m agent_readiness.lifecycle.arming disarm  (no reservation; history stays)
```

## 7. Deployment and rollback (needs approval)

Deployment is the same as for `f36db53`, plus two items:
- **`deploy/compose.yaml` changed** (the new secret). Production runs compose from `/root/agent-readiness/deploy`, so copy the new `compose.yaml` there (keep the old one as `compose.yaml.pre-judge`).
- **Compose refuses to start if the secret file is missing.**

```sh
# backup (volume tgz + .env + checksum manifest), then build <C> in a clean worktree, pre-flight `ceiling status`, disabled smoke test on a volume copy
umask 077; head -c 32 /dev/urandom | base64 | tr -dc 'A-Za-z0-9' | head -c 40 > /root/agent-readiness/deploy/secrets/judge_token
chown 10001:10001 /root/agent-readiness/deploy/secrets/judge_token && chmod 400 /root/agent-readiness/deploy/secrets/judge_token   # (or "off" to keep judge access off)
cp /root/agent-readiness/deploy/compose.yaml /root/agent-readiness/deploy/compose.yaml.pre-judge && cp /root/agent-readiness-build-<C>/deploy/compose.yaml /root/agent-readiness/deploy/compose.yaml
docker tag agent-readiness-app:latest agent-readiness-app:rollback-f36db53 && docker tag agent-readiness-app:<C-tag> agent-readiness-app:latest
cd /root/agent-readiness/deploy && docker compose up -d --no-build --no-deps app       # log: ... judge_access=on|off
# verify: health; history (Ironbark, eval-e529 report and export); config judge_access; a judge POST without the code -> 403; evidence checksums
```

**Rollback:** `docker tag agent-readiness-app:rollback-f36db53 agent-readiness-app:latest`, restore `compose.yaml.pre-judge`, then `docker compose up -d --no-build --no-deps app`.
- The v3 suite, its approval and freeze, the arming and its claims are **write-once additions** that stay on the volume. The previous image can read them and would let the **operator** (not judges) launch the armed pool.
- To stop all launches, run `arming disarm`.
- A ceiling migration is never undone by a rollback.

## 8. Remaining risks and blockers

- **No blocker** for the release candidate. The production pool needs the owner steps in §6, and each one is a checkpoint.
- **Single shot per launch:** a provider outage or VM failure during a run consumes that launch and its reservation (no retry). Four launches give some slack.
- **One run at a time:** a second judge waits about 5 minutes (they can watch). Each judge address is rate-limited to one start per 120 s.
- **Code leak:** anyone with the code can use the pool, which is bounded at 4 launches and US$10.032 reserved. Rotate the code or disarm to stop.
- **Official v1 on task 1:** Modified answers that add fee and seat details fail official v1 (both earlier runs). The report shows official v1 and post-hoc v2 side by side. No audit note appears for new runs; only the two audited runs carry one.
- **Rehearsal-mode path disclosure (existing behaviour):** in rehearsal mode the scripted stand-in navigates straight to the expected-answer pages, so the trace **path** reveals the answer set (its answers are withheld). Paid judge runs show real agent paths. Do not leave a rehearsal arming active in production; the earlier VM rehearsal data is visible only in rehearsal mode.
- **Report wording:** the report keeps its exploratory and grader labels (shared with the 12-trial report). They are honest and stay unchanged.
- **Untested on the VM:** the paid path with a real model has not run on this exact two-task manifest. The first judge launch is its first paid use. A zero-cost VM rehearsal (rehearsal-mode v3 pool) before the paid arming is recommended. Disarm or replace that rehearsal arming afterwards.
