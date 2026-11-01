# Second evaluation target: a saved documentation snapshot (offline)

**Status (2026-11-01): registered, exercised only with the zero-spend dev provider. No paid run has been made or authorized.**

## What is registered
`flask-docs` (`live/targets.py`): a script-stripped capture of a self-hosted build of the open-source Flask documentation (BSD-3). It is a *saved snapshot*, never fetched on request: there is no URL field anywhere. The target is offered only on a machine where the snapshot exists (`$AR_TARGET_SNAPSHOTS/flask-docs` or `scanner-data/targets/flask-docs`, git-ignored).

Capture (operator, offline): build the docs, then `python scripts/capture_docs_snapshot.py <built-site-dir> scanner-data/targets/flask-docs` (serves the directory on 127.0.0.1 only; the repository crawler is same-origin, robots-aware, GET-only and bounded). The Flask build used for the first run captured 75 pages, snapshot hash `b6aa1a49...`, fidelity `high` (378 scripts removed).

## Per-target configuration (Ironbark is unchanged)
| | Ironbark | flask-docs |
|---|---|---|
| goal vocabulary | rental lexicon (`RENTAL`) | none (`NEUTRAL = {}`); an attribute is a fact label that IS a goal word |
| `term_value` task kind | off (requests, schemas and approval hashes byte-identical; pinned in `tests/test_term_value.py`) | on |
| live job allowed | yes | yes, only if the snapshot exists; a person must still confirm the spend and approve every paid stage |

## Evidence rules that matter for a documentation site
* Repeated-link groups are classified (`catalogue` / `uncertain` / `navigation_group`; thresholds are provisional heuristics). Only `catalogue` groups can carry a listing claim: owner insights' site properties, the `info_absent_on_template` verifier and the scripted investigator ignore the rest. A table of contents is reported as `navigation_link_groups`, never as a product listing.
* A control with no accessible name inside an element hidden in the capture is `controls_hidden_in_capture` (not a defect); hidden `aria-labelledby` targets still name their control.

## Fidelity limits to disclose with any result
Scripts removed (JS-revealed content and site search do not work); GET only; the model-visible view of a long page is truncated, so an answer far down a long page may not be shown to the model (the run then records the pass as `success_unsupported`, not a measured success); results describe the static capture, not the live site.

## First offline end-to-end run (dev provider; a fixture, not a model)
See the report in the milestone summary: 4 `term_value` tasks accepted by the unchanged gate, 4 trials executed, no friction claims, no hypotheses (the stand-in investigator has nothing to check on a site without a catalogue listing).
