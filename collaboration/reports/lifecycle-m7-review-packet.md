# M7 review packet: Larkspur Stage B suite (no expected answers)

Source: the 24 recorded M6 Muse Spark proposals (no new model call), evaluated by evaluator v2 at the current commit (deterministic; the M6 'at least' lexicon fix included). `in v1` = part of the immutable M6 proposal `larkspur-core` v1. Detail pages = pages beyond the listing the evidence rule requires on each variant (fewer on modified when its listing cards show the decisive facts).

## All natural-verifiable candidates

| Candidate | Executed wording (= customer wording) | Capability | Persona / journey | In v1 | Max requests | Detail pages (orig / mod) | Notes |
|---|---|---|---|---|---|---|---|
| `r1-t01_beginner_riverside_included` | I'm switching careers and want to start from scratch. Show me Beginner courses at Riverside where materials are Included. | multi_condition_filter | career_switcher / match_level | yes | 14 | 5 / 5 | catalogue-speak: capitalised 'Beginner', 'Included' |
| `r1-t02_lookup_pottery_day` | I work weekdays and I'm interested in Wheel-thrown pottery — what class day does it meet on? | lookup | career_switcher / fit_schedule | yes | 14 | 0 / 0 | names the field label ('what class day'); otherwise realistic |
| `r1-t03_weekend_beginner` | I work full-time on weekdays, so I can only do Saturday or Sunday. List Beginner courses that meet on Saturday or Sunday. | either_of | career_switcher / fit_schedule | yes | 14 | 4 / 4 | **SELECTED: either/or scheduling**. realistic; both alternatives contribute |
| `r1-t04_affordable_short` | I just graduated and need a cheap, quick skill for my CV. Find courses costing $180 or less that last 6 weeks or less. | multi_condition_filter | recent_graduate / find_affordable | yes | 14 | 3 / 0 | **SELECTED: multi-condition filter**. realistic; the vague 'cheap, quick' is backed by explicit values |
| `r1-t05_lookup_meditation_fee` | My friend mentioned Mindful meditation as a cheap option — how much is the course fee? | lookup | recent_graduate / find_affordable | no | 14 | 0 / 0 | realistic |
| `r1-t06_intermediate_northside` | I want to push beyond basics. Show me Intermediate courses at Northside. | multi_condition_filter | recent_graduate / match_level | no | 14 | 2 / 2 | **SELECTED: distinct journey: match_level**. terse but realistic; capitalised 'Intermediate' |
| `r1-t08_budget_with_seats` | I need a course that costs $250 or less and still has at least 5 seats left. What qualifies? | multi_condition_filter | budget_learner / check_availability | no | 14 | 5 / 0 | **SELECTED: availability (multi-condition; the M6 false rejection, corrected)**. plain; rejected AS RUN by the 'at least' lexicon bug, admitted after the fix (M6 §4.1) |
| `r1-t12_lookup_duration_spreadsheets` | I'm considering Spreadsheets for small business but need to judge the time commitment — how long is the duration? | lookup | professional_upskiller / plan_commitment | yes | 14 | 0 / 0 | redundant field label ('how long is the duration?') |
| `r2-budget-cheap-under-200` | Money is really tight right now. What courses cost under $200? | single_condition_filter | budget_learner / find_affordable | yes | 14 | 3 / 0 | realistic |
| `r2-upskiller-intermediate-seats` | I need an Intermediate course that still has at least 5 seats left so I can join with a colleague. What qualifies? | multi_condition_filter | professional_upskiller / check_availability | no | 14 | 2 / 0 | realistic; rejected AS RUN by the 'at least' lexicon bug, admitted after the fix |
| `r2-budget-riverside-fee` | I can only get to Riverside. Which courses at Riverside cost $250 or less? | multi_condition_filter | budget_learner / fit_schedule | yes | 14 | 4 / 4 | realistic |
| `r2-upskiller-thursday-intermediate` | Work keeps me busy, but Thursdays are free. I'm looking for an Intermediate course that meets on Thursday. | multi_condition_filter | professional_upskiller / fit_schedule | yes | 14 | 2 / 2 | realistic; 'busy, but Thursdays' traced only via the second 'Thursday' (negation window does not reset at 'but') |
| `r2-switcher-beginner-materials-budget` | I'm trying a new field and want a Beginner course where materials are Included and the fee is $300 or less. What are my options? | multi_condition_filter | career_switcher / find_affordable | yes | 14 | 5 / 5 | catalogue-speak ('materials are Included') |
| `r2-recent-cheapest-beginner` | I just graduated and want to add a skill. I'm a Beginner — what's the cheapest Beginner course? | ranked_subset | recent_graduate / find_affordable | no | 14 | 1 / 0 | repetitive ('I'm a Beginner - what's the cheapest Beginner course?') |
| `r2-upskiller-riverside-most-seats` | I want an Intermediate course at Riverside for after work. Among those, which one has the most seats left? | ranked_subset | professional_upskiller / check_availability | yes | 14 | 1 / 1 | **SELECTED: filtered ranking**. realistic; ranking among a filtered subset of 2 |
| `r2-switcher-watercolour-seats` | I'm thinking of Watercolour foundations as a first creative course. How many seats are left in Watercolour foundations? | lookup | career_switcher / check_availability | no | 14 | 0 / 0 | repeats the course name; otherwise realistic |
| `r2-budget-life-drawing-fee` | I like the sound of Life drawing studio but need to watch spending. What is the course fee for Life drawing studio? | lookup | budget_learner / find_affordable | no | 14 | 0 / 0 | **SELECTED: factual lookup**. repeats the course name; otherwise realistic |
| `r2-switcher-webpages-materials` | If I sign up for Web pages from scratch, do I need to sort my own stuff or are materials Included? What are the materials for Web pages from scratch? | lookup | career_switcher / plan_commitment | yes | 14 | 0 / 0 | FLAG: yes/no-shaped ('are materials Included?') while the graded answer is a value; recommend EXCLUDING |
| `r2-recent-saturday-courses` | I work weekdays so I can only come on Saturday. Which courses meet on Saturday? | single_condition_filter | recent_graduate / fit_schedule | yes | 14 | 3 / 3 | realistic |
| `r2-budget-beginner-short` | I want something easy to start and quick to finish — a Beginner course that lasts 4 weeks. What is available? | multi_condition_filter | budget_learner / match_level | no | 14 | 2 / 0 | FLAG: 'lasts 4 weeks' is specified as EXACTLY 4 weeks; a customer may mean 'about' or 'at most' (possible ambiguity) |

