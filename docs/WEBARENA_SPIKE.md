# WebArena Verified shopping — integration spike (feasibility report)

Status: **spike complete (credential-free; no paid model call; the WebArena site itself was NOT started)**. Verdict: **CONDITIONAL GO** (see §7). Evidence labels: **[verified]** = executed here; **[docs]** = official documentation / package source; **[inferred]** = reasoning, to be confirmed against the running site.

## 1. What WebArena Verified (WAV) shopping is [docs]
- Magento 2 storefront ("One Stop Market"), image `am1n3e/webarena-verified-shopping` (optimized): **13.3 GB** (original 117 GB), Docker Hub compressed ≈ **5.4 GB** (amd64) [verified via Docker Hub API]. Ports: site 7770, **env-ctrl 7771** (container 8877). Apache-2.0 package (Python ≥3.11; evaluator is a pure-Python offline library, 3.1 MB wheel).
- Runs **independently of the other sites** (one container per site; `webarena-verified env start --site shopping` or one `docker run -d -p 7770:80 -p 7771:8877 …`). Shopping Admin (7780) is separate and not needed for storefront tasks.
- **Auth/session:** optimized image supports header login `X-M2-Customer-Auto-Login: email:password` (Magento plugin), no UI login needed; harness must send the header on frontend requests (Playwright `extra_http_headers`). Customer id/addresses for mutate tasks are baked into the image.
- **Reset:** env-ctrl `POST /reset`, `status/init/start/stop/restart`, `wait_until_ready`; **what `/reset` restores is not documented** [docs gap]. The safe reset is container recreate (`env stop` + `env start`); cost unknown until measured.
- **Resources:** RAM/CPU/startup time are **not documented**. This machine: 16 CPUs, 13 GB RAM (~7 GB free), 925 GB disk — disk is fine; RAM is plausible but unmeasured (Magento + MySQL + search engine + headless Chromium).
- **Blocker on this machine:** Docker Desktop is installed but its Linux engine is not running and WSL integration is disabled (`docker` in WSL is a stub; `docker.exe` cannot reach `dockerDesktopLinuxEngine`). I did not start Docker Desktop or pull the 5.4 GB image. To unblock: start Docker Desktop, enable *Settings → Resources → WSL integration* for this distro, then `docker pull am1n3e/webarena-verified-shopping`.
- **Complexity of what the agent encounters [inferred, not observed]:** the catalogue is scraped Amazon-style data (long product titles in URLs, e.g. task 25/286/431 URLs), a very large catalogue (task 124's expected range is US$0.01–298.00 for "wireless earphone" — a heterogeneous catalogue with junk prices), reviews with ratings, search/layered navigation, cart/checkout and customer account pages. It is **not** an Amazon equivalent (Magento Luma theme, static snapshot, no personalization) but is far richer than our 48-product store. Real DOM size/tokens per page are unmeasured and are the main cost risk.
- **Modifying the site reproducibly [inferred; precedent in the image]:** WAV itself patches Magento with a custom module (CustomerAutoLogin). We can do the same: a `Dockerfile FROM am1n3e/webarena-verified-shopping` adding a module/theme override (phtml/layout XML) + cache flush, recorded by image digest; variant = tag. HTML-rewriting proxies are quicker but change URLs/hosts and are less faithful. Full-page cache and static-content deploy must be handled per variant. Moderate effort, unverified.

## 2. Dataset and evaluator compatibility [verified from the 1.2.3 package]
- 812 tasks; **187 shopping-only** (81 retrieve, 45 navigate, 61 mutate; 48 intent templates), **56 of them in the Hard subset**; 5 more tasks mix shopping with other sites. 126/187 are read-only; only **15 tasks** have cart/checkout/account-bound evaluations.
- Evaluation = `AgentResponseEvaluator` (type-aware, deterministic: currency, lists as sets, etc.) + `NetworkEventEvaluator` (matches events in a **HAR**: method, URL pattern, post data, response status/content; navigate tasks use *the last navigation event*, defined as GET with `Accept: text/html`). Input = agent response JSON `{task_type, status, retrieved_data, error_details}` + a HAR/Playwright trace. **Ground truth and evaluators can be reused as-is via the official library** — no adapter for judging, only for capturing/forwarding the HAR and response.
- Verified here (offline, stub traces): the official evaluator scores correct/incorrect cases for tasks 286 (navigate), 124 (retrieve), 25 (retrieve list) and 431 (mutate POST) as expected; evaluator version/data checksums are emitted per result (good for provenance).

## 3. Integration findings (prototype in `src/agent_readiness/webarena/`)
1. **Browser Use's built-in HAR recorder is HTTPS-only** [verified: `har_recording_watchdog._is_https`; an HTTP run produced `entries: []`]. WAV's site is plain HTTP → official evaluation would see nothing. **Fix implemented:** `NetworkCapture` — a second Playwright connection over CDP records every request/response (method, URL, headers incl. Accept/Sec-Fetch, post data, JSON/HTML bodies ≤200 kB) into a HAR 1.2 file; `attempt()` gained an optional `network_capture` hook (default off; existing paths unchanged).
2. **Agent response contract:** `WAAnswer` mirrors WAV's `FinalAgentResponse` and is used as the Browser Use `done` schema (schema hashes computed like other tasks).
3. **Corrected tool behaviour works in this path [verified on a stub site]:** with `suite-v2-compat1` the `find_elements` output reaches the model (`<read_state>`), a scripted element-reader follows the link and the **official evaluator passes**; with `suite-v1-compat1` the same scripted model never sees the targets and fails. Whether the *live model* uses it, and how it behaves on real Magento DOM (very large pages), remains **untested**.
4. **End-to-end prototype [verified, stub site standing in for Magento]:** Browser Use agent (mock model) → loopback stub storefront → HAR → official WAV evaluator: correct navigation passes, wrong page fails, attributed by the official evaluator's missing_navigation_event. Tests: `tests/test_webarena_spike.py` (5; skipped automatically if `webarena-verified` is not installed — it is an optional extra, not in default CI).
5. **Failure attribution is preserved:** harness/tool findings (`scanner.diagnostics`) are independent of the official verdict; WAV only says pass/fail per evaluator (+ which assertion failed), so website vs agent vs tool attribution must still come from our traces. Our observed-text evidence concept has no WAV equivalent — we would add per-task *evidence requirements* ourselves only where we need "shown to the agent" analysis.

## 4. Proposed minimal integration architecture
```
Docker (WAV shopping, 7770 + env-ctrl 7771) ── optional derived image per website variant (Dockerfile + digest)
        ▲ HTTP                         ▲ header auto-login (X-M2-Customer-Auto-Login)
Browser Use agent (suite-v2 profile, allowed_domains = site origin) ── Playwright/CDP NetworkCapture → network.har
        │ done(data=WAAnswer)                                       │
        └────────────► official WAV evaluator (agent_response + HAR) ◄┘ → verdict + checksums
Agent Readiness: schedule/manifest/ledger/driver (Task 012) · metrics · diagnostics (tool-interface vs website vs agent) · private traces
```
New code needed: environment registration `webarena-shopping-v1` (base URL, container digest, auth header injection, `reset()` policy), task loader (`WATask` done), per-task limits/prompt template (done in prototype), multi-tab start-state support (task 431), manifest hooks (WAV version + data/evaluator checksums + image digest), driver wiring (profile + environment from manifest), page-size guards (token budget), trace/metrics adapter (HAR → page loads/requests; reuse journey/trace), and an end-of-episode form-state probe for tasks like 528 (see §5).

## 5. Task suitability (from the actual task definitions)
| Task | Definition / evaluator | State & reset | Suitability |
|---|---|---|---|
| **286** SSD ≥1 TB, cheapest (navigate) | start `__SHOPPING__`; response NAVIGATE/SUCCESS; last navigation GET must equal one product URL | read-only; no reset | **Good first task.** Search/sort/filter + comparison on a large catalogue; ground truth reusable. Risk: category/search ambiguity ("ssd hard drive"), step budget (12) may be too small — measure |
| **124** price range of "wireless earphone" (retrieve) | `{min,max}` numbers; expected 0.01–298.00; no network check | read-only | **Usable but costly:** needs exhaustive pagination of search results; likely exceeds 12 steps; expected range includes an anomalous US$0.01 item — genuinely hard; good for a long-horizon/"effort" study, poor as a first reliability task |
| **25** reviewers mentioning print quality, ≤3★ (retrieve list) | start on a product page; names compared as a set (["Roxanne Brandon Coffey","Nelson"]) | read-only | **Good.** Reviews + rating filtering, information density; reusable evaluator; review pagination/sorting is a natural website-intervention target |
| **431** add lowest unit-price product among 3 open tabs (mutate) | 3 start URLs ("open tabs"); POST `/checkout/cart/add/.../product/32202` with `qty=1,item=32202` | **mutates cart**; needs login header + reset between runs | **Conditional:** harness must open multiple tabs; arithmetic on unit prices (agent reasoning, not site); needs cart reset (`/reset` semantics unverified or container recreate) |
| **508** buy highest-rated NS-switch item under $60 (mutate) | 4 network evaluators incl. cart totals response body, payment-information POST (customerId 27), success page | **places an order**, needs saved address/payment, "discard cart" | **Defer.** Long checkout flow (high cost), side effects, reset each run, HAR must hold response bodies (our capture does for JSON ≤200 kB) |
| **528** refund contact form, do not submit (mutate) | needs order lookup (order #180, $12.99) in account history; evaluator expects a POST of the filled form to `^http://.*/dummy_bin$` (aborted, status −1) and **no** `/contact/index/post` | account state; form never submitted | **Unsuitable for now:** the `dummy_bin` POST implies an end-of-episode harness step that reads the form state; not reproduced in our harness yet; unclear how WAV's reference runner triggers it |
Recommended pilot set: **286, 25** (+ 124 as a separate long-horizon item), then the read-only subset (126 tasks). Treat 431 as stage 2, 508/528 as out of scope for the hackathon.

## 6. Risks
Docker/RAM unknown (13 GB host); 13 GB image pull; Magento page sizes → token cost and `max_results`/DOM truncation; catalogue data derived from scraped retail content — **do not publish screenshots/traces** without checking licensing and Meta terms (existing publication constraints apply); reset semantics undocumented; run-to-run server nondeterminism (search ordering, sessions) unmeasured; Magento full-page cache complicates per-variant changes; task difficulty (all six shortlisted are in the Hard subset) may produce floor effects rather than ceiling effects — the opposite of our synthetic store; fidelity guard's per-request cost ceiling (US$0.04) may block large Magento pages (needs calibration).

## 7. Recommendation: **CONDITIONAL GO**
Go for WAV shopping as the primary realistic benchmark **for the read-only task subset**, conditional on a 1–2 hour live check that: (a) Docker engine runs and the shopping container starts in acceptable time/RAM, (b) our agent loads and navigates real pages within the token/cost ceiling, (c) NetworkCapture + official evaluator reproduce a known-good navigation (e.g. a scripted visit to the task-286 URL passes), and (d) a no-op reset/recreate returns a clean state. NO-GO triggers: RAM <≈8 GB available makes it unstable; pages too large for the per-request cost ceiling; or non-deterministic catalogue. Fallbacks: other realistic storefronts (e.g. Mercur) or a scaled-up synthetic catalogue.

## 8. Remaining engineering before the first controlled live WebArena experiment (estimates)
| Work | Hours |
|---|---|
| Enable Docker, pull/run image, measure RAM/startup/reset, smoke the 6 shortlisted URLs | 1.5–2.5 |
| Environment registration + auth header + base-URL/origin handling + reset policy + manifest/ledger wiring | 3–4 |
| Calibrate cost ceiling/limits and DOM-size guards on real pages (mock dry-runs) | 2–3 |
| Metrics/diagnostics adaptation (HAR → page loads/requests, evidence requirements for 286/25) | 3–4 |
| Website-variant mechanism (derived image + one reviewed intervention) | 4–8 |
| Experiment plan, schedule/hash, approval round | 2 |
| **Total to first controlled live run** | **≈16–24 h** (≈8–10 h for a baseline-only first live run) |
