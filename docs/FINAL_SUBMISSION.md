# Final submission materials (2026-11-04, prepared; submitting is the owner's action; results updated to the canonical paired evaluation)

**Deadline:** official "Nov 4, 9:00 PM ET" = 2026-11-05 13:00 AEDT. Submit by 12:00 AEDT to be safe. See [FINAL_SUBMISSION_CHECKLIST.md](FINAL_SUBMISSION_CHECKLIST.md) for which requirements are confirmed and which are assumed. Paste into the form, then check each field's length limit. Use audience wording only: Larkspur Community College, **Original website**, **Agent-ready website**, Agent Readiness.

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

**Showcase: Larkspur Community College** (a fictional college). Reference results from the **canonical paired evaluation** `eval-1cf64d5eae90bcaeab531b4886140c14` (4 Nov 2026): both websites in one live evaluation, with the same three frozen questions, agent and limits.

| | Original website | Agent-ready website |
|---|---|---|
| What it is | The college's freshly redesigned website: cards show a name and summary, facts one click deep | Same design and pages, with the three recommendations applied |
| Correct answers | **0/3** | **3/3** |
| Model requests | 39 | 10 (74% fewer) |
| Agent time | 326 s | 57 s (83% less) |
| Model cost | US$0.571 | US$0.134 (77% less) |
| Beginner weekend courses found | 1/4 | 4/4 |

**Why the Original website failed:** the agents opened course pages one at a time and ran out of requests before checking them all.

**The three recommendations applied in the Agent-ready website:** every fact on the course cards, a fix for a dead end (an agent in an earlier evaluation guessed a course address and got "not found"), structured course data.

One reference paired evaluation, one agent per question on each website: a measured result for these tasks, not a statistical guarantee. Individual live runs vary.

*Historical:* two earlier separate runs of 4 Nov 2026, one per website (`eval-ea13944e…`: 0/3, 36 requests; `eval-5cf934b3…`: 3/3, 15 requests), are kept as records. They are not the reference results.

## Built with
Meta Muse Spark via the Meta Model API, Browser Use, Playwright/Chromium, Python/FastAPI, React 19 + TypeScript + Vite, SQLite, Docker, Caddy, DigitalOcean.

## Links
- Live product: https://209-38-84-72.sslip.io
  - Canonical results ("See the results"): https://209-38-84-72.sslip.io/#/reports/eval-1cf64d5eae90bcaeab531b4886140c14
  - The Larkspur journey ("How it works"): `#/lifecycle`
  - Workspace: `#/run`. Everyone can watch running and completed evaluations; starting a new live run needs an operator code, which is not distributed.
  - Technical methodology: `#/how`
  - Earlier evaluations (historical Showcase): `#/showcase`
- Evidence and reproducibility for judges (no credentials needed for the evidence; optional local runs with a judge-owned key): the README's "Evaluate it" section.
- Historical reports (separate runs, one per website): `#/reports/eval-ea13944e8ba5c08e8893426b2f8b1c8f`, `#/reports/eval-5cf934b372942da74f5157c5fca39fd6`
- Repository: https://github.com/Ezio99/Hack_Agent_Readiness/tree/final-showcase (or link the exact commit).
- **Demo video (official hackathon demo, 2:59, YouTube):** https://youtu.be/cgkxzWAKVDQ
  It is built from the product's real footage and recorded agent runs, narrated. Its results are the canonical paired evaluation above (0/3 → 3/3, 39 → 10 requests, 326 → 57 s, US$0.571 → US$0.134); the earlier diagnostic run it shows first is labelled as separate. Storyboard: [FINAL_VIDEO_SCRIPT.md](FINAL_VIDEO_SCRIPT.md).

## Honesty notes
- Larkspur is fictional. The tasks are frozen and owner-approved.
- Costs are calculated from provider-reported token usage and settled from each run's ledger; they are not invoices.
- The hackathon implementation began 2026-10-27 (Sydney). The earlier repository is a disclosed pre-event prototype.
- AI coding assistants helped build the project under the owner's direction.

## Owner to confirm on the form
Track and theme, team roster, licence field, and whether a branch or commit URL is accepted. The video is published on YouTube (link above); confirm it plays while signed out and that its visibility (public or unlisted) meets the form's rules.
