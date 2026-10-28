# Report 007 (continued) — Task 007 Stage 2, installment 4 (Bags scope, 6 runs, BAABBA)

> **Historical per-installment report, written during the pilot and before the reconciliation.** Where it differs, [Report 007](../007-availability-placement-pilot.md) governs: (a) the `find_elements` loops requested `attributes: ["href"]`; the hrefs reached the harness but not the model-visible history (earlier wording "without the href attribute" was wrong); (b) negative overhead on a failed run is replaced by a verification shortfall (overhead is reported only for successful runs); (c) statements that cost grows super-linearly from history growth are not supported (per-request prompt size is nearly constant); (d) "prose-prefixed / non-compliant" responses are the "compatibility-recovered" category; (e) the fingerprint/archival remarks refer to the pilot-time workflow; (f) the early impression that arm B always follows the minimum-visit path was revised after the Bags and Fern blocks (re-verification occurred in both arms; see Report 007 §6). Figures were re-derived from the run artifacts and agree except where noted in Report 007.


**Date:** 2026-10-28 · **Execution commit:** `969d7d4` (unchanged; tree clean except untracked `uv.lock`; `.env` mode 600) · **Schedule SHA-256:** `a2cf749c809e9a905d445d06b87fdb3411fda30978f01c291c74824a656f5eaa` (verified) · **State/artifacts:** `runs/pilot-task007/` (untracked, Git-ignored; the key was searched for and is absent)

## Authorization and command
User-approved installment of exactly 6 runs (entries 19–24 = Bags, seed 3, BAABBA, verified; entries 01–18 complete, no halt, fingerprint `969d7d4` / code hash `1bc809ec…` unchanged; no code, model, schedule or configuration change). Command: `readiness pilot run --experiment 007 --state-dir runs/pilot-task007 --allow-model-calls --approved-schedule-sha256 a2cf749c… --max-runs 6`. Task: "Find the most expensive Bags product that is currently in stock…" — answer Trail Daypack (AR-7301, 3900 cents), rank 2 (Weekend Duffel $69 is out of stock); predicted minimum detail visits A 1 / B 2.

## 1–3. Results by run (exploratory; 3 runs per arm)
| Entry | Arm | Evaluator | Visits / min / overhead | Requests = steps | Run (s) | Prompt / completion tokens | Calc. cost | Worst-case sent |
|---|---|---|---|---|---|---|---|---|
| 19 | B | PASS | 3 / 2 / **+1** | 7 | 43.6 | 66,087 / 2,553 | US$0.0935 | 0.220 |
| 20 | A | PASS | 1 / 1 / **0** | 3 | 20.2 | 28,129 / 1,140 | US$0.0400 | 0.094 |
| 21 | A | PASS | 1 / 1 / **0** | 3 | 17.7 | 28,124 / 1,101 | US$0.0398 | 0.094 |
| 22 | B | PASS | 2 / 2 / **0** | 5 | 24.0 | 46,772 / 1,515 | US$0.0649 | 0.157 |
| 23 | B | PASS | 3 / 2 / **+1** | 7 | 23.0 | 65,807 / 2,556 | US$0.0931 | 0.220 |
| 24 | A | PASS | 2 / 1 / **+1** | 4 | 11.3 | 37,099 / 1,050 | US$0.0508 | 0.125 |
Installment total: calculated actual **US$0.382** (provider reports no cost); pilot-to-date 24 of 30 runs, **US$1.757** calculated, worst-case sent US$4.212 (pilot cap 15; review halt 4.00 calculated); cumulative live spend across all experiments ≈ US$1.98 (calculated), well inside A$30. Per-request latency 1.3–3.4 s with one 11.0 s outlier (run 22).
Arm means (A / B): evaluator 3/3 vs 3/3; detail visits 1.33 vs 2.67 (**B − A = +1.33**; predicted +1); requests 3.33 vs 6.33 (+3.0; minimal-path prediction +2); calculated cost US$0.044 vs US$0.084 (×1.9, +US$0.040); run time 16.4 s vs 30.2 s.

## 4. Paths, re-verification, loops, guesses and tool errors
- **No guesses, wrong or unverified answers.** All six identified Trail Daypack. Every B run checked the one higher-priced candidate (Weekend Duffel, out of stock) before the answer (higher-priced checked 1 of 1), in descending order, with no lower-priced page opened.
- **Arm B re-verification (new):** runs 19 and 23 each **reopened the Trail Daypack page** after returning to the listing (overhead +1); run 22 was minimal (2 visits, 5 requests). Run 19's reasoning was explicitly rigorous: it needed an "exhaustive check that no Bags priced > $39 and < $69 is in stock", re-enumerated the listing, and again before answering ("to be rigorous before done, I should re-enumerate catalog"). Run 23 likewise confirmed "the complete Bags list" and reopened the page for the ID. This is the first appearance of detail-level re-verification in arm B.
- **Arm A:** runs 20–21 were minimal (1 visit, 3 requests); run 24 reopened Trail Daypack after navigating to the listing (+1).
- **Loops and tool errors:** no loop. One stray `find_elements` call (run 23, step 1) recovered immediately; the five- and six-call `find_elements` loops seen in Kitchen run 12 and Outdoors run 15 did not recur. Runs 19 and 20 used `navigate` to the root URL instead of `go_back`; harmless.

