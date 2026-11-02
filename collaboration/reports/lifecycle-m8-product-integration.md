# Report: lifecycle M8, integrating the evaluation lifecycle into the Agent Readiness product

**Date:** 2026-11-03/04. **Branch:** `m8-product-integration` (from `research/llm-task-planning` @ `604599a`). Not merged, not deployed.
**Spending:** none. No model call was made; every run in this milestone used fixtures, the recorded M7 evidence, or the loopback dev provider (a scripted
stand-in, not a model). The programme ledger is unchanged.

**Release-candidate status:** ready for owner review at the production release checkpoint. Deployment, merging, web approval and paid launch are
**not** done and need the owner (§9).

---

## 1. What M8 delivers

One evaluation lifecycle in the web product, with one data model behind every evaluation, recorded or new:

| Step | In the product | State |
|---|---|---|
| 1. Website onboarding | `#/lifecycle/website`: registered website contexts (Larkspur, Ironbark) with business context, goals, personas, weighted journeys and the content-hashed variants | **working** (view). Onboarding from a URL: **disabled** with reason (no oracle for uncontrolled sites) |
| 2. AI-assisted generation and validation | `#/lifecycle/tasks`: the recorded M6 generation run: settings, rounds (tokens, latency, cost), all 24 proposals with admission, rejection reasons and wording traces, feedback, gap report, post-fix re-evaluation | **working** (view). New paid generation: **disabled** (needs owner authorisation) |
| 3. Review, approval, freezing | `#/lifecycle/review`: suites and states (`proposed` / `approved` / `rejected` / `frozen`), the exact full hash, every task's wordings and assumptions, coverage gaps, approval and freeze records, the owner checklist and attestation text | **working** (view). Web approval: **disabled**, refused server-side (403); terminal approval unchanged |
| 4. Browser-agent evaluation | `#/lifecycle/evaluate`: launch form (frozen suite + two registered variants; the server picks the manifest), live job progress, recorded evaluations | **zero-cost rehearsal launch: working** (operator-only, needs the store on the server). **Paid launch: disabled**, refused server-side before anything is reserved |
| 5. Multidimensional report | `#/reports/<id>`: six dimensions, task matrix, exploratory analysis, diagnostics split into observed facts and hypotheses, provenance | **working** for the M7 dataset and for launched evaluations (same page, same projection) |
| 6. Re-evaluation | `#/lifecycle/reevaluate`: same frozen suite on other registered variants; the server builds a regression manifest that may differ only in its variants | **working** as a rehearsal (tested); paid disabled |
| Trace experience | `#/reports/<id>/tasks/<n>`: Original and Modified side by side: real screenshots with a step player, path, requests/limit, time, cost, v1 / v2 / prospective outcomes, evidence counts, task diagnostics | **working** |

The preloaded M7 experiment is **not** a separate dashboard: the server projects it with exactly the function it uses for launched evaluations
(`lifecycle/projection.py`); the dataset is that projection, serialised and validated. Both are served through the same routes and rendered by the same
components.

Homepage hero and footer link to the lifecycle and the Larkspur report; the hosted Ironbark workspace (`#/run`) and every existing route are unchanged.

## 2. Architecture

New package `src/agent_readiness/lifecycle/` (product layer; research modules are reused, not copied):

| Module | Role |
|---|---|
| `projection.py` | The public evaluation document from the lifecycle store plus Stage B run directories: tasks, per-trial grades (v1 as recorded, v2 post-hoc, prospective rules), oracle-derived **counts only**, metrics, navigation, reliability, the six dimensions, the exploratory analysis (v1 and v2), sanitized diagnostics, the durable ledger's settled totals. Rehearsals withhold the stand-in's answers. `trial_timeline` reuses `hosted/telemetry.py` unchanged. |
| `audit.py` | Leak audit for every public document: forbidden keys (truth, criteria, evidence paths, ledgers, authorisations, credentials…), forbidden patterns (loopback ports, local paths, tokens), and expected answers outside the agent's own output. Rehearsal documents get no agent-output exemption. A document that fails is never served or written. |
| `stage_a.py` | Public Stage A views: a generation run directory (as the M6 driver writes it) and suites with their review packet and approval/freeze state. Reads only Stage A records. |
| `dataset.py` | Builds and validates sanitized, versioned, immutable datasets (`datasets/lifecycle/<id>/v<N>/`): the projection, per-trial timelines, Stage A views, WebP screenshots, and `DATASET.json` (every file's SHA-256, the source identities incl. every source trial record and screenshot PNG hash, the builder's code hashes). `validate --store --run` re-derives every document from the source and requires byte equality. |
| `sites.py` | Server-side website contexts (variants with hashes, business context, personas). Clients select by id only. |
| `service.py` | Unifies datasets, the store and launched jobs behind one API; finds or builds the manifest server-side; refuses web approval and paid launch; caches completed projections under `runs/derived/`. |
| `jobs.py` | Launched jobs: one worker subprocess per job with the hosted executor's process model (new session, parent-death signal, hard timeout, group kill); the worker runs the unchanged Stage B runner in rehearsal mode with non-loopback sockets refused and an extended jail (§4). `admit_paid` implements the paid coordination (tested, not reachable from the web). |
| `api.py` | The `/api/lifecycle/*` routes (§3), mounted by `hosted.api.create_app(…, lifecycle=…)`. |

