# Task 016 — Implementation plan: general-purpose autonomous website investigator

**Status: PROPOSAL, revision 2 (owner feedback incorporated 2026-10-29). Overall direction approved for planning; nothing is implemented, and no spending is authorized.** Written 2026-10-29 on `main` (`10f4247`) after a focused audit. No paid call, deployment, merge or destructive operation has been made or is requested. Issue: #28. 

## Revision 2 — changes after owner review of PR #32
**Approved by the owner:** overall direction; mirror-first controlled experiments (D2); the scope deferrals (rendered snapshots, `form_state`, cross-profile control, service endpoint); mirror-only fixes (D9); the diagnostics-overlay approach (D11); preserving frozen files (D5/§12); the site zoo. The A$6 per-investigation figure is a **planning ceiling, not a spending authorization**. CI optimization was done first as PR #33 (see `docs/CI.md`); PR #31 stays open until #33 is verified and merged.

**Two revisions requested and made below:**
1. **D8 relaxed.** The investigator may produce novel, open-ended hypotheses. They stay clearly labelled *unverified*; they can lead only to a clearly labelled **experimental proposal** that needs explicit owner approval; they are never presented as verified findings. Deterministic verification and the strict evidence standard for *verified findings* are unchanged. Affected: D6, D8, D9, D10, §5, §8, §9, §13.
2. **Real Meta-powered autonomous investigation is a protected deliverable, not a late add-on.** Scripted LLM tests remain necessary but are explicitly insufficient for the demonstration. A new **blind-demonstration protocol (D13)** governs two live investigations in two different friction categories plus a clean control, with the model never handed the planted diagnosis. The milestone order (§6) now puts the first live end-to-end slice before fixes/evaluation polish and puts secondary integrations (service endpoint, dashboard) last.

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
`Observation` (deterministic fact: probe/snapshot/trace metric) → `Hypothesis` (LLM or rule claim, **never a fact**; field `tier`: `verifiable` = expressed in the claim grammar with a registered verifier, or `novel` = free-form, open-ended, unverified) → `Finding` (only from a `verifiable` hypothesis + ≥1 deterministic verification + trace support + attribution) → `Proposal` (patch + expected effect + risks; field `basis`: `verified_finding` or `unverified_hypothesis`; the latter is rendered as **EXPERIMENTAL**; always `unvalidated`) → `Effect` (measured, attached as a *derived view*, live only). A measured effect of an experimental proposal says *this change moved these metrics*; it does **not** upgrade the hypothesis to a verified finding or establish its mechanism. Mirrors and extends `remediation-audit-v1`; the old report schema is unchanged and still produced by the old product.

**D7. Attribution taxonomy (deterministic first).** Each failed/inefficient trial gets exactly one primary class with evidence: `provider_or_budget` (void), `infrastructure` (void), `task_invalid` (criterion ambiguous/infeasible, e.g. >1 acceptable answers observed), `agent` (required info was in the model-visible observation and the agent missed or mis-answered; malformed output; repeated action), `tool_interface` (info in DOM but absent from the observation the model saw — the existing visibility-gap idea generalised), `website` (required info absent from every observation along all feasible paths, or inaccessible: unlabeled/unreachable control, error response, info only after extra hops), `undetermined`. Void classes never count as website results. A cross-profile control (same tasks, a second model/profile) is an *optional* stretch to separate agent from website.

