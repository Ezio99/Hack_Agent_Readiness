# Report 014 — WebArena Verified Magento end-to-end validation (Task 014, issue #15)

**Date:** 2026-10-29. **Branch:** `task014-webarena-e2e` (from `main` `b41e77f`). **No model call of any kind was made** (scripted mock model, zero credentials, zero spend). This validates the *environment + capture + official evaluator* path on the **real** Magento site; it says nothing about live-model behaviour.

## Audit of the existing spike (PR #14, merged)
Present on `main`: `src/agent_readiness/webarena/{adapter,har,runner}.py`, `attempt(network_capture=…)` / `record_har_path` hooks in `agent.py`, `tests/test_webarena_spike.py`, `docs/WEBARENA_SPIKE.md`. Before this task all of it was validated only against a loopback stub. Added here: `scripts/webarena_validate.py` (scripted scenarios), `sanitize_har()` in `har.py` + 1 test. Adapter, runner and `NetworkCapture` were **not** modified.

## Environment (actually started)
| item | value |
|---|---|
| Host | WSL2 Ubuntu, 13.5 GiB RAM visible to Docker, ~930 GB free |
| Docker | Docker Desktop 4.57.0, engine 29.1.3 (started from WSL via `powershell.exe Start-Process "Docker Desktop.exe"`; WSL integration is still off, so `docker.exe` is used from WSL) |
| Image | `am1n3e/webarena-verified-shopping:latest`, digest `sha256:3e8cb9b945ea9b1c94ab26dba53e8d12dd0406abbf4bf686fd3bb2b6a5908feb` (5.42 GB content / 19.5 GB on disk) |
| Evaluator | `webarena-verified==1.2.3`, evaluator checksum `35c3385b…01db4e`, data checksum `d6527566…243d30` |
| Start | `docker.exe run -d --name wav-shopping -p 7770:80 -p 7771:8877 am1n3e/webarena-verified-shopping` |
| Health | site HTTP 200 after **24 s** (cold) / **23 s** (recreate); env-ctrl `GET :7771/status` reports mysqld, elasticsearch, redis, nginx, php-fpm healthy; idle RAM **1.2–1.3 GiB** |

Reproduce: `uv run --extra webarena python scripts/webarena_validate.py direct runs/webarena-014/direct-1` (and `wrong`). Output dir is Git-ignored.

## Task 286 (NAVIGATE: "least expensive ssd hard drive, min 1 TB") — scripted, no LLM
Browser Use agent (`suite-v2-compat1`) + scripted mock model → real Chromium → real Magento → `NetworkCapture` HAR → **official evaluator**.
| run | script | instance | official verdict | evaluators | HAR entries | model reqs | wall |
|---|---|---|---|---|---|---|---|
| direct-1 | navigate to the evaluator's expected product URL, then `done` | container #1 | **PASS (1.0)** | AgentResponse ✔, NetworkEvent ✔ | 488 | 2 | 12.3 s |
| wrong-1, wrong-2 | navigate to `/catalogsearch/result/?q=ssd` (negative control) | #1 | **FAIL (0.0)** | NetworkEvent ✘ `missing_navigation_event` | 464/466 | 2 | ≈6 s |
| direct-2 | as direct-1 | container #2 (after recreate) | **PASS (1.0)** | both ✔ | 488 | 2 | 6.0 s |

What this establishes: the plain-HTTP site is captured (Browser Use's own HAR would be empty), the official evaluator accepts our HAR on the real site, and it rejects a wrong page for the right reason. What it does **not** establish: that an agent can *find* the page by browsing. The "direct" script is handed the URL taken from the evaluator's expected answer — it is a known-good-navigation probe, **not** a solved task, and must not be reported as agent success. (The HAR holds ~470 entries because every page pulls static assets; the evaluator reads the last navigation event.)

## Trace capture and sanitization
- Captured per request: method, URL, request headers (incl. `Accept`, `Sec-Fetch-*`), post data, status, textual bodies ≤200 kB. Raw HAR ≈4.7 MB per run and contains session cookies/form keys: **private, Git-ignored**.
- `sanitize_har()` writes an inspection copy: 250–264 sensitive headers redacted (cookie/set-cookie/authorization/auto-login), bodies dropped, post data length-only; 0 occurrences of `PHPSESSID`/`form_key` verified by grep; 0.9 MB. The evaluator must use the **original** HAR. Site content is third-party scraped retail data, so even sanitized copies are not for publication.
- Observed quirk: `capture.entries` held 488 but the written file had 473 (direct-1) — a few late requests complete after `close()` writes the file. Harmless for `last_event_only` navigation checks; could matter for mutation tasks (write HAR after a drain, not yet done).

## Reset / reproducibility
- Wrote a marker table into `magentodb` of container #1 (`CREATE TABLE zz_marker`, 1 row confirmed) → `docker rm -f` + `run` of the same image → marker **absent**, ready in 23 s. Container recreate therefore returns the baked baseline. (Credentials of the image's database are the upstream defaults; not reproduced here.)
- Product page of container #1 vs #2: byte hashes differ only through per-render random element ids and form keys; **visible text identical** (9,891 chars, same title). Task 286 passed on both instances.
- Not tested: reset after a mutating task (cart/order), the env-ctrl reset endpoints, concurrent containers, behaviour across a Docker restart.

## Cost / size indicators (mock requests, real pages)
Home page ≈ 8.9k and product page ≈ 8.3k prompt tokens per request (35.7k / 33.3k chars) with the unchanged agent — similar to the synthetic suite (~9.4k), i.e. about US$0.013 per request at the verified Muse rates. Listing and search pages (not measured in-agent) can be larger.

## Observations about the site (not agent faults; not attributed)
A raw search `ssd 1tb` sorted by price ascending returns mostly unrelated products (cameras, consoles, cables) among 7 hits, so "find the cheapest ≥1 TB SSD" is not a one-step filter on this catalogue. This is a property of the real Magento data/search, consistent with the task's Hard rating; it should be expected to cost live agents extra steps. It is an observation from one HTTP request, not a measured success rate.

## Tests
`tests/test_webarena_spike.py`: 6 passed with the optional extra installed (5 stub-site tests from PR #14 + the new sanitizer test; these use the stub, not Magento). Full suite (with the `webarena` extra installed, stub tests included): **549 passed** in 12m25s locally. The real-Magento evidence above comes from `scripts/webarena_validate.py`, not from the pytest suite (CI has no Docker and skips these).

## Unverified / limitations
Live-model behaviour on Magento DOM; whether Muse Spark can complete 286 (or 25) by browsing; auto-login header; mutation tasks and state reset after them; the env-ctrl API; run-to-run catalogue determinism beyond two instances and one page; `suite-v2-compat1` live effect; HAR late-entry drain; WSL-integrated `docker` (works via `docker.exe`).

## Recommendation: **CONDITIONAL GO** for exactly one bounded live Muse Spark run on task 286
All four spike GO conditions are now met on the real site: container starts in ~24 s / ~1.3 GiB, per-request size is within the cost ceiling, a scripted visit passes the official evaluator, and recreate resets state. Conditions before spending: (1) your approval of an exact call plan (task 286, baseline only, `suite-v2-compat1`, proposed limits ≈ 20 steps / 20 requests / 300 s, hard cost cap ≈ US$0.40, ledger entry); (2) expect failure by exhaustion to be plausible (Hard task, noisy search) — a fail is not website evidence; (3) run the evaluator on the original HAR and keep all artifacts private. Next smallest step: the call-plan document, then 1 run; no more tasks until that result is reviewed.
