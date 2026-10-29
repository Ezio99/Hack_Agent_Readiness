# Report 016b — Task 016 M2: generic inspection, snapshot/mirror, patch DSL, site zoo

Branch `task016-m2-inspect-mirror` (stacked on `task016-m1-foundations`, PR #34). **No paid call, no model call, no live agent trial, no external crawl, no frozen-file or budget-ledger edit.** Plan: [docs/TASK016_IMPLEMENTATION_PLAN.md](../../docs/TASK016_IMPLEMENTATION_PLAN.md).

## What was built (new, under `src/agent_readiness/investigate/`)
| module | purpose |
|---|---|
| `inspect/pagemodel.py` | domain-neutral page facts: headings, landmarks, links, nav links, forms and fields, every interactive control with a computed **accessible name and its source** (aria-labelledby/aria-label/label/content/img alt/svg title/title/placeholder), images and alt, tables, JSON-LD, label/value **facts** (dl, two-column tables, "Label: value" text), and **repeated item groups** found structurally (no prices, no shop cues) |
| `inspect/crawl.py` | bounded polite crawler: same origin, robots.txt, max pages/depth/query-variants/body/asset bytes, GET only, manual in-origin redirects, per-request SSRF re-check (reuses `remediation.probe.assert_public_host`, unchanged), request delay. Capture strips scripts/iframes/objects/`<base>`/meta-refresh/inline handlers (counted in `meta.fidelity`; `js_dependent_pages` ⇒ fidelity `low`) and rewrites same-origin absolute URLs root-relative. Fetchers: `HttpFetcher` (network) and `MappingFetcher` (in-memory, offline) |
| `inspect/profile.py` | site profile (link graph, click depth, templates, listing→detail relations with per-field "shown in the listing item?" counts, controls with no accessible name) and **neutral `Observation`s** (facts with `page:` refs; none names a problem) |
| `inspect/stage.py` | pipeline hook: freezes the snapshot per investigation (write-once), writes the profile artifact, adds observations to the M1 evidence store |
| `sitemodel/snapshot.py` | content-hashed, origin-independent snapshot (hash excludes timestamps/ports/origin); save/load with per-blob and index verification |
| `sitemodel/server.py` | read-only ASGI mirror: GET/HEAD only (others ⇒ 405, recorded), exact captured keys only, restrictive CSP (`default-src 'self'`, `form-action 'self'`), `no-store`, page-view log; served with the existing `scanner.serve.serve_app` |
| `sitemodel/patch.py` | closed op set: `set_attribute` (aria-label/alt/title/lang), `insert_text`, `add_link` (target must exist in the snapshot), `copy_field_to_listing` (copy a labelled fact from each item's detail page into the item). Plain text only; bounded ops/length/volume; **every inserted string needs provenance** (site text, page title or a small interface vocabulary) so a patch cannot invent an answer; ops that match nothing are refused; assets never change; result is a new snapshot with parent/patch hashes; original untouched |
| `zoo/` | four opaque, structurally different **non-shop** sites (`site-1..4`): workshops catalogue, civic library, recipes, trail guide. `zoo/sealed/*.json` holds the planted diagnoses; `zoo/sealed.py` is the only reader and provides `assert_blind(text)` for M3+ prompt builders |
| `cli.py` (extended) | `readiness investigate inspect (--zoo ID | --url URL --permission-ack)`, `mirror SNAPSHOT`, `patch SNAPSHOT PATCH.json --out DIR` |

Demonstration assignment (sealed, owner-approved categories): `site-1` information placement, `site-2` unlabeled/icon-only controls, `site-3` clean control; `site-4` is a development site (information several links deep; exercises a third category and the novel-hypothesis path).

## Tests (all offline)
New: `test_investigate_{inspect,snapshot_mirror,patch,zoo}.py` + 2 in `test_investigate_demo.py` ≈ 44 tests, of which 1 is `browser`-marked (real Chromium browses the mirror).
- **Snapshot determinism:** same content ⇒ same hash across runs and across crawled origins (absolute URLs rewritten); zoo snapshots reproducible; save/load round-trip; any tampered blob/index rejected.
- **Crawl boundaries:** off-origin links and redirects never fetched, robots honoured, depth/page/query-variant caps, non-HTML skipped, delay applied, `HttpFetcher` refuses other origins/loopback (unless allowed)/credentials/non-http, body capped.
- **Patch safety:** markup/`javascript:`/`data:`/handlers rejected; attribute and op allow-lists; provenance rule refuses invented text; link targets must exist; no-op patches refused; assets untouched; volume bounded; deterministic; original unmodified; **static re-check** works (after `copy_field_to_listing` the inspector no longer reports the fields as absent from the listing; after labelling, unnamed controls decrease).
- **Isolation of planted diagnoses:** no investigator-facing module mentions or imports the sealed manifests or the zoo (source scan); all content an investigator can see for every zoo site — served pages, snapshot meta, profile, observations, refs, ids — passes `assert_blind`; the guard is shown to fire on category ids, summaries (case/underscore-insensitive) and "planted"; site ids/titles are opaque; no shop vocabulary in inspector/mirror code; zoo pages are script-free and self-contained.
- **Distinguishing facts without diagnoses:** `site-1` shows 0/8 listing items repeating price/date/seats; the clean control repeats every decision field and has zero unnamed controls; `site-2` has ≥ 20 unnamed controls; `site-4` has a page at depth 3.
Results run locally: fast suite `scripts/dev-tests.sh` **612 passed** (569 before); browser-marked mirror test **1 passed**; frozen/pin guards (`main_design`, `suite_core`, `experiment_infra`, `profile_v3`, `remediation`, `remediation_security`, `markers`) **127 passed**. Full CI not re-run locally (per instruction); it runs on the PR. A scratch run confirmed Chromium navigates the icon-only link on `site-2` through the mirror.

## Deviations from the plan
1. Four zoo sites (3 demonstration + 1 development), not five; a second development site is cheap to add if prompt iteration needs it.
2. The sealed manifest content is *my* authorship; blindness protects the **model**, not the author. Planted-issue tests for the **investigator** (does it discover them?) start at M5/L1.
3. Mirror form handling: GET-only; a form submission is refused and recorded, never forwarded (so search/booking forms render but do not work). `form_state` criteria remain deferred.
4. Accessible-name computation is simplified (no CSS-generated content, no full ARIA name algorithm); noted as an approximation in `pagemodel.py`.
5. The `inspect` package name shadows nothing at runtime (absolute imports), but avoid `from . import inspect` collisions with the stdlib module inside that package.

## Remaining risks
- Rendering fidelity for JS-heavy real sites is `low` by construction (scripts removed); only the zoo and server-rendered sites are faithfully mirrored.
- Item-group and fact extraction are heuristics proven on four small sites; expect gaps on messier markup. Real-site inspection is not exercised (no external crawl was authorized); the one permitted public site still needs choosing.
- The inspector's observation vocabulary is what the M5 investigator will reason over: it is neutral by test, but whether the **model** finds it sufficient is untested until L1.
- Sealed token matching is substring-based on category ids and descriptions; it guards leakage of our own labels, not paraphrases the model itself might produce.

## What M3 (task generation, criteria, freeze) needs
1. A task candidate generator over `SiteProfile`/snapshot (find-a-fact, filter-select-set from item groups, reach-a-page) plus Meta proposals through `llm.complete_structured` with `assert_blind` on every prompt.
2. Criterion types and **deterministic extractors** over the snapshot (`page_fact`, `item_set`, `reach_page`), the gate (non-empty, stable, feasible by BFS on the profile's link graph, non-leaky vs the start page, ≥ 1 hop), and graders mapped onto `suite.core.TaskInstance`/`evaluate`.
3. Freeze: write-once `tasks-manifest.json` with SHA-256, private `criteria.json` (never in prompts), investigation/holdout partition.
4. Leakage tests (truth not in task text or start page; holdout never visible to investigator inputs).
Decisions I will take unless you object: criteria are compiled from LLM-proposed *locators* but the truth is always re-extracted by code; tasks for the three demonstration sites are generated by the model blind (not from the sealed `example_task` hints, which are only for tests).
