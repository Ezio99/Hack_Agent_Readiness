# Report: M9 release readiness of the M8 live-evaluation release candidate

**Date:** 2026-11-03 (Sydney) / 2026-11-02 UTC. **Branch:** `m9-release-readiness`, from `m8-product-integration` @ `a6cd59c` (release candidate
`e080a8d` + handoff). **Production was not accessed.** Nothing was deployed, migrated, armed, launched or merged.
**Spending: none.** No model was called. Every run used fixtures, the loopback dev provider (a scripted stand-in, not a model) or the paid branch with a dummy key behind a
three-layer network block (§3.4). The programme ledger is unchanged.

---

## 0. Verdict

**GO for deploying `m9-release-readiness` HEAD** (runbook steps 1–3, §7). Deploy this branch, not `e080a8d`/`a6cd59c`: it carries three small
fixes to the tools the runbook uses for the migration and for monitoring (§2).

**Conditional GO for the ceiling migration, the paid arming and the paid launch** (steps 4–7). The conditions are the pre-flight checks in §7:
- the production admission state on the VM must equal the 2026-11-02 copy (US$10 / US$3.30 / 2 completed / 0 active / no migration);
- the jail self-test must pass in the new container;
- recommended: a zero-cost rehearsal launch on the VM (about 5 minutes). This launch is single-shot: any failure after the reservation, even
  before the first request, uses up the whole US$7.436 and the only launch (§3.4, §5 R1).

No critical defect was found. The operator launch really does run the Stage B browser-agent pipeline. Owner arming, model pinning, server-side
validation, admission, reserve-before-send, no-retry, crash recovery and fail-closed behaviour all hold under independent tests. The budget
reconciliation reproduces to the microdollar from the durable ledgers.

## 1. What was verified, and how

| # | Area | Evidence (all zero cost) | Result |
|---|---|---|---|
| 1 | The operator-token workflow runs the Stage B pipeline | Code trace: `POST /api/ironbark/jobs` → `api.start` → `StageBExecutor.admit` → `work` thread → `LifecycleExecutor.run` → worker subprocess `lifecycle.jobs` → `evalruns.runner` prepare/execute/report/audit; `serve.build` installs only `StageBExecutor`, and the API refuses any other executor (503). **Rehearsal e2e** `tests/test_lifecycle_m8_browser.py` (real worker, jailed Chromium, operator token): 1 passed in 107 s, run alone. **Paid branch** through the same API on a copy of the production DB and the real store (§3.4): the worker verified the authorisation, and the agent sent its requests to the pinned `https://api.meta.ai/v1/chat/completions` (reserved first, blocked by the network guard) | holds |
| 2 | Frozen-suite integrity, owner arming, model pinning, launch validation | All 46 store records (31 public, 15 private) re-verify against their content hashes (`WriteOnceStore.get` raises `TamperError` otherwise). `arming.plan` on a copy of the store binds manifest `64a55c5f…` (the M7 manifest; 2 manifests in the store), 12 trials, reservation 7 436 000 µUS$. The manifest agent equals `agent_config()` exactly, including the jail-policy hash: muse-spark-1.3, `https://api.meta.ai/v1`, reasoning low, 4096 tokens, `suite-v2-compat2` `d18a2b7e…`; `ModelConfig` is hard-coded and `max_retries=0`. Arming without a TTY → `not_interactive`; a wrong attestation → `attestation_mismatch`. API: no token 403; an extra field 422; repetitions 3 (not armed) 409; a second launch while running 409; a relaunch after the launch 409 | holds |
| 3 | Spending safeguards, the US$10.736 ceiling, the A$50 programme | Independent recomputation from all 48 local durable ledgers (§4). Hosted DB copy sha256 `ef18cafd…` = ceiling 10 000 000, unit 1 650 000, interval 120, 2 completed × 1 650 000. At US$10 the exact launch is refused (429, nothing reserved or claimed); after the migration it is admitted at US$7.436 and nothing more fits | holds (nuance §4.3) |
| 4 | Crash recovery, duplicates, retries, isolation, fail-closed | A single slot (`BEGIN IMMEDIATE`) plus exclusive-create launch claims. The claim and authorisation are written 0444. A void trial halts the run with no retry. The worker re-checks the claim, arming, authorisation, ledger and reservation. **New test:** `recover()` kills a real surviving worker process group by its command line, leaves other processes alone, and marks the job interrupted with the reservation kept. The jail self-test passes; the browser has no network (namespace) | holds |
| 5 | Ironbark compatibility | The historical job `eval-aa23e330…` → 200 through the new API. The deployed image's admission code (`140a4e8`, loaded from git) on the migrated DB: fail-closed at `AR_HOSTED_CEILING_USD=10`; opens at 10.736; after the Stage B launch it admits nothing. **But** before a Stage B launch it can reserve 4 legacy repetitions (§5 R3) | holds, with a runbook correction |
| 6 | Deployment and rollback after the migration | Migration rehearsed on a copy of the production DB: refusals (wrong `--expect-*`, below reservations, above A$50, service lock held); applied 10 → 10.736 with one audit row; jobs byte-identical; the stale `.env` (10) is refused. A re-run of the identical command was **refused**, not "already applied" (fixed, §2 D1) | holds after the fixes |

