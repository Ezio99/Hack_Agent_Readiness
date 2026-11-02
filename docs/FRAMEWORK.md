# Website evaluation framework (Phase 3; isolated; 2026-11-02)

Goal: turn the fixed Ironbark evaluator into a reusable framework. Site-specific knowledge is declared once, in a site definition. The engine generates tasks, validates them independently, classifies how verifiable each one is, and hands only scoring-eligible tasks to the existing execution and grading pipeline.

**Isolation.**
- The package is `src/agent_readiness/framework/`, and nothing in `hosted/` imports it (tested). The production evaluation is unchanged.
- The second site is `src/agent_readiness/sites/larkspur/`.
- Everything here runs offline: no model calls, no browser, no crawling of public websites.

## Architecture

```
SiteDefinition (framework/site.py)                         engine (framework/generate.py)
  id, label, domain, controlled?                             snapshot(original) ─► profile (investigate/inspect)
  variants: original, modified ─► frozen Snapshot              │  restricted to the declared listings
  start_path, listings, entity noun                            ▼
  oracle(): RecordOracle over the site's source records      rule candidates (taskgen/candidates.py) ─► phrase() with the site noun
                                                               ▼
                                                             acceptance gate (taskgen/gate.py): compiles against the snapshot;
                                                             rejects start-page answers, answers in the question, duplicates, ambiguity
                                                               ▼
                                                             per task: stable across variants? · grader_v2 keyable? · oracle agrees?
                                                               ▼
                                                             verifiability class (framework/verifiability.py)
                                                               ├── deterministic ──► freeze_eligible() ─► tasks-manifest + private criteria
                                                               │                     (taskgen/freeze.py format) ─► existing trials + grader_v1/v2
                                                               ├── rubric        ──► recorded with a checklist; never scored
                                                               └── human_review  ──► recorded with reasons; never scored
```

**Independent ground truth (`framework/oracle.py`).**
- The engine's expected answer always comes from the rendered snapshot (`compile_criterion`).
- For a controlled site, `RecordOracle` recomputes the answer from the site's source records (`sites/ironbark/data.py`, `sites/larkspur/data.py`) and declared field formats. It never parses a page.
- If the two agree, the task is validated. If they disagree, the page and the data differ (a site defect or an extractor defect), and the task goes to human review. A test proves this by tampering with a record.
- The oracle declines what its data does not model, for example Ironbark's "availability today", which is derived from the booking calendar. Declined tasks go to human review.

**Verifiability classes.**

| Class | Meaning | Scored? |
|---|---|---|
| deterministic | closed-form criterion, stable across variants, keyable by grader_v2, reproduced exactly by the independent oracle | **yes** (the only scored class) |
| rubric | open question ("What does the site say about delivery and collection fees?") with a checklist of values the site states | no |
| human_review | should be deterministic but is not validated: no oracle (uncontrolled site), oracle disagrees or declines, not keyable, or the answer changes between variants | no |

**Site adapter fields.** A new site needs:
- its variants as snapshots;
- its start page;
- its catalogue listing pages;
- an entity noun;
- and, to be controlled, source records plus a `Field` per stated label (storage kind, unit and display format).

Uncontrolled sites (saved snapshots, the investigation zoo) need only snapshots. Their tasks are always human review.

## Results (offline, deterministic; `python -m agent_readiness.framework.generate SITE`)

| Site | Drafts | Accepted | Deterministic (scored) | Rubric | Human review | Notes |
|---|---|---|---|---|---|---|
| Ironbark (controlled; hosted Original/Modified, hashes equal production) | 12 | 6 | **5** | 2 | 1 | the human-review task is availability today (not in the oracle) |
| Larkspur (second controlled site) | 11 | 7 | **7** | 1 | 0 | course catalogue; listing change in the modified variant |
| Zoo site-1 (uncontrolled) | 11 | 10 | 0 | 0 | 10 | no oracle, so nothing is scored |

Every deterministic task was also frozen and graded through the existing `freeze.instance` path:
- grader_v1 passes the oracle's answer and fails a wrong one;
- grader_v2 agrees with both.

Public task sets (no expected answers, no criteria): `collaboration/experiments/framework/*-taskset.public.json`. Tests: `tests/test_framework.py` (14).

## Second controlled site: Larkspur Community College

A fictional adult-education short-course catalogue.

- **Pages:** 14 courses on `/courses` (cards), one page per course with a `dl` of fee, duration, level, class day, seats left, campus and materials, an enrolment and refunds policy with a table, and an about page.
- **Data:** `sites/larkspur/data.py` is the single source. The pages are rendered from it deterministically with plain semantic HTML.
- **Variants:** `original` has cards with name, category and summary only. `modified` cards also show fee, duration, level and seats left, which mirrors Ironbark's listing-information change in a different domain. Only `/courses` differs between the variants (tested).
- **Capture:** the site is crawled with the pipeline's own crawler, exactly like any other site.

## Not yet done

- **Executing generated tasks with agents.** Running trials on Larkspur needs the site served to the jailed browser and a trials stage pointed at the frozen manifest. The path exists (`freeze` format, trials stage, dev-provider fixture), but it is not wired for framework task sets. Live runs need owner approval.
- **LLM-proposed tasks.** The existing proposer (`taskgen/propose.py`) can feed the same gate, oracle and classes, but it is not connected here because it makes paid calls.
- **Rubric grading.** Rubric checklists are recorded only; nothing scores them.
- **Phase 4 diagnostics** (DOM, accessibility, forms, JSON-LD and navigation friction, linked to agent trajectories) build on the same site definitions.
