# Product experience redesign (branch `product-experience-redesign`, 2026-11-02)

Frontend-only redesign of the hosted Agent Readiness site: a product homepage, a cinematic scroll-driven
demo of a real recorded evaluation, and a redesigned evaluation workspace. **Not deployed**; the production
branch `hosted-ironbark-evaluation` and the Droplet are unchanged. No backend, jail, grading, admission,
budget, authorization or historical data was modified. No model call was made.

## Routes (hash routing; the server still serves one static `index.html`)

| URL | Experience |
|---|---|
| `#/` (and `#/problem`, `#/how`, `#/learn`, `#/evidence`, `#/trust`) | Product homepage (sections are deep-linkable) |
| `#/demo`, `#/demo/<scene>` | Cinematic demo; scenes `intro task original friction change modified outcome method run` |
| `#/run`, `#/run/eval-<32 hex>` | Evaluation workspace. **Persistent evaluation URLs are unchanged.** |
| `#/studio` | Previous Replay Studio (archive), loaded on demand |
| `#/investigation`, `#/overview`, `#/scopes`, `#/evidence`, `#/replay`, `#/scanner` | Classic pages (archive), unchanged, loaded on demand |

The default route used to be the Replay Studio; it is now the homepage. The studio's former "Run" stage
now links to `#/run`; "Inspect evidence & replay" in the workspace hands the sanitized export to `#/studio`.

## Design direction

Paper and ink with one signal colour, editorial rather than dashboard. Newsreader (display serif, italic
for emphasis), Geist (interface), Geist Mono (data, captions, figure labels). Figures are numbered and
captioned like a journal. Original = rust `#C2552E` / `#D86C45` (night), Modified = signal blue
`#2B3BE6` / `#7280F2` (night); both pairs pass the dataviz palette validator (lightness band, chroma, CVD
ΔE ≥ 25, normal-vision ΔE ≥ 27, contrast ≥ 3:1). Status colours (pass green, not-passed rust) always ship
with a glyph and a label. Fonts are self-hosted (the production CSP is `default-src 'self'`), OFL texts
are bundled and linked from the footer.

The demo is the night variant of the same system: sticky 100svh stages inside tall scroll tracks. A single
passive scroll listener drives every track in one `requestAnimationFrame` and writes CSS custom
properties (no React render per frame); discrete state (the current agent step, the active chapter)
re-renders only when it changes. Every CSS variable falls back to `1`, the resting state, which is exactly
what reduced motion renders: tracks collapse to normal flow, journeys become click-through steppers.

## Evidence provenance (no fabricated activity)

`src/site/evidence/eval-9aaac35c.json` and `frames/*.webp` were produced by
`scripts/export_demo_evidence.py` from the hosted API's **public allowlisted projection** of
`eval-9aaac35ca488c2bf951e01e58746604a` (job status, all eight trials' steps, insights, sanitized export),
served locally in `AR_HOSTED_MODE=disabled` over a copy of the operator backup. Screenshots are the same
images production serves at `/api/ironbark/jobs/…/screenshots/…`, re-encoded to WebP (de-duplicated, 14
files, ~800 KB). Only task 1 (both arms) and one Modified task-2 frame are bundled.

Every number, step, action, goal, working-memory quote and verdict on the homepage and in the demo is read
from that file at render time. Lines labelled **Note** in the demo are editorial and are each backed by a
recorded memory or path (tests assert the supporting text). Stated honestly in the copy: one repetition;
frozen `paired-signflip-v1` verdict **inconclusive** (p = 0.125 is the minimum a 4-pair exact two-sided
sign-flip test can produce, above α = 0.10); exploratory listing rule **consistent_with_h1**; the change is
owner-selected. The Original task-1 answer is shown as recorded and as graded ("Not passed"); the demo
does not speculate about why the grader rejected it.

## Workspace

Same logic and API contract as before (`HostedEvaluation`, `LiveAgent`, `Analytics`, `Insights`,
`History` moved to `src/site/workspace/`): 1/3/5 repetitions, server-side admission and budget, operator
token sent only as a bearer header, polling, live agent view with real screenshots, per-task grid,
metrics, analytics (charts now drawn at container width, 1 unit = 1 px), insights, history comparison,
persistent URLs. New: a sticky composer column, an empty state that opens the latest evaluation, an
"Export JSON" link to the existing sanitized export endpoint, and on narrow screens an open evaluation is
shown before the composer.

## Checks run (2026-11-02, local, no paid calls)

- `npm run build` (tsc, Vite, `check-dist`): passed; 32 files, no replay data, no credentials/paths.
- `npx vitest run`: 181 passed (170 pre-existing, including every hosted-workspace behaviour test, plus 11 new site tests).
- `pytest tests/test_hosted_{api,admission,service,paired}.py dashboard/scripts/test_{deployment_safety,export_replay}.py -m 'not browser'`: 72 passed.
- `scripts/critical-tests.sh`: 214 passed, 17 deselected.
- Rendered review through the real FastAPI app (production CSP headers, disabled mode, real history) at
  1440×900 and 390×844: homepage, every demo scene at several scroll positions, workspace results/agent/
  insights tabs; reduced-motion render; keyboard tab order and focus rings on all three experiences; no
  console errors or CSP violations.

## Local preview

```bash
cd dashboard && npm ci && npm run build
# serve the build with the real API in disabled mode (no executor, no model path) over a COPY of hosted data:
cd .. && AR_HOSTED_MODE=disabled AR_HOSTED_ROOT=/path/to/copy/of/hosted/live \
  AR_STATIC_DIR=$PWD/dashboard/dist AR_PORT=8765 .venv/bin/python -m agent_readiness.hosted.serve
# open http://127.0.0.1:8765/  ·  /#/demo  ·  /#/run
```
`npm run dev` also works for the homepage and demo (they need no API); the workspace needs the API.
