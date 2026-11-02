# Report: lifecycle M1 (immutable records, write-once store, Stage A/B boundary)

**Date:** 2026-11-02. **Branch:** `research/llm-task-planning`, commit `6bdfe6c`. **Approved by the owner** (decision 8). **Not deployed.** No paid calls.

**Design:** `collaboration/proposals/two-stage-evaluation-lifecycle.md`.

## Implemented (`src/agent_readiness/suites/`)

- **`records.py`:** frozen pydantic records that refuse unknown fields: `TaskRecord`, `Wording`, `TaskSpec`, `Limits`, `Validation`, `PrivateOutcome`, `SuiteRecord`, `Approval`, `FrozenSuite`, `StatisticalPlan`, `AgentConfig`, `EvaluationManifest`, `RunResult`. Identity is `content_hash` (canonical SHA-256 of the JSON form). Validation rules:
  - **Wording categories** (natural-language amendment):
    - natural_verifiable and natural_judgment execute the customer wording unchanged, with no assumptions;
    - natural_underspecified lists what is unresolved and is not executed;
    - assisted_restatement is an explicit, labelled restatement.
  - **Category and verifiability must agree:**
    - natural_verifiable and assisted → deterministic;
    - natural_judgment → rubric or human review;
    - underspecified → human review.

    A deterministic task needs a private outcome.
  - **No answers in public records:** answer-like keys (`expected`, `answer`, `truth`, …) are refused anywhere in a public specification or in suite coverage.
  - **Approval:** `Approval.approver_role` is `owner` only (decision 7).
  - **Statistical plan** (decision 6): α defaults to 0.05; tasks are the unit of analysis. A confirmatory designation needs a feasibility assessment (minimum achievable p ≤ α, plus a minimum detectable effect or power) marked feasible. For `paired-exact-sign-flip` the minimum p must equal 2/2ⁿ. A manifest's repetitions must match its plan.
  - **Input kinds:** Stage A records accept only Stage A input kinds; Stage B records accept only Stage B kinds.
- **`store.py` (`WriteOnceStore`):**
  - content-addressed objects written with exclusive create and mode 0444; private outcomes in `private/` (0700 directory, 0400 files);
  - write-once named refs (re-pointing is refused);
  - **every read recomputes the hash** (tampering raises `TamperError`);
  - cross-record rules on write:
    - a suite's tasks exist and belong to its site;
    - a task's private outcome matches its specification hash;
    - freezing needs an **approved** approval of the **exact** suite hash;
    - an approval needs a stored suite;
    - a manifest needs a frozen suite;
    - a run result needs a manifest;
    - **a Stage A record may not reference a stored Stage B object (manifest or run result) even under an allowed input kind.**
- **`boundary.py`:**
  - Stage A input-kind whitelist;
  - Stage B outcome kinds;
  - an AST import check: Stage A modules (`records.py`, `store.py`, `boundary.py`, and the future `stage_a/`) may not import trial execution, hosted, diagnostics, the rescore, provenance, the pilot, framework execution, `evalruns`, live, scanner or the agent.

## Tests (`tests/test_suites_m1.py`): 26 passed

They cover:
- **immutability:** frozen models, unknown fields refused, write-once read-only files, idempotent puts, refs that cannot be re-pointed;
- **tampering:** public and private records, and store-level re-put;
- **integrity:** a private outcome derived for another spec is refused;
- **provenance:** part of identity, inputs typed and hashed;
- **canonical hashing;**
- **private-answer isolation:** public views and files carry no expected answer, and private permissions are correct;
- **answer-key refusal;**
- **wording-category rules** and category/verifiability agreement;
- **approval and freezing:** exact hash, rejected approvals, owner only;
- **manifests** need frozen suites;
- **the statistical plan:** confirmatory needs feasibility; 4 pairs are infeasible at 0.05; the minimum p must match the sign-flip test;
- **Stage A/B boundary:** outcome input kinds refused, disguised references to stored outcomes refused, `agent_evidence_consulted` locked to false, import check clean, the import check catches violations;
- **isolation:** no production package imports `suites`.

**Mutation check:** disabling read-time tamper detection and the outcome-reference check made exactly the 3 corresponding tests fail; the code was restored and all 26 pass.

**Regression:** critical suite 214 passed (17 deselected). The research, framework, diagnostics, grader, provenance, derived-cache and export suites: 159 passed (4 browser deselected).

## Not in M1

- Evaluator v2 (M2), new criterion kinds (M2b), the Stage A loop (M3), the approval UI or CLI and the statistical-plan helper (M4), and the Stage B runner (M5).
- `StatisticalPlan` validates a supplied feasibility assessment; it does not compute power.
