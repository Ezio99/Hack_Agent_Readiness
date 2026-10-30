# EXP-B — owner-selected exploratory modification: show the daily fee in the `/tools` listing (PROPOSAL / PRE-REGISTRATION DRAFT; nothing applied or run)

Prepared 2026-10-30 from the completed L1a site-5 run (`site-5-live`, recovery fork `site-5-live-b`). Offline only: no patch applied, no paid trial, no holdout trace opened, no frozen task changed, programme ledger untouched. Status: **draft for owner review; not pre-registered until the owner approves this document.**

## 0. What is evidence and what is a choice (kept separate)
**Investigator-supported observations (deterministic, from `site-5-live-b`):** on `/tools` the fields `condition`, `copies available`, `daily fee`, `deposit`, `next available` are shown on 8 linked detail pages and in **0** listing items (`info_absent_on_template`, verifier-supported). The hypothesis that this forces extra page views was **not promoted** (1 supporting trial; that trial passed, using 13 page views against a minimum of about 3). No finding, no proposal, no behavioural effect is established.
**Owner-selected intervention (this document):** an exploratory change chosen by the owner, labelled **EXPERIMENTAL — owner-selected, not a verified finding**. Any result is about this change on this site, these six tasks, this agent and model.

## 1. The smallest reversible patch (computed offline; not applied)
One existing DSL operation (the same one the verified-finding template would use): `copy_field_to_listing` on `/tools`, selector `li.card`, source label `daily fee`.
- Elements changed: 8 (one per tool); inserted text: `Daily fee: $N` copied from each tool's own page (the DSL's provenance rule); inserted bytes: 105; pages changed: `/tools` only; every detail page is byte-identical; links, names and structure are untouched.
- Patch sha256 `b2efe2f747c0a8713b5f0fac0b9874cf0528a7ccf475c89b25677243c10aaf1e`; parent snapshot `1796c2a3c8b5f957918f99f0262d84feccdb6391e13fb2f88dee189897b6d96b`; result snapshot `27b2754e0f85c35b47fafc2e761978ad23e1d35ff0eac9f0c553f57997808dbd`.
- Static re-check passes (the field is now on every listing item). Reversible by construction: the patch only produces a *new* mirror snapshot; the original snapshot and the real site are never touched; discarding the patched snapshot reverts.

## 2. Which frozen tasks can measure a browsing-effort change
Re-validated offline on the patched mirror with the unchanged acceptance gate (`still_valid`); all six remain valid, expected answers unchanged. No criterion or answer is reproduced here.
| task | kind / partition | role | decisive evidence pages (before → after) | baseline requests / pass |
|---|---|---|---|---|
| `gen-e38eac8644` | extremum / investigation | **affected** (daily fee) | 2 → 1 (min hops 2 → 1) | 13 / pass |
| `gen-c7c642f78c` | item_set / **holdout** | **affected** (daily fee) | 6 → 1 (min hops 2 → 1) | 13 / fail (tool_interface) |
| `gen-0384beb35e` | extremum / **holdout** | negative control, same shape, field not exposed by the patch | 2 → 2 | 13 / fail (agent) |
| `gen-0ac84d18d3`, `gen-b05c45672f`, `gen-f2731972ed` | page_fact / investigation | negative controls (detail-page facts) | 1 → 1 | 2, 3, 3 / pass |
**Instrument check (free, no model):** a scripted mock agent on the patched mirror, graded with the re-derived requirements, passes *and is evidence-backed* on both affected tasks with 3 requests / 3 page views and on the control with 4 - i.e. answering from the listing is not penalised as "not evidence-backed", so the grading cannot manufacture a failure.

## 3. Can the current tasks and metrics support the experiment? Gaps, stated plainly
1. **The frozen rule cannot return `improvement` here.** The pre-registered rule (`paired-signflip-v1`, alpha 0.10, pass-delta floor 0.25, request floor 25 %) pairs *tasks* (6 pairs, K = 1). Best case computed with the real code - both affected tasks pass in 3 requests, everything else identical - gives pass delta +0.167 (< 0.25), request change -42.6 %, p_requests = 0.50: verdict **`inconclusive`**. An exact sign-flip needs at least 5 tasks moving in the same direction (min p 0.0625) and only 2 tasks can be affected. The rule stays in force and will be reported unchanged; it is not a fair test of this hypothesis.
2. **No variance estimate:** baseline K = 1 per task. A 13-request trial may vary between runs without any change; one control task is the only (weak) noise indicator. A comparison against a different day's single trial is also exposed to model/API drift.
3. **Placebo / unmodified repeat is not implemented** in the live flow (plan item M8).
4. **Missing mechanism for an owner-selected change:** `apply_fix` accepts only auto-applicable *verified-finding* proposals, and none exists. Needed offline code: record an owner-authored (novel, unverified) hypothesis plus an owner-selected proposal carrying the patch ops, labelled EXPERIMENTAL, still behind the approval gate; plus a way to run the post-investigation stages for a completed fork (stage statuses currently `done`).
5. **No stage cap exists for `post_trials`** and the allocation (US$1.95 of 2.05) does not include it; a cap must be added and listed in its manifest.
6. **Holdout is no longer blind for the owner:** the baseline holdout failures were seen before this choice. The patch was derived from the investigator's blind observation, but the holdout result can only be reported as a *non-blind* consistency check.
7. **Metrics measure effort and correctness only;** not answer quality, not navigation (no `reach_page` task), and the `condition` / `copies available` / `next available` fields stay untested.

