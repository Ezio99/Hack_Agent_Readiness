# Report 007 (continued) — Task 007 Stage 2, installment 3 (Outdoors scope, 6 runs, ABBAAB)

> **Historical per-installment report, written during the pilot and before the reconciliation.** Where it differs, [Report 007](../007-availability-placement-pilot.md) governs: (a) the `find_elements` loops requested `attributes: ["href"]`; the hrefs reached the harness but not the model-visible history (earlier wording "without the href attribute" was wrong); (b) negative overhead on a failed run is replaced by a verification shortfall (overhead is reported only for successful runs); (c) statements that cost grows super-linearly from history growth are not supported (per-request prompt size is nearly constant); (d) "prose-prefixed / non-compliant" responses are the "compatibility-recovered" category; (e) the fingerprint/archival remarks refer to the pilot-time workflow; (f) the early impression that arm B always follows the minimum-visit path was revised after the Bags and Fern blocks (re-verification occurred in both arms; see Report 007 §6). Figures were re-derived from the run artifacts and agree except where noted in Report 007.


**Date:** 2026-10-28 · **Execution commit:** `969d7d4` (unchanged; tree clean except untracked `uv.lock`; `.env` mode 600) · **Schedule SHA-256:** `a2cf749c809e9a905d445d06b87fdb3411fda30978f01c291c74824a656f5eaa` (verified) · **State/artifacts:** `runs/pilot-task007/` (untracked, Git-ignored; the key was searched for and is absent)

## Authorization and command
User-approved installment of exactly 6 runs (entries 13–18 = Outdoors, seed 1, ABBAAB, verified; entries 01–12 complete, no halt, fingerprint `969d7d4` / code hash `1bc809ec…` unchanged; no code, model, schedule or configuration change). Command: `readiness pilot run --experiment 007 --state-dir runs/pilot-task007 --allow-model-calls --approved-schedule-sha256 a2cf749c… --max-runs 6`. Task: "Find the most expensive Outdoors product that is currently in stock…" — answer Yoga Mat (AR-7556, 3500 cents), rank 3 (Picnic Blanket $48 and Camp Stool $42 are out of stock); predicted minimum detail visits A 1 / B 3.

## 1–3. Results by run (exploratory; 3 runs per arm)
| Entry | Arm | Evaluator | Visits / min / overhead | Requests = steps | Run (s) | Prompt / completion tokens | Calc. cost | Worst-case sent |
|---|---|---|---|---|---|---|---|---|
| 13 | A | PASS | 1 / 1 / **0** | 3 | 27.9 | 28,163 / 1,340 | US$0.0409 | 0.094 |
| 14 | B | PASS | 3 / 3 / **0** | 9 | 34.2 | 85,134 / 2,325 | US$0.1163 | 0.284 |
| 15 | B | PASS | 3 / 3 / **0** | 11 | 34.6 | 106,908 / 3,041 | US$0.1466 | 0.350 |
| 16 | A | PASS | 1 / 1 / **0** | 3 | 17.8 | 28,059 / 1,087 | US$0.0397 | 0.094 |
| 17 | A | PASS | 1 / 1 / **0** | 3 | 17.9 | 28,108 / 1,075 | US$0.0397 | 0.094 |
| 18 | B | PASS | 3 / 3 / **0** | 7 | 21.8 | 65,821 / 2,074 | US$0.0911 | 0.220 |
Installment total: calculated actual **US$0.474** (provider reports no cost); pilot-to-date 18 of 30 runs, **US$1.375** calculated, worst-case sent US$3.303 (pilot cap 15; review halt 4.00); cumulative live spend across all experiments ≈ US$1.60 (calculated), far inside A$30. Per-request latency 1.1–5.0 s.
Arm means (A / B): evaluator 3/3 vs 3/3; detail visits 1.00 vs 3.00 (**B − A = +2.0**, predicted +2); requests 3.0 vs 9.0 (+6.0; minimal-path prediction +4); calculated cost US$0.040 vs US$0.118 (×2.9, +US$0.078; B range 0.091–0.147, A range 0.040–0.041); run time 21.2 s vs 30.2 s.

## 4. Paths, re-verification, loops, guesses, tool errors
- **No guesses, wrong or unverified answers; no non-target page in arm A.** Every B run checked both higher-priced candidates (2 of 2) in descending price order and stopped at the answer; overhead 0 in 6 of 6 runs.
- **Arm A (3/3 overhead 0):** read availability on the listing, opened Yoga Mat once; runs 16–17 went back and answered (minimal, 3 requests); run 13 navigated to the root listing "to verify exhaustively" before answering (no second detail visit). Unlike Home and Kitchen, **no A run reopened the product page** (no re-verification at the detail level).
- **Arm B:** run 14 used the category filter (after a `dropdown_options` call) then the three pages (9 requests); run 18 walked the unfiltered listing directly, the cleanest path (7 requests); **run 15 had a tool loop**: five consecutive `find_elements` calls without the needed `href` attribute before the agent noticed ("break loop") and clicked, then went through all three pages (11 requests, the most expensive run). The same tool-misuse pattern appeared in Kitchen run 12 (arm A), so it is a recurring model/tool failure (2 of 18 runs, one per arm), not a design effect.
- **Budget awareness:** runs 14 and 15 reached request 9+ and received Browser Use's budget warning; run 15's reasoning shows the model then rushing ("check Yoga Mat quickly due to budget", "must call done now due to budget"). The loop therefore cost both money and deliberation time, and brought a run to within one step of the final-step narrowing (11 of 12 requests).

