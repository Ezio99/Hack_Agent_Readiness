# Report 006 — Task 006 Stage 2, installment 1 (block 1 of 6: seed 2, ABBA)

**Date:** 2026-10-28 · **Code:** `1f04042` (HEAD = origin; only untracked `uv.lock`; `.env` mode 600) · **Schedule SHA-256:** `bb660b0c0f1f7a6a1215ea2bfff6beda0a2124a95201f8c93c1214254fa3dcf4` (verified before and by the driver) · **State/artifacts:** `runs/pilot-task006/` (untracked, Git-ignored; key searched for and absent)

## Authorization and command
User-approved installment of exactly 4 runs (entries 1–4 = seed 2, pattern ABBA, one complete block). Frozen configuration verified: `natural-shopping-v3-compat1` (profile SHA-256 `67f2615f…ccd3b`), `muse-spark-1.3`, 6 steps / 6 requests / 120 s, per-request estimated ceiling US$0.04, per-run cumulative cap US$0.25, full-schema hash `c80ef8b8…9a194`.
```
readiness pilot run --state-dir runs/pilot-task006 --allow-model-calls --approved-schedule-sha256 bb660b0c… --max-runs 4
```
Task: seed 2 discovery, "Find the Fern product in Bags costing at most $24.00 AUD" (target City Tote, AR-7318, 2400 cents, unavailable).

## 1. Independent evaluator
| Entry | Arm | Evaluator | Status |
|---|---|---|---|
| 01 | A | PASS | completed / agent_done |
| 02 | B | PASS | completed / agent_done |
| 03 | B | PASS | completed / agent_done |
| 04 | A | PASS | completed / agent_done |
All four returned `{AR-7318, 2400, available: false}`. A: 2/2, B: 2/2 (no difference at this size).

## 2. Navigation paths and non-target visits
Identical in all four runs: the unfiltered listing (step 1) → one click on the City Tote link → the target detail page (step 2) → `done`. No search or filter was used, no `go_back`, **0 non-target product pages** in every run, and the first product page was the target each time.

## 3. Actions, latency, tokens, cost, protocol
| Entry | Arm | Proposed actions | Requests | Latency per request (s) | Run (s) | Prompt / completion (reasoning) tokens | Calculated cost | Worst-case sent |
|---|---|---|---|---|---|---|---|---|
| 01 | A | click, done | 2 | 2.67, 2.37 | 17.7 | 18,364 / 542 (182) | US$0.0253 | 0.0622 |
| 02 | B | click, done | 2 | 2.56, 2.13 | 15.2 | 18,398 / 579 (224) | US$0.0255 | 0.0622 |
| 03 | B | click, done | 2 | 3.15, 2.79 | 8.5 | 18,397 / 768 (405) | US$0.0263 | 0.0623 |
| 04 | A | click, done | 2 | 2.21, 3.57 | 8.3 | 18,355 / 1,017 (650) | US$0.0273 | 0.0622 |
Installment total: calculated actual **≈ US$0.104** (calculated at published prices; the provider reports no cost); worst-case estimate of what was allowed onto the network US$0.249. Cumulative live spend across all experiments ≈ US$0.22 (calculated). The prompt is ≈ 34 tokens longer in B (18,397 vs 18,355–18,364), as expected from the extra "View details" text.

## 4. Compatibility recovery and output errors
Every run: request 1 raw-protocol non-compliant (one sentence of prose before the JSON), recovered and schema-valid (`prose_prefix_single_json_object`); request 2 raw-compliant pure JSON. So 4/4 first steps were prose-prefixed (cumulative 9/9 observed first steps), 4/4 second steps compliant (cumulative 5/5 later steps). Recovery attempted 4, recovered-valid 4, rejected 0. No `model_output_error`, fidelity violation, narrowing, cost-cap block or infrastructure failure.

## 5. Driver state and resume
No halt. Entries 1–4 `done`; entries 5–24 `pending`; next scheduled run is entry 05 (seed 9, B1). Run-start audit events: 4; fingerprint (commit, code hash, browser Chrome/145.0.7632.6, profile/configuration hashes, model) unchanged across the four runs. Because no halt exists, `pilot run` could resume at entry 05 without a recorded approval, but **no further run will be started without the user's explicit approval**; completed runs cannot be repeated by the driver.

## 6. Browser Use observations (actual, from the traces)
- A: `[94]<a />` / `City Tote` / `Fern · Bags` / `$24.00` — the link marker precedes the name and facts. B: `City Tote` / `[98]<a />` / `View details` / `Fern · Bags` / `$24.00` — name above, generic link, facts below; 20 "View details" links, no `aria-label`. Element indices shift by +4 in B (`[98]` vs `[94]`). As verified offline; no unexpected differences.
- The agent's stated reasoning is the same in both arms: it picks City Tote from the visible brand/category/price lines ("Fern Bags $24.00 meets criteria") and then clicks its link; in B two runs call it "view details link"/"View details", but nothing indicates confusion.

## Interpretation and limitations
At this stage there is **no observable effect**: 4/4 success, identical 2-step paths, 0 wrong visits. This matches the ceiling-effect concern: the unfiltered listing shows name, brand, category and price next to every link, and the task is solved from those facts, without search or filter, in both arms. Four runs on one seed cannot detect anything but a large effect; token and latency differences (e.g. the reasoning tokens 182–650) are within run-to-run noise (arm A itself ranges 182 to 650). The pilot continues to be informative only if later seeds (multiple candidates under every filter pair) produce more navigation; a persistent ceiling would argue for redesigning the intervention (Stage 3) rather than running all 24 runs.

## Decision (2026-10-28, user)
Task 006 is **stopped after this four-run seed-2 block**; entries 5–24 stay `pending` in `runs/pilot-task006/` and are not to be executed. The result is an **exploratory finding**: with one seed, two runs per arm and a task solvable from adjacent card text, the arms were indistinguishable (a ceiling effect). It is **not evidence that the placement of link-identifying text is irrelevant**. The follow-up design is [Task 007](../tasks/007-availability-information-placement.md).

## Next (superseded by the decision above)
Options: continue the schedule in further installments (next: seed 9 block, entries 5–8), or stop and revisit the design given the ceiling. PR #3 remains unmerged.
