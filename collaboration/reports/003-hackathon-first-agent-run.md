# Hackathon Task 001 — fresh implementation evidence

Date: 2026-10-27 Australia/Sydney. Approved specification:
[003-hackathon-first-agent-run.md](../tasks/003-hackathon-first-agent-run.md).

**PR review revision:** 57 local tests and credential-free smoke pass; remote
CI for this revision is pending. The earlier foundation/startup-fix results below
are retained as history. See the final review-revision section for current evidence.
Live Meta compatibility remains unverified.

## Delivered architecture

One newly authored Python package implements twenty synthetic products, a
server-rendered accessible storefront, deterministic feasible task generation,
strict public answer contracts, independent evaluation, Browser Use reference
adapter, runner/recorder, CLI and credential-free browser smoke. No prototype
implementation, tests, executable configuration or run artifacts were copied.
Cached public third-party dependency distributions were used for installation;
the lockfile was generated afresh from the actual environment.

Listings receive a projection of name, brand, category, price and opaque route
only. Detail URLs do not encode product IDs or stock. Both availability states
use the same browsing and filtering behavior. Ordinary labeled controls, semantic
headings, real links, keyboard focus and detail fields preserve usability.
Only listing and individual detail HTTP routes exist; no inventory or evaluator
endpoint is exposed. Private generated expected answers are never sent to the
agent, served over HTTP, or persisted as a committed answer key.

The single `natural-shopping-v1` profile observes DOM + high-detail screenshots
at 1280×960, permits normal browser navigation/search/filter interaction and
restricts filesystem, arbitrary JavaScript, extraction-model and external-search
tools. Its default budget is 30 steps, three actions per step and 180 seconds,
with a 4096-completion-token per-request cap. Overrides, hashes, sampling defaults
and model/provider configuration are recorded. Each run gets a fresh browser.

Outcomes are graded using inventory truth and task constraints, independently of
agent self-assessment and UI path. Navigation evidence is recorded separately.
Timeouts, provider errors and infrastructure failures preserve partial traces and
reported usage; unavailable metrics remain null. Token usage is never inferred
from elapsed time. Cleanup may extend the wall-clock budget by up to 15 seconds.

## Revalidation after the permission update

The user updated session permissions and requested a retry. The sandbox still
protects Git and sockets, but approval-reviewed execution now succeeds. The three
prepared commits were imported locally onto `hackathon/task001`; all 32 changed
files matched the saved commits exactly. The index and worktree were clean after
switching. Git operations can now be completed in the original checkout.

Fresh credential-free results using approval-reviewed execution:

| Check | Result |
|---|---|
| `python -m pytest -m browser -q --basetemp=artifacts/browser-recheck` | 3 passed, 21 deselected in 16.25s |
| Full suite with `--junitxml=artifacts/verification/pytest-final.xml --basetemp=artifacts/final-tests` | **24 passed in 12.91s** |
| `readiness smoke --output runs` | **Completed; independent evaluation passed** |

The CLI smoke used Chromium 145.0.7632.6 and completed in 3.085 seconds, with
six scripted browser operations, three recorded observations and null model
usage. Its evidence directory is `runs/20261027T001314-b613f9df27a2/`: initial
and filtered observations, detail observation, ordinary and actual Browser Use
screenshots, payloads, accessibility/DOM snapshots, trace, configuration and
independent evaluation. The initial listing screenshot was also visually inspected.
The three browser tests validate both task families and both stock states.

These successful checks supersede the initial Git/socket blockers below. Earlier
failed artifacts remain preserved. No model calls were made. This is a verified
credential-free vertical slice; hosted Meta compatibility and live reference-agent
success remain unverified. CI has not been run.

## Initial checks in the restricted sandbox


| Check | Result |
|---|---|
| `python -m pytest -m 'not browser' -q` | 21 passed; 3 browser cases deselected |
| `python -m pytest -q --junitxml=artifacts/verification/pytest.xml` | 21 passed, 3 failed in 3.75s |
| `python -m pytest -m browser -q` | All three cases fail at denied socket creation |
| `readiness smoke --output runs` | Recorded infrastructure_error; EPERM; no evaluation |
| `uv pip check` | 117 installed packages consistent |
| `python -m compileall -q src tests` | Passed |
| setuptools wheel build + asset inspection | Passed; templates and profile included |
| `readiness generate --kind availability --available false --seed 7` | Valid public task emitted without answer fields |
| `readiness run --output runs` | Setup error; calls disabled; no model request |
| `readiness --help` / `git diff --check` | Passed |

Offline coverage includes 300 seeded unique/feasible task cases, both stock
states, independent wrong/malformed-answer grading, full inventory detail
consistency, initial/filtered HTTP payload leakage, inaccessible truth endpoints,
actual tool restrictions, real image/schema serialization against synthetic Meta
responses, missing credentials, spending gate, trial separation, redaction and
partial usage retention during timeout.

