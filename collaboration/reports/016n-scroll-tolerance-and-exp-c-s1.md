# Scroll tolerance and EXP-C-S1 offline preparation — 2026-11-01

Status: offline implementation and preparation only. **No paid S1 trial is approved or executed.** No merge, push, deployment or ledger reconciliation performed.

## Implementation

- `agent.py`: opt-in execution wrapper for `scroll` only. For a nonzero index, read the current `BrowserSession.get_selector_map()` on each invocation. Absent index → call the existing scroll handler with `index=None`; valid, omitted and zero indices keep their original behavior. Forward Browser Use's injected execution arguments. Do not change registered schemas/descriptions, model instructions, reasoning settings, other actions, failure limits or result text. Lookup failures and ordinary execution errors remain errors.
- `profiles/suite-v2-compat2.json`: exact compat1 content except profile identity and `scroll_index_policy: page-fallback-v1`. Compat1 bytes unchanged.
- Each fallback writes a `scroll_index_fallback` trace event: requested index, `current_map_valid:false`, actual page-scroll action and ordinary result (or exception). It does not invent successful results or add observations to the model prompt.
- `evaluate/scroll_successor.py`: explicit opt-in, write-once declaration with canonical hashes of both profiles. Verify that ONLY identity/policy differ; compare recorded effective profile hashes after applying the frozen task's existing limits. All model/schema/mode/limit checks remain; placebo still checks the original snapshot. Reject undeclared succession, profile drift, tampered rules and unrelated effective changes.
- `evaluate/stage.py`, `trials/stage.py`: bind the exception into the complete post-trials manifest and pass its profile into execution for BOTH new arms. Imported task manifests and arm configuration remain untouched. Historical no-exception manifests are unchanged.
- `live/abtest.py`, `live/cli.py`: explicit `--scroll-sensitivity`, fresh fork only, required again on resume. Existing exact manifest approval and `--allow-model-calls` safeguards remain.
- `investigate/report.py`: sensitivity notice in reports/exports whenever the successor declaration is present; ordinary reports are unchanged.

## S1 preparation and exact approval

Local fork: `scanner-data/live/live-ab-ironbark-s1`, from `live-2d58a80e14` with carried investigation. Only the free `apply_fix` approval was recorded under this implementation authorization; `post_trials` is awaiting approval. No new spend reservation.

Complete post-trials manifest SHA-256:

```
99f493d1558db5d925069e5ae8ea66fc21e2927e1364a69ddb45ec9ae3a550f8
```

Local manifest: `scanner-data/live/live-ab-ironbark-s1/artifacts/manifests/post_trials-99f493d1558db5d9.json`.

Successor-rule SHA-256: `89c8cd44c4ff02bdfe9123dd4b62cfe9ab417cff00cf21fb1f1601a2eddb1944`.

Eight new trials: four frozen tasks × one placebo and one patched trial, same counterbalanced order. Model `muse-spark-1.3`; both new arms `suite-v2-compat2`. Frozen tasks, private criteria/truths and original snapshot verified identical to the source; patched snapshot, model, order, grading/rule hashes and caps verified identical to EXP-C. No investigator rerun. No task generation.

| Effective limit | US$ / count |
|---|---:|
| Each arm | 0.80 |
| Combined additional spend | 1.60 |
| Each trial | 0.50 |
| Each request | 0.05 |
| Ledger ceiling including imported history | 2.50 |
| Imported committed spending | 0.864825 |
| Headroom after imported + combined caps | 0.035175 |
| Request gate per trial | 16 |
| Frozen task limits | 14 steps / 14 model requests / 240 seconds |
| Retries | 0 |

The task's 14-request limit is tighter than the 16-request gate. Expected additional calculated spend approximately US$1.1–1.2, based on EXP-C/R1; recovery may increase it. These are calculated amounts, not bills. Reserve-before-send caps remain subject to the existing one-request usage-estimation overshoot limitation; nothing in this change strengthens that bound.

