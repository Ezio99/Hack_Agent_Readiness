# Grading reliability audit: the two paid `larkspur-core@v2` experiments (M7 and the live run)

**Date:** 2026-11-03 (Sydney). **Scope:** read-only.
- No grading change, no re-grading of records, no paid call.
- Official v1 grades remain the grades of record; nothing here changes them.

**Evidence:**
- M7: `scanner-data/research/stage-b/paid/evalrun-paid-64a55c5f3a-natural`, 12 trials, 2026-11-02.
- The live run `eval-e529db2aafecbfddd21e5c571eb85243`: local copy of production `scanner-data/hosted-copy-m9/…/evalrun-l-e529db2a-64a55c5f3a-natural`, 12 trials, 2026-11-02 23:39–23:54 UTC.
- Both runs used the same frozen suite (`0816af7f…`), manifest (`64a55c5f…`), snapshots (Original `2f9fd2ce…`, Modified `edb9a5d2…`), model and profile.

**Method.** For all 24 trials:
- the frozen task (customer wording, criterion) and its private expected answer;
- the agent's recorded answer;
- the pages it visited (mirror log), with HTTP status;
- the page content the model was actually sent (trace), where needed;
- the official v1 grade and the post-hoc v2 grade as recorded (v1 reproduction verified for all 24);
- the prospective rules (`v2.1-contrast`, `evidence-ranked-subset-2`);
- every fact the agents quoted, checked against the frozen snapshots (the 14 course pages and the `/courses` listing of each variant);
- a **decidability** measure: for each trial, how many of the 14 courses the agent could decide (include or exclude) from facts on pages it was actually shown. That is the listing cards on Modified (fee, duration, level, seats left; *not* campus or class day), otherwise the course's own page.

**Privacy.** This committed report names only items an agent itself produced. Expected answers that no agent produced are given as counts. The full private evidence matrix, the catalogue table and the decidability computation are in `scanner-data/grading-audit-m9/` (git-ignored).

---

## 1. Principal findings

1. **No agent stated a false fact, and no oracle answer is wrong.**
   - Every fee, seat count, duration, level, class day and campus quoted in the 24 answers matches the snapshot.
   - All six expected answers re-derive correctly from both snapshots.
   - Every recorded failure is either incomplete navigation or a grading artefact.
2. **Official grader v1 has a high false-negative rate.**
   - 15 of the 24 answers are correct. v1 passes only 6 of them, failing **9 correct answers** (40% recall on correct answers).
   - It has **no answer-level false positives**.
   - Cause: v1 requires exact item names for list tasks and accepts only very short sentences for single answers. A correct answer with supporting detail ("Spreadsheets for small business - $180, 9 seats left") or a full sentence ("The course fee for Life drawing studio is $210.") fails.
3. **v1's false negatives are biased against the Modified site:** 7 of the 9 are Modified trials. Modified listing cards show the facts, so agents quote them in their answers, and v1 rejects the detail. **The official v1 comparison therefore understates Modified.**
   - Live run: v1 1/6 → 2/6, while the correct answers went 2/6 → 5/6.
   - M7: v1 2/6 → 1/6, an apparent regression, while the correct answers went 3/6 → 5/6.
4. **Half of all official failures are genuine:** 9 of 18 v1 failures are incomplete navigation, not grading.
   - **Where:** 8 of the 9 are on Original, plus task 3 on Modified.
   - **Why:** on Original no listing card shows structured facts. Every filter task needs all 14 course pages (≥15 page loads), but each trial is limited to 14 model requests, and agents spent about 3 requests per course page. They decided only 2–4 of 14 courses before running out of requests.
   - **Is it a measurement error?** No. It's the readiness signal the product is meant to measure, but it is tied to the 14-request limit, and the task generator does not model this verification cost (§4).
