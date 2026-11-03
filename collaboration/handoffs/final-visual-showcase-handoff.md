# Handoff: final visual showcase phase (2026-11-04 Sydney)

**Start here.** This supersedes [final-showcase-handoff.md](final-showcase-handoff.md) for current state. Verify everything below against the repository and production before you rely on it.
- **Deadline:** **Thursday 2026-11-05 13:00 AEDT** (Meta Global AI Hackathon). A video **and** a functioning live product are both mandatory.
- **Branch:** `final-showcase`, unmerged into `main` (merging needs owner approval).
- **Handoff written at:** HEAD `dc6b9e3`, plus this document's commit.
- **Read before changing anything:** `AGENTS.md` (rules), this document, then [evaluation-launch-final.md](../reports/evaluation-launch-final.md) (launch model, audit, deploy procedure and records §5, §8, §8.1).

Legend: **DEPLOYED** = live on production now. **PLANNED** = not built or not deployed.

---

## 1. Current production state (DEPLOYED; verified 2026-11-03 21:15–21:20 UTC)

| Item | Value |
|---|---|
| URL | https://209-38-84-72.sslip.io (DigitalOcean droplet `209.38.84.72`, Sydney; Caddy TLS in front of the app container) |
| Public routes | `#/` Home · `#/demo` = `#/lifecycle` (the Larkspur journey, 8 steps) · `#/run` Workspace (`#/run/eval-…` a run) · `#/reports/eval-…` report page · `#/demo/ironbark` archive (earlier Ironbark scroll story + pre-redesign app) |
| Deployed commit | **`fdc3f43`** (journey hotfix) on top of **`9ac4485`** (unified launch + A$20 budget + explicit soft cap + approved-pair selection) |
| Image | `agent-readiness-app:hotfix-fdc3f43` = `latest` = **`sha256:a2a3792a35f361a39f72d1bceac262e1a3dbecf6ce876e1f1566f4dd0ee4cd36`**; bundle `index-u2vtLsz6.js` |
| Rollback images | • `rollback-9ac4485` = `1545dd81…`: budget-aware, but **has the journey crash** (blank `#/demo`/`#/lifecycle` while a budget is open).<br>• `rollback-dde7e22` = `d40199ef…`: pre-budget; ignores the budget, and launches return to the judge arming `larkspur-judge-1` (2 left). Rotate the operator token first (§6.7).<br>• Older: `rollback-83be351`, `rollback-f36db53`, … |
| A$20 shared budget | **OPEN**: `ar-a20-2026-11`, limit A$20.000000 at 1.50 A$/US$ (US$13.333333). Spent A$0, outstanding A$0, available A$20.00, 0 jobs (no evaluation has run on it yet) |
| Global cap | **US$39.029333** = hosted ceiling 21.956 + budget 13.333333 + one run's maximum 3.740. All commitments US$11.367751 (historical) |
| Selected evaluation | `ar-a20-2026-11` (recorded at opening): frozen **`larkspur-core@v3`** (`db2eb1cb…`), **Original vs Improved**, 3 tasks × 2 versions = 6 jailed trials, at most US$3.740 (A$5.61) per run, no launch count |
| Access | One flow for everyone: a valid access code + Run. The judge code is `deploy/secrets/judge_token` on the VM (40 characters; never print or commit it). The operator token also works identically. No operator sessions |
| Hosted ceiling (historical scope only) | US$21.956; reserved 14.476 by 4 historical jobs; settled US$0.631751 (c04); outstanding US$10.736 (e529 + 2 Ironbark); available US$10.588249 (no new launch can use it while the budget is open) |
| A$50 programme | Spend to date US$19.418057 = **A$29.13** (ledger 21 entries US$18.786306 + c04 US$0.631751, verified but not yet appended); worst case A$45.01 |
| `larkspur-judge-1` | Still the `armings/ACTIVE` pointer and still valid (record `71a26471…`, 1 of 3 used, 2 left), but **not consulted** while the budget is open. Unchanged |
| Latest verification | • Public API **19/19**.<br>• Evidence 2 422 files identical to the pre-hotfix backup.<br>• Judge code accepted on the unified path without launching (valid code + malformed `Idempotency-Key` → 422; wrong code → 403).<br>• Real browser, fresh profile per page, GET only: `#/demo`, `#/lifecycle`, `#/`, `#/run`, both reports, archive; 0 errors.<br>Details: [evaluation-launch-final.md §8, §8.1](../reports/evaluation-launch-final.md) |
| Backups on the VM (`/root/backups/`) | `predeploy-final-20261103T210207Z.tgz` (+ `.sha256` manifest; before `9ac4485`) · `admission-pre-budget-20261103T210639Z.sqlite` + `stage-b-pre-budget-…tgz` (before opening) · `predeploy-hotfix-20261103T211503Z.tgz` (latest, before `fdc3f43`) · earlier `predeploy-*`. Deployment log: `/root/agent-readiness/deploy/DEPLOYED.txt` |