## Integrity assumptions and interpretation

Both contemporary arms now share compat2; their site comparison retains the same reference-agent configuration. The imported baseline remains compat1: historical-baseline comparisons now change agent version as well as site presentation. The manifest explicitly sets baseline profile equality false and binds the narrow successor exception. Do not pool S1 with EXP-C/R1 or treat comparisons to the imported baseline as a clean site-only effect.

The frozen and exploratory decision rules remain byte-identical. At four pairs the frozen test cannot attain p ≤ 0.10. The existing exploratory rule still counts early agent failures as fewer requests; report that limitation and individual outcomes/fallback counts rather than interpreting its verdict alone as efficiency. The owner-selected intervention and small sample remain limitations.

Fallback assumes page scrolling is useful when an element index does not exist; it cannot recover intended element scrolling and may move the wrong viewport. A present but inappropriate index is deliberately unchanged. Model behavior after different tool results will naturally diverge; no model prompt or reasoning configuration is changed.

## Validation

`tests/test_scroll_policy.py` covers exact profile succession, schema/description/other-action invariance, current-map lookup, invalid/stale/valid/omitted/zero indices, injected arguments, result/error preservation, fallback records and strict control checks. The real-browser tests check actual viewport movement over repeated scrolls, stale indices after navigation, compat1 errors and full-agent recovery: two invalid scrolls terminate compat1, while compat2 logs both fallbacks and completes a scripted independently graded task. These are fixture mechanism checks, not live model evidence.

An initial direct-browser run passed, but the added full-agent test exposed missing forwarding of `page_extraction_llm`; corrected and rerun successfully. Initial sandbox browser binding failed (`PermissionError`); Chromium tests ran outside the sandbox with the test suite's loopback-only guard.

Final checks actually run:

- Focused regression: `timeout 180 .venv/bin/python -m pytest tests/test_scroll_policy.py tests/test_ab_experiment.py tests/test_investigate_expb.py tests/test_term_value.py tests/test_tool_visibility.py -m "not browser" -q -x`: **77 passed, 3 deselected**, 38.26 s.
- After adding the sensitivity report notice: scroll-policy and EXP-C files, **13 passed, 2 deselected**, 21.37 s. After the final generated-action-schema invariance assertion: scroll-policy units, **4 passed, 2 deselected**, 2.39 s.
- `timeout 180 .venv/bin/python -m pytest tests/test_scroll_policy.py -m browser -q -x` outside the sandbox: **2 passed, 4 deselected**, 10.21 s. This final run uses real navigation to a fresh document without controls to expire the old index; no selector-map mocking.
- `timeout 180 scripts/critical-tests.sh -x` outside the sandbox: **214 passed, 17 deselected**, 56.52 s. The sandbox attempt timed out after 180 s at the first TestClient request (five tests complete); the complete unsandboxed retry passed. No test conclusion is based on that timeout.
- Recomputed manifests from current code for EXP-C, R1 and S1: all exactly match their stored complete hashes. Historical code path remains hash-compatible, not merely unchanged on disk.
- `git diff --check`: clean. Full sharded CI has not run on this local change; no push performed.

Free inspection/resume command (does not approve or execute a paid stage):

```
.venv/bin/readiness live ab-experiment --id live-ab-ironbark-s1 --scroll-sensitivity
```

Paid execution remains behind explicit owner approval of the complete S1 post_trials hash and `--allow-model-calls`. No such approval is recorded.

Preservation verification: SHA-256 comparison of 2,239 protected files (EXP-C, R1, original source, investigator replay, related live run and compat1 profile) found no changes. EXP-C and R1 retain the complete approval hash `05053088ef81a2ae2c0c4cce34bef74306416ff9b7e978281b7d93cbbf087d8c`. Run artifacts and truth records remain local/ignored; no generated run data is committed.
