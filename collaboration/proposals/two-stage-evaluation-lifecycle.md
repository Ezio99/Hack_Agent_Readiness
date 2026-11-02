# Proposal: two-stage evaluation lifecycle (task-suite design → frozen agent evaluation)

**Status:** architecture and minimal implementation plan for owner review. **Not implemented. No paid calls.** It is isolated from production and the frozen experiments, and post-dates the 2026-11-04 release freeze.

**Evidence base:**
- the planner experiment (17/20 deterministic with restatement, but only 6/20 with natural wording);
- taskeval-1;
- the Larkspur pilot (8 paid jailed trials);
- docs/FUTURE_ARCHITECTURE.md.

## 1. Principles

1. **Natural-language fidelity first.** The executed task should be what a customer would actually say. Restatement is a labelled fallback, not the default. Optimising for gate acceptance at the expense of wording is a failure mode to measure, not a goal.
2. **Selection blindness.** Stage A sees only the catalogue, business context, personas, journeys, snapshots and evaluator output. Agent trials, variant pass rates and desired comparison outcomes are never inputs. This is enforced by recorded input hashes, not by convention.
3. **Hard gates before soft scores.** Deterministic verifiability (oracle, graders, cross-variant fairness) is never overridden by relevance or realism scores, nor by any advisory LLM judge.
4. **Bounded effort, honest gaps.** Stage A has a round and budget limit and a stopping rule. If quality targets are not met, it reports the gaps; it never lowers the bar to fill a suite.
5. **Immutability and pre-registration.** Stage B runs only an approved, hash-frozen suite with a statistical plan fixed before execution. Anything decided after seeing results is labelled exploratory.

## 2. Lifecycle

