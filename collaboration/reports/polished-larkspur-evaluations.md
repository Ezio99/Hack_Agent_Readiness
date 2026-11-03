# Larkspur showcase evaluations (2026-11-04 Sydney)

> **Correction, 2026-11-04 ~10:30 AEDT (owner review).** The first experiment below (internal `polished` / `polished2`, shown to the audience as "Earlier trial A/B") is
> **superseded**. Its records are kept unchanged.
>
> **Lineage, checked in the files:**
> - `polished.py` imports Improved's helpers (`from .improved import ... matching, query, redirects, _course_ld`).
> - Polished v1/v2 had Improved's 162 pages, 870 redirects, filter form, comparison table, JSON-LD on 155 pages, all facts on every card, and page audit 0. Original has 18 pages, 0 redirects, none of those features, and page audit 7.
> - v2 differed from v1 only in presentation (a result-line summary, compact header, slimmer card images).
> - So its 3/3 came from Improved's features, not from a redesign of Original.
>
> **The corrected experiment** (§6) starts from Original. It is the featured showcase.


Status legend: **DONE** (committed and tested locally), **PROPOSED** (awaiting owner approval), **PENDING** (not started).

## 1. Polished v1 (DONE, commit `60c0746`)
- **Snapshot:** `larkspur@polished` = `1053ce1884a9cf718fc631c2f7c144168b9562705727b23ef2f4fae0964f9bbb` (1 042 resources; pinned in `tests/test_larkspur_polished.py`). Original `2f9fd2ce…`, Modified `edb9a5d2…`, Improved `87e715d5…` unchanged (tested).
- **What it is:** a human-centred redesign of the college site built on Improved's information architecture (`sites/larkspur/polished.py`, `art.py`):
  - its own identity (violet and sage, serif display type, larkspur logo, original SVG illustrations per subject and campus);
  - a hero with a course finder, subject tiles, "filling fast", campuses, an enrolment explainer and a full footer;
  - listing pages with a filter panel beside a card grid; cards state every fact as a labelled list plus a seats badge;
  - course pages lead with a key-facts panel and an enrolment call to action;
  - responsive from 390 px (no horizontal scroll on any checked page).
