# Narration, voiceover pipeline and approvals (the complete film, 0:00–3:00)

**Status:**
- Act 1, Act 2 (with the corrected budget wording) and Act 3: approved.
- Act 4 and Act 5: adapted from the director's suggested lines; please confirm. No voice is recorded yet. All timings are placeholders, estimated at about 140 words per minute.

The cue sheet in `src/narration.ts` is the single source of truth. Scenes anchor their beats to cue ids, never to fixed frames. Once a real voice is recorded, only the cue times change and the animation follows the voice.

## Act 1: the opening (0:00–0:25) · approved text, about 45 words
| Cue | Film time | Line | Picture |
|---|---|---|---|
| a1.college | 0:00.4 | This is Larkspur Community College. | The home page rises out of the dark |
| a1.designed | 0:03.9 | Beautifully designed. Easy for people to browse. | The window glides aside; the catalogue scrolls; the two lines in type |
| a1.question | 0:08.3 | But what happens when an AI agent tries? | The window dims; the question in large type |
| a1.task | 0:11.0 | We gave a Meta Muse Spark agent a simple task: find beginner courses that meet on weekends. | A wipe into the agent's recorded screenshots; the task; step 1 click |
| a1.browsing | 0:17.2 | It started browsing. | Step 2: its note in large type, *"Need to check each for Beginner level + Sat/Sun meeting."*, then the real click |
| a1.watching | 0:19.9 | And Agent Readiness was watching. | The Agent Readiness mark, then a fade to black (no tagline) |

## Act 2: the investigation (0:25–1:15) · proposed text, about 105 words
| Cue | Film time | Line | Picture |
|---|---|---|---|
| a2.facts | 0:25.7 | To answer, the agent needs two facts about every course: its level, and the day it meets. | Step 2 window; budget at 12 of 14 left; "Level. Meeting day." |
| a2.pages | 0:30.0 | The catalogue doesn't show them. They're on fourteen separate course pages. | The 14 real course pages appear |
| a2.opens | 0:34.5 | So it opens them. One at a time. | The loop begins: each recorded step's screenshot stacks on the last; a tick per step |
| a2.cost | 0:40.7 | Every page costs a step. Every trip back to the catalogue costs another. | Steps 4–6: catalogue → course page → catalogue |
| a2.low | 0:51.7 | Three courses checked. Eleven to go. And its interaction budget is running low. | Steps 9–10; the remaining segments turn rust; *"low on steps (step 10/14)"* |
| a2.stops | 0:58.7 | So it stops itself, before finding all four matching courses. It names just two. | *"Out of steps."*, labelled as the agent's own note at step 11, with 3 of 14 steps left; FOUND ×2, MISSED ×2 |
| a2.recorded | 1:04.3 | Agent Readiness recorded every step, every screenshot, every decision, and traced the failure to its cause. | The product's own report: 2 of 4, 11 of 14 requests, the agent's answer |
| a2.cause | 1:10.0 | The facts the agent needed are on every course page, and on none of the catalogue cards. | "level / class day: item pages only" → the finding "Listing cards omit 'class day'" and its recommendation |

**Hand-off to Act 3:** the act ends on the report's recommendation, "State class day on each card of /courses", which sets up the improvements.

## Act 3: the transformation (1:15–1:55) · proposed text, about 95 words
| Cue | Film time | Line | Picture |
|---|---|---|---|
| a3.diagnosis | 1:15.4 | The diagnosis was clear. The facts agents need are missing from the catalogue. | The report's finding recedes; the diagnosis, isolated, in large type |
| a3.three | 1:19.5 | Agent Readiness recommended three changes. The first matters most. | 01 Put the facts on the catalogue cards (dominant) · 02 Fix the dead end · 03 Structured data |
| a3.cards | 1:22.7 | Take each course’s facts off its own page, and put them on its catalogue card. | Mindful meditation's Before course page: its 7 facts highlight, lift off and fly onto its catalogue card, which resolves into the real After catalogue |
| a3.same | 1:29.7 | Same design. Same pages. But now every card shows its level, day, fee and seats. | The After catalogue grows to centre: "Facts on catalogue cards: 14 of 14" |
| a3.visible | 1:34.5 | All four weekend beginner courses, visible from one page. | The camera pulls back: the 4 matching cards with Level and Class day outlined |
| a3.deadend | 1:38.7 | It also fixed a dead end, where an agent’s guessed address led nowhere. | Recorded Before "Not found" (task 1, step 9) → the same address on After opens the course |
| a3.data | 1:44.7 | And it described every course in structured data that agents can read directly. | The After course page + its own JSON-LD (verbatim excerpt) |
| a3.again | 1:50.6 | Then the same agent got the same task, on the improved website. | "Same task. Same agent. Same limits." and a full 14-step budget |

