# HANDOFF — Agent Readiness (written for a fresh Claude Code session)

State recorded **2026-10-30 (Sydney)**, right after PR #50 was merged. **Verify everything in section 5 against the real checkout before acting; this file is a snapshot, not a source of truth** (`STATUS.md` and `git log` are). Nothing in this document authorizes spending, approving a gate, merging or modifying evidence: all of that needs the owner's explicit, per-action authorization (section 6).

## 1. Project and product
**Agent Readiness** is a diagnostic platform for *how well AI agents can use a website*. Target users: site owners / developers who want to know whether agents (shopping, booking, research agents) can complete tasks on their site, what blocks them, and what to change. Long-term vision (see `docs/PROJECT.md`, `docs/PRODUCT_ROADMAP.md`): a registry / agent-facing API of website readiness. **That registry is a vision, not built.** The shopping agent is the *measurement instrument*, not the product.

**Core loop:** website → independent evaluation of agent outcomes → friction diagnosis → evidence-linked recommendation → controlled modification (on a local mirror, never a real site) → measured retest. Principles: evidence before scoring; a frozen reference agent; outcomes graded independently of the agent's self-assessment; separate website vs agent vs tool-interface vs infrastructure causes; negative/inconclusive results are preserved; recommendations are *unvalidated* until a retest measures an effect; no universal readiness score.

**Hackathon:** Meta Global Hackathon (Meta technology must have a meaningful role: the agent and the investigator use Meta Muse Spark `muse-spark-1.3` through the OpenAI-compatible API at `https://api.meta.ai/v1`). Implementation started 2026-10-27 (Sydney). **Internal deadline: 2026-11-04 23:59 Australia/Sydney (AEDT).** Official submission deadline is 2026-11-05 Sydney time and is held as buffer; *verify it against the official rules*. The pre-event prototype repo `Ezio99/Agent_Readiness` must never be copied as new work (`AGENTS.md`).

**Intended demo narrative:** (1) a website (here the controlled site-5 "Lakeview Tool Library"), (2) agents are run on independently graded tasks, (3) the investigator diagnoses where agents struggle (and says so honestly when it cannot), (4) a recommendation, (5) a controlled modification of a local mirror, (6) a measured retest with the frozen statistics reported unchanged next to a clearly labelled exploratory analysis.

**Experimental benchmark vs product vision:** today there is a working end-to-end *experimental pipeline* (CLI + durable run directories + evidence store + spend gates) and a read-only dashboard page that renders an exported report. There is **no polished, demo-ready dashboard journey yet** (section 8) and there is no registry.

