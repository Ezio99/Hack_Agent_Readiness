# Architecture, execution paths, frozen artifacts and consolidation audit (Task 015f)

Baseline: the tip of the Task 015 PR stack (#26, commit `1f75277`) — the only tree that contains all current code. Companion: [Report 015f](../collaboration/reports/015f-consolidation.md) (what changed, metrics, test results). Historical snapshots are in [archive/](archive/).

## 1. Integration baseline (stacked PRs)
`main` (`d8132e9`) ← **#22** Task 015 product ← **#24** pilot/experiment driver ← **#25** pilot results ← **#26** corrected main-stage proposal + verification ← **Task 015f** (this work). **#23** (future-work roadmap, one docs file) is independent. A scratch-worktree dry run merged #22 → #24 → #25 → #26 → #23 into `main` with no conflicts (59 files, +6,174/−101 vs `main`). Recommended order: merge bottom-up with merge commits (squashing would orphan the stacked bases) and retarget the next PR to `main` after each lands. Nothing is merged without the owner's approval; 015f touches no existing PR branch.

## 2. Layers (dependency direction: top depends on bottom)
```
interfaces   cli.py + {scanner,suite,remediation,experiments}/cli*.py  ·  scanner/service (FastAPI+SQLite)  ·  dashboard/ (React)
product      remediation/{probe → findings → library → engine/lifecycle, execution, discovery, targets}
experiments  experiments/ (Task 012)  ·  remediation/experiment.py (Task 015)  ·  webarena/ (Task 014)  ·  scanner/live.py (Task 011 validation)
execution    scanner/execute.py (one scan: mock|live) → agent.py (Browser Use) + capture.py (pre-send guard) + compat.py (prose-prefix parser)
environments environments/electronics + suite/{core,registry,runner}  (domain-neutral contract; oracles never import the app)
safety       ledger.py (durable USD ledger, Halt) · spend_gate.py (per-request reserve-before-send) · budget.py (A$50 programme ledger)
legacy       storefront/inventory/tasks/evaluator/contracts/oracle/metrics/runner/smoke/pilot/probe/server  (Tasks 003–007, byte-pinned)
```

## 3. Execution paths (what overlaps, and what is deliberately kept)
| path | module | status | notes |
|---|---|---|---|
| single-site live run / smoke | `runner.run`, `smoke.py` (`readiness run|smoke`) | historical, byte-pinned | reproduces Tasks 003–007; CI runs `readiness smoke` |
| Task 006/007 pilot driver | `pilot.drive` | historical | reproduces the 30-run Task 007 evidence |
| scripted suite smoke | `suite/runner.run_scripted` | current test tool | no model |
| **one scan, mock or live** | `scanner/execute.execute_scan` | **current core** | used by the service, Task 012/015 drivers, live validation; optional `request_gate` |
| Task 011 live validation | `scanner/live.run_fixtures` | executed once; evidence tooling | uses `ledger.Ledger` |
| Task 012 experiment | `experiments/driver.run_stage` | executed Stage 1; schedule/manifest hashes frozen | stage-matrix design, its own `ExperimentLedger` |
| Task 015 experiment | `remediation/experiment.run_stage` | current; main stage on hold | arm design, manifest-hash approval, halts final |
| WebArena | `webarena/live.run_live` (live, gated), `webarena/runner.run_task` (mock spike) | Task 014 evidence tooling | `run_task` is the older mock-only path kept for Report 014 reproducibility |
There are three experiment drivers (011/012/015). They share `ledger`, `spend_gate`, `budget` and `execute_scan`, but differ in design (fixture list / stage matrix / arms) and each is tied to frozen evidence; merging them is **deferred** to when Task 016 defines the next experiment shape (see §6).

## 4. Frozen, pinned and historical artifacts (never edited; how each is verified)
| artifact | verification |
|---|---|
| Legacy Task 003–007 code: `storefront.py inventory.py tasks.py evaluator.py contracts.py oracle.py` + `templates/{base,detail,listing}.html` | SHA-256 pins in `tests/test_suite_core.py`; Task 006/007 schedule hashes; profile v2/v3 file hashes (`tests/test_profile_v3.py`) |
| Task 012 Stage 1: schedule `96e459ad…`, manifest `0ef0386c…`, results | `tests/test_experiment_infra.py`, Report 012b |
| Task 015 pilot: manifest `25a22bfd…`, audit baseline, rows, gate (`stop`), effect record, ledger, status, re-audit | 8 files pinned byte-for-byte in `tests/test_remediation_main_design.py`; erratum is a separate file |
| Task 015 proposed main stage (on hold): manifest `11c7b4ec…` + 12 frozen source/config files (`experiment.FROZEN_FILES`) | `experiment.load_manifest` + `code_hashes()` drift check: **0 drift after 015f** |
| Programme budget ledger | `collaboration/budget/programme-ledger.json`; `tests/test_remediation.py` |
Consequence: the 12 frozen source files (`remediation/{probe,findings,library,engine,experiment}.py`, `spend_gate.py`, `capture.py`, `scanner/execute.py`, `profiles/suite-v2-compat1.json`, `environments/electronics/{tasks,catalog,variants}.py`) were deliberately **not** edited in 015f. Any cleanup that needs them is deferred to a deliberate re-freeze (§6).

## 5. Consolidation audit and decisions
| item | class | what/why | risk |
|---|---|---|---|
| `Halt`, `Ledger`, `cost_of` lived in `scanner/live.py` (a Task 011 feature) but were imported by 7+ modules | **consolidate (done)** → `ledger.py`; `scanner.live` re-exports | safety primitives get a neutral home; dependency direction fixed | none: identical code, re-export keeps frozen importers working |
| two verbatim copies of the live `preflight` (scanner.live, webarena.live) | **remove duplicate (done)** | one implementation | tests patched to the single location |
| `cli.py` — one 299-line `main()` mixing 12 command groups | **refactor (done)** | scanner / suite+serve-env / audit+remediation-experiment / experiment own `register()` + `main()`; legacy single-site commands stay (tests patch `cli.run`, `cli.load_repo_env`) | CLI surface unchanged (same names/options/help); 324 CLI-related tests green |
| dead imports (13), unused `scan_timeout_grace_seconds` config field, unused `metric` lambda, empty tracked `Initial.md` | **remove (done)** | noise | none |
| `bs4` imported by the site probe but undeclared; `pydantic-settings` never imported | **fix / preserve (done)** | declare `beautifulsoup4`; keep `pydantic-settings` (pinned browser-use imports it undeclared — now commented) | `pip check` clean; CI installs `requirements.lock` (already pins both) |
| dashboard Site-audit panel hard-coded a stock objective | **remove stock coupling (done)** | default empty, optional | 53 Vitest green |
| STATUS (102 lines of dated checkpoints), COLD_START handoff (21 dense lines), README (205 lines describing Tasks 003–005) | **consolidate docs (done)** | rewritten concise; full originals archived verbatim under `docs/archive/` | no test depends on them |
| legacy stack (Tasks 003–007: ~1,900 lines + 13 test files) | **preserve** | byte-pinned, reproduces completed evidence; dormant, not dead | moving files would change pinned bytes/imports |
| Task 012 `experiments/`, Task 011 `scanner/live.run_fixtures`, `webarena/runner.py`, `scripts/webarena_*.py` | **preserve** | produced/reproduce Reports 011b/012b/014; executed once | — |
| `vulture`'s ~50 "unused" findings | **no action** | all false positives (FastAPI handlers, pydantic/dataclass fields, ASGI attrs) except those removed above | — |
| `scanner/diagnostics.py` website rules keyed on the variant label (availability/specs); `NewScan` registered variants | **defer** | label-coupled findings are exactly what the audit engine replaced; removing them changes scan output and the Scanner tab | needs owner review (behaviour change) |
| stock/electronics coupling inside the frozen files (`library` templates, `findings.ATTRIBUTES`, `experiment` arms/`CHANGES`, `targets.py` demo) | **defer** | the frozen proposal depends on it; refactor together with a deliberate re-freeze | would change `FROZEN_FILES` hashes and the manifest |
| frozen importers still reach `Halt/Ledger/cost_of` via `scanner.live` (`spend_gate`, `remediation/experiment`) | **defer** | works through the re-export; switch to `agent_readiness.ledger` at the next re-freeze | none |
| `experiments.ExperimentLedger` vs `ledger.Ledger`; `experiments/analysis` permutation test vs `remediation/experiment._sign_flip_p` | **defer** | duplicated concepts but each tied to frozen evidence | — |
| test suite runtime (≈15 min, mostly real-Chromium tests) and duplicated audit helpers across remediation tests | **defer** | no safe quick win; consider a `slow` marker | — |

## 6. Remaining stock/shop coupling (inventory for Task 016)
Domain-neutral already: `suite/core`, `remediation/{probe, engine, execution, discovery}`, `ledger`, `spend_gate`, `budget`, scanner service/store. Shop-specific: `remediation/findings.py` (ATTRIBUTES: availability, SKU), `remediation/library.py` (two stock/SKU templates), `remediation/experiment.py` (arms, tasks T1/T4, `labels_only`), `remediation/targets.py` (demo storefront, change table), `scanner/diagnostics.py` (variant-label rules), `environments/electronics`, dashboard text. Task 016 should add attributes/templates as data (new `AttributeSpec`/`Template` entries) and treat the experiment layer as pluggable per recommendation; do not edit the frozen files without re-freezing.

## 7. What Task 016 can reuse as is
`SiteProbe` (SSRF-hardened, same-origin, bounded, structural card detection) · the findings→library→engine/lifecycle pattern with fingerprints and derived measured-effects views · `ledger` + `spend_gate` + `budget` (reserve-before-send, A$ ceiling) · `execute_scan` (mock|live, gate, fidelity guard) · the scanner service with registered targets, ownership checks and the audits API · the dashboard Site-audit panel · the experiment driver's patterns (frozen write-once manifest, hash approval, void classes, final halts, derived-view effect attachment) · mock-provider testing (full pipeline without a key) · the WebArena live path for external benchmarks.

## 8. Remaining technical debt and integration risks
1. Three experiment drivers and two ledgers (§5) — merge when the next design is known. 2. Shop coupling in frozen files (§6). 3. `scanner/diagnostics.py` label-keyed rules (behaviour change needs review). 4. 15-minute test suite. 5. Probe heuristics proven on two markup families only (JS-rendered sites unsupported). 6. The stack (#22–#26 + 015f) must merge bottom-up; stale STATUS/COLD_START edits in the stacked PRs may conflict if reordered. 7. Moving any byte-pinned legacy file is intentionally impossible without updating the pins.
