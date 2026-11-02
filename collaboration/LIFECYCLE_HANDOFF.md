# LIFECYCLE_HANDOFF: two-stage evaluation lifecycle (written 2026-11-02 21:xx AEDT, end of a Claude Code session)

**For the next Claude Code (Opus) agent, who owns M2 onward.**

**Verify against the repository; where this text and the code differ, the code wins.** Statements are marked **[fact]** (verified in the checkout when written), **[proposal]** (approved design, not yet built) or **[open]** (unresolved).

Nothing in this document authorises spending, deployment, merging or modifying evidence.

---

## UPDATE 2026-11-02 (later): M2–M5 implemented. Read this block first

**[fact]** M2 (`c721c47`), M2b (`5bc7892`), M3 (`11e1a59`), M4 (`258ec96`) and M5 (the final commit of the report) are implemented on `research/llm-task-planning`. The owner authorised them as one continuous zero-cost run and authorised pushing this branch; it is pushed, not merged. Full report: [`collaboration/reports/lifecycle-m2-m5.md`](reports/lifecycle-m2-m5.md).

- **What exists now:**
  - `taskeval/v2/` (evaluator v2, `gate-nl-1`, lexicon, coverage, M2b kinds);
  - `research/taskplan/{schema_v3,planner_v2}.py` (`taskplan-v2` prompt, `MetaGenerator`; paid use refuses without approval);
  - `suites/stage_a/{taskrecords,loop,selection,feedback,stopping,generators,approval}.py`;
  - `suites/plan.py`;
  - `evalruns/{manifest,runner,rehearse}.py`.
- **Tests:**
  ```bash
  .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_suites_m1.py tests/test_taskeval.py tests/test_research_taskplan.py tests/test_taskeval_v2.py tests/test_kinds_m2b.py tests/test_stage_a_loop.py tests/test_lifecycle_m4.py tests/test_evalruns_m5.py -m "not browser"
  .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_evalruns_m5.py -m browser     # real Chromium + jail; zero cost; run alone
  bash scripts/critical-tests.sh
  ```
- **Rehearse:**
  ```bash
  python -m agent_readiness.evalruns.rehearse larkspur|ironbark --root scanner-data/research/lifecycle/<new dir>
  ```
  Zero cost: a fixture generator, a SYNTHETIC approval and the loopback dev provider.
- **Still true:**
  - no paid call has been made by the lifecycle code;
  - v1 code (`criteria`, `gate`, `key`, `grader v2`, `oracle`, taskeval v1, `verify`, `schema`, `freeze`) is unchanged and pinned by hash;
  - only synthetic suites have been approved.
- **M6 Stage A done** (owner-authorised, US$0.10 cap): US$0.049804 spent; the `larkspur-core` proposal is UNAPPROVED. See [`reports/lifecycle-m6-stage-a.md`](reports/lifecycle-m6-stage-a.md).
  - The driver is `python -m agent_readiness.suites.experiments.m6_stage_a` (preflight-only by default; its fixed ledger is now used, so it refuses to run again).
  - Next: owner review of the generated tasks. Stage B and any further paid call need new authorisation. `evalruns.runner.execute` still refuses paid mode.
- The step-5 "stop for approval after M2" instruction below is superseded by the owner's later authorisation. "The research branch is not pushed" (§2) is no longer true.

## NEW AGENT START HERE

1. **Read, in order:**
   1. `AGENTS.md`;
   2. this file;
   3. `collaboration/proposals/two-stage-evaluation-lifecycle.md` (the approved design and decisions);
   4. `STATUS.md`;
   5. `docs/FRAMEWORK.md`;
   6. `docs/research/LLM_TASK_PLANNING.md`;
   7. `docs/research/LARKSPUR_PILOT.md`;
   8. `docs/DIAGNOSTICS.md`;
   9. `collaboration/reports/lifecycle-m1.md`.
2. **Branch:** `research/llm-task-planning` (local only; HEAD at writing = the commit that adds this file, on top of `6bdfe6c`). Do all lifecycle work here, or on a branch cut from it. **Never** commit to `product-experience-redesign` (the release candidate) or deploy.
3. **First tests:**
   ```bash
   .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_suites_m1.py tests/test_taskeval.py tests/test_research_taskplan.py
   bash scripts/critical-tests.sh
   ```
   Expected: 26 + 19 + 14 = **59 passed**; critical **214 passed, 17 deselected**.
