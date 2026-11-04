# Voiceover: audition and generation guide (ElevenLabs)

## The simplest workflow (about 30 minutes for you, plus about 20 minutes for me to re-time and re-render)
1. **Audition (free, today):** create a free ElevenLabs account. Generate the three audition lines below with **Dan**, then with **Haseeb** (section 1). Choose one voice.
2. **Approve the spend:** the Starter plan costs US$1 for the first month. It is needed for the commercial licence.
3. **Generate (Starter):** Text to Speech, chosen voice, fixed settings. Paste each act from `vo/SCRIPT.md` as its own generation, five generations in all. Download `act1.mp3` … `act5.mp3`.
4. **Hand over:** put the five files in `film/public/audio/vo/`.
5. **I then:**
   - mark each line's start on the waveform and update `src/narration.ts`, with each act set to `status: 'recorded'`;
   - re-render with voice, music and SFX on separate tracks, with the music ducked under the voice.
   If an act's voice runs longer than its picture, I lengthen that act; I never speed up the voice.

**Narrator:** Dan ("warm & engaging British male") is first choice; Haseeb (British documentary, softer) is the alternative. One narrator for all five acts.

**Spending:** none until approved. Auditions use the free plan's monthly credits. The final, licensed generation needs the Starter plan (US$1 for the first month, then US$6/month; it can be cancelled after delivery) and **must be approved first**.

## 1. Audition (free)
1. Sign up at elevenlabs.io (free plan). Open **Voices → Voice Library** and search "Dan" and "Haseeb". Check the descriptions match ("warm & engaging British male"; "British documentary"). Play each preview, then **Add to my voices**.
2. Open **Text to Speech**. Use the default high-quality multilingual model, and the same model for every take.
3. Settings, identical for both voices:
   - Stability **50%**
   - Similarity **75%**
   - Style exaggeration **0–10%**
   - Speaker boost **on**
   - Speed **1.0** (0.95 if rushed)
4. Generate each line below as a **separate clip**, with both voices: 6 clips, about 600 characters each, about 1.2k credits in total. Download them as `dan-1.mp3`, `dan-2.mp3`, `dan-3.mp3`, `haseeb-1.mp3`, and so on.
5. Put the clips in `film/public/audio/vo/audition/`. I will lay each one under its matching picture (Act 1 opening, the Act 2 stop, the Act 5 close) in Remotion Studio, so you judge the voice in context.

**Audition lines:**
1. *(Act 1, curious)* "This is Larkspur Community College. Beautifully designed. Easy for people to browse. But what happens when an AI agent tries?"
2. *(Act 2, tense)* "Three courses checked. Eleven to go. And its interaction budget is running low. So it stops itself, before finding all four matching courses."
3. *(Act 5, optimistic; wording to be approved)* "Agent Readiness. Building the discovery layer for the agentic web."

**Judge on:**
- warmth without sentimentality;
- natural pauses at full stops;
- no trailer-announcer emphasis;
- staying believable from curious, to tense, to optimistic.

## 2. Final generation (after approval of the voice and the Starter plan)
- **One file per act.** Generate from `film/vo/SCRIPT.md`, one act per generation, so pacing stays consistent within each act. Keep the same voice, model and settings throughout.
  - Use a full stop to get a pause, and a new paragraph for a longer one.
  - Avoid SSML or tags unless a line keeps rushing.
- **Takes:** two per act. Pick the best whole take; avoid splicing sentences from different takes.
- **Files:** export the highest-quality format the plan allows, and save as `film/public/audio/vo/act1.mp3` … `act5.mp3` (WAV is also fine).
- **Timing:** the voice sets the animation, not the other way round.
  - For each act, I mark where each line starts, either from ElevenLabs' character timestamps (if generated through the API) or by ear on the waveform in Remotion Studio.
  - I write those frames into `src/narration.ts` and set the act's `status: 'recorded'`. The scene beats move with them.
  - The voice is never stretched to fit the picture. If an act runs long, the act's length grows.
- **Budget:** the whole film is about 430 words, roughly 2.7k characters. Two takes of everything is about 5.5k credits, well within Starter's 30k.
