# Agent Readiness: status

Authoritative current handoff. Check it against the repository and production before you rely on it. The full dated history up to 2026-11-02 is preserved verbatim in [docs/archive/STATUS-2026-10-29-to-2026-11-02.md](docs/archive/STATUS-2026-10-29-to-2026-11-02.md); earlier history is in [docs/archive/STATUS-through-2026-10-29.md](docs/archive/STATUS-through-2026-10-29.md).

## Current state (2026-11-02)

**Production:** https://209-38-84-72.sslip.io (DigitalOcean, Sydney). It serves the redesigned frontend from `product-experience-redesign` @ `b3121a8` (homepage `#/`, cinematic demo `#/demo`, workspace `#/run`) on the hosted backend, which is unchanged since `hosted-ironbark-evaluation` @ `60fcbc6`.

- Mode live, access **operator-only**: public starts get 403.
- Hosted ceiling US$10. US$3.30 is reserved by two completed jobs, and **4 repetitions remain**.
- Rollback image `agent-readiness-app:rollback-60fcbc6` is kept; the command is in [deploy/DEPLOY.md](deploy/DEPLOY.md).

**Verified independently on 2026-11-02 (fresh session, public endpoints only):**
- `index.html`, the entry JS/CSS and the lazy Demo/Classic chunks served by production are byte-identical (SHA-256) to a local build of the dashboard source at `b3121a8`. The dashboard source is unchanged from `b3121a8` to HEAD.
- `/api/health` returns `mode live, evaluations enabled, access operator, active false`.
- `/api/ironbark/config` returns `worker idle, model muse-spark-1.3, profile suite-v2-compat2, remaining_repetitions 5`.
- Security headers present: CSP `default-src 'self'`, HSTS, nosniff, `no-referrer`.
- In-container checks (jail self-test, image tags, `.env`) need SSH to the VM. They were last recorded by the deploying session (see the archive) and have not been repeated in this session.

**Branches.** Production runs `product-experience-redesign`. It sits on top of `hosted-ironbark-evaluation`, then `ironbark-evaluation-runner`, then `live-m1-llm-evaluation` (draft PR #60), then `main`. It is **63 commits ahead of `main` and unmerged**, so `main` does not reproduce production. Merging (or a PR from `product-experience-redesign`) needs owner approval. `demo-cinematic-storyboard` holds 4 commits that are not in production: it is the earlier storyboard and is kept as history.

**Paid production trial completed (owner-approved, exactly one repetition):** `eval-aa23e330`, 8/8 in 9 min 01 s, real model. Original 0/4 (52 requests) → Modified 3/4 (26 requests). Frozen rule inconclusive; exploratory rule consistent_with_h1. **New calculated spend US$1.126097**, fully reconciled (0 open reservations, none settled above its reservation). Every production surface worked, including refresh recovery. Findings: an answer-length grading false negative on task 1; a tight Original-arm cap margin; a stale ceiling in the export; operator-token UX. Full details: [report](collaboration/reports/hosted-production-trial-2026-11-02.md). **No further paid call is authorized.**

**Next:** generalization (site adapters, generated and validated tasks) and expanded diagnostics, both isolated from the hosted Ironbark path until validated.

## Budget

- Hosted admission: US$10 ceiling, US$3.30 reserved, US$1.65 per repetition. Reservations are never released, even for completed jobs, so the remaining capacity is 4 repetitions.
- Programme: ceiling A$50. This is a limit, never an authorization. The recorded known-spend subtotal is US$9.440066 / A$14.1601 at the 1.50 assumption, and is partial (see `collaboration/budget/programme-ledger.json` and the archive). The 2026-11-02 production trial (US$1.126097) is **not yet appended; that is an owner action**. With it the subtotal is US$10.566163 / A$15.85. Calculated cost is not a bill.

## Deadlines

Feature freeze and demo preparation: **Wednesday 2026-11-04 (Sydney)**. The official submission deadline is 2026-11-05 13:00 Sydney (Nov 4 21:00 ET).

## Known debt and follow-ups

- Production code lives on an unmerged branch stack (see Branches above).
- Trial findings awaiting owner decisions: the task-1 answer-length grading false negative (frozen rule), and the Original-arm cap margin (about one request of headroom). See the [trial report](collaboration/reports/hosted-production-trial-2026-11-02.md).
- Demo-day documents predate the redesign and still describe the Replay Studio as the default page: [docs/THREE_MINUTE_DEMO_SCRIPT.md](docs/THREE_MINUTE_DEMO_SCRIPT.md) and [docs/RELEASE_CHECKLIST.md](docs/RELEASE_CHECKLIST.md). Refresh them on demo-preparation day.
- Archive UIs remain reachable on purpose as rollback and reference paths: the Replay Studio (`#/studio`) and the classic pages (`#/investigation` and others). The Geist font and its licence exist in both `site/fonts` and `studio/assets`. Vite emits a single asset for them, so the duplication only costs repository bytes.
- Untracked owner work in the checkout is left untouched: `src/agent_readiness/investigate/prototype/termvalue.py` and `tests/test_termvalue_prototype.py`. They are a later variant of the tracked `taskgen/termvalue.py`.
- Architecture debt that was retained by decision (three experiment drivers, frozen shop-coupled files, legacy runner) is described in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Key documents

[deploy/DEPLOY.md](deploy/DEPLOY.md) (deployment, rollback, operations) · [dashboard/PRODUCT_REDESIGN.md](dashboard/PRODUCT_REDESIGN.md) (frontend design and evidence provenance) · [collaboration/reports/hosted-ironbark-wip.md](collaboration/reports/hosted-ironbark-wip.md) (hosted backend) · [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) · [COLD_START.md](COLD_START.md).

## Standing constraints

- No paid inference, ceiling change, public paid access or publication of private traces without explicit owner approval.
- Never print or commit `META_MODEL_API_KEY`, `.env` or `deploy/secrets/`.
- Keep scripted, mock, recorded and live evidence distinct.
- Historical Task 005–007 code, config and data, pilot evidence, frozen manifests and the budget ledger are never rewritten. Stored evaluation evidence is never deleted.
- `uv.lock` is deliberately untracked. Never use a bare `git add -A`.
