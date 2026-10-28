# Task 009 — Public Replay Finalization & Dashboard Deployment

**Status:** Spec approved for implementation; publication and merge NOT approved.
**Baseline:** `main` after Task 008 / PR #4 squash merge `04c5730`.
**Owner:** Claude (implementation), user + ChatGPT (review and decisions).
**Scope:** Replay export minimization, publication review, static deployment readiness. **No live scanner or readiness score in this task.**

## Context and objective

Task 008 delivered the React dashboard, recorded-replay UI, deterministic local exporter, audits, and CI. The genuine Task 007 Fern A/B replay exports remain Git-ignored and private. We want a reliable, independently deployable dashboard with an approved recorded replay, without publishing data or changing experimental results prematurely.

## Stage A — Minimize public-facing replay schema

Create branch `task009-public-replay` from current `main`. Modify the exporter, replay UI, schema docs, and tests:

- Remove `done.success` from exported action parameters. Independent evaluator verdict is authoritative; do not imply agent self-reported success is ground truth.
- Remove `reasoning_tokens`, `finish_reason`, and redundant page `title`.
- Keep model-visible DOM, paths, navigation actions, tool-result excerpts, model-visible history/result visibility gap, guard state, prompt/completion token counts, per-step latency, and **calculated** cost, with accurate labels.
- Keep run 27 `residual_requests: null`, `required_path_completed: false`, and the note that its residual is not meaningful because required verification was incomplete.
- Preserve provenance, manifest hashes, deterministic generation, and mandatory audit-before-write; `--check` must remain read-only.
- Preserve the existing no-export UI fallback and clearly mark synthetic fixtures as synthetic.
- Do not fabricate or reconstruct missing experimental evidence. Do not alter raw artifacts, evaluator, or Report 007 numbers.

## Stage B — Private publication review

Regenerate the three real replay JSON files plus manifest **locally only**. Run `--audit`, `--check`, integrity tests, and a credential/sensitive-content scan.

Produce a concise private review report identifying:
- Exact retained fields and output sizes/hashes.
- Which retained fields are website-authored, harness-authored, model-chosen, or provider metadata.
- Direct links and relevant clauses from applicable Meta Model API terms and hackathon rules, with date/version when known; distinguish confirmed permissions, confirmed restrictions, and unresolved questions. Ownership of outputs alone does not establish unrestricted permission to disclose API interaction data.
- Remaining disclosure, privacy, provenance, and interpretation risks.
- Recommendation for further field minimization, if warranted.

**Publication gate:** No replay JSON, manifest, private review archive, or replay screenshots may be committed, pushed, deployed, or uploaded externally until the user explicitly approves the **exact** revised files/fields and applicable terms. If terms cannot be verified, flag the uncertainty and stop at this gate. Do not include model reasoning, memory, next-goal text, system prompts, full requests, raw HTTP, credentials, private paths, or screenshots in exports.

## Stage C — Static deployment readiness (configuration only)

Prepare a straightforward free static-hosting path (GitHub Pages preferred if appropriate), without automatically enabling public deployment.

- Build works without local `runs/` or secrets.
- Replay works when approved JSON exists; missing exports show the honest no-data fallback.
- Routing and refresh work on the deployment base path.
- No API credentials/backend secrets in client assets.
- Clearly distinguish **recorded experiment replay — not live inference**.
- Test a production build in a fresh browser where feasible.
- If a public dashboard **without** replay data is practical, propose it first; do not publish automatically.

## Stage D — Validation and handoff

Run dashboard build, Vitest, existing Python suite, exporter unit tests, `--audit` and `--check`, fresh-browser smoke test, and credential/sensitive-content scan. Confirm no paid model calls, new experiments, or raw artifact changes.

Open a PR with **safe code/config/docs/tests only**. Do not include generated replay exports or replay screenshots. Do not merge.

Report:
1. PR URL, branch, head SHA, and CI status.
2. Test/build/smoke results.
3. Exact revised export field inventory, file sizes, hashes, and private review location.
4. Publication-terms findings, citations/links, and unresolved blockers.
5. Deployment recommendation and blockers.
6. Rough implementation estimate and risks for a later **bounded live scanner** on the controlled storefront.

## Future milestones — not authorized by this task

- **Task 010 candidate:** bounded live scanner on the controlled storefront with strict step, time, and spend limits; no arbitrary-URL crawling initially. Separate approval required before implementation or paid calls.
- **Stretch:** task-specific evidence-backed diagnostic score. Do not present it as a validated universal readiness score.
- Pitch/storyboard: defer to Friday/weekend as agreed.

## Stop conditions

Stop after opening the PR and submitting the review report. **No automatic merge, publication, deployment, paid inference, new experiments, or unrelated feature work.**