4. **First concrete M2 task:**
   - Implement `gate-nl-1` as a new, versioned check in a new module `src/agent_readiness/taskeval/v2/` (or `taskeval/evaluator_v2.py`). Every constraint *value* must be stated in the customer's words and map unambiguously to one attribute domain of the verified catalogue; field names may be implied.
   - Classify each candidate into the four wording categories of `suites.records.Wording` (`natural_verifiable`, `natural_underspecified`, `natural_judgment`, `assisted_restatement`).
   - Prove first that **evaluator v1 results are reproduced exactly** on the 20 recorded Muse Spark proposals and the fixture when the v2 checks are off.
5. **Stop for approval:**
   - after M2, before M2b: report the tests and the category distribution on the 20 recorded proposals;
   - **before any paid LLM or browser call;**
   - before any deployment, merge or push;
   - before changing any frozen experiment, grader v1, evaluator v1 or the hosted path.

---

## 1. Project context

**Agent Readiness** [fact] is a testing and observability platform for AI agents interacting with websites. It runs browser agents (Meta Muse Spark `muse-spark-1.3`) on tasks, grades the outcomes independently of the agent's claims, captures evidence (screenshots, action timelines, request traces), diagnoses friction, and measures whether a website change helps. A public benchmark and a capability registry are intended as **separate future products** (`docs/FUTURE_ARCHITECTURE.md`) [proposal].

**Target workflow** [proposal; owner direction 2026-11-02]: business context and catalogue → LLM task generation → independent validation and refinement → **human approval** → **frozen suite** → live agent evaluation → evidence-linked diagnostics → targeted website improvement → **re-evaluation against the same frozen suite**. Live execution references the frozen manifest; it never regenerates tasks.

**Deployed hackathon product vs research** [fact]:

| | Hackathon product (production) | Research (isolated) |
|---|---|---|
| Where | https://209-38-84-72.sslip.io (DigitalOcean, operator-only starts), commit `140a4e8` on `evaluation-v2`, deployed 2026-11-02 07:12 UTC | branch `research/llm-task-planning` (local) |
| Scope | the fixed Ironbark evaluation: homepage, demo, workspace; grader v1 official; grader v2 shown as a labelled post-hoc rescore | Phase 3 framework, Phase 4 diagnostics, LLM planner, taskeval, Larkspur pilot, lifecycle M1 |
| Release candidate | `product-experience-redesign` @ `820e0ad` (hackathon release candidate; frozen; do not modify) | n/a |

The 2026-11-05 submission takes priority over research work; Wednesday 2026-11-04 is the submission-readiness checkpoint.

### Architecture and key modules [fact]

| Area | Modules | Entry points |
|---|---|---|
| Hosted product | `src/agent_readiness/hosted/` (api, admission, paired worker, jail, telemetry, insights), `deploy/` | `python -m agent_readiness.hosted.serve` (see `deploy/DEPLOY.md`) |
| Investigation engine (shared) | `investigate/`: `inspect/` profiler, `taskgen/` (criteria, gate, candidates, freeze), `trials/runner.py` (`run_trial`), `evaluate/` (frozen rules), `sitemodel/` (snapshots, mirror) | used as a library |
| Graders | v1 `investigate/taskgen/criteria.py` (`grade`, `answer_match`; official, frozen); v2 `grading/v2.py`, `grading/key.py`; post-hoc rescore `grading/rescore.py` | `python -m agent_readiness.grading.rescore RUN... --out DIR` |
| Phase 3 framework | `framework/site.py` (`SiteDefinition`, registry: ironbark, larkspur, zoo-*), `framework/oracle.py` (`RecordOracle`), `framework/generate.py` (rule-based generation, verifiability), `framework/evaluate.py` (zero-cost orchestration) | `python -m agent_readiness.framework.generate SITE`; `python -m agent_readiness.framework.evaluate SITE --root DIR --provider dev` |
| Second controlled site | `sites/larkspur/` (data.py = source of truth; render.py: original/modified variants) | via `framework.site.get("larkspur")` |
| Phase 4 diagnostics | `diagnostics/` (structural, behavioral, hypotheses, run) | `python -m agent_readiness.diagnostics.run RUN [--recorded] --out FILE` |
| Provenance | `provenance.py` (model/grader provenance from frozen records) | library |
| LLM planner (research) | `research/taskplan/` (context [SYNTHETIC], catalogue view, schema v1/v2, planner, verify, preflight, experiment) | `python -m agent_readiness.research.taskplan.experiment --client fixture` (paid `--client meta` needs approval) |
| Task evaluator v1 (research) | `taskeval/evaluator.py` (taskeval-1), `taskeval/select.py` (selection-1) | library |
| Larkspur pilot (research) | `research/pilot.py` | `python -m agent_readiness.research.pilot prepare/execute/report` (paid `execute` needs approval) |
| Lifecycle M1 | `suites/records.py`, `suites/store.py`, `suites/boundary.py` | library |
| Zero-cost model stand-in | `live/devprovider.py` (NOT a model) | used by `framework.evaluate` and `research.pilot` with provider `dev` |
| Safety | `spend_gate.py` (`RequestGate`, reserve-before-send), `ledger.py`, `hosted/jail.py` (Chromium network-namespace jail; `AGENT_READINESS_BROWSER_JAIL`, `jail.require()`, `jail.selftest()`) | library |