## 5. Does Bags show the predicted intermediate rank-2 effect? Yes, in ordering
B − A: +1.33 visits, +3.0 requests, +US$0.040 (×1.9) — between Kitchen (rank 1: −0.67 visits, −2.0 requests, −US$0.028) and the rank-3 scopes Home (+1.33, +4.3, +US$0.055) and Outdoors (+2.0, +6.0, +US$0.078). The cost contrast orders strictly by rank (Kitchen < Bags < Home < Outdoors). Visits do not separate Bags from Home (both +1.33) because Bags B had two +1 overhead revisits while Home B had none; with three runs per cell this is within noise. Accuracy was equal.

## 6. Kitchen, Bags, Home, Outdoors: required navigation vs agent inefficiency
"Required" = oracle minimum (A 1 visit; B rank visits; minimal-path requests A 2, B 2·rank). "Inefficiency" = everything above it (extra detail visits, filter steps, tool loops, listing re-checks).
| Scope (rank) | Arm | Visits (min) | Overhead | Requests (minimal) | Extra requests | Mean cost | Cost range | Mean run (s) |
|---|---|---|---|---|---|---|---|---|
| Kitchen (1) | A | 1.67 (1) | +0.67 | 6.7 (2) | +4.7 | US$0.089 | 0.039–0.134 | 32.4 |
| Kitchen (1) | B | 1.00 (1) | 0 | 4.7 (2) | +2.7 | US$0.061 | 0.052–0.066 | 22.7 |
| Bags (2) | A | 1.33 (1) | +0.33 | 3.3 (2) | +1.3 | US$0.044 | 0.040–0.051 | 16.4 |
| Bags (2) | B | 2.67 (2) | +0.67 | 6.3 (4) | +2.3 | US$0.084 | 0.065–0.093 | 30.2 |
| Home (3) | A | 1.67 (1) | +0.67 | 3.7 (2) | +1.7 | US$0.048 | 0.039–0.052 | 13.4 |
| Home (3) | B | 3.00 (3) | 0 | 8.0 (6) | +2.0 | US$0.103 | 0.102–0.104 | 25.7 |
| Outdoors (3) | A | 1.00 (1) | 0 | 3.0 (2) | +1.0 | US$0.040 | 0.040–0.041 | 21.2 |
| Outdoors (3) | B | 3.00 (3) | 0 | 9.0 (6) | +3.0 | US$0.118 | 0.091–0.147 | 30.2 |
B − A requests = required difference 2·(rank − 1) + difference in extra requests: Kitchen −2.0 = 0 + (−2.0); **Bags 3.0 = 2 + 1.0**; Home 4.33 = 4 + 0.33; Outdoors 6.0 = 4 + 2.0. Required navigation (the deterministic part: 0, 2, 4, 4 requests) explains most of the B − A gap for ranks ≥ 2; the inefficiency difference is −2.0 to +2.0 and carries the sign errors (Kitchen). Inefficiency is substantial in both arms (extra requests per run: A 2.2, B 2.5 averaged over all scopes). **Secondary finding, revised:** unnecessary detail-level revisits occurred in arm A in 5 of 12 runs (Home 2, Kitchen 2, Bags 1) and, newly, in arm B in 2 of 12 (both Bags). So the earlier impression that arm B always follows the minimum-visit path no longer holds; B re-verified when its reasoning called for an "exhaustive" check, A when it wanted to "be thorough" or to confirm the product ID. Re-verification is better described as an agent-level tendency than an arm-specific one, with a higher rate in A (rate difference 3 runs of 12, n too small to call). No run in either arm used fewer pages than required (no unverified answers in 24 runs).

## 7. Protocol, recovery and guard events
Raw-protocol non-compliant (prose before the JSON): 20 of 29 responses in this block (A 7 of 10, B 13 of 19); **all recovered and schema-valid, 0 rejected**; all six first steps prefixed. Pilot-to-date: 97 of 134 responses prefixed, 97 recovered, 0 rejected (first steps 33 of 33 across Tasks 005–007). Guard: no violations, no schema narrowing, no cost-cap blocks, no `model_output_error`, no infrastructure failure; no budget warnings or final-step events (maximum 7 of 12 requests); per-run worst-case estimates 0.094–0.220 against the 0.48 cap, every request below US$0.04.

## 8. Driver state, spend and fingerprint
Entries 01–24 `done`; entries 25–30 (Fern: A1, B1, B2, A2, A3, B3 in ABBAAB order) `pending`; **no halt**; 24 run_started/run_finished pairs; no repeats or skips; fingerprint unchanged (`969d7d4`, code hash `1bc809ec…`, Chrome/145.0.7632.6, `muse-spark-1.3`). Pilot-to-date calculated spend US$1.757 (review halt US$4.00), worst-case sent US$4.212 (cap US$15). Remaining installments need separate approval. Documentation for installments 1–4 is archived outside the repository so HEAD stays pinned at `969d7d4`; commit it only after the full pilot.
