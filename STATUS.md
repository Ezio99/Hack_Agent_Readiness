# Agent Readiness: status

Authoritative current handoff. Check it against the repository and production before you rely on it. The full dated history up to 2026-11-02 is preserved verbatim in [docs/archive/STATUS-2026-10-29-to-2026-11-02.md](docs/archive/STATUS-2026-10-29-to-2026-11-02.md); earlier history is in [docs/archive/STATUS-through-2026-10-29.md](docs/archive/STATUS-through-2026-10-29.md).

## Current state (2026-11-02)

**Production:** https://209-38-84-72.sslip.io (DigitalOcean, Sydney). It serves `evaluation-v2` @ `140a4e8`, deployed 2026-11-02 07:12 UTC with owner approval: the redesigned frontend, plus the grader_v2 post-hoc view (grader_v1 stays official), the enforced-ceiling export fix, and the operator-token UX. Executor, admission, jail and budgets are unchanged.

- Mode live, access **operator-only**: public starts get 403.
- Hosted ceiling US$10. US$3.30 is reserved by two completed jobs, and **4 repetitions remain**.
- Rollback image `agent-readiness-app:rollback-b3121a8` is kept (plus `rollback-60fcbc6`). Commands and the full verification record are in [deploy/DEPLOY.md](deploy/DEPLOY.md).

**Verified independently on 2026-11-02 (fresh session, public endpoints only):**
- `index.html`, the entry JS/CSS and the lazy Demo/Classic chunks served by production are byte-identical (SHA-256) to a local build of the dashboard source at `b3121a8`. The dashboard source is unchanged from `b3121a8` to HEAD.
- `/api/health` returns `mode live, evaluations enabled, access operator, active false`.
- `/api/ironbark/config` returns `worker idle, model muse-spark-1.3, profile suite-v2-compat2, remaining_repetitions 5`.
- Security headers present: CSP `default-src 'self'`, HSTS, nosniff, `no-referrer`.
- In-container checks were repeated over SSH before the paid trial: jail self-test ok, image `redesign-b3121a8`, `.env` as documented, provider `/v1/models` 200. See the [trial report](collaboration/reports/hosted-production-trial-2026-11-02.md).