## 2. Current state

### Completed (all on `research/llm-task-planning`; earlier items are also on `evaluation-v2`) [fact]

| Item | What | Commit (research branch) | Docs |
|---|---|---|---|
| grader v2 and rescore | key-based grading; faithful post-hoc rescore; hosted v2 view | on `evaluation-v2` (deployed at `140a4e8`) | `collaboration/reports/grader-v2.md` |
| Phase 3 | site definitions, record oracles, rule-based generation, verifiability, Larkspur, zero-cost loop | on `evaluation-v2` (`71c73cb`, `51a366b`) | `docs/FRAMEWORK.md` |
| Phase 4 | structural, behavioural and hypothesis diagnostics | on `evaluation-v2` (`ca54bc3`) | `docs/DIAGNOSTICS.md` |
| Model provenance in exports | derived from records | on `evaluation-v2` (`ce4997b`; not deployed) | |
| LLM planner | prompt `taskplan-v1`, schema v2, preflight; paid run 1 rejected (strict schema), paid run 2 succeeded | `bfa5525` … `e07280f` | `docs/research/LLM_TASK_PLANNING.md` |
| taskeval-1, selection-1, Larkspur pilot | code-only evaluator; 8 paid jailed trials | `5f602a8`, `6d6a83c` | `docs/research/LARKSPUR_PILOT.md` |
| Lifecycle proposal (approved) and **M1** | decisions recorded; immutable records, store, boundary | `7de597b`, **`6bdfe6c`** | proposal, `collaboration/reports/lifecycle-m1.md` |

**Implemented vs proposed:**
- **Implemented:** everything in the table above.
- **Proposed only** (approved design, no code): M2, M2b, M3, M4, M5, and M6 (paid; separate approval).
- **Not started:** `evalruns/` (the Stage B package).

### Deployment state [fact]

- Production runs `140a4e8`: grader v2 view, enforced-ceiling export fix, operator-token UX.
- The later `evaluation-v2` commits (Phase 3/4, provenance, ledger entries) are **not deployed**.
- Mode live, access operator-only, hosted ceiling US$10 with 4 repetitions remaining.
- Rollback images and commands: `deploy/DEPLOY.md`.

### Spend [fact]

The programme ledger is `collaboration/budget/programme-ledger.json` (pushed on `evaluation-v2`; cherry-picked here). The known-spend subtotal is **US$11.848482 / A$17.7727** of the A$50 ceiling. It includes:
- `hosted-live-2` US$1.126097;
- `research-taskplan-1` US$0.029054: an *unconfirmed conservative* reservation for a rejected request;
- `research-taskplan-2` US$0.024452;
- `research-pilot-larkspur-1` US$1.228813.

Calculated cost is not a bill.

### Tests run at handoff [fact, 2026-11-02]

| Suite | Result |
|---|---|
| `tests/test_suites_m1.py` | **26 passed** (mutation-checked: disabling tamper detection or the outcome-reference check fails exactly the corresponding 3 tests) |
| `scripts/critical-tests.sh` | **214 passed, 17 deselected** |
| taskeval, research taskplan, framework, framework evaluate (fast), diagnostics, grader v2, rescore, provenance, derived cache, export ceiling (`-m "not browser"`) | **159 passed, 4 deselected** |
| Earlier in the session | dev selection 1400 passed; dashboard vitest 189; browser e2e (`test_framework_evaluate.py -m browser`) 4 passed; existing dev-provider suites 70 passed |

### Local, git-ignored data the tests and tools rely on [fact]

