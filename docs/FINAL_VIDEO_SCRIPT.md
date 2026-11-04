# Final video storyboard: Larkspur Community College, before and after (~3:00)

Every number below is a recorded live result, audited against the production records on 2026-11-04.

## Wording and safety
- **Say:** "Larkspur Community College", "Before", "After", "Agent Readiness". Never say internal snapshot names.
- **Never show:** the access code, `.env`, `deploy/secrets/*`, a terminal or browser devtools.

## Setup (before recording)
1. Use Chrome in a fresh profile (no extensions or bookmarks bar), at 1440×900 and 100 % zoom, with system notifications off. Record at 1080p/30 fps.
2. Open these tabs in order, each loaded once so images are cached:
   - **T1** https://209-38-84-72.sslip.io/#/showcase
   - **T2** https://209-38-84-72.sslip.io/#/reports/eval-ea13944e8ba5c08e8893426b2f8b1c8f/tasks/2 (Before, task 2 replay)
   - **T3** https://209-38-84-72.sslip.io/#/reports/eval-ea13944e8ba5c08e8893426b2f8b1c8f/tasks/1 (Before, task 1: the dead end)
   - **T4** https://209-38-84-72.sslip.io/#/reports/eval-5cf934b372942da74f5157c5fca39fd6/tasks/2 (After, task 2 replay)
   - **T5** https://209-38-84-72.sslip.io/#/run/eval-5cf934b372942da74f5157c5fca39fd6 (the recorded After run in the Workspace)
3. **Optional live run** (at most A$2.84 from the A$20 budget): instead of T5, open `#/run`, paste the access code off-camera, and press **Run live evaluation** about 8 minutes before the T5 scene; cut to it once it is running. Otherwise use T5, which is a real recorded run.
4. **Showcase scrolling:** scroll steadily with the trackpad or mouse wheel. Each scene is "sticky" and changes as you scroll. Pause where the table says "hold".

## Storyboard

| # | Time | Tab · action | On screen (real evidence) | Narration (≈150 wpm) |
|---|---|---|---|---|
| 1 | 0:00–0:12 | T1, top. Hold 2 s, then scroll slowly | "Looks great to people. Can agents use it?" The Before home page rises into view | "Personal AI agents are starting to use websites on our behalf. Agent Readiness answers a simple question: can they actually use yours?" |
| 2 | 0:12–0:30 | T1, scroll through Chapter 1; hold on the course-page frame | Before: home → All courses (cards with name, subject and summary only) → course page (Course details) | "This is Larkspur Community College, freshly redesigned for people. Like many catalogues, each course card shows a name and a summary. The fee, class day, level and seats are on each course's own page." |
| 3 | 0:30–0:45 | T1, scroll to Chapter 2 (three question cards) | The 3 frozen customer questions | "We sent three fresh Meta Muse Spark browser agents three real customer questions, in an isolated browser. Every answer is checked against the college's own records, which the agents never see." |
| 4 | 0:45–0:58 | T1, scroll to "Before · measured". Hold | **0/3 · 36 · 311 s · US$0.52** | "Before: not one right answer. Zero of three, 36 model requests, over five minutes of browsing." |
| 5 | 0:58–1:22 | T2: click step **2**, then **9**, then **11** | Recorded screenshots; agent memory at step 11: "Checked 3/14 … Out of steps, returning confirmed 2 weekend Beginner courses." | "Here's why, in the agent's own screenshots and notes. The facts it needed were a click away on every course, so it opened them one at a time. After checking three of fourteen, its note says: out of steps. It found two of the four right courses." |
| 6 | 1:22–1:32 | T3: click step **9** | Step 9: `/courses/introduction-to-python` (the not-found page) | "Another agent guessed a course address from its name, and hit a dead end." |
| 7 | 1:32–1:50 | T1, scroll to Chapter 4 (three cards). Hold | "Put the facts on the cards" · "Fix the dead end" · "Describe each course" | "Agent Readiness found the cause and recommended three changes: put every fact on the course cards, fix the dead end, and describe each course in structured data. Same pages, same design." |
| 8 | 1:50–2:02 | T1, scroll slowly through Chapter 5 (the wipe) | The All courses page wiping from Before to After | "Here's the same catalogue after the change. The design hasn't moved; the facts are now where an agent looks." |
| 9 | 2:02–2:20 | T4: click step **2**, then **6** | After, task 2: memory at step 2 lists all 4 courses from the cards; answer at step 6 | "Same questions, same agent, evaluated again. It read all fourteen cards on one page and answered, without opening a single course page." |
| 10 | 2:20–2:38 | T1, scroll to Chapter 7. Hold on "0/3 → 3/3", then the table | **0/3 → 3/3** · requests **36 → 15** · time **311 s → 121 s** · cost **US$0.52 → US$0.20** | "Zero of three became three of three, with 58 percent fewer model requests and 61 percent less time and cost. That's one agent per question: a measured result for these tasks, not a statistical guarantee." |
| 11 | 2:38–2:55 | T5: show the grid (3 completed), click one cell, then the **Readiness report** tab | The real After run: grid, agent screenshot, report header | "And it's a product, not a slide. With an access code, anyone can run it live: press Run, watch the agents work, and read the report." |
| 12 | 2:55–3:00 | T1, jump to "Your turn." | The finale buttons | "Agent Readiness. See your website the way an agent does." |

## Facts to keep exact (audited)
| Fact | Before | After |
|---|---|---|
| Correct answers | 0/3 | 3/3 |
| Model requests | 36 | 15 |
| Agent time | 311 s | 121 s |
| Settled cost | US$0.52 | US$0.20 |
| Task 2 courses found | 2 of 4 | 4 of 4 |

Both runs were live on 4 Nov 2026, each version alone, with the same 3 frozen tasks and the same agent (muse-spark-1.3). The derived figures are 58 % fewer requests and 61 % less time and cost.

## After recording
- Watch the cut once with the sound off and check that no secret, code or URL token is visible.
- Upload the video with the visibility the form requires, open the link in a signed-out window, and paste it into the submission.