**D8 (revised). Investigator (Meta) = read-only, tool-using, schema-bound, open to novel hypotheses, strict about what counts as verified.**
- Tools (no side effects): `list_trials`, `trial_summary`, `get_step(trial, n)` (sanitised), `page_text(page)`, `query_dom(page, selector)`, `compare_observation_to_dom(trial, step)`, `metric_compare(taskA, taskB)`. Bounded calls/tokens per investigation. Page text is wrapped as untrusted data; output only via JSON schema; every cited evidence id is checked to exist.
- **Two hypothesis tiers, both allowed.** `verifiable`: the claim uses the closed grammar (`info_absent_on_template`, `info_only_after_k_hops`, `control_unlabeled`, `observation_missing_dom_content`, `repeated_navigation`, `inconsistent_content_across_pages`, `error_response_on_path`, `step_overhead_vs_minimum`) and a registered verifier checks it against the snapshot and traces. `novel`: any open-ended explanation the model finds (e.g. a pattern across pages or a mechanism the grammar cannot express). A `novel` hypothesis requires a one-sentence falsifiable prediction ("if X were changed, metric Y on tasks Z would move in direction D") and ≥1 cited observation; it is stored as `unverified` and shown in its own report section.
- **Verified-finding promotion rule (unchanged strictness):** only a `verifiable` hypothesis whose verifier returns `supported`, with support in ≥2 independent trials/tasks (or one deterministic structural proof, e.g. unlabeled control on the only path) and attribution `website`/`tool_interface`. The investigator cannot promote anything; promotion is code. If nothing is promoted and no novel hypothesis is proposed: `no_supported_issue`, with the checked claims listed.
- **Novel hypothesis → experimental proposal.** The model may attach a proposed change. It must be expressible in the patch DSL (D9) to be auto-testable, otherwise it is recorded as `manual_change_described` (not auto-applicable, no experiment). Mandatory labelling: "EXPERIMENTAL — based on an unverified hypothesis; supporting observations: …; not a verified finding". It needs its own explicit owner approval (separate manifest hash, separate cap) before any patch is applied or trial run, exactly like a verified-finding proposal, and the report states which kind each proposal is.
- Held-out safeguard: the investigator never receives holdout traces or any `truth` value. It is also never given site-zoo metadata (D13).
- Provider: `LLMClient` protocol; `MetaClient` (OpenAI-compatible, `muse-spark-1.3`, reuses `ModelConfig`, `compat.py` prose-prefix recovery, schema validation, one retry, `LLMCallGate`); `ScriptedClient` (tests); `RecordedClient` (replays committed fixtures **and the live transcripts from approved runs**); configurable base URL/model for other OpenAI-compatible providers.

