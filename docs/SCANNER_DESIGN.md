# Protected scanner — design, threat model and API (Task 011)

Status: implemented locally and credential-free. **No live inference has ever been run through it, no scanner is deployed, nothing here authorizes spending.**

## What it does
An invited developer selects a *registered* task and *registered* storefront variant, runs a bounded browser-agent scan, and reads: independent verdict, what the agent loaded/did, effort (requests, page views, time), calculated cost, and evidence-linked findings with unvalidated recommendations. Two scans of the same task can be compared (controlled when exactly one factor differs).

Pipeline: API → `ScanManager` (one slot) → `execute_scan` → loopback environment server (ephemeral port, registered variant only) → Browser Use agent with the existing fidelity guard/step-aware schema narrowing/request gate, profile `suite-v1-compat1` (12 steps / 12 requests / 240 s) → recorder → independent evaluator (`suite.core.evaluate`) → `scanner.diagnostics`.

## Providers (never conflated)
- **mock** (default; the only mode ever executed): the real agent, browser, environment, guard and evaluator run, but the model's decisions come from `scanner/mock.py` behaviours (`correct, lazy, wrong, loop, stuck, escape, provider_error`). Results are labelled MOCK everywhere (API `mock`, `inference_label`, UI banner, cost basis). They validate the pipeline and diagnostics, not any model.
- **live**: refused unless `SCANNER_LIVE_ENABLED=1`, `SCANNER_LIVE_BUDGET_USD>0` and `META_MODEL_API_KEY` are all set. Not exercised by tests/CI.

## Evidence (answers "visiting ≠ seeing")
Evidence requirements now include `observed_text` facts checked against the DOM text the agent actually received per step (e.g. the RAM figure on a product page), not just URLs. `correct` + missing evidence is reported as "correct but required information was not shown to the agent". Limit: text in the DOM text sent to the model is the proxy for "shown"; the model may still ignore it.

## Failure attribution (`scanner/diagnostics.py`)
Categories: `task_outcome, website, agent_reasoning, agent_tool_interface, infrastructure, security, undetermined`; confidence `observed | inferred | hypothesis`. Rules: (1) tool output carrying links that the next model request did not contain (history showed only a count) ⇒ `agent_tool_interface`, observed; (2) identical action ≥3× in a row ⇒ `agent_reasoning`, inferred; (3) wrong answer with all required facts shown ⇒ `agent_reasoning`, inferred; (4) required facts never shown ⇒ `undetermined` (navigation vs discoverability cannot be separated by one run); (5) limit/provider/guard stops ⇒ `infrastructure`, never the website; (6) stock-on-detail-only variant ⇒ website observation + a *hypothesis* with a controlled rescan (`availability: detail→listing`). Recommendations are always `hypothesis_unvalidated`.

## Threat model and controls
| Threat | Control |
|---|---|
| Unauthorized use / cost | Operator-issued invitation codes (`readiness scanner invite`), HMAC-SHA256 hashed at rest, expiry, redemption cap (atomic), failed-attempt lockout, short-lived sessions (default 30 min) with per-session scan quota; no master code in the frontend |
| Reading others' results | Every scan read/compare checks invitation ownership; unknown and foreign ids both return 404 |
| SSRF / arbitrary browsing | API accepts only `task_id`, `variant_id`, `mode`, `mock_behavior` (extra fields rejected 422). Target is a loopback server started by the harness; the browser `allowed_domains` is that single origin (tested: off-origin navigation is blocked and reported) |
| Prompt injection via user input | No user-supplied prompt/instruction field exists |
| Runaway execution | 12 steps, 12 model requests, 240 s wall clock, per-request and cumulative estimated-cost ceilings (existing guard), one concurrent scan (atomic), no automatic retry; restart marks active scans `interrupted` and never reruns |
| Budget | Live budget reserved atomically in an append-only ledger before a scan; failed live scans keep their full reservation; default budget 0 (disabled). Estimates ≠ billed spend |
| Abuse | Kill switch (file + admin endpoint `X-Admin-Token`, constant-time compare; cancels running), per-client rate limit, body-size limit, CORS exact-origin allowlist (none by default), `Cache-Control: no-store` |
| Data leakage | Whitelist projections (`views.py`): no oracle/truth, raw model text, traces, paths, headers or keys; results/ledger/DB live in the Git-ignored `scanner-data/` |

Known limits: single process/host, SQLite, in-memory rate limiter (resets on restart; not shared), client address is the socket peer (a proxy needs trusted-header handling before deployment), no TLS (terminate at a proxy), mock behaviour selection is allowed for demos (`allow_mock_behaviors`). A future deployment requires a separate security review.

## API
`GET /api/health` · `GET /api/registry` · `POST /api/session {code}` → `{token,…}` · `GET /api/session` · `POST /api/scans {task_id,variant_id,mode,mock_behavior?}` (+`Idempotency-Key`) → 202 `{scan_id,status}` · `GET /api/scans` · `GET /api/scans/{id}` · `GET /api/compare?baseline=&rescan=` · `POST /api/admin/kill {enabled}`.
Scan states: `queued → running → complete | error | cancelled | interrupted`. Refusals: 401 auth, 402 budget, 403 live disabled/admin, 404 not yours, 409 scan in progress/not complete, 413 body, 422 invalid target, 429 quota/rate/lockout, 503 killed.

## Local use
```
readiness scanner invite --label me      # prints a one-time code
readiness scanner serve                  # http://127.0.0.1:8100
cd dashboard && VITE_SCANNER_API_URL=http://127.0.0.1:8100 npm run dev   # Protected scanner tab
```
Env: `SCANNER_DATA_DIR`, `SCANNER_SECRET` (set one in any shared deployment; a local `.dev-secret` is generated otherwise), `SCANNER_ADMIN_TOKEN`, `SCANNER_CORS_ORIGINS`, `SCANNER_LIVE_ENABLED`, `SCANNER_LIVE_BUDGET_USD`.
The public GitHub Pages build has no API URL and says so; no scanner is deployed.

## Hosting options (none approved)
1. Local only (current). 2. Single small VM/container with Chromium (≈2 GB RAM) behind a TLS proxy, within the US$10/month planning allowance *only if separately approved*. Needs: trusted-proxy client IPs, persistent volume for `scanner-data/`, secrets via environment, Meta-terms confirmation before any live use.

## Proposed live validation plan (NOT approved; for separate approval)
Purpose: learn whether real Muse Spark can attempt the four P0 task types at all (Task 010 used scripted navigators only).
- Tasks: one fixture per template — `t1-anc-headphones-under-250-all`, `t2-compare-air14-vs-probook15`, `t3-cheapest-monitor-27in-usbc-120hz`, `t4-policy-delivery-tessera-whisper`; variant `availability-listing+specs-structured` only (default).
- Runs: 4 (one each), sequential, no retries. Limits 12 steps / 12 requests / 240 s.
- Estimated maximum: 12 requests × US$0.04 ceiling = **US$0.48 per run, US$1.92 for all four** (observed mock-sized requests ≈ US$0.013 each, so expected ≈ US$0.2–0.5 total). Estimates only; the provider reports no cost.
- Preconditions: explicit approval of this plan; the pinned `suite-v1-compat1` schema hashes are probe-verified against the live API first with a ≤1-request, ≤US$0.04 check (also needs approval); budget set to 2.00; results stay private.
- Success of the validation = documented behaviour (including failures); not a performance claim. One run per task cannot support effect estimates.
