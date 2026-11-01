# CODEX_HANDOFF — Agent Readiness (written 2026-11-01, from a Claude Code session)

Read `AGENTS.md`, `STATUS.md`, `docs/SECOND_TARGET.md` and `collaboration/proposals/EXP-C-ironbark-listing-terms-preregistration.md` first. **Verify against the repository; this document may age.** Where this text and the code differ, the code wins.

## 1. State
* Repo `Ezio99/Hack_Agent_Readiness`, branch `live-m1-llm-evaluation`, draft **PR #60** (not merged). HEAD at writing: `ef2cfe2` (all earlier work is pushed). This handoff is one further commit.
* Working tree: two **untracked** files left on purpose — `src/agent_readiness/investigate/prototype/` and `tests/test_termvalue_prototype.py` (C0b prototype, superseded by `taskgen/termvalue.py`; do not commit, may be deleted).
* Never use `git add -A` (`uv.lock` is deliberately untracked). `scanner-data/`, `.env`, `runs/`, `artifacts/` are git-ignored.
* Recent commits (newest first): `ef2cfe2` EXP-C cap tests · `8468a65` DEV PROVIDER banner/provenance · `19478ee` EXP-C driver + pre-registration · `787f160`/`baf2c83` second target (Flask) · `0250386` `term_value` kind · `521532a` P2a definition-list fact cleaning · `d8b53f9`, `1c42c7f` profile evidence correctness.

## 2. Product and architecture
Goal: an AI-agent website evaluator — autonomous tasks, browser evidence, independent grading, friction diagnosis, evidence-backed (and clearly labelled unvalidated) recommendations.
* `src/agent_readiness/investigate/` — the pipeline. `flow.py` (stages: inspect, taskgen, freeze, baseline_trials, trace, investigate, recommend, report, apply_fix, post_trials, evaluate, final_report); `inspect/` (crawl, `pagemodel.py`, `profile.py`: listing classification, hidden-control handling); `taskgen/` (criteria kinds `page_fact`, `reach_page`, `item_set`, `extremum`, plus opt-in `term_value` in `termvalue.py`; `gate.py` acceptance gate; `propose.py`; `goal.py` goal grounding); `trials/` (runner, attribution); `investigator/` (loop, tools, deterministic `verifiers.py`); `recommend/` (patch templates); `evaluate/` (frozen `design.py` paired-signflip-v1; `exploratory.py`); `sitemodel/` (`snapshot.py` content-hashed snapshot, `patch.py` constrained patches, `server.py` read-only mirror); `insights.py` (owner insights); `report.py`/`export.py`; `fork.py`.
* `src/agent_readiness/live/` — live product: `targets.py` (registry), `jobs.py`/`worker.py`/`api.py` (job manager, worker subprocess, API), `grant.py` (spend grants), `devprovider.py` (zero-spend loopback stand-in, NOT a model), `abtest.py` + `cli.py` (`readiness live ...`, including `ab-experiment`, `replay-investigator`).
* Shared safety: `ledger.py`, `spend_gate.py` (reserve-before-send), `agent.py` (Browser Use 0.11.13 adapter, profiles in `profiles/`), `netguard.py` (tests are loopback-only).
* Dashboard: `dashboard/` (Vite/React); not reviewed in recent work (`LivePanel.tsx` still has rental wording).
* Other: `exp2/` + `sites/ironbark/` (Ironbark generator and frozen EXP-2 — do not touch), `scanner/`, `remediation/`, `webarena/`.

## 3. Running things
* Python env: `.venv` (`.venv/bin/python`, `.venv/bin/readiness`). Credentials: `META_MODEL_API_KEY` in env or repo `.env`; never print/commit it.
* Tests (risk-based, per AGENTS.md): affected files first with a timeout, then `scripts/critical-tests.sh` (~1 min, 214 passed at HEAD, 17 deselected), `scripts/dev-tests.sh` (~2.5 min). Browser tests are marked `browser`; do not run browser/dashboard work concurrently. Dashboard: `cd dashboard && npx vitest run`. Full local run is rarely needed (sharded CI, `docs/CI.md`; CI was green on `52c0ae5`; later commits were not CI-checked here).
* Zero-spend end-to-end: `python -m agent_readiness.live.devprovider --root scanner-data/live --port 8199` then run the server per `docs/LIVE_M1.md`, or drive `JobManager` as in `tests/test_live_m1.py` and `tests/test_second_target.py` (real worker and Chromium, fixture "model"). Results from it say nothing about model behaviour.
* Offline free commands: `readiness investigate inspect ...`, `readiness live ab-experiment --id X --root R` (prints manifests, spends nothing without both `--approve-hash` and `--allow-model-calls`).