**Act 3 evidence:**
- Every flying fact is a real row of the Before course page, and it lands on the box where the After card shows the same label and value. The build fails if any pair differs.
- Every catalogue image is the frozen Before or After snapshot.
- The dead end is the recorded screenshot from the diagnostic run (the run whose report produced these recommendations).
- The JSON-LD lines are a verbatim excerpt of the After page's own data.

## Act 4: the proof (1:55–2:35) · about 75 words · evidence: ONLY the paired run `eval-1cf64d5e`
| Cue | Film time | Line | Picture |
|---|---|---|---|
| a4.again | 1:55.4 | We ran the same tasks again, this time with both versions side by side, in a new evaluation. | "A new live evaluation · 4 Nov 2026, 3:18 pm" · "Before and After, side by side." · Same 3 customer tasks / Same Meta Muse Spark agent / Same 14-step limit |
| a4.before | 2:00.5 | Before, the agent found just one of four matching courses. | Before: its 13 recorded steps stack fast (a tick each), the budget drains to 1 left; *"Remaining 10 unchecked due to step budget…"*; found 1 of 4 |
| a4.after | 2:09.8 | After, it found all four, in three requests, without opening a single course page. | After, beside it: one clean window, 3 steps; *"Found 4 candidates … all Beginner."*; 4 of 4 · 3 of 14 requests · 18 s · no course pages |
| a4.correct | 2:19.0 | Across the three tasks, correct answers went from zero to three. | **0/3 → 3/3**, "Correct answers · checked against the college's records"; Task 1–3 ✕ → ✓ |
| a4.metrics | 2:24.2 | Seventy-four percent fewer requests. Eighty-three percent less time. Seventy-seven percent lower cost. | 74% (39 → 10) · 83% (326 s → 57 s) · 77% (US$0.57 → US$0.13), each with to-scale bars |
| a4.works | 2:30.7 | Same agent. Same tasks. A website that finally works for it. | The product's Live report for this run: the Before/After summary cards highlighted |

**Act 4 evidence:**
- **Single source:** every number and frame comes from `eval-1cf64d5e`, captured by `scripts/capture_paired.py` into `data/paired.json`.
- **Build-time check:** the build fails if the record disagrees with the spoken figures (74/83/77, 0/3 → 3/3, 13 and 3 requests).
- **Terminology:** "Correct answers" is the product's correctness metric. The Live report footage also shows "Exact match 1/3" for After, honestly and separately; the narration never claims exact match.
- **Nothing from the 4 Nov diagnostic run or the After-alone run** appears in this act. The title card establishes it as a new evaluation.

## Act 5: the product and the vision (2:35–3:00) · about 48 words
| Cue | Film time | Line | Picture |
|---|---|---|---|
| a5.today | 2:35.5 | Today, Agent Readiness helps websites understand how AI agents experience them. | The real Workspace and Live report, floating. The internal budget ID in the Workspace header is covered. |
| a5.tomorrow | 2:40.5 | Tomorrow, it could help agents discover which websites they can actually use. | A dashed frame labelled **"CONCEPT · TOMORROW · NOT YET BUILT"** and "Illustrative sites and values". An agent with a task asks: which websites can I actually use? |
| a5.which | 2:46.0 | Which ones support their task. Which ones are reliable. And where they can succeed. | Four fictional `.example` sites, scored on: Supports the task / Usable by agents / Reliable / Effort to succeed. The agent goes where it can succeed. |
| a5.brand | 2:53.7 | Agent Readiness. | The real mark draws; the wordmark |
| a5.tagline | 2:55.5 | Building the discovery layer for the agentic web. | The tagline; hold to 3:00 |

## Evidence notes
- **Truthful framing of the budget:** the agent did **not** hit the 14-step cap. It used 11 of 14 (`limit_stop: false`), and its own note at step 11 says *"Out of steps"*.
  - The film shows exactly that: the counter ends at 3 of 14 left, labelled "The agent's note at step 11 of 14 · it stopped and answered".
  - The narration says "the budget is running low … so it stops", never that the budget hit zero.