## 2. Repository map
`/home/vaibhav/Projects/Hack_Agent_Readiness` (GitHub `Ezio99/Hack_Agent_Readiness`, branch `main`). Python 3.12 + uv; dashboard in React/TypeScript/Vite.
| area | where |
|---|---|
| CLI (`readiness …`) | `src/agent_readiness/cli.py` + one module per group (`investigate/cli.py`, `scanner/`, `suite/`, `remediation/`, `experiments/`) |
| Reference browser agent (Browser Use), profiles, pre-send fidelity guard | `agent.py`, `capture.py`, `compat.py` (prose-prefix recovery), `profiles/*.json` (`suite-v2-compat1` is the agent profile for the investigation work) |
| **Task 016 investigation pipeline** | `src/agent_readiness/investigate/` — `inspect/` (crawl/profile), `sitemodel/` (content-hashed snapshot, read-only mirror, patch DSL), `taskgen/` (candidates, model proposals in 3 batches, gate, freeze), `trials/` (runner, `run_plan`/`run_arm`, attribution, trace), `investigator/` (tool loop, verifiers, tools, report), `recommend/` (patch templates, `apply_fix`), `evaluate/` (`design.py` = frozen paired-signflip rule; `exploratory.py` = EXP-B rules, plan and order; `stage.py`), `llm/` (Meta client, scripted/recorded clients, classified provider errors), `zoo/` (planted-issue development sites, sealed diagnoses), `flow.py` (stage list + builder), `fork.py`, `owner.py`, `export.py`, `allocation.py` |
| Spend safety | `ledger.py` (durable reserve-before-send ledger), `spend_gate.py` (per-request / per-run / named scope caps, restart-safe), `budget.py` (A$ programme ledger file: `collaboration/budget/programme-ledger.json`) |
| Dashboard | `dashboard/` (pages: Overview, Scopes, Evidence, Replay (Task 007 recorded data), Scanner, Audit, **Investigation** (reads a sanitized export or a labelled synthetic fixture)); `scripts/` there include the `dist` safety check |
| Protected scanner service, electronics environment, WebArena spike, remediation product | `scanner/`, `environments/electronics/`, `webarena/`, `remediation/` (earlier tasks; see `docs/ARCHITECTURE.md`) |
| Docs | `README.md`, `STATUS.md` (authoritative current state; **partly stale — it still mentions M3 in places**), `COLD_START.md`, `AGENTS.md`, `docs/ARCHITECTURE.md`, `docs/TASK016_IMPLEMENTATION_PLAN.md`, `docs/META-INTEGRATION.md`, `docs/CI.md`, `collaboration/reports/*` (016a–016l are the Task 016 reports; **016k = investigator incident and recovery fork; 016l = EXP-B implementation**), `collaboration/proposals/EXP-B-listing-fee-preregistration.md` (**the amended pre-registration**), `collaboration/TASK016_HANDOFF.md` (older handoff) |
Run data lives in **`investigations/`** (git-ignored, local to this machine, contains private criteria/transcripts: never commit, never print keys). Also git-ignored: `runs/`, `.env`, `uv.lock` (**never `git add -A`; add explicit paths**).

**Pipeline stages** (`flow.STAGES`): inspect → taskgen → freeze → baseline_trials → trace → investigate → recommend → report → apply_fix → post_trials → evaluate → final_report. Spending stages (`taskgen`, `baseline_trials`, `investigate`, `post_trials`) stop at `awaiting_approval` in live mode until the owner approves the **exact sha256 of the stage manifest** (`readiness investigate approve RUN --stage S --sha256 H --note "..."`), then must be re-run with `--allow-model-calls`. `apply_fix` is gated in every mode. A failed/void/quarantined trial halts the stage and is never silently retried.

## 3. Commands
```bash
# install (README)
uv venv --python 3.12 && uv pip sync requirements.lock && uv pip install --no-deps --no-build-isolation -e . && .venv/bin/python -m playwright install --with-deps chromium
# tests (offline, no key): fast loop ~35 s
scripts/dev-tests.sh
.venv/bin/python -m pytest -m "not browser" -q -p no:cacheprovider    # ~4 min, 929 tests at the time of writing
.venv/bin/python -m pytest -m browser -q                                # browser shards (CI runs them)
cd dashboard && npx tsc --noEmit && npx vitest run && npm run build     # dashboard (66 tests at the time of writing)
# CI: .github/workflows/test.yml (logic 1/2, 2/2; browser 1-4/4; "gate (required check)"), dashboard.yml (path-filtered), full.yml, pages.yml (deployment: do NOT trigger without approval)
gh pr checks N ; gh run list --branch main
# investigation CLI
readiness investigate l0 plan | run --approved-sha256 H --allow-model-calls --out DIR
readiness investigate run SITE --mode mock|live --id ID [--n-tasks 8 --total-cap-usd 2.05 --fix PROPOSAL_ID --post-plan FILE --allow-model-calls]
readiness investigate status RUN_DIR | approve RUN_DIR --stage S --sha256 H --note N | export RUN_DIR --out FILE
readiness investigate fork SOURCE --id NEW [--carry-investigation] | propose-owner RUN_DIR … | recover-batch RUN_DIR --batch I --abandon --note N
```
Credentials: `META_MODEL_API_KEY` in the environment or the git-ignored repo-root `.env` (mode 600). Never print it.

