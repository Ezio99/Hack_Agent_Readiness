# Report: lifecycle M2–M5 (evaluator v2, new task kinds, Stage A loop, approval and freezing, Stage B runner)

**Date:** 2026-11-02. **Branch:** `research/llm-task-planning` (isolated research; not deployed, not merged). **Agent:** Claude Code (Opus), continuing from the M1 handoff (`6bdfe6c`, `2dae3a6`).
**Authorisation:** the owner authorised M2, M2b, M3, M4 and M5 as one continuous zero-cost run, and pushing this research branch. **No paid model or browser-agent call was made.** No deployment or merge was made, nothing was changed on `product-experience-redesign` / `evaluation-v2` / `main`, and no frozen experiment, ledger entry or official result was touched. Every approval in this work is of a **synthetic fixture suite**; no real suite was approved on the owner's behalf.

Design: [`collaboration/proposals/two-stage-evaluation-lifecycle.md`](../proposals/two-stage-evaluation-lifecycle.md). M1: [`lifecycle-m1.md`](lifecycle-m1.md).

## Commits

| Milestone | Commit | Tests added |
|---|---|---|
| M2 evaluator v2 | `c721c47` | `tests/test_taskeval_v2.py` (30, incl. the cross-process fingerprint test added in M5) |
| M2b ranked_subset / either_of | `5bc7892` | `tests/test_kinds_m2b.py` (8) |
| M3 bounded Stage A loop | `11e1a59` | `tests/test_stage_a_loop.py` (9) |
| M4 approval, freezing, plan, manifest | `258ec96` | `tests/test_lifecycle_m4.py` (12) |
| M5 Stage B runner and rehearsals | the commit adding this report | `tests/test_evalruns_m5.py` (7 fast + 1 browser) |

## 1. Implementation summary

### M2: evaluator v2 (`src/agent_readiness/taskeval/v2/`)

- **Layering, never relaxing v1.** Evaluator v1 (`taskeval/evaluator.py`) runs first and unchanged.
  - With the v2 checks disabled, its records are returned exactly. Parity is proven on the 20 recorded Muse Spark proposals and the 20 fixture proposals.
  - With the checks enabled, each v2 record embeds its v1 record untouched.
  - A candidate is admitted only if every v1 hard gate except `executable_wording_unambiguous` passed. That gate concerns the executed wording, which v2 chooses:
    - **natural:** the customer's words, through the v1 acceptance gate minus only its literal field-name rule. Length, blindness, compile, stability, yes/no, reachability, start-page leak, answer-in-question and entity naming all still apply.
    - **assisted:** v1's restated question, through the full v1 gate.
- **`gate-nl-1`** (`nl.py`, `lexicon.py`; versioned, code only).
  - Every specification component is traced to the customer wording (values, comparators, rankings, the looked-up fact), and every value the customer states is traced back to the specification (intent preserved both ways).
  - Field names may be implied, but only by a value or cue that maps to exactly one attribute of the verified catalogue.
  - Vague quantities ("a tight budget", "a few weeks", "several places") are detected and preserved as unresolved; they are never converted into numbers.
  - The lexicon maps phrases to attribute classes, comparators and directions, never to values. The one documented exception is the availability idiom "still has places", which means > 0 (definitional).
  - Negative context ("I work Monday to Friday", "don't want a beginner class") is recognised within a sentence. Definitional value sets ("weekends" = Saturday, Sunday) are recognised.
- **Four categories** (`suites.records.Wording`):
  - `natural_verifiable`: executed unchanged;
  - `natural_underspecified`: preserved, not executed, with what is unresolved;
  - `natural_judgment`: rubric or human review;
  - `assisted_restatement`: labelled, with every assumption recorded.

  An underspecified request may yield a separately labelled **assisted derivative** from the generator's stated assumption, or later from an owner clarification (M4). Assisted results are never pooled with natural ones.
- **Ambiguity classes:** value collisions across domains, cues that resolve to several attributes (e.g. "How much is X?" on Ironbark, which has four prices), and numbers with no identifiable field.
- **Coverage** (`coverage.py`):
  - a persona × journey matrix, counted only when the declared journey is consistent with the task's attributes;
  - a capability axis (lookup, single and multi-condition filter, extremum, ranked_subset, either_of, policy rubric);
  - diversity (criterion-signature similarity);
  - the provisional targets of §3.4, with a gap list.

  The natural-wording share is reported as an aspirational metric, not an admission rule.