- **Quotes are verbatim:** every on-screen note is a verbatim excerpt of the recorded note. `excerpt()` in `src/evidence.ts` fails the build if an excerpt is not in the record.
- **Source of "the four right courses":** the After run's answer to the same task, which the official grader matched exactly to the college's own records.
  - Found by Before: Beginners yoga and Wheel-thrown pottery.
  - Missed: Mindful meditation and Home electrical basics.
- **Report footage** is the deployed product's own report for this Before run, captured read-only (`scripts/capture_product.py`). It shows "Not correct · Not an exact match", which is honest for Before.

## Voiceover recommendation
**Service: ElevenLabs.** One narrator for the whole film, with one file per act.

**Candidate voices** (from ElevenLabs' Voice Library listings; audition before choosing):
1. **Dan, "warm & engaging British male"** (recommended first): closest to the brief's warm, confident, conversational delivery.
2. **Haseeb, "soothing and engaging British documentary voice"**: softer and more intimate; good for curiosity and optimism.
3. **Russell, "deep & serious British documentary narrator"**: strongest in the tension of Act 2. There is a risk of a trailer tone, so audition with low style exaggeration.

**How to audition (free, no purchase):**
1. Create a free ElevenLabs account and open the Voice Library. Listen to each voice's preview (free).
2. On the free plan (about 10k credits/month, roughly 10 minutes of audio), generate the three audition lines in `film/vo/AUDITION.md` with each voice:
   - Act 1: curiosity
   - Act 2: tension
   - Act 5: optimism
   That is about 600 characters per voice, about 1.8k credits for all three voices.
3. Settings to start from: stability around 50%, similarity around 75%, style exaggeration 0–15%. Keep the same settings for every act.
4. Send me the takes, or drop them in `public/audio/vo/audition/`. I'll lay them against the picture in Remotion Studio so you can judge them in context.

**Licensing: needs your approval.** ElevenLabs' pricing page lists the commercial licence from the Starter plan (US$1 for the first month, then US$6/month; it can be cancelled after delivery). Third-party guides say the free plan is non-commercial and may require attribution. The final film audio should therefore be generated on Starter.
- The whole film's narration is about 430 words, roughly 2.6k characters, so even several takes per act fit well within Starter's 30k credits.
- No subscription has been purchased and no audio has been generated.

**Timing pipeline (built and tested end to end with a local stand-in voice; full detail in `vo/AUDITION.md`):**
1. Save the chosen take of each act as `public/audio/vo/act1.mp3` … `act5.mp3`.
2. `node scripts/vo.mjs align`:
   - levels each file to −16 LUFS;
   - finds every line, from ElevenLabs timestamps if generated through the API or from the waveform otherwise;
   - writes `data/vo.json`.

   `src/narration.ts` then places each line at its designed frame, or later if the voice needs the room. Beats tied to a line move with it, and beats between lines are re-timed proportionally. An act grows only if its voice is longer than its picture. The voice is never stretched or sped up.
3. `node scripts/score.mjs` re-times the score to the same timeline.
4. Render, then `node scripts/master.mjs`: one gain to about −16 LUFS integrated, with true peak at or below −1 dBTP.

## Tracks
| Track | File | Notes |
|---|---|---|
| Music | `public/audio/music/score.wav` | Original temp score, synthesised by `scripts/score.mjs`: no samples, no licence, no cost. It is a restrained ambient bed: warm D major for the website; a tonal shift and a soft heartbeat pulse when the recorded agent appears; the pulse speeds up (72 → 120 bpm) as the budget drains and stops dead at "out of steps"; then clarity for the diagnosis. It can be replaced by a licensed track (needs approval if paid). |
| Sound effects | `public/audio/sfx/{click,tick,chime,stop}.wav` | Also synthesised. Soft clicks on the agent's two recorded clicks, a tick on every recorded step, a low stop, and a chime under the mark. |
| Voiceover | `public/audio/vo/<act>.mp3` (levelled copies in `vo/mix/`) | One file per act, cut at the narrator's own pauses and placed line by line. Music dips to about 13 dB below the voice under each line. |

## Needs approval
1. **Act 2 narration text** (above).
2. **ElevenLabs:** free-plan auditions now (no cost), then Starter (US$1 first month) for the final, licensed generation.
3. **The temp score:** keep the original synthesised score, or license or commission one (ask first if it is paid).
4. **The truthful budget framing** above: "Out of steps" as the agent's words, with 3 of 14 left on screen.