```
                    ┌──────────────────── STAGE A: TASK-SUITE DESIGN (per site, per suite version) ───────────────────┐
 site definition ─► │ round r:  generator (LLM, versioned prompt)  ─►  taskeval-2 (code-only)  ─►  feedback synthesiser  │
 catalogue (verified)│            ▲   targets + structured feedback        hard gates / soft criteria     rejection categories,│
 business context    │            └──────────────────────────────────────  coverage matrix  ◄──────────  coverage gaps,       │
 personas, journeys  │   stop: targets met | max rounds | budget | no marginal gain       ─► candidate pool     duplicates      │
                    └───────────────────────────────────────────────────────────────────────────────┬────────────────────────┘
                                                              suite proposal + gap report ─► OWNER REVIEW ─► approved suite version
                    ┌──────────────────── STAGE B: FROZEN AGENT EVALUATION ─────────────────────────┴────────────────────────┐
                    │ evaluation manifest (immutable, hashed) = suite version × site variants × agent profile × model settings │
                    │   × request limits × graders × repetitions × randomisation × pre-registered comparison plan              │
                    │ zero-cost preflight (dev provider, jail) ─► approval ─► paid run (gate, ledger, jail) ─► results:         │
                    │   pre-registered verdicts | exploratory analyses | diagnostics (Phase 4) | provenance                    │
                    └──────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

## 3. Stage A design

### 3.1 Inputs (hashed into the suite record)
- **Site definition:** variants, snapshots, oracle.
- **Verified catalogue view:** attributes, domains, entities.
- **Business context,** labelled `synthetic` or `owner-provided`.
- **Personas and journeys,** each with priority weights.
- **Capability targets** (§3.3).
- **Generator configuration:** model, prompt version, schema version, reasoning effort, token limit.
- **Evaluator version and configuration.**
- **An explicit `agent_evidence_consulted: false`.** Stage A has no API for reading trial data.

### 3.2 taskeval-2: what changes from taskeval-1

| Check | Kind | Change |
|---|---|---|
| Grounding, answerable, unique, oracle agreement, grader v1/v2 compatibility, cross-variant fairness, evidence | hard | unchanged (reused) |
| **Natural-wording gate (proposed `gate-nl-1`)** | hard, for the executed wording | Every constraint *value* must be stated in the customer's words, and the stated values must map unambiguously to one attribute's domain. "Held on Saturdays" passes because Saturday belongs only to class day. "Under a tight budget" fails because no threshold is stated. It replaces the literal field-name requirement *for natural wording only*; the existing gate stays the official gate for frozen experiments. **Needs owner decision (§7).** |
| **Intent preservation** | hard if the restatement is executed | Criterion values must be traceable to the wording; the restatement may add field names but not new thresholds. Thresholds the generator introduced are recorded as `assumptions`. A task whose spec rests on an unstated assumption cannot run with natural wording. |
| Expressibility | hard | Classifies into deterministic, rubric or human review, with the reason. Extends to new criterion kinds only when they ship with oracle support (§5, M2b). |
| Ambiguity | hard | Gate ambiguity checks plus value collisions across attributes (the same value in two domains). |
| Business relevance | soft | Persona-to-attribute map and journey match. Owner-provided maps override synthetic ones. |
| Realism | soft | Question form, customer context, length, no internal field names, no catalogue jargon. Optional **advisory** LLM judge: recorded with its own provenance, can only lower confidence, never overrides a hard result, off by default. |
| Diversity and duplication | soft + hard | An identical criterion is a hard reject. Near-duplicate similarity, and capability and attribute spread, are soft. |

### 3.3 Coverage matrix and targets (per suite)

Cells are persona × journey. A capability axis is reported alongside:

| Capability | Description | Status |
|---|---|---|
| lookup | one fact of one named item | today |
| filter-1 | one condition | today |
| filter-n | several conditions | today |
| extremum | highest or lowest | today |
| constrained ranking | e.g. "cheapest beginner course" | needs extension |
| two-item comparison | | needs extension |
| either/or condition | | needs extension |
| policy (rubric) | | today |

Default targets (configurable, frozen into the suite record):
- every persona ≥ 2 tasks;
- every journey with weight ≥ 0.10 ≥ 1 task;
- ≥ 4 capabilities;
- ≥ 30 % multi-condition;
- **≥ 70 % of tasks executable in natural wording**;
- no near-duplicate pair above 0.6 similarity;
- suite size 8–12 deterministic tasks, plus ≤ 2 rubric tasks reported separately.

### 3.4 Feedback synthesiser (round r → r+1)

The synthesiser turns evaluator output into structured, answer-free guidance:
- **Rejection categories with counts and examples of wording only:** for instance, "3 proposals implied a threshold without stating it; state the amount or day in the customer's words", or "'category' is not a verified attribute".
- **Uncovered coverage cells:** "no task for professional_upskiller × check_availability".
- **Duplicates to avoid,** by criterion signature.
- **Capabilities still missing.**

It never passes expected answers, agent results or variant outcomes.

### 3.5 Stopping rule

Stop at the first of:
1. all targets met (§3.3);
2. **R_max = 3** rounds;
3. the Stage A budget cap is reached;
4. two consecutive rounds each add fewer than 2 new accepted tasks that fill an uncovered cell or improve natural-wording share.

On stopping:
- **Targets met:** the result is a suite proposal (the deterministic selection rule picks from the pool, maximising coverage; quality breaks ties).
- **Targets not met:** a gap report naming the uncovered cells, the dominant rejection causes, and which gaps need criterion-language extensions rather than more generation.

The owner approves, edits (manual tasks are run through the same evaluator), or rejects.

## 4. Stage B design

### 4.1 Evaluation manifest (immutable; content-hashed; write-once)

- **Suite:**
  - suite version id and hash;
  - per task: customer wording, executed wording (with a flag: natural or restated), structured specification, verifiability class, evidence requirements and request limits;
  - expected outcomes in **private records**, referenced by hash.
- **Identities:**
  - the oracle;
  - the graders: official version plus the post-hoc rescore versions allowed;
  - each site variant's snapshot sha256 and source fingerprint;
  - the catalogue and context fingerprints.
- **Agent:** model, endpoint, reasoning effort, max completion tokens, profile name and hash, parser, and jail policy hash.
- **Design:**
  - variants;
  - repetitions;
  - randomisation and counterbalancing seed;
  - task order;
  - stopping and void policy: no retries, and void trials excluded and listed.
- **Pre-registered comparison plan:**
  - primary metric (evidence-supported pass);
  - secondary metric (requests);
  - test (paired, task-level exact sign-flip over repetition means);
  - α;
  - minimum detectable effect;
  - **a power and feasibility check:** for example, exactly 4 task pairs can never reach p ≤ 0.10, so the plan must have enough tasks or repetitions;
  - holdout tasks, if any;
  - what counts as exploratory.
- **Budget:** worst-case reservation from frozen limits, hard cap, per-request cap, and approval record.

### 4.2 Execution and results

- **Runs:** the identical frozen suite on every variant.
- **Preflight:** a zero-cost run (dev provider, jailed) on the byte-identical manifest is required before the paid run.
- **Provenance per request:** model settings and profile hash (`provenance.model_provenance`).
- **Results are split into three labelled sections:**
  1. pre-registered verdicts;
  2. exploratory analyses;
  3. diagnostics (structural, behavioural, hypotheses, using the existing status rules).
- **Grading:** official grades never change. Rescoring is post hoc and labelled.

**Regression testing:** re-running an approved evaluation manifest on a new site snapshot creates a new manifest that differs only in snapshot fingerprints, with a diff report. A changed oracle answer for a task, for instance after a catalogue change, invalidates that task for the run, and the reason is listed.

## 5. Minimal implementation plan (isolated; reuse first)

| Milestone | Builds | Reuses | Tests and validation (zero cost unless stated) |
|---|---|---|---|
| **M1 Records and storage** | `SuiteRecord`, `TaskRecord` (three wordings, spec, private outcome ref, provenance, evaluation), `EvaluationManifest`; hashing; write-once store under `scanner-data/suites/` | `suite.core.canonical_hash`, freeze format | schema round-trip, immutability, private/public split |
| **M2 taskeval-2** | `gate-nl-1` (value-explicit natural-wording gate) as a *new versioned* check; intent preservation; capability classifier; coverage matrix | taskeval-1, research Verifier, oracle, gate v1, graders | adversarial wording tests (implied thresholds, value collisions, leaks); taskeval-1 results reproduced exactly when gate-nl-1 is off |
| **M2b Criterion extensions (optional, separate approval)** | `ranked_subset` (filter then extremum) and `either_of` conditions, each with oracle support and grader v2 keys | criteria, RecordOracle | oracle/page agreement on Ironbark and Larkspur; frozen experiments unaffected (new kinds only) |
| **M3 Stage A loop** | feedback synthesiser, round controller, stopping rule, gap report, per-round budget accounting | research planner (prompt v2 with feedback slot), schema v2, MetaClient gate | **multi-round fixture generator** (deterministic rounds that improve or stall) exercising every stop path |
| **M4 Approval and freeze** | owner approval record; manifest freezer with the pre-registered plan and power check | pilot `prepare`, freeze | the manifest is rejected if the power check fails or any task lacks private outcomes |
| **M5 Stage B runner** | generalise the pilot runner to any manifest and variant set; counterbalancing from the seed; pre-registered vs exploratory sections | pilot runner, `run_trial`, RequestGate, jail, rescore, provenance, diagnostics | zero-cost jailed run on Larkspur and Ironbark manifests; results byte-stable on re-render |
| **M6 Paid validation (approval required)** | Stage A on Larkspur (≤ 3 rounds), then one pre-registered Stage B evaluation | all | Stage A cost about US$0.025 per round, so ≤ US$0.10. Stage B priced from the frozen manifest *before* approval. As an illustration only, 8 tasks × 2 variants × 3 repetitions = 48 trials, about US$7 calculated, worst-case reservation about US$30. |

**Effort:** M1–M5 need about 3 working days with tests. M2b adds about 1 day.

**Isolation:**
- packages `agent_readiness/suites/` (Stage A and the store) and `agent_readiness/evalruns/` (Stage B), on a branch off `research/llm-task-planning`;
- nothing in `hosted/` imports them (an AST test, as for framework and diagnostics);
- frozen Ironbark experiments and grader v1 are untouched.

## 6. What this changes relative to the pilot

| Pilot | Lifecycle |
|---|---|
| single generation round | 2–3 rounds, with structured feedback |
| restated wording executed | natural wording preferred and measured (≥ 70 % target); restatement labelled |
| no comparison plan | pre-registered plan with a power check |
| ad-hoc artefacts | versioned suite and evaluation manifests with an approval step and a regression diff |

## 7. Decisions needed from the owner

1. **Natural-wording gate (`gate-nl-1`):** adopt it as a new, versioned gate for executed natural wording (values stated and domain-unambiguous; field names may be implied)? The existing gate stays for frozen experiments. *Recommended.*
2. **Restatement policy:** should restated wording be (a) never executed, (b) executed only as a separately labelled "assisted wording" condition, or (c) allowed as a per-task fallback? *Recommended: (b). Natural and assisted results are never pooled.*
3. **Coverage targets and stopping thresholds** (§3.3, §3.5): accept the defaults?
4. **Criterion-language extensions (M2b):** ranked subsets and either/or conditions are needed for realistic "cheapest beginner course" journeys. Build them now or later?
5. **Advisory LLM judge for realism:** off by default. Enable it (as a paid call) in M6?
6. **Stage B statistical default:** a task-level paired exact sign-flip over repetition means, with α = 0.10 and a minimum of 3 repetitions and 8 tasks. Or a different plan?
7. **Who approves suites:** the owner only, or delegated?
8. **Timing:** start after the 2026-11-05 submission?
