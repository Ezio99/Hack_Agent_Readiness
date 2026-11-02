# Handoff: M8, integrating the evaluation lifecycle (M2–M7) into the live Agent Readiness product

**Written:** 2026-11-03, at the end of the Claude Code (Opus) session that implemented lifecycle M2–M7.
**For:** a fresh Claude Code agent that will receive M8 implementation instructions separately.
**Branch at writing:** `research/llm-task-planning` @ `5b4d129` (pushed to `origin`). The commit that adds this file sits on top of it.

**Status of this document.** Nothing in it authorises spending, deployment, merging, approval or modification of evidence. Statements were verified against the checkout when written. **Where this document and the code disagree, the code wins.** Re-verify hashes before relying on them. `STATUS.md` remains the authoritative current-state record for the whole project.

---

## 0. Start here

1. **Read, in order:**
   1. this file;
   2. `AGENTS.md`. Its "Current state" paragraph is **stale**: it says production runs `product-experience-redesign` @ `b3121a8`. Production actually runs `evaluation-v2` @ `140a4e8`; see §2.
   3. `STATUS.md`;
   4. `collaboration/LIFECYCLE_HANDOFF.md` (top "UPDATE" block);
   5. `collaboration/proposals/two-stage-evaluation-lifecycle.md` (the approved design and its 8 owner decisions);
   6. the reports:
      - `collaboration/reports/lifecycle-m1.md`;
      - `collaboration/reports/lifecycle-m2-m5.md`;
      - `collaboration/reports/lifecycle-m6-stage-a.md`;
      - `collaboration/reports/lifecycle-m7-review-packet.md`;
      - `collaboration/reports/lifecycle-m7-browser.md`;
   7. `deploy/DEPLOY.md` (production, rollback, operations);
   8. `dashboard/PRODUCT_REDESIGN.md` (frontend routes and design).
2. **Verify the checkout:**
   ```bash
   cd ~/Projects/Hack_Agent_Readiness
   git fetch origin && git status -sb && git log --oneline -3
   git rev-parse research/llm-task-planning origin/research/llm-task-planning evaluation-v2 product-experience-redesign main
   ```
3. **Baseline tests** (all zero cost; tests never call a paid model):
   ```bash
   .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_suites_m1.py tests/test_taskeval.py tests/test_research_taskplan.py \
     tests/test_taskeval_v2.py tests/test_kinds_m2b.py tests/test_stage_a_loop.py tests/test_lifecycle_m4.py tests/test_evalruns_m5.py \
     tests/test_m6_stage_a_preflight.py tests/test_m7_paid_guard.py -m "not browser"        # expect 144 passed, 1 deselected
   bash scripts/critical-tests.sh                                                            # expect 214 passed, 17 deselected
   (cd dashboard && npx vitest run)                                                          # frontend; see §9 for the count at writing
   .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_evalruns_m5.py -m browser   # real Chromium + jail, zero cost; run ALONE
   ```
4. **Owner-only actions** (never automate or impersonate): suite approval and freezing, any paid call, deployment, merging, ceiling changes, public paid access.

---

## 1. Repository and branches

`origin` = `https://github.com/Ezio99/Hack_Agent_Readiness.git`.