## 2. Defects found and fixed on this branch

| | Defect | Severity | Fix |
|---|---|---|---|
| D1 | `ceiling migrate`: re-running the runbook's exact command (`--expect-ceiling 10`) after it was applied, for example after a dropped SSH session, is refused with `policy_mismatch`. The M8 docs promise "re-running a completed migration is a no-op". The existing test re-ran with `--expect-ceiling 10.736` only. Safe (nothing changes), but alarming at the exact moment the owner is checking a production budget change | low (operational) | `plan()` treats the target as already applied when the last audit row recorded exactly this from→to and the reservations still equal `--expect-reserved`. After a launch, the same command is refused (`reservations_mismatch`), and an unrelated `--expect-ceiling` is still refused |
| D2 | `ceiling migrate` printed the `.env` value with `:g` (6 significant digits). For example 12.345678 → `12.3457`, which leaves the service fail-closed (`budget_policy_mismatch`). 10.736 itself printed correctly | low | `ceiling.env_value()` gives the exact decimal; tests check the round trip through `serve.ceiling_microusd` |
| D3 | `hosted.admin watch`, the runbook's monitor for the paid run (step 7), counted `8 × repetitions` runs (the retired engine). A Stage B launch has 12, so it would show "12/8 runs". It also never printed why a run stopped | low (monitoring) | It uses the status's `tasks_planned` and appends the `stopped`/`error` reason |
| D4 | Rollback guidance (M8 §11.1, DEPLOY.md) says the old image "admits normally" with `AR_HOSTED_CEILING_USD=10.736`. Before the Stage B launch, that re-enables the retired engine for 4 × US$1.65 = US$6.60 of the capacity meant for the Stage B evaluation | medium (documentation) | DEPLOY.md: after a migration, roll back with `AR_HOSTED_CEILING_USD=10` (fail-closed). See §7 step 8 |

Tests: `tests/test_m9_release_readiness.py` (12): D1–D3, the deployed image's admission code on a migrated DB (before and after the launch), and
worker-kill recovery. Without the fixes, 8 of them fail.

## 3. Detail

### 3.1 The launch path (area 1)
- The client chooses only `repetitions` (`StartRequest`, `extra='forbid'`). Everything else comes from the active arming on the server.
- `admit` refuses before reserving when:
  - nothing is armed, or the arming's mode is not the service's;
  - the arming no longer verifies;
  - the repetitions are not armed;
  - all launches are used, or the arming's total is exhausted.
- It then reserves (single slot, ceiling, rate limit) and claims the launch. Paid launches also get a PaidAuthorization, re-verified with `evalruns.authorization.verify`.
- The worker refuses unless all of these hold:
  - the admission row is `running`;
  - the claim names this job;
  - the arming hash is unchanged and still verifies;
  - the authorisation matches the claim and the arming's attestation;
  - the ledger is unused;
  - the reservation equals the claim.
