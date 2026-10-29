# Report 015f — codebase consolidation (Task 015f / issue #27)

**Date:** 2026-10-29. Branch `task015f-consolidation`, based on the tip of the Task 015 PR stack (#26, `1f75277`); PR base = `task015-main-proposal`. **No paid call, merge, deployment or modification of historical evidence.** Architecture map, classification of every audited item, frozen-artifact register and Task 016 reuse guide: [docs/ARCHITECTURE.md](../../docs/ARCHITECTURE.md).

## Integration baseline
Open PRs form one stack: `main` ← #22 ← #24 ← #25 ← #26 ← this PR; #23 (docs roadmap) is independent. A scratch-worktree dry run merged #22 → #24 → #25 → #26 → #23 into `main` with **no conflicts**. This work starts from #26's tip (the only tree with all current code) and touches no other PR branch.

## What was done
| class | change |
|---|---|
| **Consolidate** | `Halt`, `Ledger`, `cost_of` (safety primitives imported by 8 modules) moved from `scanner/live.py` (a Task 011 feature) to **`agent_readiness/ledger.py`**; `scanner.live` re-exports them, so frozen importers (`spend_gate.py`, `remediation/experiment.py`) are unchanged. The verbatim duplicate live `preflight` in `webarena/live.py` removed — one shared implementation. |
| **Refactor** | `cli.py`'s single 299-line `main()` mixing 12 command groups: the scanner, suite/serve-env, audit + remediation-experiment and experiment groups now own `register()` + `main()` in their own packages (`scanner/cli.py`, `suite/cli.py`, `remediation/cli_impl.py`, `experiments/cli_impl.py`); `cli.py` keeps the historical single-site commands (tests patch `cli.run`, `cli.load_repo_env`) and a 4-line dispatch. CLI names, options and behaviour are unchanged. |
| **Remove** | 13 unused imports; unused `scan_timeout_grace_seconds` config field; unused `metric` lambda; the empty tracked file `Initial.md`; the hard-coded stock objective that pre-filled the dashboard Site-audit panel (now optional, empty by default). |
| **Fix** | `beautifulsoup4` is imported by the site probe but was undeclared → declared. `pydantic-settings` looks unused but the pinned `browser-use` imports it undeclared → kept and now commented in `pyproject.toml`. |
| **Documents** | `STATUS.md` 102 → 19 lines, `README.md` 205 → 47 lines (it described Tasks 003–005), `COLD_START.md` handoff rewritten; the originals are archived **verbatim** in `docs/archive/`. New `docs/ARCHITECTURE.md`. |
| **Preserved on purpose** | Byte-pinned legacy Task 003–007 stack; Task 011 live-validation driver; Task 012 experiment package; Task 014 WebArena tooling; every frozen/evidence/budget file; the frozen Task 015 source files (so the proposed main-stage manifest stays valid). |
| **Deferred (needs review)** | merging the three experiment drivers/two ledgers; stock coupling inside the frozen files; label-keyed rules in `scanner/diagnostics.py` (behaviour change); frozen importers switching to `agent_readiness.ledger`; test-suite runtime. See ARCHITECTURE §5–§8. |
Why not more: the audit found little genuinely dead code (vulture's ~50 hits were framework false positives). The real complexity is generational — completed experiments that are SHA-pinned, hash-frozen or cited as evidence. Moving or merging them would violate the evidence constraints or invalidate frozen manifests, so the safe simplifications are structural (ownership, duplication, entry points, documents), not mass deletion.

## Metrics (before = `1f75277`, after = this branch)
| metric | before | after |
|---|---|---|
| `cli.py` lines / `main()` lines | 314 / 299 | 148 / 124 (four command groups moved to their packages: +278 lines of owned modules) |
| files importing safety primitives from a feature module (`scanner.live`) | 8 | 4 (2 frozen files + 2 for the shared `preflight`) |
| verbatim duplicate code blocks removed | `preflight` ×2 | ×1 |
| `pyflakes` findings in `src` | 20 | 9 (all intentional: registration/availability imports, re-exports, frozen files) |
| `STATUS.md` / `README.md` lines | 102 / 205 | 19 / 47 (originals archived) |
| declared direct dependencies | 9 (+1 undeclared import) | 10 (all imports declared) |
| tracked junk | 1 empty file | 0 |
| total `src` Python lines | 8,237 | 8,277 (+40: moved code gained module docstrings; **line count is not the goal**) |
| tests | 675 | 675 (none removed; 3 monkeypatch targets updated for the single `preflight`) |

## Verification (all run on the final code)
- **Full Python suite (with the `webarena` extra): 675 passed, 0 failed, 114 warnings (third-party deprecations), 13 min 01 s.** Dashboard: 53 Vitest passed, `tsc` clean. `uv pip check` clean.
- **Frozen/historical evidence intact:** diff against the base is empty for all 12 frozen source files, `collaboration/experiments/`, `collaboration/budget/`, the byte-pinned legacy files and templates, and the profiles; `experiment.load_manifest` + `code_hashes()` on the proposed main manifest `11c7b4ec…`: **hash valid, 0 source drift**; the 8 Task 015 pilot artifacts are pinned byte-for-byte by tests that pass; the Task 006/007/012 hash tests pass; the programme ledger (A$6.2067 spent, A$43.7933 remaining) is unchanged.
- **CLI:** every command group still parses and runs (`suite list`, `scanner invitations`/`live-validate status`, `audit`, `experiment schedule`, `remediation-experiment plan|run|status`); 324 CLI/env/probe/scanner/remediation/experiment/pilot tests were also run in isolation after the CLI split.
- **CI:** see the PR (checks run on the final head).

## Remaining technical debt and integration risks
See ARCHITECTURE §8: three experiment drivers and two ledgers; shop coupling in the frozen files; label-keyed scan diagnostics; 15-minute suite; probe validated on two markup families; the stack must merge bottom-up. Risk of this PR itself: low — behaviour-preserving moves with identical code, re-exports for old import paths, and a full-suite pass; the only behavioural edits are the dashboard's empty default objective and the removal of an unused config field.

## What Task 016 can reuse cleanly
ARCHITECTURE §7: the SSRF-hardened `SiteProbe`; the findings → library → engine/lifecycle pattern (add attributes/templates as data); `ledger`/`spend_gate`/`budget`; `execute_scan` (mock|live with the gate); the scanner service + audits API + dashboard panel; the experiment patterns (write-once manifest, hash approval, void classes, final halts, derived-view effects); mock-provider testing; the WebArena live path. Start from `agent_readiness.ledger`, not `scanner.live`.
