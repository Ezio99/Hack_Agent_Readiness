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

## Orchestration and zero-cost execution (`framework/evaluate.py`)

One interface for every site. There is no site-specific code in the engine; a test checks the AST of `evaluate.py`, `generate.py`, `verifiability.py` and `oracle.py`.

```
prepare(site, root)  -> generate + validate + freeze; persisted as a standard investigation run:
                        snapshot/, site-profile, tasks-manifest, private/criteria.json, framework-taskset (public view),
                        framework-provenance (site, variant hashes, oracle, generation rules, verifiability counts,
                        tasks-manifest sha256, criteria sha256, official grader v1, post-hoc grader v2 derivation id, agent provider and profile)
execute(run)         -> every eligible task x every variant through investigate.trials.runner.run_trial (real Browser Use, real Chromium,
                        snapshot served on loopback), each request behind the RequestGate and ledger; non-base variants use the private
                        record re-derived on that variant (evaluate.stage.still_valid); resumable; trial records in the standard format
results(run)         -> v1 grades as recorded, grader_v2 post-hoc view (grading.rescore, v1 reproduction check), per-variant totals,
                        evidence files per trial; written once as framework-results
```

**Zero cost only.** `provider=dev` is the loopback dev provider (`live.devprovider`, not a model), pinned to the run and serving real HTTP. `provider=mock` is the in-process scripted agent, with behaviours correct, wrong and lazy. Any non-loopback endpoint is refused.

**A shared fix to the dev provider (`live/devprovider.py`).** It cached one scripted agent per (run, task). A second variant or repeat of the same task therefore got an exhausted script and the first trial's stale mirror URL, and answered at step 1. It is now keyed per trial (by mirror URL), and a regression test covers it. Single-trial uses behave exactly as before.

### Execution results (2026-11-02, dev provider, local Chromium, no model, no cost)

| Site | Trials (variants × tasks) | Void | Correct answers (v1 strict) | Evidence-supported, v1 = v2 | Model requests | Rescore faithful |
|---|---|---|---|---|---|---|
| Larkspur | 14 (2 × 7) | 0 | 14/14 | original 7/7, modified 7/7 | 46 + 46 | yes |
| Ironbark | 10 (2 × 5) | 0 | 10/10 | original 3/5, modified 3/5 | 21 + 21 | yes |

The stand-in is handed the frozen answer, so these numbers prove the pipeline, not agent or website quality.

The two Ironbark trials that aren't evidence-supported are the per-day tasks, which need only the 16-item `/hire` listing. The stand-in navigates without scrolling, so the answer items low on the listing were never shown to it. The evidence rule correctly refuses to credit an answer the agent could not have seen. A real agent has to scroll there, as the recorded Muse Spark trials did.

The scripted agent answering wrongly fails every task on both sites (test).

## Limitations, and what stands between Larkspur and a real (paid) agent run

1. **No paid execution path for framework sites.** The hosted executor is deliberately Ironbark-only: `live/ironbark_runner` pins the ORIGINAL/MODIFIED snapshot hashes, the tasks and rule hashes, and validates manifests against them. A Larkspur paid run needs:
   - a framework executor using the hosted admission/budget and a manifest-approval step;
   - per-arm caps sized from Larkspur's task limits;
   - the jailed browser.

   The framework orchestrator refuses non-loopback endpoints by design.
2. **No browser jail locally.** `execute` uses local Chromium. Production isolation (network namespace, loopback mirror only) exists only in the hosted container; a real run must go through it.
3. **No pre-registered comparison rule for framework task sets.** Results are per-variant totals. The frozen `paired-signflip-v1` and exploratory rules are tied to the investigation/proposal flow. Before any effect claim, a rule must be registered against the task-set hash, with repetition count and power considered (with an exact two-sided sign-flip test, 4 task pairs can never reach p ≤ 0.10, since the minimum is 2/16 = 0.125; 5–7 pairs can only if nearly all point the same way).
4. **The scripted stand-in is not a behavioural model.** It cannot exercise scrolling, recovery, or the real-model protocol issues seen with Muse Spark (prose-prefixed JSON, invalid indices), which `suite-v2-compat2` handles.
5. **Generated task limits** come from hop distance (8 + 3 × hops, at most 16 steps). The paid Ironbark trial used 13 of 14 requests on Original tasks, so the limits and caps for a new site should be checked against a first real run.
6. **Oracle and task coverage.** The oracle answers page_fact, item_set and extremum only. Rubric tasks are recorded but not graded. LLM-proposed tasks are not connected (they would need paid calls).
7. **Larkspur is a local snapshot.** It is served only to the agent's browser on loopback, never published.