## 4. Pre-registration (to be fixed by the owner's approval before any trial)
**H1 (exploratory, directional):** showing the daily fee in each `/tools` listing item reduces browsing effort on tasks whose decisive information is the daily fee, without reducing evidence-backed correctness.
**Prediction:** on `gen-e38eac8644` and `gen-c7c642f78c` model requests fall by at least 25 % (13 -> at most 9) and page views fall; no task loses an evidence-backed pass.
**Primary metric:** model requests per trial on the two affected tasks (paired, per task, patched minus baseline). **Secondary:** page views; evidence-backed pass; calculated cost per trial; void trials; the frozen-rule verdict (reported unchanged, expected `inconclusive`).
**Design A (existing machinery after the small code change in section 6):** patched arm only, the six frozen tasks, K = 1, same model, profile, limits and arm configuration as the baseline; comparison against the imported baseline trials (paired by task).
**Design A+ (recommended addition, needs placebo code):** also re-run the three same-shape tasks (`gen-e38eac8644`, `gen-c7c642f78c`, `gen-0384beb35e`) once on the **unmodified** mirror in the same session, giving a run-to-run noise estimate and removing most of the drift confound.
**Decision rules (fixed in advance):**
- *Consistent with H1:* both affected tasks meet the prediction, no evidence-backed pass is lost, and the negative controls stay within tolerance (page_fact tasks: |change in requests| <= 1; deposit-extremum: <= 3 requests; with A+, the affected-task reductions must also exceed the largest unmodified-repeat difference observed).
- *Not supported:* an affected task shows less than 25 % fewer requests, or a pass is lost.
- *Uninterpretable:* a control moves beyond tolerance, any trial is void, a gate refuses, or the run stops early.
**Allowed claims:** "consistent with / not consistent with a reduction in browsing effort for this exploratory change on this site and these tasks". **Not allowed:** "proved", "improved readiness", any claim about other sites, correctness gains, or about the holdout failures' causes.
**Validity checks (each recorded):** patched snapshot hash equals the approved one; detail pages byte-identical; only `/tools` changed; `still_valid` lists all six tasks; the re-derived evidence requirements are used for the patched arm; fidelity guard unchanged; no void trial; model, profile, limits and K identical to the baseline; spend reconciles with the ledger.
**Stopping conditions:** stop (no automatic retry) on any void or infrastructure error, spend-gate refusal or bound violation, a stage-cap hit, an accounting mismatch, an ambiguous request, or a protocol violation. No interim analysis: all trials of the approved manifest run in a fixed order, and the analysis is the one stated here.
**Limitations:** n = 1 per task per arm (2 per task with A+); one site and one model; effort, not correctness; baseline and patched trials are not simultaneous (A+ mitigates); a listing change alters what the affected tasks measure (that is the intended effect); holdout not blind to the owner; exploratory by design.

## 5. Budget (calculated estimates, not bills)
Committed so far: US$0.670252 of the US$2.05 ceiling (US$1.379748 remaining). Per-trial history: page_fact 0.023-0.036, extremum / item_set 0.165-0.173 (13 requests each).
| arm | trials | expected | planning cap |
|---|---|---|---|
| patched (Design A) | 6 | US$0.33 (fee tasks drop to about 3-4 requests) to US$0.60 (no change) | **US$0.80** (new `post_trials` stage cap, per-trial 0.50, per-request 0.05) |
| unmodified repeats (A+) | 3 | about US$0.51 | **US$0.60** |
| **Design A+ total** | 9 | **US$0.84 - 1.11** | **US$1.40** |
After A+ at the cap: committed would be at most US$2.07 against the US$2.05 ceiling, so the A+ cap must be US$1.35 or the ceiling raised (owner decision); the expected total is about US$1.5-1.8, about A$2.3-2.7 on top of what is already spent. Replicated designs (K = 3 per arm) were estimated at about US$1.7-2.6 and do not fit the current ceiling.

## 6. Offline code needed before any paid step (separate draft PR, tests, no model call)
(1) owner-selected exploratory proposal path (labelled, approval-gated) and an offline `propose-owner` command; (2) run the post-investigation stages (`apply_fix`, `post_trials`, `evaluate`, `final_report`) for a completed fork; (3) a `post_trials` stage cap enforced by the existing scope mechanism and listed in the manifest; (4) optional placebo (unmodified) arm for A+; (5) tests for each, including that the proposal cannot be applied without its exact-manifest approval. Approvals then required, each for an exact hash: the apply-fix manifest and the post-trials manifest (and the placebo arm inside it).

## 7. Decisions requested
(a) Design A or A+; (b) cap numbers (A+ needs US$1.35 total or a higher ceiling); (c) accept that the frozen rule will almost surely report `inconclusive` and that the decision rules above govern interpretation; (d) approve the code PR in section 6; (e) accept the non-blind holdout limitation.
