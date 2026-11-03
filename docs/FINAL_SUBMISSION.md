# Final submission materials (2026-11-04, prepared; submitting is the owner's action)

**Deadline:** 2026-11-05 13:00 AEDT. Paste from here into the actual form, then check each field's length limit.

## Project name
Agent Readiness

## One-line pitch
Usability testing for AI agents: real Muse Spark browser agents do your customers' tasks on your website. Agent Readiness checks every answer against your own records, shows where the agents struggled and what to change, then measures the change.

## Description (long)
Personal agents are starting to browse the web for people, and most websites have never been tested with one. Agent Readiness turns that into a repeatable product workflow:

1. **Frozen website snapshot.** A content-hashed copy of the site is served to agents from a jailed mirror. No live crawling happens on request.
2. **Customer tasks.** The tasks are generated from the business context, checked against an independent oracle built from the site's own records, and approved and frozen by the owner.
3. **Live evaluation.** Fresh Meta Muse Spark (`muse-spark-1.3`) Browser Use agents run in isolated Chromium network namespaces, with a per-request spend cap and a shared evaluation budget.
4. **Readiness report.** Correctness, an exact-match grade, evidence (did the agent see the pages that hold the answer), navigation efficiency, reliability and cost per agent. Every agent run can be replayed with its recorded screenshots and working notes.
5. **Evidence-linked recommendations, then re-evaluation** of a new immutable version, under the same frozen tasks and agent.

**The showcase: Polished Larkspur** (a fictional community college).

| Stage | Result |
|---|---|
| Original site | Agents answered 0/3 correctly in 39 model requests |
| Improved (first round of recommendations) | 3/3 in 6 requests; one paired live run |
| Polished v1: a human-centred redesign, evaluated on its own | 3/3 correct, 8 requests, 65 s, US$0.11 |
| Polished v2: the change the v1 traces justified (the results line names every match; compact results) | 3/3 correct, 9 requests, 79 s, US$0.12 |

- **The friction v1 showed:** on one task the agent saw only three of four results ("Visible 3… scroll down to reveal the 4th course") and spent an extra request.
- **v2 did not beat v1.** The agent read the new summary, then scrolled anyway to verify the facts. That difference is within run-to-run variation at one agent per task.
- **The finding:** agents verify, so they need each match's deciding facts on screen. We report this as measured rather than inventing a success.

## Built with
Meta Muse Spark via the Meta Model API (the browser-agent decisions; task generation offline), Browser Use, Playwright/Chromium, Python/FastAPI, React 19 + TypeScript + Vite, SQLite, Docker, Caddy, DigitalOcean.

## Links
- Live product: https://209-38-84-72.sslip.io
  - Showcase: `#/showcase`
  - Journey: `#/lifecycle`
  - Workspace: `#/run`
- Reports: Polished v1 `#/reports/eval-abc5fc838a5428b6753a424e189ba1cc`, Polished v2 `#/reports/eval-11ee8a1e6dad19998865db7187c8cb5e`, Original vs Improved `#/reports/eval-c04fdb100d6b1c877de96dabe76eb052`.
- Repository: https://github.com/Ezio99/Hack_Agent_Readiness, branch `final-showcase` (unmerged into `main`; link the exact commit).
- Video: record from [FINAL_VIDEO_SCRIPT.md](FINAL_VIDEO_SCRIPT.md).

## Honesty notes (keep in the submission)
- Larkspur is fictional. The tasks are frozen and owner-approved.
- Each result is one live run per task: exploratory, not a statistical claim.
- Costs are calculated from provider-reported token usage and settled from the run's ledger; they are not invoices.
- The hackathon implementation began 2026-10-27 (Sydney). The earlier `Agent_Readiness` repository is a disclosed pre-event prototype; third-party models and frameworks pre-exist.
- AI coding assistants (Codex, Claude Code) helped build the project under the owner's direction.

## Owner to confirm on the actual form
Track and theme, the team roster, any licence field, the video host and privacy setting, and whether a branch or commit URL is accepted.