## 4. Completed work (merged to `main`)
Merge commits (short SHA): #34 a841e4b M1 foundations; #35 529a87c M2 inspector/mirror/patch DSL/zoo; #37 249278f M3 taskgen+freeze; #39 013712f M4/M5 trace + investigator; #40 4932a1c M6 recommend/apply/retest/evaluate; #41 70ed2fe bug hunt; #43 4286a49 **M7 read-only Investigation dashboard page + sanitized exporter**; #44 8396fab / #45 f688dd9 / #46 80b3626 L0 diagnostics, strict schemas, reasoning caps; #47 418ef6d L1a config (3-batch taskgen, baseline stage cap, crash-safe attempts); #48 cfdfc04 investigator repair + recovery fork; **#49 7dcb732 EXP-B design; #50 a58ca4b EXP-B implementation**. Earlier tasks (003–015) are summarized in `STATUS.md` / `docs/ARCHITECTURE.md`.

**L0 (Meta capability probe):** attempt 1 (hash `4a3af8a9…`) failed at the first request (schemas not strict-mode compliant); attempt 2 (`18a9c310…`) got HTTP 200 but empty output at a 200-token cap (hidden reasoning tokens count inside `max_completion_tokens`; the spend gate also under-reserved input by ~16 tokens); **attempt 3 (`0ce19b49…0b86`) PASSED C1–C7, US$0.038231 calculated** (`investigations/l0-probe-3`). Reasoning effort `low` is sent; completion caps 1,024 (echo) / 4,096 (structured).

**L1a on site-5 (`investigations/site-5-live`, the ORIGINAL run: never modify):** taskgen manifest `f1f29bf5…` (3 batches x 4 proposals, 6,144 tokens each, no retries): 12 proposals → **6 accepted** (3 page_fact, 2 extremum, 1 item_set; **no `reach_page`**), US$0.027114. Baseline manifest `9b887448…`: 6 trials, K=1, US$0.603977, **4 of 6 passed**. The first investigator attempt (manifest `cc9760e5…`) paid one request (US$0.002125) and then crashed on a recovery bug (single `action` object) — repaired in #48; its report said `no_supported_issue` and **must not be read as a negative finding**.
| task | kind / partition | baseline | note |
|---|---|---|---|
| `gen-0ac84d18d3` | page_fact / investigation | pass, 2 requests | detail-page fact |
| `gen-b05c45672f` | page_fact / investigation | pass, 3 | detail-page fact |
| `gen-f2731972ed` | page_fact / investigation | pass, 3 | detail-page fact |
| `gen-e38eac8644` | extremum / investigation | pass, 13 | **daily fee (affected by the experiment)** |
| `gen-0384beb35e` | extremum / holdout | **fail (agent)**, 13 | deposit; same-shape control |
| `gen-c7c642f78c` | item_set / holdout | **fail (tool_interface)**, 13 | **daily fee (affected)** |
Neither failure establishes a website defect. Frozen evaluation rule (in the tasks manifest, **never change**): `paired-signflip-v1`, alpha 0.10, min 4 pairs, pass-delta floor 0.25, request-reduction floor 0.25.

**Investigator (recovery fork `investigations/site-5-live-b`, manifest `d7bb1785…`):** completed, 8 requests, US$0.037036, all reconciled. One hypothesis `hyp-03c7dbfe96` (`info_absent_on_template`, label `daily fee`): *the `/tools` listing shows none of the five fields (`condition`, `copies available`, `daily fee`, `deposit`, `next available`) that all 8 detail pages carry* — **deterministically verified as a pattern, NOT promoted** (1 supporting trial, needs 2), no findings, no proposals. Holdout was never exposed to the investigator.