## 4. Targets
* **Ironbark** (`ironbark`): fictional equipment-hire storefront from `exp2.snapshot.snapshot("control")`; snapshot `d2824b210ed9e9d85dac527eb0b4eeb519540a70a7c59ff8690c204ff677538f`. Rental goal lexicon (`live/lexicon.py` `RENTAL`), `term_value` OFF. Its taskgen request/schema/prompt hashes are pinned in `tests/test_term_value.py` and must not change silently.
* **Flask docs** (`flask-docs`): saved snapshot of a self-built Sphinx docs site (BSD-3), 75 pages, hash `b6aa1a496a28ce1d87ecf89caa470548bb14c9d698c1d1483a50a3004a104519`, loaded from `scanner-data/targets/flask-docs` (machine-local, git-ignored; rebuild with `scripts/capture_docs_snapshot.py`, see `docs/SECOND_TARGET.md`). Neutral lexicon, `term_value` ON. Only the offline dev-provider run exists (4 `term_value` tasks accepted, 4 trials, all `success_unsupported` because the model-visible view of long pages is truncated). No paid Flask run.
* No URL-ingestion feature exists by design.

## 5. Experiment infrastructure and spend safeguards
* Every paid stage presents an **approval manifest**; the exact sha256 must be approved (`approvals.jsonl`) and the pipeline refuses to start otherwise. Live jobs use a **grant** (`live/grant.py`). Spend is reserved before send in a durable fsync'd ledger (`spend/ledger.jsonl`) with per-request, per-trial, per-arm, combined and ledger-ceiling caps; a refused or over-bound trial is void and halts the stage. Retries 0.
* Forks (`investigate/fork.py`) import frozen tasks + baseline trials + full spend history, never approvals; `--carry-investigation` also carries the investigator and marks `inspect` done.
* EXP-B machinery (owner-selected labelled proposal, unmodified-repeat "placebo" arm, counterbalanced order, control-integrity checks, exploratory rules `exploratory-listing-v1`) is what EXP-C/R1 reuse. The frozen rule `paired-signflip-v1` cannot reach "improvement" with 4 pairs (minimum p 0.125 > 0.10).
* Programme ledger `collaboration/budget/programme-ledger.json` has **not** been updated for L0, L1a, EXP-B, EXP-C or R1. Ceiling A$50 is a limit, not an authorization. Calculated cost is not a bill.

## 6. EXP-C and R1 (real model `muse-spark-1.3`, profile `suite-v2-compat1`)
Intervention: owner-selected, EXPERIMENTAL, not a verified finding — show `refundable deposit`, `minimum hire`, `delivery and collection` on 9 listing pages' cards (252 lines, patched snapshot `40c5d886963c925a7b99ff721d7971d5ebacbc52d0237d9549febe301d74f1ed`, patch `406c0240…`, proposal `prp-2f3f998f8a`). Source/baseline: `scanner-data/live/live-2d58a80e14` (4 frozen tasks, all failed at 12–13 of 14 requests). Manifests: `apply_fix` `ac07d360c349cc73765c99b4d2b30300cd19ebe3d18279b7cf6c81bf72c0d8f2`, `post_trials` `05053088ef81a2ae2c0c4cce34bef74306416ff9b7e978281b7d93cbbf087d8c`. Caps: arms 0.80/0.80, combined 1.60, ledger ceiling 2.50.
* **EXP-C** — `scanner-data/live/live-ab-ironbark` (executed 2026-11-01 15:17–15:26 AEDT): spend US$1.138 (run total 2.003). Strict: unmodified 0/4 (baseline and placebo); patched 2/4 (delivery-required pass at 7 requests, minimum-hire pass at 7); requests patched 3/11/7/7 vs placebo 13/13/13/13. Frozen verdict **inconclusive** (p_requests 0.125); exploratory **not_supported**. One terminal `agent_failure` (invalid scroll).
* **R1** — `scanner-data/live/live-ab-ironbark-r1` (replication, identical manifest hash): spend US$1.071 (total 1.936). Patched strict 1/4 (minimum hire); two terminal invalid-scroll failures; frozen **inconclusive**; exploratory **consistent_with_h1**, but this is inflated by early tool failures counted as fewer requests. Treat as non-independent support.
* Pre-registration: `collaboration/proposals/EXP-C-ironbark-listing-terms-preregistration.md`. Do not modify these run directories, their verdicts or rules. Also never touched: `replay-4bad5b1b` (investigator replay of `live-2d58a80e14`; its corrected claim stayed an unverified open-ended hypothesis) and `live-2d58a80e14`, `live-46b6ba92b8`.
* Caution on interpretation: the improvement is suggestive for strict success, clearer for answer completeness and request counts on finished trials; n = 1 per cell, 4 tasks of one family, owner-selected change after seeing the baseline.