## 5. Does Outdoors reproduce Home's predicted rank-3 effect? Yes, in direction and size
Home: B − A = +1.33 visits, +4.3 requests, +US$0.055 (×2.1). Outdoors: +2.0 visits, +6.0 requests, +US$0.078 (×2.9). Both rank-3 scopes show B at the oracle minimum of 3 visits against A at 1, at equal accuracy, with B costing 2–3× more. Arm A was cleaner in Outdoors than in Home (overhead 0 in 3 of 3 versus +1 in 2 of 3), so the Outdoors contrast is closer to the predicted +2 visits.

## 6. Home, Kitchen, Outdoors: required navigation vs agent inefficiency
"Required" = the oracle minimum (detail visits A 1, B rank; minimal-path requests A 2, B 2·rank = click, go-back per higher-priced candidate, click, done). "Inefficiency" = everything above that: extra detail visits (overhead), filtering, tool loops, listing re-checks.
| Scope (rank) | Arm | Detail visits (min) | Overhead | Requests (minimal path) | Extra requests | Mean cost | Cost range | Mean run (s) |
|---|---|---|---|---|---|---|---|---|
| Home (3) | A | 1.67 (1) | +0.67 | 3.7 (2) | +1.7 | US$0.048 | 0.039–0.052 | 13.4 |
| Home (3) | B | 3.00 (3) | 0 | 8.0 (6) | +2.0 | US$0.103 | 0.102–0.104 | 25.7 |
| Kitchen (1) | A | 1.67 (1) | +0.67 | 6.7 (2) | +4.7 | US$0.089 | 0.039–0.134 | 32.4 |
| Kitchen (1) | B | 1.00 (1) | 0 | 4.7 (2) | +2.7 | US$0.061 | 0.052–0.066 | 22.7 |
| Outdoors (3) | A | 1.00 (1) | 0 | 3.0 (2) | +1.0 | US$0.040 | 0.040–0.041 | 21.2 |
| Outdoors (3) | B | 3.00 (3) | 0 | 9.0 (6) | +3.0 | US$0.118 | 0.091–0.147 | 30.2 |
Decomposition of B − A requests = required difference (2·(rank − 1)) + difference in extra requests: Home 4.33 = 4 + 0.33; Outdoors 6.0 = 4 + 2.0; Kitchen −2.0 = 0 + (−2.0). So required navigation explains most of the Home and Outdoors gap, and inefficiency (arm-specific tool loops, thoroughness detours, filter steps) explains the rest and the whole Kitchen discrepancy. Extra requests per run are 1–5 in both arms (mean A 2.5, B 2.6): agent inefficiency is large but roughly arm-neutral on average and very variable run to run, whereas the required-navigation difference is deterministic and scales with rank. Across three scopes the B − A cost difference orders as predicted (Kitchen −US$0.028 ≲ 0, Home +US$0.055, Outdoors +US$0.078) but Kitchen's wrong sign and arm A's wide ranges keep this exploratory; Bags (rank 2) and Fern (rank 3 of 8) are still to run. Re-verification at the detail level: arm A +1 in 4 of 9 runs, arm B 0 of 9; no run in either arm had fewer pages than required.

## 7. Protocol, recovery and guard events
Raw-protocol non-compliant (prose before the JSON): 26 of 36 responses (A 6 of 9, B 20 of 27); **all recovered and schema-valid, 0 rejected**; all six first steps prefixed. Pilot-to-date: 77 of 105 responses prefixed, 77 recovered, 0 rejected (first steps 27 of 27 across Tasks 005–007). Guard: no violations, no schema narrowing, no cost-cap blocks, no `model_output_error`, no infrastructure failure; the step-aware budget-warning rule passed live again (runs 14 and 15: warnings at requests 9 and 9–11); no run reached the final step (maximum 11 of 12 requests); per-run worst-case estimates 0.094–0.350 against the 0.48 cap, every request below US$0.04.

## 8. Driver state and fingerprint
Entries 01–18 `done`; entries 19–30 (Bags, Fern) `pending`; **no halt**; 18 run_started/run_finished pairs; no repeats or skips; fingerprint unchanged (`969d7d4`, code hash `1bc809ec…`, Chrome/145.0.7632.6, `muse-spark-1.3`). Remaining installments need separate approval. Documentation for installments 1–3 is archived outside the repository so HEAD stays pinned at `969d7d4`; commit it only after the full pilot.