Changes to existing modules (all additive; the hosted Ironbark path is otherwise untouched):

- `hosted/admission.py`: `reserve_amount(job_id, client, microusd)`: lifecycle jobs (`lc-<32 hex>`) reserve against the **same** durable ceiling and the **same single evaluation slot** as hosted repetitions (rehearsal = US$0, still exclusive; never reduced).
- `hosted/api.py`: registers the lifecycle routes; the worker banner reports a lifecycle job as busy without exposing it as an Ironbark job; restart recovery also kills lifecycle workers.
- `hosted/serve.py`: `build_lifecycle` (env `AR_LIFECYCLE_DATASETS`, `AR_LIFECYCLE_STORE`, `AR_LIFECYCLE_RUNS`); any lifecycle problem only disables the lifecycle, never the site.
- `diagnostics/`: `hypotheses-2`, `behavioral-2`, a `basis` field on every finding, and a v2 source for M2b kinds (§6).
- `grading/contrast.py`, `grading/evidence_ranked.py`: new, prospective (§6). `grading/v2.py`, `grading/key.py`, `grading/rescore.py` and grader v1 are **unchanged** (their SHA-256 pins still pass).
- `deploy/Dockerfile`: copies `datasets/` into the image and sets `AR_LIFECYCLE_DATASETS`.
- Frontend: `dashboard/src/site/lifecycle/{Lifecycle,Report,Trace,parts}.tsx`, `lifecycle.css`, `lib/lifecycleApi.ts`, routes `#/lifecycle[/<step>|/suites/<sha>|/jobs/<id>]` and `#/reports/<id>[/tasks/<n>]`, a "Lifecycle" nav item, homepage links.

Boundaries kept: Stage A views never read Stage B outcomes; frozen suites, run results and the M7 evidence are read, never written (a launched rehearsal adds new `RunResult` records to the store, write-once); private oracle data never leaves the server except as counts; natural and assisted conditions stay separate (one run per condition, analysed per condition); official v1 grades are reported as recorded.

## 3. API routes and security boundaries

| Route | Access | Notes |
|---|---|---|
| `GET /api/lifecycle/overview` | public | step availability and reasons (onboarding, approval, paid, rehearsal) |
| `GET /api/lifecycle/sites`, `/sites/{id}` | public | registered contexts only |
| `GET /api/lifecycle/generations`, `/generations/{id}` | public | Stage A runs (from datasets) |
| `GET /api/lifecycle/suites`, `/suites/{sha}` | public | store suites are audited against their own private outcomes before serving |
| `POST /api/lifecycle/suites/{sha}/decision` | — | **always 403** `owner_authentication_not_configured`, with or without the operator token |
| `GET /api/lifecycle/frozen` | public | frozen suite refs a launch may name (server store only) |
| `GET /api/lifecycle/evaluations`, `/evaluations/{id}` | public | datasets and launched jobs; a launched evaluation is projected, audited, then cached |
| `GET …/evaluations/{id}/trials/{trial}`, `…/screenshots/{name}` | public | ids and names are pattern-checked; screenshots resolved inside the dataset / trial directory only |
| `POST /api/lifecycle/evaluations` | operator token | body `{"frozen_suite": "<name>@v<N>", "variants": [a, b], "mode": "rehearsal"\|"paid"}`, `extra="forbid"`: any task, URL, model, limit or cap field is a 422. `paid` → **403** `paid_launch_not_authorized` before anything is reserved. Non-operator → 403. Unknown suite → 404; unregistered variants → 422; busy slot → 429 |
| `GET /api/lifecycle/jobs/{id}` | public | progress; live steps redacted for rehearsals |

The hosted Ironbark routes and their contract (`{"repetitions": 1|3|5}` only) are unchanged.