- **Records:** `suites/stage_a/taskrecords.py` maps every admitted record one-to-one onto M1 `TaskRecord` / `PrivateOutcome`. The module lives in Stage A because the M1 isolation rule forbids `taskeval` from importing `suites`.
  - Public evidence paths are limited to pages the criterion itself names.
  - Full evidence paths (which name answer items for set and ranking tasks) stay private.
- **Finding:** the v1 public view (`taskeval.evaluator.public`, unchanged) keeps evidence page paths. For set tasks these name the answer items' pages. The v2 public view withholds them (tested).

### M2b: ranked_subset and either_of (`taskeval/v2/kinds.py`, `research/taskplan/schema_v3.py`)

- **Kinds.** `ranked_subset` (filter, then the highest or lowest) and `either_of` (2–4 alternatives on one text attribute, optionally AND 0–2 conditions).
  - Each has compile (from the frozen pages), a record oracle (from source data), an acceptance gate, grader v1 support (the unchanged `criteria.grade` on the compiled truth) and grader v2 keys (`build_key_any`, the same extractors).
  - Ill-posed instances are refused: ties, a filter selecting all items or fewer than 2, and a degenerate either/or.
- **Nothing shared was modified.** `criteria.py`, `gate.py`, `grading/key.py`, `grading/v2.py`, `framework/oracle.py`, `taskeval/evaluator.py`, `select.py`, `verify.py`, `schema.py` and `freeze.py` are pinned by SHA-256 in `tests/test_taskeval_v2.py`.
  - Every new function delegates existing kinds to the v1 code.
  - The v1 gate still refuses the new kinds as malformed (tested).
  - The replica gate used for the new kinds returns exactly what gate v1 returns on a corpus of existing-kind drafts (tested).
- **Oracle and compile agreement** on every systematically generated instance:
  - Larkspur: 317 instances, 197 compiled, 120 refused;
  - Ironbark: 253 instances, 123 compiled, 130 refused.

  Every compiled instance is reproduced exactly by the oracle and is stable across both variants. The only disagreements are 3 Ironbark instances that compile refuses and the oracle answers (the safe direction: no task is created). They come from v1's unit comparison ("1 day" vs "2 days"), which v1 `item_set` shares.
- **Wire schema v3** adds `one_of`. Schema v1/v2 and `parse_item` are unchanged, and every v1-valid proposal parses identically. The kinds are enabled by evaluator configuration (`new_kinds`; off by default).

### M3: bounded Stage A loop (`suites/stage_a/`)

- **Round controller** (`loop.py`). Each round runs:
  1. prompt `taskplan-v2` (`research/taskplan/planner_v2.py`: v1 rules plus natural-wording guidance, the M2b shapes and a feedback slot; `taskplan-v1` unchanged);
  2. evaluator v2, cumulative over all candidates so that earlier admissions never change;
  3. selection-2;
  4. coverage of the selection;
  5. the stopping rule;
  6. the feedback synthesiser.
- **Limits:** at most 3 rounds by default; the budget cap is checked against the next round's worst-case reservation before it is sent; no retries.
- **Stopping** (`stopping.py`): `targets_met`, `max_rounds`, `diminishing_returns` (two consecutive rounds each adding fewer than 2 useful tasks), or `budget_cap`. Targets and acceptance thresholds are never lowered; unmet targets go to the gap report.
- **Feedback** (`feedback.py`) contains:
  - rejection categories with counts and wording-only examples;
  - uncovered cells and missing capabilities;
  - signatures to avoid;
  - underspecified wordings with the standing advice.

  It never contains expected answers. Wording examples are never echoed for rejections that cite the answer: the gate refuses such a candidate before deriving its answer, so it cannot be scrubbed, and echoing it would confirm the answer. This was a real leak path found and closed during the work.
- **Selection-2** (`selection.py`): deterministic, using evaluator records only.
- **Output:** an **unapproved** `SuiteRecord` proposal plus `TaskRecord`s and private outcomes in the store, and a write-once run directory. The directory preserves:
  - generation settings, prompt and schema versions, request hashes;
  - raw responses and proposals;
  - public and private evaluator records, rejection reasons;
  - feedback per round, coverage, the gap report and provenance.
