# Separate A$20 evaluation budget: implementation, tests and deployment/migration plan (release candidate; NOT deployed)

**Date:** 2026-11-03/04 (Sydney). **Branch:** `final-showcase`. **Production:** `dde7e22` (image `d40199ef…`), unchanged.
**Cost:** US$0. Nothing deployed, no budget opened, no arming, no ceiling change, no production settlement, no paid call, no change to the programme ledger.
**Owner decisions implemented (2026-11-03):**
1. The ceiling is scoped to legacy jobs, and budget jobs are bounded by their own budget, with a global safety control.
2. Budget `ar-a20-2026-11`: A$20 at 1.50, integer units, conservative rounding, atomic limits.
3. Off-host spending goes through allocations reserved before use and settled afterwards from a verified ledger.
4. Programme entries carry an explicit job identity with robust duplicate detection; the c04 append is prepared only.
5. The copied-ledger rule for Ironbark is implemented and tested, but nothing is settled in production.
6. Existing jobs and `larkspur-judge-1` stay under the A$50 programme.
7. The workspace distinguishes programme spend, the hosted ceiling and the budgets.

Plan: [budget-a20-plan.md](budget-a20-plan.md).

## 1. What changed

| Area | Change |
|---|---|
| `hosted/admission.py` | **Additive tables:**<br>• `budgets` (write-once: limit in µA$, rate as an integer ratio 3/2, limit in µUS$, attestation);<br>• `budget_jobs` (job → budget, primary key, written in the **same** `BEGIN IMMEDIATE` as the reservation);<br>• `budget_allocations` and `allocation_settlements` (write-once, `ledger_sha256` UNIQUE);<br>• `global_caps` (append-only history).<br>**One check inside the transaction:**<br>• legacy jobs: legacy committed + new ≤ hosted ceiling;<br>• budget jobs: Σ `ceil(µUS$ × 3 / 2)` of the budget's committed jobs and allocations + new ≤ limit;<br>• **and** all commitments + new ≤ global cap.<br>`totals()` keeps its keys with the ceiling's (legacy) meaning and adds `all_*`, `global_*` and `budgets`; also `capacity_microusd(scope)` and `job_budget` |
| `hosted/budget.py` (new) | Owner commands, each at an interactive terminal with a typed confirmation:<br>• `open`: write-once; the global cap becomes previous cap (or ceiling) + this budget's limit in US$, rounded down;<br>• `allocate`: atomic budget + global check before any off-host request;<br>• `settle-allocation`: ledger-verified; one ledger is charged once and never if it settled a hosted job; open requests only at their bound;<br>• `status`: read-only.<br>Code constant `MAX_TOTAL_BUDGETS_MICRO_AUD = A$20`: no further budget without a reviewed release |
| `lifecycle/arming.py` | `hosted-arming-v2` with a required `budget`; the attestation names it ("charged to the separate budget …, not to the A$50 programme or the hosted ceiling"). v1 records serialise **exactly** as before (no `budget` key): `larkspur-judge-1` `71a26471…` and `larkspur-live-1` `3e1606cf…` still equal their launch claims and verify. `--budget` on prepare/arm (refuses if the budget is not open); summary shows `charged_to` and the capacity of its own scope |
| `hosted/stageb.py` | A launch reserves in its arming's scope (`budget=rec.budget` for v2) |
| `hosted/settlement.py` | **`fork-prefix-1`**: an Ironbark fork's ledger is assessed after its imported prefix only if all of these hold:<br>• the fork's own `fork.json` declares the source ledger;<br>• that source's sha256 is pinned in `RECORDED_SOURCES` (`90bbc68f…`, 126 lines, US$0.864825, recorded once as `ironbark-source`);<br>• the first 126 lines hash to exactly it;<br>• the remainder is a complete ledger by itself.<br>No file is changed; one differing byte refuses. The audit carries `budget`; `programme_view` delegates to `programme.py` |
| `hosted/programme.py` (new) | Explicit identity: `hosted_job`/`hosted_jobs`, plus an explicit map for the three earlier hosted entries; **no text matching**.<br>`check` flags duplicate ids, a job recorded twice, a job in a budget, an entry of another budget, an identity mismatch, and an entry that names a job id without declaring it.<br>`view` gives programme spend = ledger + verified legacy hosted costs not yet recorded; held = unverified legacy reservations; worst = spend + held + the ceiling's available.<br>`propose` writes a proposal only. `append` (owner terminal) **inserts the entry as text, keeping every existing byte** (the ledger is partly hand-formatted), and is verified to parse to the old document + the entry |
| `hosted/api.py`, `ceiling.py`, `serve.py` | `spending`: the ceiling's scope (unchanged keys) + `global` + `budgets[]` + `charged_to` + `programme` (cached 30 s; the image ships the programme ledger read-only at `/app/budget/programme-ledger.json`). History rows carry `budget`. `ceiling status` labels its figures "programme/legacy jobs only" when budget jobs exist. The startup log adds each budget and the global cap |
| Dashboard | "Spending & capacity" has four labelled sections:<br>• **A$50 programme · actual expenditure**;<br>• **Hosted admission ceiling · a safety cap for programme runs, not spending**;<br>• **Separately allocated budgets**;<br>• **Live runs** (authorised launches, what they are charged to, how many their scope covers).<br>The ceiling is never called a budget. History Cost shows "programme" or the budget id |
| `deploy/Dockerfile` | `COPY collaboration/budget/programme-ledger.json` (read-only display) and `AR_PROGRAMME_LEDGER`. No compose, secret or `.env` change |

