# Ironbark Hire Co. — a realistic equipment-rental storefront (candidate Experiment 2 site)

**Status:** new, isolated, offline. It is *not* the EXP-B tool-library site, it replaces nothing, and no agent has been run on it. Nothing here is an experimental result.
Screenshots: [docs/screenshots/ironbark/](screenshots/ironbark/). Candidate experiments: [collaboration/proposals/EXP2-candidate-scenarios.md](../collaboration/proposals/EXP2-candidate-scenarios.md).

## Run it
```bash
readiness site serve                              # control site on http://127.0.0.1:8200/
readiness site serve --variant cost --port 8201   # a candidate variant (see below)
readiness site build --variant control            # writes build/ironbark/control/ (git-ignored)
readiness site variants                           # lists variants with their build fingerprints
readiness site catalogue --out catalogue.json     # the machine-readable source of truth
readiness site tasks                              # illustrative candidate tasks with independently computed answers
```
No network, model, or credentials are used. The server binds loopback, serves GET/HEAD only and returns 405 to anything else. The site has no JavaScript and no forms.

## What it is
A fictional Sydney equipment-hire business (the name, makers *Kestrel / Marlow / Torvald*, phone number, `.example` e-mail address and street address are invented; the footer says so on every page).

* **16 hire products** in 5 categories (drilling & breaking, cutting, landscaping, access & height, ground & concrete), **8 accessories/consumables**, **3 kits**.
* Pages: home, catalogue (all, three sort orders, five category pages), 16 product pages, 16 booking-calendar pages, accessories (index + 8), kits, hire terms and pricing, about, contact. 55 pages and 51 assets (106 files) in the control build.
* Product data: stable IDs (`IB-DRL-001` …), slugs, maker/model, daily/weekend/weekly rates, refundable deposit, minimum hire, delivery optional/required, fleet size, a specification table, what is included, hire conditions, and an eight-week booking calendar.
* Deliberate overlap so tasks are non-trivial: e.g. three items can cut (tile saw 80 mm deep, cut-off saw 125 mm deep, chainsaw); two can drill masonry (10 mm vs 26 mm); delivery is required for four heavy items and optional for the rest; some items are booked out on specific days; accessories fit by shank/blade/battery/voltage tags.

## What is real functionality and what is presentation
| Real (and tested) | Presentation only |
|---|---|
| Every price, rate, deposit, specification, condition and availability shown comes from `data.py`; tests re-read the rendered HTML and compare | Typography, colours, layout, the logo, the brand name and the marketing copy |
| Internal links, category pages and the three catalogue sort orders (pre-rendered, real URLs such as `/hire/sort/price-asc`) | The illustrations: **original SVG drawings made for this repo, not photographs** (no licensed photo library is available). Each product has two images (a drawing and a facts card built from the data) with alt text |
| Booking calendar pages (8 weeks, per day: units free) | "Today" is fixed at **Mon 2 Nov 2026** so pages are reproducible; a real business would show live dates |
| Hire terms: the rules `quote()` implements (daily/weekly cap, weekend rate, 10 % waiver, delivery fees, deposit not a charge) | Home-page tiles, feature strip, "How hire works", about page |
| Mobile menu (`<details>`, no script) | — |

Not implemented on purpose (so nothing looks functional that is not): **no search box, no cart or checkout, no booking form, no accounts**. The contact page says bookings are by phone or e-mail and that nothing can be booked.

## Source of truth and grading
`src/agent_readiness/sites/ironbark/data.py` is the single source; `catalogue.json` is its committed export (a test fails if they differ). `grading.py` computes expected answers from the same data — e.g. the cheapest item that can cut 100 mm deep, which items are available for a whole weekend, a full cost with waiver and delivery, which accessories fit a machine — and `tests/test_sites_ironbark.py` re-derives each answer from the *rendered pages* to prove a visitor can reach it. `readiness site tasks` prints 8 illustrative task shapes. **They are examples, not frozen tasks.**

## Variants and isolation
Four candidate variants add content to the unchanged control (details and designs in the proposal). Each addition carries `data-variant="<flag>"`; the stylesheet, images and all other markup are byte-identical. Tests verify, page by page, that removing a variant's marked elements reproduces the control exactly, that only the intended pages change, and that the combined variant is the union.

| name | flag | adds |
|---|---|---|
| `discoverability` | `discover` | "Browse by job" pages and navigation link, "Also called" and "Good for" on product pages and cards |
| `availability` | `avail` | "Dates at a glance" on product pages (booked periods, next free weekend) and "Next free" on cards |
| `cost` | `cost` | "Your hire cost" table on product pages (hire, waiver, delivery totals for 1–3 days, weekend, week) |
| `compatibility` | `compat` | "Works with" on product pages and "Fits these hire items" on accessory pages, with kit links |

Combine with `+`, e.g. `--variant cost+availability`.

## Quality checks run
* 36 offline tests (data, crawl, truth, determinism, isolation, server, grading).
* axe-core 4 (WCAG 2 A/AA + best practice) in headless Chromium: **0 violations** on 11 control pages, 13 pages of the all-variants build, and 3 mobile pages; no horizontal scroll at 390 px. (A manual axe run, not a CI check.)
* The first axe/crawl runs found, and the final build fixes: card headings that skipped a level, white-on-orange button contrast, muted-text contrast on tinted backgrounds, and a utility bar outside any landmark.

## Known limits
* Illustrations are drawings; a more convincing demo might later use licensed or self-shot photography.
* Fixed "today"; no live availability; no search; prices are invented.
* The investigation snapshot/mirror crawler has **not** been run on this site. It uses an external stylesheet and SVG images, so a snapshot would need to capture non-HTML assets; that is untested integration work, not part of this change.
* Variant additions are written to be realistic, not to be effective; whether any of them changes agent behaviour is unknown until measured.

## Experiment 2 infrastructure (added later)
`readiness exp2 assess|pool|plan|rules|run|status`: crawl integration, deterministic task generation with independent verification, study plan, cost model and the approval-gated baseline driver. See [collaboration/proposals/EXP2-protocol.md](../collaboration/proposals/EXP2-protocol.md).
Two corrections made by that work: the core drill is now classed courier delivery (22 kg, under the terms page's 25 kg rule), and the pipeline's default crawl limits are replaced by explicit ones for this site (the defaults would drop 31 of 51 assets).