Not natural-verifiable: `r1-t09_refund_policy` (natural_judgment, policy rubric: not scored deterministically, excluded from Stage B); `r1-t07` (spec changed 'under' to 'at most'), `r1-t10` (ranking within a filter of one item), `r1-t11` (degenerate either/or): correct rejections.

## Selection (six natural-verifiable tasks)

- **multi-condition filter**: "I just graduated and need a cheap, quick skill for my CV. Find courses costing $180 or less that last 6 weeks or less." (recent_graduate / find_affordable; `r1-t04_affordable_short`)
- **either/or scheduling**: "I work full-time on weekdays, so I can only do Saturday or Sunday. List Beginner courses that meet on Saturday or Sunday." (career_switcher / fit_schedule; `r1-t03_weekend_beginner`)
- **filtered ranking**: "I want an Intermediate course at Riverside for after work. Among those, which one has the most seats left?" (professional_upskiller / check_availability; `r2-upskiller-riverside-most-seats`)
- **factual lookup**: "I like the sound of Life drawing studio but need to watch spending. What is the course fee for Life drawing studio?" (budget_learner / find_affordable; `r2-budget-life-drawing-fee`)
- **availability (multi-condition; the M6 false rejection, corrected)**: "I need a course that costs $250 or less and still has at least 5 seats left. What qualifies?" (budget_learner / check_availability; `r1-t08_budget_with_seats`)
- **distinct journey: match_level**: "I want to push beyond basics. Show me Intermediate courses at Northside." (recent_graduate / match_level; `r1-t06_intermediate_northside`)

Coverage of the six: personas recent_graduate 2, budget_learner 2, career_switcher 1, professional_upskiller 1; journeys find_affordable 2, check_availability 2, fit_schedule 1, match_level 1 (plan_commitment not covered); capabilities multi-condition filter 3, either_of 1, ranked_subset 1, lookup 1.
Excluded on quality: the yes/no-shaped materials lookup (`r2-switcher-webpages-materials`) and the exact-'4 weeks' task (`r2-budget-beginner-short`); no wording was rewritten.

**Provisional suite targets NOT met by v2** (reported, not lowered): deterministic_tasks: 6 (target 8-12); tasks_per_persona: {'budget_learner': 2, 'career_switcher': 1, 'professional_upskiller': 1, 'recent_graduate': 2} (target >= 2 each); weighted_journeys: {'check_availability': 2, 'find_affordable': 2, 'fit_schedule': 1, 'match_level': 1, 'plan_commitment': 0} (target >= 1 for each journey with weight >= 0.1). The six-task size is the owner's budget design for this first paid evaluation; the targets were written for 8-12-task suites.

**Answers and this packet:** no task's wording contains its own expected answer (acceptance gate). Course names do appear in lookup wordings, and a few of those courses are among the answers of OTHER tasks (e.g. a lookup names a course that a filter task selects). That links no answer to its task; a global substring scan flags it, the per-task check does not. The agent never sees this packet.

## Revision (v1 is preserved, immutable)

- v1 `larkspur-core` (13 tasks, unchanged): `873e07c306cafc6772706c528391ffe5ef734eb7e3ca6216e2bd780b81e8ed89`
- v2 proposal `larkspur-core` (6 tasks; prepared by the system, NOT approved): `172d1e712eb18871fd4f24b227a2448ec44a546347bb9874f0946c5609f7848b`
- kept from v1: 3; added (re-validated offline): 3; removed from v1: 10

## Owner checkpoint: commands (run them yourself, in an interactive terminal; not through an agent)

```bash
cd ~/Projects/Hack_Agent_Readiness
.venv/bin/python -m agent_readiness.suites.stage_a.approval review scanner-data/research/stage-a/store 172d1e712eb18871fd4f24b227a2448ec44a546347bb9874f0946c5609f7848b --markdown
.venv/bin/python -m agent_readiness.suites.stage_a.approval decide scanner-data/research/stage-a/store 172d1e712eb18871fd4f24b227a2448ec44a546347bb9874f0946c5609f7848b approved --notes "M7: six-task Larkspur suite"
#   type exactly the attestation it prints; it prints the APPROVAL hash
.venv/bin/python -m agent_readiness.suites.stage_a.approval freeze scanner-data/research/stage-a/store 172d1e712eb18871fd4f24b227a2448ec44a546347bb9874f0946c5609f7848b <APPROVAL_SHA>
#   it prints the FROZEN SUITE hash: send it back to continue
```