**Owner-selected experiment (EXP-B):** the owner chose an exploratory change: show `Daily fee: $N` in each `/tools` listing item (one `copy_field_to_listing` op, 8 elements, 105 bytes, detail pages untouched; patch sha256 `b2efe2f747c0a8713b5f0fac0b9874cf0528a7ccf475c89b25677243c10aaf1e`, parent snapshot `1796c2a3…`, result snapshot `27b2754e…`). It is **experimental and owner-selected, never an investigator-verified finding.** Design A+ (approved): six patched trials (all six frozen tasks) + three unmodified-repeat ("placebo") trials of `gen-e38eac8644`, `gen-c7c642f78c`, `gen-0384beb35e`; K=1 per task per arm; **fixed execution order** (`execution_order_sha256` `824dd4f0f53091dec3a2e8446368e281f534a5d9a951b3278e4e931ed2a1e768`): placebo e38 → patched e38 → patched c7c → placebo c7c → placebo 0384 → patched 0384 → patched 0ac8 → patched b05c → patched f273. **Caps (durable spend gate):** patched arm US$0.80, unmodified arm US$0.55, combined post-trials US$1.35 (= sum, redundant by design), per trial US$0.50, per request US$0.05, ledger ceiling US$2.05. **Statistics:** the frozen `paired-signflip-v1` is computed and reported unchanged (best case is `inconclusive`: only two tasks can be affected); the separate exploratory rules `exploratory-listing-v1` (hash `f8c25e461c64eb87c0bd77c5e0a38dce0a5721ddfd471a2d2eb35efc4aa6ea99`) use the contemporaneous unmodified repeat as the PRIMARY comparison and the imported baseline as SECONDARY; verdicts `consistent_with_h1` / `not_supported` / `inconclusive_conflicting_comparisons` (no support claimed if the comparisons conflict) / `uninterpretable`. Details: the pre-registration and Report 016l.

