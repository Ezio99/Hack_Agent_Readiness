# Final three-minute video: Polished Larkspur (2026-11-04)

Recording plan for the submission video. It replaces [THREE_MINUTE_DEMO_SCRIPT.md](THREE_MINUTE_DEMO_SCRIPT.md), the earlier Ironbark draft. Every number below is a recorded result. Read them from the screen, not from memory.

## Setup
- **Where:** production, https://209-38-84-72.sslip.io, in a fresh browser profile at 1440×900, 100 % zoom, with system notifications off.
- **Never show:** the access code, `.env`, `deploy/secrets/*` or a terminal.
- **Workspace segment:** paste the access code off-camera, or blur it in editing.
- **Live run:** each one costs at most A$2.84, from the A$20 budget. Use one live run only if a fresh run is wanted on camera. Otherwise open the recorded Polished v2 run `#/run/eval-11ee8a1e6dad19998865db7187c8cb5e`; it shows the same grid, traces and report.
- **Order:** record the showcase (`#/showcase`) first, then the Workspace. Scroll the showcase slowly; each scene is sticky.

## Timed script

| Time | Screen | Narration |
|---|---|---|
| 0:00–0:15 | `#/showcase` hero: "Built for people. Tested by agents." Scroll until the Polished v1 site rises | "Personal AI agents are starting to use websites for us. Agent Readiness measures whether they can, with real browser agents, real customer tasks, and answers checked against the business's own records." |
| 0:15–0:35 | Chapter 1: the three Polished v1 pages swap as you scroll | "This is Larkspur Community College, a fictional college. We redesigned its site for people: a new identity, a course finder, labelled facts on every card, and a layout that works on a phone. We kept everything that had already helped agents." |
| 0:35–0:55 | Chapter 2: the three customer questions, then the v1 numbers | "Then three fresh Muse Spark agents got three real customer questions, each in an isolated browser. Every answer was right: three of three, 8 model requests, 65 seconds, eleven cents of model calls." |
| 0:55–1:25 | Chapter 3: scroll through the task 2 trace; pause on step 3 | "Task 2 took four requests where the others took two, so we looked. These are the agent's own screenshots and working notes. It used the finder, read 'four courses found', and could see three. Its note: 'Visible 3… scroll down to reveal the 4th course.' That's one extra step and one extra model request, caused by a tall header and big card images." |
| 1:25–1:45 | Chapter 4: three recommendation cards; then the v1/v2 wipe | "The recommendation: say the whole answer before the first card, and make results fit. Two answers missed the exact-match grade only because they added fees and seats. That's grading format, not the website, so we didn't touch it. Polished v2 is the same site with exactly those two changes." |
| 1:45–2:10 | Chapter 6: the v2 trace; pause on step 4 | "Same tasks, same agent, evaluated again. The agent read the new summary and noted all four courses, then scrolled anyway, 'to verify fourth course details'." |
| 2:10–2:30 | Chapter 7: "v2 did not beat v1." and the table | "So v2 did not beat v1: 9 requests against 8, both three for three. With one agent per task, that difference is within run-to-run variation. The lesson is still real: agents verify. Naming the answer isn't enough; they want each match's deciding facts on screen. That's the next recommendation, not yet built." |
| 2:30–2:45 | "Where Larkspur started": the four result cards | "For context: on the original Larkspur site, agents got zero of three right in 39 requests. Agent Readiness's first round of fixes took that to three of three in 6. The polish kept that." |
| 2:45–3:00 | `#/run`: the Polished v2 preview, the A$20 budget line, then the recorded run grid and report tab | "Anyone with an access code can run this live: enter the code, press Run, watch the agents, read the report. Agent Readiness: evaluate a real website, find the friction, change it, and measure honestly." |

## Guardrails while recording
- Say "did not beat", not "improved". Say "within run-to-run variation", not "proved".
- Costs are calculated from provider-reported token usage and settled from the ledger. They are not invoices.
- Larkspur is fictional. The tasks are frozen and owner-approved (`larkspur-core@v3`).
