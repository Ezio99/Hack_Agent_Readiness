# Task 016 — Implementation plan: general-purpose autonomous website investigator

**Status: PROPOSAL for owner review. Nothing in this plan is implemented or approved.** Written 2026-10-29 on `main` (`10f4247`) after a focused audit. No paid call, deployment, merge or destructive operation has been made or is requested. Issue: #28. Submission deadline (per handoff): 2026-11-04 9 PM EST (timezone unconfirmed).

## 0. Audit baseline: what I verified, and discrepancies found

| Check | Result |
|---|---|
| Checkout | `main` = `10f4247`, clean; stack #22–#26 and #29 are **merged** |
| Fast suite | `scripts/dev-tests.sh`: **534 passed, 144 deselected, 39.4 s** (needs the venv on `PATH`; see §14.6). Full collection: **678 tests** |
| CI (last green `main` runs) | 13.2–14.7 min. One run's steps: install 0.7, non-browser 3.3, **browser 8.5** min |
| Budget | A$50 ceiling, ≈A$6.21 spent, **≈A$43.79 remaining** (ledger, calculated not billed). No paid call authorized |

Discrepancies the owner should know about:
1. **`collaboration/TASK016_HANDOFF.md` is not on `main`.** It exists only on branch `task016-handoff` (open PR #30), together with refreshed STATUS/COLD_START/AGENTS/ARCHITECTURE. I read it from that branch. `main`'s STATUS/ARCHITECTURE still describe the PR stack as open and give `d8132e9` as the baseline — stale until #30 merges.
2. The handoff names the plan `docs/TASK016_PLAN.md`; your instruction names it `docs/TASK016_IMPLEMENTATION_PLAN.md`. I followed yours.
3. **PR #31** (raise CI timeout 15→25 min) is open. §14 proposes a fix that makes it unnecessary; I would close #31 if you adopt §14.
4. **`scanner/execute.py` is frozen (hash-pinned in the proposed main-stage manifest) yet it calls `scanner/diagnostics.analyze` internally.** "Replace `scanner/diagnostics.py`" (a carried-in 015f decision) therefore cannot be done by editing `execute.py`; see D11.
5. `execute_scan` (frozen) takes a *registered* `task_id` and an in-process *environment variant*. It cannot run a task on an arbitrary URL. This is the biggest reuse gap (D5).

## 1. Goal

`readiness investigate <url> [--goals goals.yaml]` runs the full loop and produces one evidence-linked report:

inspect → generate tasks (owner-defined + autonomous) → freeze tasks and independent success criteria → baseline agent trials → Meta-powered investigation → deterministic evidence validation → recommendations → **owner-approved** controlled fix → rerun → **improvement / regression / inconclusive**, including **"no supported issue"**.

Non-goals: a universal readiness score; automated edits to a live third-party site; a claim of causal effect beyond the measured tasks/model/site/n; consolidating the three historical drivers; touching any frozen artifact.

## 2. Reuse / extend / replace map

Frozen files (12 in `experiment.FROZEN_FILES`, plus byte-pinned legacy, pilot evidence, ledger) are **imported, never edited**. Anything marked "beside" is a new module.

| Existing | Verdict for Task 016 |
|---|---|
| `remediation/probe.py` (SiteProbe: SSRF guard `assert_public_host`, same-origin, bounded, manual redirects) | **Frozen; import `assert_public_host`/limits only.** Its heuristics are shop-specific (price-in-card, two attributes, no JS). New `investigate/inspect/` crawler beside it |
| `remediation/{findings,library,engine,experiment,targets}.py` | **Frozen, stock-coupled.** Keep for the existing audit product. Reuse *patterns* (fingerprints, derived-view effects, manifest-hash approval, void classes, final halts) and `engine.report_sha256`, `attach_measured_effects` semantics. New evidence model beside them |
| `remediation/discovery.py` (detector registry), `execution.py` (agent-vs-site separation) | **Not frozen but shop-coupled** (product-template regex). Keep; new generic trace analyzers beside them |
| `suite/core.py` (TaskSpec/TaskInstance/EvidenceRequirement/`evaluate`, `canonical_hash`) | **Reuse as-is.** Generated tasks become `TaskInstance`s with a dynamic answer model and a generic criterion grader, so independent evaluation, `public()` (no truth) and evidence-backed logic are reused unchanged |
| `scanner/execute.py` | **Frozen.** Copy-adapt its ~100-line run loop into `investigate/trials/runner.py` (D5). Reuses `agent.attempt/create_model/profile`, `Recorder`, `build_journey`, `calculated_cost` by import |
| `agent.py`, `capture.py` (pre-send guard), `compat.py` (prose-prefix parser), `recorder.py`, `env.py` | **Reuse.** `capture.py` is frozen (import only) |
| `ledger.py`, `spend_gate.RequestGate/upper_bound_usd`, `budget.py` | **Reuse.** `upper_bound_usd(body)` works on any chat body, so a thin `LLMCallGate` covers non-browser LLM calls with the same reserve-before-send ledger |
| `scanner/service` (FastAPI, sessions, registered targets, store) | **Extend**: add `/api/investigations` for *registered* targets only |
| `scanner/diagnostics.py` | **Leave in place** (frozen `execute.py` and `experiment.py` import it). Add `diagnostics_v2` as a service-layer post-processor (D11) |
| `environments/electronics`, `scanner/mock.py` | Unchanged; becomes one of several test sites. Mock agent for generated tasks is new |
| dashboard (React/Vite/Vitest) | Extend with an "Investigation" page; existing panels untouched |
| `cli*.py` pattern (`COMMANDS`, `register`, `main`, lazy imports) | Reuse for a new `investigate` group |

## 3. Architectural decisions (answers to the handoff's §9 questions)

**D1. One new package, `src/agent_readiness/investigate/`, built beside everything.** Layers: `inspect → sitemodel(snapshot, patch) → taskgen → trials → evidence → investigator → fixes → evaluate → report`, orchestrated by a stage machine (`pipeline.py`) with durable per-stage artifacts under `investigations/<id>/` (git-ignored).

**D2. Trials run against a frozen local mirror of the site, not the live third-party origin.** A bounded same-origin crawl is stored on disk as a `SiteSnapshot` (pages + assets, content-hashed, robots-respecting) and served on loopback with **GET only** and form posts captured-not-forwarded. Why: (a) an agent clicking "buy/delete/subscribe" on someone's real site is a safety and legal problem; (b) baseline and post-fix runs differ *only* by the patch, which is what "controlled" means; (c) site drift between baseline and rerun is eliminated; (d) it gives a deterministic substrate for ground truth. Cost: fidelity loss on JS-heavy sites. Mitigation in M2: optional Playwright *rendered* snapshot (DOM serialised after load, scripts stripped, interactive state not captured). Honest limit: SPAs with server-side state are reported as `snapshot_fidelity: low` and trials on them are labelled accordingly. Audit of third-party URLs requires an `--i-operate-or-have-permission` acknowledgement, robots.txt compliance, rate limits, and the existing public-host/SSRF rules. The hosted API never accepts a free URL (unchanged: registered targets only).

**D3. Tasks are hybrid and always pass through the same deterministic gate.**
- *Owner-defined*: goals file gives task text plus a criterion (literal expected answer + the page that proves it, or a structured criterion).
- *Autonomous*: `taskgen/candidates.py` derives candidate journeys deterministically from the snapshot (find-a-fact on a page, filter-and-select-set from repeated item pages, reach-a-page, locate-policy/contact). Meta (`taskgen/propose.py`) sees a **sanitised site summary** (titles, headings, link graph, template clusters, extracted field names) and proposes *task text + criterion spec in a closed grammar*, referencing snapshot page ids. LLM output is a hypothesis; the gate decides.
- *Gate (all must pass, else rejected with a recorded reason)*: criterion compiles; truth is **computed by a deterministic extractor from the snapshot** (the LLM never supplies the truth); truth non-empty and unique/stable under re-extraction; **feasible** (BFS over the snapshot link graph from the start page finds the evidence pages within `max_steps`); **non-leaky** (truth not in task text; not derivable from the start page's model-visible text; evidence requires ≥1 navigation); not near-duplicate of another task.
- Criterion types (closed set, each with a grader, extractor and tests): `page_fact` (value at a locator on a page), `item_set` (items satisfying a predicate over structured fields extracted from repeated detail pages → precision/recall, the generalisation of the electronics oracle), `reach_page` (final URL/page evidence), `form_state` (stretch: captured sandbox submission).
- Freeze: write-once `tasks-manifest.json` (task specs, criteria hashes, snapshot hash, agent profile, limits, partition) with SHA-256; the private `criteria.json` is stored separately and never enters an agent or investigator prompt.

**D4. Leakage controls (tested, not asserted).** Agent sees only `TaskSpec.public()` and the mirror. Mirror serves page content only (no manifest, no criteria, no `X-` hints). Static test: criteria truth strings do not appear in any prompt/trace field except pages the site itself serves. Task partition frozen at freeze time: **investigation tasks** (investigator may see their traces) and **holdout tasks** (never shown to the investigator or used to choose a fix; used only for before/after). Fix patches are generated from *findings*, not from criteria, and are checked for answer-injection (D8).

**D5. Generic trial runner.** `trials/runner.py` is a copy-adapt of `execute_scan` taking `(GeneratedTask, SiteSnapshot|PatchedSnapshot)` instead of `(task_id, variant)`; same profile (`suite-v2-compat1`), fidelity guard, `RequestGate`, wall-clock timeout, `build_journey`, `core.evaluate`. Duplicating ~100 lines is the price of leaving frozen `execute.py` alone; if you later re-freeze, fold them together (listed as debt). Mock mode: a scripted navigator over the snapshot (follows the BFS evidence path, with injectable failure modes: gives up, answers wrong, loops) so the *entire* pipeline runs with no key.

**D6. Evidence graph with five separate record types** (`evidence-v1`, JSON, each with id, provenance, created_at, mode ∈ scripted|mock|recorded|live):
`Observation` (deterministic fact: probe/snapshot/trace metric) → `Hypothesis` (LLM or rule claim, in the closed claim grammar, **never a fact**) → `Finding` (hypothesis + ≥1 deterministic verification + trace support + attribution) → `Proposal` (patch + expected effect + risks; `unvalidated`) → `Effect` (measured, attached as a *derived view*, live only). Mirrors and extends `remediation-audit-v1`; the old report schema is unchanged and still produced by the old product.

**D7. Attribution taxonomy (deterministic first).** Each failed/inefficient trial gets exactly one primary class with evidence: `provider_or_budget` (void), `infrastructure` (void), `task_invalid` (criterion ambiguous/infeasible, e.g. >1 acceptable answers observed), `agent` (required info was in the model-visible observation and the agent missed or mis-answered; malformed output; repeated action), `tool_interface` (info in DOM but absent from the observation the model saw — the existing visibility-gap idea generalised), `website` (required info absent from every observation along all feasible paths, or inaccessible: unlabeled/unreachable control, error response, info only after extra hops), `undetermined`. Void classes never count as website results. A cross-profile control (same tasks, a second model/profile) is an *optional* stretch to separate agent from website.

**D8. Investigator (Meta) = read-only, tool-using, schema-bound, with deterministic verification.**
- Tools (no side effects): `list_trials`, `trial_summary`, `get_step(trial, n)` (sanitised), `page_text(page)`, `query_dom(page, selector)` , `compare_observation_to_dom(trial, step)`, `metric_compare(taskA, taskB)`. Bounded calls/tokens per investigation.
- Page text is wrapped as untrusted data, instructions in page content are ignored by construction (system prompt + delimiters), outputs only via a JSON schema; a hypothesis must cite evidence ids that exist (checked), and claim kinds are a **closed grammar** with a registered verifier each: `info_absent_on_template`, `info_only_after_k_hops`, `control_unlabeled`, `observation_missing_dom_content`, `repeated_navigation`, `inconsistent_content_across_pages`, `error_response_on_path`, `step_overhead_vs_minimum`. A claim outside the grammar is stored as `hypothesis/unverifiable` and can never become a finding or a recommendation.
- Finding promotion rule: verifier `supported` **and** support in ≥2 independent trials/tasks (or one trial with a deterministic structural proof, e.g. unlabeled control on the only path) **and** attribution = `website`/`tool_interface`. Everything else is reported as observation or unverifiable hypothesis. If nothing is promoted: outcome `no_supported_issue`, with the checked claims listed.
- Held-out safeguard: the investigator never receives holdout traces or any `truth` value.
- Provider: `LLMClient` protocol; `MetaClient` (OpenAI-compatible, `muse-spark-1.3`, reuses `ModelConfig`, `compat.py` prose-prefix recovery, schema validation, one retry, `LLMCallGate`); `ScriptedClient` (tests); `RecordedClient` (replays committed fixtures); configurable base URL/model for other OpenAI-compatible providers.

**D9. Fixes = a declarative patch DSL applied to the mirror; the owner approves; nothing touches a real site.** Ops (closed set): `copy_field_to_listing` (join detail-page fields onto listing items by href — generalises "show availability on cards"), `set_accessible_name`, `add_link`, `insert_text` (from existing page text only), `surface_policy_link`, `label_form_control`. Each patch: size-bounded, no script/external URL, every inserted string must have provenance in existing snapshot content or a fixed vocabulary, **static re-check** (the finding's own verifier must flip to `not_observed` on the patched snapshot — otherwise the proposal is marked ineffective before spending anything), answer-injection check against criteria. Library templates in frozen `library.py` remain available through an adapter but the new path doesn't depend on them. Output for the owner: patch JSON + human diff to apply on their real site. States: `proposed → approved(by owner, recorded) → applied(mirror) → measured`. The pipeline refuses to apply or spend without the recorded approval.

**D10. Evaluation design (pre-registered, written into the manifest before any trial).** Arms: `baseline`, `patched`, optional `placebo` (neutral patch of similar size). Same frozen tasks (investigation + holdout), same profile/seed schedule, K repeats, paired by task. Primary metric: evidence-backed pass; secondary: model requests, page views, cost. Verdict rule fixed in advance: `improvement` / `regression` / `inconclusive` with sign-flip permutation test (reuse the existing approach from `remediation/experiment`, re-implemented in `evaluate/stats.py` — no import of private helpers) and an effect-size floor; holdout and investigation results reported separately; any void run excluded and listed. With realistic n (≈12 pairs) most results will be `inconclusive` and the report says so. Claim language: "on these tasks, this model, this snapshot, n = …".

**D11. Replacing `scanner/diagnostics.py` without editing frozen `execute.py`.** Add `investigate/diagnose.py` (trace-driven, label-free, supports `no_supported_issue`), called by the scanner *service layer* on the stored scan events and returned as `diagnostics_v2` next to the legacy `diagnostics`. The Scanner tab reads v2 when present and falls back to legacy for stored scans. Legacy module remains for frozen importers. Needs your confirmation (Q7).

**D12. Budget & safety.** One new `InvestigationLedger` using existing `Ledger`/`Halt`; stage caps from AUD via `budget.check_stage`; per-request reserve-before-send for browser trials *and* LLM calls; approval = SHA-256 of the stage manifest (existing pattern); void classes and final halts as in Task 015; secrets never logged (existing `Recorder` scrubbing). Programme budget is only ever *checked*, never edited, except by a separately approved ledger entry after real spend.

## 4. Module layout

```
src/agent_readiness/investigate/
  models.py          evidence-v1 records, ids, provenance, enums (attribution, claim kinds)
  pipeline.py        stage machine, run dir, resume, approvals, void handling
  inspect/           crawl.py (robots, rate limit, SSRF reuse), pagemodel.py (headings, landmarks, links, forms,
                     controls+accessible names, tables, JSON-LD/microdata, label:value pairs), templates.py (page clustering),
                     rendered.py (optional Playwright snapshot)
  sitemodel/         snapshot.py (store/hash), server.py (loopback GET-only mirror), patch.py (DSL), patchops.py
  taskgen/           candidates.py, propose.py (LLM), criteria.py (types, extractors, graders), gate.py, freeze.py, goals.py
  trials/            runner.py, schedule.py, mock_agent.py, attribution.py, records.py
  investigator/      agent.py (tool loop), tools.py, claims.py (grammar), verifiers.py, promote.py, sanitize.py
  fixes/             propose.py (LLM + rule), validate.py (static re-check, injection, provenance), approve.py
  evaluate/          design.py (pre-registration), stats.py, verdict.py
  report/            build.py (investigation-report-v1 + derived effects view), render_md.py
  llm/               client.py (protocol), meta.py, scripted.py, recorded.py, gate.py
  diagnose.py        trace-driven diagnostics v2
  cli.py             `readiness investigate inspect|plan|run|status|approve-fix|report`
tests/investigate/   (mirrors the layout; see §8)
tests/fixtures/sites/ planted-issue site zoo (§8)
```
Service: `scanner/service/investigations.py` (new router, registered targets only). Dashboard: `pages/Investigation.tsx`, `lib/investigationApi.ts`.

## 5. Pipeline stages and gates

| # | Stage | Output | Spend | Gate |
|---|---|---|---|---|
| 1 | inspect | `snapshot/` + `site-profile.json` | none | permission acknowledgement, robots |
| 2 | taskgen | candidates, LLM proposals, gate verdicts | small LLM | none |
| 3 | freeze | `tasks-manifest.json` (+hash), private `criteria.json` | none | write-once |
| 4 | baseline trials | trial records | **trials** | **owner approves manifest hash + cap** |
| 5 | investigate | hypotheses → verified findings | **LLM** | approved cap (same stage manifest) |
| 6 | recommend | proposals + static re-check | LLM | none |
| 7 | apply fix | patched snapshot | none | **owner approves a specific proposal** |
| 8 | post trials | trial records (patched, placebo) | **trials** | **approval of second manifest hash** |
| 9 | report | `investigation-report-v1` + verdict | none | — |

`--mode mock|recorded|live` is global; `live` additionally needs `--allow-model-calls` as today. Stages are resumable and never silently re-run a spending step.

## 6. Milestones (ordered; each ends with the fast suite green and a short report)

| M | Content | Est. | Notes |
|---|---|---|---|
| M0 | Merge PR #30 (docs), CI optimization PR (§14), close #31 | 0.5 d | Approvals required. Speeds all later iteration |
| M1 | `models`, run-dir/pipeline skeleton, `llm/` (scripted/recorded/Meta stub + gate), plan doc→spec | 1 d | No network |
| M2 | `inspect` (generic page model, templates, robots) + `snapshot`/mirror server + `patch` DSL + **site zoo** | 1.5 d | Largest new surface; rendered snapshot deferred to stretch |
| M3 | `taskgen` (candidates, criteria types, extractors/graders, gate, freeze) + leakage tests | 1.5 d | Core scientific validity |
| M4 | `trials` (runner, mock navigator, attribution, schedule) | 1 d | Real Chromium tests only for the runner's boundary |
| M5 | `investigator` (tools, grammar, verifiers, promotion, sanitisation) + `diagnose` v2 | 1.5 d | Mock LLM fixtures incl. injection attempts |
| M6 | `fixes` + `evaluate` + `report` + end-to-end mock pipeline on all zoo sites | 1.5 d | Includes no-issue control, placebo |
| M7 | CLI group, service endpoint, dashboard Investigation page, docs/STATUS/COLD_START | 1 d | |
| M8 | **Live validation** (approval): 1–2 sites, small caps | 0.5 d + spend | Meta JSON-mode probe first (Q4) |

≈ 9.5 d of focused work against **6 calendar days** to the deadline. This does not fit unless cut. **Proposed cut line** (what I would protect): M1–M6 complete in mock mode, M7 reduced to CLI + read-only dashboard page, M8 on one real-agent run on one planted-issue site and one no-issue control. **Defer if time-pressed:** rendered (Playwright) snapshots, `form_state` criterion, cross-profile control, placebo arm in live runs (kept in mock/tests), service endpoint. I will re-estimate after M2; tell me if you want a harder scope cut now.

## 7. Risks

1. **Schedule** (above). Biggest risk; mitigated by the cut line and by doing CI first.
2. **Mirror fidelity** on JS-heavy sites → results look cleaner than reality. Mitigation: explicit `snapshot_fidelity` label; demo on sites we can honestly mirror.
3. **Ground truth for arbitrary sites** is only as good as extractors; wrong truth makes a site look bad. Mitigation: gate (unique, stable, feasible), extractor unit tests, task-invalid class, human-readable criteria in the report, owner can veto tasks at freeze.
4. **LLM investigator over-claims or is injected by page text.** Mitigation: closed claim grammar + deterministic verifiers + citation checks + untrusted-data framing; test with planted injection pages.
5. **Meta endpoint behaviour**: ~80 % of agent steps already need the prose-prefix recovery; JSON mode/tool-calling for the investigator is unverified. Mitigation: tiny probe before M8; `compat.py` recovery + schema validation + one retry; investigator uses a plain structured-output loop rather than native tool-calling.
6. **Statistical power**: ≈12 pairs rarely gives `improvement`. We report `inconclusive` honestly; demo can use a site where friction is large; claims limited accordingly.
7. **Hidden shop coupling** creeping into "general" code (e.g. price-in-card). Mitigation: zoo spans ≥4 structurally different sites; a lint-style test fails on shop vocabulary in `investigate/`.
8. **Duplicated runner** (D5) drifts from `execute_scan`. Mitigation: shared tests on both; debt entry.
9. **Cost surprises**: reserve-before-send gate, caps per stage; no spend without hash approval.
10. **Third-party URL legality/ethics**: permission acknowledgement, robots, rate limits; hosted API stays registered-targets-only.
11. **CI sharding** could hide a lost test; mitigated by a coverage-union check (§14).

## 8. Test strategy

- **Everything runs without a key**: scripted LLM, mock navigator, recorded fixtures. Fast tests stay in `-m "not browser and not slow"`; browser/pipeline tests marked as today.
- **Site zoo** (hand-built, committed, small): ≥4 structurally different static sites. Planted issue families *not named to the system*: (a) key attribute only on detail pages, (b) unlabeled/icon-only controls, (c) policy/contact buried N hops deep, (d) inconsistent values across pages, plus (e) a **clean control site** and (f) a site with a *different* planted issue than any rule was written for. Pass criteria: investigator-pipeline finds the planted issue family from traces and verifiers (via scripted LLM seeded with realistic *wrong* hypotheses too), refuses on the control (`no_supported_issue`), and never emits a finding outside the grammar.
- **Leakage tests**: truth strings absent from agent prompts/serving paths/investigator context; holdout traces absent from investigator tools; criteria not derivable from the start page; task text ∌ truth; frozen manifest hash changes if any task/criterion is edited; post-freeze edit attempts rejected.
- **Independent follow-up**: after a patch, the post-trial evaluation uses the *same* frozen criteria and a fresh snapshot hash; verifier-flip check; placebo and holdout reported separately.
- **Attribution tests**: golden traces for each class, including void classes never counted as website results.
- **Injection tests**: pages containing "ignore previous instructions…" never alter tool use or schema output.
- **Property tests**: patch DSL never produces script/external URL/oversize; extractors are deterministic.
- **Regression guards**: frozen-file hash tests, `test_markers`, existing 678 tests untouched. Dashboard: Vitest for the new page.
- **No-spend guarantee test**: live mode without approval hash/`--allow-model-calls` refuses.

## 9. Interfaces

CLI: `readiness investigate inspect URL`, `plan URL --goals` (freezes + prints manifest hash + cost bound), `run --approve <hash>` (stages 4–5), `recommend`, `approve-fix <proposal-id>`, `run --stage post --approve <hash>`, `report`. Service: `POST /api/investigations` for registered targets; `GET` for state/report. Dashboard: timeline (stage status), evidence graph (observation → hypothesis → finding → proposal → effect, with void/unverifiable clearly marked), before/after panel with verdict, task partition shown.

## 10. Meta usage (demonstrable, load-bearing)

Meta models perform: (1) task proposal from site summaries, (2) the agent under test, (3) trace-driven hypothesis generation and investigation, (4) contextual fix proposals in the patch DSL. Deterministic code owns facts, truth, safety, controls and measurement. The report shows which statements originated from Meta and which were verified.

## 11. Budget (estimates; not authorizations)

Historical live cost ≈ US$0.08–0.10 per trial. A default investigation (6 tasks = 4 investigation + 2 holdout; baseline K=2 → 12 trials; patched 12; optional placebo 6) ≈ 24–30 trials ≈ **US$2.4–3.0 ≈ A$3.6–4.5**, plus investigator/taskgen LLM calls (to be bounded by the gate; exact estimate after the Meta probe). Proposed default hard cap **A$6.00 per investigation**; two live demonstrations ≈ A$12 of the A$43.79 remaining. Nothing is spent until you approve an exact manifest hash.

## 12. What stays untouched (verified by existing tests)

Legacy Task 003–007 files and templates, profile v2/v3, Task 012 Stage 1 schedule/manifest, Task 015 pilot artifacts and gate result (`stop` + erratum), the proposed main-stage manifest `11c7b4ec…` and its 12 frozen files, and the budget ledger. The 24-run stock experiment stays on hold. If any step turns out to require editing a frozen file I will stop and ask.

## 13. Definition of done for Task 016

A reviewer can run one command on a planted-issue mirror in mock mode and see the full chain; the same pipeline on the clean control returns `no_supported_issue`; leakage/injection/attribution tests pass; one approved live investigation (if you authorize it) produces an honestly labelled result; STATUS/COLD_START/report updated; frozen hashes unchanged.

## 14. CI optimization (separate small PR, before M1; needs your approval)

**Measured (runs on `main`, `test.yml`):** one serial job of 13.2–14.7 min = install 0.7 + non-browser 3.3 + **browser 8.5** (101 Chromium tests). Other observations: (i) the workflow triggers on both `push` and `pull_request`, so every commit on a PR branch runs the full suite **twice** (e.g. `ci-timeout`, `task016-handoff`); one push run took 30.5 min (queue contention); (ii) no concurrency control, so superseded commits keep running; (iii) PR #30 was cancelled by the 15-min timeout after all tests had passed (raising the limit treats the symptom).

**Proposal (no test removed, filtered or skipped):**
1. **Triggers:** `pull_request`, `push` only on `main`, plus `workflow_dispatch`. `concurrency: group: ci-${{ github.ref }}, cancel-in-progress: true` (not cancelling on `main`). Removes the duplicate run and stale runs.
2. **Parallel jobs:** `logic` (`-m "not browser"`, 3.3 min) and `browser` as a **4-shard matrix** (≈2.2 min of tests each). Sharding via a few lines in `tests/conftest.py` (`--shard-id/--num-shards`: sort node ids, assign `i % n`) — no new dependency, covers every test by construction. Per-shard `--basetemp` and artifact names.
3. **Cache Playwright browsers** (`~/.cache/ms-playwright`, keyed on the Playwright pin in `requirements.lock`).
4. **Merge-time verification is preserved or strengthened:** a final `gate` job (`needs: [logic, browser]`, `if: always()`) is the single required status check; it fails unless every shard succeeded. A **coverage check** in the gate compares the union of shard-collected node ids to the full `--collect-only` count, so a shard can never silently drop tests. A **scheduled + manual unsharded full run** (`python -m pytest -q`, single job, 25-min timeout) cross-checks the sharded result. The browser/info-boundary suite still runs in full on every PR and on `main`.
5. **Guard test:** `tests/test_markers.py` currently asserts the literal commands `python -m pytest -m "not browser" -q` / `-m browser -q`. It must be updated *deliberately* to assert the new invariants (no `slow`/`not slow` filter; every shard runs `-m browser` with shard flags; the gate and coverage check exist). I will propose that diff for your review rather than slip it in.
6. **Local speed (optional, dev-only):** make `scripts/dev-tests.sh` find `.venv` (it currently fails with `python: not found` unless the venv is on `PATH`) and optionally pass `-n auto` when `pytest-xdist` is installed (534 tests ≈ 39 s → est. 10–15 s; xdist stays out of CI and `requirements.lock`).

**Expected effect (estimate, unmeasured until tried):** PR wall-clock ≈ install ~1 min + max shard ~2.5–3 min ≈ **4–5 min** (from 13–15), and half the runner-minutes per commit. Risk: Chromium test contention/ports under parallel shards on 2–4 vCPU runners; I would validate with three consecutive runs before asking you to merge, and fall back to 2 shards if flaky. Dashboard workflow is already path-filtered and unchanged.

## 15. Open questions for you (my recommended default first)

1. **Mirror-first trials (D2)** instead of trialling on the live origin? *Recommend yes; live-origin trials only for sites you operate, as a later option.*
2. **Scope cut (§6):** accept deferring rendered snapshots, `form_state`, cross-profile control and the service endpoint? *Recommend yes.*
3. **Demo sites:** may I author the planted-issue zoo (4–5 small sites) as committed fixtures, and which real public/own site, if any, do you want inspected (inspect-only, no trials) to show generality? *Recommend zoo + one own-or-permitted real site.*
4. **Meta capabilities:** approve a minimal paid probe (a handful of calls, cap ≈A$0.30) to check JSON-schema output/tool-calling behaviour for the investigator before M5? *Recommend yes, after M1.*
5. **Fix scope:** OK that "controlled environment" means the patched mirror plus an exported patch for the owner, never a push to a real site? *Recommend yes.*
6. **Pre-registered verdict thresholds (D10):** accept pass-rate delta floor ≥ +0.25 (paired, sign-flip p ≤ 0.10) or ≥25 % fewer requests at equal pass rate? *I will propose exact numbers in the manifest design for approval; objection welcome now.*
7. **Diagnostics v2 as a service-layer overlay (D11)** rather than touching frozen `execute.py`? *Recommend yes.*
8. **Frozen-file exception policy:** if a clean design needs one change in a frozen file (e.g. a hook in `execute.py`), do you prefer I (a) duplicate, as planned, or (b) stop and plan a deliberate re-freeze? *Recommend (a) now.*
9. **Per-investigation cap** A$6 default and two live demos (≈A$12 total): acceptable envelope to plan against (not an authorization)?
10. **CI:** approve the §14 PR as the first deliverable and closing #31? Should the sharded design also require a `gate` check in branch protection (a repo-settings change you'd make)?
11. **Branching/PRs:** one PR per milestone from `task016-*` branches, merged by you? And should this plan go on a branch and PR now (I have left it uncommitted)?
12. **Deadline timezone** (2026-11-04 9 PM EST — confirm), since it fixes the live-validation window.
