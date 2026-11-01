# Agent Readiness — static cinematic storyboard

**Checkpoint A draft, awaiting owner visual review.** Six editable 1920×1080 frames and a contact sheet. No animation, video, backend, model calls or dashboard changes. Work is isolated to `demo-film/` on `demo-cinematic-storyboard`, following the specification at `0fde28e` (the requested original base was `4eac56a`).

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

`generated/`, `frames/` and `exports/` are reproducible presentation outputs. Edit the manifest/components, not generated files. The only captured images in `assets/` are public dashboard components with source and image hashes in `assets/capture-provenance.json`. They are not website captures. Mismatched source/selection bindings disable these crops; reusable composed evidence views remain available.

Optional `capture.py` regenerates those UI crops from the unchanged dashboard default, served on loopback port 4190. It deliberately does **not** support arbitrary dashboard reports: build the existing dashboard normally (`cd dashboard && npm ci && npm run build`, retaining its required distribution guard), serve `dashboard/dist` on port 4190, then run `python demo-film/capture.py`. It only allows that loopback origin and verifies the selected fixture. Ordinary preview/rendering does not require this step or Node.

## Frame provenance

| Frame | Visual anchor | Evidence boundary |
| --- | --- | --- |
| 01 Hook | Illustrative user goal and Browse/Compare/Verify cards | Concept only; no recorded actions, website capture or Meta assistant UI. |
| 02 Product | Brand and Scan → Insights → Improvements → Results | Product positioning/presentation vocabulary; not a claim that dashboard navigation already uses these labels or that Meta production agents are integrated. |
| 03 Behavior | Actual public report storyboard plus a selected event composed from its exact archived text | Current manifest selects task-1/patched and nine allowlisted entries. Focus is the real browser-tool page-scroll fallback, not a verified website defect. JSON pointers retain original event references, including repeated event numbers. |
| 04 Improvement | Actual owner-selected suggestion card beside an illustrative field layout | Existing deposit, minimum-hire and delivery labels only; no invented values, captures or page diffs. Owner-selected and not independently verified. |
| 05 Results | Report-derived metrics and actual contemporary task-outcome rows | Placebo/original 2/4 versus patched/modified 3/4 supported passes; 50 → 29 requests, rounded 42% fewer. Qualification remains visible. Frozen `inconclusive` and exploratory `not_supported` are preserved, not recomputed. Historical baseline/EXP-C/R1 are not pooled. |
| 06 Vision | Workflow, brand and public repository link | Developer-infrastructure vision. Repository visibility was checked read-only as PUBLIC on 2026-11-01; no deployment or integration claim. |

## Validation and handoff

- 14 focused offline adapter/configuration tests pass: source/hash/provenance gating, contemporary-arm selection, missing/void fields, changing task/event selection, repeated-trial rejection, alternate counts/narration, safe projection and read-only source integrity.
- Offline Chromium render checks pass for all six 1920×1080 frames, exact 50% layout and responsive 390px contact sheet/keyboard focus. Alternate-task/copy and long-number/missing-value checks use transient test data only; no synthetic results are exported.
- Visual review: contact sheet plus individual behavior/results frames inspected; headings, primary metrics and featured-event text are clear. Actual UI crops remain visually distinct from navy illustrative scenes. The product subtitle was separated from its headline during review.
- Image/source/config hashes are recorded in `assets/capture-provenance.json` and `exports/render-manifest.json`.
- Required critical regression suite: **214 passed, 17 deselected** in 64.92s (offline). The existing dashboard was built without source changes and its required distribution guard passed.
- Final scope check: only `demo-film/` files added relative to `0fde28e`; dashboard, evaluator, public S1 fixture and historical experiment trees unchanged. PR #60 branch remains at `049292e`; the original checkout and its pre-existing untracked prototype files are untouched.

Limitations: this is a static art-direction review, not a three-minute film. Small text inside actual report crops is secondary and best inspected at 100%; the main message is carried by large headings, metrics and the featured-event card. System Arial/Helvetica fallbacks can vary slightly across machines; committed PNGs show the reviewed rendering. The adapter currently supports one completed trial per contemporary arm/task in already-validated public `investigation-dashboard-v1` reports; other formats/repeats need an explicitly reviewed adapter extension. Only the current public task has archived storyboard entries; selecting another task shows the task question and unavailable-event state, never another task's events. No captured website pages are available in the public S1 asset.

Owner approval of the visual direction is still required before Checkpoint B. No motion work has started.