## 2. Tests (zero cost)

| Check | Result |
|---|---|
| `tests/test_budget.py` (new, 19; added to `scripts/critical-tests.sh`) | **Opening the budget:**<br>• typed, write-once, global cap +13 333 333 µUS$;<br>• a second budget is refused (reviewed maximum).<br>**Limits and rounding:**<br>• integer µA$ rounded up;<br>• the limit is exact: 13 333 333 µUS$ = A$20 admitted, +1 µUS$ refused.<br>**Isolation:**<br>• historical/programme jobs never change the budget, and budget jobs never change the ceiling's figures;<br>• settling a programme run leaves the budget unchanged.<br>**Settlement and held reservations:**<br>• settlement moves a budget job from held to spent (A$0.947628) and releases the rest once;<br>• running, interrupted and failed budget jobs keep their full reservation; owner recovery commits at the bound.<br>**Global cap:** binds even after a later ceiling increase.<br>**Concurrency:**<br>• 10 concurrent A$3 allocations on separate connections: exactly 6 admitted (A$18), 4 refused;<br>• 8 concurrent launches mixing scopes: exactly 1 admitted, every limit held.<br>**Allocations:**<br>• held before use, settle once and idempotently;<br>• a reused ledger is refused, whether from an allocation or a hosted job;<br>• open requests are refused unless committed at their bound; over-maximum is refused;<br>• an injected crash leaves no partial row and the retry settles.<br>**Rollback, read-only, terminal:**<br>• older-image accounting is more conservative;<br>• a job can be in at most one budget;<br>• `status` is read-only; changes need a terminal.<br>**Programme ledger:** identity and duplicate detection on the real ledger.<br>**Production copies:**<br>• **Ironbark rule:** US$1.090968 / US$1.126097 eligible (= `hosted-live-1`/`-2`), release US$1.082935 on settlement, never automatic, no file changed;<br>• **Ironbark refusals:** one changed byte → `fork_prefix_mismatch`, an unpinned source → `fork_source_unrecorded`, a remainder touching an imported request → refused;<br>• **Judge launches:** `larkspur-judge-1` launches stay programme jobs and opening the budget leaves the programme capacity at US$10.588249; a v2 arming (`larkspur-core@v3`, Original vs Improved) verifies, is charged to the budget, admits exactly 3 (A$20 / A$5.61) and leaves the programme scope untouched;<br>• **Programme view:** A$29.13 spent, A$45.01 worst case, before and after the c04 settlement (a verified ledger counts, never the reservation); the c04 proposal appended changes nothing (no double count) and a second append is refused;<br>• **API:** separate blocks |
| Hosted/admission/ceiling/API/service/Stage B/lifecycle/M9/presentation/Larkspur/evalruns set | 230 passed |
| `scripts/critical-tests.sh` | 252 passed |
| `scripts/dev-tests.sh` | 1 732 passed, 2 failed (the known Task-015 ledger-total tests; unchanged) |
| `tests/test_showcase_judge_browser.py` (alone) | 1 passed: the existing judge path end to end, 6 jailed trials, automatic settlement |
| `scripts/m9/judge_paid_path_rehearsal.py` (three tasks, Original vs Improved, network blocked) | exit 0: launches reserve before sending, are blocked, void, halt; reservations kept; pool 1 left; the judge code in no file |
| **Rollback, real code:** `dde7e22` (the current production image) on a copy with c04 settled, the budget open, a budget job and an allocation | Starts (`.env` 21.956 = DB). Counts the budget job against the ceiling: available US$6.848 instead of US$10.588, so it admits **1** judge launch instead of 2 (more conservative). Changes no settlement, budget, allocation or cap row. Cannot launch under a v2 arming (its model accepts only `hosted-arming-v1`, extra fields forbidden). Back on the new code, the budget figures are intact and the old image's launch is a programme job |
| Dashboard vitest / build | 221 passed / CHECK PASSED |
| Production, read-only | Current `admission.sqlite` copied read-only (sha256 `6868bc95…` = production). New code on it: programme spend US$19.418057 = **A$29.13** (c04 counted once, from its settlement), held 0, the ceiling's available US$10.588249, worst case **A$45.01**, ledger problems none; `budget status`: none open, no global cap; database byte-identical afterwards |

