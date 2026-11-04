# Voiceover: audition, generation and integration (ElevenLabs)

The picture is approved and the integration pipeline is built and tested. The only thing missing is the voice itself, and producing it needs your ElevenLabs account.

## The simplest workflow

There are two equivalent routes; pick one.

### Route A, the website (no key shared)
1. **Audition (free):**
   - Create a free ElevenLabs account.
   - In **Voices → Voice Library**, find **Dan** ("warm & engaging British male") and **Haseeb** (British documentary, softer), and choose **Add to my voices**.
   - In **Text to Speech**, generate the three audition lines (section 1) with each voice, using the settings in section 2.
   - Save the clips as `film/public/audio/vo/audition/dan-1.mp3`, `dan-2.mp3`, `dan-3.mp3`, `haseeb-1.mp3`, and so on.

   If the library shows "not available for free users" for either voice, the audition also needs Starter (step 2).
2. **Approve the spend:**
   - Starter costs US$1 for the first month, then US$6/month, and can be cancelled after delivery.
   - It is required for the commercial licence. The free plan's audio must not be used in the film.
3. **Generate:**
   - Use the chosen voice and the same settings.
   - Paste each act from `vo/SCRIPT.md` as its own generation: five generations, two takes each.
   - Save your preferred take of each act as `film/public/audio/vo/act1.mp3` … `act5.mp3`.

### Route B, the API (exact word timings)
1. Put the key in `film/.env` as `ELEVENLABS_API_KEY=…`. The file is gitignored; the scripts read it but never print it.
2. Check the account and voices:
   - `node scripts/elevenlabs.mjs account` shows the plan and credits left.
   - `node scripts/elevenlabs.mjs voices` lists the voices added to My voices.
3. Generate. Every command is a dry run that prints the character cost until you add `--confirm`.
   - `node scripts/elevenlabs.mjs audition --voice Dan --confirm` (then `--voice Haseeb`): 336 characters per voice.
   - `node scripts/elevenlabs.mjs acts --voice Dan --confirm`: 2,279 characters for all five acts. Add `--take 2` to get a second take.

   The API also saves ElevenLabs' character timestamps, so every line is placed exactly.

### Then, either route
I run the following:
- **Auditions:**
  - `node scripts/vo.mjs audition`
  - `npx remotion render Audition out/audition-dan.mp4 --props='{"voice":"dan"}'` (and the same for Haseeb)

  Each voice's three clips are laid under the pictures they belong to (the Act 1 opening, the Act 2 stop and the Act 5 close), with the film's music and mix, so the voices are judged in context.
- **The film:**
  - `node scripts/vo.mjs align` measures the act files and places every line.
  - `node scripts/score.mjs` re-times the music to the voice.
  - Render the complete film for approval.

## How the voice drives the picture
- **Levelling:**
  - Each act file is brought to **−16 LUFS** with a single fixed gain. A transparent look-ahead limiter catches only the rare peaks above −2 dBFS.
  - There is no compression, no speed change and no time stretch.
- **Lines:**
  - Each line's start and end come from the API timestamps, or from the waveform: speech is detected and grouped into the act's lines at the narrator's pauses.
  - A line whose speaking rate is unusual is flagged as a likely mis-cut. It can be corrected by hand in `public/audio/vo/overrides.json`.
- **Placement:**
  - Each line plays at its designed frame in the approved cut. It may start up to 0.4 s early if it would otherwise run into the next line.
  - It is never earlier than the previous line's end plus a natural breath (0.27–0.5 s).
  - If a line is longer than its slot, later beats move. If an act's voice is longer than its picture, the act grows; nothing is cut or sped up.
  - Every picture beat follows. Beats tied to a line move with it, and beats between lines (the recorded steps in Act 2, the opening's camera moves) are re-timed proportionally between the surrounding lines.
- **Music:** the score is regenerated on the same timeline, so its harmony changes, bells and pulse stay on the picture.
- **Mix:**
  - The voice plays at unity.
  - Music sits at 0.75 between lines and dips smoothly to 0.27 under speech (about 13 dB below the voice): an 8-frame dip before the first word and a 20-frame recovery after the last.
  - Sound effects stay where the recorded events are.
- **Captions:** the captioned version shows each line from its first word to just after its last.
- **Test:** the whole chain has been run end to end with a local stand-in voice (Windows text-to-speech). That build carries a red "SCRATCH VOICE · TIMING TEST, NOT FOR RELEASE" mark and is never published as the film.

## 1. Audition lines (one clip each)
1. *(Act 1, curious)* "This is Larkspur Community College. Beautifully designed. Easy for people to browse. But what happens when an AI agent tries?"
2. *(Act 2, tense)* "Three courses checked. Eleven to go. And its interaction budget is running low. So it stops itself, before finding all four matching courses."
3. *(Act 5, optimistic)* "Agent Readiness. Building the discovery layer for the agentic web."

Put each sentence group on its own paragraph, as above, so the voice pauses between them.

**Judge on:**
- warmth without sentimentality;
- natural pauses at full stops;
- no trailer-announcer emphasis;
- staying believable from curious, to tense, to optimistic.

## 2. Settings (identical for every clip)
- **Model:** Eleven v4 (`eleven_v4`), chosen 2026-11-04 after Dan and Haseeb on Multilingual v2 sounded robotic. Use the same model throughout.
- **Stability** 50%
- **Similarity** 75%
- **Style exaggeration** 5% (0–10%)
- **Speaker boost** on
- **Speed** 1.0 (0.95 if rushed)

## 3. Final generation
- **One file per act**, so pacing stays consistent within each act. Use the same voice, model and settings throughout.
  - Put each narration line on its own paragraph, as in `vo/SCRIPT.md`.
  - No SSML or tags unless a line keeps rushing.
- **Takes:** two per act. Pick the best whole take; never splice sentences from different takes.
- **Files:** the highest-quality format the plan allows (MP3 192 kbps or WAV), saved as `film/public/audio/vo/act1.mp3` … `act5.mp3`.
- **Budget:** the whole film is 2,279 characters. Two takes of everything plus both auditions come to about 5.2k credits, well within Starter's 30k.
