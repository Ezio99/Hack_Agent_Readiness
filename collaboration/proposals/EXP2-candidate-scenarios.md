# EXP-2 candidate scenarios on the Ironbark Hire Co. site (PROPOSAL; nothing run, nothing claimed)

Site: [docs/IRONBARK_STOREFRONT.md](../../docs/IRONBARK_STOREFRONT.md). Prepared offline. No model call, no trial, no investigator run, no frozen artifact, ledger or EXP-B file touched.

## 0. Read this first
* These are **candidate scenarios for future controlled experiments**, not findings. **We do not know that any agent has trouble with the control site.** Nothing here says the investigator discovered anything; the control pages were written to be ordinary, answerable, realistic pages, not to make an agent fail.
* A scenario can only be *promoted* to an experiment after a baseline run shows an effort or correctness problem on the control that matches its mechanism (the same discipline as EXP-B: an unpromoted pattern is an observation, an owner-selected change is exploratory).
* Each variant is **additive**: it adds information or navigation that the control lacks but never removes or contradicts control content. The control already contains the answer to every candidate task somewhere on the site (verified by tests), so a task failure on the control is a navigation/effort question, not an impossible task.
* Lessons carried from EXP-B that shape this design: n = 1 per cell was too thin; the frozen pairing rule could not return "improvement" with only two affected tasks; a control task flipped outcome. So each scenario below should have **at least five affected tasks**, **K ≥ 3 repeats per task and arm**, a contemporaneous unmodified repeat, and negative controls fixed in advance.

## 1. How to build an otherwise identical control
`readiness site serve --variant control` vs `--variant <name>` (or `readiness site build`). Both come from one build function; the control has no flags. Isolation is tested: stripping a variant's `data-variant` elements from every page reproduces the control byte-for-byte after normalisation; stylesheet and images are identical; only the intended pages differ (cost: the 16 product pages; availability: products and the pages that list them; compatibility: products and accessories; discoverability: every page's navigation, plus new `/jobs` pages). `readiness site variants` prints a build fingerprint per variant, to be recorded in any future manifest.

## 2. The scenarios

### A. Discoverability: customer language versus trade names — variant `discoverability`
* **User tasks affected:** "I want to break up an old concrete path", "I need something to cut ceramic/porcelain tiles", "hire a jackhammer / cement mixer / whacker packer / scaffolding". Natural-language recommendation tasks where the customer's words differ from the catalogue's formal names.
* **Barrier:** the control names items formally ("Electric demolition hammer 15 kg", "Petrol cut-off saw 350 mm", "Reversible plate compactor") and describes jobs in trade terms. There is no site search and no browse-by-job route; the customer must map their words to the right category and read descriptions.
* **Exact change:** a "Browse by job" nav link and `/jobs` + 10 job pages listing suitable items; "Also called: …" (e.g. jackhammer, concrete saw, wacker) on every card and product page; "Good for" links on product pages; a "What are you working on?" tile row on the home page.
* **Expected behaviour (hypothesis only):** fewer page views and fewer wrong recommendations on job-phrased tasks; no effect on tasks stated with the exact product name.
* **Independent grading:** exact set of acceptable product IDs per task (`grading.py` examples `ex-07`, `ex-08`), computed from descriptions and availability that the control already shows.
* **Confounders / negative controls:** the extra nav link and extra text change every page (note this in the manifest); the new job pages create new routes the agent may wander into, so count page views by type. Negative controls: tasks that name the product exactly ("Hire the 250 mm wet tile saw") and spec lookups, which should not benefit.

### B. Information accessibility: dated availability — variant `availability`
* **User tasks affected:** "Which items can I hire for the weekend of 6–9 Nov?", "When is the cut-off saw next free?", "Is the scissor lift free on 17 Nov for two days?".
* **Barrier:** in the control each product shows only "available/fully booked **today**" and links to a separate per-product calendar page (an eight-week table). Answering a multi-item date question means opening up to 16 calendar pages and reading dozens of cells.
* **Exact change:** "Dates at a glance" on each product page (fully booked periods; next free Fri–Mon weekend) and "Next free: <date>" / "Next booked day: <date>" on every product card. The calendar pages are unchanged.
* **Expected behaviour (hypothesis only):** fewer page views on cross-product date questions; little or no effect on single-item date lookups that the calendar already answers.
* **Independent grading:** `available_for(product, start, end)` over the committed bookings (rule: at least one unit free on every day), exact set or date answers (`ex-02`). The "dates at a glance" text is derived from the same function (tested), so the two arms cannot disagree.
* **Confounders / negative controls:** the fixed "today" date; items with several units make "free count" ambiguous for a reader (the calendar page states the rule). Negative controls: cost and spec tasks; a single-item "is it free on date X" task which both arms answer from one calendar page.

