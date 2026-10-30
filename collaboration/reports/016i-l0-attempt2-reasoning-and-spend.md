# Report 016i — L0 attempt 2: reasoning budget, sanitized diagnostics, reservation policy

**L0 attempt 2 (approved hash `18a9c310…25ee`, main `f688dd9`):** P1 returned HTTP 200 with usage; the output did not validate (not strict JSON, no recovery); the probe stopped; verdict FAIL. Ledger: reserve US$0.00096, settle US$0.000981. Artifacts in `investigations/l0-probe-2/` (untouched; attempt 1 in `l0-probe/` also untouched).

## 1. The working Meta path (in this repo — no separate earlier repo exists)
`~/Projects/Agent_Readiness` (pre-event prototype) contains no Meta/Muse/key references; `Hack_Agent_Readiness_archive` only holds Task 007 documents of this repo. The working integration is this repo's Browser Use path (`agent.create_model`, profiles `natural-v3`/`suite-v2-compat1`), validated in Task 004. Concrete differences from the investigator `MetaClient` / L0:

| | Working agent path | `MetaClient` / L0 attempt 2 |
|---|---|---|
| model / endpoint / auth | `muse-spark-1.3`, `https://api.meta.ai/v1`, bearer | identical |
| `reasoning_effort` | `"low"` on the wire (profile; `reasoning_models=["muse-spark"]` forces Browser Use to send it) | **not sent** |
| `max_completion_tokens` | 4,096 (v3 profiles); Task 004 attempts at 16/128 returned `content: null` | **200** (P1/P2), 1,500 / 1,200 (P3–P6) |
| temperature / penalties | omitted | omitted |
| structured output | `response_format` strict `json_schema` with the real schema (Task 004 Stage B accepted it) | strict `json_schema` (now `additionalProperties:false`) |
| parsing | Browser Use + prose-prefix recovery (`compat.py`) | same recovery via `complete_structured` |
| usage / finish reason | usage incl. `completion_tokens_details.reasoning_tokens`, `finish_reason` captured in traces | **dropped** |

Evidence from this repo (confirmed): Task 004 — reasoning tokens count inside `completion_tokens`; `finish_reason: length` with `content: null` when the cap is exhausted; `reasoning_effort: low` accepted; trivial request 110–126 reasoning tokens; strict-schema `done` request 906 reasoning tokens (994/1,024 completion). 491 live agent responses (profile caps 4,096, effort low, all `stop`): completion median 300 / p90 447 / max 979; reasoning median 120 / p90 214 / max 790.

## 2. L0 failure — what the artifacts allow
Confirmed: HTTP 200; usage reported; text did not validate even through recovery; settled cost US$0.000981; latency 2.3 s; the report row did not count the cost (`total_calculated_usd` 0.0 understated spend).
Hypothesis (unverified; response text was never stored): **empty content at the 200-token cap** — hidden reasoning used the allowance. Support: US$0.000981 requires completion ≤ 200 and therefore prompt ≥ 105 tokens, and the cap makes 200 completion tokens the most likely value; latency ≈ Task 004's 1.4 s + 3.75 ms/token at ~200 tokens. Not excluded: prose/non-JSON or schema-mismatched JSON.
**Why evidence was lost:** (a) `MetaClient` never read `finish_reason` or `reasoning_tokens`; (b) `complete_structured` raised `StructuredOutputError` with only a reason string, discarding the response; (c) `l0.run` recorded no cost/usage on that branch. The raw-text file only receives successes.
**Fix:** `LLMResponse` gains `finish_reason` and `reasoning_tokens`; `StructuredOutputError.diagnostics` = `{kind (empty_content | truncated | not_json | schema_mismatch), finish_reason, content_chars, prompt/completion/reasoning tokens, cost_usd, schema_errors (location + type only)}`; L0 rows keep it and count the cost. Model text is never stored.

## 3. Spending safety
The reservation was `estimate_cost_usd`: (text chars/4 + schema bytes/4) × 1.10 = 89 input tokens, plus the full 200-token cap = US$0.00096. Reasoning tokens are part of `completion_tokens`, so the cap bounds them; the shortfall was on the **input** side: the provider's prompt count was ≥ 105 (≥ 16 more than 89). The character-based estimate ignores fixed chat-template/role framing, and a 10 % multiplicative margin is negligible for a ~90-token prompt (Task 004 Stage A also showed 15 prompt tokens for an ~8-token message). The exact provider tokenisation is not known; I could not calibrate estimate-vs-actual from the earlier live traces (they do not record the estimate next to the usage in a joinable form).
**Policy:** `RequestGate(input_overhead_tokens=…)` adds a fixed token allowance (128 ≈ 8× the observed shortfall, US$0.00016/request) to every `MetaClient` reservation; default 0, so the WebArena, scanner and experiment paths are byte-identical. The reservation is larger, so the run cap, per-request cap and ledger ceiling bind **earlier**, never later; unsettled/non-200 requests still keep the full bound; a violation still closes the gate. Regression test reproduces the exact attempt-2 numbers (old gate: violation; new: settles; tight ceiling and per-request cap still refuse; default unchanged).