## 4. Execution, isolation and spending

- **Rehearsal launch (enabled, operator-only):** the API reserves **US$0** in the hosted admission (occupying the single slot, so a hosted Ironbark repetition and a lifecycle job never run Chromium at once) → worker subprocess → `runner.prepare/execute/report` in rehearsal mode → `audit_public` → job `completed` only if the leak audit is clean and nothing stopped early.
- **Jail:** the manifest declares the evalruns jail policy (hidden: `~/Projects`, `~/.ssh`, `~/.claude`, `/root`), which on the VM would not hide `/app`, `/data` or `/run/secrets`. The lifecycle worker therefore **adds** the deployment policy's hidden paths (`AGENT_READINESS_BROWSER_JAIL`) and the lifecycle store and runs roots; the extra paths are recorded on the job. Hiding more never weakens the declared boundary; `jail.require()` and the self-test still run before any trial.
- **Paid coordination (implemented and tested; not reachable from the web):** `jobs.admit_paid` verifies the owner's write-once `PaidAuthorization` with the unchanged `evalruns.authorization.verify` (exact frozen suite with a real owner approval, exact manifest, trial count, cap equal to the manifest hard cap, worst case within it, pinned agent), refuses an experiment ledger that has entries, then reserves the manifest's worst case (rounded up to whole microdollars) against the hosted ceiling. The runner's own reserve-before-send gate, per-trial and scope caps, and ledger-counted trials (no retries) then apply unchanged. `PAID_WEB_LAUNCH = False`.
- **Paid vs rehearsal in new records:** every projection carries `mode` (`paid` | `rehearsal`), `execution_provider` and, for rehearsals, a notice; rehearsal answers and stand-in memory are withheld because they are derived from the private outcomes.

## 5. Reporting: six dimensions (no composite score)

Each dimension is a set of measured quantities with its basis printed beside it:

1. **Task success:** per variant, official v1 passed / evidence-backed, post-hoc v2 passed / evidence-backed, prospective v2.1 review passes; exploratory sign-flip analysis under both graders, labelled.
2. **Navigation efficiency:** requests (mean, total), steps, page views, time, revisits, item pages opened, calculated cost; paired bars per task.
3. **Evidence quality:** trials whose answer pages were shown, correct-but-unsupported, required pages not shown (counts), prospective rule `evidence-ranked-subset-2`.
4. **Information accessibility:** from each variant's frozen snapshot: on how many listing cards and item pages each fact is stated; per task, where its facts are placed and the minimum link steps.
5. **Agent reliability:** dead ends (HTTP errors, failed actions), recovery, partial and empty answers, trials at the request limit, limit stops, voids, protocol-parser recoveries.
6. **Coverage:** the frozen suite's own coverage record (personas, journeys, capabilities, targets met/unmet) and its gaps, exactly as frozen.

The M7 report states, in the header: **exploratory; 6 tasks × 1 repetition per variant; no statistical power for a general improvement claim; none is made.**

M7 as shown (from the dataset; identical to the M7 report): official v1 2/6 → 1/6, post-hoc v2 3/6 → 4/6; 65 → 46 requests; 424 s → 199 s; spend US$1.520696 settled (111 requests, 0 unsettled; the per-trial records sum to US$1.52069 because each record rounds). Task 1: Original named 1 of 5 courses in 12 requests and 67 s (US$0.170); Modified named all 5 in 3 requests and 16 s (US$0.039); v1 fails both, v2 accepts Modified. Task 6 is the second comparison (12 → 3 requests, 78 s → 16 s; both correct under v2, both v1 format failures).

## 6. Grading and diagnostics findings (versioned; nothing retroactive)