---

## 2. Architecture and code locations

| Layer | What | Where |
|---|---|---|
| Frontend | React 19 + TypeScript + Vite SPA, hash routing. One showcase data source: `site/showcase.ts` (`LIVE` = featured run `eval-c04…`, `FIRST_LIVE` = `eval-e529…`, `FEATURED_TASK`, `PAGE_AUDIT`) reading `site/showcase/larkspur.json` + `site/showcase/frames/` | `dashboard/src/App.tsx`, `site/router.ts`, `site/Shell.tsx`, `site/Home.tsx`, `site/LatestLive.tsx`, `site/lifecycle/` (journey `Lifecycle.tsx`, `Report.tsx`, `Trace.tsx`, `parts.tsx`), `site/workspace/` (`HostedEvaluation.tsx` = the Workspace, launch, budget panel; `History.tsx`), `site/demo/` (`Demo.tsx`, `Journey.tsx`, `engine.tsx`: the scroll-driven engine of the archived Ironbark story), CSS `site/*.css`, `site/workspace/workspace.css`, `lib/lifecycleApi.ts` (API types). Tests `*.test.tsx` (vitest, jsdom) |
| Backend API | FastAPI app, one process, `uvicorn` on :8080 behind Caddy | `src/agent_readiness/hosted/api.py` (routes: `/api/health`, `/api/ironbark/config`, `/api/ironbark/jobs` [POST launch], `/api/ironbark/jobs/{id}` status (+ `accounting`), `/live`, trials, screenshots, export; `/api/lifecycle/*`), `hosted/serve.py` (startup, env, fail-closed checks) |
| Launch and admission | Valid code → `StageBExecutor.admit(charge="budget")` → `Admission.reserve_amount` (one `BEGIN IMMEDIATE`: slot, budget soft cap, global cap; assignment `budget_jobs`) → `arming.pool_launch` (claim `<budget>-l<N>`, PaidAuthorization, ledger dir) | `hosted/stageb.py`, `hosted/admission.py`, `hosted/budget.py` (budget, allocations, evaluations: owner CLI), `lifecycle/arming.py` (judge armings v1 + `BudgetPool` = budget evaluations) |
| Settlement and accounting | Auto-settles a finished job at its ledger-verified cost; owner `settlement apply` for others; copied-ledger rule `fork-prefix-1` (Ironbark); programme ledger identity | `hosted/settlement.py`, `hosted/programme.py`, `hosted/ceiling.py` |
| Worker | Subprocess per job: re-checks the launch claim (`arming.check_launch`), then runs Stage B trials in the browser jail with per-request reserve-before-send | `lifecycle/jobs.py`, `evalruns/runner.py`, `evalruns/authorization.py`, `hosted/jail.py`, `deploy/jail-policy.json` |
| Evaluation pipeline (lifecycle) | Site → Stage A task generation (paid; NOT on the launch path) → owner review/approve/freeze (`suites/stage_a/approval.py`: revise, decide, freeze) → manifest → Stage B runs → projection (report) → diagnostics | `lifecycle/` (`service.py`, `projection.py`, `audit.py` leak audit, `sites.py`), `suites/` (write-once store), `evalruns/manifest.py`, `diagnostics/run.py`, `grading/` (v1 official, v2 post-hoc) |
| Website snapshots | Deterministic, content-hashed renders of the fictional sites, served to agents from a frozen mirror. Larkspur: `data.py` (records/oracle), `render.py` (`VARIANTS`, `snapshot(variant)`), `improved.py` (Improved: browse pages, filter form results, `/courses/compare`, JSON-LD, redirects). Registration: `framework/site.py` `SITES["larkspur"]` (`variants=("original","modified")`, `releases=("improved",)`) | `src/agent_readiness/sites/larkspur/`, `src/agent_readiness/framework/site.py` |
| Report and replay | Report = `lifecycle/projection.py` output (cached under `stageb/derived/*.projection-1+equivalent-page-1.json`), audited before publication; UI `site/lifecycle/Report.tsx`, trace replay `Trace.tsx`, Workspace grid; per-trial screenshots served from run artefacts | backend `hosted/api.py`, `lifecycle/service.py` |
| Deploy | `deploy/Dockerfile` (builds dashboard, installs package, copies `datasets/`, `collaboration/budget/programme-ledger.json`), `deploy/compose.yaml` (app + caddy, secrets), `deploy/Caddyfile`, `deploy/DEPLOY.md` | VM: `/root/agent-readiness/deploy/` (`.env`, `secrets/`, `DEPLOYED.txt`), data volume `agent-readiness_data` → `/data/hosted` |
| Production data layout | `/data/hosted/live/admission.sqlite` (jobs, policy, settlements, budgets…), `live/stageb/jobs/*.json` + runs, `lifecycle/store/` (write-once suites, approvals, manifests), `lifecycle/stage-b/` (`armings/`, `launches/`, `authorizations/`, `ledgers/`, `budget-pools/`), `live/launch-requests.sqlite` (idempotency, created on first keyed launch) | — |