None of this is in the repository.
- `scanner-data/research/taskplan/taskplan-20261102T203537-meta-7aca17/`: the 20 recorded Muse Spark proposals, used by the pilot's `prepare`.
- `scanner-data/research/pilot/pilot-larkspur-live-2f8108d3/`: the paid pilot run.
- `scanner-data/hosted-copy/`: a read-only copy of two production forks.
- `scanner-data/framework-runs/`.

Tests that need private data skip themselves when it is absent (for example `test_diagnostics.py::test_real_paid_trial_fork_diagnoses_as_documented`).

### Known limitations and technical debt [fact]

- **taskeval-1 imports the research planner's `Verifier`;** promote it before productising.
- **The acceptance gate (v1) requires literal field names,** so only 6/20 natural customer wordings pass. That is the motivation for `gate-nl-1`.
- **The criterion language cannot express** ranked-within-a-filter or either/or (M2b), so those intents go to human review.
- **Persona-to-attribute maps and business context are synthetic;** realism criteria are simple heuristics.
- **The Larkspur pilot** used restated wording only (now the "assisted" condition), one repetition and no pre-registered rule, so it is exploratory.
- **Stage B pieces exist only inside `research/pilot.py`** (Larkspur-specific) and `framework/evaluate.py` (zero-cost); there is no general runner yet (M5).
- **Request limits** (8 + 3 × hops, at most 16) caused budget exhaustion on Larkspur tasks that need scanning many pages, on both variants.
- **The research branch is not pushed;** ask the owner before pushing.
- **Untracked files** `src/agent_readiness/investigate/prototype/` and `tests/test_termvalue_prototype.py` are the owner's experimental work. Do not commit or delete them.

## 3. Approved decisions (owner, 2026-11-02; full text in the proposal §1)

1. **Natural-wording gate:** approved as a separate, versioned evaluator-v2 check. Evaluator v1 and the frozen experiments stay unchanged.
2. **Restated wording:** only as a separately labelled **assisted-wording** condition. Never pool assisted and natural outcomes.
3. **Coverage and stopping (provisional):** at most 3 generation rounds, the proposed coverage targets, a budget cap, a diminishing-return stop and explicit gap reports. Never lower thresholds to fill a suite.
4. **New task kinds:** ranked-within-a-filter and either/or in M2b (after M2), with independent oracle and grader support.
5. **Advisory LLM realism judge:** deferred (off by default).
6. **Statistics (revised):** confirmatory α = **0.05**. Repetitions are clustered within tasks, and **tasks are the unit of analysis**. A feasibility, power or detectable-effect assessment is required for the actual paired design (an exact sign-flip test needs ≥ 6 task pairs at α = 0.05; necessary, not sufficient). Primary outcome, comparison rule, repetitions, analysis and stopping rule are pre-registered before execution. **Underpowered studies may run only as exploratory,** with no confirmatory claims. Never assume 8 × 3 is sufficient.
7. **Human approval** (initially the owner) precedes immutable freezing. Substantive edits create a new version and need reapproval.
8. **Timing:** begin now (done: proposal update and M1). **Review after M1 before M2.**

**Natural-language requirements:**
- Four categories:
  - **natural & verifiable:** executed as is;
  - **natural but underspecified:** preserved, not executed until a clarification is recorded;
  - **natural & judgment-based:** rubric or human review;
  - **assisted restatement:** labelled and evaluated separately.
- **Preserve genuine ambiguity; never silently invent thresholds or constraints.**
- **70 % natural wording is aspirational,** not an admission rule.
- **Preserve** customer wording, executed wording, interpretation decisions, assumptions, validation reasons and provenance.

**Frozen suite and reusable live runs:** a suite is approved and then frozen (content-hashed). Every evaluation manifest references the frozen suite by hash and runs it unchanged on every variant and every repeated evaluation. Regression runs on a new snapshot create a new manifest with a diff.

## 4. Next implementation work

Each milestone is followed by a report and owner review.

### M2: evaluator v2
- **Objective:** a versioned evaluator v2 (`taskeval-2`) that adds `gate-nl-1`, the four wording categories, intent preservation (recorded assumptions; no invented thresholds), ambiguity classification (missing values, value collisions across domains, gate ambiguity), a coverage matrix (persona × journey × capability) and diversity measures.
- **Acceptance:**
  - with v2 checks disabled, v1 decisions on the 20 recorded proposals and the 20 fixture proposals are reproduced exactly;
  - adversarial wording tests pass (implied thresholds such as "tight budget" → `natural_underspecified`; a value in two domains → ambiguous; leaked answers rejected);
  - the outputs map one-to-one onto `suites.records.Wording` and `TaskRecord` (records build and store without error);
  - the category distribution on the 20 recorded proposals is reported, with no change to grader v1, evaluator v1 or the gate v1 code.