- The runner verifies the authorisation a third time. It checks that the runtime `ModelConfig` equals the manifest's model and endpoint, and runs every request through `RequestGate` with a per-trial cap of 14 × US$0.044, a scope cap equal to the authorisation's US$8.00, and trials counted from the ledger.
- The worker extends the jail at runtime (it also hides the store, runs and Stage B roots, and in the container `/app`, `/data` and `/run/secrets`) and restores it afterwards.
- `/api/ironbark/config` polling calls `arming.verify` on every request. That costs about 2 ms when warm (0.7 s cold), so it does not load the VM during a run.

### 3.2 Model pinning
`AgentConfig` in the M7 manifest:
- `muse-spark-1.3`, `https://api.meta.ai/v1`, reasoning `low`, 4096 completion tokens;
- profile `suite-v2-compat2` (sha256 `d18a2b7e…`), jail-policy sha256 `daf167a4…`.

It is identical to the pinned `agent_config()`. The arming verifies the full configuration. The authorisation verifies the model fields. The runner compares `ModelConfig()` with the manifest. `create_model` uses `max_retries=0`.

### 3.3 Budget enforcement chain (area 3)
1. **Hosted admission:** US$7.436 is reserved at launch and never released.
2. **Per launch:** a write-once authorisation with a US$8.00 cap and a fresh ledger `<STAGE_B>/ledgers/<arming>-l1/`.
3. **Per request:**
   - an upper bound is reserved and fsync'd before sending; the per-request cap is US$0.044;
   - a bound above the cap is refused;
   - the trial is limited to 14 requests and a US$0.616 run cap;
   - the US$8.00 scope cap applies across the launch.
4. **After a request:** settled from usage. A missing usage report keeps the full bound counted. A settlement above the bound closes the gate and halts the run.

### 3.4 Paid branch rehearsal, no network (new in M9; `scripts/m9/paid_path_rehearsal.py`)
**Inputs:** copies of the production DB and the real store, a paid arming `m9-nonet-1` of `larkspur-core@v2`, and the operator token.

**Three layers keep it zero-cost:**
- a `sitecustomize` guard in every Python process, inherited by the worker, refuses every non-loopback connect and non-local DNS lookup;
- `HTTP(S)_PROXY` points at a dead loopback port;
- the key is a dummy, and the process environment wins over the repository `.env`.

Inside the run the agent's requests failed with "Connection error.", and no response or usage was ever recorded, so nothing was sent.

**Result** (reproduced twice, the second time with the committed script and the fixes):

| Step | Outcome |
|---|---|
| Launch at US$10 | 429, nothing reserved or claimed |
| Migration to 10.736 | audit #1; jobs unchanged; the old `.env` value refused |
| Launch | 202. The worker re-verified the authorisation (`authorization-check-1`: 12 planned trials, verified). The agent targeted `api.meta.ai/v1/chat/completions` |
| Ledger | 2 requests **reserved before sending** (US$0.068408), 0 settled. browser-use issued its second request after the first connection error, as M8 observed |
| Trial and run | trial void (`infrastructure_error`); the run halted with the remaining 11 trials not run (no retries) |
| Afterwards | admission `failed`, US$7.436 held, total US$10.736 = ceiling, remaining 0. Relaunch 409. Claim and authorisation 0444. The history route of the old engine still 200 |

**Harness note:** the first attempt ran inside `unshare -rn`. There, the jailed browser could not nest its namespaces, so the worker failed at the jail self-test **before any request**. It still kept the full reservation and used the launch. That was an artefact of the harness (the same self-test passes outside it), but it is exactly the production failure class in R1.

## 4. Budget (verified independently)

### 4.1 Programme
- `collaboration/budget/programme-ledger.json`: 18 entries, sum **US$13.418982** (recomputed).
- **Unreconciled event-period spend, recomputed** from the durable ledgers. Per ledger: settled amount, else the reservation in full. De-duplicated across forks by `(request id, timestamp)`.

| Item | USD |
|---|---|
| L0 probes (`l0-probe` unsettled reservation 0.000950 + `-2` 0.000981 + `-3` 0.038231) | 0.040162 |
| L1a/EXP-B `site-5-live` with its `-b`/`-c` forks (the original is contained in `-c`) | 1.534404 |
| EXP-2 `exp2-pilot-1` | 1.141478 |
| Live taskgen smoke/exposure (`live-46b6…` 0.483129, `96a6…` 0.105844, `b6d9…` 0.062682, `bb5d…` 0.195084, `cb37…` 0.071032, `d722…` 0.064148) | 0.981919 |
| Investigator replay `replay-4bad5b1b` increment over its imported history | 0.122799 |
| **Total** | **3.820762**, equal to M8 |