---

## 3. Immutable evidence (never modify, re-generate or "clean up")

**Website snapshots** (sha256, pinned in `tests/test_larkspur_improved.py`):
- `larkspur@original` `2f9fd2ce09a044547ceb728acb9b85108931d81ca6b01374198144f509fed2eb`
- `larkspur@modified` `edb9a5d2884a0e85fff8f9dfc6ed0e8a4bed41f9616e82678fc466864befe69f`
- `larkspur@improved` `87e715d59c2376f82b23f33007496edf193812eb574a65a8629109bbe35e63b5`

Any change to `sites/larkspur/data.py`, `render.py` or `improved.py` that alters these is forbidden. A new version must be a **new** variant (see §5).

**Frozen suites:**
- **`larkspur-core@v3`:** frozen `db2eb1cb64eb62448ded0168d849f8a0dad8ab6f2796db4aa4bacbe25a6fb045` → suite `0e46a1efe0a628ff2fb69c72ce0c0eb2323919570e4e3fbde1ac296d93460360`, owner approval `59c866ba56c6…`.
  - Tasks: `gen-23f1802ee0-n` (fee ≤ $250, ≥ 5 seats), `gen-8334922e62-n` (weekend, Beginner), `gen-f302fa8fe2-n` (fee ≤ $180, ≤ 6 weeks).
  - Judge manifest (Original vs Improved): `c32cfc6fa1a0…`.
- **`larkspur-core@v2`:** frozen `0816af7f7440…`, manifest `64a55c5f3a93…` (the M7 dataset and `eval-e529`).

**Genuine paid evaluations:**

| Job | What | Result | Settled cost |
|---|---|---|---|
| `eval-c04fdb100d6b1c877de96dabe76eb052` (featured) | v3, Original vs Improved | Original 0/3 correct, 39 requests, 262 s; **Improved 3/3 correct, 6 requests, 54 s** | **US$0.631751** (ledger `larkspur-judge-1-l1` `b5b1b4d0…`) |
| `eval-e529db2aafecbfddd21e5c571eb85243` (first live) | v2, Original vs Modified, 12 trials | — | US$1.546226 (`larkspur-live-1-l1` `e4675700…`); the record says "failed"; kept as written |
| `eval-9aaac35c…`, `eval-aa23e330…` (Ironbark, retired engine) | — | — | forked ledgers; own increments US$1.090968 / US$1.126097 |

Local read-only copies (git-ignored): `scanner-data/hosted-copy-fs/` (production after c04; admission `280fb9ef…`; **do not modify; tests compare its hash**), `scanner-data/hosted-copy-m9/`.

