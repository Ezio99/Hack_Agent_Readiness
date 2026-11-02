# Two-stage evaluation lifecycle (task-suite design → frozen agent evaluation)

**Status:** approved by the owner 2026-11-02. Implementation starts with the proposal update and M1 only; later milestones need review after M1.

**Isolation:** branch `research/llm-task-planning`. The hackathon release candidate, the deployed service and existing frozen experiments (grader v1, evaluator v1, the hosted Ironbark evaluation) are not modified. No paid LLM or browser calls and no deployment without separate approval. **The 2026-11-05 submission takes priority;** Wednesday 2026-11-04 is the submission-readiness checkpoint.

**Evidence base:**
- the planner experiment (17/20 deterministic with restatement; 6/20 with natural wording);
- taskeval-1;
- the Larkspur pilot (8 paid jailed trials);
- docs/FUTURE_ARCHITECTURE.md.

**Product workflow this implements:** business context and catalogue → LLM task generation → independent validation and refinement → **human approval** → **frozen suite** → live agent evaluation → evidence-linked diagnostics → targeted website improvement → **re-evaluation against the same frozen suite**. A frozen suite is reusable across repeated live evaluations and website variants. Live execution references the frozen manifest and never regenerates tasks.

## 1. Approved decisions (2026-11-02)

| # | Decision | Status |
|---|---|---|
| 1 | **Natural-wording gate.** A separate, versioned evaluator-v2 check. Evaluator v1 and the frozen experiments stay unchanged. | approved |
| 2 | **Restated wording.** Only as a separately labelled *assisted-wording* condition. Assisted and natural-wording outcomes are never pooled. | approved |
| 3 | **Coverage and stopping.** At most three generation rounds, with the proposed coverage targets, a budget cap, a diminishing-return stopping rule and explicit gap reports. Acceptance thresholds are never lowered to fill a suite. | approved provisionally |
| 4 | **New task kinds.** Ranked-within-a-filter and either/or, built in M2b (after M2), with independent oracle and grader support. | approved |
| 5 | **Advisory LLM realism judge.** Off by default; deterministic checks and human review come first. | deferred |
| 6 | **Statistical plan.** Revised (§4.2): α = 0.05 confirmatory, clustering-aware, feasibility or power assessment required, pre-registration, and underpowered studies run as exploratory. | revised |
| 7 | **Suite approval.** Human approval is required, initially by the owner. Approval precedes immutable freezing; substantive edits create a new version that needs reapproval. | approved |
| 8 | **Timing.** Begin now with the proposal update and M1; review after M1. Supersedes the earlier post-submission and Wednesday-start restrictions. | approved |

## 2. Principles

1. **Natural-language fidelity.** Prefer what a customer would actually say. Preserve genuine customer ambiguity. Never silently invent numeric thresholds or constraints.
2. **Strict separation of Stage A from Stage B outcomes.** Task design and selection never see agent trials, variant pass rates or desired comparison outcomes. This is enforced through imports, record schemas and store references (§3.6), not by convention.
3. **Hard gates before soft scores.** Deterministic verifiability (oracle, graders, cross-variant fairness) is never overridden by relevance or realism scores.
4. **Bounded effort, honest gaps.** Stage A has round and budget limits and a stopping rule. If quality targets are not met, it reports the gaps.
5. **Immutability and pre-registration.** Stage B runs only an approved, hash-frozen suite with a statistical plan fixed before execution. Anything else is exploratory.

## 3. Stage A: task-suite design

### 3.1 Loop

Each round runs: generator (LLM, versioned prompt) → evaluator v2 (code only) → feedback synthesiser → next round. It stops when:
- the targets are met; or
- 3 rounds are complete; or
- the budget cap is reached; or
- two consecutive rounds each add fewer than 2 accepted tasks that fill an uncovered cell or improve natural-wording share.

The output is a suite proposal plus a gap report, which goes to human approval.