5. **v2 is better but not "correct by default".**
   - **2 answer-level false negatives:** task 5 Modified in both runs. A correct answer that mentions the rejected alternative fails `multiple_candidates`.
   - **1 evidence false negative:** live task 2 Modified. The fee was on the listing card the model received, but the page-fact evidence rule demands the course page.
   - **No answer-level false positives.**
   - **4 of its 13 passes are correct answers the agent could not have verified:** lucky or under-verified, so strict-evidence over-credit. 2 of those 4 are also official v1 passes (M7 task 4 Modified and task 5 Original).
6. **The prospective `v2.1-contrast` rule does not generalise.**
   - It was designed from M7's task-5 Modified answer ("… (vs Furniture restoration …)") and passes it.
   - It **fails the live run's semantically identical answer** ("… the other Riverside Intermediate, Furniture restoration, is Sunday with only 1 seat left …"), which has no marker word like "vs".
   - It should not be adopted as is.
7. **`evidence-ranked-subset-2` works as intended.** It flags M7 task-5 Original (an **official v1 pass**) and the live task-5 Original (a v2 pass) as comparisons the agent never saw. Only 2 of 3 required pages were shown; Furniture restoration, the only competitor, was never opened.

## 2. Task-by-task evidence matrix

**Legend.**
- **Answer:** Correct / Partial k/n (only correct items, missing some) / Incomplete (no qualifying item, or none answered) / Empty.
- **Verified:** decidable courses of 14 from facts shown. "Seen" for page facts.
- **v1, v2:** P = pass, F = fail, with grading accuracy:
  - ✓ correct;
  - **FN** = a correct answer failed;
  - **FN-ev** = a supported answer judged unsupported;
  - **OC** = credited although the deciding facts were not shown (over-credit under strict evidence).
- **R** = model requests (limit 14).

### Task 1: "I need a course that costs $250 or less and still has at least 5 seats left. What qualifies?"

List, 5 expected items. Fee and seats are on Modified cards only.