## 4. Corrective L0 manifest (explicit, evidence-based)
`reasoning_effort: "low"` (as every validated profile); completion caps P1/P2 1,024 (trivial echoes; Task 004 needed > 126 reasoning tokens even for trivial requests), P3–P6 4,096 (the validated production cap; 491 live responses never reached it). Caps are ceilings billed on actual use but reserved in full. Unchanged: prompts (six `messages_sha256` identical to the approved manifest), the six-request sequence, criteria, the US$0.03 per-request / US$0.10 total caps, zero retries, approval gates.
Worst-case total (calculated upper bounds incl. overhead): **US$0.0818 = A$0.123** (US$0.08183), each request ≤ US$0.0182 (< 0.03); expected actual spend is far lower (live agent responses averaged ~300 completion tokens).
**L0 manifest SHA-256 (after review round 1): `0ce19b499a243252ffbf4f0172f8e084cbd0119f3d7fad2ae3b90ca5b0490b86`** (first revision `028831b2…9884` is superseded; do not approve it). Worst case US$0.08183.
One existing test assertion encoded the old caps (`max_completion_tokens <= 1500`, worst case < A$0.10) and was updated to the new, explicit limits (worst case < the run cap; cap ≤ 4,096).

## Remaining risks / not done
- Cause of the P1 failure is still a hypothesis until a request records `finish_reason`.
- `taskgen` (`max_tokens` 2,500) and the investigator loop (1,800) use the same `MetaClient`; they now send `reasoning_effort: low` and reserve the overhead, but their caps are unchanged and their stage manifests (L1a hashes) do not list reasoning effort or caps. Raising them and listing them in those manifests is a follow-up needing your decision before L1a.
- 4,096-token reasoning could still be exhausted on harder prompts; the diagnostics will show it.

## Review round 1 (reviewer findings; no cap, prompt, sequence, retry or gate change)
1. **Reservation guarantee clarified and tested.** The 128-token allowance is *not* a proven upper bound. Documented in `spend_gate.upper_bound_usd`: the completion side is bounded (provider-enforced cap; reasoning counted inside it); the input side is an estimate (chars/4 + schema bytes/4, +10 %, + fixed allowance for framing) that does **not** cover text tokenising denser than ~3.6 chars/token or a provider counting schemas far above bytes/4. Such a miss is detected after the fact (true cost recorded, violation flagged, gate closes) so at most one request can overshoot. Caps apply to reserved amounts and are unchanged. New tests: bound grows monotonically with prompt/schema size (100 B … 80 kB, 1…60 properties) and adds the allowance exactly once; no violation for sizes up to 80 kB under the stated assumption (3.7 chars/token + full allowance + the whole cap used); a 2-chars/token prompt IS under-reserved, is detected, the ledger keeps the actual cost and the gate refuses the next send.
   Found while testing: `estimate_cost_usd` rounds to 5 decimals (possibly down by up to US$0.000005), enough to flag a spurious violation on a tiny prompt. With the allowance enabled the reservation is now recomputed from token counts and rounded **up** to the next micro-dollar; the default path (allowance 0) is byte-identical. This is the only reason the manifest hash changed (per-request `upper_bound_usd` moved in the 6th decimal).
2. **Non-string content.** `complete_structured` now checks `isinstance(resp.text, str)` before validation *and* recovery; non-string content (list of parts, dict, number, None) is classified `not_text`/`empty_content` with sanitized diagnostics and the error `non_string_content`, never reaching `recover()`. Tests: `recover` patched to fail if called; real `MetaClient` + `l0.run` end to end (200 with list content: probe stops cleanly, cost settled and counted, diagnostics kept, no text leaked, ledger `reserve`+`settle`).
3. **Diagnostic metadata.** `upper_bound_usd` details now report `image_headroom_tokens` (images only) and `input_overhead_tokens` (fixed allowance) separately; tested for image and text-only bodies.
4. **Test cleanup.** The reasoning-effort validation test uses a plain `pytest.raises` loop over `"none"`, `"max"`, `""`.

Checks: full non-browser suite 818 passed; CI status below in the PR.