## 5. Current execution state (verify!)
- `main` = **`a58ca4b0d9b95667ef7203a90a4fde6764f879be`** (merge of PR #50; main CI "Credential-free checks" green). Working tree was clean.
- **Experimental fork: `investigations/site-5-live-c`** (created with `readiness investigate fork investigations/site-5-live-b --id site-5-live-c --carry-investigation`). Source run: `site-5-live-b` (itself a fork of the original `site-5-live`). Integrity verified: 209 imported files, `imported_files_sha256` `85b0307195b94e91…`; six frozen tasks (4 investigation / 2 holdout) and tasks manifest identical to the original; snapshot `1796c2a3…`; six baseline trials identical; carried investigator evidence prefix = 15 lines (`5254ebef…`), investigator status `completed`.
- **Spending:** the fork's ledger is byte-identical to the source's: 118 entries, **US$0.670252 committed** (taskgen 0.027114 + baseline 0.603977 + failed investigator attempt 0.002125 + investigator 0.037036), no outstanding reservations, no bound violations. Ceiling US$2.05 → **US$1.379748 remaining**; at the combined cap US$1.35 the headroom is US$0.029748. The programme ledger file (A$50 ceiling, last recorded A$6.2067 spent) does **not** include L0 (about US$0.0402) or L1a (US$0.670252) — roughly A$1.07 at 1.50 AUD/USD; estimated programme remaining about A$42.7. Do not edit the programme ledger without authorization.
- **Owner-selected proposal prepared (free):** `prp-06082b03bb` (hypothesis `hyp-9532f003ef`, owner `project-owner`, status `proposed`, not applied, no `patched/` directory, **no approvals recorded**). The hypothesis/prediction text deliberately names no holdout task.
- **`apply_fix` manifest (awaiting approval): sha256 `8cf55be28e515eb2c2a392b8655443dc6a490e05f23df1ef89c708c009c50c94`** (file `investigations/site-5-live-c/artifacts/manifests/apply_fix-8cf55be28e515eb2.json`; applies to the LOCAL MIRROR only; patch `b2efe2f7…`, result snapshot `27b2754e…`, carries `forked_from` provenance).
- Stage status in `site-5-live-c`: taskgen, freeze, baseline_trials, inspect, trace, investigate (carried), recommend (carried), report **done**; `apply_fix` **awaiting_approval**; `post_trials`, `evaluate`, `final_report` **not started**. The plan file is `investigations/site-5-live-c/plan-input.json` (a copy is committed at `collaboration/experiments/EXP-B/post-plan.json`).
- Other directories: `investigations/l0-probe`, `-2`, `-3` (L0 attempts, keep), `site-5-live` (original, keep untouched), `site-5-live-b` (fork with the completed investigator, keep untouched).
- Blockers: none technical. Pending owner decisions: approve `apply_fix`; later approve `post_trials`; authorize the paid run.

## 6. Critical restrictions (non-negotiable)
1. **Never spend money without the owner's explicit authorization of that run.** Calculated cost ≠ bill; the A$50 ceiling is a limit, not an authorization.
2. **Never approve an exact-manifest gate yourself** (`readiness investigate approve`) and never run with `--allow-model-calls` unless the owner authorized exactly that hash/run in this session.
3. Never modify frozen tasks, the frozen evaluation rule, the original run `site-5-live`, `site-5-live-b`, the L0 artifacts or the programme ledger. Never delete or rewrite evidence; preserve provenance and auditability (quarantine, don't discard).
4. **Never expose holdout evidence to the investigator** (it sees investigation-partition tasks/trials only). Do not open holdout trial traces. The owner accepted that the holdout is not blind *to the owner*.
5. Keep **verified findings** and **owner-selected exploratory changes** distinct everywhere (labels, reports, dashboard). Keep the **frozen statistical verdict** separate from the **exploratory verdict**; never present the latter as replacing the former; never claim support if the comparisons conflict; allowed wording is "consistent with / not consistent with …", not "proved".
6. Do not silently retry void, failed or quarantined trials; stop and report. Do not re-send an ambiguous taskgen request (`recover-batch` is an explicit owner decision).
7. Do not merge PRs without explicit authorization; do not push to `main`; use branches + PRs; commit explicit paths only (`uv.lock` untracked; never `git add -A`).
8. Never print/commit `META_MODEL_API_KEY`, `.env`, private criteria, raw traces or generated run data. Never deploy the dashboard / run `pages.yml` without approval; never embed real run data in the public build.
9. Keep scripted / mock / recorded / live evidence distinct; label synthetic fixtures; do not claim functionality that does not exist.

## 7. Next priorities
1. **Obtain the owner's approval of the exact `apply_fix` hash `8cf55be2…` and apply the experimental patch** (to the local mirror): `readiness investigate approve investigations/site-5-live-c --stage apply_fix --sha256 8cf55be28e515eb2c2a392b8655443dc6a490e05f23df1ef89c708c009c50c94 --note "<who approved what>"`, then (free, no `--allow-model-calls`) `readiness investigate run site-5 --mode live --n-tasks 8 --total-cap-usd 2.05 --id site-5-live-c --fix prp-06082b03bb --post-plan investigations/site-5-live-c/plan-input.json` — it applies the patch and stops at the `post_trials` gate.
2. **Prepare and report the exact `post_trials` manifest** printed at that gate (check: nine-step `execution_order` and its hash above, `rules_sha256` above, `proposal_id`, patched/placebo snapshot hashes, caps 0.80 / 0.55 / 1.35 / 0.50 / 0.05, ceiling 2.05, `forked_from.paid_stages_rerun: false`). Stop for the owner.
3. **Execute the nine-trial A+ experiment only after explicit paid-run authorization** (approve that exact hash, then re-run the same command with `--allow-model-calls`). Expected cost US$0.84–1.11 (hard caps above). On any void/quarantine/cap refusal/integrity error: stop and report.
4. **Evaluate and report** (`evaluate` and `final_report` are free): report the frozen verdict and the exploratory verdict separately with the evidence; include the coverage limitations (no `reach_page` task; `condition`/`copies available`/`next available` untested; the start-page leakage check ignores navigation labels; n=1 per cell).
5. **Build a polished, minimal Agent Readiness dashboard for the hackathon demo** (below).

## 8. Dashboard: what exists and what is proposed
**Exists (merged):** a React/Vite app with pages Overview / Scope comparison / Evidence & method / Recorded replay (Task 007) / Protected scanner / Site audit, and (#43) an **Investigation** page that loads a sanitized `investigation-dashboard-v1` export (`readiness investigate export RUN --out FILE`) or a clearly labelled synthetic fixture and shows the stage timeline, task outcomes (void-aware), evidence-backed findings, unverified hypotheses, proposals, and a baseline-vs-patched panel with measured/unmeasured and scripted/mock/recorded/live labels. **The exporter does not yet export the placebo (unmodified-repeat) trials or `evaluation.exploratory`.** Do not describe the demo dashboard as finished: **there is no polished demo journey.**
**Proposed (not built):** prioritise a compelling journey over new infrastructure: (1) *Website overview* (site, pages, task set, coverage limits), (2) *Agent activity* (per-trial outcome/requests/page views and sanitized journeys, void-aware), (3) *Findings and recommendations* (verified vs unverified vs owner-selected, evidence links), (4) *Before / after* (frozen verdict next to the exploratory verdict, placebo vs patched vs historical, honest "inconclusive"). Reuse the existing design system and the exporter; extend the exporter for placebo trials and the exploratory block; label scripted/mock/recorded/live; keep real run data out of the public build unless the owner approves a sanitized export.

## 9. Known issues / debts
- `readiness investigate fork --carry-investigation` prints a stale "NOT imported: … evidence store, investigator output" line (carry mode does import them); cosmetic.
- `fork` supports runs whose snapshot can be re-derived (zoo sites); crawled sites would need snapshot import.
- The start-page leakage check in the task gate reads body text only and ignores navigation labels; acceptance of a navigation task is not proof of validity.
- `STATUS.md`/`COLD_START.md` are partly stale; update them as part of closing the work (owner approval for merges).
- The combined US$1.35 cap equals the sum of the arm caps (redundant by design).
- Programme ledger not updated for L0/L1a runtime spend (needs owner agreement).
- The auto-mode classifier in some Claude Code sessions blocks live-mode CLI commands that reach approval gates unless the owner authorizes them explicitly.

## 10. Onboarding prompt for the next session
(Ready-to-paste; the same text was given to the owner in chat.)
```
You are taking over the Agent Readiness project (Meta Global Hackathon; internal deadline 2026-11-04 23:59 Sydney). Work in /home/vaibhav/Projects/Hack_Agent_Readiness.
1) Read collaboration/HANDOFF.md fully, then AGENTS.md, STATUS.md, docs/PROJECT.md, docs/DECISIONS.md, collaboration/proposals/EXP-B-listing-fee-preregistration.md and collaboration/reports/016k and 016l.
2) Verify the recorded state yourself: git status/log (main should be a58ca4b0… or later), the investigations/ run directories (site-5-live, site-5-live-b, site-5-live-c, l0-probe*), the fork integrity (agent_readiness.investigate.fork.verify_fork on each fork), the ledger totals (US$0.670252 committed, no outstanding reservations), proposal prp-06082b03bb and the apply_fix manifest hash 8cf55be2…0c94 (read the manifest file, recompute nothing paid). Do not trust the handoff over the repository; report any discrepancy.
3) Obey the restrictions in HANDOFF section 6: no spending, no approving gates, no --allow-model-calls, no merging, no editing frozen tasks / original runs / L0 artifacts / the programme ledger, no holdout exposure, no secrets. Only the owner can authorize those, per action.
4) Then reply with: a short summary of your understanding (project, state, restrictions), any discrepancies, and your proposed immediate next action (priority 1 in HANDOFF section 7 is waiting for the owner's approval of the exact apply_fix hash; in the meantime propose useful free work, e.g. exporter support for the placebo arm / exploratory block and the dashboard journey plan). Wait for my authorization before any consequential change.
```