**Branches.** Production runs `product-experience-redesign`. It sits on top of `hosted-ironbark-evaluation`, then `ironbark-evaluation-runner`, then `live-m1-llm-evaluation` (draft PR #60), then `main`. It is **63 commits ahead of `main` and unmerged**, so `main` does not reproduce production. Merging (or a PR from `product-experience-redesign`) needs owner approval. `demo-cinematic-storyboard` holds 4 commits that are not in production: it is the earlier storyboard and is kept as history.

**Paid production trial completed (owner-approved, exactly one repetition):** `eval-aa23e330`, 8/8 in 9 min 01 s, real model. Original 0/4 (52 requests) → Modified 3/4 (26 requests). Frozen rule inconclusive; exploratory rule consistent_with_h1. **New calculated spend US$1.126097**, fully reconciled (0 open reservations, none settled above its reservation). Every production surface worked, including refresh recovery. Findings: an answer-length grading false negative on task 1; a tight Original-arm cap margin; a stale ceiling in the export; operator-token UX. Full details: [report](collaboration/reports/hosted-production-trial-2026-11-02.md). **No further paid call is authorized.**

**Branch `evaluation-v2` (deployed; see Production):**
- grader_v2 with adversarial tests, and a labelled post-hoc rescore with exact v1 reproduction checks ([design and historical results](collaboration/reports/grader-v2.md)). All 12 recorded runs rescore faithfully; 13 trials newly pass, none newly fail, and no verdict category changes.
- Hosted v2 view beside the official v1 grades.
- Export now reports the enforced ceiling.
- Operator-token field is visible and held in memory only.

grader_v1 remains the grader of record.

**Phase 3 framework (isolated; not on the hosted path):** [docs/FRAMEWORK.md](docs/FRAMEWORK.md).
- Site definitions, with independent record oracles for controlled sites.
- Verifiability classes; only deterministic, oracle-validated tasks are scoring-eligible.
- Validated autonomous task generation: Ironbark gets 5 deterministic tasks (its variants are exactly the hosted Original/Modified) and the second controlled site, Larkspur Community College, gets 7. The uncontrolled zoo site correctly gets 0.
- Eligible tasks freeze into the existing manifest format and grade through grader_v1/v2.

**Zero-cost evaluation loop (milestone met, 2026-11-02):** `framework/evaluate.py` runs prepare → execute → results through the same interface for every site. The path is site definition → independent oracle → task generation → validation → manifest freezing → agent execution (real Chromium, loopback dev provider) → evidence capture → grading (official v1 + post-hoc v2) → persisted results, with full provenance.

| Site | Trials | Correct answers | Evidence-supported |
|---|---|---|---|
| Larkspur | 14 | 14/14 | 14/14 |
| Ironbark | 10 | 10/10 | 6/10 (the scripted stand-in doesn't scroll the long listing, and the evidence rule correctly refuses to credit unseen answers) |

Fixed the shared dev provider's per-trial script reuse. Limitations and what blocks a real Larkspur run: [docs/FRAMEWORK.md](docs/FRAMEWORK.md).

**Model provenance:** derived from the frozen records into exports and the workspace methodology (on `evaluation-v2`, not deployed): muse-spark-1.3, reasoning_effort low (frozen by owner decision), 4096, profile and hash, official v1 / post-hoc v2.

**Phase 4 diagnostics (isolated, milestone met):** [docs/DIAGNOSTICS.md](docs/DIAGNOSTICS.md). Structural, behavioural and evidence-linked layers share one finding schema (stable id, context, severity, evidence, recommendation, status).
- Detects exactly the intentional Original→Modified change on both controlled sites.
- On the real paid trial: 11 structural and 16 behavioural observations (including a real 404 dead end); 3 hypotheses are `supported_exploratory` (the frozen rule was inconclusive; the three facts were changed together); 3 risks are `unverified`.
- On fixture runs, hypotheses stay `hypothesis` by rule.

Future product architecture (not implemented): [docs/FUTURE_ARCHITECTURE.md](docs/FUTURE_ARCHITECTURE.md).

**Next:** feature freeze. Demo and submission preparation for Wednesday 2026-11-04 (submission deadline 2026-11-05 13:00 Sydney).

**Research branch `research/llm-task-planning` (isolated, not deployed, not merged; pushed to origin with owner authorisation 2026-11-02):**
- LLM task planner: two paid planner runs.
- taskeval-1 and selection-1.
- Isolated Larkspur pilot: 8 paid jailed trials.
- **Two-stage evaluation lifecycle:** proposal approved with eight decisions. **M1–M5 implemented** (M2 `c721c47`, M2b `5bc7892`, M3 `11e1a59`, M4 `258ec96`, M5 in the report's final commit):
  - evaluator v2 with gate-nl-1 and the four wording categories (12–13 / 20 recorded Muse Spark proposals now execute in the customer's own words, against 6 / 20 under the v1 gate);
  - ranked_subset and either_of kinds;
  - the bounded Stage A loop;
  - human approval and freezing, the statistical plan and manifests;
  - the general Stage B runner.
  - **Zero-cost rehearsals** on Larkspur and Ironbark (real Chromium in the jail, loopback dev provider; NOT a model).
  - **No paid call.** Every approval made was of a SYNTHETIC fixture suite.
  - Report: [collaboration/reports/lifecycle-m2-m5.md](collaboration/reports/lifecycle-m2-m5.md).

**M6 Stage A (owner-authorised, cap US$0.10): done.**
- One paid generation: 2 requests, **US$0.049804 calculated**; schema v3 accepted; stopped at `targets_met` after 2 rounds.
- 18/24 proposals natural_verifiable as run; 20/24 after a zero-cost lexicon fix ("at least N" was misread as a superlative) re-evaluated offline.
- Suite proposal `larkspur-core` is UNAPPROVED, awaiting the owner's review.
- Report: [collaboration/reports/lifecycle-m6-stage-a.md](collaboration/reports/lifecycle-m6-stage-a.md).
- Stage B and further paid calls are not authorised.

Handoff: [collaboration/LIFECYCLE_HANDOFF.md](collaboration/LIFECYCLE_HANDOFF.md).

## Budget

- Hosted admission: US$10 ceiling, US$3.30 reserved, US$1.65 per repetition. Reservations are never released, even for completed jobs, so the remaining capacity is 4 repetitions.
- Programme: ceiling A$50. This is a limit, never an authorization. The recorded known-spend subtotal is partial (see `collaboration/budget/programme-ledger.json` and the archive). The 2026-11-02 production trial (US$1.126097) is appended as `hosted-live-2`, making the subtotal US$10.566163. Research planner requests add US$0.024452 calculated from usage (`research-taskplan-2`) plus US$0.029054, an UNCONFIRMED conservative upper bound for a rejected request (`research-taskplan-1`). The isolated Larkspur research pilot (`research-pilot-larkspur-1`) adds US$1.228813, calculated from usage. M6 Stage A (`research-stage-a-m6-1`) adds US$0.049804 calculated. The current subtotal is **US$11.898286 / A$17.8474**. Calculated cost is not a bill.

## Deadlines

Feature freeze and demo preparation: **Wednesday 2026-11-04 (Sydney)**. The official submission deadline is 2026-11-05 13:00 Sydney (Nov 4 21:00 ET).

## Known debt and follow-ups

- Production code lives on an unmerged branch stack (see Branches above).
- Original-arm cap margin (about one request of headroom): left unchanged by owner decision. See the [trial report](collaboration/reports/hosted-production-trial-2026-11-02.md).
- After a reviewed deploy, production's cached `<run>.public.json` exports keep the old ceiling display until regenerated.
- Demo-day documents predate the redesign and still describe the Replay Studio as the default page: [docs/THREE_MINUTE_DEMO_SCRIPT.md](docs/THREE_MINUTE_DEMO_SCRIPT.md) and [docs/RELEASE_CHECKLIST.md](docs/RELEASE_CHECKLIST.md). Refresh them on demo-preparation day.
- Archive UIs remain reachable on purpose as rollback and reference paths: the Replay Studio (`#/studio`) and the classic pages (`#/investigation` and others). The Geist font and its licence exist in both `site/fonts` and `studio/assets`. Vite emits a single asset for them, so the duplication only costs repository bytes.
- Untracked owner work in the checkout is left untouched: `src/agent_readiness/investigate/prototype/termvalue.py` and `tests/test_termvalue_prototype.py`. They are a later variant of the tracked `taskgen/termvalue.py`.
- Architecture debt that was retained by decision (three experiment drivers, frozen shop-coupled files, legacy runner) is described in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Key documents

[deploy/DEPLOY.md](deploy/DEPLOY.md) (deployment, rollback, operations) · [dashboard/PRODUCT_REDESIGN.md](dashboard/PRODUCT_REDESIGN.md) (frontend design and evidence provenance) · [collaboration/reports/hosted-ironbark-wip.md](collaboration/reports/hosted-ironbark-wip.md) (hosted backend) · [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) · [COLD_START.md](COLD_START.md).

## Standing constraints

- No paid inference, ceiling change, public paid access or publication of private traces without explicit owner approval.
- Never print or commit `META_MODEL_API_KEY`, `.env` or `deploy/secrets/`.
- Keep scripted, mock, recorded and live evidence distinct.
- Historical Task 005–007 code, config and data, pilot evidence, frozen manifests and the budget ledger are never rewritten. Stored evaluation evidence is never deleted.
- `uv.lock` is deliberately untracked. Never use a bare `git add -A`.
