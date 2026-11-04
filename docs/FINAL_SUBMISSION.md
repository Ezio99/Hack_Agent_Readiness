# Final submission materials (2026-11-04, prepared; submitting is the owner's action)

**Deadline:** official "Nov 4, 9:00 PM ET" = 2026-11-05 13:00 AEDT. Submit by 12:00 AEDT to be safe. See [FINAL_SUBMISSION_CHECKLIST.md](FINAL_SUBMISSION_CHECKLIST.md) for which requirements are confirmed and which are assumed. Paste into the form, then check each field's length limit. Use audience wording only (Larkspur Community College, Before, After, Agent Readiness).

## Project name
Agent Readiness

## One-line pitch
Usability testing for AI agents: real Muse Spark browser agents do your customers' tasks on your website. Agent Readiness checks every answer against your own records, shows why agents struggle, and measures the fix.

## Description
A website can look great to people and still be unusable for the AI agents that will increasingly act for them. Agent Readiness makes that measurable:

1. **Freeze the website.** A content-hashed copy is served to agents from an isolated mirror.
2. **Approve the questions.** Customer tasks are generated from the business context, checked against an independent oracle built from the site's own records, and approved and frozen by the owner.
3. **Evaluate live.** Fresh Meta Muse Spark Browser Use agents work in isolated Chromium sandboxes, under per-request spend caps and a shared evaluation budget.
4. **Read the report.** Correctness, evidence (did the agent see the pages that hold the answer), navigation, reliability and cost per agent. Every run replays with its recorded screenshots and the agent's own working notes.
5. **Fix and measure again.** The report's recommendations are tied to evidence. The changed site is re-evaluated with the same frozen tasks and agent.

**Showcase: Larkspur Community College** (a fictional college), live on 4 Nov 2026, each version evaluated on its own with the same three frozen questions and the same agent.

| | Before | After |
|---|---|---|
| What it is | The college's freshly redesigned website: cards show a name and summary, facts one click deep | Same design and pages, with the three recommendations applied |
| Correct answers | **0/3** | **3/3** |
| Model requests | 36 | 15 |
| Agent time | 311 s | 121 s |
| Model cost | US$0.52 | US$0.20 |

**Why Before failed:** the agents opened course pages one at a time and ran out of steps, and one hit a dead end.

**The three recommendations applied in After:** every fact on the course cards, the dead end fixed, structured course data.

One agent per question: a measured result for these tasks, not a statistical guarantee.

## Built with
Meta Muse Spark via the Meta Model API, Browser Use, Playwright/Chromium, Python/FastAPI, React 19 + TypeScript + Vite, SQLite, Docker, Caddy, DigitalOcean.

## Links
- Live product: https://209-38-84-72.sslip.io
  - Showcase: `#/showcase`
  - Workspace (every run evaluates Before and After side by side, 6 agents): `#/run`
  - Live report (the latest paired run; until one exists, the two separate 4 Nov runs, labelled as such): `#/reports/latest`
  - Journey (the evaluation and improvement process, step by step): `#/lifecycle`
- Reports:
  - Before: `#/reports/eval-ea13944e8ba5c08e8893426b2f8b1c8f`
  - After: `#/reports/eval-5cf934b372942da74f5157c5fca39fd6`
- Repository: https://github.com/Ezio99/Hack_Agent_Readiness, branch `final-showcase` (link the exact commit).
- Video: [FINAL_VIDEO_SCRIPT.md](FINAL_VIDEO_SCRIPT.md).

## Honesty notes
- Larkspur is fictional. The tasks are frozen and owner-approved.
- Costs are calculated from provider-reported token usage and settled from each run's ledger; they are not invoices.
- The hackathon implementation began 2026-10-27 (Sydney). The earlier repository is a disclosed pre-event prototype.
- AI coding assistants helped build the project under the owner's direction.

## Owner to confirm on the form
Track and theme, team roster, licence field, video host and privacy setting, and whether a branch or commit URL is accepted.
