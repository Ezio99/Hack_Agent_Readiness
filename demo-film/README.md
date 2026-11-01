# Agent Readiness — static cinematic storyboard

**Checkpoint A.1 premium refinement, awaiting owner visual review.** Six editable 1920×1080 frames and a contact sheet. No animation, video, backend, model calls or dashboard changes. Work is isolated to `demo-film/` on `demo-cinematic-storyboard`, starting from `7f22307`, following the configurability specification at `0fde28e`.

## Preview

Open [`index.html`](index.html) directly in a browser. It is a contact sheet of exported PNGs; click a frame to inspect its editable HTML. Everything loads from local files, with no service or dependency required. View individual frames at **50% browser zoom** for 960×540 review, or 100% for capture detail.

Alternatively, from the repository root:

```sh
python3 -m http.server 4191 --bind 127.0.0.1 --directory demo-film
```

Open `http://127.0.0.1:4191/`. The server is optional and serves static files only. The contact sheet adapts to narrow screens; individual frames intentionally retain their 1920×1080 artboard.

Exports: [`exports/contact-sheet.png`](exports/contact-sheet.png) and `exports/01-hook.png` through `exports/06-vision.png`. These are static design compositions, not final footage or a fresh evaluation.

## Edit and regenerate

Three separate layers keep presentation independent of evidence:

1. [`demo-manifest.json`](demo-manifest.json) selects the exact report hash/run, contemporary arms, proposal, task, archived event references, focus event, scene order/visibility, copy, voiceover and emphasis. This is an editorial draft, not a new experiment approval.
2. [`evidence_adapter.py`](evidence_adapter.py) reads the selected **existing, sanitized public report**, validates its hash and recorded provenance, and projects an explicit allowlist. It preserves task outcomes, requests, source references and stored verdicts. It never writes the report, reads raw traces, invokes inference or regrades anything.
3. [`scenes.js`](scenes.js) and [`film.css`](film.css) provide reusable compositions. There are no S1 metrics, denominators or event IDs in the components. The generated local JS bundle avoids browser `file://` fetch restrictions.

See [`SCHEMA.md`](SCHEMA.md) for the manifest and adapter interface, replacement procedure and supported limits. Change a headline, featured task, selected events or focus in the manifest, then rebuild; no scene source edit is needed. Scene order is the manifest array order. `visible: false` removes a scene from the contact sheet and export list. `emphasis` selects a composition focus; Checkpoint A provides static emphasis only.

Python 3.10+ is sufficient to project the manifest:

```sh
python3 demo-film/build.py
python3 -m unittest discover -s demo-film -p 'test_*.py' -v
```

To export screenshots, use a Python environment with Playwright and Chromium installed (`python -m pip install playwright`, `python -m playwright install chromium`), then:

```sh
python demo-film/render.py
```

The renderer builds the inputs first, exports all enabled frames and contact sheet, and checks local-file loading, dimensions, image readiness, headline/footer bounds, half-scale layout, narrow contact-sheet layout, keyboard focus and alternate data. It aborts external requests. `generated/narration.txt` resolves evidence placeholders from the same data used for metrics. After any evidence/copy change, regenerate **all** outputs together; do not reuse old PNGs or narration.

`generated/`, `frames/` and `exports/` are reproducible presentation outputs. Edit the manifest/components, not generated files. The prior public dashboard crops in `assets/` and their provenance remain unchanged as reference material. A.1 frames use purpose-built compositions of adapter evidence rather than those small screenshots. Composed views are explicitly labelled; no website captures are invented.

Optional `capture.py` regenerates those UI crops from the unchanged dashboard default, served on loopback port 4190. It deliberately does **not** support arbitrary dashboard reports: build the existing dashboard normally (`cd dashboard && npm ci && npm run build`, retaining its required distribution guard), serve `dashboard/dist` on port 4190, then run `python demo-film/capture.py`. It only allows that loopback origin and verifies the selected fixture. Ordinary preview/rendering does not require this step or Node.

## Frame provenance

