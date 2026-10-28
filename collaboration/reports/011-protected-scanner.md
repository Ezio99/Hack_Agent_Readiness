# Report 011 — Protected live scanner (credential-free)

Branch `task011-protected-scanner`. Design, API, threat model: [docs/SCANNER_DESIGN.md](../../docs/SCANNER_DESIGN.md).

## What was built
Evidence upgrade (observed-text facts), generic agent/profile/schema-hash plumbing (`suite-v1-compat1`; legacy profiles and their pinned hashes untouched), `scanner/` mock provider + executor + diagnostics, invitation-gated service, `readiness scanner` CLI, dashboard tab.

## What was actually run
- `pytest` full suite incl. real-Chromium tests (all four templates mock-executed end to end; all four variants for T3; personas lazy/wrong/loop/stuck/escape/provider_error), service/security tests (hashed codes, single use, lockout, expiry/revocation, race-safe redemption and reservation, ownership isolation, no free-form targets, quota + idempotency, one concurrent scan, budget exhaustion, kill switch, restart recovery, body/CORS/rate limits, generic error recording), and a local Playwright E2E (UI → API → agent → evaluator → UI). Counts: see PR.
- Dashboard: `tsc`, vitest, build. `check:dist` flags only the pre-existing local, Git-ignored `public/replays/` export; it must be absent for any public build.
- Screenshots kept local (`Hack_Agent_Readiness_archive/task011-screenshots/`).

## Findings / limits
- A mock scan is not model evidence. Real Muse Spark has not attempted these tasks; the `loop` persona reproduces the known tool-visibility gap (Task 007) to prove the classifier, not to measure its frequency.
- "Shown to the agent" = DOM text in the model's observation; the model may ignore it.
- Attribution is rule-based and conservative; ambiguous cases are `undetermined`.
- Rate limiter/state are single-process; a proxy deployment needs trusted-header handling and a security review.
- No live inference, deployment, or merge was performed. Live-validation plan (≤US$1.92 estimated max) is proposed for separate approval.
