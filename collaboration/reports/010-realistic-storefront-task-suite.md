# Report 010 — Realistic storefront and diverse task suite (credential-free)

**Date:** 2026-10-28 · **Branch:** `task010-realistic-storefront` (PR open, **not merged**) · **Baseline:** `main` `c3d477c` · **Design:** [docs/TASK_SUITE_DESIGN.md](../../docs/TASK_SUITE_DESIGN.md)
No model call, API key use, deployment, paid service or private-artifact publication occurred. Scripted navigators are smoke checks, **not** model runs; no model has been run on the new environment.

## 1. What was built
- `agent_readiness/suite/` — domain-neutral contracts (`TaskSpec`, `TaskInstance`, `Variant`, `evaluate`, registries) and a credential-free scripted-smoke runner. A test proves the core imports no environment and exercises it with a toy non-shopping domain.
- `agent_readiness/environments/electronics/` — `electronics-v1`: 48-product catalogue (+ returns/delivery policies), FastAPI storefront (home, category listings, search, detail, help/returns/delivery; filters, sort, pagination), two controlled factors (4 variants), independent oracles, graders and four task templates (10 fixtures), scripted navigators.
- CLI: `readiness suite list | show <task> | smoke [--all-variants] [--output dir]` and `readiness serve-env [--variant availability=detail,specs=fragmented]`.
- Unchanged and byte-pinned: legacy storefront, inventory, task kinds, evaluator, oracle, templates, Task 006/007 schedule hashes.

## 2. Environment and fixture inventory
`environment_id` electronics-v1 · data version `electronics-v1+7c4eaccbb161` · variants (default first): `availability-listing+specs-structured`, `…-listing+specs-fragmented`, `…-detail+specs-structured`, `…-detail+specs-fragmented`.
| Category | Products | Notes |
|---|---:|---|
| Headphones | 14 | 8 with ANC (4 in stock ≤ A$300; 3 ≤ A$250), out-of-stock and over-budget ANC decoys, cheap non-ANC, one wired model |
| Laptops | 10 | RAM 8–64 GB, advertised battery 9–20 h, similar names (Air 14 / Air 14 Plus), RAM tie across two models |
| Monitors | 12 | 24–34 in, 60–165 Hz, USB-C or not; each of four cheaper decoys fails exactly one criterion |
| Accessories | 12 | chargers/cables/dock/hub/sleeves/mouse/stand with watts and connectors (compat-ready for later tasks) |
Tasks (frozen objective text and truth are in the design doc; public specs via `readiness suite show`): T1 ×3 (2 complete-set, 1 any-valid), T2 ×2 (one tie), T3 ×2, T4 ×3 = 10 task instances, all with 12 steps / 240 s / 12 requests.

## 3. Evaluator proof and verification (actual results)
- **Full local suite: 419 passed** (previous baseline 302): 117 new tests; legacy tests unchanged and green. Dashboard/Python exporter suites unaffected.
- **Scripted feasibility:** all 10 fixtures × 4 variants = 40 in-process runs evaluator-PASS and evidence-backed (3–6 page requests each); 40 more through real Chromium (every fixture × every variant) PASS, plus a deliberately wrong answer for each fails.
- **Wrong answers fail:** T1 — incomplete set, out-of-stock ANC decoy, over-budget ANC, non-ANC cheap item, empty list, wrong price, duplicates (and, for `any_valid`, sets, ineligible, over-budget); T2 — wrong RAM/battery conclusion, tie reported as a winner, sides swapped, wrong figures, similarly named product; T3 — each cheaper decoy (size, refresh, USB-C, out of stock), pricier eligible monitors, wrong price, unknown SKU, non-monitor, and the second fixture's decoys; T4 — every field mutated individually and another category's policy applied. Malformed or extra-field answers fail schema validation.
- **Evidence semantics:** a correct answer without the required pages is `passed` but not `evidence_backed`; with the pages it is both.
- **Not trivially answerable / no leakage:** crawl of every reachable page in all variants finds all 48 product pages and both policy pages and none of: oracle/truth/eligible/evaluator/fixture/task identifiers, data attributes, comments, scripts, hidden content. First-page checks: T1's eligible set spans listing page 2; RAM/battery/USB-C/policy numbers never appear on home or listing cards; SKUs only on detail pages. Variant identity never appears in URLs, headers or pages.
- **Variant invariants:** same products, order and prices across availability levels; stock cues and the in-stock filter exist only in `listing`; every specification fact appears in both presentations; policy pages byte-identical in every variant; the Browser Use agent view shows the factor differences (4 variants).
- **Browser behaviour:** real navigation, filtering, sorting, pagination, search, breadcrumbs, back/forward, policy links; mobile (390 px) no horizontal scroll on six page types × two presentations (this found and fixed an overflow in the delivery table); keyboard skip link, accessible names for every control/link, single `h1`, landmarks.
- **Defects found by the checks and fixed:** mobile overflow (table now scrolls in a labelled region); search ignored accessory connectors (`usb-c charger`); the first T4 scripted navigator read the nav bar's category and the independent grader rejected it — evidence that the evaluator, not the navigator, decides.

## 4. Limitations and unverified items
- One catalogue and ten fixtures; synthetic data; browse-only (no cart/checkout, no structured API, no policy-placement factor yet).
- Scripted navigators prove feasibility and grading, **not** that Muse Spark (or any agent) can solve the tasks within 12 steps, nor that either factor level is easier.
- The wire-level answer contract for Browser Use (new profiles, new schema hashes, guard) is not implemented; model-driven execution of these tasks is untested.
- Pagination/filter semantics are a plausible shop, not an accessibility audit (no axe-style tooling; basic semantics and keyboard checks only).
- Screenshots were produced locally (`Hack_Agent_Readiness_archive/task010-screenshots/`, **not committed or deployed**).

## 5. What Task 011 must consume
Registry/instances (`suite.registry.instances()`, `get_instance`), `TaskSpec.public()` (agent-visible), `evaluate(instance, answer, variant, visited_paths)` (independent verdict; keep truth server-side), `Variant`/`create_app` for controlled targets (variant chosen server-side, never by the user or URL), result records carrying task/template/version/environment/data/variant/evaluator/contract ids and a `mode` (`scripted_smoke` now; `mock`/`live` to be added), and the limits (12/240/12). It still needs: answer-schema → Browser Use adapter and new profile/guard pins, network allowlisting of the environment origin, mock provider fixtures for these tasks, and trace capture of visited paths for evidence checks.