- **Cross-check:**
  - The union of all real ledgers (excluding the dev-provider, mock, dry-run and rehearsal ledgers) is US$14.630743. That equals 13.418982 + 3.820762 + 0.000336 − 2.606 (Tasks 004–007, which have no local ledger) − 0.003337 (task011 recorded above its ledger).
  - Of that, 14.600739 is settled. The remaining 0.030004 is the two unsettled reservations (`research-taskplan-1` 0.029054 and the L0 probe 0.000950).
  - The excluded ledgers record `provider: dev` or are mock/dry-run.
- **Reconciled known spend: US$17.240080 = A$25.86** at the ledger's conservative 1.50 (a planning rate, not a market rate). **A$24.14 left** of A$50.
- Spend outside this workstation cannot be counted.

### 4.2 Hosted
- The copy shows US$3.30 reserved, backed by US$2.217065 of actual spend.
- One launch reserves 12 × 14 × 0.044 = 7.392 + 0.044 = **US$7.436**.
- **US$10.736 is the exact minimum** that admits it. After the launch, nothing remains.

### 4.3 Nuance: what bounds the actual spend
US$7.436 is the planning bound, not a hard stop:
- The enforced limits are the per-trial caps on **reserved** amounts (12 × US$0.616 = US$7.392) and the per-launch scope cap of US$8.00.
- A request whose true cost exceeds its estimated bound is recorded and closes the gate. Only one such request can happen per launch, but its excess is not bounded by US$0.044 in principle: the input-token estimate is characters/4 × 1.1 plus a screenshot allowance.
- **Even counted at the US$8.00 cap, the programme stays inside A$50:** 17.240080 + 8.00 = US$25.24 = A$37.86.
- M7 spent US$1.520696 on the same manifest.

### 4.4 If the single launch fails
A second attempt needs a new arming and another migration to US$18.172. Worst case for two full launches: 17.240080 + 2 × 7.436 = US$32.112 = A$48.17. That is inside A$50 but leaves A$1.83. A failed launch's real spend is usually small: the rehearsed failure reserved US$0.068.

## 5. Outstanding risks (not fixed; owner awareness)

| | Risk | Mitigation |
|---|---|---|
| R1 | **Single shot.** Any failure after admission uses up US$7.436 and the only launch, even with zero spend. Examples: a jail self-test that fails in the worker (the runner's self-test has no retry, unlike the service's start-up check), a provider outage, a restart, a disarm. Demonstrated at both 0 and 2 requests | Pre-flight (§7): jail self-test immediately before the launch. A zero-cost VM rehearsal of the same suite. No deploys or restarts during the run |
| R2 | **The new image has not run on the VM.** The M8 rehearsals ran in Docker Desktop (WSL2); production's kernel and AppArmor differ | Step 3 checks plus the recommended VM rehearsal |
| R3 | **Rollback between the migration and the launch** with `AR_HOSTED_CEILING_USD=10.736` re-enables the retired engine for US$6.60 | Roll back with `10` (fixed in DEPLOY.md) |
| R4 | **The production DB state is a 2-day-old copy** | `ceiling status` on the VM first. `migrate --expect-*` refuses on any difference |
| R5 | **The provider key is in the jailed Chromium's environment** (`jail.py` launches it with `{**os.environ}` after the paid worker loaded the key). It existed in production before M8. Web content cannot read process environments. The browser has no network, `/proc` is fresh, and the pages are our own snapshots | Follow-up: drop `META_MODEL_API_KEY` from the jail's environment (a security-boundary change; not made before the deadline without review) |
| R6 | **A failure inside `admit`** after the reservation and claim but before the job file is written (for example a disk error) leaves the admission row `reserved` with no worker, so the slot is blocked until restart. Fail-closed, and unlikely | `docker compose restart app` (recover marks it interrupted) |
| R7 | **`/api/ironbark/config` reports `available: true`** after the launches are used up. Cosmetic: the workspace disables Run (`launches.left` 0, `repetitions` []) | none needed |
| R8 | **Documentation inaccuracies:** the M8 report, handoff, STATUS and AGENTS.md date the M8 work "2026-11-04". The commits are 2026-11-03 Sydney (`9b11545`…`a6cd59c`, 00:40–08:31 +11:00). The `lifecycle/jobs.py` docstring still mentions `AR_LIFECYCLE_PAID` and `paid.check`, which no longer exist | Recorded here. The M8 documents are left as historical records |
| R9 | The reconciliation covers this workstation's ledgers only. AUD is a planning estimate. The suite is exploratory (6 tasks × 1 repetition, no improvement claim) | as disclosed in M8 |