**Inputs, hashed into the suite record:**
- site definition (variants, snapshots, oracle);
- verified catalogue view;
- business context, labelled `synthetic` or `owner-provided`;
- personas and journeys with weights;
- capability targets;
- generator configuration;
- evaluator version and configuration.

### 3.2 Natural-language classification (amendment)

Every candidate's customer wording is classified into exactly one of four categories:

| Category | Meaning | Executed as | Scoring |
|---|---|---|---|
| **natural_verifiable** | the customer's own wording states every value the criterion needs, unambiguously | the customer wording, unchanged | deterministic, natural-wording condition |
| **natural_underspecified** | the intent is clear but a value is missing, e.g. "under a tight budget" or "a few weeks" | **not** executed deterministically as is; recorded as needing clarification. Genuine ambiguity is preserved, never resolved by an invented threshold | excluded from deterministic scoring. It may become an *assisted* task only if a clarification is explicitly recorded (by a human, or as a labelled assisted restatement). |
| **natural_judgment** | an answer that needs judgment, e.g. "which course would best set me up for IT" | the customer wording | rubric or human review; never deterministic |
| **assisted_restatement** | the customer wording plus an explicit restatement (may add field names; any added value is a recorded assumption) | the restated text, **labelled `assisted`** | deterministic, assisted condition only; never pooled with natural |

Each task record preserves the original customer wording, the executed wording, the category, **interpretation decisions** (for example "field name implied by a value unique to the class-day domain"), **assumptions** (any value not stated by the customer), validation reasons and provenance.

The **70 % natural-wording execution** figure is an **aspirational development metric** reported per suite. It is **not** an admission requirement.

### 3.3 Evaluator v2 (built in M2; versioned; v1 unchanged)

- **Hard checks (unchanged from v1):** grounding, answerable, unique, oracle agreement, grader v1/v2 compatibility, cross-variant fairness, evidence.
- **New `gate-nl-1`:** every constraint value is stated in the customer's words and maps unambiguously to one attribute domain; field names may be implied. It replaces the literal field-name requirement for natural wording only. The existing gate stays for frozen experiments.
- **New intent preservation:** criterion values must be traceable to the wording. Anything else is an assumption, and it forces the assisted or underspecified category.
- **Ambiguity classification:** gate ambiguity, value collisions across domains, and missing values (underspecified).
- **Soft criteria (rank only, never admit):** business relevance, realism, diversity.

### 3.4 Coverage targets (provisional; frozen into each suite record)

- Persona × journey cells, plus a capability axis: lookup, single-condition filter, multi-condition filter, extremum, ranked-within-a-filter (M2b), either/or (M2b), policy rubric.
- Defaults:
  - every persona has ≥ 2 tasks;
  - every journey with weight ≥ 0.10 has ≥ 1 task;
  - ≥ 4 capabilities;
  - ≥ 30 % multi-condition;
  - no near-duplicate pair above 0.6 similarity;
  - 8–12 deterministic tasks, plus ≤ 2 rubric tasks reported separately.

### 3.5 Feedback synthesiser

Feedback contains:
- rejection categories with counts and wording-only examples;
- uncovered cells;
- duplicate signatures to avoid;
- missing capabilities;
- underspecified wordings, returned as "state the value in the customer's words, or keep the ambiguity and mark it".

It never contains expected answers, agent results or variant outcomes.

### 3.6 Stage A / Stage B boundary (implemented in M1)

- **Imports:** Stage A modules may not import trial execution, agent results, diagnostics of trials, grading rescore or the pilot runner. An AST test checks this.
- **Data:** Stage A records accept inputs only of allowed kinds (catalogue, context, site, generator, evaluator, suite). References to runs, trials or results are rejected when a record is built and when it is written to the store.
- **Freezing:** freezing requires a human approval of the exact suite content hash. Any substantive edit changes the hash, so the old approval no longer applies.
- **Stage B:** Stage B records reference a frozen suite by hash and cannot modify it.