The browser checks inspect raw response bodies, hidden DOM,
accessibility trees, DOM snapshots, actual Browser Use serialized observations
and screenshot artifacts before opening details. In the initial execution,
the sandbox rejected `socket.create_server(('127.0.0.1', 0))` with
`PermissionError: [Errno 1] Operation not permitted`. Consequently neither those
initial checks nor the initial CLI smoke reached Chromium. The successful
revalidation above now establishes browser navigation and observation-boundary
checks for this fixture. It does not establish live reference-agent success.
CI is written but has not been executed.

The first synchronous TestClient attempt also hung in this restricted sandbox's
cross-thread event-loop wakeup. Final HTTP tests use asynchronous ASGITransport
and pass. A single platform-probe value is supplied in the offline SDK test to
avoid the same restriction; request serialization/transport/parsing remain real.

## Versions and Meta compatibility

Python 3.12.3; Browser Use 0.11.13; Playwright 1.58.0; FastAPI 0.136.1;
Pydantic 2.13.5; SDK 2.54.0; pytest 9.1.1. Exact Linux/Python 3.12 dependencies
are pinned in `requirements.lock`. `pydantic-settings` is explicitly installed
because the pinned Browser Use package imports it without declaring it.

[Meta integration evidence](../../docs/META-INTEGRATION.md) links the official
protocol requirements and explains the offline compatibility checks. The
candidate default is `muse-spark-1.3` at `https://api.meta.ai/v1`, with bearer
`MODEL_API_KEY`. No key was requested or used for hosted inference. **Meta access,
hosted schema acceptance and live agent compatibility remain unverified.** A
model ID/configuration snapshot does not guarantee immutable hosted behavior.

## Inspectable local artifacts

Generated artifacts are ignored by Git and are not part of the source commits:

- `artifacts/verification/pytest.txt` and `pytest.xml`: initial restricted-suite evidence;
  `pytest-final.xml` records the successful 24-test recheck.
- `artifacts/verification/smoke.txt`: initial restricted CLI smoke output and artifact path.
- `runs/20261026T234100-decdaa49855c/`: initial recorded socket failure, run metadata,
  trace and readable summary. There is no answer, screenshot or grade.
- `runs/20261026T233955-17bdf79cb487/`: default live-command spending-gate failure.
- `runs/20261026T233014-45c492a70fe1/`: earlier smoke infrastructure failure.

No live trials were attempted; no successful measurements are being claimed.
Synthetic model responses and scripted browser smoke are wiring checks only.

## Review commits and portable delivery

The original checkout protects `.git` as read-only. `git add` failed creating
`.git/index.lock`, so no commit or index update could occur there during the initial handoff. A clean local
clone at `/tmp/readiness-hackathon-review` holds review commits instead:

1. `35034ec` — storefront, generator, evaluator and first ten tests.
2. `6853142` — reference profile, adapter, runner, artifacts, tests and browser CI.
3. `da8b1f4` — initial documentation/evidence and environment limitations.
4. A permission-update evidence commit in the original checkout records the
   successful Git restoration and browser revalidation.

`artifacts/hackathon-task001.bundle` exports the review branch and new commits
relative to original base `ddbaca7a911f3c9b1e03f750e5eeee923da20cfa`. Verify it with
`git bundle verify artifacts/hackathon-task001.bundle`. In a **clean writable
clone** with that base, fetch the bundle's `hackathon/task001` branch and switch
to it. Do not discard the visible working-tree changes in the original checkout.
The bundle contains source and documentation only. No push or remote action was
performed. At the initial handoff the original repository HEAD/index were unchanged. The
permission-update revalidation above subsequently restored the three commits to
the original checkout and switched it to `hackathon/task001`.

## Acceptance still pending
- Separately approved authenticated Meta validation, then live agent trials and
  independent evaluation; preserve every attempt, including failures.
- Participant-specific event-rule verification.

This introduces fresh `run-v1`, `synthetic-v1` task IDs, inventory and profile
hashes. Prototype run/task formats and measurements are not backward-compatible
baselines. No dashboard, registry, readiness score, additional behavior profile
or accessible-label intervention was implemented. The complete historical Task
002 acceptance checklist must not be marked complete from these offline checks.

## First remote CI attempt and startup fix

