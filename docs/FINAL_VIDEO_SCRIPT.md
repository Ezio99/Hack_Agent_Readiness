# Final three-minute video: Larkspur Community College, before and after (2026-11-04)

Recording plan. Every number is a recorded live result; read it from the screen.
- **Audience wording:** say "Larkspur Community College", "Before", "After" and "Agent Readiness". Never say internal snapshot names.
- **Setup:** production https://209-38-84-72.sslip.io in a fresh browser profile at 1440×900, 100 % zoom, notifications off. Never show the access code, `.env`, secrets or a terminal; paste the code off-camera or blur it.
- **Live run:** each run of the After site costs at most A$2.84 from the A$20 budget. If no fresh run is needed, open the recorded After run `#/run/eval-5cf934b372942da74f5157c5fca39fd6`.

| Time | Screen | Narration |
|---|---|---|
| 0:00–0:15 | `#/showcase` hero: "Looks great to people. Can agents use it?" Scroll until the site rises | "Personal AI agents are starting to use websites for us. Agent Readiness measures whether they can: real browser agents, real customer questions, every answer checked against the business's own records." |
| 0:15–0:35 | Chapter 1: the three website pages swap as you scroll | "This is Larkspur Community College, freshly redesigned for people. Like many catalogues, each course card shows a name and a summary. The fee, class day, level and seats left are on each course's own page." |
| 0:35–0:55 | Chapter 2: the three questions; then "Before · measured" | "Three fresh Muse Spark agents got three real customer questions. Not one right answer: zero of three, 36 model requests, over five minutes of browsing." |
| 0:55–1:25 | Chapter 3: scroll through the Before trace; pause on the last step | "Here's why, in the agent's own screenshots and notes. It opened course pages one at a time and kept returning to the catalogue. Its last note: 'Checked 3 of 14… out of steps.' Another agent guessed a course address and hit a dead end." |
| 1:25–1:45 | Chapter 4: the three recommendation cards | "Agent Readiness found the cause and recommended three things: put every fact on the course cards, fix the dead end, and describe each course in structured data. Same pages, same design." |
| 1:45–2:00 | Chapter 5: the Before/After wipe | "Here is the same catalogue after the change. The design hasn't moved; the facts are now where an agent looks." |
| 2:00–2:20 | Chapter 6: the After trace | "Same questions, same agent, evaluated again. It read all fourteen cards on one page and answered, without opening a single course page." |
| 2:20–2:40 | Chapter 7: "0/3 → 3/3" and the table | "Zero of three became three of three. Model requests fell from 36 to 15, agent time from 311 seconds to 121, and cost from 52 cents to 20. That's one agent per question: a measured result for these tasks, not a statistical guarantee." |
| 2:40–3:00 | `#/run`: the After preview, the budget line, the recorded After run and its report tab | "Judges can run it live: enter the access code, press Run, watch the agents work, and read the report. Agent Readiness: see your website the way an agent does, fix what gets in the way, and measure the difference." |

## Guardrails
- "Before" is the redesigned original website; "After" is the same design with the recommendations applied. Both were evaluated live on 4 Nov 2026, each on its own, with the same frozen tasks and agent.
- Costs are calculated from provider-reported token usage and settled from each run's ledger; they are not invoices.
- Earlier experiments (3 Nov Original vs Improved; superseded redesign trials) are history. Don't present them as the featured result.
