# grader_v2: design, adversarial tests, historical rescore (2026-11-02)

**Status:** implemented on branch `evaluation-v2`. **Not deployed**; production deployment awaits owner review. grader_v1 is unchanged and remains the grader of record for every recorded experiment.

## Problem

grader_v1 (`investigate/taskgen/criteria.py`, `answer_match`) handles string tasks and set tasks differently, and is brittle in both.

- **String tasks.** An answer passes only if it equals the truth after normalisation, or contains it within at most `len(truth) + 16` characters. So "Electric scissor lift 6 m" passes, but "Electric scissor lift 6 m with a refundable deposit of $600" fails, even though it is correct and its extra detail is true.
- **Set tasks.** Each element must equal a name exactly. "Cordless drill driver kit 18V" ≠ "… 18 V", and "Name - $100 refundable deposit" ≠ "Name".

## Design (`src/agent_readiness/grading/`)

grader_v2 grades against an **answer key**, not by string similarity. It does not widen the 16-character tolerance.

**Answer key (`key.py`).**
- The key is re-derived from the frozen snapshot with grader_v1's own extractors (`compile_criterion`, `_items`, `_fact`).
- It is refused unless the re-derived truth equals the frozen truth. So v1 and v2 can never disagree about what the right answer is; they differ only in how an answer's wording is judged.
- Candidates:
  - extremum / item_set: every listing item, each with its own page's labelled facts.
  - page_fact / reach_page / term_value: the truth (with the facts of its page) plus every other value or title the site offers (v1's distractors).
- The key also records the numbers the task itself states: condition thresholds, the listing size, and the numbers on the answer's page.

**Answer decomposition (`v2.py`).**
- *Mentions*: full candidate names in canonical form. Case, punctuation, number/unit spacing ("18V" = "18 V") and thousands separators are ignored. The longest match wins and matches don't overlap, so "Wood chipper 100 mm" is never read as "Wood chipper". Partial names are not matched.
- *Residual*: everything else, which must be consistent detail:
  - no hedge ("or", "maybe", "probably", "/", "?", …);
  - no negation ("not", "except", "isn't", …);
  - a number within 4 tokens of a fact label must equal **that** fact. Money binds to money-valued labels and plain numbers to plain-valued labels; labels with non-numeric values never bind. So "deposit $210" contradicts a $600 deposit when $210 is the day rate;
  - any other number must be stated for the mentioned candidate, by the task, or on the answer's page;
  - extremum tasks: no superlative of the opposite direction (fact labels such as "minimum hire" are excluded from this check);
  - at most 40 residual tokens.

**Decision.**
- String tasks pass if exactly one candidate (the truth) is mentioned and the residual is consistent.
- Set tasks pass if every element maps to candidates whose own details are consistent, nothing unrecognised is listed, and the mapped set equals the truth set exactly.
- Every grade carries reason codes. A `review` flag marks failures a human might overturn (for example, a contrastive mention of a competitor). Scoring stays binary and conservative.

**Evidence.** A v2 evidence-supported pass is a v2 pass together with the trial's stored `evidence_satisfied`. That flag records which pages were shown to the agent and does not depend on the answer.

**Rescore (`rescore.py`).**
- Reads a run read-only; `freeze.load` verifies the frozen criteria and snapshot hashes.
- Faithfulness checks: grader_v1 is re-applied to every stored answer and must reproduce every stored grade. The pre-registered frozen rule (`design.compare`) and the exploratory rule must also reproduce the stored verdicts from the stored v1 flags.
- Only after those checks pass are the same rules applied to the v2 flags, and those results are labelled **post hoc / not pre-registered**.
- Output goes to separate files: `<run>.grader-v2.json` (private: contains answers) and `.public.json` (no answers, expected values or criteria). Nothing is written into the run.

**Hosted (not deployed).**
- Completed repetitions get a `grading_v2` view: per-task v2 outcome and reasons, plus the rules applied to v2 grades. There is also a `summary_v2` total.
- The view is cached as `<run>.grader-v2.json` beside the job files. It is withheld unless the rescore is faithful.
- The workspace headline stays grader v1. v2 appears as a secondary line labelled "Grader v2, post-hoc rescore … (official result above: grader v1)", with per-cell markers only where v2 differs and post-hoc verdicts labelled "not pre-registered".

## Adversarial tests (all pass)

`tests/test_grader_v2.py`: 47 tests on a synthetic site.

**Accepted:**
- exact answers;
- case, punctuation and thousands-separator variants;
- supporting detail bound to its label, with the number before or after the label;
- the same candidate repeated;
- the listing size ("all 8 machines");
- a label containing "minimum" in a max task;
- set answers with consistent per-item details, including one joined string or a stated threshold prefix;
- page-fact detail quoted from its own page.

**Rejected:**
- the wrong candidate;
- "A or B";
- the truth plus a competitor;
- an injection that names the truth inside a wrong answer;
- "probably", "?" and "/";
- "not" and "isn't";
- a day rate given as the deposit;
- another machine's deposit;
- invented numbers;
- an opposite superlative;
- partial names;
- empty, non-string and over-long answers;
- set answers with missing, extra or wrong items, a contradictory per-item detail, unrecognised elements ("and others", "All of them"), hedges or negation;
- a bare "45 dollars" for "$45" (conservative).

**Key safety:** a tampered frozen truth is refused, canonical name collisions are refused, tied extremes cannot be frozen, and the profile is not mutated.

**v1 behaviour is pinned unchanged**, including the motivating false negatives.

`tests/test_grader_v2_rescore.py`: 5 tests on an offline scripted run whose stored flags come from v1 itself. They cover exact reproduction, read-only operation, no truth or answers in the public view, tamper detection and hosted view behaviour.

## Historical results under v2 (post hoc; all 12 runs faithful)

The table shows evidence-supported passes, v1 → v2. Verdicts show the stored v1 verdict → the same rule on v2 grades. The full public record is in [rescore-summary.json](../experiments/grader-v2/rescore-summary.json).

| Run | Arms (v1 → v2) | Frozen `paired-signflip-v1` | Exploratory |
|---|---|---|---|
| Ironbark source run (historical baseline) | baseline 0 → 1 /4 | n/a | n/a |
| EXP-C | baseline 0 → 1, patched 2 → 3, placebo 0 → 0 | inconclusive (p 0.5) → inconclusive (p 0.625) | not_supported → not_supported |
| EXP-C R1 | baseline 0 → 1, patched 1 → 2, placebo 0 → 0 | inconclusive → inconclusive | consistent_with_h1 → same |
| EXP-C S1 | baseline 0 → 1, patched 3 → 4, placebo 2 → 3 | inconclusive (p 0.25) → inconclusive (p 0.25) | not_supported → not_supported |
| hosted `eval-9aaac35c` | Original 1 → 1, Modified 4 → 4 (baseline 0 → 1) | inconclusive (p 0.125, Δ 1.0) → inconclusive (p 0.25, Δ 0.75) | consistent_with_h1 → same |
| hosted `eval-aa23e330` (paid trial) | **Original 0 → 1, Modified 3 → 4** (baseline 0 → 1) | inconclusive → inconclusive | consistent_with_h1 → same |
| site-5 L1a, recovery fork, EXP-B | no change (4/6, 4/6; EXP-B 4/6, 6/6, 1/3) | inconclusive → inconclusive | consistent_with_h1 → same |
| earlier Ironbark live / replay runs | replay 0 → 1; others unchanged | n/a | n/a |

What changes:
- Every change is the same pattern: a correct answer to task 1 (highest deposit) or task 2 (deposits under $200) that adds the correct deposit or the per-item deposits. 13 trials pass for the first time (0 v1 passes are rejected by v2; verified from the summary).
- **No verdict category changes in any run.** p-values change only where the baseline task-1 pass moves the paired difference.
- No answer that v1 accepted is rejected by v2 (0 of 13 changes go from pass to fail).
- The hosted demo evidence (`eval-9aaac35c`, 1/4 → 4/4) is unchanged, so the homepage and demo copy stay accurate.

v2 stays conservative in some cases, and these still fail with `review` set:
- Correct answers that name competitors for comparison, for example "…scissor lift $600 vs stump grinder $500 and wood chipper 100mm $500" (EXP-C placebo) and the site-5 "Pressure Washer… highest among: Cordless Drill $40, …" lists. This follows the instruction that multiple-candidate answers do not pass.
- `eval-9aaac35c` Original task 1, because "e.g. stump grinder $500" is a partial competitor name.

## Limitations

- Deterministic and lexical: partial names, paraphrased names ("6-metre lift") and spelled-out numbers are not matched, so they fail.
- Label binding uses token proximity. Ties between labels are accepted only if the number is consistent with one of the tied labels.
- Free-text claims without numbers ("…, the newest machine") are not checked unless they contain a hedge, a negation or an opposite superlative.
- v2 covers the generated-criteria grader. The EXP-2 grader (`exp2/answers.py`) is separate and untouched.

## Deployment (approved 2026-11-02)

**What changes in production:**
- the job-status API gains `grading_v2` and `summary_v2`;
- the workspace shows the v2 line and markers;
- the export reports the enforced ceiling with its basis;
- the operator-token field is visible and held in memory only.

**What does not change:** the executor, admission, jail, grading of record (v1), budgets, access mode and stored evidence.

**Derived caches** live in a separate, versioned namespace under the hosted root, never inside a run:
- `derived/grader-v2/<run>.<derivation_id>.json`. The derivation id hashes the rescore schema and the grading sources, so any grader change gives new cache names.
- `derived/public-export/<run>.export-v2.json`.

Both are disposable: deleting them only causes regeneration from the run. The pre-fix export caches (`<run>.public.json`) are no longer read, and they are left in place untouched.
