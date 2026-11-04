# Agent Readiness: the film

The hackathon film, built programmatically with [Remotion](https://www.remotion.dev) 4 (React). It lives on the isolated `film` branch only. It is never deployed, and nothing in `dashboard/` or `src/` imports it. The product is not modified to make the film.

**Status:** only the opening (Act 1, 25 s) exists, as a visual prototype for review. The other acts are not built yet.

## What is real and what is drawn
| On screen | Source |
|---|---|
| Larkspur website (opening shots A and B) | The frozen **Before** snapshot (`polishedoriginal`, the exact pages the agents browsed), served through the product's read-only mirror and rendered at 2× in the agents' own font environment (see below) |
| "Recorded" browser view (shot C) | The agent's **own recorded screenshots**, unchanged bytes, from the public report API (Before run `eval-ea13944e…`, task 2) |
| Customer task, agent notes, actions, step limit, run date | `data/evidence.json`, generated from the same records. Nothing is typed by hand |
| Highlight outline, cursor, click pulse | Drawn by the film, but **only** on the target of an action the agent recorded at that step (step 1: Click "Browse all courses"; step 2: Click "Watercolour foundations"). Positions come from the frozen page's layout |
| Typography, mark, camera moves | Motion design (the Agent Readiness mark is the product's own) |

Audience names only: Larkspur Community College, Before, After, Agent Readiness, Meta Muse Spark. Internal snapshot names, Ironbark, access codes and credentials never appear.

## Setup (zero cost, read-only)
```bash
cd film
npm install                         # Remotion 4.0.540 + its compositor/ffmpeg
npx remotion browser ensure         # Remotion's headless Chrome
./scripts/agent-fonts.sh            # the agents' fonts, into film/.fonts only (nothing system-wide)
cd .. && PYTHONPATH=src ../Hack_Agent_Readiness/.venv/bin/python film/scripts/capture.py   # any env with playwright + the repo's src
```
`capture.py` writes `public/captures/**` and `public/fonts/**` (gitignored, regenerable) and `data/evidence.json` (committed, with the SHA-256 of every captured file). It reads the public report API with GET requests only and calls no model.

**Fonts:** the hosted agents ran Chromium in `python:3.12-slim-bookworm` with Playwright's font packages (Liberation, FreeFont, Loma, IPA Gothic, WenQuanYi) and no DejaVu. `scripts/agent-fonts.sh` reproduces that font set in an isolated fontconfig, and renders at a 1265 px layout (the agents' 1280 px window minus its scrollbar). As a result, the 2× website renders match the recorded screenshots in layout and type.

## Render
```bash
npx remotion studio src/index.ts                                   # scrub and preview
npx remotion render src/index.ts Opening out/opening.mp4           # 1920×1080, 30 fps, H.264 (CRF 16)
npx remotion render src/index.ts OpeningCaptions out/opening-captions.mp4   # same, with the proposed narration as captions
```

## Layout
```
src/Root.tsx            one composition per act (only Opening so far)
src/scenes/Opening.tsx  Act 1 timeline and proposed narration timings
src/components/         BrowserWindow, PageImage, ActionHighlight, Typed, StepBudget, Mark
src/theme/              product colours (dark theme) and OFL fonts (Newsreader, Geist, Geist Mono)
src/evidence.ts         typed access to data/evidence.json
scripts/                capture.py, agent-fonts.sh
NARRATION.md            proposed voiceover + assets awaiting approval
```

## Licences
- Fonts: SIL OFL (licence files copied alongside).
- Liberation, FreeFont, Loma, IPA and WenQuanYi fonts are used only to render captures, and are not redistributed.
- Remotion is free for individuals and organisations of up to 3 people; larger teams need a company licence. The owner must confirm.