**Never modify:**
- historical job records, ledgers, launch claims, authorisations, `armings/*.json`, `budget-pools/*.json`;
- `admission.sqlite` rows: settlements and budgets are write-once; never edit by hand;
- the write-once lifecycle store;
- `collaboration/budget/programme-ledger.json` (append only, owner-approved, via `hosted.programme append`);
- `datasets/lifecycle/m7-larkspur-browser-1`;
- `dashboard/src/fixtures/live/eval-c04fdb10-*.json`, `dashboard/src/site/showcase/` exports (regenerate only via the export script and only for a new run);
- historical Task 005–007 code, config and data, frozen manifests, pilot artefacts, earlier reports' recorded numbers;
- the owner's untracked files `src/agent_readiness/investigate/prototype/` and `tests/test_termvalue_prototype.py` (never stage, move or delete).

---

## 4. Spending and security (DEPLOYED behaviour)

- **Launch authorisation, exactly two conditions:**
  1. a valid access code (Bearer header, held in page memory only);
  2. the shared budget's commitments below A$20: settled actual costs **plus the full reservation (A$5.61) of any run not yet reconciled**.

  A launch's own worst case is **not** compared with what remains (soft cap), so the last run may finish above A$20, by at most one run (A$5.61). The hard total stays ≤ A$25.61; the global cap US$39.029333 bounds everything and provably never refuses an under-budget launch. The Workspace states this explicitly.
- **Execution protections (not authorisation):**
  - **One run at a time:** a second launch → **409** "An evaluation is already running…", and the page opens the running evaluation.
  - **Duplicates:** a per-click `Idempotency-Key` returns the same run on double-click or retry.
  - **Invalid codes:** limited (10 per 10 min per address; a valid code always passes).
  - **Per-run limits:** per-request cap US$0.044, per-trial request limits, hard cap US$3.696 per run in the manifest and paid authorisation.
- **Settlement:**
  - A finished job settles automatically at its verified ledger cost and releases the rest.
  - A failed or interrupted run without a verifiable ledger **keeps its full reservation** until the owner reconciles it (`settlement audit` then `settlement apply --allow-open-requests`, owner terminal).
  - Historical jobs never count against the A$20 budget.
- **Historical accounting:**
  - **A$50 programme:** separate and unchanged. c04 is verified, but its append proposal is in `collaboration/budget/proposals/c04-ledger-append.json` and **not applied**.
  - **Historical holds:** e529 and the Ironbark holds remain on the old ceiling. Ironbark is settleable under `fork-prefix-1`; e529 is eligible. Neither is settled.
- **Secrets:**
  - `META_MODEL_API_KEY`, `.env`, `deploy/secrets/*`: never print, log or commit.
  - The judge and operator codes must never appear in responses, URLs, logs or files (tests enforce this).
- **Owner approval is required for:**
  - any deploy or rollback;
  - any paid evaluation (including the first run on the budget and the Polished run);
  - recording or selecting a budget evaluation (`budget evaluation-add` / `evaluation-use`: owner types at the terminal);
  - settlements, ceiling migrations, armings;
  - programme-ledger appends;
  - secret rotation;
  - merging to `main`;
  - pushing to non-`final-showcase` branches if unsure.

  The interactive owner gates (`budget open`, `evaluation-add`, `evaluation-use`, `settlement apply`, `ceiling migrate`, `arming arm`, `approval decide`) are typed by the owner. Never script around them; prepare a guarded wrapper (as `/root/open-budget.sh`) that the owner runs with `ssh -t`.

---

## 5. Next phase (PLANNED; nothing below exists yet)