## 4. Stage B: frozen agent evaluation

### 4.1 Evaluation manifest (immutable, content-hashed, write-once)

- the frozen suite reference;
- per task: customer wording, executed wording, wording category and condition (natural or assisted), structured specification, verifiability class, request limits, evidence requirements; expected outcomes in **private records** referenced by hash;
- oracle and grader identities (official version, plus the post-hoc rescore versions allowed);
- site variant snapshot and source fingerprints;
- model, endpoint, reasoning effort, max completion tokens, agent profile name and hash, jail policy hash;
- design: variants, repetitions, randomisation and counterbalancing seed, void policy (no retries);
- task selection rule;
- the **pre-registered statistical plan**;
- budget (worst-case reservation, hard cap, per-request cap) and approval references.

### 4.2 Statistical plan (revised per decision 6)

- **Confirmatory α = 0.05** by default, two-sided.
- **Repeated trials are clustered within tasks.** Repetitions of a task are not independent units. The default analysis aggregates repetitions per task and per variant, compares variants within task (paired), and treats **tasks as the unit of analysis**. Any trial-level model must account for the clustering, for example with task-level random effects or cluster-robust inference.
- **Feasibility or power is required** for the actual paired design before a study can be confirmatory:
  - the minimum achievable p-value of the chosen test with the planned number of tasks must be ≤ α. For an exact two-sided sign-flip test over *n* task pairs that minimum is 2/2ⁿ, so *n* ≥ 6 at α = 0.05; this is necessary, not sufficient;
  - plus a stated minimum detectable effect, or power estimate, under assumed between-task variability.

  No size, including 8 tasks × 3 repetitions, is assumed sufficient.
- **Pre-registered before execution:** primary outcome, comparison rule, repetitions, analysis, stopping rule, and the confirmatory or exploratory designation.
- **Underpowered or infeasible studies may proceed as exploratory,** with no confirmatory claims; results are labelled accordingly.

### 4.3 Execution and results

- **Runs:** the identical frozen suite on every variant.
- **Preflight:** a mandatory zero-cost preflight (dev provider, jail) on the byte-identical manifest.
- **Per-request provenance** is recorded.
- **Results come in separate sections:** pre-registered or confirmatory, exploratory, and diagnostics.
- **Grading:** official grades never change; rescoring is post hoc and labelled.
- **Regression:** re-running on a new snapshot creates a new manifest that differs only in fingerprints, with a diff report. A task whose oracle answer changed is invalidated for that run, with the reason stated.

## 5. Implementation plan and order

| # | Milestone | Status |
|---|---|---|
| M1 | Immutable suite, task and evaluation-manifest records; write-once content-addressed store; canonical hashes and provenance; public/private separation; Stage A/B boundary; tests | **this step** |
| M2 | Evaluator v2: `gate-nl-1`, the natural-language categories (§3.2), intent preservation, ambiguity classification, coverage matrix; v1 reproduced exactly when the v2 checks are off | after M1 review |
| M2b | Ranked-within-a-filter and either/or criterion kinds, with independent oracle and grader v2 support | after M2 |
| M3 | Bounded LLM generation and evaluation loop (≤ 3 rounds), feedback synthesiser, stopping rule, gap report; deterministic multi-round fixtures | after M2b |
| M4 | Human approval workflow and suite freezing; statistical plan with the feasibility check | after M3 |
| M5 | General zero-cost execution rehearsal against frozen manifests (Larkspur, Ironbark) | after M4 |
| M6 | Paid validation (Stage A generation, one Stage B run), priced from frozen manifests | **separate approval** |

All of this lives in new packages: `agent_readiness/suites/` for the records, store and Stage A, and later `agent_readiness/evalruns/` for Stage B. Nothing in `hosted/` imports them, and an AST test checks this.
