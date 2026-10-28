# Report 013 — T1 diagnosis and experimental preparation (credential-free)

Branch `task013-t1-diagnosis`. Full technical write-up and the proposed experiment: [docs/TASK013_T1_DIAGNOSIS_AND_EXPERIMENT_PLAN.md](../../docs/TASK013_T1_DIAGNOSIS_AND_EXPERIMENT_PLAN.md). **No model call was made; Stage 1 results/configuration/artifacts are unchanged.**

## Changes
| Area | Change |
|---|---|
| Root cause | Browser Use 0.11.13 returns `find_elements`/`search_page` results with `long_term_memory` (count line) and no `include_extracted_content_only_once`; `MessageManager` then shows the model only the count line. Pinned by a test. |
| Reference agent | New `suite-v2-compat1` (`tool_result_visibility: read-state-v1` → `agent.apply_tool_result_visibility`); `suite-v1-compat1` and the frozen Task 012 manifest untouched; `execute_scan(profile_id)`, manifest/driver take the profile from the frozen manifest |
| Evidence/diagnostics | `t1-evidence-v2` requires SKU text; diagnostics separate not-observed / observed-but-misused / tool-interface / incomplete execution; gap detector aware of `<read_state>`; Stage 1 records not rewritten (offline re-evaluation: both Stage 1 T1 failures were SKU-blind) |
| Website | optional factor `sku` (`hidden` default | `listing`); new variant `…+sku-listing`; original four variants byte-identical (golden hashes) |
| Mock | `element_reader` scripted behaviour (uses link targets only if actually shown) |
| Proposal | Part A (8 runs: 5 × v2 + 3 × v1 control, T1/V0), decision gate, Part B (14 runs), Part C alternative, exact schedules and hashes (`docs/task013-proposed-schedules.json`) |

## Tests actually run
Full Python suite: **543 passed** (was 523). CI status: see the PR. New: `tests/test_tool_visibility.py` (4), `tests/test_sku_factor.py` (≈18), T1-evidence and diagnostics updates. A scripted/mock pass shows the mechanism delivers information; it is **not** evidence about live model reliability.

## Uncertainties / recommendation
Whether the live model uses the `<read_state>` content is unknown until Part A. If v2 baseline passes reliably, SKU-on-listing has no success headroom (only a mechanically expected effort effect) and the availability factor (Part C) is the better demonstrable improvement. Recommended next action: approve Part A only (8 runs, ≈US$0.7–1.3 expected, ceiling US$2.00), after the small driver/manifest extension for the reference-agent arm; decide B vs C from its data.