- **Kept from Improved:** the GET filter (every submission captured), browse pages, comparison table, schema.org JSON-LD and every redirect. Images are decorative (`alt=""`); every fact is real text.
- **Validity:** all 3 `larkspur-core@v3` tasks (and all 6 v2 tasks) stay valid on Polished with unchanged answers (the runner's own `validity` check). Page audit: 0 findings. Every link resolves inside the snapshot.

## 2. Single-version evaluation support (DONE, same commit)
The budget could only record a pair. The minimal, backward-compatible change:
- `lifecycle/arming.plan`: a **budget evaluation** may name one registered version; judge armings stay paired (tested).
- `hosted/budget evaluation-add --variants polished` (1 or 2 versions; `open` unchanged).
- Job status has one arm; diagnostics run per version (structural and behavioural findings; no cross-version comparison); Workspace, History, Report and Trace render one column.
- Same frozen suite, agent, manifest plan, seed and per-request cap (a regression manifest of the v3 manifest; only the variants differ). 3 trials; **per-run maximum US$1.892 = A$2.84** (pair: US$3.740).
- **Zero-cost rehearsal:** the real app, real jailed Chromium, scripted dev provider, on a copy of the production store: code → Run → live grid → 3/3 runs → report → trace replay with real screenshots of Polished v1; 0 console errors.
- **Tests:** critical 263 passed; budget/polished/improved 45 passed; hosted/settlement/stage B 40 passed; vitest 224 passed; dashboard build CHECK PASSED.

## 3. Deployments and evaluation records (DONE, 2026-11-04; owner-approved, then the owner's standing authorization)
| Step | Record |
|---|---|
| Push `60c0746`, `38f65d4` | owner-approved |
| Deploy `60c0746` | A0 matched the hotfix record (image `a2a3792a…`, DB `d870675…`, 2 422 files). Backup `predeploy-polished-20261103T215431Z` verified. Clean build `46aa6463…`, compose identical. Disabled smoke on a volume copy: 0 tracebacks, historical reports 200. Switch: `rollback-fdc3f43`. A5: 403 without/with a wrong code, judge code accepted without launching (422), evidence 2 422/2 422 identical, 9 routes in a real browser with 0 errors |
| Deploy `f32a88e` (delegated, audited `evaluation-add/use`) | backup `predeploy-delegated-20261103T220216Z`; image `f663f018…`; rollback `rollback-60c0746`; evidence identical |
| Record + select `ar-a20-polished-v1` | `--delegated` (statement names the agent, sha256 `a594fe91…` of the reviewed terms, `budget-pools/DELEGATIONS.jsonl`); backup `admission-pre-polished-v1-20261103T220322Z` |
| Deploy `70c56d7` (Polished v2 + exports) | backup `predeploy-polished2-20261103T221653Z` (2 660 files); image `4b878538…`; rollback `rollback-before-polished2` = `f663f018…`; evidence identical; 10 routes, 0 errors |
| Record + select `ar-a20-polished-v2` | terms sha256 `aa534feb…`; backup `admission-pre-polished-v2-20261103T221819Z` |

The budget opening, allocations and settlements remain owner-typed. Nothing raised a budget, cap or per-run limit.

## 4. Results (genuine live evaluations, Muse Spark `muse-spark-1.3`, `larkspur-core@v3`, one run per task, each version alone)
| | Polished v1 `eval-abc5fc83…` | Polished v2 `eval-11ee8a1e…` |
|---|---|---|
| Snapshot | `polished` `1053ce18…` | `polished2` `1b02ed09…` |
| Correct (grader v2) | **3/3** | **3/3** |
| Exact match (grader v1) | 1/3 | 0/3 |
| Model requests (per task) | **8** (2 · 4 · 2) | **9** (2 · 5 · 2) |
| Agent time | 64.7 s | 78.9 s |
| Settled cost | **US$0.108110** (A$0.16) | **US$0.121951** (A$0.18) |
| Evidence shown (incl. equivalent table) | 3/3 | 3/3 |

Budget after both: spent A$0.35 of A$20 (`ar-a20-2026-11`).

**Polished v1 findings** (from its traces):
- Tasks 1 and 3: answered from the comparison table in 2 requests each. No friction.
- Task 2 friction (observed): the agent used the home finder, reached "4 courses found", saw three cards ("Visible 3 ... Scroll down to reveal the 4th course") and spent a step and a request scrolling. The cause is presentational: a tall listing header and decorative card images.
- Exact-match misses: answers carried extra detail. The report's own diagnostics label this a grading-format effect, not a website problem, so it does not justify a site change.

**Polished v2 changes** (`polished2.py`): each result line names every match before the first card; listing pages get a compact header and slimmer card images. Same resources and facts.

**Polished v2 outcome: no improvement on this run.**
- Task 2 took 5 requests. The agent first read the select options (a new step), then selected, submitted, scrolled "to verify fourth course details", and answered.
- Its memory before the scroll already listed all four courses, read from the new summary line. It still scrolled, because the 4th card's facts were below the fold.
- Tasks 1 and 3 were unchanged.
- With one run per task, the one-request differences are within run-to-run variation. Neither version is better on this evidence.

**Remaining friction and next recommendation (not built, not evaluated):** agents verify the deciding facts before answering. A results view that keeps the deciding facts of every match on screen (e.g. a compact table of the filtered courses) addresses what the agent actually did. Names alone do not.

## 5. Stages 5–6 (DONE)
- **Showcase** `#/showcase` (`dashboard/src/site/story/`):
  - Chapters: Polished v1 → evaluation → discovered friction → recommendation → Polished v2 → re-evaluation → measured result → where Larkspur started.
  - Real data only: exported frames and agent memory, settled costs.
  - Reduced-motion fallback; no API calls.
  - Tested: vitest checks the table against `larkspur.json`; reviewed in a browser at 1440 and 390 px.
- **Home:** a Polished band with both live results. Nav has "Showcase"; the footer links the Polished reports.
- **Workspace:** runs Polished v2 alone. It shows a preview of the selected version, and its copy matches the shared budget.
- **Ironbark:** remains the archive only (`#/demo/ironbark`). Historical reports are unchanged.
- **Deploy `730037b`:**
  - backup `predeploy-showcase-20261103T225011Z` (2 898 files);
  - image `40679aa0…`, rollback `rollback-before-showcase` = `4b878538…`;
  - evidence identical; 403 without a code;
  - 13 public routes in a real browser with 0 errors, plus the showcase at 1440 and 390 px.
- **Checks before the deploy:** critical 264 passed; polished/budget 49 passed; vitest 226 passed; `test_showcase_judge_browser` and `test_judge_experience_browser` passed (run alone).
- **Submission:** [FINAL_SUBMISSION.md](../../docs/FINAL_SUBMISSION.md), [FINAL_VIDEO_SCRIPT.md](../../docs/FINAL_VIDEO_SCRIPT.md).


## 6. Corrected experiment: Before → After (featured; DONE)
**Audience names:** Larkspur Community College · Before · After · Agent Readiness. Internal names stay in code, tests and this document only.

### Snapshots
| Audience name | Internal snapshot | sha256 | What it is |
|---|---|---|---|
| Before | `polishedoriginal` (`polished_original.py`) | `2ee4a7be…` | Original re-skinned only. Same 18 pages and links, Original's card content (subject, name, summary), the same 7 page-audit findings. No filter, table, structured data or redirects (tested) |
| After | `modifiedpolished` (`modified_polished.py`) | `2a16c38b…` | Before plus exactly the Before report's recommendations: all 7 labelled facts on each card, a redirect for the observed dead end (name-based course URL), schema.org Course/ItemList data. Same pages and design; audit 0 |

### Live evaluations
Each version alone, `larkspur-core@v3`, muse-spark-1.3, recorded and selected with `--delegated`.

| | Before `eval-ea13944e…` | After `eval-5cf934b3…` |
|---|---|---|
| Correct (v2) / exact (v1) | **0/3** / 0/3 | **3/3** / 1/3 |
| Evidence shown | 0/3 | 3/3 |
| Model requests (per task) | 36 (13 · 11 · 12) | 15 (6 · 6 · 3) |
| Course pages opened | 11 | 0 |
| Agent time | 311 s | 121 s |
| Settled cost | US$0.521494 | US$0.204389 |

**Before findings (its report):**
- Listing-fact gaps, linked to the tasks: fee and seats (task 1), class day (task 2), fee and duration (task 3). Level appears in task 2's agent notes; campus and materials come from the page audit.
- One dead end: `/courses/introduction-to-python` returned 404.
- Budget exhaustion on task 1; partial answers on tasks 2 and 3.
- No structured data.

All three agents' last notes say they were out of steps.

**After:** every agent answered from `/courses` alone, with no dead ends. The exact-match misses on tasks 1 and 3 carry extra detail (fees, seats), which the report labels a grading-format effect.

**Budget:** `ar-a20-2026-11` spent A$1.43 of A$20 after all four runs (two superseded, two featured). The Workspace's selected evaluation is `ar-a20-after`.

### Product changes
- **Audience labels at the presentation layer:** `VARIANT_LABEL`, `audienceText`, and `displayTitle` for stored job titles. Stored records are unchanged.
- **Pages rebuilt on Before/After:** Home, the hero card, the showcase (`#/showcase`), the Journey re-evaluate step, nav and footer. Earlier experiments are labelled "Earlier".
- **Workspace:** runs After and shows its preview.
- **Mobile overflow fixed:** Journey, job page, report badges.

### Checks
- **Before deploying:** critical tests; `test_larkspur_before_after.py` (pins every snapshot, Before = Original's pages/links/cards/audit, After = Before + exactly the recommendations); vitest 226, including a no-internal-names assertion on Home and the showcase.
- **Production sweep:** 22 public routes × desktop and mobile; 0 internal names in text or `alt`/`aria-label`/`title`, 0 errors, 0 writes. Overflow fixes re-verified against production data with the local build.
