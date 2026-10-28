# Task 008 — Standalone Agent Readiness Diagnostic Dashboard

**Status:** Stage A authorized for implementation; Stage B requires review before publishing trace exports.
**Date:** 2026-10-28
**Base:** `main` (Task 007 merged as `91933a2`)
**Product pitch:** [Agent Readiness pitch](../proposals/agent-readiness-pitch-discussion.md)
**Evidence:** [Task 007 reconciled report](../reports/007-availability-placement-pilot.md)
**Implementation owner:** Claude/Codex on a dedicated Task 008 branch. **No merge without explicit user approval.**

## Goal

Build a standalone, developer-facing web app that explains **what happened, why it happened, and what a website owner could change** when a Meta Muse Spark-powered shopping agent uses a site. The app is the product; the controlled storefront is the test fixture; the reference agent is the measurement instrument.

Optimize for the Meta Global Hackathon's three-minute demo and its rubric (Impact 30%, Meta AI 25%, Technical Depth 20%, Demo 25%). Use only measured evidence. Recorded replay must never be presented as live inference.

## Architecture

- **React + TypeScript + Vite**, standalone from the existing storefront, preferably under a clearly named frontend directory after inspecting repository conventions.
- **Static data initially:** read committed reconciled Task 007 metrics; no backend/database, no API key in browser, no live agent execution.
- Inspect repo structure and current data schema before choosing implementation details; keep the experiment runner, tests and frozen experiment unchanged.
- Make the UI usable on desktop and reasonably responsive, with accessible labels and clear chart legends.

## Stage A — Implement now (P0)

### Diagnostic overview

Render genuine Task 007 data, with definitions and limitations:
- 30 runs, **29/30 independent evaluator PASS** (A 15/15, B 14/15); a completed agent action is not the same as a correct answer.
- Arm A (availability on listing cards): **4.67 requests/run, US$0.0621 estimated cost/run, 22.9 s/run**.
- Arm B (availability only on product detail pages): **7.47 requests/run, US$0.0974 estimated cost/run, 27.2 s/run**.
- Five scopes: Kitchen, Bags, Home, Outdoors, Fern; three runs per arm per scope.
- Include success, model requests, calculated token cost, elapsed time, actual vs oracle-required detail visits, variability and failed-run verification shortfall. Use correct units and mark costs as **calculated estimates**, not bills.

### Controlled A/B comparison

- Show precisely what differs between variants: availability on listing cards (A) versus detail pages (B).
- Scope selector and per-arm comparison of task outcome, requests, visits and costs; show run-level evidence where available.
- Distinguish deterministic **website-required navigation** from unnecessary agent revisits and **agent–tool interface failures**.
- **Never report negative navigation overhead as efficiency**. Overhead = actual minus oracle minimum for **successful runs only**. For run 27 show required 3, observed 1, verification shortfall 2 and independent evaluator FAIL.
- Present an evidence-backed recommendation: surface availability on listing cards for stock-sensitive tasks, with explicit controlled-test limitations.

### Product framing

- Make the Meta Muse Spark model's central role visible and accurate.
- Explain that the current results come from one synthetic 20-product storefront, one model/framework, three repetitions per cell. No universal readiness score or claims about real websites.
- Clear navigation between overview, scope comparison and the evidence behind findings.
- No placeholder data disguised as real results.

## Stage B — Design/proposal only until separately approved

Build **recorded agent trace replay** after Stage A review:
- Select real successful A and B runs for the same scope and **Fern run 27** (failure).
- Timeline: model-visible observation (only if available), action, tool response, page/navigation state, per-step request/cost if recorded, and final independent evaluator outcome.
- Run 27: seven repeated `find_elements` calls; tool returned hrefs, but model-visible history retained only `Found 11 elements matching "a".`; agent exhausted step budget and answered an out-of-stock product. Attribute to **agent–tool interface**, not storefront.
- Raw browser traces are preserved **locally**, outside Git. Inspect schema and propose a **deterministic sanitized export**; no fabricated steps, screenshots, reasoning or missing fields.
- **Stop for user approval before committing or publishing any trace exports**. Enumerate export files and fields, inspect for secrets, private paths, user data, model text and licensing risks. Label all playback **Recorded experiment replay**.

## Technical constraints and data integrity

- Read `collaboration/reports/007-pilot-data/per-run-reconciled.json` and related verification scripts; avoid hand-maintained divergent numbers.
- Preserve Task 007 frozen artifacts, code and results; no reruns or changes to evaluator, protocol, model settings or experiment configuration.
- Distinguish protocol raw-valid (50/182), compatibility-recovered (132/182), rejected (0) from task correctness.
- The tool-output visibility loops occurred in three runs (18 repeated calls in total), but not all observed extra effort is a website defect.
- Use lightweight deterministic checks for headline data and UI calculations; run existing offline tests.
- No new billable model calls. No broad dependency or infrastructure expansion without explaining need.

## Workflow

1. Inspect `main`, existing task conventions, reconciled data and pitch.
2. Create a dedicated `task008` implementation branch (do not develop directly on `main`).
3. Implement **Stage A only**: standalone dashboard, real data, A/B comparisons and recommendation.
4. Validate local build, data consistency and offline tests; provide screenshots and local run commands.
5. Return Stage B sanitized replay export proposal, including exact files/fields and risks.
6. Open PR for review; **do not merge** and **do not publish trace exports** without explicit approval.

## Stage A acceptance criteria

- Standalone app starts with documented commands and builds successfully.
- Numbers reconcile to Task 007 report and underlying committed per-run data.
- A/B comparison and diagnostic recommendation are clear to a non-researcher.
- Run 27 is visibly an independently evaluated failure, not a success or efficient short path.
- Cost labels say estimated/calculated; trace replay is not simulated or claimed live.
- No model calls, no experiment modifications, no secrets or raw local artifacts committed.
- Existing tests pass, or any unrelated failures are reported with evidence.

## Explicit non-goals

Arbitrary URL scanning; new experiments; multiple models; checkout; public registry/API; composite readiness score; larger synthetic storefront; production backend; live model execution. These require later decisions.

## First response requested from Claude/Codex

Briefly confirm the chosen frontend directory and existing data contract, then implement Stage A on a branch. Return changed files, build/test commands and results, screenshots, PR link, and Stage B export proposal. Stop for review.
