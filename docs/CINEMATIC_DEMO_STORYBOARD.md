# Agent Readiness — cinematic demo storyboard v1

Status: **Checkpoint A / creative specification only**. Base: `049292e` (PR #60). No application, experiment, dashboard, or evidence changes.

## Product story

**Thesis:** The web is changing. Is your website ready?

**Promise:** Test how agents navigate a site, inspect their behavior, explore concrete improvements, and compare outcomes.

**Positioning rule:** Sell the capability. Demonstrate the behavior. Document the rigor.

**Format:** 16:9, approximately 180 seconds, voiceover + typography + composited UI + actual dashboard capture. No talking head, generic robot art, or uninterrupted scrolling walkthrough. Visual benchmark: polished developer-product launch.

## Visual system

- Canvas: 1920×1080, 16:9; safe text area 160px from horizontal edges and 100px from vertical edges.
- Background: deep navy/near-black (`#090F1C`), elevated surfaces (`#142235`), white (`#F6F9FC`), muted text (`#A8B8CC`), one cyan accent (`#68D5FF`). These are proposed palette tokens, not existing dashboard colors.
- Typography: clean sans-serif; one bold headline per scene, max 7 words where practical. Large metrics, sparse labels, generous spacing.
- Motion direction: 250–650ms purposeful transitions, one primary focus at a time; subtle glow, no gratuitous particles. Reduced-motion-friendly static fallback.
- Product navigation language: **Scan → Insights → Improvements → Results**. This is the target presentation vocabulary, not a claim that current dashboard already uses these labels.
- One primary visual anchor per frame. Avoid dense methodology, repeated caveats, or paragraphs on screen.

## Six scenes

| Time | Scene / headline | Composition / transition | Spoken idea | Provenance |
|---|---|---|---|---|
| 00:00–00:20 | **The web is changing.** | Illustrative user prompt to find rental equipment; stylized agent/browser movement across listings; focus on hard-to-find terms. Browser nodes collapse into a trace. | AI agents increasingly act on websites; developers need to understand how well sites support them. | **Illustrative concept**, not S1 footage or Meta personal-agent UI. |
| 00:20–00:35 | **Meet Agent Readiness.** | Trace morphs into the Agent Readiness wordmark; four-stage workflow appears. | See how agents use a website, find friction, test improvements. | Product positioning; do not imply production Meta integration. |
| 00:35–01:25 | **See what agents actually do.** | Transition to actual recorded Ironbark report. Highlight task, nine-event allowlisted storyboard, archived action evidence. Zoom one real event. | A reference agent performs a task; independent code checks evidence and outcomes. | **Recorded S1 data**. Scroll-index fallback is a browser-tool interaction, not a verified website defect. |
| 01:25–02:05 | **Turn observations into action.** | Show actual owner-selected improvement card. Separate illustrative listing-card layout reveals existing deposit, minimum hire and delivery terms. | Surface important existing rental facts directly on listing cards. | Owner-selected change; illustrative listing cards are **not captured website screenshots or a real before/after diff**. |
| 02:05–02:40 | **See what changed.** | Actual S1 comparison rows; animate 2/4 → 3/4 evidence-supported passes and 50 → 29 model requests. Compact persistent label: `Exploratory comparison · Improvement not established`. | Recorded modified arm had one more supported pass and 42% fewer requests in this run. | Contemporary S1 arms only; small inconclusive comparison, not proof of causal/general improvement. |
| 02:40–03:00 | **Ready for the agentic web.** | Four stages converge; product mark and tagline; concise end card with repository/product link only if verified and publicly accessible. | Agent Readiness provides a feedback loop for developers building for agents. | Vision, not claim of universal score or full autonomous S1 pipeline. |

## Static scene deliverables for Checkpoint A

Produce **six individually inspectable 1920×1080 static frames**, named `01-hook` through `06-vision`, and a contact sheet. These are design references, not final recorded footage. Include a clear provenance note for each frame in a sidecar README. Prefer editable HTML/CSS/SVG source in an isolated `demo-film/` directory; don't alter dashboard source.

Before proceeding to motion, review legibility at 50% scale, visual consistency, clear differentiation of illustrative versus recorded content, and whether each frame communicates its point in under three seconds.

## Non-negotiable boundaries

- Do not edit frozen task truths, evaluator, grading, experiment ledgers, S1 public asset, or stored verdicts.
- Do not fabricate website captures, page diffs, agent tool calls, live inference, verified investigator recommendations, or Meta production integration.
- No paid model calls, merge, deployment, submission, or modification of PR #60 without explicit owner approval.
- Preserve `049292e` as fallback; work on `demo-cinematic-storyboard` only.
- Do not start animation/dashboard refactoring until Checkpoint A visuals have been reviewed.

## Approval gate

Checkpoint A is complete when six frames + contact sheet + editable source exist and the owner approves the look. Checkpoint B (animation) is a separate decision.

## Configurability requirement (added before Checkpoint A implementation)

The film must be **data-driven**, not a hardcoded S1-only composition. Separate three layers:

1. **Evidence adapter:** Load an explicitly selected, existing, validated recorded evaluation/report through a read-only adapter. Preserve task outcomes, request counts, source event references, provenance and uncertainty/verdict metadata. Never invent missing fields.
2. **Demo manifest:** A human-reviewed configuration selects the report/run, featured task/event sequence, scene order, headline copy, voiceover copy, visual emphasis and optional scene visibility. Store presentation text separately from evidence. Mark illustrative content as such.
3. **Reusable scene components:** Render static frames from the manifest and adapter. Metric values and denominators must be derived from the selected report, never embedded in scene markup. Handle varying task counts, missing optional fields and longer numbers gracefully.

For Checkpoint A, supply a sample manifest pointing at the existing S1 report and a small, documented schema/interface. **Do not create a new report or change evidence data.** If a complete automated adapter is too large for Checkpoint A, implement a minimal read-only fixture adapter with source references and clearly document the remaining adapter work; don't pretend it supports arbitrary reports yet.

No automatic cherry-picking of the best-looking run. Switching runs must be an explicit editorial decision, and results, qualifications, labels and narration must remain consistent with the selected evidence. Avoid causal language when a report's verdict doesn't support it.

Acceptance check: changing the manifest's featured task and presentation copy must not require changing scene source code. A later validated report should be swappable through a documented data adapter without redesigning the six scenes.