- **Reuse:** `taskeval/evaluator.py` (keep v1 intact; version the new code separately), `research/taskplan/verify.py` (criterion translation), `investigate/taskgen/gate.py` (v1 gate, unchanged), `framework/oracle.py`, `grading/key.py`, `suites/records.py`.
- **Likely files:** new `src/agent_readiness/taskeval/v2/*.py` (or `evaluator_v2.py`), new `tests/test_taskeval_v2.py`, and possibly `suites/records.py` helpers (non-breaking).
- **Tests:** v1 reproduction, adversarial natural-language cases, category/verifiability agreement with `TaskRecord`, a public/private split (no expected answers in public evaluation records), and boundary (`suites.boundary.forbidden_imports` must stay empty if any v2 code lives under `suites/stage_a`).
- **Dependencies and risks:**
  - domain-unambiguity needs the catalogue view's value domains (`research/taskplan/catalogue.py`), and numeric thresholds need unit-aware parsing (`criteria.quantity`);
  - risk of quietly relaxing validation: `gate-nl-1` relaxes **only** the literal field-name rule for natural wording, while every hard v1 check still applies.
- **Boundaries:** no paid calls; do not modify `criteria.py`, `gate.py`, `taskeval/evaluator.py` (v1) or frozen data.

### M2b: ranked-within-a-filter and either/or
- **Objective:** new criterion kinds, `ranked_subset` (filter conditions, then the highest or lowest by a numeric attribute) and `either_of` (OR between conditions on one attribute, e.g. Saturday or Sunday), with compile, oracle answering, grader v1/v2 support and gate rules.
- **Acceptance:**
  - on Ironbark and Larkspur, the oracle (from records) and compile (from pages) agree for every generated instance;
  - ties are refused;
  - existing kinds and frozen manifests are unaffected (their hashes are pinned by existing tests);
  - grader v2 keys the new kinds.
- **Reuse:** `investigate/taskgen/criteria.py` (add kinds without changing existing behaviour; consider a separate module plus registry if pins forbid edits), `framework/oracle.py`, `grading/key.py`/`v2.py`.
- **Tests:** oracle and page agreement, tie refusal, v1 grading of the new kinds, unchanged hashes of frozen Ironbark artefacts (run `tests/test_term_value.py`, `tests/test_ab_experiment.py`, `tests/test_remediation_main_design.py`).
- **Risk:** `criteria.py` is shared by frozen experiments. Prefer additive code paths and prove byte-identical behaviour for existing kinds.

### M3: bounded generation and evaluation loop (Stage A)
- **Objective:** a round controller (≤ 3 rounds), a feedback synthesiser (rejection categories, uncovered cells, duplicates, underspecified wordings, never answers or agent data), a stopping rule (targets met, 3 rounds, budget cap, or two rounds with fewer than 2 useful additions), a gap report, and a suite proposal as a `SuiteRecord` (Stage A).
- **Acceptance:** deterministic multi-round **fixture** generators exercise every stop path; the loop records provenance of every round (prompt and schema versions, inputs, costs); Stage A code passes `suites.boundary.forbidden_imports`; nothing reads trial or Stage B data.
- **Reuse:** `research/taskplan/planner.py` (add a feedback slot via a new prompt version, e.g. `taskplan-v2`, keeping v1), `schema.py` v2 wire schema and `preflight.py`, `MetaClient.live` with a research-local ledger (paid use needs approval), taskeval-2.
- **Likely files:** `src/agent_readiness/suites/stage_a/{loop,feedback,stopping}.py`, tests.
- **Risk:** feedback leaking answers. Test that feedback texts contain no oracle-derived values.

### M4: human approval and immutable freezing
- **Objective:**
  - an approval workflow: present the suite proposal with its public view and gap report; record an `Approval` (owner) and a `FrozenSuite`;
  - an `EvaluationManifest` builder with a statistical-plan helper that computes feasibility (exact sign-flip minimum p for the planned task count, plus a stated MDE or power under stated assumptions) and refuses a confirmatory designation when infeasible.
- **Acceptance:** a substantive edit creates a new version and makes the old approval inapplicable (the store already enforces exact-hash approval); manifests carry every field in proposal §4.1; underpowered plans are labelled exploratory.
- **Reuse:** `suites/records.py`, `suites/store.py`, `research/pilot.py` (`prepare`: freezing, worst-case budget), `framework/evaluate.py` (`_plan`).
- **Risk:** power assumptions are themselves assumptions, so record them explicitly.