## 6. Tests run (all zero cost; browser tests alone)

| Check | Result |
|---|---|
| Broad regression (lifecycle M1–M8, graders, hosted including ceiling and Stage B, diagnostics, framework, deployment safety, export) at `a6cd59c` | 354 passed, 5 deselected |
| `scripts/critical-tests.sh` at `a6cd59c` | 214 passed, 17 deselected |
| `tests/test_lifecycle_m8_browser.py -m browser` (operator launch → worker → jailed Chromium → report), alone | 1 passed (107 s) |
| `dashboard`: `npx vitest run` | 198 passed (18 files) |
| `tests/test_m9_release_readiness.py` (new) + `tests/test_hosted_ceiling.py` | 12 + 24 passed; 8 of the new tests fail without the fixes |
| Paid-branch rehearsal with no network (`scripts/m9/paid_path_rehearsal.py`), twice | as §3.4 |
| Store integrity (46 records) and `arming.plan` on a copy of the real store | as §1 |
| Re-run after the fixes: M9, ceiling, Stage B, hosted API/admission/service, lifecycle M8, deployment safety | 118 passed |
| Re-run after the fixes: `scripts/critical-tests.sh` | 214 passed, 17 deselected |

Not run: `npm run build` and `docker build` (no dashboard or Dockerfile change on this branch; M8 recorded both passing).

## 7. Runbook for the owner (corrected; nothing executed). `<C>` = HEAD of `m9-release-readiness`

M8 report §11 applies, with these changes:
- deploy `<C>` from `m9-release-readiness`;
- the pre-flight checks below;
- roll back with `AR_HOSTED_CEILING_USD=10`.