## 7. Pending: invalid-scroll investigation (read-only findings; nothing implemented)
* Browser Use `scroll(index=None|0)` scrolls the page; any other index must exist in the current step's selector map (indices on these pages are ~700–2,900) else it returns a hard error `Element index N not found in browser state`.
* The model emits an explicit `index` on every scroll (0 works; 1 and 888 never existed in any DOM; 1515 was real and worked). Of 28 scroll calls in the 8 patched trials, 10 were invalid. Not stale, not an adapter mismatch (clicks with real indices work), not snapshot structure — model action selection plus Browser Use strictness, made terminal by our `max_failures=2` (`agent.py`). Baseline/placebo never scrolled.
* Highest-deposit task fails strictly in all arms for **answer format** ("6m" vs "6 m"; or > 16 extra characters), not navigation. Do not weaken the grader.
* **Proposed (awaiting approval; NOT implemented):** `scroll_index_policy: "page-fallback-v1"` in a new profile `suite-v2-compat2` (invalid scroll index → page scroll, same result text, event logged/counted; schema and prompt unchanged), a declared/hashed profile-successor rule in `_check_control`, offline tests (unit with fake session, real-browser long-page repeated scroll, stale/invalid index, recovery, compat1 unchanged, Ironbark hash invariance), then one labelled sensitivity run **EXP-C-S1** (new fork of `live-2d58a80e14`, same tasks/snapshots/model/grader/order, one patched + one placebo per task, caps ≤ US$1.60, expected ~US$1.1–1.2), results never merged with EXP-C/R1.

## 8. Known defects and limitations
* Model-visible views of long pages are truncated/viewport-limited, so passes can be `success_unsupported` (all 4 Flask dev trials). Evidence rules must not be loosened to hide this.
* Goal analysis (`taskgen/goal.py`) is still Ironbark-shaped (`/category/` paths); the neutral exact-label rule is a minimal workaround for documentation targets.
* Listing-classification thresholds (50%/25%/2 pages) are provisional heuristics. Compact Ironbark taskgen prompt changed in `1c42c7f`: older taskgen approval hashes may be stale (recompute; STATUS.md notes it).
* Dev provider handler state persists across arms (meaningless request counts); the dev-provider investigator is a scripted stand-in; a `model: muse-spark-1.3` label still appears in dev exports (banner now says DEV PROVIDER).
* The exploratory rule counts early terminations as request reductions. `STATUS.md` lacks EXP-C/R1; the dashboard has rental wording and was not updated.
* Flask snapshot is machine-local; Flask yields only ~4 `term_value` tasks on one page.

## 9. Recommended next task and acceptance criteria
Task: implement the approved-in-principle scroll fix (section 7) **only after the owner approves it**, offline first. Acceptance: all section-7 offline tests pass; `compat1` behaviour byte-identical; Ironbark request/schema hashes and the EXP-C `post_trials` hash unchanged; `scripts/critical-tests.sh` green on the committed HEAD; manifest for EXP-C-S1 produced and printed (free) with caps ≤ US$1.60. Only then ask for approval of the S1 `post_trials` hash. Then: update `STATUS.md`, optionally write a `016`-style EXP-C report, and re-check CI on PR #60.

## 10. Deadline and priorities
Internal deadline **2026-11-04 23:59 Australia/Sydney**; official deadline 2026-11-05 is buffer (verify against official rules). Priorities: (1) trustworthy, evidence-backed analysis; (2) the second site (Flask) demonstrably working; (3) a reliable polished demo. Keep EXP work from displacing demo readiness.

## 11. Conventions
* Evidence correctness first: observations vs hypotheses vs unvalidated recommendations stay distinct; uncertain observations are classified, not silently dropped or promoted; the independent grader and verifiers are never weakened to make a result look better.
* Historical runs, frozen manifests, original snapshots, EXP-2/Task 005–007 code and the budget ledger are immutable.
* **No paid model call, hosting or deployment without explicit owner approval of the exact manifest hash** and `--allow-model-calls`; no merges without approval. Report outcomes faithfully, including failures, voids and confounders; separate dev-provider plumbing from real-model measurements.
* Commit small reviewable units; record the checks actually run; do not push or merge unless asked. Pre-event prototype provenance rules in `AGENTS.md` apply.
