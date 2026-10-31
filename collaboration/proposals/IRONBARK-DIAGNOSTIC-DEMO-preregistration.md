# Pre-registration: Ironbark diagnostic demonstration (written before any real-model run of this scenario)

Status: **proposal; nothing in this note has been run against a real model.** Written 2026-11-02. It is an operator document: it is not an input of the investigator, the task generator or any prompt (a test checks that the investigator's first message and tools do not contain its expected-claim wording).

## Purpose
Show that the existing pipeline can turn real browsing-agent behaviour on the Ironbark demo site into an evidence-backed, honestly labelled finding and an actionable (still UNVALIDATED) recommendation. The first real run (job `live-bb5d48501b`) correctly reported no friction because its two tasks were answered from information already on the listing cards. This scenario targets the information the site shows only on each machine's own page.

## Scenario
- Site: Ironbark control snapshot (captured copy; the agent browses a read-only local mirror).
- Goal (exact text): "Can an AI agent compare the refundable deposit, minimum hire period, and delivery requirements across the hire machines?"
- Preferred: model-generated tasks under that goal (autonomous path). Fallback and offline validation: the four owner-authored tasks in `collaboration/proposals/ironbark-owner-tasks.json` (file SHA-256 `9d37ec0431d6c47f32ce208920684be138ceee5ffa92cf390edecfac171feb5b`; grant-bound normalised hash `cd2bfa5ee3eff6ce83dc777faf535882f923cb9923cc279821b9a9f6224bb5fd`). They are labelled OWNER-AUTHORED in the run and the report, pass the same independent gate, and their expected answers are computed by code.
- Caps: the existing grant (US$2.00; stage caps 0.15 / 1.40 / 0.40; per-request 0.05). Owner-tasks-only generation makes no model request.

## Expected claim class (recorded here, not shown to the investigator)
A website-side information-placement pattern: fields that decide these tasks are on every machine's own page but not on the listing cards (`info_absent_on_template`, any of the labels refundable deposit / minimum hire / delivery and collection, which the captured profile shows on 16 of 16 pages and 0 of 16 listing items). Other website-side claim kinds are not expected; an agent-side explanation or "no friction" are acceptable outcomes.

## What the investigator receives
Task ids and questions, the recorded trials and the site's captured pages through its read-only tools. It receives no criteria, no expected answers, no claim label, no profile statistics and nothing from this note. The goal text names the fields the shopper cares about; it does not say where they are or what is wrong.

## Success criteria (decided before the run)
1. At least 2 selected tasks need fields that are only on detail pages.
2. At least 2 distinct tasks show a measurable cost: at least 2 extra page views on a clean success, or a failure attributed to website / tool interface / undetermined (never the agent).
3. The investigator submits a verifiable claim with a parameter stated in its own text; the deterministic verifier returns `supported`; it is promoted to a finding by the existing rule (at least 2 independent task supports or a structural proof). The rule and the verifiers are not changed for this run.
4. A recommendation exists whose patch passed the static re-check, labelled UNVALIDATED, with its evidence trials and request counts shown.
5. The report shows VERIFIED / OBSERVED / INCONCLUSIVE separately, the partial-or-complete goal coverage and the owner-authored label where it applies.
6. Spend within the grant; replay makes zero requests.

## Outcomes that count as honest results, not failures of the product
- "No friction": the agent solves all tasks efficiently. Reported as such.
- Supported but not promoted (1 task impacted): reported as OBSERVED.
- Agent-attributed failures: reported as such, never as website findings.

## Not claimed
No effect of the recommended change (no retest in the live UI), no claim about real sites, no statistics (n = 1 per task, one model, one site).

## Rehearsal (offline)
A mock-mode rehearsal with a deliberately inefficient scripted agent exercises the chain task -> trial -> investigator -> verifier -> promotion -> recommendation -> report. It validates the pipeline and wording only; it says nothing about a real model's investigative ability.
