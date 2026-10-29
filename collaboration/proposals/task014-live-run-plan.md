# Task 014 follow-up — PROPOSED live run plan: WebArena shopping task 286, one run (NOT APPROVED, NOT EXECUTED)

**Status: proposal for review, 2026-10-29. No model call has been made or is authorized. Nothing in this document is run until the project owner approves this exact plan.** Baseline: [Report 014](../reports/014-webarena-magento-e2e.md) (PR #17, merged `8803674`), which validated only scripted/mock navigation on the real Magento site.

## 1. Question and scope
Can the frozen reference agent, starting from the normal storefront entry point with no hint of the answer, find and open the product page the official evaluator expects for task 286 ("View the product page for the least expensive ssd hard drive with a minimum storage capacity of 1TB")? **One task, one run, one model configuration, baseline site only.** A single run is feasibility evidence, not a success rate and not evidence about website readiness.

## 2. Exact configuration
| item | value |
|---|---|
| Model / endpoint | `muse-spark-1.3` at `https://api.meta.ai/v1` (`ModelConfig` defaults; provider `meta`; key from `META_MODEL_API_KEY`, never printed) |
| Reference agent | `suite-v2-compat1` **unchanged** except the run-limit overrides below (vision on, 1280×960, `reasoning_effort: low`, 4,096 completion tokens, parser `muse-prose-prefix-json-v1`, `tool_result_visibility: read-state-v1`). No compatibility issue found that needs approval, but see risk R1 (answer schema) |
| Task input | `WATask.prompt()` = official intent + `Start at http://localhost:7770` + the answer-format instruction. The start URL is the site root (`task.start_urls[0]`) |
| Site | existing container `wav-shopping` (digest `sha256:3e8cb9b9…`), **kept as is, not recreated**; pre-run health check must pass (HTTP 200 + env-ctrl `/status` all healthy) |
| Evaluator | `webarena-verified==1.2.3`, run **after** the agent finishes, on the **original** HAR + the agent's `done` payload; checksums recorded |
| Limits | `max_steps` 16, `max_model_requests` 16, run timeout 300 s, per-model-request timeout 30 s, per-step timeout 60 s, `allowed_domains` = `http://localhost:7770` |
| Answer envelope | official `WAAnswer` (`task_type`, `status`, `retrieved_data`, `error_details`) as the `done` schema. Verified offline that for task 286 the evaluator requires `task_type == NAVIGATE` and `status == SUCCESS` and tolerates `retrieved_data` null/[]/non-empty |

## 3. No access to answers (checks, all offline, before any spend)
- The agent's task text, system instructions, schema and tool list are asserted **not** to contain the expected product slug, the evaluator's expected URL, "portable-ssd", or any evaluator field (string scan of every message that would be sent; the scan is repeated on the recorded request bodies after the run).
- The expected URL lives only inside the in-process official package; the agent's Chromium can reach only the storefront origin and never the evaluator data or `runs/`.
- The site is unmodified; the agent discovers the product by browsing/search like any user. (Whether the store's own search/listing is noisy is an observation about the site, not a handicap added by us.)
- Wire schema recorded with its hash; the live path uses the existing pre-send schema-fidelity guard.

## 4. Cost, ceiling, ledger
- Verified prices: US$1.25 / US$4.25 per M input/output tokens (`docs`/`capture.py` constants; the preflight refuses to spend if they differ). Calculated cost, not a bill; the provider reports none.
- Per request (estimate): Magento page text ≈ 8–9k prompt tokens measured (mock requests on the real pages) + screenshot (≈1–2k, unmeasured on Magento) + history, i.e. ≈ 10–13k input and 0.25–1k output ⇒ **≈ US$0.015–0.022**. Listing/search pages may be larger; per-request estimate cap stays at the existing US$0.04 (a request estimated above it is blocked pre-send).
- Expected run: 6–12 requests ⇒ **≈ US$0.10–0.25**. Worst case at the 16-request limit ⇒ ≈ US$0.35–0.45.
- **Hard ceilings:** cumulative estimated cap for the run **US$0.50** (enforced before every request by the existing `estimated_cost_limit` guard); ledger ceiling for this programme step **US$0.60** (run reservation US$0.50 + optional schema probe US$0.04 + US$0.06 slack). The persistent append-only ledger (`scanner/live.py` `Ledger`: reserve-before-request, unsettled reservations count in full, an item can be attempted once, never auto-retried) is reused in a new directory `runs/webarena-014/live/` (Git-ignored). Programme-wide ledger headroom is unaffected beyond this US$0.60 (Task 012 committed US$0.718 of its US$6.00).
- Total expected spend including probe ≈ US$0.15–0.30; **no spend above US$0.60 is possible by construction**.

## 5. Gated sequence (each step separately logged)
0. *Offline, credential-free (≈1–2 h, can start on approval):* add a guarded live path to `webarena/runner.py` (live provider, `--allow-model-calls`, ledger reserve/settle, pre-send leak scan, post-run request-body scan, credential scrub identical to the existing runner); stub-transport tests proving: refuses without the flag, refuses over ceiling, one attempt only, leak scan trips on a planted slug, HAR + official evaluation still run when the agent errors. Report and re-run the full offline suite.
1. *Optional but recommended — one schema probe (≤ US$0.04, 1 request):* send the real `WAAnswer` wire schema (strict `json_schema`) with a trivial prompt. See R1.
2. *The run:* exactly one execution, sequential, no retry, no replacement, container not recreated.
3. *Post-run, no spend:* official evaluation on the original HAR, sanitized HAR copy, request-body scan, diagnostics, Report 014b.

## 6. Stop conditions
The run stops at the first of: agent calls `done`; 16 steps; 16 model requests; 300 s; estimated per-request cost over US$0.04 (blocked pre-send); cumulative estimate over US$0.50; schema-fidelity violation; provider/HTTP error (no retry); two consecutive unparsable model outputs (Browser Use default); navigation outside the allowed origin (blocked by `allowed_domains`); container health failure mid-run (checked at start and end). Any guard-class stop halts everything and is reported as such; a wrong answer or running out of the agent's own budget is a result, not a halt.

## 7. Evidence and independent evaluation
HAR via `NetworkCapture` (original kept private, sanitized copy via `sanitize_har`); the full Browser Use trace (requests, parser recovery, actions, tokens, timings); pre- and post-run container health and image digest; evaluator version/checksums. Outcome = the **official evaluator's** verdict on the original HAR; the agent's own `done(success)` is never used. Raw strict-JSON compliance vs compatibility-recovered responses are reported separately, as before.

## 8. Failure attribution (pre-registered; no attribution from failure alone)
| class | counts as | evidence required |
|---|---|---|
| **Environment** | container/Docker/Magento/network fault, HTTP 5xx or page-error responses in the HAR, health check fail, timeout caused by host load | health endpoint, HAR statuses, container logs; the run is then **void/inconclusive**, not a task failure |
| **Provider/infrastructure** | HTTP error, schema rejection, malformed API response | request record; halts, no retry |
| **Browser-tool** | the tool hid or mishandled information (e.g. repeated `find_elements` with a count-only result, truncated/oversized DOM, click or navigation that the browser layer swallowed, parser rejection of a valid action) | trace shows the information was present on the page but absent from the model's observation, or a tool-result/action mismatch |
| **Website** | the needed information was **not** present in what the agent observed (e.g. price/capacity not on result pages, search returns unrelated items) — judged from observed text and the HAR, never from the agent's failure | observed-text evidence; where unclear, "undetermined" |
| **Agent** | the information was available and the tool behaved, but the agent chose wrongly (wrong product, premature `done`, extra navigation after reaching the target, wrong `task_type`, hallucinated page) | trace of observations vs decisions |
A final navigation after reaching the right page breaks the evaluator's last-event rule: it is recorded as an agent action, with the HAR order shown. Anything not separable is labelled "undetermined".

## 9. Unresolved risks (for your review)
- **R1 — answer schema acceptance (concrete):** the unchanged official `WAAnswer` produces `retrieved_data: anyOf[{type: array, items: {}}, null]`; an unconstrained `items: {}` in a strict `json_schema` may be rejected by the Meta endpoint (all schemas proven so far had typed items). Hence the optional US$0.04 probe. If rejected, the smallest remedy (needs your approval because it changes the answer contract wording, not the evaluator): type `retrieved_data` items as `string | number | boolean | object`, evaluated by the same official evaluator.
- **R2 — likely hard task / noisy search:** a raw search for "ssd 1tb" sorted by price returned mostly unrelated products among 7 results. A failure on one run is likely to be informative about difficulty, not conclusive about anything; do not read it as website unreadiness or as an agent-capability rate.
- **R3 — `last_event_only` rule:** success requires the product page to be the last navigation; an agent that opens the right page then wanders will fail for agent-side reasons.
- **R4 — live path is new code:** step 0 must pass before any spend; a bug there is a reason to stop, not to retry live.
- **R5 — vision token cost on Magento is unmeasured** (only text-side size was measured); the per-request cap and the ledger bound the exposure regardless.
- **R6 — third-party content and terms:** the run sends scraped retail page content and screenshots to the Meta API and stores them in private artifacts. Publication of traces/screenshots stays prohibited pending the open Meta-terms/licensing review (unchanged standing constraint).
- **R7 — one run is not evidence of reliability, variance, or of `suite-v2-compat1` effectiveness** (its live behaviour is still unverified); results must not be pooled with Task 011/012 data.
- Out of scope and unapproved: any other task (25, 124, 431, 508, 528), repeats, site variants, derived images, Stage 2.

## 10. Approval requested
Approve (a) step 0 offline implementation, (b) the optional ≤US$0.04 schema probe, (c) exactly one live run at the limits above with ceiling US$0.60, or amend any of them. No call happens before a reply naming what is approved.