### M5: generalised zero-cost Stage B runner
- **Objective:** `src/agent_readiness/evalruns/` executes any frozen `EvaluationManifest` across variants and conditions (natural and assisted never pooled) with counterbalancing from the seed, the jail (`jail.require()` plus self-test), the RequestGate and ledger, no retries, and a halt on void or bound violation. It writes `RunResult` records and separates results into pre-registered/confirmatory, exploratory and diagnostics sections (reusing `diagnostics.run`, `grading.rescore`, `provenance`).
- **Acceptance:** a **zero-cost** dev-provider rehearsal on frozen Larkspur and Ironbark manifests completes, with the rescore faithful; the manifest hash is byte-identical between rehearsal and any later paid run; the runner refuses non-loopback endpoints unless a separate approval mechanism (M6) is supplied.
- **Reuse:** `research/pilot.py` (`execute`, `report`, jail enabling, counterbalancing), `framework/evaluate.py` (`dev_provider`, `results`), `investigate/trials/runner.run_trial`.
- **Risk:** Stage B must never feed back into Stage A; keep `evalruns` out of Stage A imports (already listed as forbidden in `suites/boundary.py`).

### M6 (separate approval): paid validation
One Stage A generation (≤ 3 rounds) and one Stage B evaluation, priced from the frozen manifest (worst case = Σ request limits × per-request cap) and capped. **Do not start without explicit owner approval.**

## 5. Non-negotiable constraints

- Research work stays isolated from production; never modify `product-experience-redesign`, the deployed service, `hosted/` behaviour or the frozen experiments.
- Grader v1, evaluator v1, the acceptance gate v1, frozen manifests, pilot evidence and the programme ledger history stay unchanged. The ledger is append-only with owner authorisation.
- **Stage A cannot access agent evaluation outcomes:** not via imports, data references or summaries.
- **No paid LLM or browser calls** without explicit owner approval, with a stated maximum reservation and cap.
- **No deployment, merge or push** without explicit approval.
- **No weakening of validation** to improve acceptance rates; report gaps instead.
- **No claims of statistical significance** without an appropriate, feasible, pre-registered analysis; everything else is exploratory.
- **Preserve private expected answers** (only in `private/` files) and security controls (jail, spend gate, operator token, secrets). Never print or commit `.env`, `deploy/secrets/*`, the API key or the operator token. Never use a bare `git add -A` (`uv.lock` is deliberately untracked).

## 6. Environment and commands [fact]

```bash
cd ~/Projects/Hack_Agent_Readiness
git checkout research/llm-task-planning
# fresh environment (README.md): Python 3.12 + uv
uv venv --python 3.12 && uv pip sync requirements.lock && uv pip install --no-deps --no-build-isolation -e . && uv pip check
.venv/bin/python -m playwright install --with-deps chromium

# fast, relevant suites
.venv/bin/python -m pytest -q -p no:cacheprovider tests/test_suites_m1.py tests/test_taskeval.py tests/test_research_taskplan.py
.venv/bin/python -m pytest -q -p no:cacheprovider tests/test_framework.py tests/test_framework_evaluate.py tests/test_diagnostics.py tests/test_grader_v2.py tests/test_grader_v2_rescore.py tests/test_model_provenance.py -m "not browser"
bash scripts/critical-tests.sh                              # ~1 min
.venv/bin/python -m pytest -m "not browser and not slow" -q -p no:cacheprovider    # dev selection, ~8 min
# browser e2e (real Chromium; zero cost; do not run concurrently with other browser work)
.venv/bin/python -m pytest -q -p no:cacheprovider tests/test_framework_evaluate.py -m browser
# offline tools
.venv/bin/python -m agent_readiness.framework.generate larkspur
.venv/bin/python -m agent_readiness.research.taskplan.experiment --client fixture
```

## 7. Open questions [open]

- Whether `gate-nl-1` should live in taskeval-2 only, or also become a new versioned acceptance gate in `investigate/taskgen` (an owner decision if it would touch shared code).
- Default coverage targets are provisional (decision 3). Expect the owner to tune them after M3's first gap report.
- How human clarification of `natural_underspecified` tasks is captured (UI, file or CLI) is undecided; M4 should propose it.
- Pushing `research/llm-task-planning` to origin needs owner approval.
