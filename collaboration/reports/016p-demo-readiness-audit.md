# Demo-readiness audit and spending reconciliation — 2026-11-01

Experimental development is frozen. S1 is accepted as completed sensitivity evidence. No further paid calls, merges or deployments authorized. This audit changed no UI, experiment implementation, grading or verdicts.

## Verification and publication

Reviewed `b6d7534`: 12 intended implementation/profile/test/handoff files. Reviewed `f61c02a`: three report/handoff files. Neither includes raw S1 artifacts, private truth, credentials or generated trial data. Both were pushed to `live-m1-llm-evaluation`; PR #60 remains draft and unmerged. Tracked tree was clean before this administrative work; the two known untracked prototype paths are unchanged.

2,239 protected historical files still match the pre-implementation SHA-256 inventory. The programme ledger amendment below is explicitly owner-authorized; previous entries, historical USD figures, exchange assumption and all runtime ledgers are preserved. No verdict changed.

## Spending reconciliation

| Item | Fork ledger total US$ | Imported history excluded US$ | New programme entry US$ |
|---|---:|---:|---:|
| Original Ironbark source, counted once | 0.864825 | 0 | 0.864825 |
| EXP-C | 2.002855 | 0.864825 | 1.138030 |
| R1 | 1.935751 | 0.864825 | 1.070926 |
| S1 sensitivity | 2.002312 | 0.864825 | 1.137487 |

The three experiments add US$3.346443. Including their previously unrecorded source once adds US$4.211268 to the earlier US$4.137830 subtotal. **Recorded known-spend subtotal US$8.349098 = A$12.5236 at the unchanged assumed 1.50 conversion.** This is neither a bill nor a fully reconciled whole-programme total. Earlier L0/L1a/EXP-B/EXP-2, taskgen smoke/stray exposure and replay items remain explicitly marked unreconciled; the apparent A$37.4764 balance is against recorded entries only and is not authorization or a verified available budget. No imported fork balance is counted twice.

## Audit evidence and limits

Read current dashboard, export/target/goal interfaces and second-target documentation. Ran all dashboard tests: **138 passed**. Budget test: **1 passed**; broader accounting/remediation checks: **26 passed, 8 deselected**, 5.74 s outside the sandbox. The initial broader run had 19 passes before a loopback socket permission error; its bounded unsandboxed retry passed. Browser-inspected the actual existing Vite app at 1365×900 with no backend configured, then loaded a read-only S1 export through its real file picker. Both loaded without page exceptions or error alerts. Saved local inspection images `/tmp/demo-first-screen.png` and `/tmp/demo-impact.png`. No evaluation, backend, model or paid call was started. Existing source files were unchanged by the browser audit.

The first screen is polished, but its first large message is a yellow technical service-configuration warning, followed by a file picker and multiple synthetic-data notices. The product hero starts substantially below these. It defaults to synthetic cabin data with 12→4 / 13→4 examples, not accepted Ironbark evidence. Thus value is understandable within 15 seconds once read, but credibility/setup distractions dominate the initial view.

The S1 report loads reliably without a backend. Starting a complete real evaluation is inappropriate for a two-minute demo: S1 alone took several minutes, live calls are now forbidden, and the UI-started grant deliberately excludes fix/retest stages. Use recorded evidence to demonstrate the complete loop, with a clearly labelled optional mock plumbing demonstration outside the timed pitch. No promise of arbitrary-URL ingestion: only registered snapshots exist.

The five-part report architecture already covers site → tasks → recommendations → change → impact. Evidence labels, independent grading, owner-selection disclosures, inert captured pages and highlighted side-by-side changes are strengths. However, action-by-action agent behavior is absent from this investigation export; effort counts and IDs substitute for an inspectable action story. The separate historical replay concerns Task 007, not current Ironbark.

## Prioritized implementation plan (proposals only)

Estimates are focused engineering time, including local checks; no paid experiments are included.

