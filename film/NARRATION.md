# Opening (0:00–0:25): proposed narration and approvals

**Status:** proposal. No voiceover has been recorded. The `OpeningCaptions` render shows these lines as captions at their intended timings.

## Narration (59 words, about 140 words per minute)
| Time | Picture | Line |
|---|---|---|
| 0:00–0:04 | The Larkspur home page rises out of the dark | "This is Larkspur Community College." |
| 0:04–0:09.5 | The window moves aside; the catalogue scrolls. *Beautifully designed. Easy to browse. Made for people.* | "Its new website is beautiful, clear, and easy for people to use." |
| 0:09.5–0:13 | A wipe into the agent's recorded view; **RECORDED** badge; the customer task | "Now, AI agents browse for us." |
| 0:13–0:17.5 | Step 1 → Step 2: the agent's own notes, the real clicks; *"Need to check each…"* | "We asked one, powered by Meta Muse Spark: which beginner courses meet on weekends?" |
| 0:17.5–0:21.5 | The window recedes. *It works for people. Can an AI agent actually use it?* | "It works for people. But can an agent actually use it?" |
| 0:22–0:25 | The Agent Readiness mark draws itself | "Agent Readiness finds out." |

**Hand-off to Act 2:** the opening ends with the agent's note *"Need to check each for Beginner level + Sat/Sun meeting"* and the step bar at **2 of 14**. Act 2 picks up from that exact moment with the draining budget (signature animation 1).

## Needs approval
1. **The narration text above.** Alternative closing line: "That's what Agent Readiness measures."
2. **Voice:** the owner's own voice, a hired voice, or AI text-to-speech. AI text-to-speech is a paid external service and needs explicit approval. Timing is locked to the voice, so this decision gates the final cut.
3. **Music and sound design:** none yet. Proposed: a restrained, licensed ambient or electronic bed (about 90–100 BPM), with soft UI ticks on the agent's clicks. Needs a source and licence.
4. **On-screen claims in the opening:**
   - "a fictional college"
   - "Recorded run · 4 Nov 2026 · Meta Muse Spark agent"
   - "Step 2 of 14": the task's recorded limit is 14 steps / 14 model requests.
5. **The drawn cursor:** it travels to the recorded click target. The agent has no visible mouse; the cursor visualises the recorded click (approved policy).
6. **The address pill** shows "Larkspur Community College · /path". The real mirror host (a loopback address) is deliberately not shown.

## Facts used (from `data/evidence.json`)
- **Run:** Before `eval-ea13944e8ba5c08e8893426b2f8b1c8f`, started 2026-11-03T23:31:41Z (4 Nov AEDT), model `muse-spark-1.3`.
- **Task 2 (customer wording, verbatim):** "I work full-time on weekdays, so I can only do Saturday or Sunday. List Beginner courses that meet on Saturday or Sunday."
- **Step 1:** note "Homepage shows 14 courses. Need to browse all courses to filter Beginner weekend courses." Action: Click "Browse all courses".
- **Step 2:** note "On /courses page listing 14 courses. Need to check each for Beginner level + Sat/Sun meeting." Action: Click "Watercolour foundations".