| Item | Finding | Change |
|---|---|---|
| Diagnostics, `either_of` | `hypotheses._criterion_labels` ignored `either_of` and `ranked_subset`, so M7 reported "Risk only: no evaluated task compares items by 'class day'" although task 3 does | `hypotheses-2`: both kinds count their labels. On M7: 5 hypotheses + 1 unverified (was 4 + 2); the class-day finding is now a hypothesis linked to task 3 |
| Diagnostics, v2 missing | `diagnose()` takes v2 from `rescore_run`, which crashes on M2b kinds, so v2 was silently empty and every v1 format failure read as "incorrect answer" | fallback to the lifecycle runner's row grader (same `_trial_rows`, `build_key_any` keys, only when faithful) |
| Diagnostics, labels | v1 format rejections were reported as incorrect answers (severity high) | `behavioral-2`: new rule `v1-format-rejection` (low) when v2 accepts; M7: 4 format rejections, 5 incorrect answers (was 9 "incorrect") |
| Observed vs hypothesis | — | every finding carries `basis`: `observed` (page fact or recorded behaviour) or `hypothesis` (unverified, hypothesis, supported_exploratory); the UI shows them in separate columns, hypotheses hatched |
| v2 and runner-ups | v2 fails "Spanish conversation 2 … (vs Furniture restoration with 1 seat …)" as `multiple_candidates` (task 5, Modified) | prospective **grader v2.1-contrast** (`grading/contrast.py`): passes only if the expected candidate is named first, every other candidate follows an explicit contrast marker within 3 tokens, and each segment passes v2's unchanged residual checks against that candidate's own facts. M7: accepts exactly that one answer; tests refuse hedges, wrong order, contradictions and unmarked lists. Shown as "review rule (prospective)", never applied |
| `ranked_subset` evidence | the rule required only the winner's page (task 5 Original answered without opening the other candidate) | prospective **`evidence-ranked-subset-2`**: listing + every filtered candidate whose decisive facts are not on its card. M7: Original task 5 shows 2 of 3 required pages (comparison not evidenced); Modified 3 of 3. Recorded evidence rule and grades unchanged |

Stored M7 reports, run results, ledgers and evidence are unchanged; the derived views carry their rule versions (`hypotheses-2`, `behavioral-2`, `2.1-contrast`, `evidence-ranked-subset-2`, `projection-1`).

## 7. The M7 demo dataset

`datasets/lifecycle/m7-larkspur-browser-1/v1/` (127 files, 4.4 MB): `evaluation.json`, 12 trial timelines, 111 WebP screenshots (the recorded frames re-encoded to ≤ 1024 px, quality 72; no pixel edited), the frozen suite v2 and the v1 proposal review views, and the M6 generation view. Source: `evalrun-paid-64a55c5f3a-natural`, manifest `64a55c5f…`, frozen suite `0816af7f…`, both RunResults with their evidence-directory hashes, every source trial record and PNG hash.

Validation: `python -m agent_readiness.lifecycle.dataset validate datasets/lifecycle/m7-larkspur-browser-1/v1 --store scanner-data/research/stage-a/store --run scanner-data/research/stage-b/paid/evalrun-paid-64a55c5f3a-natural --generation scanner-data/research/stage-a/m6-larkspur-core-20261102T121242Z` → `valid: true, rederived_from_source: true` (byte-equal). Without the local sources (CI, the VM) the structural, hash and pattern checks run at startup; a tampered dataset is not served (tested).

Withheld: expected answers and every oracle record, criteria truths, evidence texts and required page paths (counts only), authorisation records, raw ledgers (settled totals only), credentials, model inputs and raw responses, local paths and loopback ports. Shown: the agent's own answers, memory and actions in the paid run (run evidence, as the hosted product already shows) and the site's own pages. The Stage A view withholds the wording of any proposal rejected for revealing its answer (none in M6). The dataset was finalised at the M8 commits listed in §8; later projection changes require a new version (`v2`), never an edit.

## 8. Tests and checks (zero cost)

| Check | Result |
|---|---|
| `tests/test_lifecycle_m8.py` (new, 31) | passed |
| `tests/test_lifecycle_m8_browser.py` (new, real jailed Chromium + worker subprocess through the API; run alone) | 1 passed (87 s) |
| lifecycle M1–M7 suites + M8 + graders + hosted + diagnostics + framework + deployment safety (not browser) | see the final run below |
| `scripts/critical-tests.sh` | see the final run below |
| `dashboard`: `npx vitest run` | 195 passed (189 existing + 6 new, which render the committed M7 dataset) |
| `npm run build` (tsc, Vite, `check:dist`) | passed |
| Rendered review (real FastAPI app, disabled mode, dataset only, production headers): lifecycle steps, report, traces for tasks 1, 5, 6, homepage at 1440×900 and 390×844 | no console errors; no horizontal overflow (one found and fixed: an `sr-only` header escaping a scroll container) |
| Docker image build and disabled-mode smoke test | see §8.1 |

The final regression figures and the image smoke test are appended in §8.1 when run.

## 9. Owner decisions needed

### 9.1 Owner authentication for web approval and paid authorisation (workstream stopped for input)

Web approval and paid launch stay disabled until one of these is chosen and implemented. The terminal flow keeps working.

