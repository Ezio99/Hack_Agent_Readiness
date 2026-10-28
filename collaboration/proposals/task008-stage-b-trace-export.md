# Task 008 Stage B — proposal: sanitized recorded-trace replay export

**Status: PROPOSAL ONLY — nothing here is implemented, and no trace export may be committed or published until the user approves the file list, fields and risks below.** Prepared with Stage A (branch `task008-dashboard-stage-a`). Raw run artifacts stay local under `runs/pilot-task007/` and are never committed.

## What the replay is for
A timeline that lets a reviewer see, step by step, what the Muse Spark agent saw, decided and did, and where the effort went, labelled **Recorded experiment replay** (never live, never simulated). Three runs, all real:
| Replay | Run | Why |
|---|---|---|
| Fern, arm A | `25-s02-A1` (PASS, 4 requests, overhead +1) | availability on the listing: 1 required page, one revisit |
| Fern, arm B | `26-s02-B1` (PASS, 8 requests, overhead 0) | availability only on detail pages: filter, Picnic Blanket → Reading Lamp → Trail Daypack, minimum path |
| Fern, arm B | `27-s02-B2` (**evaluator FAIL**, 12 requests, shortfall 2) | seven repeated `find_elements` calls; hrefs reached the harness but the model-visible history kept only `Found 11 elements matching "a".`; step budget exhausted; out-of-stock answer |
(Fern is the only scope containing the failure; 25 and 26 are the first A and B runs of that scope — alternatives 28/29 re-opened the page three times, 30 is another clean B run.)

## What the local traces contain (inspected, not changed)
Per run directory: `run.json` (21 KB), `trace.jsonl` (≈ 0.64 MB for run 27; 75% is the full `model_request` prompts incl. the ~23.6k-character system prompt), `model-response-NN.json` (raw HTTP-response captures incl. the model text), `history.json` (88 KB), `step-NNN.png` and `model-input-*.png` (≈ 80 KB each), `agent-workspace/`, `summary.md`. Event kinds in `trace.jsonl`: `run_started`, `browser_version`, `initial_actions`, `model_request`, `model_http_request`, `model_http_response`, `model_output_recovery`, `model_response`, `observation` (step, url, title, `dom` = the Browser Use text view sent to the model, screenshot ref, `proposed_actions`), `step_result` (actions executed, `extracted_content`, errors, state), `run_finished`.

## Proposed deterministic export (script + files)
`dashboard/scripts/export_replay.py` (stdlib only): reads `runs/pilot-task007/pilot-state.json` and the three run directories, writes sorted-key JSON with no timestamps; `--check` regenerates in memory and fails if the committed files differ (so the export is reproducible and reviewable). It records SHA-256 of each source file in the manifest. Output (all under `dashboard/public/replays/`):
1. `manifest.json` — schema version, export-script SHA-256, source run IDs and source-file SHA-256s, schedule SHA-256, execution commit, list of included/excluded field classes, sanitization rules applied.
2. `fern-A-25-s02-A1.json`, `fern-B-26-s02-B1.json`, `fern-B-27-s02-B2.json` — one file per replay (≈ 40–90 KB each estimated).
3. *(optional, needs separate approval)* `screenshots/<run>/<step>.webp`: the agent-visible screenshots (24 images), downscaled to 640 px wide; default is **no screenshots** (DOM text only).