| Branch | Head | Purpose / state |
|---|---|---|
| `main` | `df85106` (2026-10-31) | Old baseline (merge of PR #59). **Does not reproduce production.** |
| `live-m1-llm-evaluation` | local `049292e`, origin `c3dd445` | Draft PR #60 stack base. **The local branch is 8 commits behind origin.** |
| `ironbark-evaluation-runner` | `108a556` | Local Ironbark operator workflow (stack). |
| `hosted-ironbark-evaluation` | `2c83064` | Hosted backend (stack). |
| `product-experience-redesign` | `820e0ad` | Hackathon **release candidate**, frozen ("do not modify"). Its frontend `b3121a8` was deployed earlier and is kept as rollback image `rollback-b3121a8`. |
| **`evaluation-v2`** | `bf55db7` | **Production branch. Deployed commit: `140a4e8`** (2026-11-02 07:12 UTC). Later commits on it are **not deployed**: `ce4997b` provenance in exports, `71c73cb` Phase 3, `51a366b` zero-cost loop, `ca54bc3` Phase 4 diagnostics, `2ed0038` deploy record, plus 3 ledger entries. |
| **`research/llm-task-planning`** | `5b4d129` + this handoff | **All research and lifecycle work (M1–M7).** It contains every source and frontend change of `evaluation-v2`: `140a4e8`, `ce4997b`, Phase 3 and Phase 4 are all ancestors. It lacks only 3 `evaluation-v2` commits (`50e05eb`, `d542de9`, `bf55db7`), which are cherry-pick duplicates of programme-ledger entries the research branch already holds as `39b0ddd`, `940e4b2`, `d55dd7c`. |
| `demo-cinematic-storyboard` | `59eb161` | Earlier storyboard; history only. |

**Topology:** `main` ← `live-m1-llm-evaluation` ← `ironbark-evaluation-runner` ← `hosted-ironbark-evaluation` ← `product-experience-redesign` ← `evaluation-v2` ← (merge-base `ca54bc3`) ← `research/llm-task-planning`. `evaluation-v2` is 82 commits ahead of `main`; research is 24 ahead of `evaluation-v2`. Nothing is merged to `main`. **Merging requires the owner.**

**Product-code delta between production and research:**
- **Since the deployed `140a4e8`,** only `ce4997b` touches the product surface (`hosted/api.py`, `dashboard/src/site/workspace/HostedEvaluation.tsx` plus its test and CSS, `deploy/DEPLOY.md`). It is not deployed.
- **Everything else research adds lives in new packages** that the hosted product does not import: `framework/`, `diagnostics/`, `grading/rescore` additions, `taskeval/`, `research/`, `suites/`, `evalruns/`.

**Working tree** (research branch):
- Clean except two **untracked owner files: `src/agent_readiness/investigate/prototype/` (`termvalue.py`) and `tests/test_termvalue_prototype.py`.** These are the owner's experimental work. Never stage, commit, move or delete them. Never use `git add -A`.
- `uv.lock` is deliberately untracked.

**Local-only and git-ignored** (`.gitignore`, `deploy/.gitignore`):

| What | Where |
|---|---|
| Model credentials | `.env` (repo root) |
| Production secrets (`meta_model_api_key`, `operator_token`) | `deploy/secrets/` |
| All run data, stores and ledgers | `scanner-data/` (see §6) |
| Dashboard build output and screenshots | `dashboard/dist` |

The **research store holding the owner-frozen suite exists only on this machine**: `scanner-data/research/stage-a/store/`.

---

## 2. The live product (production)

- **URL:** https://209-38-84-72.sslip.io. DigitalOcean VM, Ubuntu 24.04, 2 vCPU / 4 GB + 2 GB swap.
- **Running:** image `agent-readiness-app:latest` = `evalv2-140a4e8d0bf8`.
- **Mode and limits:** mode `live`, access **operator-only** (public starts get 403), hosted ceiling **US$10**. US$1.65 is reserved permanently per repetition; US$3.30 is reserved by two completed jobs.
- **Rollback images:** `rollback-b3121a8`, `rollback-60fcbc6`.
- **Details:** `deploy/DEPLOY.md`, `STATUS.md`.

**Shape:** one VM runs **Caddy** (automatic HTTPS; HSTS, CSP, nosniff, no-referrer) in front of **one app container** (`deploy/compose.yaml`, `deploy/Dockerfile`). The container holds the FastAPI API, the job worker and jailed Chromium.

**Container hardening:**
- uid 10001, `cap_drop: ALL`, `no-new-privileges`;
- seccomp/AppArmor unconfined only so that unprivileged namespaces work for the jail;
- `mem_limit 4g`, `pids_limit 1024`;
- data volume `/data`, holding `/data/hosted/live/...` and the derived caches under `/data/hosted/live/derived/`;
- the private source run `live-2d58a80e14` mounted read-only.

### Backend: `src/agent_readiness/hosted/`

| Module | Role |
|---|---|
| `serve.py` | Entry point (`python -m agent_readiness.hosted.serve`). Config **only from the environment**: `AR_HOSTED_MODE` (disabled, rehearsal or live), `AR_HOSTED_ACCESS` (operator or public), `AR_HOSTED_CEILING_USD`, `AR_OPERATOR_TOKEN_FILE`, `META_MODEL_API_KEY_FILE`, `AR_HOSTED_DATA`. |
| `api.py` | **Fixed-target API, Ironbark only.** The public request body is `{"repetitions": 1\|3\|5}` and nothing else: **no URL, task, model, browser command or spending field exists, by design.** |
| `admission.py` | Durable admission in integer microdollars. Reservations survive crashes and are never reduced. |
| `paired.py` | `WorkerExecutor`: one worker subprocess per evaluation, with a hard timeout and process-group kill. It runs `live.ironbark_runner` (`prepare` + `run_worker` → `live/abtest.drive`): 4 frozen Ironbark tasks on Original and Modified. |
| `jail.py` | Network-isolated Chromium (user, net, pid and mount namespaces; loopback only; two bridged ports, mirror and CDP; application/data/secret directories hidden). `selftest()`; `require()` makes an unjailed launch an error. |
| `telemetry.py` | Allowlisted public projection of a trial's `trace.jsonl`. Never DOM dumps, model inputs, usage, private files or loopback ports. |
| `insights.py` | Deterministic friction findings from telemetry. No model call. |
| `admin.py` | Operator CLI inside the container: `health`, `start --repetitions 1`, `watch`, `list`. |

**API routes:**
- `GET /api/health`
- `GET /api/ironbark/config`
- `GET, POST /api/ironbark/jobs`
- `GET /api/ironbark/jobs/{job_id}`
- `GET /api/ironbark/jobs/{job_id}/repetitions/{index}/trials/{arm}/{task}`
- `GET /api/ironbark/jobs/{job_id}/repetitions/{index}/trials/{arm}/{task}/screenshots/{name}`
- `GET /api/ironbark/jobs/{job_id}/live`
- `GET /api/ironbark/jobs/{job_id}/insights`
- `GET /api/ironbark/jobs/{job_id}/repetitions/{index}/export`

**Grading in production:**
- grader v1 (`investigate/taskgen/criteria.py`: `grade`, `answer_match`) is official;
- grader v2 (`grading/v2.py`, `grading/key.py`; post-hoc via `grading/rescore.py`) is shown as a labelled view beside it.

### Frontend: `dashboard/` (Vite + React + TypeScript; hash routing; one static `index.html`)

| Route | Experience |
|---|---|
| `#/` (and `#/problem`, `#/how`, `#/learn`, `#/evidence`, `#/trust`) | Product homepage, `dashboard/src/site/Home.tsx` |
| `#/demo`, `#/demo/<scene>` | Cinematic demo of a recorded evaluation, `dashboard/src/site/demo/` |
| `#/run`, `#/run/eval-<32 hex>` | Evaluation workspace, `dashboard/src/site/workspace/HostedEvaluation.tsx`, API client `dashboard/src/lib/liveApi.ts` |
| `#/studio`; `#/investigation`, `#/overview`, `#/scopes`, `#/evidence`, `#/replay`, `#/scanner` | Archive pages, loaded on demand |

### Active workflows

- **Operator starts a hosted evaluation:** with the token, in the UI or `hosted.admin start`.
- **Workers:** run paired Ironbark repetitions in live mode (real Muse Spark).
- **Results UI:** shows progress, telemetry, insights, official v1 plus labelled v2, and exports.
- **Deploying an app image:** build in a separate VM worktree, smoke-test it disabled on loopback against a copy of the data volume, retag, then `docker compose up -d --no-build --no-deps app`.

**No further paid call, deployment, ceiling change or public paid access is authorised.**

---

## 3. Research lifecycle architecture (M1–M7)

The **approved design** is `collaboration/proposals/two-stage-evaluation-lifecycle.md`, with owner decisions 1–8: natural-wording gate; assisted wording never pooled; ≤ 3 rounds with targets never lowered; new task kinds; LLM realism judge deferred; α = 0.05 with tasks as the unit; human approval before freezing; timing.

**Two stages, enforced apart:**
- **Stage A** designs a task suite and must never see agent outcomes.
- **Stage B** evaluates an approved, frozen suite.

```
business context + verified catalogue (research/taskplan/context.py [SYNTHETIC], catalogue.py)
  -> Stage A loop (suites/stage_a/loop.py): generator (planner_v2 prompt taskplan-v2, schema v3) -> evaluator v2 (taskeval/v2)
     -> selection-2 -> coverage -> stopping rule -> feedback (no answers) -> next round (<= 3)
  -> UNAPPROVED SuiteRecord + TaskRecords + PrivateOutcomes in a write-once store (suites/store.py)
  -> owner review packet -> owner decide (attestation, interactive terminal) -> freeze (FrozenSuite + ref name@vN)
  -> EvaluationManifest (evalruns/manifest.py) + pre-registered StatisticalPlan (suites/plan.py)
  -> Stage B (evalruns/runner.py): prepare (one run per wording condition; snapshot-specific validity) -> execute (jailed Chromium,
     reserve-before-send gate; rehearsal = dev provider; paid = only with a matching PaidAuthorization) -> report (official v1,
     post-hoc v2, pre-registered/exploratory/diagnostics) -> RunResult records -> public-artefact leak audit
```

### Module map

| Area | Path | Notes |
|---|---|---|
| Immutable records (M1) | `src/agent_readiness/suites/records.py` | Frozen pydantic records that refuse unknown fields; identity = canonical SHA-256. Types: `TaskRecord`, `Wording` (4 categories), `TaskSpec` (no answer keys), `PrivateOutcome`, `SuiteRecord`, `Approval` (`approver_role` = "owner"), `FrozenSuite`, `StatisticalPlan`, `AgentConfig`, `EvaluationManifest`, `RunResult`. |
| Write-once store (M1) | `suites/store.py` | `objects/<kind>/<sha>.json` (0444), `private/<sha>.json` (dir 0700, files 0400), `refs/<kind>/<name>.json` (write-once). Tamper detection on every read. Cross-record rules: freezing needs an approved approval of the exact hash; a manifest needs a frozen suite; Stage A may not reference Stage B objects. |
| Stage A / B boundary (M1) | `suites/boundary.py` | AST import check over `suites/{records,store,boundary}.py` and `suites/stage_a/**`. Forbidden: trials, hosted, diagnostics, rescore, provenance, pilot, `framework.evaluate`, `evalruns`, live, scanner, agent. Tested directly and transitively. |
| Evaluator v2 (M2) | `taskeval/v2/{evaluator,nl,lexicon,coverage}.py` | Runs **evaluator v1 unchanged** first. `checks=False` returns v1 exactly. `gate-nl-1` replaces only v1's literal field-name rule for natural wording. |
| Record mapping | `suites/stage_a/taskrecords.py` | v2 record → `TaskRecord` / `PrivateOutcome`. Public evidence paths are limited to criterion-named pages. |
| New kinds (M2b) | `taskeval/v2/kinds.py`, `research/taskplan/schema_v3.py` | `ranked_subset` and `either_of`: compile, record oracle, replica gate, grader-v2 keys (`build_key_any`). Existing kinds are delegated to unchanged v1 code. |
| Stage A loop (M3) | `suites/stage_a/{loop,selection,feedback,stopping,generators}.py`, `research/taskplan/planner_v2.py` | Fixture generators (zero cost). The paid `MetaGenerator` (planner_v2) refuses without an approval note. |
| Approval and freezing (M4) | `suites/stage_a/approval.py` | `review_packet`, `render_markdown`, `decide`, `freeze`, `revise` (preparing role explicit), `clarify`. CLI: `python -m agent_readiness.suites.stage_a.approval review\|decide\|freeze`. |
| Statistics (M4) | `suites/plan.py` | Exact sign-flip test over task-level paired differences; min p = 2/2ⁿ; Monte Carlo power and MDE under stated assumptions. Confirmatory is refused when infeasible. |
| Manifests (M4/M5) | `evalruns/manifest.py` | Declares the **real** pinned agent (`agent_config()`); worst-case budget; regression manifests with a diff. |
| Stage B runner (M5/M7) | `evalruns/runner.py` | `prepare`, `steps` (seeded counterbalancing), `execute`, `condition_results` (rescore's row grader plus `build_key_any`), `report`, `public_report`, `audit_public`. |
| Paid guard (M7) | `evalruns/authorization.py` | `PaidAuthorization` (write-once), `ledger_dir(experiment_id)`, `verify(...)`. |
| Rehearsal and drivers | `evalruns/rehearse.py`, `evalruns/m7_larkspur.py`, `suites/experiments/m6_stage_a.py` | `rehearse.py`: zero-cost end-to-end on Larkspur and Ironbark. `m7_larkspur.py`: M7 driver (revise, packet, rehearse-synthetic, manifest, rehearse, paid). `m6_stage_a.py`: M6 driver with preflight. |
| Shared engine (used, NOT modified) | v1 code pinned by SHA-256 in `tests/test_taskeval_v2.py` | `investigate/taskgen/{criteria,gate,freeze}.py`, `grading/{key,v2}.py`, `framework/oracle.py`, `taskeval/{evaluator,select}.py`, `research/taskplan/{verify,schema}.py`. Also used: `investigate/trials/runner.run_trial`, `spend_gate.py`, `ledger.py`, `hosted/jail.py`, `live/devprovider.py`, `framework/site.py` (sites `larkspur`, `ironbark`), `diagnostics/run.py`. |

---

## 4. The lifecycle in detail

### 4.1 Task generation, validation, feedback, selection (Stage A)

- **Generator.**
  - Prompt `taskplan-v2` (`research/taskplan/planner_v2.py`): v1 rules plus "state values in the customer's words", the M2b shapes and a feedback slot.
  - Wire schema `taskplan-schema-v3` (strict; only keywords Meta has accepted; Meta accepted it live in M6).
  - Proposals are **intents**. Answer-like fields are stripped.
  - Parse: `schema_v3.parse_item_v3`. Evaluator v2 normalises `values: null` for v1 (`evaluator.v1_shape`).
- **Evaluator v2** (`taskeval-2`):
  - **Hard gates:** every v1 gate (schema, grounding, expressible, answerable, unique, oracle agreement, grader v1 and v2 compatibility, cross-variant fairness, evidence). The executed wording passes either `gate-nl-1` (natural) or the full v1 gate (assisted).
  - **Categories:**
    - `natural_verifiable`: the customer's words are executed unchanged;
    - `natural_underspecified`: preserved, not executed, with what is unresolved; may yield a labelled assisted derivative;
    - `natural_judgment`: rubric or human review;
    - `assisted_restatement`: labelled; never pooled with natural.
  - **`gate-nl-1`:**
    - traces every value, comparator, ranking and looked-up fact to the wording, and every stated value back to the spec;
    - detects vague quantities (never turned into numbers), negative context, value-domain collisions and ambiguous cues;
    - the lexicon is `taskeval/v2/lexicon.py` (`nl-lexicon-1`).
  - **Identity:** `taskeval-2` plus a config fingerprint, deterministic across processes (tested).
- **Feedback** (`feedback-1`):
  - contains rejection categories with wording-only examples, uncovered cells, missing capabilities, signatures to avoid, and underspecified advice;
  - **never** contains answers; never echoes wordings rejected for leaking an answer.
- **Selection** `selection-2`: deterministic greedy for coverage. **Stopping** `stopping-1`: `targets_met`, `max_rounds`, `diminishing_returns`, `budget_cap` (checked before sending).
- **Provisional targets** (`taskeval/v2/coverage.py: TARGETS`): ≥ 2 tasks per persona; every journey with weight ≥ 0.10 covered; ≥ 4 capabilities; ≥ 30 % multi-condition; no near-duplicates; 8–12 deterministic tasks; ≤ 2 rubric tasks. **Never lowered:** unmet targets go to the gap report.

### 4.2 Owner review, approval, immutable freezing

- **Review packet** (`approval.review_packet` / `render_markdown`): wordings, categories, assumptions, coverage and gaps. Public only.
- **`decide`:**
  - the owner types `I am the owner and I approve suite <full sha>` (or "reject");
  - **a non-synthetic suite can only be decided when `sys.stdin.isatty()`**: an interactive terminal, so no agent or CI;
  - suites named `synthetic-*` are test fixtures, and their approvals are labelled `[SYNTHETIC FIXTURE …]`.
- **`freeze`:** the store refuses unless an **approved** `Approval` of the **exact** suite hash exists. It writes the ref `name@vN`.
- **`revise`:** a new version and hash referencing the old one (input kind `suite`). The old approval does not carry over. The preparing role is explicit (`by="system"` for agent-prepared revisions).
- **`clarify`:** an owner clarification of an underspecified request becomes a re-validated **assisted** task, labelled with who clarified it and when.
- **This guard is not authentication.** The web product will need an authenticated owner identity; see §7.

### 4.3 Real browser-agent execution and isolation (Stage B)

- **`prepare`:**
  - creates one standard `InvestigationRun` **per wording condition**;
  - writes `tasks-manifest` with the frozen executed wordings, private `criteria` from `PrivateOutcome.expected`, and `variant-criteria`, where each variant's private record is re-derived and checked: the frozen answer must re-derive and the executed wording must pass its gate. Otherwise the task is invalidated for that variant, with a reason;
  - writes the `snapshot-manifests` and `evalrun-provenance` artefacts.
- **`execute`:**
  - `run_trial` uses real Chromium inside `hosted/jail.py` (`jail.require()` plus `selftest()`; state restored afterwards), with the snapshot served on loopback;
  - order is counterbalanced from the manifest seed;
  - a void trial or a bound violation halts the run; there are no retries;
  - **rehearsal** uses the pinned loopback dev provider (`live/devprovider.py`, a scripted stand-in, NOT a model). **Paid** uses the pinned agent (`agent.ModelConfig()`: `muse-spark-1.3`, `https://api.meta.ai/v1`; profile `suite-v2-compat2`, reasoning effort low, 4096 completion tokens) and **requires** a verified `PaidAuthorization`.
- **The manifest hash is identical** between the rehearsal and the paid run. The mode is a run property, not a manifest property.

### 4.4 Spending authorisation, reservation, durable ledgers, restart safety

- **Reserve-before-send** (`spend_gate.RequestGate`, `ledger.Ledger`):
  - each request's upper bound is fsync'd to `ledger.jsonl` before it is sent;
  - it is settled to the actual calculated cost from provider usage;
  - a failure keeps the full reservation counted;
  - a bound violation closes the gate, and the flag is recovered from the ledger after a restart.
- **Prices** are verified constants (US$1.25 / US$4.25 per M tokens; `ledger.VERIFIED_PRICES`). Costs are calculated, not billed.
- **Paid Stage A** (M6): `MetaGenerator` with a fixed ledger directory and gate run id, a 3-request cap and a US$0.10 run cap. The driver's preflight refuses a used ledger. `MetaClient.complete` makes exactly one POST (no retries, no redirects).
- **Paid Stage B** (M7): `evalruns/authorization.py`.
  - `PaidAuthorization` is write-once (exclusive create, 0444) and content-hashed. It binds the experiment id, the exact frozen suite (approval must be real; synthetic is refused), the manifest hash, the maximum trials and the cap. The manifest hard cap must equal the cap, and the worst case must fit; neither is ever relaxed. It also binds the pinned agent configuration.
  - The ledger is fixed at `scanner-data/research/stage-b/ledgers/<experiment_id>/`.
  - A scope cap applies across all trials, with a per-trial run cap of max requests × US$0.044.
  - Trials are counted from the ledger, so restarts are safe; a trial that ever reserved is never re-run.
- **Hosted product admission is a separate system:** `hosted/admission.py`, microdollars, US$1.65 per repetition, global ceiling US$10. See §7 for reconciling the two.
- **Programme ledger:** `collaboration/budget/programme-ledger.json` (append-only by text insertion; never re-serialise it). Known-spend subtotal **US$13.418982 / A$20.1285** of the A$50 limit, which is a limit, not an authorisation.

### 4.5 Grading

- **Official grader v1:** `criteria.grade` / `answer_match`. Exact after normalisation; a string answer may carry at most `len(truth)+16` extra characters; set elements must equal names exactly.
- **Post-hoc grader v2:** `grading/v2.py` with keys from `grading/key.py` and, for M2b kinds, `taskeval/v2/kinds.build_key_any`. It accepts consistent supporting detail and rejects hedges, contradictions and multiple candidates. It is binary and conservative; `review` flags never change the score.
- **`grading.rescore.rescore_run` cannot key the M2b kinds:** v1 `compile_criterion` raises a pydantic validation error, not `KeyError_`. The Stage B runner therefore uses `rescore._trial_rows` with `build_key_any` keys. `rescore.py` is unchanged.

### 4.6 Evidence, diagnostics, reporting, provenance

- **Evidence per trial:** see §6. The evidence rule requires visits to the pages that hold the answer. `observed_text` requirements are also recorded.
- **Diagnostics** (`diagnostics/run.py`): structural, behavioural and hypothesis layers sharing one finding schema. They are advisory, and only run when the manifest's variants are the site's registered ones.
- **Reports:** `runner.report` has `preregistered`, `exploratory` (per-condition tallies and analysis) and `diagnostics` sections, plus `run_results` and `trials`. `public_report` strips v2 reason texts. `audit_public` scans:
  - store objects: each task for its own answer, every other kind for any answer;
  - run public artefacts;
  - public report files.
- **Provenance:** every record carries `Provenance` (created_at, created_by **role**, tool, version, config fingerprint, typed `InputRef`s). Model provenance for exports: `src/agent_readiness/provenance.py`.

---

## 5. Experimental results

### 5.1 M6: the first paid Stage A generation (report `collaboration/reports/lifecycle-m6-stage-a.md`)

- **Configuration:** Larkspur; `muse-spark-1.3`, reasoning effort low, 6000 completion tokens; `taskplan-v2` / schema v3; 12 proposals per round; ≤ 3 rounds; owner cap US$0.10.
- **Spending:** **2 requests, US$0.049804 calculated:**
  - round 1: US$0.020578; 2917 prompt + 3984 completion tokens (2216 reasoning); 19.9 s;
  - round 2: US$0.029226; 3678 + 5795 (4050 reasoning); 24.6 s, **close to the 6000-token cap**.
- Meta **accepted schema v3**. The loop stopped at **`targets_met`** after 2 rounds.
- **Quality:**
  - As run: 18/24 natural_verifiable, 1 judgment, 5 rejected.
  - **2 of those rejections were false**: "at least 5 seats" was misread as a superlative. Fixed in `f51968c`; the offline re-evaluation gives 20 natural_verifiable and 3 correct rejections.
  - 0 underspecified.
  - Realism concern: catalogue-speak in 12 of 24 wordings, field labels named in 11 of 24.
- **Stored:**
  - **v1 proposal** `larkspur-core` v1: `873e07c306cafc6772706c528391ffe5ef734eb7e3ca6216e2bd780b81e8ed89` (13 tasks; immutable; never approved);
  - run directory: `scanner-data/research/stage-a/m6-larkspur-core-20261102T121242Z/`;
  - ledger: `scanner-data/research/stage-a/ledgers/m6-larkspur-core/`.

### 5.2 M7: the first paid Stage B browser evaluation (report `collaboration/reports/lifecycle-m7-browser.md`)

**Suite and approvals:**
- Suite **v2** `larkspur-core`: `172d1e712eb18871fd4f24b227a2448ec44a546347bb9874f0946c5609f7848b`. It holds 6 natural tasks: 3 kept from v1 and 3 re-validated offline. It was prepared by the agent (`created_by: system`).
- **Owner approval** `31f1e3aaca7ede03…`, decided at a terminal at 2026-11-02 12:40:29 UTC.
- **Frozen suite** `0816af7f7440bb08fae6235c9cb77642d434dce1a8db585d08f5be5983b9b1d7` (ref `larkspur-core@v2`).

**Manifest** `64a55c5f3a936766627a596af233595efd7c35cd448397f32357b604e6981377`:
- variants original `2f9fd2ce…` and modified `edb9a5d2…`;
- natural only, 1 repetition, seed 7; exploratory plan;
- worst case **US$7.392** against the US$8.00 cap.

**Authorisation and experiment:**
- authorisation record sha `a9049bd6bdd1687012ae2a25371f300a0386cfad029b005ef0a02132d7c42868`;
- experiment `m7-larkspur-browser-1`.

**Spending:** **111 requests, US$1.520696 calculated.** All settled, none above its reservation. 1,054,811 prompt + 47,571 completion tokens. Original US$0.906 (65 requests, 424 s); Modified US$0.615 (46 requests, 199 s). 0 void, no halt, rescore faithful, leak audit clean.

| # | Task id | Capability | Customer wording (executed) | Original | Modified |
|---|---|---|---|---|---|
| 1 | `gen-23f1802ee0-n` | multi-condition / availability | "I need a course that costs $250 or less and still has at least 5 seats left. What qualifies?" | v1 ✗ v2 ✗; 1 of 5 courses; 12 req, 67 s | v1 ✗ v2 ✓; 5 of 5 with details; **3 req, 16 s** |
| 2 | `gen-4cb59bf627-n` | lookup | "I like the sound of Life drawing studio but need to watch spending. What is the course fee for Life drawing studio?" | v1 ✓ v2 ✓; 3 req | v1 ✗ (full sentence) v2 ✓; 3 req |
| 3 | `gen-8334922e62-n` | either_of | "I work full-time on weekdays, so I can only do Saturday or Sunday. List Beginner courses that meet on Saturday or Sunday." | ✗ (1 of 4); 12 req | ✗ (2 of 4); 13 req |
| 4 | `gen-ae6c23b20b-n` | multi-condition (match_level) | "I want to push beyond basics. Show me Intermediate courses at Northside." | ✗ empty answer; 13 req | **v1 ✓ v2 ✓** (with a 404 dead end on a guessed URL) |
| 5 | `gen-f090b4b9bc-n` | ranked_subset | "I want an Intermediate course at Riverside for after work. Among those, which one has the most seats left?" | v1 ✓ v2 ✓ (did not open the other candidate) | v1 ✗ v2 ✗ `multiple_candidates`; correct but named the runner-up |
| 6 | `gen-f302fa8fe2-n` | multi-condition | "I just graduated and need a cheap, quick skill for my CV. Find courses costing $180 or less that last 6 weeks or less." | v1 ✗ v2 ✓; 12 req, 78 s | v1 ✗ v2 ✓; **3 req, 16 s** |

**Totals:** official v1 2/6 (Original) vs 1/6 (Modified); post-hoc v2 3/6 vs 4/6. **Exploratory: no claim.**

**Diagnostics:** 43 findings (11 structural, 26 behavioural, 6 hypotheses), for example "'class day' only on item pages", "budget exhaustion", "dead end on task 4". Diagnostics take "incorrect" from v1 and do not understand `either_of`.

**Known grading issues:**
- v1 rejects correct answers that carry details or are full sentences;
- v2 fails a correct answer that names a contrasted runner-up;
- the `ranked_subset` evidence rule only requires the winner's page (lenient).

**Demo candidate:** task 1 Original vs Modified; see report §4.

### 5.3 Earlier zero-cost rehearsals (M5)

Under `scanner-data/research/lifecycle/`:
- `rehearsal-larkspur-20261102b`: base 24/24 + regression 20/20;
- `rehearsal-ironbark-20261102`: 18 natural + 4 assisted;
- `rehearsal-larkspur-20261102-attempt1`: the bugs it exposed.

---

## 6. Artefact locations and schemas (all under git-ignored `scanner-data/`)

| Artefact | Path |
|---|---|
| Recorded Muse proposals (v1 planner, 20) | `scanner-data/research/taskplan/taskplan-20261102T203537-meta-7aca17/` |
| Larkspur pilot (8 paid trials, pre-lifecycle) | `scanner-data/research/pilot/pilot-larkspur-live-2f8108d3/` |
| M6 run | `scanner-data/research/stage-a/m6-larkspur-core-20261102T121242Z/`: `experiment.json`, `loop.json` (raw responses and feedback), `proposals.json`, `evaluation.{public,private}.json`, `feedback-r2.json`, `coverage.json`, `gap-report.json`, `suite-proposal.json`, `review-packet.md`, `re-evaluation-post-fix/` |
| Lifecycle store (**suites, the owner approval, the frozen suite, manifests, run results**) | `scanner-data/research/stage-a/store/` (`objects/{task,suite,approval,frozen_suite,manifest,run_result}/`, `private/`, `refs/frozen_suite/{larkspur-core@v2,synthetic-larkspur-core-m7-rehearsal@v2}.json`) |
| Paid ledgers | `scanner-data/research/stage-a/ledgers/m6-larkspur-core/ledger.jsonl`, `scanner-data/research/stage-b/ledgers/m7-larkspur-browser-1/ledger.jsonl`. Lines are `{ts, kind: reserve\|settle, id: "<gate id>:reqNN", usd}`. |
| M7 authorisation | `scanner-data/research/stage-b/authorizations/m7-larkspur-browser-1.json` |
| M7 paid run | `scanner-data/research/stage-b/paid/evalrun-paid-64a55c5f3a-natural/` plus `report-paid-64a55c5f3a.{private,public}.json` and `audit-paid-64a55c5f3a.json` |
| M7 rehearsals | `scanner-data/research/stage-b/rehearsals/` (synthetic and exact) |

**`InvestigationRun` layout** (each Stage B run): `run.json` (state and config: site, mode, condition, manifest sha) and `artifacts/`, which holds:
- `snapshot`, `site-profile`, `tasks-manifest`, `snapshot-manifests`, `evalrun-provenance`, `authorization-check-N`, `execution-N`;
- `trials/<variant>-<task_id>-r<rep>.json`.

`private/` holds `criteria.json` (expected answers) and `variant-criteria.json`. `trial-data/<trial>/<stamp>/` holds the evidence.

**Trial record keys:**
- `arm`, `variant`, `variant_sha256`, `condition`, `gate_id`, `task_id`, `trial_id`, `repeat`, `trial_dir`;
- `outcome` {answer, run_status, stop_reason, errors};
- `evaluation` {passed, evidence_backed, evidence_satisfied, answer_valid, missing_evidence, …};
- `metrics` {model_requests, steps, page_views, prompt_tokens, completion_tokens, calculated_cost_usd, elapsed_seconds, limits};
- `journey` (per-step actions, executed results, paths);
- `guard`, `mirror`, `protocol`, `task`.

**Evidence directory files:**
- `step-NNN.png` screenshots;
- `model-input-<hash>.png`;
- `model-response-NN.json`;
- `trace.jsonl` (browser isolation, browser version, initial actions, each `model_request` / `model_response` with usage);
- `observations.json` ([{path, text}]);
- `history.json`;
- `trial-result.json`;
- `agent-workspace/`.

**Private data never leaves `private/`** or the `*.private.json` files: expected answers, criteria, variant criteria, evaluator private records. Agent answers live in trial records, which are run evidence, not public outputs.

**Production data** lives on the VM: `/data/hosted/live/...`. A read-only copy of two forks is in `scanner-data/hosted-copy/`.

---

## 7. Product integration readiness

### Already in the live product
- the hosted API and worker (Ironbark only, 4 fixed tasks, paired Original/Modified);
- operator-token access;
- durable admission;
- the network jail with startup self-test;
- telemetry, insights, exports;
- official v1 plus labelled v2 view;
- the redesigned homepage, demo and workspace.

### Only in research
Everything in §3: generation, evaluator v2, new task kinds, the Stage A loop, the store, approval and freezing, manifests and plans, the general runner, the paid guard, diagnostics in reports, Larkspur as a second site, and the model-provenance export (`ce4997b`, not deployed).

### Reusable as they are (library-level, tested)
- `suites/*`, `taskeval/v2/*`, `evalruns/{manifest,runner,authorization}.py`, `suites/plan.py`, `diagnostics/run.py`, `grading/{v2,key,rescore}.py`, `framework/site.py`;
- the hosted `jail.py`, `telemetry.py` (an allowlisted public projection of `trace.jsonl`, applicable to evalruns trials) and `insights.py`;
- dashboard workspace components (`dashboard/src/site/workspace/`).

### Missing for a web-usable lifecycle (capabilities, not instructions)
1. **API surface** for suites, review packets, decisions, freeze, manifests, evaluation runs and results. Today these are Python and CLI only. The hosted API deliberately accepts **no task, URL, model or spending fields**. New endpoints must select **server-side** frozen artefacts by hash, not accept free-form task content for execution.
2. **Authenticated owner identity** for approval and paid authorisation. The current guard (exact attestation plus an interactive terminal) blocks automation but is not authentication, and it cannot work from a browser. A web flow needs a real owner credential and an audit trail. **This is an open owner decision.**
3. **Persistent storage in the container.** The lifecycle store and ledgers are local `scanner-data/` paths. The product would need them on the data volume (`/data/...`), with backup. The owner-frozen `larkspur-core@v2` currently exists only on this workstation.
4. **Reconciliation of two spend systems:** hosted admission (microdollars, US$1.65 per repetition, global ceiling US$10) and the research per-experiment ledgers plus `PaidAuthorization`. Both are durable, reserve-before-send and restart-safe. The product needs one coherent ceiling and reporting.
5. **A general worker.** The hosted worker runs `live/ironbark_runner` (frozen experiment code). Running `evalruns` jobs needs a worker path that reuses `WorkerExecutor`'s isolation, process and timeout model.
6. **UI** for suite review (wordings, flags, coverage gaps), decision and freeze status, run progress across natural and assisted conditions, both graders labelled, diagnostics and evidence. RunResults do not record the mode explicitly (rehearsal vs paid), so a consumer must use `summary.execution_provider`.
7. **A site registry beyond the two controlled sites,** each with an oracle. Uncontrolled sites have no oracle, so their tasks are human-review only.

### Safeguards that cannot simply be bypassed
- **Owner approval before freezing:** the store enforces an approved approval of the exact hash, and an agent may never decide a real suite.
- **Paid authorisation:** the manifest and frozen suite are bound by hash; the cap is never relaxed; trials are counted from the durable ledger; there are no retries; synthetic suites never qualify.
- **The network jail:** `jail.require()` plus a startup self-test; evaluations stay disabled if it fails.
- **Stage A never sees agent outcomes** (`suites/boundary.py`).
- **Private answers stay private**, and the public leak audit must pass.
- **Grader v1 remains official** and its grades never change; v2 is post-hoc and labelled.
- **Natural and assisted results are never pooled.**

---

## 8. Constraints, risks and open issues

### Constraints
- **Preserve the live deployment** (`evaluation-v2` @ `140a4e8`, rollback images) until explicit owner approval. No deploy, ceiling change or public paid access.
- **Do not merge research wholesale.** Do not modify `product-experience-redesign`, historical frozen experiments (Tasks 005–007 code, config and data; frozen manifests; pilot evidence), stored evaluation evidence or ledger history.
- **The programme ledger is append-only** by text insertion.
- **Never print or commit** `.env`, `deploy/secrets/*`, the API key, the operator token, private answers or hidden evaluation data.
- **No paid API call** without separate owner authorisation stating a cap.
- **Preserve unrelated work and untracked files** (§1). Use explicit `git add <paths>`.
- **Testing policy:** see `AGENTS.md`. Do not run browser tests, dashboard builds or servers concurrently.

### Open architectural decisions (owner)
- the web authentication model for owner approval and paid authorisation;
- whether lifecycle runs share the hosted admission ceiling or keep separate experiment caps;
- where the lifecycle store lives in production;
- the merge strategy: research → `evaluation-v2` → `main`. The 3 duplicate ledger cherry-picks will conflict trivially, because the research ledger is a superset;
- whether to promote evaluator v2 and the new kinds out of "research";
- `taskplan-v3` wording realism (catalogue-speak);
- the stricter `ranked_subset` evidence rule;
- v2 review rules for contrastive mentions.

### Technical debt and known bugs
- **The lexicon is heuristic and English-only.** The negation window does not reset at "but". Comparator and superlative edge cases remain beyond the fixed "at least N".
- **v1 limitations (unchanged, inherited):**
  - "1 day" and "2 days" are treated as incomparable units;
  - the naive start-page substring leak rule;
  - v1's verifier reads the Larkspur context module global (v2 supplies the configured context temporarily);
  - the v1 public view (`taskeval.evaluator.public`) keeps evidence page paths, which name the answer items of set tasks.
- **`taskeval/evaluator.py` (v1) imports the research `Verifier`.** Promote it before productising.
- **`grading.rescore.rescore_run` crashes on the M2b kinds;** the runner works around it.
- **Diagnostics:** v1 "incorrect" labels; they don't understand `either_of`; `from_framework_run` revalidates with the v1 gate.
- **RunResult has no explicit mode field.** The M7 manifest has both rehearsal and paid RunResults.
- **The 14-request limit** (8 + 3 × hops) dominates outcomes on many-page tasks.
- **Six-task suites miss the provisional targets** (8–12 tasks, persona minimums).
- **Persona-to-attribute maps and business contexts are SYNTHETIC.**
- **The M6 completion headroom was thin** (5795 of 6000 tokens).
- **`AGENTS.md`'s "Current state" summary is stale;** `STATUS.md` is authoritative.
- **The local branch `live-m1-llm-evaluation` is 8 commits behind origin.**

### Coverage gaps
- Only Larkspur has seen real paid lifecycle runs; Ironbark has rehearsals only.
- Only 1 repetition; no confirmatory design.
- No public or multi-user flows.
- No end-to-end test exists through the hosted API for lifecycle runs (none exist yet).

---

## 9. Useful commands

```bash
# lifecycle review (owner runs decide/freeze in an interactive terminal)
.venv/bin/python -m agent_readiness.suites.stage_a.approval review scanner-data/research/stage-a/store <SUITE_SHA> --markdown
# zero-cost end-to-end rehearsals (real Chromium in the jail, dev provider; writes under --root; ~15-40 min)
.venv/bin/python -m agent_readiness.evalruns.rehearse larkspur --root scanner-data/research/lifecycle/<new-dir>
# M6 preflight only (zero cost; its fixed ledger is used, so a paid run refuses)
.venv/bin/python -m agent_readiness.suites.experiments.m6_stage_a --preflight-only
# M7 driver (zero-cost subcommands: revise | packet | rehearse-synthetic | manifest SHA | rehearse SHA; 'paid' needs authorisation and refuses a used ledger)
.venv/bin/python -m agent_readiness.evalruns.m7_larkspur packet
# hosted service locally (disabled mode by default)
AR_HOSTED_MODE=disabled .venv/bin/python -m agent_readiness.hosted.serve
```

**Test counts at writing:**
- lifecycle non-browser: 144 passed;
- critical: 214 passed, 17 deselected;
- dashboard vitest: 189 passed (16 files), run 2026-11-03;
- M5 browser end-to-end: 1 passed (last run during M5 and M7 preparation).

## 10. References

- **Design:** `collaboration/proposals/two-stage-evaluation-lifecycle.md`.
- **Reports:** `collaboration/reports/lifecycle-{m1,m2-m5,m6-stage-a,m7-review-packet,m7-browser}.md`.
- **Earlier research:** `docs/research/LLM_TASK_PLANNING.md`, `docs/research/LARKSPUR_PILOT.md`, `docs/FRAMEWORK.md`, `docs/DIAGNOSTICS.md`, `docs/FUTURE_ARCHITECTURE.md`, `collaboration/reports/grader-v2.md`.
- **Product:** `deploy/DEPLOY.md`, `dashboard/PRODUCT_REDESIGN.md`, `collaboration/reports/hosted-ironbark-wip.md`, `collaboration/reports/hosted-production-trial-2026-11-02.md`, `docs/ARCHITECTURE.md`.
