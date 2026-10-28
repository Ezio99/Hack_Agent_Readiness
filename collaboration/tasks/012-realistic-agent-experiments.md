# Task 012 — Realistic Agent Experiments and Website-Friction Evidence

**Status:** Planned; experiment design and credential-free preparation authorized. **No live/paid model calls, hosting, deployment, PR merge, or private artifact publication without separate explicit approval.**
**Owner:** Claude implements after Task 011 agent integration is validated; user and ChatGPT review design, results and spending gates.
**Dependency:** Task 010 realistic electronics-v1 storefront and independent evaluators; Task 011 new task/profile/answer-schema integration, bounded Browser Use runner, trace capture, and mock end-to-end validation. A full public scanner deployment is NOT required to begin the experimental pilot.
**Product objective:** Establish whether realistic website design choices cause measurable agent difficulty, whether that difficulty matters for customer-task outcomes or effort, and whether evidence supports specific, testable developer improvements. Do not manufacture failures or conflate agent/tool faults with website faults.

## Research questions and hypotheses
- RQ1 / capability baseline: Can a fixed, versioned reference agent complete T1–T4 on electronics-v1? Which errors and partial successes occur?
- RQ2 / availability: Holding the agent, catalogue, task and specification presentation constant, does listing-visible vs detail-only stock affect T1 discovery completeness, actions, latency or calculated cost? Explore T3 effects separately.
- RQ3 / specifications: Holding all else constant, does structured vs fragmented/prose product specification presentation affect T2 field extraction and comparison, and T3 constraint selection?
- RQ4 / policies: Can the agent accurately combine product, returns and delivery information (T4)? **Existing variants do not change policy placement; T4 is a capability/control task, not a policy-design A/B test.**
- RQ5 / attribution: Which observed problems are plausibly website-induced, agent reasoning errors, tool-interface errors, infrastructure errors or undetermined? What concrete remediation could be retested?

## Pre-registration and experimental integrity
1. Freeze exact environment/data version, 10 fixture IDs, task text, oracle/evaluator versions, model ID, prompts, Browser Use profile, observation mode, tools, timeouts, token/request limits, run order, and analysis code before paid runs. Preserve immutable manifest/hash and full attempt ledger (including aborted/failed runs).
2. Use controlled paired comparisons with one website factor changed at a time, randomized or counterbalanced execution order, repeated trials, and clearly recorded seed/temperature where supported. Never imply deterministic model behavior.
3. Run an **8-run feasibility pilot** spread across T1–T4 and relevant variants only after a separately approved exact call plan. Gate a **focused 24–32-run study** on pilot findings and separate approval; do not automatically proceed. A 10-fixture × 4-variant single pass is 40 runs, not a powered or replicated causal study.
4. Predefine exclusions and stopping rules. Record failures, schema invalidity, timeouts and provider/tool errors; do not silently retry, discard or cherry-pick. Treat low-n results as exploratory, report denominators and uncertainty, and avoid generalization to other websites or models.
5. Verify test feasibility in mocks and use the Task 010 scripted checks only as feasibility evidence, never as live-model results.

## P0 per-run metrics and data contract
Record run_id, mode (mock/scripted/live), experiment_id, timestamp, code commit, environment/data/variant IDs, task/template/fixture/contract/evaluator versions, agent/model/tool/profile and prompt/config hashes, limits, run order, and result artifact provenance.

**Outcome:** independently graded task PASS/FAIL; schema validity; task-specific field correctness and partial accuracy; T1 precision/recall and ineligible items; T2 RAM/battery extraction, tie/comparison correctness and product identity; T3 all-constraint satisfaction, cheapest-eligible correctness, price accuracy and missed alternatives; T4 return-window, fee, delivery-price and time-field accuracy. Distinguish answer correctness from evidence-backed correctness.

**Effort:** model requests, browser/tool actions by type, unique product/detail/policy pages visited, revisits, backtracks, repeated/failed tool calls, limit exhaustion, wall-clock elapsed time and completion status. Record input/output tokens and **calculated** inference cost with price assumptions/version separately from **actual billed** spend (if known).

**Evidence and diagnosis:** private per-step observations, action/result timestamps and visited paths, relevant evidence excerpts or safely referenced trace spans; evidence coverage and gaps. A visited URL alone is not proof the agent read the necessary information. Classify each failure/friction as website, agent reasoning, agent–tool interface, infrastructure, mixed or undetermined; attach supporting trace spans, confidence and explicit alternative explanations. Do not attribute a tool loop to the website.

**Controlled contrasts:** success-rate differences (percentage points), partial-accuracy differences, request/action overhead (absolute and relative), latency difference (median and distribution), calculated cost difference, and variation across repetitions. Show per-run points and sample sizes; do not hide outliers.

**Developer-value metric:** count of distinct *evidence-supported, actionable and testable* issues, with issue definition, observed behavior, impact metric, candidate fix and validation experiment. Avoid optimizing issue count through speculative recommendations.

## Deliverables
- Credential-free experiment manifest generator/validator, run schedule, result schema, data export and analysis/reporting pipeline compatible with Task 011; no model network access in default tests.
- A small pre-registered pilot plan: exact fixtures, variants, ordering, maximum model requests/tokens/steps/time, expected and maximum estimated USD cost, spend ledger, abort conditions and approval checkpoint. **Ask user before executing any live call.**
- After approval and execution: complete attempt ledger, independently verified outcomes, per-task metrics, controlled contrasts with uncertainty, trace-backed issue candidates, negative/null results, alternative explanations and explicit limitations.
- A developer-facing experimental evidence view or export using existing dashboard/scanner components; label scripted/mock/recorded/live modes conspicuously. Do not publish private traces or results without approval.
- Report 012 with reproducibility manifest, methodology, failures, observed findings, calculated vs billed costs, and recommended candidate remediations for a later controlled before/after task.

## Acceptance criteria
- Every live result can be traced to a versioned task, environment, agent configuration and independent verdict; no evaluator truth leaks to the agent.
- Both successes and failures, malformed outputs and infrastructure/tool errors remain inspectable and correctly attributed or marked uncertain.
- Comparisons hold non-target variables fixed and show sample size, variability and limits; T4 is not misrepresented as an A/B test.
- Findings support a developer's concrete next action or explicitly say evidence is insufficient.
- All paid experiments and public/private publication remain behind explicit user approval gates.

**Sequence:** Task 011 integration/mock gate → Task 012 credential-free preparation → separately approved 8-run live pilot → review → separately approved focused study → evidence-informed diagnostics/remediation. Task 013/014 (diagnostic recommendations and before/after validation) remain proposed, not authorized.
