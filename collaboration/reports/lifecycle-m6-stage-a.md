# Report: lifecycle M6, first paid Stage A task-generation experiment (Larkspur)

**Date:** 2026-11-02. **Branch:** `research/llm-task-planning`.

**Authorisation (owner, 2026-11-02):** ONE Stage A generation experiment with a hard total cap of **US$0.10**. It does not cover Stage B, further experiments or any other paid use.

**Not done, by design:**
- no Stage B and no browser-agent call;
- no approval or freezing: the `larkspur-core` proposal is UNAPPROVED and the decision is the owner's, at an interactive terminal;
- no deployment or merge;
- no change to production or frozen experiments.

## 1. Result in one paragraph

**Two paid requests, calculated cost US$0.049804** (cap US$0.10).
- Meta **accepted `taskplan-schema-v3`** (strict structured output) on the first request.
- The loop stopped at **`targets_met` after round 2**, so the third request was never sent.

**As run:** 24 proposals gave 18 natural_verifiable tasks, 1 judgment (policy rubric), 0 underspecified, 0 assisted and 5 rejected. Every admitted task passed every hard gate (oracle agreement, answerability, grader v1/v2, cross-variant fairness, evidence). The selected suite has 12 natural deterministic tasks plus 1 rubric task and meets every provisional coverage target.

**Review found a lexicon bug.** "at least 5 seats left" was read as the superlative "least", so **2 of the 5 rejections were false rejections** of realistic phrasing. It was fixed at zero cost and the same 24 recorded proposals were re-evaluated offline: **20 natural_verifiable, 1 judgment, 3 correct rejections**, with no paid call.

## 2. Configuration and enforcement actually used

| Setting | Value |
|---|---|
| Model / effort / completion cap | `muse-spark-1.3` / `low` / 6000 tokens per request |
| Prompt / schema | `taskplan-v2` / `taskplan-schema-v3` (strict) |
| Proposals per round / rounds / requests | 12 / ≤ 3 / ≤ 3 |
| Caps | total US$0.10 (run cap in the durable gate, ledger ceiling, loop budget stop); per request US$0.04 |
| Gate run id / ledger | `m6-larkspur-core` / `scanner-data/research/stage-a/ledgers/m6-larkspur-core/ledger.jsonl` (fixed path) |
| Suite name | `larkspur-core` (proposal only) |

**Per-request cap.** US$0.04 was chosen by the agent, not the owner. The preflight refused US$0.035 because a pathologically large feedback round could reserve US$0.035135. The US$0.10 total is enforced on every actual request regardless of the per-request figure.

**Enforcement, inspected before any paid call** (`spend_gate.py`, `ledger.py`, `investigate/llm/meta.py`):
- **Reserve before send.** The worst-case bound is written to an fsync'd ledger before the POST.
- **Durable across restarts.** The request count, the committed amount and any bound-violation flag are re-read from the ledger. The ledger lives in a fixed directory, so a restart cannot exceed 3 requests or US$0.10. Rehearsed: a "restarted" client was refused at the request-count cap.
- **No retries.** `MetaClient.complete` makes exactly one POST; httpx does not retry; redirects are off. The loop never retries a round: a provider error, schema rejection or gate refusal now stops the loop as `generator_error`, with the error preserved.
- **Failures cost their full reservation.** An HTTP 400 keeps the full reservation counted (rehearsed).

**Mandatory preflight** (`python -m agent_readiness.suites.experiments.m6_stage_a --preflight-only`; zero cost; all 8 checks passed):
1. model settings;
2. verified published prices (US$1.25 / US$4.25 per M tokens);
3. credential present (the value was never printed);
4. schema v3 uses only keywords Meta has already accepted, every object strict, and the fixture pool validates and parses;
5. reservation bounds (rehearsed rounds US$0.029344 and US$0.030350);
6. fresh ledger;
7. the real `MetaClient` and gate over a mock HTTP transport with this experiment's caps and request bodies: reserve before every send, settlement, restart refusal, HTTP 400 handling;
8. isolation (branch, Stage A boundary clean).

