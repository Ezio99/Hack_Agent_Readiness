# Report 011b — Approved live Muse Spark validation of the four P0 task types

Date 2026-10-28. Branch `task011-live-validation` (driver `src/agent_readiness/scanner/live.py`; guards tested with stubs in `tests/test_scanner_live_guards.py`, live code path exercised against a local fake provider in `tests/test_scanner_live_path.py`). Private artifacts (traces, results, ledger) are in Git-ignored `runs/live-validation-011/`; nothing was published.

## Setup (as approved)
Model `muse-spark-1.3` @ `https://api.meta.ai/v1`, profile `suite-v1-compat1` (reasoning low, 4,096 completion cap, parser `muse-prose-prefix-json-v1`), default variant `availability-listing+specs-structured`, 12 steps / 12 requests / 240 s, one run per task, sequential, no retries, fixed order. Prices re-verified on the official page (input $1.25, output $4.25 per M; no separate reasoning price) — calculated cost only, the provider reports none. Ledger ceiling US$2.00 including the probe, reservation before each request.

## Schema probe
1 request, HTTP 200, strict `json_schema` with the real T1 full AgentOutput wire schema (7,954 B) accepted; valid single `done` action with the exact data; 62 prompt + 699 completion tokens (617 reasoning) = **US$0.0030** (cap 0.04).

## Results (independent evaluator; each run completed with `agent_done`)
| Task | PASS | Evidence-backed | Requests | Steps | Pages loaded (reference path) | Time | Tokens in/out | Calc. cost |
|---|---|---|---|---|---|---|---|---|
| T1 headphone discovery | PASS | yes | 9 | 10 | 9 (6) | 34.3 s | 87,901 / 2,021 | US$0.1185 |
| T2 laptop comparison | PASS | yes | 5 | 6 | 5 (4) | 22.7 s | 48,338 / 1,737 | US$0.0678 |
| T3 monitor selection | PASS | yes | 5 | 6 | 5 (3) | 14.8 s | 48,420 / 1,272 | US$0.0659 |
| T4 returns + delivery | PASS | yes | 7 | 8 | 7 (3) | 36.4 s | 67,093 / 2,011 | US$0.0924 |
Total calculated: probe + 4 runs = **US$0.348** of the US$2.00 ceiling (not a bill). Answers exactly matched the oracle in every field (no partial-accuracy cases). No run hit any limit; no fidelity violations, no cost-limit blocks, no final-step schema narrowing, no infrastructure errors, no retries, no interrupted attempts.

## Navigation (from the private traces; page loads, not proof of reading)
- T1: used the ANC / max-price / in-stock filters, then opened three candidate product pages (go_back between them) — verification beyond what the filtered listing needed; the in-stock filter was available in this (listing) variant.
- T2: opened Kestrel Air 14 directly from home, searched for Nordwave ProBook 15, read its page.
- T3: set the screen/refresh/USB-C controls via dropdowns and checkboxes, opened the winning product page.
- T4: product page → delivery policy → returns policy → navigated to delivery and returns **again** before answering (repeat reads of pages already loaded).
Diagnostics found no tool-visibility gap and no repeated-action loop in any run.

## Protocol / integration findings
- **Raw strict-JSON compliance was 1 of 26 model responses** (the first response in every run); the other 25 needed the opt-in `muse-prose-prefix-json-v1` recovery, all 25 recovered to valid actions, 0 rejected. This is the known Muse Spark prose-prefix behaviour (Tasks 004–007) — the integration works only because of the compatibility parser, and the result must be reported as "compat-parser", not "strict".
- Schema acceptance, hosted structured output, evidence capture (observed-text), cost ceilings and the fidelity guard all behaved as designed. Evidence capture reported every required fact as shown in all four runs.
- Cost per run was ~14–25% of the US$0.48 reservation; later requests carried ~9–10k input tokens each.

## Attribution
All four are PASS, so there is no failure to attribute. Extra page visits (T1 verification, T4 repeats) look like agent verification behaviour; this study cannot say whether any site design would have changed them. No website defect is indicated or claimed.

## Limits of this validation
4 runs, one per task, one variant, one model configuration, a synthetic storefront and scripted-equivalent task fixtures: it shows Muse Spark **can** complete all four task types end to end through this harness (4/4 here), not how reliably (no variance estimate), and nothing about variant effects or the value of any recommendation. Task 012 needs a separate experimental plan.
