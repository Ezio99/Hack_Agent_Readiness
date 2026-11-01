# Checkpoint A data contract

This is a narrow local interface, not a general report-import platform. All paths below are relative to `demo-film/`, including when passing `build.py --manifest /path/to/alternate.json`. Sources must remain within this repository. The sample manifest is the complete example.

## `demo-manifest-v1`

| Field | Interface |
| --- | --- |
| `evidence` | `adapter`, `source`, SHA256, exact `run_id`, `proposal_id`, `original_arm`, `modified_arm`. Current adapter supports only contemporary `placebo` versus `patched`. Historical `baseline` is never aggregated. |
| `featured` | Exact `task_id`, `arm`, ordered `event_refs` JSON pointers such as `/storyboard/steps/5`, and optional `focus_ref` within that selection. Repeated event numbers remain distinct by source index. Selection is explicit; no automatic ranking or cherry-picking. |
| `captures` | Optional provenance sidecar and proposal binding. Actual report UI crops are reused only for the same source SHA/proposal; storyboard also requires the archived task, arm and full event-reference sequence to match. Omit for another report. |
| `presentation` | Brand, workflow labels, verified repository URL/date, illustrative goal/action/field labels and their editorial source. Field labels are concepts, never asserted to be captured pages or rental values. Review them when changing targets. |
| `scenes[]` | Array order determines contact sheet/frame order. Unique `id` (`NN-name`), reusable `component`, `visible` boolean, time range, headline line array, optional eyebrow/body line array, provenance caption, voiceover template and emphasis. |

Components: `hook`, `product`, `behavior`, `improvement`, `results`, `vision`. Emphasis values: `concept`, `workflow`, `focus-event`, `sequence`, `illustration`, `metrics`. Behavior `sequence` de-emphasizes the focus card; `focus-event` highlights it. Other emphasis values describe the component's static visual anchor. Long arbitrary prose still requires visual review; this is cinematic art direction, not an automatic layout engine.

Voiceover placeholders traverse the projected evidence, e.g. `{evidence.original.requests}`, `{evidence.task_count}`, `{evidence.featured.focus.text}`. Missing fields resolve to `unavailable`, not a guessed value. Presentation copy must be editorially reviewed alongside the selected report; templating does not certify claims. In particular, review owner-selected wording, illustrative labels and uncertainty narration on any report change.

## `film-evidence-v1` adapter output

- `source_sha256`, `run_id`, `label`, authoritative `provenance`.
- `rows[]`: task ID/question/source pointer and `original`/`modified` records with strict pass, evidence-supported pass, requests and trial pointer. Boolean false differs from missing/null.
- `task_count`: all source tasks, not only favorable tasks or tasks with complete data. All are included in aggregate metrics; if an arm has a missing/void/noncompleted trial or missing field, that aggregate field becomes unavailable. No silent denominator reduction.
- `original`/`modified`: sums of valid single-trial source values; `request_change_label` derives percentage change only when the original total is positive and both totals are present. Missing values render as an em dash. Strict and supported values remain separate; the visible metric is explicitly labelled evidence-supported.
- `featured`: task/arm, question, selected events `{event, category, text, ok, ref}`, focus and availability. Only allowlisted public event fields are projected. An unavailable task/arm storyboard yields no events/capture; it never borrows another task's sequence.
- `proposal`: ID, exact label, owner-selected flag, validation, basis and source pointer.
- `verdicts`: stored frozen and exploratory verdicts, unchanged. `uncertainty` preserves the report reason, rule ID/scope, storyboard note and demo note. No statistical rule is rerun. An inconclusive frozen verdict produces the persistent improvement-not-established label; other verdicts receive conservative “See stored verdicts” text, never automatic causal language.

Optional captures remain separate from normalized evidence. Captured UI includes its original typography and labels; composed fallback views are explicitly labelled composed, not actual UI screenshots. Large task sets show up to five outcome rows with an explicit remaining-count notice; aggregates include every task. Composed story views show up to eight selected entries plus an explicit additional-entry count. The initial S1 capture shows its complete nine-entry public sequence.

## Explicit report replacement

1. Select an already-validated, sanitized public report. This adapter requires `schema: investigation-dashboard-v1`, `audience: public-demo`, authoritative recorded/real-model provenance, a complete selected run and one trial per arm/task. Unsupported reports fail closed. This does not independently validate a new report's experimental integrity or sanitation; that review must already have happened.
2. Update manifest source/SHA/run/proposal and featured task/event/focus references explicitly. Do not change the old report. Keep other experiment histories separate. Omit `captures` for a new source unless authentic, separately reviewed UI crops with matching provenance are supplied.
3. Review all presentation/voiceover/illustration fields against the new evidence and its stored verdicts. The adapter provides facts and conservative labels, not a claim-writing system.
4. Run adapter tests, build and render; inspect all frames/narration. Headline and task selection changes need no component edits. Updated evidence of this schema needs no scene redesign. A different schema or repeated-trial model needs a new read-only adapter returning this interface, with focused tests and review.
5. Commit the manifest, projected data and regenerated exports together. Never claim a source change is a newly executed trial.

The replacement browser test changes the featured task/copy and exercises a missing-storyboard state, longer counts and missing metrics. Synthetic test variations remain in memory and are not saved as example reports or exported frames.