**D9. Fixes = a declarative patch DSL applied to the mirror; the owner approves; nothing touches a real site.** Ops (closed set): `copy_field_to_listing` (join detail-page fields onto listing items by href — generalises "show availability on cards"), `set_accessible_name`, `add_link`, `insert_text` (from existing page text only), `surface_policy_link`, `label_form_control`. Each patch: size-bounded, no script/external URL, every inserted string must have provenance in existing snapshot content or a fixed vocabulary, **static re-check** (the finding's own verifier must flip to `not_observed` on the patched snapshot — otherwise the proposal is marked ineffective before spending anything), answer-injection check against criteria. Library templates in frozen `library.py` remain available through an adapter but the new path doesn't depend on them. Proposals based on a `novel` hypothesis use the same DSL and the same safety checks, but skip the finding-verifier flip check (there is none) and are marked experimental. Output for the owner: patch JSON + human diff to apply on their real site. States: `proposed → approved(by owner, recorded) → applied(mirror) → measured`. The pipeline refuses to apply or spend without the recorded approval.

**D10. Evaluation design (pre-registered, written into the manifest before any trial).** Arms: `baseline`, `patched`, optional `placebo` (neutral patch of similar size). Same frozen tasks (investigation + holdout), same profile/seed schedule, K repeats, paired by task. Primary metric: evidence-backed pass; secondary: model requests, page views, cost. Verdict rule fixed in advance: `improvement` / `regression` / `inconclusive` with sign-flip permutation test (reuse the existing approach from `remediation/experiment`, re-implemented in `evaluate/stats.py` — no import of private helpers) and an effect-size floor; holdout and investigation results reported separately; any void run excluded and listed. With realistic n (≈12 pairs) most results will be `inconclusive` and the report says so. Claim language: "on these tasks, this model, this snapshot, n = …". For an experimental proposal the verdict is reported as a measured effect of the change only; the report repeats that the underlying hypothesis remains unverified.

**D11. Replacing `scanner/diagnostics.py` without editing frozen `execute.py`.** Add `investigate/diagnose.py` (trace-driven, label-free, supports `no_supported_issue`), called by the scanner *service layer* on the stored scan events and returned as `diagnostics_v2` next to the legacy `diagnostics`. The Scanner tab reads v2 when present and falls back to legacy for stored scans. Legacy module remains for frozen importers. (Approved by the owner.)

**D12. Budget & safety.** One new `InvestigationLedger` using existing `Ledger`/`Halt`; stage caps from AUD via `budget.check_stage`; per-request reserve-before-send for browser trials *and* LLM calls; approval = SHA-256 of the stage manifest (existing pattern); void classes and final halts as in Task 015; secrets never logged (existing `Recorder` scrubbing). Programme budget is only ever *checked*, never edited, except by a separately approved ledger entry after real spend.

**D13 (new). Blind live demonstration protocol.** Purpose: show real Meta-powered autonomous investigation without handing the model the diagnosis.
- **Demonstration set (three live investigations):** (A) a site with an *information-placement* friction (a decision-relevant attribute only on detail pages); (B) a site with a *different* category — *accessibility/interface* friction (icon-only or unlabeled controls on the only path) — chosen so no existing rule or library template matches it; (C) a **clean control** with no planted issue. Sites differ structurally and in domain from the electronics store.
- **Blindness:** the zoo's planted-issue manifest lives in a sealed file that only the post-hoc `scorer` reads. Site ids in prompts/reports are opaque (`site-1`…). A test fails if any string from a sealed manifest, a CSS class/comment/file name naming the issue, or a category label appears in any prompt, tool output, snapshot served to the agent, or task text. No prompt tells the model what category of problem might exist; the investigator's instructions list the *tools and the output schema*, not the failure modes (the verifiers' grammar is applied to its output afterwards, not shown as a menu of answers — the model may use the grammar's names only if it chooses to).
- **Scoring is honest and separate:** after the report is frozen, the scorer compares findings/hypotheses to the sealed manifest and records: found (verified) / found (novel, unverified) / missed / false positive on the control. A miss or a false positive is reported as is; we do not tune prompts on the demonstration sites after seeing a result without recording it as a second attempt (attempts are all preserved).
- **Development vs demonstration sites:** prompt/verifier iteration uses separate development zoo sites; the three demonstration sites are frozen first (hashes recorded) and used once each (one repeat allowed if a void class occurs). Live transcripts are saved (private) and a sanitised replay fixture is committed only after your approval.
- **Scripted tests stay** (they prove the plumbing, leakage controls and verifier correctness) but are labelled as such; no scripted result is ever presented as agent behaviour.

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

Stage 6 may also emit **experimental proposals** (from `novel` hypotheses), each separately approved. Live checkpoints **L0** (Meta capability probe), **L1** (first end-to-end live slice on a development site) and **L2** (the three blind demonstrations) each need your explicit approval of an exact manifest/cap. `--mode mock|recorded|live` is global; `live` additionally needs `--allow-model-calls` as today. Stages are resumable and never silently re-run a spending step.

## 6. Milestones (revised order: vertical slice with a real model first; secondary integrations last)
Each milestone ends with the fast suite green and a short report. Live work happens only at the named checkpoints, each with your approval.

| M | Content | Est. | Notes |
|---|---|---|---|
| M0 | CI optimization (**done: PR #33, awaiting your review**); merge #30; close #31 after #33 merges | — | Owner actions |
| M1 | `models` (evidence-v1 with hypothesis tiers), pipeline/run-dir skeleton, `llm/` (Meta client, scripted, recorded, call gate) | 1 d | No network. **L0 probe** (≈A$0.30 cap, needs approval) right after: JSON-schema output / prose-prefix behaviour for the investigator |
| M2 | `inspect` (generic page model, templates, robots) + `snapshot`/mirror server + patch DSL + **zoo**: dev sites + the 3 sealed demonstration sites (A information-placement, B accessibility/interface, C clean control) | 1.5 d | Blindness tests (D13) written here |
| M3 | `taskgen` (candidates, Meta proposals, criteria types, gate, freeze) + leakage tests | 1.5 d | Core scientific validity |
| M4 | `trials` (runner, mock navigator, attribution, schedule) | 1 d | |
| M5 | `investigator` (tools, hypothesis tiers, verifiers, promotion, sanitisation) + `diagnose` v2 | 1.5 d | Scripted fixtures include wrong hypotheses, injection pages, novel hypotheses |
| **L1** | **First live end-to-end slice** (taskgen → baseline trials → Meta investigation → report) on a *development* zoo site, small cap | 0.5 d + spend | Approval of exact manifest hash. Finds integration problems while there is time to fix them |
| M6 | `fixes` (+experimental proposals) + `evaluate` + `report` + full mock pipeline on all zoo sites | 1.5 d | |
| **L2** | **Blind demonstrations A, B, C** with real Meta agent + investigator; approved fix on the sites where a proposal emerges; post trials; scoring | 1 d + spend | Protected window; see below |
| M7 | CLI polish; read-only dashboard Investigation page; docs/STATUS/COLD_START | 1 d | Secondary |
| M8 | (stretch) service endpoint for registered targets; rendered snapshots; placebo arm in live runs | — | Only if time remains |

**Deadline (owner, 2026-10-29).** Internal project deadline: **2026-11-04 23:59 Australia/Sydney (AEDT)**. The official submission deadline is 2026-11-05 Sydney time; that day is deliberately reserved as buffer. This plan does not assume the official deadline has changed (to be verified against the official rules). Working back from 11-04 23:59 AEDT: M1 done (PR #34); M2 2026-10-30; M3–M5 2026-10-31 → 11-01; **L1** (first live slice, needs approval) by 2026-11-01; M6 by 11-02; **L2 (the three blind demonstrations) no later than 2026-11-03 Sydney time** so that 11-04 is for scoring, report, replay assets and polish. Time protection: (1) nothing in M7/M8 may displace L1/L2; (2) if the plan slips the first things dropped are M8, then the dashboard page (M7), then the live holdout/placebo arms — never L1/L2 or the blind protocol; (3) minimum viable demonstration if time collapses: M1–M5 + L1 + L2. I will re-estimate after M2 and after L1 and tell you early.

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
11. **CI sharding** could hide a lost test; mitigated by a coverage-union check, verified in PR #33.
12. **The live model may not find the planted issue, or may over-claim novel hypotheses.** That is a legitimate, reportable result; protections: verified/unverified separation, scoring against sealed manifests, all attempts preserved. Risk to the *schedule* is handled by L1 (early live slice) and the protected L2 window.
13. **Prompt over-fitting to demonstration sites.** Mitigated by development/demonstration split (D13).

## 8. Test strategy

- **Scripted/mock tests are necessary, not sufficient** (they prove plumbing, leakage controls and verifier correctness; they never count as evidence of model behaviour). **Blindness tests (D13):** sealed-manifest strings absent from prompts, tool outputs, served pages and task text. **Hypothesis-tier tests:** a `novel` hypothesis can never become a finding, always renders EXPERIMENTAL/unverified, never reaches a trial without its own approval hash, and its experimental proposal cannot be marked `verified`. **Everything else runs without a key**: scripted LLM, mock navigator, recorded fixtures. Fast tests stay in `-m "not browser and not slow"`; browser/pipeline tests marked as today.
- **Site zoo** (hand-built, committed, small): ≥5 structurally different static sites split into *development* sites and three sealed *demonstration* sites (D13). Planted issue families *not named to the system*: (a) key attribute only on detail pages, (b) unlabeled/icon-only controls, (c) policy/contact buried N hops deep, (d) inconsistent values across pages, plus (e) a **clean control site** and (f) a site with a *different* planted issue than any rule was written for (this exercises the novel-hypothesis path). Pass criteria: investigator-pipeline finds the planted issue family from traces and verifiers (via scripted LLM seeded with realistic *wrong* hypotheses too), refuses on the control (`no_supported_issue`), and never emits a finding outside the grammar.
- **Leakage tests**: truth strings absent from agent prompts/serving paths/investigator context; holdout traces absent from investigator tools; criteria not derivable from the start page; task text ∌ truth; frozen manifest hash changes if any task/criterion is edited; post-freeze edit attempts rejected.
- **Independent follow-up**: after a patch, the post-trial evaluation uses the *same* frozen criteria and a fresh snapshot hash; verifier-flip check; placebo and holdout reported separately.
- **Attribution tests**: golden traces for each class, including void classes never counted as website results.
- **Injection tests**: pages containing "ignore previous instructions…" never alter tool use or schema output.
- **Property tests**: patch DSL never produces script/external URL/oversize; extractors are deterministic.
- **Regression guards**: frozen-file hash tests, `test_markers`, existing 678 tests untouched. Dashboard: Vitest for the new page.
- **No-spend guarantee test**: live mode without approval hash/`--allow-model-calls` refuses.

## 9. Interfaces

CLI: `readiness investigate inspect URL`, `plan URL --goals` (freezes + prints manifest hash + cost bound), `run --approve <hash>` (stages 4–5), `recommend`, `approve-fix <proposal-id>`, `run --stage post --approve <hash>`, `report`. Service: `POST /api/investigations` for registered targets; `GET` for state/report. Dashboard: timeline (stage status), evidence graph (observation → hypothesis → finding → proposal → effect, with unverified/novel hypotheses and EXPERIMENTAL proposals visually distinct from verified findings, and void classes marked), before/after panel with verdict, task partition shown.

## 10. Meta usage (demonstrable, load-bearing)

Meta models perform: (1) task proposal from site summaries, (2) the agent under test, (3) trace-driven, open-ended hypothesis generation and investigation (verified or clearly-labelled unverified), (4) contextual fix proposals in the patch DSL. Deterministic code owns facts, truth, safety, controls and measurement. The report shows which statements originated from Meta and which were verified.

## 11. Budget (estimates; not authorizations)

Historical live cost ≈ US$0.08–0.10 per trial. A default investigation (6 tasks = 4 investigation + 2 holdout; baseline K=2 → 12 trials; patched 12; optional placebo 6) ≈ 24–30 trials ≈ **US$2.4–3.0 ≈ A$3.6–4.5**, plus investigator/taskgen LLM calls (to be bounded by the gate; exact estimate after the Meta probe). Planning ceiling **A$6.00 per investigation** (not an authorization). Planning envelope for approval requests: L0 probe ≈ A$0.30; L1 ≈ A$3–6; L2 three blind investigations ≈ A$12–18 (the control and any investigation without an approved fix need fewer trials). Worst-case plan ≈ A$24 of the A$43.79 remaining, leaving ≈A$20 for a repeat after a void run. Each checkpoint is requested separately with an exact manifest hash; nothing is spent until you approve it.

## 12. What stays untouched (verified by existing tests)

Legacy Task 003–007 files and templates, profile v2/v3, Task 012 Stage 1 schedule/manifest, Task 015 pilot artifacts and gate result (`stop` + erratum), the proposed main-stage manifest `11c7b4ec…` and its 12 frozen files, and the budget ledger. The 24-run stock experiment stays on hold. If any step turns out to require editing a frozen file I will stop and ask.

## 13. Definition of done for Task 016

A reviewer can run one command on a planted-issue mirror in mock mode and see the full chain; the same pipeline on the clean control returns `no_supported_issue`; leakage/blindness/injection/attribution/hypothesis-tier tests pass; **the approved live checkpoints L1 and L2 have produced real Meta-powered investigations on two different friction categories and a clean control, scored against sealed manifests with misses and false positives reported as they are**; STATUS/COLD_START/report updated; frozen hashes unchanged.

## 14. CI optimization — implemented separately (PR #33; supersedes the proposal in this section)
The §14 proposal was built and measured before any Task 016 coding. Result (3 consecutive green runs on GitHub-hosted runners): **wall-clock 13–15 min → 4.7 / 4.8 / 5.2 min**; one run per PR commit instead of two; complete suite preserved by sharding plus a gate that compares the shards' node ids with a full collection; verified red on a failing test and on a silently dropped test; unsharded nightly cross-check added. Details, caveats (runner-minutes per run rose, ~19 vs ~14) and the branch-protection settings you must configure: `docs/CI.md`. PR #31 is to be closed only after #33 is verified and merged.

## 15. Decisions made and open questions
**Decided by the owner (2026-10-29):** mirror-first (Q1), scope deferrals (Q2), site zoo (Q3, partly; see below), mirror-only fixes (Q5), diagnostics overlay (Q7), preserve frozen files / duplicate rather than re-freeze (Q8), CI first as a separate PR (Q10), A$6 as a planning ceiling only (Q9).

**Still open (my recommended default first):**
1. **Real-site generality:** do you want one own-or-permitted real public site *inspected only* (no trials) to show the inspector generalises beyond the zoo? Which one, if any?
2. **Demonstration domains (D13):** OK that A is information-placement and B is accessibility/interface friction (unlabeled/icon-only controls on the only path), with the clean control C? Or name another second category.
3. **L0 Meta probe** (≈A$0.30 cap) right after M1 — approve in principle? (exact request will follow with call count and cap)
4. **Verdict thresholds (D10):** I will put exact numbers in the pre-registered manifest for approval at L1; objections welcome now (default: paired pass-rate delta ≥ +0.25 with sign-flip p ≤ 0.10, or ≥25 % fewer requests at equal pass rate).
5. **Experimental proposals:** OK that an approved experimental proposal is tested with the same trial budget logic and reported as "measured effect of the change; hypothesis unverified"?
6. **Branching/PRs:** one PR per milestone from `task016-*` branches, merged by you? (This plan lives in PR #32.)
7. ~~Deadline timezone~~ — settled by the owner: internal deadline 2026-11-04 23:59 Australia/Sydney; 11-05 is buffer (see §6). Still to verify: the official rules' exact deadline.
