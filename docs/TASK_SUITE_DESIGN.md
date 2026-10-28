# Task suite and reference-environment design (Task 010)

Status: implemented on branch `task010-realistic-storefront` (PR open, not merged). Credential-free; no model call is made by any code or test in this design.

## 1. Principles
- **Preserve the past.** The Task 005–007 storefront, inventory, task kinds, evaluator, oracle, pilot schedules, profiles and run artifacts are untouched (their SHA-256s are pinned by `tests/test_suite_core.py`). The new environment is a *separate, versioned* package; historical experiments reproduce exactly.
- **Domain-extensible core.** `suite/core.py` knows nothing about shopping or electronics (a test proves it and a toy "atlas" domain exercises the contract). Electronics is the first registered environment.
- **Independent truth.** Oracles read the immutable catalogue directly; the web app, query layer, presentation code and scripted navigators are never imported by an oracle or grader (and vice versa for truth). Truth lives only in `TaskInstance.truth`; the public spec (`TaskSpec.public()`) carries neither truth nor concrete evidence pages.

## 2. Environment `electronics-v1`
- **Identity:** `environment_id = electronics-v1`; `data_version = electronics-v1+<12-hex hash of the canonical catalogue + policy snapshot>` (currently `electronics-v1+7c4eaccbb161`, pinned by a test). Any data change changes the version; ids and fixtures are never edited in place.
- **Catalogue:** 48 deterministic products (headphones 14, laptops 10, monitors 12, accessories 12) in `environments/electronics/catalog.py`: SKU, name, brand, category, integer AUD cents, stock flag, featured rank, rating and normalized specs (ANC, form, battery hours; CPU, RAM, storage, screen, advertised battery, weight, charger watts; monitor size, resolution, refresh, USB-C, panel; accessory kind, output watts, connector). Compatibility-ready fields (laptop charger watts, accessory output watts/connectors) exist for future tasks. Policies (returns by category; delivery by shipping class) live in the same snapshot and drive both the policy pages and the oracle. Fictional brands; no personal data, payments, carts or orders.
- **URLs:** `/` home · `/c/{headphones|laptops|monitors|accessories}` listing (`q, brand, max_price, sort, page, anc, form, min_ram, min_screen, usb_c, min_refresh, in_stock`) · `/search?q=…` · `/p/{slug}` detail (SKU shown on this page only) · `/help`, `/help/returns`, `/help/delivery`. Unknown routes 404, invalid filters 422, page numbers clamp. Page size 12 so eligible products spread across pages.
- **UI:** semantic landmarks, skip link, labelled forms, working filters/sort/pagination/search, breadcrumbs, responsive layout (policy tables scroll inside a labelled region), no `<img>` or placeholder/fake controls. No cart or checkout in v1 (a non-functional cart would be a fake control).
- **Controlled variants** (`variants.py`), selected by server configuration only; the variant never appears in a URL, header or page:
  - `availability`: `listing` (stock shown on home/listing/search cards, plus an in-stock filter) vs `detail` (stock only on product pages; no listing cue; the in-stock filter parameter is ignored so filtering cannot leak stock).
  - `specs`: `structured` (labelled specification table on detail pages; key-attribute chips on cards) vs `fragmented` (the same facts as prose on detail pages; no chips). A test checks that every fact value appears in both presentations.
  - Variant id: `electronics-v1/availability-<level>+specs-<level>` (4 variants; default `listing+structured`). Neither level is assumed better.
- **Policy/delivery pages and filters are identical in every variant**; underlying data and task wording never change when a factor changes.

## 3. Task contract (`suite/core.py`)
`TaskSpec` (public, frozen): `task_id, template_id, version, environment_id, data_version, objective, answer_schema (JSON Schema), start_path, outcome_type (unique | set | any_valid), evidence_policy, limits (12 steps / 240 s / 12 requests, as Task 007), evaluator_id/version, parameters`. `TaskInstance` adds the private `truth`, the pydantic answer model, the grader and the private `evidence` page requirements. `evaluate()` returns an `EvaluationRecord` with: `answer_valid`, `passed` (answer correctness only), `evidence_satisfied`/`evidence_backed` (additionally requires the required pages to have been observed), `missing_evidence`, `reasons`, `details`, and the task/template/version/environment/data/variant/evaluator/contract ids. Malformed answers fail with a schema reason, never an exception. Templates and environments register themselves (`suite/registry.py`); the scanner (Task 011) can enumerate and instantiate them generically.

## 4. P0 tasks (frozen fixtures; objective text is the only agent-visible task content)
| Template | Fixtures | Outcome | Frozen objective (fixture 1) | Evidence required | Oracle |
|---|---|---|---|---|---|
| T1 discovery | `under-250-all`, `under-200-all` (set), `under-300-any` (any_valid) | complete eligible set / one valid | every in-stock ANC headphone at or below A$250.00: SKU + price | reported products seen | ANC ∧ in stock ∧ price ≤ budget over the catalogue (3 / 2 / 4 eligible) |
| T2 comparison | `air14-vs-probook15`, `slate16-vs-air14` (RAM tie) | unique | RAM and advertised battery of two named laptops, who has more RAM / longer battery (`a`/`b`/`tie`) | both product pages | spec values + three-way comparison |
| T3 constraint selection | `27in-usbc-120hz`, `32in-usbc-60hz` | unique | cheapest in-stock monitor ≥ size, USB-C, ≥ refresh: SKU + price | the selected product's page | global minimum over eligible inventory; builder asserts a unique minimum and ≥ 1 pricier alternative |
| T4 policy/delivery | `lumio-pro-27c` (bulky, pays delivery), `kestrel-air-14` (14-day, 15% fee, free delivery), `tessera-whisper` | unique | return window, restocking fee %, delivery cost (cents, 0 if free for this price), delivery days min/max | product page + both policy pages | policy tables + product price/class |
Feasibility is verified programmatically (scripted navigators complete all 10 fixtures in all 4 variants; oracles assert uniqueness/size). Decoys: cheaper monitors that each fail one criterion, out-of-stock ANC items within budget, in-stock ANC items above budget, cheap in-stock non-ANC headphones, similarly named laptops, eligible items on listing page 2.

## 5. Evaluator semantics
Correctness only is `passed`; `evidence_backed` is reported separately (as in Task 007). T1 `set` requires exactly the eligible set with catalogue prices (precision/recall reported); `any_valid` requires exactly one eligible product; T2–T4 grade field by field. The agent's self-assessment is never an input. Scripted-smoke results carry `mode: scripted_smoke` and are never evidence about an agent.

## 6. Compatibility, risks and what is deliberately not done
- **No migration of legacy code:** the old `PublicTask.kind` literal, `Answer` model, runner profiles and Browser Use wire schema (pinned hashes) remain. Wiring the new tasks into the model-driven runner needs *new* profiles and a generic answer wrapper (different wire-schema hashes) — that is Task 011's integration work and must not alter old profiles.
- **Browser Use answer schema:** `TaskSpec.answer_schema` is a JSON Schema; the runner must adapt it to Browser Use's `output_model_schema` (or a `done` payload) and re-pin the guard hashes for the new profile.
- **Risk — scripted ≠ model:** feasibility proves the pages and graders, not that a model finds the answer in 12 steps.
- **Risk — fixture memorization / single catalogue:** one catalogue and ten fixtures; results do not generalize to real sites. Generated tasks (D006) are future work and would need independent feasibility validation.
- **Risk — factor interactions:** the two factors are crossed (4 variants) but no model has been run on them; no variant is claimed to be better.