The user authorized pushing `hackathon/task001`, monitoring CI, and opening a PR
only after CI passes. [Run 40425362650](https://github.com/Ezio99/Hack_Agent_Readiness/actions/runs/40425362650)
installed all locked dependencies and passed 21 offline tests, but all three
browser cases failed during Chromium startup before any storefront interaction.
The artifacts and full log are preserved in ignored `artifacts/ci-first-failure/`
and `artifacts/verification/ci-first-failure.log`.

Inspection found Browser Use defaults Chromium sandboxing off inside a container
and on outside one. Local verification had used the container default; GitHub's
Ubuntu 24.04 VM used the other launch path. The profile now records the same
explicit sandbox-off setting in both environments, and CI pins Ubuntu 24.04
instead of following a migrating runner label. DOM/screenshot settings, task
truth and evaluator rules are unchanged. No live model trials existed before
this profile-setting correction; code/profile hashes distinguish the wiring runs.

An additional regression test checks both container-detection outcomes produce
the same required launch flags. Another ensures an internal operation timeout is
classified as infrastructure failure, rather than incorrectly labeled as the
experiment's wall-clock deadline. After the fix, all **26 local tests passed in 10.94s**, including all three
real-browser cases (`artifacts/verification/pytest-ci-fix.xml`). Remote
[revalidation passed in run 40426022852](https://github.com/Ezio99/Hack_Agent_Readiness/actions/runs/40426022852)
for commit `b278a7e9a64aa7c176ca24884cfd39c0e1e45a0f`. GitHub's runner passed
23 offline tests in 2.69s, three browser cases in 6.13s, the CLI smoke with an
independent passing grade, and artifact upload. The smoke artifact path is
`runs/20261027T003126-d62bafa307a4/` within the downloadable evidence archive.
The earlier failed CI run is retained, not discarded. No provider calls or
paid model trials were made.

## PR #1 requested review revision — 2026-10-27

The user requested the following changes before merge. No merge or live-model
trial is authorized. The existing `hackathon/task001` branch and PR #1 are retained.

### Configuration and request controls

The runner now resolves one effective profile and passes it explicitly through the
model adapter, browser options, reference agent and scripted smoke. Components no
longer reload defaults. Regression fixtures check actual wire token limits, SDK
timeouts, tool permissions, instructions, viewport, agent step limits and recorded
hashes; a real-browser test checks viewport geometry and early stopping.

The single profile advances from v1 to `natural-shopping-v2`, with conservative
defaults of 10 steps, 120 seconds, 10 request attempts and 2,048 completion tokens
per response. The SDK request timeout is 30 seconds, the agent step timeout is
60 seconds, and cleanup may take an additional 15 seconds. Profile v1 remains
in Git history; old artifacts are not rewritten. This is a new configuration
version, not an additional benchmark variant or comparison experiment.

The explicit `--allow-model-calls` authorization gate remains mandatory.
`--max-model-requests` joins the step/time overrides. A synchronous pre-invocation
gate blocks the next provider-adapter call once the cap is reached, including
framework retries. Failed/cancelled requests count; SDK retries are disabled.
Setup consumes the same wall-clock budget, with an expiry check before execution.
The additive run-v1 fields include `limits`, `model_request_count`, and
`configuration_hash`; the effective `profile_hash` is preserved. Request exhaustion
is recorded separately from infrastructure errors and wall-clock timeout.

These are request/time/response-token controls, not a guaranteed dollar budget.
Prompt sizes, changing prices, missing usage and provider billing on failed or
cancelled requests prevent that guarantee. Future live trials require separate
configuration and expenditure approval.

### Artifact privacy

The recorder registers the configured credential at setup and the adapter key at
the recording boundary. Redaction covers nested sensitive header/key fields,
common URL/JSON encodings, recognizable textual authorization, URL userinfo and
credential query keys. JSON, JSONL and text summaries share the same redactor.
Provider errors are sanitized before framework logging/history; credentials in
model endpoint URLs are rejected. Focused tests preserve useful non-secret page
observations and usage while checking traces, errors, history/configuration and
summary output for secret leakage. Screenshot extraction/preservation still works.

Raw artifacts must be inspected before publication. Redaction is not arbitrary
PII detection or screenshot OCR; model/page content and PNGs can contain private
information unrelated to the configured API credential. The browser never receives
the model API key. No generated private/run artifacts are committed.

### Actual fresh verification

| Check | Result |
|---|---|
| Full suite, `pr1-review-final.xml` | **57 passed in 12.92s** |
| Standalone real-browser suite, `pr1-review-browser.xml` | **4 passed, 53 deselected in 10.07s** |
| `readiness smoke --output runs` | **Completed; independent evaluation passed; 0 model requests** |
| Git diff whitespace check | Passed |
| GitHub Actions for this revision | Pending push/revalidation |

The successful smoke is preserved at `runs/20261027T010440-8c0e0676c0bc/` with
configuration, limits/hashes/counts, observations, screenshots, trace and grade.
An earlier 55-test full pass and the later 56-test pass preceded the final
regressions; the final 57-test result above is authoritative for this revision.
Offline adapter fixtures use synthetic responses and MockTransport; scripted
smoke uses deterministic browser interactions. Neither is a live model experiment.
No live/authenticated or paid model calls occurred.

User-created local onboarding changes in AGENTS.md and COLD_START.md were read
and preserved separately; they are not staged into this review revision.
