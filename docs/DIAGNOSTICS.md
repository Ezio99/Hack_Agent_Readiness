# Diagnostics (Phase 4; isolated; 2026-11-02)

`src/agent_readiness/diagnostics/` turns a site's frozen versions and recorded agent trials into findings. Nothing in `hosted/` imports it (tested), and it is read-only over runs. No model calls.

```
python -m agent_readiness.diagnostics.run RUN_DIR [--recorded] --out report.json      # also writes report.md
```

The run directory is either a Phase 3 framework run (versions come from the site definition) or, with `--recorded`, a recorded paired fork such as a hosted Ironbark repetition. For a fork, Original is its snapshot with the `placebo-*` trials, Modified is its patched snapshot with the `patched-*` trials, and the fork's recorded comparison verdicts are included.

## Three layers, one finding schema

Every finding has:
- a **stable id**: `S-`/`B-`/`H-` plus a hash of rule, site and subject. It does not depend on the version, so a change can be shown to resolve a finding;
- **site and version context** (version name and snapshot sha256), plus task ids;
- **severity** (high/medium/low/info) and an **impact** statement;
- **evidence references**: page, locator, listing field, trial and step, linked findings, comparison;
- a **recommendation**, with **how to verify** it;
- a **status** (below) and the **evidence origin**: page, real_model, dev_fixture or scripted.

| Layer | Rules | Status |
|---|---|---|
| **Structural** (`structural.py`, from the frozen snapshot's profile) | listing-fact-gap (a fact on ≥ 80 % of item pages but ≤ 20 % of listing cards; one finding per item-page template; sort/filter chips excluded), unnamed-control, heading-structure, missing-landmark, image-alt, form-label, no-structured-data, unreachable-page | `observed` (a page fact; never reported as a proven failure) |
| **Behavioural** (`behavioral.py`, from trial records, aggregated per rule × task × version) | revisit (returning to a page twice or more; scrolling is one visit), loop, retry, dead-end (HTTP errors and failed actions; the browser's own favicon/robots requests excluded), unnecessary-navigation, budget-exhaustion, unsupported-answer, incorrect-answer (cites the post-hoc grader_v2 result when the rescore is faithful) | `observed` |
| **Evidence-linked hypotheses** (`hypotheses.py`) | links a listing gap to the tasks that compare items by that fact through that listing, and to their behaviour per version (item pages opened, requests, evidence-supported passes) | `unverified`, `hypothesis`, `supported_exploratory` or `supported` (below) |

**Status rules. Nothing is causal by default.**
- **`unverified`**: no evaluated task depends on the structural issue.
- **`hypothesis`**: dependent tasks exist and their behaviour is cited, but the issue is untested, or was tested only with fixture or scripted behaviour (which can never support it).
- **`supported_exploratory`**: a version without the issue was run on a real model; item pages opened and requests both fell; evidence-supported passes did not fall; and the recorded exploratory rule agreed. The pre-registered rule did not establish it.
- **`supported`**: as above, and the pre-registered rule established an improvement.

When one tested change resolved several issues together, the finding says that support applies to the combined change.

## Validation on the controlled sites

**Structural detection of the intentional change.** Both sites' known Original→Modified change is detected exactly: all of the change, and nothing else.

| Site | Gaps on Original | Resolved by Modified | Introduced | Persisting (correct: not part of the change) |
|---|---|---|---|---|
| Larkspur | campus, class day, course fee, duration, materials, seats left | **course fee, duration, seats left** (exactly what Modified adds to cards) | 0 | campus, class day, materials |
| Ironbark | delivery and collection, minimum hire, refundable deposit, per week, weekend (+ accessories "fits") | **delivery and collection, minimum hire, refundable deposit** (exactly the S1 change) | 0 | per week, weekend, fits |

Larkspur's "level" is not flagged on Original: 3 of 14 card summaries contain the word "Beginner", so the profiler counts the fact as partly on the cards. That is a known limit of text matching.

## Results

### Real model: the paid production trial `eval-aa23e330` (Ironbark, Muse Spark, 1 repetition)

[report](../collaboration/experiments/diagnostics/ironbark-eval-aa23e330.md)

**Directly observed (structural, 11).**
- The /hire listing omits five facts that every item page states. Three are resolved by Modified.
- No item page carries structured data.
- No unnamed controls, missing landmarks or unlabelled form controls were found.

**Directly observed (behavioural, 16).**
- Original:
  - all four tasks used 13 of 14 model requests;
  - the agent returned to /hire 2–3 times per task;
  - a /hire ↔ /hire-terms loop on task 1;
  - a real dead end on task 3: the agent requested the guessed URL `/hire/wood-chipper-100-mm`, which does not exist (404);
  - all four answers graded wrong by grader_v1. For task 1, the post-hoc grader_v2 says the answer was correct.
- Modified: only task 1 was "incorrect" (the known grader_v1 false negative; v2 says correct) plus revisits.

**Hypotheses, `supported_exploratory` (3).** Listing cards omit refundable deposit (tasks 1, 2), delivery and collection (task 3) and minimum hire (task 4). On Modified, where these are on the cards:
- item pages opened per task fell from 3 to 1;
- requests per task fell from 13 to 5–7;
- evidence-supported passes rose.

The exploratory rule (`exploratory-listing-v1`) says consistent_with_h1. The pre-registered rule (`paired-signflip-v1`) is **inconclusive**. The three facts were changed together, so support applies to the combined change. This is one repetition.

**Unverified (3).** The per week and weekend rates, and accessory "fits", are missing from cards, but no task compares items by them.

### Zero-cost fixture runs (Larkspur, Ironbark; dev provider, not a model)

[Larkspur](../collaboration/experiments/diagnostics/larkspur-fixture-run.md) · [Ironbark](../collaboration/experiments/diagnostics/ironbark-fixture-run.md)

- **Structural:** as in the validation table.
- **Behavioural:**
  - Larkspur: 2 observations (unnecessary navigation on Modified; the stand-in still opens item pages the Modified listing makes unnecessary).
  - Ironbark: 5 (unsupported answers, because the stand-in never scrolls the long listing).
- **Hypotheses:** Larkspur course fee and duration, and Ironbark delivery and minimum hire, stay **`hypothesis`**. A version without the gap was run, but only with fixture behaviour, which by rule cannot support a claim about agents. Campus and class day are `hypothesis` (untested). Gaps no task depends on are `unverified`.

## Limitations

- **Small rule set by design.** The listing-fact-gap rule is the only one linked to behaviour. Other structural rules (names, landmarks, headings, forms, alt text) are observed but have no hypothesis linking yet.
- **Thresholds are heuristics.** The 80 %/20 % thresholds are provisional, and the profiler's text matching can count incidental words as a fact being present (Larkspur "level").
- **No statistics in the behavioural measures.** These are means over the recorded trials (one repetition here). Support comes only from the recorded comparison rules.
- **Structured data is checked for presence, not correctness.** It is not compared with visible values.
- **Accessibility is assessed from the captured DOM profile, not a live accessibility tree.**