| Frame | Visual anchor | Evidence boundary |
| --- | --- | --- |
| 01 Hook | Large equipment-browser illustration, agent goal and amber rental-terms question | Concept only; no recorded actions, website capture or Meta assistant UI. |
| 02 Product | Route-style vector mark and unified Scan → Insights → Improvements → Results rail | Product positioning/presentation vocabulary; not a claim that dashboard navigation already uses these labels or that Meta production agents are integrated. |
| 03 Behavior | Large selected archived action, adjacent-event progression and complete selected-event timeline | Current manifest selects task-1/patched and nine allowlisted entries. Focus is the real browser-tool page-scroll fallback, not a verified website defect. JSON pointers retain original event references, including repeated event numbers. |
| 04 Improvement | Two illustrative equipment listing layouts: less-prominent terms → terms surfaced on card | Existing deposit, minimum-hire and delivery labels only; no invented values, captures or page diffs. Owner-selected and not independently verified. |
| 05 Results | Report-derived metrics, task-outcome strips and relative request bars | Placebo/original 2/4 versus patched/modified 3/4 supported passes; 50 → 29 requests, rounded 42% fewer. Qualification remains visible. Frozen `inconclusive` and exploratory `not_supported` are preserved, not recomputed. Historical baseline/EXP-C/R1 are not pooled. |
| 06 Vision | Opening browser motif reprised, workflow rail and public repository link | Developer-infrastructure vision. Repository visibility was checked read-only as PUBLIC on 2026-11-01; no deployment or integration claim. |

## Validation and handoff

- 14 focused offline adapter/configuration tests pass: source/hash/provenance gating, contemporary-arm selection, missing/void fields, changing task/event selection, repeated-trial rejection, alternate counts/narration, safe projection and read-only source integrity.
- Offline Chromium render checks pass for all six 1920×1080 frames, exact 50% layout and responsive 390px contact sheet/keyboard focus. Alternate-task/copy and long-number/missing-value checks use transient test data only; no synthetic results are exported.
- Visual review: contact sheet plus individual behavior/results frames inspected; headings, primary metrics and featured-event text are clear. Composed recorded action views carry source-event references, while browser/listing illustrations carry explicit concept labels. No dashboard screenshots dominate the composition.
- The local Geist face is checked as loaded; timeline source references, exact selected action text and per-task comparison marks are checked against adapter output.
- Image/source/config hashes are recorded in `assets/capture-provenance.json` and `exports/render-manifest.json`.
- Required critical regression suite: **214 passed, 17 deselected** in 66.70s (offline). A.1 does not alter/build the dashboard; its earlier Checkpoint A build and required distribution guard passed unchanged.
- Final scope check: only `demo-film/` files changed relative to `7f22307`; dashboard, evaluator, public S1 fixture and historical experiment trees unchanged. PR #60 branch remains at `049292e`; the original checkout and its pre-existing untracked prototype files are untouched.

Limitations: this is a static art-direction review, not a three-minute film. Small timeline references/provenance captions are secondary; the main message is carried by large headings, metrics and the featured-event card. Geist is bundled locally under its SIL Open Font License, with system fallbacks; no remote font loading is needed. Committed PNGs show the reviewed rendering. The adapter currently supports one completed trial per contemporary arm/task in already-validated public `investigation-dashboard-v1` reports; other formats/repeats need an explicitly reviewed adapter extension. Only the current public task has archived storyboard entries; selecting another task shows the task question and unavailable-event state, never another task's events. No captured website pages are available in the public S1 asset.

Owner approval of the visual direction is still required before Checkpoint B. No motion work has started.

## A.1 visual review

The locked Midnight / Electric Cyan system lives in `tokens.css`: canvas #080D16, surface #101B2B, elevation #19283B, accent #66D9EF, text #F5F8FC and secondary #A5B4C8. Amber identifies the illustrative terms challenge and recorded browser-tool behavior; green is reserved for evidence-supported outcomes. Tokens are standalone for potential future reuse; the dashboard does not import them.

01 and 06 share a recognizable browser/equipment motif. 02 uses a restrained route mark and connected workflow rail. 03 replaces dense UI with a large exact archived action and progression; the timeline includes every selected entry in source order. 04 makes the owner-selected layout idea tangible with clearly illustrative cards and field names, without prices or fabricated values. 05 emphasizes measured outcomes with per-task pass strips and proportional request bars; frozen verdicts and the improvement-not-established qualification remain visible. No animations or final video are included.

The event progression shows up to three neighboring entries around the explicitly selected focus; it does not choose better-looking outcomes. Long neighboring text is visually truncated with full text in its tooltip; the selected action retains its exact text at a fitted font size. The full selected sequence remains represented by source-reference timeline nodes. Presentation-only browser/listing labels are configurable in the manifest.