Priorities, in deadline order:
1. **Polished Larkspur as a NEW immutable snapshot (`larkspur@polished`).**
   1. **Implement** `src/agent_readiness/sites/larkspur/polished.py`, modelled on `improved.py`: deterministic render from `data.py`, every page captured, links resolve inside the snapshot, form results and redirects captured.
   2. **Register** it: add `"polished"` to `render.VARIANTS` and to `SITES["larkspur"].releases` in `framework/site.py`. **Do not alter** original/modified/improved.
   3. **Test** like `tests/test_larkspur_improved.py`:
      - pin the new sha256;
      - assert the other three are unchanged;
      - check links and captures, oracle consistency (the deciding facts must match `data.py`), and that the three v3 tasks still have the same correct answers on Polished (the runner re-checks this: a changed answer sets the task aside);
      - check `lifecycle/projection.equivalent_pages` behaviour if it has a comparison table.
   4. **Deploy** it (image-only, §6.6).
   5. **Record and select (owner, terminal):**
      ```
      docker compose exec -it app python -m agent_readiness.hosted.budget evaluation-add --db /data/hosted/live/admission.sqlite --budget ar-a20-2026-11 --id ar-a20-polished --frozen larkspur-core@v3 --variants original polished
      ```
      then `budget evaluation-use --budget ar-a20-2026-11 --id ar-a20-polished`. Its per-run maximum must be ≤ US$3.740; the same 3 tasks × 2 versions give exactly that. Tested in `tests/test_budget.py::test_the_owner_can_switch_the_budget_to_another_approved_immutable_pair` (with `modified`).
   6. **Run:** the paid run of Original vs Polished needs separate owner approval. Judges then run it from the Workspace.
2. **Cinematic scroll-driven demo.** The Ironbark story's scroll engine is in `dashboard/src/site/demo/` (`engine.tsx`, `Demo.tsx`, `Journey.tsx`, `demo.css`), archived at `#/demo/ironbark`. The featured Larkspur journey is `site/lifecycle/Lifecycle.tsx` (`#/demo` = `#/lifecycle`).
   - **Data:** use only recorded evidence (`showcase.ts`/`larkspur.json`, frames exported by `scripts/showcase/export_larkspur_showcase.py`).
   - **Keep:** strict CSP (`default-src 'self'`, no inline script or eval), `prefers-reduced-motion`, and the `[data-reveal]` pattern.
3. **Visual consistency** across Home (`Home.tsx`, `home.css`, `LatestLive.tsx`), Workspace (`workspace/*`) and Journey (`lifecycle/*`). Known cosmetic: the Workspace history table scrolls horizontally at 1 440 px (Cost column).
4. **Final evaluation:** the first budget-funded paid run(s) (owner approval). After a new featured run, regenerate the showcase data with the export script and update `LIVE` in `showcase.ts` (keep the c04 record as history).
5. **Video:** record the judge flow (code → Run → progress → report) and the journey on production. Never show secrets.
6. **Submission:** Thursday 2026-11-05 13:00 AEDT.

---

## 6. Operational instructions

### 6.1 Build and test (zero cost; loopback only; never a paid call)

```sh
cd /home/vaibhav/Projects/Hack_Agent_Readiness            # uv venv in .venv; never commit uv.lock; never `git add -A`
uv run pytest -q -x tests/<affected>.py                    # first: the tests that exercise your change
scripts/critical-tests.sh                                  # ~75 s; 262 pass (includes test_settlement, test_budget, test_unified_launch)
scripts/dev-tests.sh                                       # ~7 min; 1 742 pass + 2 KNOWN failures (§7)
cd dashboard && npx tsc --noEmit -p . && npx vitest run && npm run build   # 224 pass; build ends "CHECK PASSED"
# Browser e2e (run ALONE, after `npm run build`; they serve dashboard/dist):
uv run pytest -q tests/test_judge_experience_browser.py -m "browser or slow or not browser"   # ~10 min; full judge path in a real browser
uv run pytest -q tests/test_showcase_judge_browser.py -m "browser or slow or not browser"     # ~4 min
uv run pytest -q tests/test_larkspur_improved.py                                             # snapshot pins
```
- Paid-path rehearsal with the network blocked: `scripts/m9/judge_paid_path_rehearsal.py` (docstring has the exact invocation with `M9_NO_NETWORK=1`).
- Never run browser tests or builds concurrently.

### 6.2 Run locally (view-only, real backend + built frontend, no launches)