| Run | Variant | Answer (agent's own) | Answer class | Verified | R | v1 | v2 |
|---|---|---|---|---|---|---|---|
| M7 | Original | "Beginners yoga - $150, 12 seats left (qualifies…)" | Partial 1/5 | 3/14 | 12 | F ✓ | F ✓ (`contradictory_detail`, `hedged`) |
| M7 | Modified | 5 items, each with fee and seats | **Correct** | 14/14 | 3 | F **FN** (detail in items) | P ✓ |
| Live | Original | "Unable to complete full check within step limit. Checked 3 of 14 courses … No confirmed qualifying …" | Incomplete (honest) | 3/14 | 13 | F ✓ | F ✓ (`hedged`, `negated`: not fooled by the unchecked names listed) |
| Live | Modified | identical to M7 Modified | **Correct** | 14/14 | 3 | F **FN** | P ✓ |

### Task 2: "… What is the course fee for Life drawing studio?"

Single page fact. The fee is on the course page, and also on the Modified card.

| Run | Variant | Answer | Answer class | Verified | R | v1 | v2 |
|---|---|---|---|---|---|---|---|
| M7 | Original | "$210" | **Correct** | seen (course page) | 3 | P ✓ | P ✓ |
| M7 | Modified | "The course fee for Life drawing studio is $210." | **Correct** | seen (course page) | 3 | F **FN** (sentence length) | P ✓ |
| Live | Original | "$210" | **Correct** | seen (course page) | 3 | P ✓ | P ✓ |
| Live | Modified | "The course fee for Life drawing studio is $210." | **Correct** | **seen on the listing card**: the trace shows "Life drawing studio … Course fee $210" in the model's input | 2 | F **FN** + evidence **FN-ev** | P, but `evidence_backed` false: **FN-ev** (the page-fact rule requires the course page) |

### Task 3: "I work full-time on weekdays, so I can only do Saturday or Sunday. List Beginner courses that meet on Saturday or Sunday."

Either-of list, 4 expected items. Class day is on **no** card in either variant.

| Run | Variant | Answer | Answer class | Verified | R | v1 | v2 |
|---|---|---|---|---|---|---|---|
| M7 | Original | "Beginners Yoga" | Partial 1/4 | 4/14 | 12 | F ✓ | F ✓ |
| M7 | Modified | "Wheel-thrown pottery", "Beginners yoga" | Partial 2/4 | 9/14 | 13 | F ✓ | F ✓ |
| Live | Original | "Beginners yoga - Beginner Saturday", "Mindful meditation - Beginner Sunday" | Partial 2/4 | 3/14 | 13 | F ✓ | F ✓ |
| Live | Modified | "Wheel-thrown Pottery" (after a guessed URL `/courses/yoga-for-beginners` → **404**) | Partial 1/4 | 9/14 | 13 | F ✓ | F ✓ |

All four are genuine incomplete navigation. The Modified change does not expose class day, so this task cannot benefit from it.

### Task 4: "I want to push beyond basics. Show me Intermediate courses at Northside."

List, 2 expected items. Level is on Modified cards, campus is not.

| Run | Variant | Answer | Answer class | Verified | R | v1 | v2 |
|---|---|---|---|---|---|---|---|
| M7 | Original | `[]` | Empty | 3/14 | 13 | F ✓ | F ✓ |
| M7 | Modified | "Life drawing studio", "Web pages from scratch" (one guessed URL `/courses/building-web-pages` → **404**, `/courses/` → **404**) | **Correct** | **12/14**: the campus of the two Riverside Intermediates was never seen | 13 | P **OC** | P **OC** |
| Live | Original | 3 checked non-matches + "No confirmed Intermediate at Northside found … (14 courses total, list page shows no Level/Campus, detail pages required)" (quoting the local mirror URL; shown as a site path since the M9 fix) | Incomplete (honest) | 3/14 | 13 | F ✓ | F ✓ |
| Live | Modified | "Life drawing studio", "Web pages from scratch" (`/courses/` → **404** once) | **Correct** | 14/14 | 12 | P ✓ | P ✓ |

### Task 5: "I want an Intermediate course at Riverside for after work. Among those, which one has the most seats left?"

Ranked subset, one expected answer: "Spanish conversation 2". The only other Intermediate course at Riverside is Furniture restoration.

| Run | Variant | Answer | Answer class | Verified | R | v1 | v2 |
|---|---|---|---|---|---|---|---|
| M7 | Original | "Spanish conversation 2" | **Correct** | **4/14**: Furniture restoration never seen; ER-2 not satisfied (2 of 3) | 13 | P **OC** | P **OC** |
| M7 | Modified | "Spanish conversation 2 - … 8 seats left (vs Furniture restoration with 1 seat on Sunday) …" | **Correct** | 14/14 | 11 | F **FN** | F **FN** (`multiple_candidates`, flagged for review); v2.1-contrast: P |
| Live | Original | "Spanish conversation 2 - Intermediate, Riverside, Thursday, 8 seats left" | **Correct** | **2/14**: Furniture restoration never seen | 13 | F (length; a strict reading would fail it anyway) | P **OC** |
| Live | Modified | "Spanish conversation 2 - … 8 seats left (the most …; the other Riverside Intermediate, Furniture restoration, is Sunday with only 1 seat left, and the other Intermediates are Northside)." | **Correct** | 14/14 | 11 | F **FN** | F **FN** (`multiple_candidates`, review); **v2.1-contrast: F** (no marker word) |

### Task 6: "… Find courses costing $180 or less that last 6 weeks or less."

List, 3 expected items. Fee and duration are on Modified cards.

| Run | Variant | Answer | Answer class | Verified | R | v1 | v2 |
|---|---|---|---|---|---|---|---|
| M7 | Original | 3 items with fee and weeks | **Correct** | **4/14**: the other 10 courses were not checked | 12 | F **FN** (detail in items) | P **OC** |
| M7 | Modified | 3 items with fee and weeks | **Correct** | 14/14 | 3 | F **FN** | P ✓ |
| Live | Original | "Mindful meditation - $120, 4 weeks", "Beginners yoga - $150, 6 weeks" | Partial 2/3 | 4/14 | 13 | F ✓ | F ✓ |
| Live | Modified | 3 bare names | **Correct** | 14/14 | 3 | P ✓ | P ✓ |

## 3. M7 vs the live run

| | M7 Original | M7 Modified | Live Original | Live Modified |
|---|---|---|---|---|
| Official v1 passes | 2/6 | 1/6 | 1/6 | 2/6 |
| Post-hoc v2 passes | 3/6 | 4/6 | 2/6 | 4/6 |
| **Correct answers** (audit) | **3/6** | **5/6** | **2/6** | **5/6** |
| **Correct and verified** from the facts shown (strict) | 1/6 | 4/6 | 1/6 | **5/6** |
| Incomplete navigation (partial, empty or none) | 3 | 1 | 4 | 1 |
| v1 false negatives | 1 | 4 | 1 | 3 |
| Requests (total) | 65 | 46 | 68 | 44 |

- **Modified behaviour is nearly deterministic.** Task 1 and task 2 Modified answers are word-for-word identical across the two runs; task 6 and task 4 match in content. These are tasks where the listing card answers the question in about 3 requests.
- **Original results differ mainly by luck.** Each Original trial decides only 2–4 of 14 courses, so whether a lucky early page happens to hold the answer decides the grade (task 6: M7 correct but unverified, live partial).
- **The live run reproduces M7's direction more clearly** once grading artefacts are removed. Correct and verified: Original 1/6 in both runs; Modified 4/6 → 5/6.
- **With 6 tasks × 1 repetition, none of this is statistically supported.** The paired exact sign-flip test gives p = 1.0 on the official v1 outcome (§5).

## 4. Root causes and severity

| # | Root cause | Effect | Severity | Trials |
|---|---|---|---|---|
| R1 | **v1 exact matching:** list items must be bare names; single answers must be ≤ expected answer + 16 characters | 9 correct answers failed; biased against Modified (7 of 9) | **High** (it is the official grader, and it reverses M7's headline direction) | M7: T1m, T2m, T5m, T6o, T6m · Live: T1m, T2m, T5o, T5m |
| R2 | **Evidence rule is positive only:** "the answer's pages were shown", not "every deciding fact was shown" | 4 correct-but-unverified answers credited (2 by v1, 4 by v2) | Medium (over-credit concentrated on Original, which narrows the measured difference) | M7: T4m, T5o, T6o · Live: T5o |
| R3 | **Page-fact evidence is page-specific:** it ignores the same fact stated on another page of the variant (the Modified card) | 1 supported answer judged unsupported | Low–medium | Live T2m |
| R4 | **v2 `multiple_candidates`:** a single-answer response that also names the rejected alternative fails | 2 correct, fully verified answers failed (flagged for review) | Medium | T5m (both runs) |
| R5 | **`v2.1-contrast` uses a marker word list** ("vs", "than", …) | The fix for R4 fails the next equivalent phrasing | Medium (a prospective rule; do not adopt) | Live T5m |
| R6 | **Verification cost is not modelled in task feasibility.** On Original, filter tasks need ≥15 page loads against a 14-request limit (observed about 3 requests per page). The generator records only `min_hops` = 2 | Original failures measure the request budget as much as the site; task 3 is effectively infeasible on **both** variants (class day is on no card) | Medium (disclosure and design; not a grading error) | 9 incomplete trials |
| R7 | **Task wording:** task 5's "for after work" has no time-of-day field and is not part of the criterion | Ambiguity only; the expected answer is the same under any reading. Agents read it as a weekday | Low | T5 |
| R8 | **Site behaviour seen by agents:** guessed slugs (`introduction-to-python` vs the real `intro-to-python`, `yoga-for-beginners`, `building-web-pages`), `/courses/` with a trailing slash and a query filter `?level=…&campus=…` all return 404 | Wasted requests; a genuine readiness finding about the site, not a grading issue | Low (a recommendation for the site owner) | 7 trials |

**Attribution of the 18 official v1 failures (both runs):**

| Cause | Failures |
|---|---|
| Grader false negatives (R1) | 9 (of which R4 also fails v2: 2) |
| Genuine incomplete navigation under the request limit (R6) | 9 |
| Incorrect facts | 0 |
| Wrong task or oracle definition | 0 |

## 5. Uncertain cases

- **Strict vs positive evidence (R2)** is a policy choice, not a fact. Under the product's stated rule ("the pages that contain the answer must have been shown"), the four OC passes are compliant. Under an exhaustive-verification reading they are lucky. Report both, rather than silently switching.
- **Live T5 Original** fails v1 on sentence length. Under strict evidence it would fail anyway (comparison not seen), so v1 is right for the wrong reason.
- **M7 T1 Original:** v2's reasons (`contradictory_detail`, `hedged`) are questionable for a partial answer, but the outcome (fail) is correct because 4 of 5 items are missing.
- **Statistical claims:** none can be made. The pre-registered analysis is exploratory (p = 1.0). The audit changes the interpretation of grading accuracy, not the evidential strength.

## 6. Recommendations

### Safe before the deadline (no grading or record change)
1. **Disclose these findings on the judge-facing report and in the submission:**
   - v1's measured false-negative rate and its bias against Modified;
   - that 9 of 18 failures are budget-limited navigation;
   - that no agent stated a false fact.

   Wording only: official v1 stays the grade of record and v2 stays labelled post-hoc. (A small UI note can be added on owner approval; this audit implements nothing.)
2. **Show this report's "correct answers" and "correct and verified" counts as an audit view,** not as grades, if shown at all. Present them only beside, never instead of, v1 and v2.
3. **Site recommendations for the Larkspur owner (the product's purpose):**
   - put campus and class day on the cards (task 3 and the remaining task 4 cost);
   - redirect `/courses/` to `/courses`;
   - consider filter URLs;
   - keep readable, predictable slugs.

### Deferred: a new, explicitly versioned prospective policy (needs owner approval and pre-registration before any use)
- **`grader v3` (proposed id `generated-criteria v3`):**
  - v2's consistent-detail acceptance for list items and sentences;
  - a **semantic** contrast rule (the alternative is named together with a fact that disqualifies or ranks it below, checked against that candidate's own facts) instead of a marker list;
  - the same hedge, negation and number checks as v2.
- **`evidence rule 3`:**
  - **(a)** fact-equivalent evidence: any page of *that variant* stating the deciding fact counts, which covers the Modified card;
  - **(b)** a separately reported **verification coverage** (decidable courses / all, as computed here), so "correct", "supported" and "verified" stay three distinct dimensions, never one composite score;
  - **(c)** extend `evidence-ranked-subset-2` to list tasks.
- **Task feasibility:** the generator should compute each task's **minimum verification cost** per variant (page loads needed to decide every course) and compare it with the request limit. Tasks that cannot be verified within the limit should be labelled, or the limit raised, before freezing a suite. Task 3 would be flagged on both variants.
- **Golden test set:** these 24 trials, with this audit's classifications, as reproducible fixtures for any future grader version (expected outcomes per trial, from the private matrix). A new grader must reproduce the ✓ cells and fix the FN cells without creating false positives.
- Re-grading the two recorded experiments with v3 would be a labelled post-hoc view, like v2. **Official v1 results are never overwritten.**

## 7. Reproducibility

- **Evidence extraction:** the trial records, the private criteria, `evalruns.runner.condition_results` (v1 reproduction and v2 rows), `grading.contrast` and `grading.evidence_ranked`. All are read-only.
- **Snapshot facts:** `framework.site.get('larkspur').snapshot(variant)` → `build_profile`, i.e. the course-page and listing text.
- **Model input check** (live T2 Modified): `trace.jsonl` model requests contain "Life drawing studio … Course fee $210".
- **404s:** the trial records' mirror logs.
- **Private outputs** (git-ignored): `scanner-data/grading-audit-m9/evidence.json`, `catalogue.txt`, `verification.txt`.