Not run: the 33-minute CI suite.

## 3. Capacity

| Scope | Spent (actual) | Held | Available |
|---|---|---|---|
| **New budget `ar-a20-2026-11`** (after `open`) | A$0 | A$0 | **A$20.00** (US$13.333333): 3 launches of the current option (US$3.740 = A$5.61 each, A$3.17 left) |
| **A$50 programme** | US$19.418057 = **A$29.13** | US$0 unverified | worst case A$45.01 (the hosted ceiling's US$10.588249); authorised by `larkspur-judge-1`: 2 × US$3.740 → A$40.35 |
| **Hosted ceiling** (programme jobs, safety cap) | US$0.631751 settled | US$10.736 (e529, Ironbark) | US$10.588249 of US$21.956 |
| **Global cap** (after `open`) | – | – | US$35.289333 over every commitment (today US$11.367751) |

Optional, separately approved: settling Ironbark under `fork-prefix-1` releases US$1.082935 of the ceiling. The programme ledger already holds both amounts. The programme worst case becomes A$46.63.

## 4. Deployment and migration plan (each step needs owner approval)

**A. Deploy** the release commit (this branch's HEAD after this report), exactly as [hosted-settlement.md](hosted-settlement.md) §6.2:
- read-only preflight against the expected state:
  - `admission.sqlite` with 1 settlement;
  - ceiling 21.956 / reserved 14.476;
  - `larkspur-judge-1` 2 left;
  - worker idle;
- backup and manifest;
- clean-worktree build;
- disabled smoke test on a volume copy;
- tag `rollback-dde7e22`;
- switch.

The image creates the five empty tables; it opens no budget and changes nothing else.

Verify:
- `/api/ironbark/config` `spending.budgets == []`, `global == null`, `available` 10.588249, `programme.spent_aud` 29.13 / `worst_case_aud` 45.01;
- `ceiling status` and `arming status` unchanged (2 left, problems []);
- `budget status` "none open";
- evidence files byte-identical (only `admission.sqlite` changes: the new empty tables).

No compose, secret, `.env` or ceiling change.

**B. Open the budget** (owner terminal; separately approved; app running or stopped, either is safe):
```sh
cd /root/agent-readiness/deploy
T=$(date -u +%Y%m%dT%H%M%SZ); docker run --rm -v agent-readiness_data:/data:ro -v /root/backups:/out alpine cp /data/hosted/live/admission.sqlite /out/admission-pre-budget-$T.sqlite
docker compose exec -it app python -m agent_readiness.hosted.budget open --db /data/hosted/live/admission.sqlite --id ar-a20-2026-11 --limit-aud 20 --rate 1.50
#   prints "I am the owner and I open budget ar-a20-2026-11: limit A$20.000000 at 3/2 A$ per US$ (US$13.333333); it is separate from the A$50
#   programme and all historical spending; the global hosted cap becomes US$35.289333"  -> type it exactly
docker compose exec app python -m agent_readiness.hosted.budget status --db /data/hosted/live/admission.sqlite
```
Expected: `ar-a20-2026-11` A$20.000000 available; global cap US$35.289333; the ceiling's scope unchanged (available US$10.588249); `larkspur-judge-1` 2 left, still charged to the programme.

**C. Use the budget** (each separately approved):
- **Hosted launches:** a new arming that names the budget. Prepare first, then you type the attestation:
  ```sh
  python -m agent_readiness.lifecycle.arming prepare --arming <id> --mode paid --frozen larkspur-core@v3 --variants original improved --repetitions 1 --launches <n> --budget ar-a20-2026-11
  ```
  **Note:** only one arming is active at a time, and there is no command to re-activate an earlier one (arming ids are write-once). Arming a budget pool therefore ends `larkspur-judge-1`'s **2 remaining programme launches**. Use them first, or decide to forgo them. Their records and claims stay as written.
- **Off-host work:**
  - before it starts: `budget allocate --budget ar-a20-2026-11 --ref <ref> --max-usd <max> --purpose "<what>"`;
  - the local run's experiment cap must be ≤ the allocation;
  - afterwards: copy its ledger to the VM and run `budget settle-allocation --ref <ref> --ledger <file> --expect-settled <amount>`.

**D. Programme ledger (separately confirmed):**
- **c04:** the proposal is [collaboration/budget/proposals/c04-ledger-append.json](../budget/proposals/c04-ledger-append.json): `hosted-stageb-judge-1`, US$0.631751, `hosted_job` c04, from the production settlement (ledger `243deaca…`, 45/45).
  1. Fill `authorized_by`/`recorded_on`.
  2. Run `python -m agent_readiness.hosted.programme append --ledger collaboration/budget/programme-ledger.json --proposal …` (owner terminal).
  3. Commit.

  Known spend becomes US$19.418057; programme spend to date stays US$19.418057 (no double count).
- **Ironbark (optional):** `settlement apply` for each job with `--expect-settled 1.090968` / `1.126097` (owner terminal, after `audit` shows `fork-prefix-1`).

**Rollback:**
- **Image:** `docker tag agent-readiness-app:rollback-dde7e22 agent-readiness-app:latest && docker compose up -d --no-build --no-deps app`.
- **What the older image does:**
  - it ignores the five tables;
  - it counts budget jobs against the ceiling (more conservative);
  - it cannot launch under a v2 arming (`active()` is None for it, so the workspace shows "not armed");
  - it never changes budget rows.
- **Data:** rows are additive and never deleted in normal operation. To undo opening the budget entirely, stop the app and restore `admission-pre-budget-<T>.sqlite`. That backup predates any budget job, so restore only if none was admitted.

## 5. Limits
- **Off-host allocations are an accounting control:** the hosted service cannot stop a local process from sending. The local run's own experiment cap (reserve-before-send) must be set ≤ the allocation, and its ledger is verified at settlement.
- **The programme figures in the workspace are a snapshot:** they come from the programme ledger shipped with the image and are updated by a deploy. Hosted runs are matched by identity, so a settled run not yet appended still counts exactly once.
- **The global cap is not raised by a later ceiling migration.** That only makes programme admission stricter, and a reviewed change is needed to re-base it.
