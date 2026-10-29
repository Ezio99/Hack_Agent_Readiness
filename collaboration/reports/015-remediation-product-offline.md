# Report 015 — autonomous diagnosis and remediation product (offline implementation; no paid call)

**Date:** 2026-10-29. Scope (owner-approved): offline implementation and tests, durable per-request spend guard integration, AUD budget tracking. **No model call, no key use, no spend.** Spec: [docs/TASK015_REMEDIATION_EXPERIMENT_SPEC.md](../../docs/TASK015_REMEDIATION_EXPERIMENT_SPEC.md).

## What was built
| area | files | notes |
|---|---|---|
| Diagnosis engine | `src/agent_readiness/remediation/{probe,findings,library,execution,discovery,engine,targets}.py` | black-box HTTP probe → rule-derived findings → library recommendations → optional agent-execution evidence → re-audit lifecycle → measured effects (only when supplied) |
| Product interfaces | `scanner/service/api.py` (+`store.py`), `cli.py`, `dashboard/src/pages/Audit.tsx` | `GET /api/targets`, `POST /api/audits`, `GET /api/audits[/id]`, admin `POST /api/admin/targets/{id}/changes`; `readiness audit URL [--previous]`; `readiness scanner serve --demo-target`; dashboard "Site audit" panel |
| Budget | `src/agent_readiness/budget.py`, `collaboration/budget/programme-ledger.json` | AUD tracking, USD originals kept, documented rate 1.50 (conservative), `check_stage()` |
| Spend guard | `src/agent_readiness/spend_gate.py` (extracted from `webarena/live.py`, unchanged behaviour), `scanner/execute.py` `request_gate=` | the Task 014 durable reserve-before-send gate now serves the synthetic suite too |
| Demonstration | `scripts/remediation_loop_demo.py`, `collaboration/reports/015-offline-demo-output.txt` | a pure API client (the service is started with `readiness scanner serve --demo-target`) |
Legacy code, schedules, profiles and data are untouched; Task 014 behaviour is preserved (its 16 gate tests still pass after the extraction).

## How each acceptance criterion is met (evidence = test or output)
1. **Detects stock absent from cards but present on product pages:** on the unmodified site the probe observes `0 of 54 listing cards … 6 of 6 sampled product pages` with page/element evidence (`test_baseline_detects_…`, demo output).
2. **Selects the recommendation from the library by evidence:** `show-availability-on-listing-cards` is selected only because `attribute_detail_only:availability` was observed; a second template (SKU) fires or not depending on what is observed (`test_recommendation_is_selected_…`, `test_findings_follow_the_observed_site_in_every_combination` over four site states).
3. **Evidence, rationale, benefit, confidence/validation:** each recommendation carries supporting evidence, a rationale generated from the finding's own counts, expected benefit, risks, `confidence` (`prior_evidence_other_site`, with the Task 007 basis and its limits) and `validation = unvalidated`.
4. **Independent rescan recognises resolution:** re-audit → `attribute_detail_only:availability` and `filter_absent:availability` are `RESOLVED` with card/filter evidence (`test_modified_site_is_recognised_…`, API test, demo).
5. **No labels/arms/hard-coded outcomes:** `test_nothing_in_the_engine_can_depend_on_arm_variant_or_demo_labels` (function signatures + source scan of the engine modules); `test_probe_is_not_tied_to_the_electronics_templates` runs the same rules on a differently structured stub shop; the audit API rejects any `url`/`variant_id` field (422).
6. **Distinct categories:** report sections `findings` (observed facts), `agent_execution` (separate; links to website findings only as `inferred`), `recommendations` (`proposed`, `unvalidated`), `lifecycle` (resolution ≠ effect), `measured_effects` (empty unless an experiment summary is attached with provenance). `test_taxonomy_…`, `test_audit_with_a_mock_agent_scan_keeps_agent_evidence_separate…` (findings identical with and without the scan).
7. **Through the product:** the API test and the demo run the whole loop over HTTP (invitation → session → audit → operator change → re-audit); CLI and dashboard use the same endpoints.

## Offline demonstration (actual output, abridged; mock scan variant in the `.txt`)
`uv run python scripts/remediation_loop_demo.py` → baseline audit: `[website_property] attribute_detail_only:availability: 0 of 54 listing cards (across 6 listing pages) show stock / availability state; 6 of 6 sampled product pages do.` + `filter_absent:availability` → `RECOMMENDATION [unvalidated, prior_evidence_other_site] Show stock status on listing cards`; operator applies `availability-on-listing-cards`; re-audit → `LIFECYCLE attribute_detail_only:availability: RESOLVED — 54 of 54 listing cards show stock`, `filter_absent:availability: RESOLVED`; `measured effects: not_measured`. With `--scan`, a **mock** agent scan is attached; it opened 5 product pages and (being scripted) behaves identically after the change — the product records that without claiming any improvement.

## Tests actually run
- New: `tests/test_remediation.py` (15), `tests/test_remediation_api.py` (3, one with real Chromium and a mock agent), `tests/test_webarena_live_gate.py` (+1: the gate in `execute_scan`; 17 total), `dashboard/src/audit.test.tsx` (3). Dashboard: 53 Vitest passed, `tsc` clean, build OK.
- Full Python suite (with the `webarena` extra): **590 passed** in 13m58s (570 before this work + 20 new).
- `npm run check:dist` fails locally only because Git-ignored replay files exist in `dashboard/public/replays/` on this machine (pre-existing, unrelated; CI does not have them).

## Limits and honest caveats
- The probe is validated on two markup families (our storefront, a differently structured stub). It uses text cues (e.g. "In stock", "SKU …") and structural heuristics; real sites will expose gaps, and `insufficient_coverage` / `indeterminate` are reported instead of guesses. JavaScript-rendered cards are not seen (plain HTTP). Only audit sites you operate or may test; the service accepts registered targets only.
- The recommendation library has two templates. Trace-driven discovery currently flags two generic patterns (list→product ping-pong, repeated product page) as candidates **without** recommendations.
- "Resolved" means the property is no longer observed. Whether agents do better is a separate, unmeasured question until the paid experiment runs.
- Prior evidence (Task 007) is from a different site and task, n = 3 per cell, descriptive.
- The managed demo target's initial state is operator configuration; the "apply change" endpoint is an admin-only stand-in for the site owner's own deployment.
- Not yet built: the pilot/experiment driver (≈ 3–4 h). No live model has run on any of this.

## Next (needs your decision; nothing paid is authorized)
Spec §10 contains the exact paid plan: pilot = 2 runs, hard cap US$1.00 = A$1.50; experiment = 18 runs, hard cap US$5.00 = A$7.50 after pilot review; per-request US$0.05, per-run US$0.50; programme check against the A$50 ceiling (A$44.12 remaining). First approve building the driver, then the pilot.
