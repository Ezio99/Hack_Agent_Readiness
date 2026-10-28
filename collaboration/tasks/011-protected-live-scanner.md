# Task 011 — Protected Live Scanner MVP

**Status:** Approved for design and implementation of a protected, locally testable vertical slice. **No paid hosting activation, paid inference, public scanner launch, PR merge, or private artifact publication without separate explicit approval.**
**Baseline:** `main` after Task 009 PR #5 squash merge `1cde559`; public dashboard deployed at https://ezio99.github.io/Hack_Agent_Readiness/ (public build without replay data).
**Owner:** Claude implements; user and ChatGPT review.
**Sequence:** Implement after Task 010 storefront/task foundations are merged and reconcile the scanner with the new task/environment contracts.
**Product goal:** Turn Agent Readiness from a retrospective experimental dashboard into a developer tool: select a registered storefront/task, initiate an authorized bounded scan, and receive independently evaluated, evidence-backed diagnostics.

## Product contract
- Public visitors can explore the dashboard, configure a controlled scan, and inspect already approved public examples. Public UI must not imply a scan ran when it did not.
- Only invited, server-authorized users may start **new Meta-powered scans** or view private results.
- Backend alone holds provider credentials, raw traces, evaluation truth, invitation/session secrets, quotas and scan execution state. Never expose these through the static bundle or public endpoints.
- MVP supports only pre-registered controlled storefront variants and predefined task templates; **no arbitrary URLs, prompts, target origins, user-supplied agent instructions or open-ended browsing**.
- An independent evaluator determines PASS/FAIL; model self-claims are not authoritative. Diagnose website effects separately from agent–tool interface failures; avoid a universal readiness score.

## Stage A — Architecture and threat-model gate (no deployment)
1. Inspect current Python agent driver, guard, evaluator, data model, dashboard, CI, and deployment. Reuse existing machinery; do not rewrite the experiment stack.
2. Propose a minimal architecture for the separate backend and static GitHub Pages frontend. Railway is a *candidate*, not a mandate; check browser/Playwright runtime, memory, process lifetime, persistence, network egress, price, and operational constraints. Hosting allowance of about **US$10/month is planning comfort, not permission to incur charges**.
3. Document threat model: anonymous traffic, code guessing/reuse, session theft, cross-user result access, concurrent quota races, SSRF, malicious storefront content, secret/log leakage, cost runaway, worker crash/retry, service abuse, public deployment of private data.
4. Specify API contract and state transitions. Use server-verified one-time/redeemable invitation codes -> short-lived authenticated sessions, with securely stored hashes, expiry, redemption caps, per-session scan quotas and authorization on every private result read. Do not embed a master invitation code in frontend. Avoid building a general account platform.
5. Present backend hosting and any operational decisions that require user approval; proceed with local implementation of the agreed bounded design unless a material architecture change is necessary.

## Stage B — Local implementation, zero paid calls
- UI: clearly labelled controlled target/task selector, access-code redemption, launch control, pending/running/complete/error states, actionable result page with independent verdict, request count, elapsed time, calculated cost, navigation/actions, diagnostic evidence, and baseline comparison. The historical dashboard remains accessible as evidence.
- Backend: small API and bounded worker using existing harness. Explicit allowlists for target origins and navigation, task IDs, tool/action types; enforce at browser/network layer, not just request validation.
- Security: server-side secret management, hashed/revocable codes, short session TTL, private result authorization, request validation, body-size limits, CORS allowlist, rate limits, one concurrent scan, atomic quota/budget reservation, global kill switch, durable execution/budget ledger, no automatic billable retries, timeout/cancellation and failure cleanup.
- Caps: maximum 12 agent steps, 240-second wall clock, conservative token/request and estimated-cost ceilings; document that estimated USD ceilings do **not** guarantee billed spend. Enforce at each step, not only at completion. Global budget initially disabled until explicitly funded/approved.
- Store raw traces privately and sanitize any response; no replay exports, model reasoning, provider request bodies, credentials or local paths to public storage. Avoid returning private evaluator truth to the agent.
- Provide a deterministic **mock provider** mode for all local and CI tests; no network inference by default. UI must distinguish mock, recorded, and real inference.
- Prefer an end-to-end vertical slice to generalized infrastructure; no arbitrary-user website scanning.

## Stage C — Validation and approval gates
- Automated tests: auth/code redemption, expiry, authorization isolation, replayed/stolen sessions, quota races, double submissions, kill switch, cost exhaustion, 12-step/240-second cutoffs, SSRF/redirect escapes, secret redaction, restart recovery, provider failures and cancellation, and no inadvertent inference in CI.
- Integration: deterministic mocked scan from UI -> API -> bounded harness -> evaluator -> result. Browser smoke at desktop/mobile; verify no secrets or private artifacts in the public build. Preserve Task 007/009 tests and metrics.
- Prepare deployment plan and configuration, **but do not provision paid services, set live credentials, enable a public scanner endpoint, or trigger paid inference**.
- Open PR with code/tests/docs and safe mock fixtures only; no raw traces, replay JSON, private archives, screenshots or secrets. Report CI, test results, remaining security risks, hosting estimate and exact user approvals required for private live pilot.

## Explicit stop gates
1. **PR review/merge:** user approval required.
2. **Hosting/provisioning:** user approval of provider, plan, maximum spend, credentials and configuration required; US$10/month is not automatic authorization.
3. **Live Meta inference:** separate approval of exact scenario, call count, caps and remaining budget; no paid calls during this task by default.
4. **Public invited-user activation:** separate approval after private deployment, abuse tests and verified budget controls.
5. **Publication of replay or raw/private results:** remains prohibited absent exact-file and terms approval.

## Definition of done for this PR
A developer can use the locally running product to redeem a test invitation, initiate a **mock** bounded controlled-storefront scan, inspect an independent evaluation and diagnostic report, and compare with a baseline; unauthorized attempts fail safely. Documentation explains precisely how a future approved real Meta run would execute, without claiming one has occurred.