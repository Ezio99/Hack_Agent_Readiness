# Narration, voiceover pipeline and approvals (Acts 1–2)

**Status:** the narration text below is approved for Act 1 and proposed for Act 2. No voice is recorded yet. All timings are placeholders, estimated at about 140 words per minute.

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
| a2.low | 0:51.7 | Three courses checked. Eleven to go. And the budget is running low. | Steps 9–10; the remaining segments turn rust; *"low on steps (step 10/14)"* |
| a2.stops | 0:58.7 | So it stops, and answers with what it has: two of the four right courses. | *"Out of steps."*; FOUND ×2, MISSED ×2 |
| a2.recorded | 1:04.3 | Agent Readiness recorded every step, every screenshot, every decision, and traced the failure to its cause. | The product's own report: 2 of 4, 11 of 14 requests, the agent's answer |
| a2.cause | 1:10.0 | The facts the agent needed are on every course page, and on none of the catalogue cards. | "level / class day: item pages only" → the finding "Listing cards omit 'class day'" and its recommendation |

**Hand-off to Act 3:** the act ends on the report's recommendation, "State class day on each card of /courses", which sets up the improvements.

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

**Timing pipeline once a voice is chosen:**
1. Generate each act separately and save it as `public/audio/vo/act1.wav`, `act2.wav`, and so on.
2. Set that act's `status: 'recorded'` in `src/narration.ts`.
3. Measure each line's start: ElevenLabs can return character-level timestamps with the audio, which a small script can turn into cue frames; otherwise mark them by ear on the waveform in Remotion Studio.
4. Write those frames into the cue sheet. Scene beats move with them; the voice is never time-stretched to fit the animation.

## Tracks
| Track | File | Notes |
|---|---|---|
| Music | `public/audio/music/score.wav` | Original temp score, synthesised by `scripts/score.mjs`: no samples, no licence, no cost. It is a restrained ambient bed: warm D major for the website; a tonal shift and a soft heartbeat pulse when the recorded agent appears; the pulse speeds up (72 → 120 bpm) as the budget drains and stops dead at "out of steps"; then clarity for the diagnosis. It can be replaced by a licensed track (needs approval if paid). |
| Sound effects | `public/audio/sfx/{click,tick,chime,stop}.wav` | Also synthesised. Soft clicks on the agent's two recorded clicks, a tick on every recorded step, a low stop, and a chime under the mark. |
| Voiceover | `public/audio/vo/<act>.wav` | One file per act; played only when that act's status is `recorded`. |

## Needs approval
1. **Act 2 narration text** (above).
2. **ElevenLabs:** free-plan auditions now (no cost), then Starter (US$1 first month) for the final, licensed generation.
3. **The temp score:** keep the original synthesised score, or license or commission one (ask first if it is paid).
4. **The truthful budget framing** above: "Out of steps" as the agent's words, with 3 of 14 left on screen.
