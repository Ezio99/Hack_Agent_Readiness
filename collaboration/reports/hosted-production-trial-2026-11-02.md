# Paid production end-to-end trial: `eval-aa23e330` (2026-11-02)

**What was authorized:** the owner explicitly approved exactly one paired repetition, with US$1.65 reserved, on https://209-38-84-72.sslip.io. The owner started it from the workspace UI with the operator token. The verification session ran read-only checks over SSH and through public endpoints.

## Pre-trial checks (all passed)

| Check | Result |
|---|---|
| Deployed revision | VM checkout `b3121a8` (`product-experience-redesign`). Image `redesign-b3121a8` = `8e0e2378`. Container healthy, 0 restarts. Rollback image `rollback-60fcbc6` present. |
| Served frontend | `index.html`, entry and lazy chunks byte-identical to a fresh local build of `b3121a8` |
| Config | `.env`: mode live, access operator, ceiling 10. Secrets mode 400, owned by uid 10001. |
| Service log | `mode=live access=operator evaluations=enabled jail=verified` |
| Jail self-test (in container) | `ok, mirror_reachable, escapes_blocked, filesystem_hidden` |
| Provider | `GET https://api.meta.ai/v1/models` returned 200 and listed `muse-spark-1.3` (no inference call) |
| Admission ledger | policy ceiling US$10.00, US$1.65 per repetition, 120 s interval. One completed job, US$1.65 reserved. |
| Concurrency | worker idle, no active job |
| Operator authorization (live) | valid body with no token, a random token or a malformed header: 403 each. PUT/DELETE/PATCH: 405. No job created, no reservation. Enforced server-side by `hmac.compare_digest` before admission (`hosted/api.py`). |
| Secret hygiene | operator token and provider key: 0 matches across all 333 commits on 125 refs (including `origin/*`), tracked files, the built frontend, VM app and Caddy logs, and the container environment |

## Result

`eval-aa23e33012717c4a30ca21be1239e85f`: completed 8/8 in 9 min 01 s. Evidence origin `real_model`, model `muse-spark-1.3`, profile `suite-v2-compat2`. The `post_trials` manifest `99f493d1…` is the same approved hash as S1.

| Task | Original | Modified |
|---|---|---|
| 1 highest deposit | not passed (13 req) | not passed (6 req), **see grading finding** |
| 2 deposit < $200 | not passed: 2 of 4 machines found (13 req) | pass (8 req) |
| 3 delivery required | not passed: incomplete list (13 req) | pass |
| 4 minimum hire 2 days | not passed: wrong single item (13 req) | pass |
| **Total** | **0/4, 52 requests** | **3/4, 26 requests** |

Frozen rule `paired-signflip-v1`: **inconclusive**. Exploratory listing rule: **consistent_with_h1**. The previous evaluation `eval-9aaac35c` gave Original 1/4 (50 req) and Modified 4/4 (26 req).

## Production workflow verified

- Operator start, admission and reservation (remaining repetitions 5 → 4).
- Live progress through `/config`, `/jobs/{id}` and `/live`.
- Per-step timeline with goal, memory and actions; real jailed-browser screenshots served (PNG).
- Independent grading; results persisted.
- Insights generated (for example, detail-page dependency of 2.0 vs 0.0 detail views).
- Public export (41.8 KB): no absolute paths, credential words, IPs or internal run IDs.
- History lists both evaluations. The duration estimate updated to 550 s, measured over 2 samples.
- Refresh recovery on desktop and mobile, both mid-run and after completion: the URL, state and results are restored.
- Throughout: no console errors, no failed requests, and no non-GET requests from the browser.

## Spend reconciliation (calculated at published prices; not a bill)

Fork ledger `paired-86a64616…/spend/ledger.jsonl`:
- 141 reservations, all 141 settled, 0 open, 0 settled above their reservation.
- 78 new items, matching the 52 + 26 model requests.
- **New spend US$1.126097**: placebo (Original) 0.766724 + patched (Modified) 0.359373.
- The remaining 63 items are imported source history of US$0.864825.

Hosted admission now holds two completed jobs: US$3.30 of US$10 reserved, 4 repetitions remaining. Reservations are never released.

The programme ledger (`collaboration/budget/programme-ledger.json`) has **not** been changed. Appending this trial is an owner action. With this trial, the known-spend subtotal would become US$10.566163 (A$15.85 at 1.50).

## Findings

1. **Grading false negative from answer length (validity, high).** Frozen tasks are graded through `investigate/taskgen/freeze.py`, which calls `criteria.grade` and then `answer_match`. That function accepts the truth only as an exact match, or within an answer at most `len(truth) + 16` characters long. All four task-1 answers across both evaluations name the same machine (Electric scissor lift 6 m). Only the bare name passed (`9aaac35c` Modified). The answers that added "$600 refundable deposit" failed, including this run's Modified task 1 ("…with a refundable deposit of $600"). So part of any task-1 difference reflects answer verbosity, not navigation. The rule is frozen for these experiments; changing it is an owner decision on experiment design. Generated tasks (Phase 3) need a rule that tolerates supporting detail consistent with the truth.
2. **Original-arm cap margin (reliability, medium).** The placebo arm spent US$0.766724 against its US$0.80 cap. Each request reserves about US$0.036, so the arm was about one request from refusal. A repetition in which all four Original tasks reach the 14-request limit (56 requests, about US$0.83) would likely be halted mid-trial. Caps and reservations are unchanged (they are spending limits); this needs an owner decision before any public opening.
3. **Export reports a stale ceiling (correctness, low).** The public export shows `ceiling_usd 2.0, remaining 0.009078`. `investigate/export.py` reads `total_cap_usd` from the fork's `run.json`, which was copied from the source run. The enforced ledger ceiling is the approved `post_trials` value of US$2.50 (`flow.py` uses the stage options), so the real remaining headroom was US$0.509.
4. **Operator UX (low).** "Run evaluation" stays disabled until a token is entered, but the token field is in a collapsed "Operator access" section below the button. The owner initially found the button greyed out.

No regression from the redesign was found: every non-grading outcome reproduces the previous evaluation's pattern.