**Per run (header):** `id`, `arm`, `scope`, `rank`, task wording, independent evaluator `{passed, reasons}`, answer submitted, `required_visits`, `observed_visits`, `overhead` (successful runs only) or `verification_shortfall` (failed), request attribution `{required, agent, tool}`, totals (requests, tokens, calculated cost, seconds), protocol counts.
**Per step (from `observation`, `model-response-NN.json`, `step_result`):**
- `step`; `page` (`listing` | `filtered listing` | `product detail`), `path` only (`/`, `/?brand=Fern…`, `/products/<route>`), `title`;
- `model_visible_dom` — the text of `observation.dom` (what the model was shown; includes the listing text, so arm A shows stock lines and arm B does not);
- `model_visible_last_result` — the `Result` line for the previous step as it appeared in the request's `<agent_history>` (extracted by a fixed regex; this is what proves run 27's mechanism, e.g. `Found 11 elements matching "a".`);
- `model_response`: `raw_protocol` (`raw_valid` | `recovered`), `prose_prefix` (text before the JSON, only when recovered), `evaluation_previous_goal`, `memory`, `next_goal`, `thinking`, `action` (JSON), `finish_reason`, `usage {prompt, completion, reasoning}`, `latency_s`, `estimated_cost_usd` (calculated from tokens at published prices, labelled as an estimate);
- `tool_result`: for each executed action, `{action, result_text (≤ 600 chars, ellipsised and flagged `truncated`), error}`; for `find_elements` this is the harness-side output with hrefs, shown next to `model_visible_last_result` to make the visibility gap explicit;
- `guard`: `schema` (`full` | `done_only`), `budget_warning` (bool), `final_step` (bool).
Missing fields stay `null`; no step, screenshot, reasoning or value is synthesised or smoothed.

## Excluded on purpose
The system prompt and complete `model_request` messages (≈ 480 KB/run, mostly boilerplate), raw HTTP bodies and headers, `request_id`s, `history.json`, `agent-workspace/`, `model-input-*.png`, absolute local paths, `artifact_path`, localhost **ports** (URLs reduced to path + query), `.env`/credentials (none present; checked), browser/OS details beyond the already-published Chrome version, and the private task-truth record (only the evaluator verdict and reasons are exported).

## Sanitization checks (run by the script and reviewed by a human before any commit)
1. Credential scan: the `META_MODEL_API_KEY` value (read from the environment, never printed) and generic key/token patterns must not appear in any exported file.
2. Path scan: no `/home/`, `/tmp/`, `runs/`, `127.0.0.1:<port>`, usernames or email addresses.
3. Allow-list schema: exporter emits only the named fields; unknown fields are dropped, not copied.
4. Size and count budget (≤ 300 KB total without screenshots); the file list in the manifest must match the directory.
5. Round-trip check against `per-run-reconciled.json` (requests, tokens, cost, visits, verdicts) so the replay agrees with the dashboard numbers.
6. Manual review of every exported text field (model `thinking`/`memory` strings, tool output, DOM) before commit.

## Risks to decide on before approval
- **Model-generated text:** exports include Muse Spark output (reasoning, plans, prose prefixes). Publication terms for Meta model outputs and the hackathon's public-repository/IP rules are **unverified here**; the user should confirm before any commit. A safer fallback: omit `thinking`/`memory` and keep only actions, results and the short `next_goal`.
- **Storefront content:** synthetic products and prices only; product IDs (`AR-xxxx`) appear on detail pages and in answers (post-hoc; the evaluator verdict is already public in Report 007).
- **Reproducibility vs privacy:** SHA-256s of local source files are published but the files are not; only someone with the local artifacts can re-run `--check`.
- **Misreading risk:** a replay of one failure can be mistaken for typical behaviour; the UI will show the run's rank within the 30 runs and keep the Kitchen/Fern limitations visible.
- **Size/licensing of screenshots:** deferred (optional above).

## Stage B UI (after approval of the export)
A "Recorded replay" page: replay picker (A vs B Fern, and run 27), step stepper/scrubber with keyboard control, side-by-side panels for *what the model saw* vs *what the tool returned*, per-step requests/tokens/estimated cost, a running tally of required vs agent-induced vs tool-interface requests, a banner "Recorded experiment replay — not live inference", and for run 27 an annotated callout across steps 3–9 attributing the loop to the **agent–tool interface**, ending in the independent FAIL and the verification shortfall (required 3, observed 1, shortfall 2).

## Approval requested
(1) the three runs; (2) the field list and exclusions; (3) whether to include `thinking`/`memory`; (4) whether to include downscaled screenshots; (5) license/terms confirmation for model-generated text. No export is generated or committed until then.