| Option | What it is | Strength / cost |
|---|---|---|
| **A. SSH-verified owner terminal (recommended for the hackathon)** | The web shows the exact hash and the command; the owner approves via `ssh` → `docker compose exec -it app python -m agent_readiness.suites.stage_a.approval decide /data/hosted/lifecycle/store <sha> approved`. Identity = the SSH key; the existing TTY guard and attestation apply unchanged | no new attack surface; zero implementation; not "in the browser" |
| B. Passkey (WebAuthn) owner credential | A passkey is registered from the owner terminal; web approval signs a challenge that contains the suite hash; the signed assertion is stored with an immutable approval record | strongest browser option; ~1 day; a new dependency and CSP review |
| C. Separate owner secret + TOTP | A distinct owner secret (not the operator token) plus a time-based code; HMAC-attested approval records | moderate; secret handling and rotation |
| D. OAuth restricted to the owner's account | e.g. GitHub sign-in allowed for one account | external dependency, sessions/cookies, callback and CSP changes |

### 9.2 Other decisions
1. **Deploy M8?** Recommended first step: deploy view-only (dataset served, no lifecycle store on the VM, so launches stay disabled). Optionally copy the store later to enable operator rehearsals.
2. **Lifecycle spending:** M8 implements one ceiling (lifecycle paid runs would reserve their worst case against the hosted US$10 admission). Confirm, or keep separate experiment caps.
3. **Where the store lives in production:** proposed `/data/hosted/lifecycle/store` (on the backed-up volume).
4. **Merge strategy** research → `evaluation-v2` → `main` (unchanged from the handoff).
5. **Promote** grader v2.1-contrast and `evidence-ranked-subset-2` from prospective to post-hoc views, if wanted (would be new versions).

## 10. Deployment procedure (NOT executed; needs owner approval)

Production today: `evaluation-v2` @ `140a4e8`, image `agent-readiness-app:latest` = `evalv2-140a4e8d0bf8`, rollback images `rollback-b3121a8`, `rollback-60fcbc6`.

```sh
# on the VM, as for the last two deployments
cd /root && git -C agent-readiness fetch origin m8-product-integration
git -C agent-readiness worktree add --detach /root/agent-readiness-build-m8 <M8_COMMIT>
cd /root/agent-readiness-build-m8 && docker build -f deploy/Dockerfile -t agent-readiness-app:m8-<short> .
# backup the data volume first
docker run --rm -v agent-readiness_data:/data -v /root/backups:/out alpine tar czf /out/predeploy-m8-$(date -u +%Y%m%dT%H%M%SZ).tgz -C /data .
# smoke test DISABLED on loopback against a COPY of the data volume (as in DEPLOY.md): /api/health, /api/lifecycle/overview,
# /api/lifecycle/evaluations (lists m7-larkspur-browser-1), /#/lifecycle, /#/reports/m7-larkspur-browser-1, the Ironbark workspace
docker tag agent-readiness-app:latest agent-readiness-app:rollback-140a4e8
docker tag agent-readiness-app:m8-<short> agent-readiness-app:latest
cd /root/agent-readiness/deploy && docker compose up -d --no-build --no-deps app
docker compose logs app | grep 'lifecycle:'   # datasets=m7-larkspur-browser-1 store=no launch=disabled paid=disabled web-approval=disabled
```

No `.env`, secret, ceiling or access change is needed. The lifecycle store is **not** copied in the view-only deployment. To enable operator rehearsals later: copy `scanner-data/research/stage-a/store/` to `/data/hosted/lifecycle/store/` (owned by uid 10001; `private/` 0700 with 0400 files; objects 0444) and restart.

**Rollback:** `docker tag agent-readiness-app:rollback-140a4e8 agent-readiness-app:latest && docker compose up -d --no-build --no-deps app`. The data volume is unaffected in both directions: M8 adds only `/data/hosted/lifecycle/` (absent in the view-only deployment) and admission rows with `lc-` ids (none without the store), which the older image ignores.

## 11. Limitations

- Web approval, paid launch, new paid generation and URL onboarding are disabled (by design in this release).
- Only Larkspur has a paid lifecycle evaluation; launched evaluations in M8 were rehearsals (scripted stand-in), which prove the pipeline only.
- Re-evaluation is limited to registered snapshots (Larkspur and Ironbark: `original`, `modified`). A new website release needs a registered snapshot.
- The business contexts and personas are SYNTHETIC (labelled everywhere).
- The prospective rules are heuristics: the contrast markers are English-only; the ranked-subset rule uses the snapshot's card text.
- The job progress view polls every 4 s; there is no push channel.
- Dataset v1 was rebuilt during M8 development before publication; from the final M8 commit it is immutable.