### C. Decision support: transparent total cost and rental constraints — variant `cost`
* **User tasks affected:** "What is the total to hire the tile saw for a weekend with the damage waiver and delivery?", "Cheapest way to have the scaffold tower for 3 days including everything", compare two machines' full cost.
* **Barrier:** in the control the product page states the three rates, deposit and minimum hire, and says waiver, delivery and deposit are "described in the hire terms". The rules (daily-capped-at-weekly, 10 % waiver, delivery $45/$120, delivery required for heavy items, deposit not a charge) are on `/hire-terms`. A total needs data from two pages and arithmetic.
* **Exact change:** a "Your hire cost" table on every product page: hire charge and totals (collected; with waiver; with waiver and delivery, or with required delivery) for 1, 2, 3 days, weekend, 1 week, plus the deposit and minimum-hire note. No rates change.
* **Expected behaviour (hypothesis only):** fewer arithmetic errors and fewer page views on total-cost tasks; none on specification tasks.
* **Independent grading:** `quote()` (numbers in AUD, deposit excluded) — `ex-03`, `ex-04`; tests recompute the answers from the rendered rates and the rules on the terms page.
* **Confounders / negative controls:** rounding of the 10 % waiver (cents appear); required delivery is added automatically for four items (stump grinder, wood chipper, scaffold tower, scissor lift), which a careless task statement could omit; stale arithmetic habits are model-specific. Negative controls: availability and compatibility tasks; a "which is cheaper per day" task that needs no totals.

### D. Compatibility and bundles — variant `compatibility`
* **User tasks affected:** "Which accessories fit the demolition hammer?", "What do I need to buy to cut tiles with the 250 mm saw?", "Is there a kit for masonry drilling and what does it cost?".
* **Barrier:** in the control compatibility exists only as free text on each *accessory* page ("30 mm hex shank. Suits 30 mm hex demolition hammers."). Product pages say nothing about accessories, and kits are listed on a separate page. The reader must search the accessories list and match shank/blade/voltage descriptions.
* **Exact change:** "Works with" on product pages (links to every compatible accessory, universal items marked, and links to kits that include the item) and "Fits these hire items" with product links on accessory pages.
* **Expected behaviour (hypothesis only):** fewer page views on accessory-matching tasks and fewer false matches (e.g. recommending a 250 mm blade for a 350 mm saw).
* **Independent grading:** exact set of accessory IDs per product (`ex-05`), kit rates and consumables (`ex-06`). The matching rule (tag intersection, universal accessories fit all) is in `data.compatible_accessories`; the free-text "Fits" line on each control accessory page is stored with the tags in `data.py` and tested to be shown.
* **Confounders / negative controls:** a "universal" definition ambiguity (the safety pack and 240 V lead fit many items) — grade as a set with the rule stated in the task; kit lookups available in both arms from `/kits`. Negative controls: tasks about items with no specific accessories (e.g. the ladder).

### (E, not implemented) Standardised comparison table
A genuinely distinct fourth friction is that specification labels are not standardised across products (e.g. "Max cutting depth" exists only for saws). A `/compare/<category>` page with identical columns would be inexpensive, but it overlaps with C and A for most tasks and was left out to keep the first set small.

## 3. Task sets and sizing (a proposal)
Each scenario needs at least five affected tasks plus negative controls; the eight shapes in `readiness site tasks` are *illustrations*. Tasks would be generated or authored once, frozen with a partition (investigation vs holdout) **before** any run, and graded by code from `data.py`, never by the agent's own claim. Suggested minimum per scenario: 5 affected + 3 negative-control tasks × K = 3 × {control, variant, contemporaneous unmodified repeat} = 72 trials per scenario — a size and cost that needs its own approval and budget estimate; none is authorised by this document.

## 4. What must be decided before any experiment
1. Whether the first step is a *baseline-only* run on the control (to see whether any friction exists) rather than a patch test.
2. Sample sizes, caps and the pre-registered decision rule (the frozen `paired-signflip-v1` needs ≥ 5 affected tasks to have any power).
3. How the site is captured for the investigation pipeline (the current snapshot flow captured inline-styled HTML; this site uses an external stylesheet and SVG images).
4. Whether to treat the SVG illustrations as part of the evaluated content (they carry text that repeats page facts) or as presentation to be held constant, which this design does (identical in every variant).
