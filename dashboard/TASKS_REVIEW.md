# Tasks page and progressive-disclosure review

Baseline: `18b5bd9` on PR #60. Navigation is Scan → Tasks → Insights → Improvements → Results. This is a read-only addition and label relocation, not live generation or an evaluation-engine change.

## Five-screen audit (performed before the UX simplification)

- Scan: keep website/task-count/friendly model cards and journey action. Move original experiment label, run ID and exact API model identifier to the existing report technical disclosure; friendly model name is product context.
- Tasks: keep exact prompts, selected-task context, owner-authored status and replay availability visible. Put selection/freeze/archive history, generation provenance and task/arm identifiers under Technical details.
- Insights: keep actions, selected-entry ordinal, playback status and inspector outcomes. Replace the main exact pace with “Illustrative timing · Not recorded timing”; move the unchanged 2.2-second interval, archive event number, source pointer, arm code and scroll-detail limitations into event Technical details. No timer or animation changes.
- Improvements: keep the explicit illustrative-footage disclaimer and owner-selected attribution. Existing patch identifiers and experimental outcomes are already under disclosure; leave them there.
- Results: retain metrics-first panels and stored verdict/methodology disclosure. Move the internal S1 experiment name out of the primary heading; it remains in Technical details.

## Task evidence and provenance

Task prompts are rendered directly from the existing public report projection (`id`, `question`), verbatim. No private criteria, answers, expected values, raw traces or generator payloads are read. Four tasks appear for the built-in example; only task-1/patched has public replay entries. The action is offered only for that sequence; other tasks explicitly show replay unavailable and cannot start a fabricated journey.

The built-in S1 task-authorship wording comes from approved `docs/HACKATHON_PITCH_DRAFT.md` (vision reconciliation and Muse task-generation roles): the four prompts are owner-authored, selected and frozen; S1 imported those tasks and did not rerun task generation/investigation. `investigate/taskgen/propose.py` implements model-driven candidate proposals, while `gate.py` accepts/rejects candidates independently. The Muse Spark capability explanation is conditional and separate from S1 authorship. It does not label S1 prompts model-generated or claim autonomous S1 generation. Imported reports receive unknown generation/freeze provenance rather than borrowing the built-in claim.

Tasks and the existing task selector share state. Stage-only navigation preserves the current event and pauses playback. Deliberately selecting a different task retains the established reset behavior; no per-task bookmark manager is added. The exact pace remains in Technical details and is unchanged at runtime. All source references and interpretation limitations are retained, not discarded.

## Validation / handoff

18 focused studio tests; full dashboard **153 passed, 7 existing skips**; critical **214 passed, 17 deselected** in 60.73s. TypeScript, production build and unchanged distribution guard pass (8 files, no replay directory or unapproved assets). No dependencies/config changes.

Fresh Chromium desktop/390px checks verify exact prompt list, keyboard navigation/disclosures, unsupported-task states, Tasks → Insights entry continuity, the current selected-task dropdown, Results details, Improvements disclaimer, imports/reloads and classic fallback. External requests are blocked. Real-clock desktop/mobile full-playback regression also rerun, including reduced motion, synchronization, pause/end/restart and manual selection; no clock acceleration or model calls. The public archive remains limited to one task/arm journey. [Tasks desktop](review/tasks-desktop.png) · [390px](review/tasks-narrow.png).

No live generation, editing, rerunning, new agent run, grading/evidence mutation, submission, merge or deployment. The original experimental verdicts/outcomes and private-data protections are unchanged. Owner review and post-push CI remain separate from local validation.