Use a **copy** of the production data (the service adds tables to the database it opens):
```sh
D=$(mktemp -d) && cp -r scanner-data/hosted-copy-fs/data/hosted $D/hosted
AR_HOSTED_MODE=disabled AR_HOSTED_CEILING_USD=21.956 AR_HOSTED_DATA=$D/hosted AR_STATIC_DIR=$PWD/dashboard/dist \
  AR_LIFECYCLE_DATASETS=$PWD/datasets/lifecycle AR_PORT=18090 uv run python -m agent_readiness.hosted.serve
# open http://127.0.0.1:18090/#/  (verified 2026-11-04)
```
To run evaluations locally (zero cost: real jailed Chromium, scripted dev provider), follow `tests/test_judge_experience_browser.py`. It builds a rehearsal budget on a store copy and serves the app with uvicorn. Frontend-only iteration: `cd dashboard && npm run dev` (API calls need the backend).

### 6.3 Inspect in a real browser

Use Playwright (`uv run python`, `playwright.sync_api`).
- **CSP:** the site's CSP blocks string-evaluating waits (`wait_for_function("...")`). Use locator assertions (`expect(locator).to_contain_text(...)`).
- **Fresh context per page:** a crash on one route otherwise masks the next.
- **What to collect:** `pageerror` and console errors, and fail on any non-GET request when checking production.
- **Render every route after any production state change** (the journey crash was missed because only the Workspace was rendered with the budget open).

### 6.4 Inspect production (read-only)

- **SSH:** `SSH_AUTH_SOCK=~/.ssh/readiness-agent.sock ssh root@209.38.84.72`. The agent key expires: ask the owner to run `! SSH_AUTH_SOCK=~/.ssh/readiness-agent.sock ssh-add ~/.ssh/readiness_key_new`.
- **Never let `docker compose exec` consume a piped script's stdin:** add `</dev/null` to each exec inside `bash -s` scripts.
- **Useful commands** (in `/root/agent-readiness/deploy`):
  ```sh
  docker compose exec -T app python -m agent_readiness.hosted.budget status --db /data/hosted/live/admission.sqlite </dev/null
  docker compose exec -T app python -m agent_readiness.hosted.ceiling status --db /data/hosted/live/admission.sqlite </dev/null
  docker compose exec -T app python -m agent_readiness.lifecycle.arming status </dev/null
  curl -s https://209-38-84-72.sslip.io/api/ironbark/config | python3 -m json.tool
  ```
- **Judge-code check without launching:** POST with the code (read from `secrets/judge_token` into a tmpfs header file, never printed) and `idempotency-key: x` → 422 means the code is valid. This is in [evaluation-launch-final.md §8](../reports/evaluation-launch-final.md).

### 6.5 Register or switch an approved evaluation pair

See §5 step 1:
- only registered (code-shipped, content-hashed) versions;
- only an owner-approved frozen suite;
- per-run maximum ≤ US$3.740;
- owner-typed `evaluation-add` then `evaluation-use`;
- `budget status` lists the evaluations and the selected one.

A new task suite goes through the owner flow (revise → decide → freeze; `suites/stage_a/approval.py`), never task generation on the launch path.

### 6.6 Deploy safely (owner approval each time)

Follow [evaluation-launch-final.md §5 A0–A5](../reports/evaluation-launch-final.md) (§8.1 is the hotfix record, the model for small releases):
1. **A0:** read-only pre-flight against the expected state; stop on any difference.
2. **A1:** verified backup tar + sha256 manifest + `.env`/compose copies.
3. **A2:** clean-worktree build; `compose.yaml` must be identical.
4. **A3:** read-only checks with the new image + disabled smoke test on a **volume copy** (loopback port).
5. **A4:** confirm the worker is idle; tag `rollback-<current>`; `docker compose up -d --no-build --no-deps app`.
6. **A5:**
   - public checks: budget open, cap, selected pair, programme unchanged, invalid codes 403;
   - evidence manifest diff;
   - judge-code check without launching;
   - real-browser check of **every** route.

Verify the release diff first (`git diff --stat <deployed> <new> -- . ':!collaboration' ':!STATUS.md'`). Record in `deploy/DEPLOYED.txt` and a report.

### 6.7 Roll back

- **Image:**
  ```sh
  docker tag agent-readiness-app:rollback-<x> agent-readiness-app:latest && docker compose up -d --no-build --no-deps app
  ```
  Use `rollback-9ac4485` only if the journey crash is acceptable. Prefer re-deploying a fixed commit.