The preflight result was saved before the paid call (`m6-larkspur-core-20261102T121242Z.preflight.json`).

**Zero-cost changes committed before the paid run** (`b930daa`):
- the fixed-ledger `MetaGenerator`;
- the loop preserving generator errors, latency, finish reason and reasoning tokens;
- the experiment driver and its preflight;
- 4 tests.

**Programme ledger.** Before the run, the known-spend subtotal was US$11.848482, about A$17.77 of the A$50 limit.

## 3. Cost, tokens, latency

| Round | Reserved | Calculated cost | Prompt tokens | Completion tokens (reasoning) | Latency | Finish reason |
|---|---|---|---|---|---|---|
| 1 | US$0.029344 | **US$0.020578** | 2,917 | 3,984 (2,216) | 19.9 s | stop |
| 2 | US$0.030274 | **US$0.029226** | 3,678 | 5,795 (4,050) | 24.6 s | stop |
| **Total** | US$0.059618 | **US$0.049804** | 6,595 | 9,779 (6,266) | 44.5 s | |

- Both reservations were settled from provider-reported usage. Neither settled above its reservation; there was no bound violation and nothing is unsettled.
- Costs are calculated at published prices; they are not a bill.
- The programme ledger was appended (entry `research-stage-a-m6-1`), taking the known-spend subtotal from **US$11.848482 to US$11.898286** (A$17.85 at the ledger's 1.5 rate).
- **Watch item:** round 2 used 5,795 of the 6,000 completion tokens, 4,050 of them reasoning, and still finished with `stop`. A larger feedback slot or more proposals per round could truncate the JSON. With only 205 tokens of headroom, 12 proposals per round is near the practical limit at this cap.

## 4. Task quality

### 4.1 Categories and rejections (24 proposals)

| | As run (evaluator at `b930daa`) | Post-fix re-evaluation (offline, same proposals) |
|---|---|---|
| natural_verifiable | 18 | **20** |
| natural_underspecified | 0 | 0 |
| natural_judgment | 1 (refund policy, rubric) | 1 |
| assisted_restatement | 0 | 0 |
| rejected | 5 | 3 |
| round 1 / round 2 natural | 7 / 11 of 12 | 8 / 12 of 12 |

**Rejections and their assessment:**

| Proposal (customer wording) | Reason | Assessment |
|---|---|---|
| "Money is tight. What's the cheapest course under $200?" (spec: course fee *at most* $200) | intent not preserved: "under" means below | **Correct.** The generator changed the comparator. No course costs exactly $200 today, so the answer would coincide, but the rule must hold on any snapshot. The feedback named it, and round 2 used `less_than` for "under $200". |
| "…costs $250 or less and still has at least 5 seats left" | "'least 5 seats left' asks for a ranking" | **FALSE REJECTION** (lexicon bug, fixed) |
| "…an Intermediate course that still has at least 5 seats left…" (round 2) | same | **FALSE REJECTION.** The faulty reason was fed back in round 2, so the generator repeated the phrasing and was rejected again. |
| "…an Advanced course that meets on Tuesday. Among those, … the most seats left" | the filter selects 1 item: nothing to rank | **Correct** (ill-posed: one Advanced Tuesday course) |
| "…an Intermediate or Advanced course at Northside costing $300 or less" | degenerate either/or: no Advanced course under those conditions | **Correct** (the only Advanced course is $480). It is a realistic request, but it does not test OR. |

**The bug.** `gate-nl-1` treated "least" in "at least 5" as a superlative followed by the "seats" cue. Fix: a "least"/"most" preceded by "at" or "the" and followed by a number is a comparator. Three regression tests were added, including one proving a real superlative ("the most seats left") is still caught. Re-evaluated offline, both rejected tasks become natural_verifiable and nothing else changes.

### 4.2 Fidelity: dropped or invented constraints

- **No admitted task has an invented or dropped constraint.** Every constraint value was traced to the customer's words, and no stated value went unrepresented. The one changed comparator was caught.
- **Zero underspecified requests.** `taskplan-v2` asks the generator to prefer stating values, and it complied every time. That gives high verifiability but **less realism**: the suite contains no "a few weeks"- or "affordable"-style requests. The six vague requests seen in the earlier `taskplan-v1` run did not recur.
- **Realism concern ("catalogue-speak").**
  - 12 of 24 wordings capitalise catalogue values mid-sentence ("Show me Beginner courses at Riverside where materials are Included").
  - 11 of 24 name a field label ("what class day", "how long is the duration?").
  - Mean length is 18.7 words.

  These are natural enough to execute, but stilted. The deterministic checks cannot score this; it needs the owner's review (or the deferred advisory realism judge).

### 4.3 Oracle agreement and answerability

- **Every admitted task:** independent record oracle agrees with the page-derived answer; answerable (some but not all items, no ties); grader v1 and v2 compatible; same answer on both site variants; evidence pages exist.
- The two answerability rejections were correctly refused as ill-posed.

### 4.4 Coverage, diversity, redundancy

| | As run | Post-fix |
|---|---|---|
| Admitted capabilities | multi-condition filter 7, lookup 6, single-condition filter 2, ranked_subset 2, either_of 1 | multi 9, lookup 6, single 2, ranked 2, either 1 |
| Persona × journey cells with an admitted task | 14 / 24 | 15 / 24 |
| Near-duplicate admitted pairs (> 0.6 similarity) | 0 | 0 |
| Selected suite | 12 natural deterministic + 1 rubric; natural share 1.00; multi-condition share 0.58; targets met | 12 + 1; multi-condition share 0.67; targets met |
| Per persona (selected) | career_switcher 5, recent_graduate 2, budget_learner 3, professional_upskiller 3 | 4, 2, 4, 3 |
| Per journey (selected) | find_affordable 3, fit_schedule 5, match_level 1, check_availability 1, plan_commitment 2, understand_policies 1 | 3, 5, 1, 2, 1, 1 |

- No extremum (unfiltered "best") task was generated.
- Either/or is under-represented: 1 admitted, and the other one was degenerate.
- fit_schedule is over-represented relative to its 0.25 weight.

### 4.5 Across the feedback round

Round 1's feedback listed:
- uncovered cells and missing capabilities (single-condition filter, extremum, ranked_subset);
- the gaps: professional_upskiller and budget_learner below 2 tasks, no check_availability task, 7 of 8 deterministic tasks.

Round 2 addressed the coverage gaps:
- added 2 check_availability tasks, professional_upskiller tasks, 2 single-condition filters and 2 ranked_subsets;
- fixed the "under" comparator;
- avoided the ill-posed shapes;
- produced no duplicates.

**Natural admissions rose from 7/12 to 11/12** (12/12 post-fix). The single round-2 rejection was the lexicon bug, and the faulty feedback reason contributed to it. Extremum was still not proposed.

## 5. Representative generated tasks (customer wording; expected answers kept private)

Selected, natural_verifiable:
- **multi-condition filter:** "I just graduated and need a cheap, quick skill for my CV. Find courses costing $180 or less that last 6 weeks or less." The vague "cheap, quick" is backed by stated values.
- **either_of:** "I work full-time on weekdays, so I can only do Saturday or Sunday. List Beginner courses that meet on Saturday or Sunday." "Weekdays" is recognised as a negative mention.
- **ranked_subset:** "I want an Intermediate course at Riverside for after work. Among those, which one has the most seats left?"
- **multi-condition filter:** "Work keeps me busy, but Thursdays are free. I'm looking for an Intermediate course that meets on Thursday."
- **single-condition filter:** "Money is really tight right now. What courses cost under $200?"
- **lookup:** "I work weekdays and I'm interested in Wheel-thrown pottery — what class day does it meet on?"
- **lookup, quality concern:** "If I sign up for Web pages from scratch, do I need to sort my own stuff or are materials Included? What are the materials for Web pages from scratch?" It invites a yes/no reply, while the graded answer is a value. Consider rejecting it on review.
- **policy rubric:** "If I enrol and then can't attend, can I get a refund? Explain the college refund policy."

Admitted, not selected:
- "I want something easy to start and quick to finish — a Beginner course that lasts 4 weeks. What is available?"
- "… I'm a Beginner — what's the cheapest Beginner course?" (excerpt; ranked_subset)

Rejected examples are listed in §4.1. The full owner review packet (Markdown, no answers) is at `scanner-data/research/stage-a/m6-larkspur-core-20261102T121242Z/review-packet.md`.

## 6. Outputs (git-ignored; preserved verbatim)

Run directory `scanner-data/research/stage-a/m6-larkspur-core-20261102T121242Z/`:
- `experiment.json`: settings, approval note, cost, ledger entries, per-round records with request hashes, usage, latency, finish reason and reasoning tokens;
- `loop.json`: full per-round records including the raw response text and feedback in/out;
- `proposals.json` (raw proposals);
- `evaluation.public.json`;
- `evaluation.private.json` (0600; expected answers);
- `feedback-r2.json`, `coverage.json`, `gap-report.json`, `suite-proposal.json`, `review-packet.md`;
- `re-evaluation-post-fix/` (offline, labelled).

Elsewhere:
- the preflight record (`../m6-larkspur-core-20261102T121242Z.preflight.json`);
- the durable ledger (`../ledgers/m6-larkspur-core/ledger.jsonl`);
- the store `scanner-data/research/stage-a/store/` with **UNAPPROVED** suite proposal `larkspur-core` v1 `873e07c306cafc6772706c528391ffe5ef734eb7e3ca6216e2bd780b81e8ed89`, its 13 task records and 12 private outcomes. No approval and no frozen suite exist. The leak check found no expected answer in any stored public record.

**The stored proposal reflects the as-run evaluation.** It does not include the two falsely rejected tasks. The post-fix selection (in `re-evaluation-post-fix/selection.json`) swaps in "costs $250 or less and still has at least 5 seats left". If the owner prefers the corrected selection, it can be stored as a new version through `approval.revise` at review time. That would be a zero-cost owner action.

## 7. Limitations

- **One run, one model setting, 24 proposals.** No statistical claim can be made about generator quality.
- **Lexicon coverage.** The run exposed a parsing bug in a common construction ("at least N"). More such cases are likely:
  - "busy, but Thursdays" only traced because "Thursday" recurs later, since the negation window does not reset at "but";
  - a comparator-word audit over a larger real corpus is advisable.
- **The `taskplan-v2` prompt's "prefer stating values"** produced 0 vague requests and catalogue-speak wording. Realism, and the share of genuinely underspecified customer requests, needs owner review before the prompt is changed.
- **The yes/no-shaped lookup** shows that the v1 gate's "yes/no answer" rule only checks the answer, not the question form.
- **Completion headroom** is thin at 12 proposals per round (§3).
- **The feedback synthesiser repeats evaluator reasons verbatim,** so an evaluator bug becomes misleading generator guidance (seen in round 2).

## 8. Recommended next step

Review the 13 selected tasks and the two corrected ones together, using `review-packet.md` and §5. Decide:
1. whether to accept the post-fix selection (a revision, then the owner's decision at a terminal);
2. whether catalogue-speak wordings are acceptable, or whether `taskplan-v3` should ask for more colloquial phrasing while keeping values explicit;
3. whether the yes/no-shaped lookup should be excluded.

Before any further paid generation:
- extend the lexicon tests with a comparator/negation corpus taken from this run;
- reset the negation window at "but";
- consider 10 proposals per round, or a higher completion cap, for headroom.

No further paid call is proposed until the owner has reviewed.
