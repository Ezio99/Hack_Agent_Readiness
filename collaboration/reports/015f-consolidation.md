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

---
## Review follow-up (2026-10-29, after the owner's review of PR #29)

### 1. Owner decisions applied
Keep the three historical experiment drivers and the stock-specific frozen code **intact** (ARCHITECTURE §5 now says *preserve*, not *defer*). General-purpose scan diagnostics and broader website-probe coverage are **carried into Task 016** (ARCHITECTURE §8), which is to be a substantial but feasible autonomous-investigation implementation (issue #28), not a minimal MVP.

### 2. The "removed wheel file" — a mistake of mine, now corrected
Two of my consolidation commits used a bare `git add -A` and accidentally **committed two files that must not be tracked**: a stray `nothing-0.0.3-py2.py3-none-any.whl` (1.5 KB, produced by a leftover `pip download nothing` probe command in the repo root) and `uv.lock` (392 KB; deliberately untracked per STATUS). A follow-up commit removes both (`uv.lock` stays on disk) and `.gitignore` now ignores `uv.lock` so this cannot recur. They remain in that branch's intermediate history only; the PR's net diff contains neither (`git diff --name-status` shows no such file). No documented workflow referenced either file.
**Install/offline verification (fresh checkout + fresh venv):** `uv venv --python 3.12` → `uv pip sync requirements.lock` → `uv pip install --no-deps --no-build-isolation -e .` → `uv pip check` ("All installed packages are compatible", 117 packages) → `readiness --help`, `readiness suite list`, `import bs4, agent_readiness.remediation.probe` all work; the built metadata lists `beautifulsoup4>=4.12`. `requirements.lock` is **unchanged** (it already pinned `beautifulsoup4==4.15.0` and `pydantic-settings==2.15.0`), so the documented install (requirements.lock, network or a package cache) and CI's install steps behave exactly as before; the dependency change adds a declaration, not a new package. CI itself ran those exact steps green on the earlier head.

### 3. Independent code review of PR #29 (code-review skill, medium) — findings and dispositions
| # | finding | verdict | action |
|---|---|---|---|
| 1 | `cli.py` imported every command-group tree at parser-build time: CLI start-up 0.55 s → 1.6 s, and an import error in one feature would break all commands | **valid (introduced by 015f)** | heavy imports made local to the handlers; `register()` is cheap. Start-up measured **0.50–0.53 s** (before 015f: 0.52–0.61 s) |
| 2 | `preflight`/`VERIFIED_PRICES` (core live safety check) still lived in `scanner/live.py`; three drivers depended on each other's modules for it | **valid** | moved next to the ledger (`ledger.py`); `scanner.live`/`webarena.live` re-export for existing and frozen importers |
| 3 | default ceiling "defined twice" (`DEFAULT_CEILING_USD` vs `CEILING_USD`) | **partly valid** (the second is an alias) | `scanner/cli.py` now uses `ledger.DEFAULT_CEILING_USD`; the alias remains for existing importers/tests |
| 4 | `audit()` residue: duplicate `json` alias, trailing `return`, `main` returning `audit()` | **valid, trivial** | cleaned |
| 5 | `readiness scanner live-validate` loaded the scanner config (creating a data dir and dev secret) although it only uses its ledger | **valid, pre-existing** | config is now loaded only by the subcommands that need it |
| 6 | dashboard audit panel no longer pre-fills a shopper task, so reports lack task-relevance flags unless the user types one | **valid** — a deliberate behaviour change (removes stock coupling) that my PR text under-stated | label now says recommendations are marked task-relevant only when a task is provided; PR description corrected |
| 7 | `beautifulsoup4>=4.12` loose in `pyproject.toml` while the probe is evidence-pinned | **acknowledged, not changed** | consistent with every other dependency (lower bounds in `pyproject`, exact pins in `requirements.lock`, which pins 4.15.0 and is what CI/README install); the probe source is frozen and its results do not depend on a particular bs4 minor within that range as far as tested |
The reviewer also found no undefined names and confirmed no frozen file was touched.

### 4. Fast development workflow (CI unchanged)
New `slow` marker (40 logic-level tests that still take > 1.5 s: whole mock pipelines, `plan()` with live probes) and `scripts/dev-tests.sh` = `pytest -m "not browser and not slow"`: **531 tests in ≈ 35 s** versus ≈ 14 min for the complete suite (`browser` was already excluded by `-m "not browser"`, which still takes ≈ 3 min). `tests/test_markers.py` guards that the markers are registered, that CI still runs exactly `-m "not browser"` and `-m browser`, and that no CI step filters `slow`. The full suite remains the PR contract.

### 5. Final verification on the final head
**Full Python suite (with the `webarena` extra): 678 passed, 0 failed, 114 warnings (third-party deprecations), 15 min 14 s** (675 + 3 marker-guard tests). Dashboard: 53 Vitest passed, `tsc` clean. The proposed main-stage manifest `11c7b4ec…`: hash valid, **0 source drift**; no frozen source file, pilot artifact, `collaboration/experiments/`, `collaboration/budget/` or `requirements.lock` differs from the base. CI results: see the PR checks on the final head.
