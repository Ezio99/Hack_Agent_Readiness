# Agent Readiness: the film

The hackathon film, built programmatically with [Remotion](https://www.remotion.dev) 4 (React). It lives on the isolated `film` branch only. It is never deployed, and nothing in `dashboard/` or `src/` imports it. The product is not modified to make the film.

**Status:** the complete 3:00 cut is built. Act 1, the opening (0:00–0:25) · Act 2, the investigation (–1:15) · Act 3, the transformation (–1:55) · Act 4, the proof (–2:35; ONLY the paired run, see `CANONICAL.md`) · Act 5, the product and the vision (–3:00; the vision is drawn as a labelled concept). The picture cut is approved. The voiceover pipeline is built and tested end to end, and awaits the recorded voice; until then, timings are placeholders (see `vo/AUDITION.md`).

## What is real and what is drawn
| On screen | Source |
|---|---|
| Larkspur website (opening shots A and B) | The frozen **Before** snapshot (`polishedoriginal`, the exact pages the agents browsed), served through the product's read-only mirror and rendered at 2× in the agents' own font environment (see below) |
| "Recorded" browser view (shot C) | The agent's **own recorded screenshots**, unchanged bytes, from the public report API (Before run `eval-ea13944e…`, task 2) |
| Customer task, agent notes, actions, step limit, run date | `data/evidence.json`, generated from the same records. Nothing is typed by hand |
| Highlight outline, cursor, click pulse | Drawn by the film, but **only** on the target of an action the agent recorded at that step (step 1: Click "Browse all courses"; step 2: Click "Watercolour foundations"). Positions come from the frozen page's layout |
| Act 2 browser windows, notes, ledger, budget | Each recorded step's own screenshot (steps 2–11), verbatim note excerpts (checked at build time), the recorded action, and the step limit (14) from the task record |
| Act 2 report footage | The deployed product's own readiness report for the Before run, captured read-only (`scripts/capture_product.py` → `data/product.json`) |
| Music and sound effects | Original, synthesised by `scripts/score.mjs` (no samples, no third-party audio) |
| Typography, mark, camera moves | Motion design (the Agent Readiness mark is the product's own) |

Audience names only: Larkspur Community College, Before, After, Agent Readiness, Meta Muse Spark. Internal snapshot names, Ironbark, access codes and credentials never appear.

## Setup (zero cost, read-only)
```bash
cd film
npm install                         # Remotion 4.0.540 + its compositor/ffmpeg
npx remotion browser ensure         # Remotion's headless Chrome
./scripts/agent-fonts.sh            # the agents' fonts, into film/.fonts only (nothing system-wide)
cd .. && PYTHONPATH=src ../Hack_Agent_Readiness/.venv/bin/python film/scripts/capture.py   # any env with playwright + the repo's src
../Hack_Agent_Readiness/.venv/bin/python film/scripts/capture_product.py                       # the product's report pages (read-only)
cd film && node scripts/score.mjs                                                               # music + sound effects
```
`capture.py` writes `public/captures/**` and `public/fonts/**` (gitignored, regenerable) and `data/evidence.json` (committed, with the SHA-256 of every captured file). It reads the public report API with GET requests only and calls no model.

**Fonts:** the hosted agents ran Chromium in `python:3.12-slim-bookworm` with Playwright's font packages (Liberation, FreeFont, Loma, IPA Gothic, WenQuanYi) and no DejaVu. `scripts/agent-fonts.sh` reproduces that font set in an isolated fontconfig, and renders at a 1265 px layout (the agents' 1280 px window minus its scrollbar). As a result, the 2× website renders match the recorded screenshots in layout and type.

## Render
```bash
npx remotion studio src/index.ts                                   # scrub and preview
npx remotion render src/index.ts Opening out/opening.mp4           # 1920×1080, 30 fps, H.264 (CRF 16)
npx remotion render src/index.ts Act2 out/act2.mp4
npx remotion render src/index.ts Preview out/film-0-180.mp4        # the whole film, one continuous score (Act3/Act4/Act5 render alone too)
```
Every composition has a `…Captions` variant that shows the narration lines at their cue times.

### Voiceover
```bash
node scripts/vo.mjs align          # measure public/audio/vo/act1..act5, level to -17 LUFS, place every line -> data/vo.json
node scripts/score.mjs             # re-time the score to the voice (always after align)
node scripts/vo.mjs audition       # audition clips in public/audio/vo/audition/ -> data/audition.json
npx remotion render src/index.ts Audition out/audition-dan.mp4 --props='{"voice":"dan"}'
node scripts/vo.mjs clear          # back to placeholder timing
node scripts/elevenlabs.mjs …      # optional API route (dry run unless --confirm), see vo/AUDITION.md
```

## Layout
```
src/Root.tsx            one composition per act + the running preview; music / SFX / voiceover tracks
src/narration.ts        the narration cue sheet (text + designed timing per act), voice placement and the timeline warp; scenes anchor to its cue ids
src/Voice.tsx           the voice track (lines cut at the narrator's pauses), the music ducking, the audition composition
data/vo.json            measured voice: where each line sits in its act file (written by scripts/vo.mjs)
src/scenes/Opening.tsx  Act 1
src/scenes/Act2.tsx … Act5.tsx  Acts 2–5
src/components/         BrowserWindow, PageImage, ActionHighlight, Typed, StepBudget, Mark
src/theme/              product colours (dark theme) and OFL fonts (Newsreader, Geist, Geist Mono)
src/evidence.ts         typed access to data/evidence.json
scripts/                capture.py, capture_product.py, capture_transform.py, capture_paired.py, agent-fonts.sh, score.mjs, vo.mjs, elevenlabs.mjs
NARRATION.md            narration with timings, voiceover plan, approvals
vo/AUDITION.md          voice audition, generation and integration
vo/SCRIPT.md            the narration, one paste per act
```

## Licences
- Fonts: SIL OFL (licence files copied alongside).
- Liberation, FreeFont, Loma, IPA and WenQuanYi fonts are used only to render captures, and are not redistributed.
- Remotion is free for individuals and organisations of up to 3 people; larger teams need a company licence. The owner must confirm.