- **Generators:**
  - `RoundsFixture` and `FeedbackFixture`: developer-written, NOT model output, zero cost. `FeedbackFixture` reads the feedback slot and answers the named gaps.
  - The paid `MetaGenerator` lives in `planner_v2.py`, outside Stage A, because it needs the agent's model configuration, which the boundary forbids. It refuses without an owner approval note.
- **Boundary:** Stage A is clean directly (AST) and transitively; importing the loop loads no forbidden module (tested in a subprocess).

### M4: approval, freezing, statistics, manifests

- **Approval workflow** (`suites/stage_a/approval.py`):
  - `review_packet`: public, with no answers; Markdown rendering with a checklist.
  - `decide`:
    - the owner types an exact attestation naming the decision and the full suite hash;
    - a **non-synthetic suite can only be decided at an interactive terminal**, so no automated process (agent, CI) can approve or reject one;
    - synthetic fixture decisions are labelled as test decisions in the record.
  - `freeze`: the store requires an approved approval of the exact hash; a write-once ref `name@vN` is created.
  - `revise`: a new version and hash referencing the old one, with coverage recomputed; the old approval does not apply.
  - `clarify` (proposed answer to the handoff's open question): an owner clarification of an underspecified request is re-validated by evaluator v2 and becomes an assisted task whose assumption names who clarified it and when. The customer's wording is kept, and it never becomes natural.
  - CLI: `python -m agent_readiness.suites.stage_a.approval review|decide|freeze`.
- **Statistical plan** (`suites/plan.py`; α = 0.05 by default).
  - Repetitions are aggregated per task and variant, and tasks are the unit of analysis.
  - The test is the exact two-sided sign-flip over per-task paired differences, computed exactly by dynamic programming (pure Python, deterministic).
  - Feasibility: the minimum achievable p is 2/2ⁿ, so n ≥ 6 is needed; Monte Carlo power and the minimum detectable effect are computed under explicitly stated assumptions (baseline, effect, between-task SD on the logit scale).
  - A confirmatory designation is refused when infeasible, unless an explicit exploratory fallback is allowed, in which case the fallback is recorded. 8 × 3 is not assumed sufficient: at effect 0.25 its power is ≈ 0.11.
  - Pre-registration checks are applied to every manifest.
- **Manifest builder** (`evalruns/manifest.py`). It records:
  - the frozen suite by hash;
  - variants with snapshot hashes;
  - conditions (natural first, assisted separately);
  - oracle and graders (v1 official, v2 post-hoc, with code hash);
  - the **real** agent configuration a paid run would use (`muse-spark-1.3`, endpoint, reasoning effort, completion cap, profile and hash, jail-policy hash);
  - repetitions and seed;
  - the plan;
  - a worst-case budget, with paid approval `null`.

  Regression manifests share the same frozen suite, plan and agent and differ only in variants and the budget they imply; a diff is produced, and any other difference is refused.

### M5: generalised Stage B runner (`src/agent_readiness/evalruns/`)

- **`prepare`.**
  - It creates one standard investigation run **per wording condition** (never pooled), holding the base snapshot and profile, a tasks-manifest whose questions are the frozen executed wordings, and the frozen private outcomes.
  - It also writes **snapshot-specific manifests** per variant. The frozen answer must re-derive on that snapshot and the executed wording must still pass its gate (`gate-nl-1` rules for natural, the full v1 gate for assisted); otherwise the task is invalidated for that variant, with the reason.
- **`execute`.** It runs the unchanged `run_trial`:
  - real Chromium in the network jail (`jail.require()` plus a self-test, with process state restored afterwards);
  - the reserve-before-send `RequestGate` with the manifest's per-request and per-trial caps;
  - the pinned loopback dev provider;
  - counterbalancing from the manifest seed, no retries, and a halt on a void trial or a bound violation.

  **Paid mode is refused** pending M6, and the manifest hash is identical between rehearsal and paid mode (tested).
- **`report`.**
  - Official grader v1 grades as recorded; post-hoc grader v2 via `grading.rescore` (faithfulness check), plus `build_key_any` for the new kinds.
  - Per-condition tallies and the per-task paired analysis under the pre-registered plan, in separate `preregistered` / `exploratory` / `diagnostics` sections. Diagnostics are advisory and only computed when the variants are the site's own.
  - `RunResult` records in the store, with an evidence-directory hash.
  - A public view with no answers.
- **`audit_public`.** It scans every public artefact for expected answers:
  - store objects: each task is checked for its own answer; suites, approvals, frozen suites, manifests and run results are checked for any answer;
  - each run's public artefacts;
  - the public reports.

  It is also proven to catch an injected leak.
- **`rehearse.py`.** The full zero-cost chain per site; see §4.

## 2. Branch status

- `research/llm-task-planning`: M2 `c721c47` → M2b `5bc7892` → M3 `11e1a59` → M4 `258ec96` → M5 and docs (final commit). Pushed to `origin` with the owner's authorisation, without merging.
- Untouched: `product-experience-redesign` `820e0ad` (release candidate), `evaluation-v2` `bf55db7` (production runs `140a4e8`), `main`.
- The untracked owner prototype files (`src/agent_readiness/investigate/prototype/`, `tests/test_termvalue_prototype.py`) were left as they were and never staged.

## 3. Tests run (all local, zero cost)

| Suite | Result |
|---|---|
| Baseline before any change: `test_suites_m1.py` + `test_taskeval.py` + `test_research_taskplan.py` | 59 passed |
| Baseline `scripts/critical-tests.sh` | 214 passed, 17 deselected |
| `test_taskeval_v2.py` (M2) | 29 passed |
| `test_kinds_m2b.py` (M2b) + frozen-artefact suites (`test_term_value`, `test_ab_experiment`, `test_remediation_main_design`, `test_framework`, `test_investigate_taskgen`, non-browser) | 108 passed |
| `test_stage_a_loop.py` (M3) | 9 passed |
| `test_lifecycle_m4.py` (M4) | 12 passed |
| `test_evalruns_m5.py` (M5, fast) | 7 passed |
| `test_evalruns_m5.py -m browser` (real Chromium, jail, dev provider) | 1 passed (63 s; run alone) |
| All lifecycle suites together (M1, taskeval v1, taskplan, M2, M2b, M3, M4, M5 fast) | 126 passed; with framework, framework-evaluate, diagnostics, graders, provenance and frozen-artefact suites: 269 passed, 5 deselected (browser) |
| `scripts/critical-tests.sh` after every milestone | 214 passed, 17 deselected (M2, M2b, M3, M4, M5) |

## 4. Zero-cost end-to-end rehearsals

**Run:** `python -m agent_readiness.evalruns.rehearse SITE --root scanner-data/research/lifecycle/<dir>`. All outputs are git-ignored.

**Chain:**
1. Stage A loop with a developer-written fixture generator (NOT a model);
2. review packet, then a SYNTHETIC approval and freeze;
3. pre-registered plan;
4. manifest declaring the real agent configuration;
5. Stage B in real Chromium inside the network jail (self-test passed for every run), with the loopback dev provider (NOT a model; scripted from the frozen tasks, so it "answers correctly" by construction);
6. official grader v1, post-hoc grader v2, RunResult records, leak audit.

**Zero money.** These prove the pipeline, not agent or website performance.

**Larkspur** (`scanner-data/research/lifecycle/rehearsal-larkspur-20261102b`)

Hashes: suite `356e00cb…`, frozen `49d052ba…`, manifest `3447f692…`.

- **Stage A:**
  - `FeedbackFixture`: round 1 had 10 intents (5 natural admitted, 4 rejected: a duplicate, an answer leak, a hallucinated attribute, a dropped constraint; 1 preserved underspecified + 1 assisted derivative).
  - The feedback named the uncovered cells and missing capabilities (ranked_subset, either_of, extremum, policy rubric). Round 2 drew 8 intents for exactly those gaps.
  - Stopped at **`targets_met` after 2 rounds**.
  - Suite: 12 natural tasks (1 lookup, 2 single-condition filters, 5 multi-condition filters, 3 either_of, 1 ranked_subset); natural share 1.00.
  - Gap report: the preserved "a few weeks" request.
- **Plan:** confirmatory requested and refused as infeasible. Minimum p 0.00049 is fine, but power is 0.07 at effect 0.25 for 12 tasks × 1 repetition, so the plan is **exploratory**, with the fallback recorded.
- **Budget:** worst case US$14.784 against the US$5 cap (`within_cap: false`). Recorded; a paid run would need a smaller design or an approved cap.
- **Base manifest** (original vs modified): **24/24 trials executed**, 0 void, no halt.
  - v1 passed 12/12 and v1 evidence-backed 12/12 on each variant; v2 likewise. v2 keyed every kind, including either_of and ranked_subset.
  - Rescore faithful. 66 dev-provider requests per variant.
  - Exploratory analysis: 12 pairs, mean difference 0, p = 1.0 (expected: the stand-in answers both variants identically).
  - 2 RunResult records. Diagnostics: 17 findings, all labelled hypothesis or unverified.
  - **Leak audit clean** (22 public artefacts × 13 answers).
- **Regression manifest** `16994dab…`: the same frozen suite on `modified` plus a new snapshot `release2` (one fee changed: Mindful meditation $120 → $265).
  - The diff changes **only `variants`**; the frozen suite is identical.
  - **4 tasks were invalidated on `release2` with reasons:**
    - 3 × "the expected answer changed on this snapshot";
    - 1 × the weekend either/or became degenerate (no Sunday course under $200).
  - The remaining **20/20 trials executed** (12 on modified, 8 on release2), all passing v1 and v2 with evidence.
  - Leak audit clean (25 artefacts). Diagnostics correctly reported as unavailable, because the snapshots are not the site's registered variants.

**Ironbark** (`scanner-data/research/lifecycle/rehearsal-ironbark-20261102`)

Hashes: suite `d699b3e7…`, frozen `3b09ad26…`, manifest `3ea012f0…`.

- **Stage A:**
  - Synthetic Ironbark context; `RoundsFixture` with a 1-round limit, so it stopped at **`max_rounds`**.
  - Suite: 9 natural and **2 assisted** tasks (2 lookups, 5 single-condition filters, 1 multi-condition filter, 1 extremum, 2 ranked_subset). The assisted tasks are the derivatives of "How much is the Petrol chainsaw?" (ambiguous between 4 prices) and "cheap to hire" (vague).
  - Gap: multi-condition share 0.09 < 0.30, reported, not filled. Either/or is impossible on this catalogue.
- **Plan:** exploratory (power 0.03). Worst case US$13.024.
- **Stage B:** **two separate runs, natural (18 trials) and assisted (4 trials), never pooled**. All 22 executed, 0 void.
  - Natural: v1 passed 9/9 per variant, evidence-backed 8/9. Assisted: passed 2/2, evidence-backed 1/2. v2 is identical to v1.
  - The missing evidence credit is the known stand-in limitation: the scripted agent does not scroll Ironbark's long listing, and the evidence rule correctly refuses to credit unseen answers (as in Phase 3).
  - Rescore faithful for both conditions. 4 RunResult records. Diagnostics: 21 natural-condition findings (hypothesis or unverified).
  - **Leak audit clean** (26 artefacts × 11 answers).

**First attempt (kept as evidence, `…-attempt1`).** All 24 base trials ran, then reporting crashed. That attempt surfaced two bugs, both fixed before the clean re-run:
1. `grading.rescore.rescore_run` cannot be used with the new kinds: v1 `compile_criterion` raises a validation error, not `KeyError_`. The runner now uses rescore's own row grader with `build_key_any` keys; `rescore.py` is unchanged. A fast regression test was added.
2. The evaluator fingerprint depended on Python's per-process hash randomisation (a set in the lexicon), so suite hashes were not reproducible across processes. It is now sorted. The suite, frozen-suite and manifest hashes were verified identical under `PYTHONHASHSEED` 1, 2 and 3 on both sites, and a cross-process test was added.

The resume safeguard (the re-derived suite must equal the recorded one) caught the second bug.


## 5. Natural-language fidelity and coverage metrics

The gate-v1 figure is evaluator v1's `natural_wording_passes_gate`.

| Proposal set | gate v1, natural wording | v2: natural_verifiable | natural_underspecified (+ assisted derivatives) | natural_judgment | rejected | natural share of executable tasks |
|---|---|---|---|---|---|---|
| 20 recorded Muse Spark proposals, M2 | 6 / 20 | **12** | 5 (+5) | 1 | 2 (ranked within a filter: not expressible before M2b) | 12 / 17 = 0.71 |
| 20 recorded Muse Spark proposals, M2b | 6 / 20 | **13** | 6 (+6) | 1 | 0 | 13 / 19 = 0.68 |
| 20 fixture proposals, M2b | n/a | 9 (the 8 v1 passes + 1 ranked) | 0 | 2 | 9 (all by v1 hard gates or schema) | 1.00 |
| Larkspur Stage A pool (26, developer-written) | n/a | 18 | 1 (+1) | 2 | 5 (duplicate, leak, hallucinated attribute, dropped constraint, duplicate) | 0.95 |
| Ironbark Stage A pool (12, developer-written) | n/a | 9 | 2 (+2) | 0 | 1 (answer visible on the start page) | 0.82 |

**The 6 recorded proposals that v2 preserves as underspecified** are:
- "don't cost too much";
- "under a tight budget";
- "something affordable … low cost";
- "a short course that won't cost much";
- "several places left";
- "only last a few weeks".

In each, the generator had silently chosen a threshold ($300, $180, $250, 6 weeks / $200, ≥ 5 seats, ≤ 4 weeks). The thresholds are now recorded as assumptions of labelled assisted derivatives, never as the customer's request.

Coverage of the selected rehearsal suites:

| Suite | Deterministic | Natural share | Capabilities | Multi-condition share | Targets met | Gaps |
|---|---|---|---|---|---|---|
| Larkspur rehearsal | 12 | 1.00 | 5 of 7 (lookup, single and multi-condition filter, ranked_subset, either_of; no extremum or policy rubric selected) | 0.58 | yes | none (1 preserved underspecified request) |
| Ironbark rehearsal | 11 | 0.82 | 5 of 7 (either_of impossible; no policy rubric) | 0.09 | no | multi-condition share 0.09 < 0.30 |

## 6. Limitations and unresolved issues

- **The lexicon is heuristic and English-only.** It was tuned on 58 wordings, and its errors are conservative in direction: a missed value makes a task assisted or underspecified; it never invents one. Unknown phrasings ("budget-friendly", "on the cheaper side") fall back to `added_assumption` (assisted) or are missed as vague cues. It needs review on real generator output (M6) and a broader adversarial corpus. Words that double as domain values in other senses (e.g. "in advance" vs level Advanced) can produce a false "unrepresented value" rejection.
- **Negative context is a 4-token window inside a sentence.** Constructions such as "anything but Monday" with the value far from the cue are not handled.
- **v1 limitations inherited, not fixed:**
  - the unit comparison treats "1 day" and "2 days" as incomparable (Ironbark minimum hire);
  - the start-page leak rule is a naive substring check (e.g. truth "1" inside "14 courses"), which rejects some valid lookups;
  - the v1 verifier reads the Larkspur context module global. v2 supplies the configured context through it for the v1 call; this is the identity on Larkspur.
- **Soft scores.** Novelty and quality are pool-relative and are recomputed as rounds add candidates (admission, category, gates and wording never change; tested). Persona relevance uses v1's Larkspur-only persona map, so it is meaningless on Ironbark (soft only).
- **The feedback synthesiser withholds known answers** and never echoes answer-leak wordings. It still echoes rejected or underspecified customer wordings, which the generator wrote itself.
- **Coverage targets are the provisional defaults.** The rehearsal pools were written to reach them; with real generator output, expect gaps.
- **Ironbark** cannot express either/or: its only text attribute has two values, so an OR of both selects everything. This is reported as a capability gap.
- **The statistical plan's power is simulated under assumptions.** For the rehearsal suites (12 natural tasks, 1 repetition) the plan is correctly **exploratory**. A confirmatory design needs many more tasks or repetitions: for example 24 tasks × 3 repetitions at an assumed effect of 0.45 and low between-task variance.
- **Worst-case budget.** For 12 tasks × 2 variants × 1 repetition at US$0.044 per request, the worst case is ≈ US$14.8 against a US$5 cap (`within_cap: false` in the manifest). A paid Stage B run therefore needs either fewer tasks or a higher, explicitly approved cap.
- **The dev provider is a scripted stand-in.** On Ironbark it does not scroll the long listing, so evidence-supported passes are lower there (as in Phase 3). Rehearsal grades prove the pipeline, not agent or website quality.
- **Approval guard.** The interactive-terminal requirement prevents automated decisions; it is not authentication. A real deployment needs an authenticated owner identity.
- **Diagnostics** reuse `diagnostics.run.from_framework_run`, which re-validates variants with the v1 gate. For natural-wording and M2b tasks it falls back to the base private records. They are advisory, and absent for regression manifests that use non-registered snapshots.
- **Not built:** the advisory LLM realism judge (deferred by decision 5); M6 (paid validation; separate approval).

## 7. Instructions for a real LLM generation experiment (M6; NOT executed)

**Needs explicit owner approval, a stated cap and an approval note.** Nothing below has been run.

1. **Stage A (one paid generation, ≤ 3 rounds).**
   - Generator: `research.taskplan.planner_v2.MetaGenerator(ledger_dir, approval_note=..., run_cap_usd=0.10, max_requests=3)`.
   - Model settings: `muse-spark-1.3`, `reasoning_effort` `low`, `max_completion_tokens` 6000, prompt `taskplan-v2`, schema `taskplan-schema-v3`, 12 tasks per round.
   - Loop: `suites.stage_a.loop.run(site, view, X.CONTEXT, gen, config=LoopConfig(suite_name="larkspur-core", stop=StopRule(budget_cap_usd=0.10)), created_at=..., out_dir=scanner-data/research/stage-a/<run>, store=WriteOnceStore(...))`.
   - **Estimated maximum: US$0.091.** The worst-case reservation is computed locally: round 1 US$0.029344, a feedback round about US$0.03035, 3 rounds ≤ US$0.091. The cap is US$0.10. Paid run 2 of the v1 planner cost US$0.024 calculated.
   - Preflight: checked locally. `json_schema_v3` uses only JSON-Schema keywords Meta has already accepted live (`PROVEN_KEYWORDS`), and every object is strict (all properties required, `additionalProperties: false`). A live structured-output acceptance check of the v3 schema has not been made; it is part of M6.
2. **Owner review.** `python -m agent_readiness.suites.stage_a.approval review STORE SUITE --markdown`. The owner then decides at a terminal (`decide …`), optionally clarifies underspecified requests (`clarify` → `revise`), and freezes (`freeze`).
3. **Stage B (one paid evaluation).**
   - Build the manifest with `evalruns.manifest.build` and a plan from `suites.plan.make_plan`. Expect exploratory designation at this scale.
   - Rehearse the byte-identical manifest first: `evalruns.runner.prepare(..., mode="rehearsal")` → `execute` → `report` → `audit_public`.
   - Recommended exploratory design within the existing US$5 cap: **8 trials**, e.g. 4 natural tasks × 2 variants × 1 repetition. Worst case ≈ Σ max_model_requests × US$0.044 ≈ US$4.9; expected ≈ US$1.2 calculated, based on the Larkspur pilot's US$1.23 for 8 trials.
   - Alternatively, 12 natural tasks × 2 variants × 1 repetition. This needs a cap of ≈ US$15 worst case (expected ≈ US$3.7), still exploratory.
   - The paid mode is deliberately refused today: M6 must add an explicit approval check (approval note, cap, manifest hash) before `execute` will run with `mode="paid"`, and append to the programme ledger only with owner authorisation.
4. **Programme budget.** The known subtotal is US$11.848482 / A$17.7727 of the A$50 limit, so ≈ A$32 remains. The A$50 ceiling is a limit, not an authorisation.

## 8. Readiness for a live frozen-suite demonstration

**The lifecycle machinery is ready for a live frozen-suite demonstration on Larkspur, pending owner decisions. It is not ready to be described as validated with a real agent.**

**Ready (demonstrated at zero cost on both controlled sites):**
- Generation with feedback, independent validation, natural-wording classification, approval and freezing.
- Manifest construction with a pre-registered plan.
- Jailed Stage B execution with official and post-hoc grading.
- Snapshot-specific re-evaluation with invalidation.
- A leak-free public output.
- The paid path refuses to run until approved.

**Required before a live demonstration (owner decisions, not engineering gaps):**
1. Approve M6 with a cap, and decide the design: about 8 trials within US$5, or 24 trials at a worst-case cap of about US$15.
2. Run one paid Stage A generation, or approve the fixture-generated suite as a demo suite. A demo suite would be a real approval at a terminal; the existing approvals are synthetic only.
3. Add the M6 paid-mode approval check to `evalruns.runner.execute` (a small change, deliberately not made without approval).

**Caveats for any live claim:**
- With 8–12 tasks and 1 repetition, results are exploratory by the pre-registered rule.
- Natural and assisted results must be reported separately.
- The lexicon has not yet seen real `taskplan-v2` output.

**Hackathon priority.** The research branch does not touch the deployed product. The production release (`evaluation-v2` @ `140a4e8`, rollback images) remains the hackathon fallback. Nothing here should be merged or deployed before the 2026-11-05 submission without the owner's explicit decision.