- **To pre-budget `rollback-dde7e22`:** first rotate `secrets/operator_token` (procedure in [budget-a20-deployment.md §4](../reports/budget-a20-deployment.md)). Launches revert to `larkspur-judge-1` (2 left, the old ceiling / A$50 programme).
- **Data:** restore the matching `/root/backups/` file with the app stopped. Undo the budget opening only before any budget run (`admission-pre-budget-*.sqlite` + `stage-b-pre-budget-*.tgz`).

---

## 7. Risks, known issues and priorities

- **Known test failures (pre-existing, unchanged):** `tests/test_remediation.py::test_budget_is_tracked_in_aud_with_original_usd_records_and_a_documented_rate` and `tests/test_remediation_main_design.py::test_programme_ledger_records_the_pilot_and_does_not_count_it_twice` (Task-015 ledger totals). The 33-minute CI suite was not run for these releases.
- **Budget pitfalls:**
  - A failed or interrupted run without a verifiable ledger holds A$5.61 until reconciled; 3–4 such runs could exhaust the pool early.
  - The budget has no close operation.
  - `budget evaluation-use` affects the next launch immediately: coordinate with the owner and don't switch during judging without approval.
- **Production pitfalls:**
  - The SSH agent key expires mid-session.
  - `.env` `AR_HOSTED_CEILING_USD` must equal the database ceiling, or evaluations are disabled for everyone.
  - Rebuild `dashboard/dist` before browser tests.
  - Docker on the VM warns that the volume "was not created by Docker Compose": harmless.
  - The worker must be idle before any switch.
- **Rollback limitation:** no budget-aware rollback image without the journey crash exists. After the next good release, its predecessor tag becomes the rollback.
- **Pending owner decisions:**
  - append c04 to the programme ledger;
  - optional Ironbark settlements (fork-prefix) and e529 (only with a lower ceiling, see [hosted-settlement.md §2](../reports/hosted-settlement.md));
  - the first paid budget run;
  - Polished.
- **Cosmetic:** history table horizontal scroll; the history "Passed" column uses the exact-match grade (c04 shows 0% → 0% while Correct is 0/3 → 3/3).
- **Deadline priorities (about 29 hours from this handoff):**
  1. keep production working (any release: full §6.6 including every route in a browser);
  2. Polished snapshot + tests + deploy;
  3. visual and cinematic polish;
  4. owner-approved Original vs Polished run and showcase export;
  5. video;
  6. submission.

  Cut scope before risking the live product.

## 8. Key documents

- **Launch and budget model, audit, procedures, deployment records:** [evaluation-launch-final.md](../reports/evaluation-launch-final.md)
- **Budget design and history:** [budget-a20-plan.md](../reports/budget-a20-plan.md), [budget-a20-implementation.md](../reports/budget-a20-implementation.md) (partly superseded), [budget-a20-deployment.md](../reports/budget-a20-deployment.md) (rollback §4)
- **Settlement:** [hosted-settlement.md](../reports/hosted-settlement.md), [hosted-settlement-reconciliation.json](../reports/hosted-settlement-reconciliation.json)
- **Showcase and presentation:** [final-showcase-release.md](../reports/final-showcase-release.md), [final-showcase-three-task-suite.md](../reports/final-showcase-three-task-suite.md) (§8–10: v3 freeze, arming, first paid launch), [final-presentation-fix.md](../reports/final-presentation-fix.md)
- **Earlier milestones:** [m9-release-readiness.md](../reports/m9-release-readiness.md), [lifecycle-m8-product-integration.md](../reports/lifecycle-m8-product-integration.md), `docs/` (`FRAMEWORK.md`, `DIAGNOSTICS.md`, `CI.md`, `PROJECT.md`, `DECISIONS.md`), `deploy/DEPLOY.md`

**Commit IDs:**

| Commit | What |
|---|---|
| `fdc3f43` | Deployed journey hotfix |
| `9ac4485` | Release (unified launch, budget, soft-cap UI, pair selection) |
| `f9797cb` | Procedures |
| `b5618ba` | Deploy and opening record |
| `dc6b9e3` | Hotfix record |
| `42b04ba` | Unified flow |
| `dd89e97` / `f60fcbf` | Budget foundations |
| `dde7e22` | Settlement |
| `a3ad4cd` | Presentation fixes |
| `83be351` | Three-task suite |
