# Report 015e — verification of the Task 015 main-stage experiment (offline; no live call)

**Date:** 2026-10-29. Scope (owner): verify the designed experiment — full suite and CI, statistics, gate/control interpretation, manifest integrity and budget — without expanding scope or tuning thresholds. **No model call, no key use, no spend.** No statistical threshold, gate threshold, task, arm or limit was changed.

## 1. Full suite and CI
- **Full Python suite on the final code (with the `webarena` extra): 675 passed, 0 failed, 114 warnings, 15 min 09 s** (`pytest -q`). The earlier stale budget expectation is corrected and green. Warnings are third-party deprecations only (pytest-asyncio loop-scope default, `idna`/`url_normalize` transitional-processing); none from this repository's code.
- Dashboard: 53 Vitest passed, `tsc` clean (unchanged by this verification).
- **PR #26 CI:** see the PR; the previous head's checks were still running when this work started, and the new head triggers a fresh run — the result is stated in the hand-over message, not assumed here.

## 2. Statistical implementation — what verification found and fixed
New `tests/test_remediation_statistics.py` (32 tests) checks `_sign_flip_p` against an **independent exact enumeration with rational arithmetic** and the verdict rule against the proposal text.
| check | result |
|---|---|
| six consistently favourable nonzero differences | exactly **0.03125** ✔ — **found defect:** the implementation rounded to 4 decimals (0.0312) |
| five consistently favourable | exactly **0.0625** ✔; four: 0.125 |
| mixed favourable/unfavourable; fractional values | matches the independent enumeration; two-sided/symmetric ✔ |
| zero differences; all-zero; tied absolute values (all tied, balanced tied) | matches; all-zero ⇒ p = 1; balanced ties ⇒ p = 1 ✔ (zeros/ties are handled by the enumeration itself) |
| fewer than 5 valid pairs (0–4 pairs) | verdict is **inconclusive even when p is forced to 0** ✔ (and void pairs reduce the pair count) |
| verdict rule vs proposal | supports needs ≥ 5 pairs, mean Δ requests ≤ −3, mean Δ visits ≤ −2, pass-rate not worse, p ≤ 0.07, control within ±2; a consistent −2 effect is *inconclusive*; zero effect is *not supported* ✔ |
Fix: `_sign_flip_p` now returns the exact unrounded fraction. The decision outcome could not change at the 0.07 threshold, but reported p-values were misreported by 5·10⁻⁵ and the exact values the owner asked for are now asserted.

## 3. Gate and control interpretation — verification and two further defects found
- `room-to-act-v2` is prospective-only: a test asserts the verdict code (`analyze`, `effect_record`, `_pairs`) contains no reference to the gate, and that giving the baseline "room" changes neither the deltas nor p. It is used only inside `run_stage` as a continue/halt criterion.
- Void classes: a direct test maps every run status to its class (`estimated_cost_limit`→budget_stop, `infrastructure_error`/`model_output_error`/`cancelled`→provider_failure, `timeout`→ambiguous_timeout, `diagnostic_fidelity_violation`/bound violation→guard_violation, `request_limit`→agent_limit, `completed`) and asserts that only `completed`/`agent_limit` are non-void, and that void runs never count as room.
- Original pilot: the corrected gate marks the pilot's incomplete baseline answer as room (R1–R3), the modified pilot run shows none, and the original frozen decision `stop` is unchanged (all 8 pilot artifacts pinned byte-for-byte).
- **Defect 1 (halts were not final):** after a halt the stage could be resumed by simply re-running the command, which would continue past the stopping rule (an earlier test had even encoded this as acceptable). **Fixed:** every halt is persisted (`halt.json`) and re-running is refused; continuing needs a new approval. A run with a ledger marker but no recorded result (driver crash) is now recovered as a void row and halts the stage.
- **Defect 2 (interim-gate edge):** one void + one valid baseline showing no room was reported as "no room (n=2)". **Fixed:** a ceiling is claimed only from two valid baselines; otherwise `halt_inconclusive`.
- **Negative control:** documented in the proposal and frozen in the manifest (`negative_control_limits`) as a coarse diagnostic for large unrelated shifts only — passing it does not rule out confounding, drift or unrelated effects; failing it only prevents a `supports` verdict.

## 4. Manifest integrity and budget
- Because the fixes changed frozen files (`experiment.py`), the earlier proposed manifest `ee2f6e06…` is **superseded** (never approved, never run; kept under `collaboration/experiments/task015/main/superseded/`). **Revised manifest SHA-256: `11c7b4ec8f7c381b247dd4b5f2b7c21d125110c6ee951113ac91fa6f2c90bff9`**, frozen on a clean tree (commit `e32ea6c`), seed 20261030, 24 runs.
- Verified after freezing: manifest content hash matches; **all 12 frozen source/config hashes valid (0 drift)**; audit baseline hash matches the manifest (audit id `5c927050dfbf`, recommendation `rec-show-availability-on-listing-cards`).
- Budget: stage hard cap **A$6.00 (US$4.00)**, per request US$0.05, per run US$0.50, programme ceiling **A$50**; the executed pilot is in the committed ledger **exactly once** (US$0.214509 = A$0.32): spent A$6.2067, remaining A$43.7933; the runtime pilot ledger (private) is skipped as already recorded, so the main-stage summary shows A$6.2067 (not 6.53); after the full stage cap A$37.7933 would remain. Expected A$2.43 – 3.60 – 4.77; worst case = the cap.
- Safeguards verified by tests and the dry run: durable per-request gate on every scan (24/24 mock runs: every request reserved and settled, 0 unsettled); one attempt per run id; no retry/replacement; halts final; live needs the exact manifest hash + `--allow-model-calls` + the recorded pilot; code-drift halts. Mock dry run of the revised manifest: 24/24 completed, 0 void, interim gate continue, effect record `mode: mock` and never attached ([015d-main-dry-run-output.txt](015d-main-dry-run-output.txt)).

## 5. Changes made
`remediation/experiment.py` (exact p; sticky halts and crash recovery; interim edge; frozen caveat text), 32 new verification tests, two updated tests (halt semantics), proposal/report wording (negative control, halts, statistic), revised manifest + audit baseline, superseded copies, status docs. The statistical and gate thresholds, arms, schedule logic, limits and caps are unchanged.

## 6. Readiness
Ready for your final execution decision on the revised manifest, subject to PR #26's CI being green on its final head. Exact command (NOT authorized, not run):
```
uv run readiness remediation-experiment run \
  --manifest collaboration/experiments/task015/main/manifest.json \
  --audit collaboration/experiments/task015/main/audit-baseline.json \
  --root runs/task015 --mode live \
  --approve-manifest-sha256 11c7b4ec8f7c381b247dd4b5f2b7c21d125110c6ee951113ac91fa6f2c90bff9 --allow-model-calls
```
Residual uncertainty is scientific, not procedural: n = 6 blocks, one model/site/task, unobserved `labels_only` cost, post-hoc gate thresholds (disclosed), and p ≤ 0.07 being an exploratory criterion.
