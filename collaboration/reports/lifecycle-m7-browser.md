# Report: lifecycle M7, first paid Stage B browser-agent evaluation (Larkspur)

**Date:** 2026-11-02. **Branch:** `research/llm-task-planning` (not merged, not deployed).

**Authorisation.** The owner's conditional paid authorisation, amended to 6 natural tasks × 2 variants × 1 repetition = **12 trials**, with a hard cap of **US$8.00**. The condition was met by the owner: suite `larkspur-core` v2 was approved and frozen at an interactive terminal (approval `31f1e3aa…` at 12:40:29 UTC; frozen suite `0816af7f7440bb08fae6235c9cb77642d434dce1a8db585d08f5be5983b9b1d7`). The agent made no approval and no Stage A model call. Production and frozen experiments are untouched.

**Exact spending: US$1.520696 calculated** (111 requests; all settled from provider-reported usage, none above its reservation, none unsettled). This is not a bill. The programme known-spend subtotal moves from US$11.898286 to **US$13.418982** (A$20.13 at the ledger's 1.5 rate) of the A$50 limit.

Review packet (wordings, flags, owner commands): [`lifecycle-m7-review-packet.md`](lifecycle-m7-review-packet.md).

## 1. Design and safety, as executed

**Suite.** `larkspur-core` v2 (`172d1e71…`) was prepared from the recorded M6 proposals: 3 tasks kept from the immutable v1 (`873e07c3…`, unchanged) and 3 re-validated offline after the M6 lexicon fix.

**Manifest** `64a55c5f3a936766627a596af233595efd7c35cd448397f32357b604e6981377`:
- variants `original` and `modified` (Larkspur snapshots `2f9fd2ce…` / `edb9a5d2…`);
- natural condition only; 1 repetition; seed 7;
- plan **exploratory**: 6 tasks × 1 repetition has no power, and a confirmatory designation was not requested;
- the pinned agent `muse-spark-1.3`, endpoint `https://api.meta.ai/v1`, reasoning effort low, 4096 completion tokens, profile `suite-v2-compat2` (`d18a2b7e…`). None of these were changed.

**Worst-case reservation, computed before any paid call: US$7.392** (6 tasks × 2 variants × 14 max requests × US$0.044), within US$8.00.

**Guard** (`evalruns/authorization.py`, used by `runner.execute`). The write-once authorisation `a9049bd6…` binds:
- the experiment id `m7-larkspur-browser-1`, whose ledger is fixed at `scanner-data/research/stage-b/ledgers/m7-larkspur-browser-1/`;
- the exact frozen suite, which must carry a real owner approval (synthetic suites and approvals are refused);
- the manifest hash;
- 12 trials maximum, counted from the durable ledger, so restarts are safe and a trial that ever reserved is never re-run;
- the US$8.00 cap, which the manifest's hard cap must equal and the worst case must fit;
- the pinned agent configuration.

At runtime, each request was reserved before it was sent: a per-request cap of US$0.044, a per-trial cap, and a scope cap of US$8.00 across all trials. There were no retries. The run would have halted on a void trial or a bound violation; neither occurred.

**Isolation.** Real Chromium ran in the network jail; the self-test passed. Grading: official grader v1 (unchanged) and post-hoc grader v2 (labelled). One run per wording condition. Snapshot-specific validity was checked: no task was invalidated on either variant.

**Zero-cost checks before the paid call:**
- guard tests (8);
- the lifecycle suites (144 passed) and critical tests (214 passed);
- a pre-freeze rehearsal on a synthetic copy;
- a rehearsal of the **byte-identical manifest** (dev provider, jailed): 12/12, all pass, rescore faithful, leak audit clean.

**Paid run:** 12/12 trials executed, 0 void, no halt. Rescore faithful. **Leak audit clean** (35 public artefacts × 10 answers).

## 2. Results

| | Original (facts only on course pages) | Modified (cards show fee, duration, level, seats) |
|---|---|---|
| Trials | 6 | 6 |
| Official grader v1 passed / evidence-backed | **2 / 2** | **1 / 1** |
| Post-hoc grader v2 passed / evidence-backed | 3 / 3 | **4 / 4** |
| Model requests | 65 | **46** |
| Calculated cost | US$0.906 | **US$0.615** |
| Agent time (sum of trials) | 424 s | 199 s |

Totals: 1,054,811 prompt tokens and 47,571 completion tokens. Prompt tokens are dominated by screenshots, about 9.5k tokens per request. Mean elapsed time is 52 s per trial.

### Per task (original → modified)

| # | Task (capability) | Original | Modified | What happened |
|---|---|---|---|---|
| 1 | Under $250 with ≥ 5 seats (availability, multi-condition) | ✗ v1 ✗ v2: listed 1 of 5 courses; 12 requests, 67 s | v2 ✓ (v1 ✗): all 5 correct; **3 requests, 16 s** | On original the agent opened course pages one by one and stopped with 4 required pages unvisited. On modified it read the fee and seats from the cards and answered from the listing. v1 fails only because each item carried "– $180, 9 seats left" (a v1 exact-name rule). |
| 2 | Life drawing studio fee (lookup) | ✓ v1 ✓ v2; 3 requests | v2 ✓ (v1 ✗); 3 requests | Same path on both variants. The modified answer was a full sentence ("The course fee … is $210."), which exceeds v1's length tolerance. |
| 3 | Weekend Beginner courses (either/or) | ✗ (1 of 4) | ✗ (2 of 4) | Class day is on course pages only, on **both** variants, so up to 14 pages must be opened. The agent visited non-candidates (Watercolour, Python, Italian), used 12–13 of its 14 requests, and stopped with a partial list. |
| 4 | Intermediate courses at Northside (match level) | ✗: **empty answer** after 13 requests, visiting Riverside courses | **✓ v1 ✓ v2** | Modified cards show the level, which narrowed the search to Intermediate courses. On modified the agent also guessed a URL (`/courses/building-web-pages`), hit **"Not found"**, and recovered. |
| 5 | Intermediate at Riverside, most seats (filtered ranking) | ✓ v1 ✓ v2 | ✗ v1, ✗ v2 (`multiple_candidates`, flagged for review) | The modified answer was correct but named the other candidate for contrast ("… vs Furniture restoration with 1 seat"). Both graders conservatively fail an answer that mentions two candidates; a human would accept it. On original the agent answered correctly without opening the other candidate's page (see §4). |
| 6 | ≤ $180 and ≤ 6 weeks (multi-condition) | v2 ✓ (v1 ✗); 12 requests, 78 s, 3 detail pages | v2 ✓ (v1 ✗); **3 requests, 16 s** | Both answers were correct and carried the price and duration with each name (v1 fails on that format). Modified reached it from the cards with a quarter of the requests and cost. |

**Exploratory per-task analysis.** The primary outcome is the official v1 evidence-supported pass, and this analysis was pre-registered as **exploratory**. Paired differences were −1, 0, 0, +1, −1, 0; mean −0.17; exact sign-flip p = 1.0.

Under post-hoc v2 the differences are +1, 0, 0, +1, −1, 0 (mean +0.17).

**Neither supports any claim.** With 6 tasks and 1 repetition, no difference could be significant. The v1/v2 divergence is a grading-format effect (4 of the 12 trials were correct answers with supporting detail), not agent behaviour. No improvement claim is made.

### Concrete, demonstrable observations

1. **Facts on listing cards change the work, not just the outcome.** In the three tasks the cards could answer (1, 2, 6), the modified site needed 3 requests per task, against 12 on original for tasks 1 and 6. Time fell from 67–78 s to 16 s, and cost from about US$0.17 to US$0.04 per trial. In task 1 that also turned an incomplete answer (1 of 5) into a complete one (5 of 5).
2. **When a needed fact is only on item pages, the request limit becomes the failure mode.** Task 3 needs class day, which is on no card on either variant. Both variants ended with partial lists after 12–13 requests. Diagnostics: "budget exhaustion" observed, plus the structural finding "'class day' is only on item pages".
3. **A dead end:** the guessed URL in task 4 (modified) returned "Not found" (diagnostics: "dead end on task 4").
4. **Grading strictness, not agent error, explains most official failures.** Four correct answers with supporting detail failed v1's exact-name and length rules; v2 accepts consistent detail. One correct answer that also named a contrasted alternative failed both graders. v1 stays the grader of record and its grades are reported unchanged.

### Diagnostics (Phase 4; real-model origin)

43 findings:
- **11 structural, observed:** for example, "'class day' / 'campus' / 'materials' only on item pages" on both variants, and "fee / duration / seats only on item pages" on original;
- **26 behavioural, observed:** budget exhaustion, incorrect answer, revisit, unnecessary navigation, dead end;
- **4 hypotheses:** for example, "listing cards omit 'seats left': suspected contributor to item-page navigation on task 1". These stay *hypothesis*: the run is exploratory.

Caveat: diagnostics take "incorrect answer" from v1, so v1 format failures are counted there. They also do not recognise the either/or kind: the finding "no evaluated task compares items by 'class day'" is wrong for task 3.

### Invalidation and execution failures

- No task was invalidated on either snapshot.
- No void trial, transport error, jail failure, bound violation or authorisation mismatch.
- Every trial ended `agent_done`. Several used 11–13 of 14 requests.

## 3. Evidence (git-ignored, preserved locally)

Run `scanner-data/research/stage-b/paid/evalrun-paid-64a55c5f3a-natural/`:
- `artifacts/trials/*.json`: per trial, the outcome, official evaluation, metrics (requests, tokens, cost, elapsed) and the step-by-step journey;
- `trial-data/<trial>/<stamp>/`: `step-NNN.png` screenshots, `model-input-*.png`, `model-response-NN.json`, `trace.jsonl` (each model request and response with usage), `observations.json` (pages seen), `history.json`;
- `artifacts/snapshot-manifests.json`, `artifacts/authorization-check-1.json`, `artifacts/execution-1.json`.

Other files:
- reports `scanner-data/research/stage-b/paid/report-paid-64a55c5f3a.{private,public}.json` and `audit-paid-64a55c5f3a.json`;
- ledger `scanner-data/research/stage-b/ledgers/m7-larkspur-browser-1/ledger.jsonl`;
- authorisation `scanner-data/research/stage-b/authorizations/m7-larkspur-browser-1.json`;
- RunResult records (original, modified) in `scanner-data/research/stage-a/store`.

Rehearsals: `scanner-data/research/stage-b/rehearsals/`.

## 4. Strongest trace for a three-minute demonstration

**Task 1, "I need a course that costs $250 or less and still has at least 5 seats left. What qualifies?"**, original vs modified:
- **Original** (`trial-data/original-gen-23f1802ee0-n-r1/20261102T124441-bd1c6f9e6966/`, 12 screenshots): the agent opens the listing, sees only names and summaries, opens course pages one at a time, runs low on its 14-request budget and answers with 1 of 5 courses. The evidence rule shows exactly which 4 required pages it never saw.
- **Modified** (`…/modified-gen-23f1802ee0-n-r1/20261102T124549-edd6cfdfe62c/`, 3 screenshots): one listing view and one scroll; all 5 courses, each with its fee and seats; 3 requests, 16 s, US$0.039 against US$0.170.
- Storyline: the same frozen, owner-approved customer question; the same agent; one website change (facts on cards); evidence-linked diagnosis (the "'seats left' only on item pages" finding); a 4× fewer-request completion.
- State honestly that v1 marks the modified answer failed, because each name carried its fee and seats. v2 (post-hoc, labelled) accepts it. This is a good moment to show why two graders exist.

Backup: task 6 (both correct; 12 → 3 requests, 78 s → 16 s) is the cleanest efficiency example without grading caveats beyond v1 format.

## 5. Limitations

- **One repetition, 6 tasks:** exploratory only; no statistical or improvement claim.
- **v1 strictness dominates the official numbers.** v2 is the more faithful reading but is post-hoc; any headline must show both, labelled.
- **The `ranked_subset` evidence rule requires only the winner's page,** as `extremum` does. On original, task 5 was answered correctly without opening the other Intermediate-Riverside candidate's page. It was graded evidence-backed, but the comparison was not demonstrably made.
- **Request limit of 14:** filtering tasks that require opening many pages approach it on both variants, so outcomes partly measure the limit.
- **Diagnostics** inherit v1's "incorrect" labels and do not understand `either_of`.
- **The six-task suite misses the provisional suite targets** (8–12 tasks, ≥ 2 per persona, plan_commitment journey). This was disclosed in the review packet and not lowered.

## 6. Recommended next actions (owner decisions; nothing started)

1. Use the task-1 pair (and task 6 as backup) for the hackathon demonstration. Show both graders, labelled.
2. Before any confirmatory claim: more tasks and repetitions under a pre-registered plan. Even 6 tasks × 3 repetitions remains underpowered; see `suites.plan.feasibility`.
3. Grader follow-ups (zero cost; v1 stays official):
   - teach v2 to accept a contrasted mention ("X, vs Y with fewer") only under explicit review rules;
   - make diagnostics read v2 and understand `either_of`.
4. Consider an evidence rule for `ranked_subset` that requires every subset member's page (a new evaluator/grader version; never retroactive).
5. Site hypothesis to test next (exploratory): add class day and campus to the cards (tasks 3 and 4 depend on them).