```sh
# 1. BACKUP (VM): as M8 §11 step 1 (volume tarball + .env copy).
# 2. DEPLOY the image + lifecycle store: as M8 §11 step 2, but fetch the M9 branch:
git -C /root/agent-readiness fetch origin m9-release-readiness && git -C /root/agent-readiness worktree add --detach /root/agent-readiness-build-m9 <C>
cd /root/agent-readiness-build-m9 && docker build -f deploy/Dockerfile -t agent-readiness-app:m9-<C> .
#    PRE-FLIGHT A (read-only, new image): expect ceiling US$10.000000; US$3.300000 held by 2 job(s) completed; active 0; no migration line. Else STOP.
docker run --rm -v agent-readiness_data:/data:ro agent-readiness-app:m9-<C> python -m agent_readiness.hosted.ceiling status --db /data/hosted/live/admission.sqlite
#    PRE-FLIGHT B (store copied intact): expect "31 objects, 15 private, refs ['frozen_suite/larkspur-core@v2.json', ...]"
docker run --rm -v agent-readiness_data:/data:ro agent-readiness-app:m9-<C> python -c "from pathlib import Path; from agent_readiness.suites.store import WriteOnceStore as W; s=W(Path('/data/hosted/lifecycle/store')); o=[s.get(p.parent.name,p.stem) for p in (s.root/'objects').glob('*/*.json')]; v=[s.get('private_outcome',p.stem) for p in (s.root/'private').glob('*.json')]; print(len(o),'objects,',len(v),'private, refs',sorted(str(p.relative_to(s.root/'refs')) for p in (s.root/'refs').rglob('*.json')))"
#    (the private/ directory is 0700 for uid 10001; the image runs as uid 10001, so this read works)
docker tag agent-readiness-app:latest agent-readiness-app:rollback-140a4e8 && docker tag agent-readiness-app:m9-<C> agent-readiness-app:latest
cd /root/agent-readiness/deploy && docker compose up -d --no-build --no-deps app
# 3. VERIFY: as M8 §11 step 3 (log line engine=stage-b armed=none (not_armed); health; history 200).
#    PRE-FLIGHT C (recommended, zero cost, about 5 min; a mode switch, so it needs your approval):
#      sed -i 's/^AR_HOSTED_MODE=.*/AR_HOSTED_MODE=rehearsal/' .env && docker compose up -d --no-build --no-deps app
#      docker compose exec -it app python -m agent_readiness.lifecycle.arming arm --arming vm-rehearsal-1 --mode rehearsal --frozen larkspur-core@v2 --variants original modified --repetitions 1 --launches 1
#      docker compose exec app python -m agent_readiness.hosted.admin start --repetitions 1 --watch      # expect completed 12/12 runs
#      sed -i 's/^AR_HOSTED_MODE=.*/AR_HOSTED_MODE=live/' .env && docker compose up -d --no-build --no-deps app   # rehearsal data stays in /data/hosted/rehearsal
#      (rehearsal mode uses its own admission DB /data/hosted/rehearsal/admission.sqlite. If that DB exists with another ceiling, the service
#       reports budget_policy_mismatch: then skip C rather than changing anything. A rehearsal arming is never launchable in live mode.
#       The rehearsal adds rehearsal-labelled RunResult records to the store, as the M8 container rehearsal did. Pre-flight B's count is
#       therefore taken before it.)
# 4. CEILING MIGRATION: as M8 §11 step 4. If the session drops, re-running the same command now reports "already applied".
# 5. ARM (paid): as M8 §11 step 5 (prepare must show manifest 64a55c5f…, 12 trials, reserves US$7.436000, "fits for repetitions [1]").
#    PRE-FLIGHT D, immediately before the launch:
docker compose exec app python -c "from agent_readiness.hosted import jail; print(jail.selftest())"     # ok True
docker compose exec app python -m agent_readiness.lifecycle.arming status                              # problems: [], launches left 1
# 6. LAUNCH: #/run → operator token → 1 repetition → Run evaluation. Do not deploy, restart or disarm until it is terminal.
# 7. MONITOR: as M8 §11 step 7. `admin watch` now shows x/12 runs and any stop reason.
# 8. ROLLBACK (image):
docker tag agent-readiness-app:rollback-140a4e8 agent-readiness-app:latest
sed -i 's/^AR_HOSTED_CEILING_USD=.*/AR_HOSTED_CEILING_USD=10/' .env     # after a migration: keep the old engine fail-closed (budget_policy_mismatch; history viewable)
docker compose up -d --no-build --no-deps app
#    Never restore the pre-deploy volume after a paid launch (its spend would vanish from the hosted accounting).
```

## 8. Production actions that require the owner's explicit approval

1. **Deploy** `m9-release-readiness` HEAD (`<C>`) to the VM and copy the lifecycle store (steps 1–3, with pre-flights A and B).
2. *(Recommended)* **Zero-cost VM rehearsal** (pre-flight C): a temporary `AR_HOSTED_MODE=rehearsal`, one rehearsal arming, and back to live.
3. **Ceiling migration** 10 → **10.736** with `--expect-ceiling 10 --expect-reserved 3.3` and the stated reason, plus `AR_HOSTED_CEILING_USD=10.736` in `deploy/.env` (step 4).
4. **Paid arming** over SSH: arming id (e.g. `larkspur-live-1`), 1 repetition, 1 launch, reserving US$7.436 (step 5). Typed by the owner.
5. **The paid launch** (step 6). Expected about US$1.5 (M7); planning bound US$7.436; enforced cap US$8.00.
6. **Programme ledger:** append the reconciliation entry US$3.820762, the +US$0.000336 task012 correction and, after the run, its settled total.
7. **Merge strategy** (`m9-release-readiness` → `m8-product-integration` → `evaluation-v2` → `main`). Any public-access change. Any later second migration or arming.