| Priority | Action and concrete target | Why / acceptance | Estimate |
|---|---|---|---|
| P0 | Establish a read-only recorded-demo entry in `dashboard/src/pages/Investigation.tsx`, `LivePanel.tsx`, `App.tsx`; reuse `lib/reportStore.ts` | Hero and one accepted recorded case first; setup/live controls secondary. Default must not silently present synthetic data as current evidence. Distinguish previously real model execution from running live now. Provide a reviewed portable export and rehearse reload/open from a fresh tab without backend. | 2–3 h |
| P0 | Correct generic evidence labels in `Investigation.tsx` (`provenanceOf`, `Hero`, `Cell`) and `lib/investigation.ts` (`tally`, `classifyOutcome`), with relevant existing UI tests | `provenanceOf` currently labels any all-live-mode dev-provider export “LIVE EXPERIMENT · real model trials”, despite its DEV PROVIDER notice. Headline/table passes count strict `passed` without checking `evidence_backed`. Show separate answer-match and evidence-supported outcomes; do not change grading. This matters especially for Flask. | 1.5–2.5 h |
| P0 | Replace stale verdict explanations and simplify comparison in `Investigation.tsx` (`ExploratoryPanel`, `Comparison`, `ResultCard`) and its tests | Rendered S1 falsely says “only two tasks that can be affected”; S1 has four. Derive sample/arm labels, preserve frozen verdicts, expose contemporary 2/4→3/4 beside 50→29 requests, and state “no website improvement established”. Keep compat1 historical comparison visibly separate from compat2 contemporary arms. Avoid headline request savings without outcomes and failure context. | 1.5–2 h |
| P0 | Provide one short safe action/evidence storyboard in `Investigation.tsx`, `lib/investigation.ts` and `src/agent_readiness/investigate/export.py` | Show selected task → agent navigates/reads → missing field/evidence → proposed change → observed retest. Derive a reviewed compact summary from recorded evidence; preserve exporter exclusions for raw traces, secrets and truth. Explicitly label owner-selected proposal and scroll fallback as tool behavior. Do not build a new replay platform. | 2–3 h |
| P1 | Make targets drive defaults/copy in `LivePanel.tsx` and `live/targets.py`; adapt `Investigation.tsx` site description | Goal defaults to comparing hire prices/availability even on Flask; available pricing/availability claims must match captured verifiable fields. Copy also says “customer tasks” and “Ironbark only”; captured-page panel calls every site a controlled test business. Keep general views neutral, with honest target-specific descriptions. | 1–1.5 h |
| P1 | Prepare an honest Flask second-target card and reproducible local asset checklist using `docs/SECOND_TARGET.md`, `live/targets.py`, `Investigation.tsx` | Saved Flask snapshot exists locally but is Git-ignored; no persistent Flask run is present under the live root inspected. Evidence so far is dev-provider plumbing: four strict answers without required model-visible support. Present portability of inspection/task contracts, not validated autonomous performance or a discovered defect. No fabricated result and no new paid run. | 1–2 h |
| P1 | Reduce navigation overload in `App.tsx`, `Investigation.tsx`, `components/Storefront.tsx`, `styles.css` | Keep current evidence primary and historical tabs secondary. Improve page selection for 75-page docs; static frame links are intentionally inactive, so make navigation obvious. Retain explicit styling-only presentation-mode disclosure. Verify sticky headings, fresh-tab reload, no-API mode, file error/recovery and laptop viewport. | 1–2 h |
| P1 | Write/rehearse a two-minute runbook in a new demo document; align `README.md`, `dashboard/README.md`, `docs/LIVE_M0.md`, `docs/LIVE_M1.md` | Setup docs and PR originally claimed no real model invocation; now stale. Freeze reviewed exports and provenance, close live controls, rehearse without external services, keep a clearly labelled backup. No hosting/deployment assumed. | 1 h |
| P2 | Trim dense IDs, explanatory duplication and owner-oriented jargon in `Investigation.tsx`, `components/ui.tsx`, `styles.css` | Main view: task, observation, suggestion, changed page, result and uncertainty. Details retain IDs, p-values, budgets and trace references. Improve keyboard/narrow-screen behavior after P0/P1. | 1–2 h |

P0 total approximately 7–10.5 h. Full plan approximately 12–18 h; sequence small reviewed increments and cut P2 first.

## Suggested judge narrative (120 seconds)

0–15 s: “We show developers where AI agents struggle on their site, link the diagnosis to evidence, and test proposed fixes.”

15–45 s: One recorded Ironbark task and observable behavior; distinguish website observations from agent/tool limitations. The tested three-field change was owner-selected, not an autonomous verified finding.

45–85 s: Original/changed listing side by side. Under the same compat2 instrument: placebo 2/4 evidence-supported passes versus patched 3/4, requests 50 versus 29. Explain “promising differences, not established improvement”; frozen inconclusive and exploratory not supported remain visible. S1 stays a sensitivity experiment.

85–105 s: Flask as a separate saved-documentation target; explicitly offline dev-provider plumbing, not a successful real-model benchmark. Show what it can inspect and what remains unsupported.

105–120 s: Meta’s demonstrated role in real Ironbark task generation/browser decisions/investigation; independent grading and inspectable evidence as the product’s value. Close on a developer decision, not a universal score or a claim that this fix is proved.

No UI changes implemented. Stop for review before any demo work.
