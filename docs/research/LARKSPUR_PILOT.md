# Larkspur end-to-end pilot: evaluator-selected LLM tasks on a real agent (2026-11-02)

**Status:** isolated research on branch `research/llm-task-planning`. It is not part of the release candidate, nothing was deployed, and the hosted path and budget are untouched.

**Scope:** one repetition, 4 tasks × 2 site versions = 8 paid browser trials. Exploratory: no pre-registered comparison rule. The sample is too small for any statistical claim.

## Components

- **`agent_readiness/taskeval/` (taskeval-1, config fingerprint `6fa92ba0ee58ad55`).** A code-only evaluator, with no LLM judge.
  - **Hard deterministic gates:** schema, grounding, expressible, answerable, unique, executable wording passes the acceptance gate (which also catches answer leaks), oracle agrees, grader v1 compatible, grader v2 compatible, cross-version fair, evidence sufficient.
  - **Soft judgments with explicit criteria:** persona relevance (a documented, synthetic persona-to-attribute map), journey relevance, realism (question form, customer context, length, no quoted field names), specificity (constraint values stated in the customer's own words; the rest are recorded as assumptions the generator introduced), and novelty.
  - Soft scores rank candidates; they never admit one.
- **`taskeval/select.py` (selection-1).** Deterministic greedy coverage: +3 per new persona, +2 per new journey, +1 per new attribute, +3 for the first multi-condition task, plus quality. Ties are broken by id. It never uses agent performance.
- **`research/pilot.py`.**
  - Freezes the suite in the standard run layout (snapshot, profile, tasks-manifest, private criteria, evaluator records, selection, provenance).
  - Computes the worst-case reservation from the frozen limits and enforces a US$5 hard ledger cap.
  - Enables the hosted browser jail in require mode and self-tests it.
  - Runs counterbalanced trials through `run_trial` with the RequestGate. No retries; it halts on a void trial or a gate violation.
  - The report reuses `framework.evaluate.results`, `grading.rescore`, `provenance` and `diagnostics` unchanged.

## Evaluator findings for all 20 Muse Spark proposals (run `taskplan-20261102T203537-meta-7aca17`)

**17 of 20 pass every hard gate.**

| Candidate | Persona | Journey | Attributes | Hard gates | Quality | Specificity | Natural wording passes gate | Selected |
|---|---|---|---|---|---|---|---|---|
| cs_affordable_beginner_included_01 | career switcher | find_affordable | fee, level, materials | pass | 0.70 | 0.33 | no | **Y** |
| rg_affordable_under180_02 | recent graduate | find_affordable | fee | pass | 0.80 | 0.00 | no | |
| bl_cheapest_beginner_03 | budget learner | find_affordable | – | **fail: expressible** (ranking within a filtered subset) | – | – | no | |
| pu_lookup_fee_lifedrawing_04 | upskiller | find_affordable | fee | pass | 0.50 | – | yes | |
| bl_affordable_riverside_05 | budget learner | find_affordable | campus, fee | pass | 0.72 | 0.50 | no | |
| rg_best_cheap_short_06 | recent graduate | find_affordable | – | **fail: expressible** (ranking within a filtered subset) | – | – | no | |
| cs_saturday_beginner_07 | career switcher | fit_schedule | class day, level | pass | 0.97 | 1.00 | no | |
| pu_northside_tuesday_08 | upskiller | fit_schedule | campus, class day | pass | 1.00 | 1.00 | no | **Y** |
| rg_sunday_courses_09 | recent graduate | fit_schedule | class day | pass | 0.70 | 1.00 | no | |
| bl_riverside_monday_10 | budget learner | fit_schedule | campus, class day | pass | 0.67 | 1.00 | no | |
| cs_lookup_day_pottery_11 | career switcher | fit_schedule | class day | pass | 0.80 | – | yes | |
| pu_intermediate_list_12 | upskiller | match_level | level | pass | 0.90 | 1.00 | yes | |
| cs_beginner_included_13 | career switcher | match_level | level, materials | pass | 0.78 | 0.50 | no | |
| pu_advanced_list_14 | upskiller | match_level | level | pass | 1.00 | 1.00 | yes | |
| pu_intermediate_seats_15 | upskiller | check_availability | level, seats left | pass | 0.85 | 0.50 | no | |
| cs_lookup_seats_japanese_16 | career switcher | check_availability | seats left | pass | 0.50 | – | yes | |
| bl_seats_cheap_17 | budget learner | check_availability | fee, seats left | pass | 0.75 | 0.00 | no | **Y** |
| rg_short_duration_18 | recent graduate | plan_commitment | duration | pass | 0.80 | 0.00 | no | **Y** |
| cs_lookup_duration_spreadsheets_19 | career switcher | plan_commitment | duration | pass | 0.50 | – | yes | |
| bl_refund_policy_20 | budget learner | understand_policies | – | **fail: expressible** (open policy question; rubric) | – | – | no | |

For the three failures, the other gates also fail as a cascade, because no verifiable specification exists.

**Specificity** exposes the generator's assumptions. "A few weeks" became `duration ≤ 4 weeks`. "Low-cost courses that still have places" became `fee ≤ $250 AND seats left ≥ 5`. A specificity of 0 means every threshold was the LLM's choice, not the customer's words.

## Selection (deterministic, before any execution)

| Step | Picked | Score |
|---|---|---|
| 1 | cs_affordable_beginner_included_01 | 11.70 |
| 2 | pu_northside_tuesday_08 | 8.00 |
| 3 | rg_short_duration_18 | 6.80 |
| 4 | bl_seats_cheap_17 | 6.75 |

- **Coverage:** 4/4 personas; 4/6 journeys (find_affordable, fit_schedule, plan_commitment, check_availability); 7/7 verified attributes; 3 of 4 tasks are multi-condition (one has 3 conditions).
- **Freezing:** the suite was frozen as manifest `79444aee…` (criteria `1e8e2751…`, site versions original `2f9fd2ce…` and modified `edb9a5d2…`). It was byte-identical in the zero-cost preflight and the paid run.
- **Executed wording:** the restated question for all four tasks (customer question + "Precisely: <statement generated from the verified criterion>"). The customer question is preserved separately. **None of the four customer questions passes the gate on its own**, and the restated form is not assumed to be equally difficult.

## Execution

| Item | Detail |
|---|---|
| Jail | self-test ok (mirror reachable, escapes blocked, filesystem hidden); every trial records `browser_isolation: netns-loopback-mirror-only` |
| Model and profile | muse-spark-1.3, profile `suite-v2-compat2` (sha256 `29ad53dc…`, verified against the profile file); `reasoning_effort` low, `max_completion_tokens` 4096, the same on all 83 requests |
| Graders | official grader v1; grader v2 rescore faithful |
| Order | counterbalanced |
| Retries | none; no trial was void and nothing was halted |

**Zero-cost preflight:** the same frozen suite, dev provider (not a model), jailed: 8/8 trials, rescore faithful.

## Results (real agent; exploratory, n = 1 per cell)

| Task (executed wording) | Original | Modified |
|---|---|---|
| fee ≤ $250 AND seats left ≥ 5 (budget learner) | not passed: no answer; 13 requests; 2 of 14 course pages opened | **passed, evidence-supported: 5/5 correct; 3 requests; 0 course pages opened** |
| duration ≤ 4 weeks (recent graduate) | not passed: 1 of 2 found; 13 requests | **passed, evidence-supported: 2/2; 3 requests** |
| campus Northside AND class day Tuesday (upskiller) | not passed: no answer; 13 requests; 3 pages opened | not passed: no answer; 13 requests; 3 pages opened |
| level Beginner AND fee ≤ $300 AND materials Included (career switcher) | not passed: 1 of 5 found; 12 requests | not passed: 3 of 5 found; 13 requests |
| **Total** | **0/4 evidence-supported; 51 requests** | **2/4; 32 requests** |

grader_v1 and grader_v2 agree on every trial: none of the failures is a wording false negative.

**The outcome follows what the listing cards show.**
- Modified cards state fee, duration and seats left, so the two tasks needing only those facts were answered from the listing in 3 requests.
- The tasks also needing campus, class day or materials require opening course pages on both versions, because those facts are on neither version's cards. The agent opened at most 3 of 14 course pages before running into its 13–14-request limit, and failed on both versions.

**Navigation behaviour** (behavioural diagnostics, observed):
- **Budget exhaustion:** 3 Original and 2 Modified trials.
- **Revisits** of `/courses`: 4 Original, 2 Modified.
- **Unnecessary navigation:** 3 trials.
- **Dead ends:** the agent guessed URLs that do not exist (`/enrolment`, `/courses/italian-for-travellers`, `/courses/japanese-for-travellers-1`), the same pattern as Ironbark's `/hire/wood-chipper-100-mm`.

**Diagnostics linked to tasks:** the structural layer detects exactly Modified's change (fee, duration and seats left resolved on cards).

| Hypothesis | Original → Modified | Status | Basis |
|---|---|---|---|
| "Cards omit seats left" | 2 → 0 item pages; 13 → 3 requests; 0 → 1 supported | **hypothesis** | behaviour improved, but no recorded comparison rule supports it |
| "Cards omit duration" | 3 → 0 item pages; 13 → 3 requests; 0 → 1 supported | **hypothesis** | as above |
| "Cards omit course fee" | improved (2 tasks) | **hypothesis** | as above |
| "Cards omit campus / class day / materials" | no improvement; these facts are missing from both versions | **hypothesis** | untested: no version without the gap was run |

## Cost and latency

| Item | Value |
|---|---|
| Model requests | 83 (801,116 prompt + 53,510 completion tokens) |
| **Calculated from usage (not a bill)** | **US$1.228813** |
| Reserved as it went | US$2.938332 (all settled, 0 open) |
| Worst case allowed | US$4.928; hard cap US$5 |
| Agent time | 530 s in total across the 8 trials. Successful Modified trials took about 21 s; budget-limited trials 67–101 s. |
| Earlier task-generation request | US$0.024452, 18.2 s (paid run 2 of the planner experiment) |

The programme ledger records this as `research-pilot-larkspur-1`. The known-spend subtotal is US$11.848482 / A$17.7727.

## Limitations

- **Tiny sample:** one repetition, 4 tasks × 2 versions. No pre-registered rule, so every comparison is exploratory and no verdict is claimed.
- **Restated wording:** it states criteria precisely and may be easier, or simply different, than the natural customer request. The natural wording was not executed, because it fails the acceptance gate.
- **Thresholds chosen by the LLM:** budget and timing thresholds, such as $250 or 4 weeks, were the LLM's choices, not the customers'. They are recorded as assumptions.
- **Persona model:** the persona-to-attribute map and the journey weights are synthetic, and the realism criteria are simple heuristics.
- **Request limits:** the 13–14-request limits come from the frozen generator (8 + 3 × hops). Tasks that require scanning many course pages hit them on both versions. That may say as much about the limit as about the site.
- **Two weak spots in the evaluator:** it imports the research planner's verifier (to be promoted before productisation), and no LLM judge was used. Business relevance rests on explicit rules only.
