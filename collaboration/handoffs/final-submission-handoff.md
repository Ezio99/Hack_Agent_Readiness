# Handoff: final submission (2026-11-04 16:30 AEDT)

**Start here.** This supersedes [final-visual-showcase-handoff.md](final-visual-showcase-handoff.md) for the current state. Verify everything against the repository and production before you rely on it.

- **Deadline:** official "Nov 4, 9:00 PM ET" = **Thu 2026-11-05 13:00 AEDT**. Submit by **12:00 AEDT**: a third-party listing implies an hour earlier.
- **Branch:** `final-showcase` (unmerged into `main`; merging needs owner approval). Production runs **`4dae086`**.
- **Read first:** `AGENTS.md`, this document, [docs/FINAL_SUBMISSION_CHECKLIST.md](../../docs/FINAL_SUBMISSION_CHECKLIST.md) (pass/fail and owner actions), [docs/FINAL_SUBMISSION.md](../../docs/FINAL_SUBMISSION.md), [docs/FINAL_VIDEO_SCRIPT.md](../../docs/FINAL_VIDEO_SCRIPT.md), and the experiment record [collaboration/reports/polished-larkspur-evaluations.md](../reports/polished-larkspur-evaluations.md).
- **The application is frozen.** Change it only for a submission-blocking defect, with the owner's approval.

---

## 1. Production (verified 2026-11-04 05:04–05:30 UTC)

| Item | Value |
|---|---|
| URL | https://209-38-84-72.sslip.io (DigitalOcean `209.38.84.72`, Sydney; Caddy → app container) |
| Deployed | `4dae086` (judge-facing copy cleanup), image `sha256:f493c7ce9146…` (`copyclean-4dae086` = `latest`) |
| Rollback | `rollback-before-copyclean` = `04c130ab3f3a` (`3c2b5ce`). Earlier tags chain back: `rollback-before-paired`, `-herocopy`, `-spec`, `-public`, `-readiness`, … Log: `/root/agent-readiness/deploy/DEPLOYED.txt` |
| Latest backup | `/root/backups/predeploy-copyclean-20261104T050321Z.tgz` + `.sha256` (3 416 files, verified) |
| Selected evaluation | **`ar-a20-pair`**: frozen `larkspur-core@v3`. Each run tests **Before vs After** together: 3 tasks × 2 versions = 6 agents, at most **US$3.740 (A$5.61)** per run |
| A$20 budget `ar-a20-2026-11` | Spent **A$2.491408**, outstanding A$0, available A$17.51; 5 runs, all settled |
| Global cap | US$39.029333; all commitments US$13.03 |
| Legacy hosted ceiling | US$21.956, historical scope only. Its status prints "remaining US$-3.828" because it also lists budget-funded reservations; budget jobs are bounded by their budget, not this ceiling. Display quirk, unchanged |
| A$50 programme | Unchanged since the earlier handoff. Budget spend is separate. Not appended |
| Last checks | Every public route at 1440 and 390 px: 0 errors, 0 writes, 0 overflow, 0 internal terms (`scripts/showcase/public_sweep.py`); evidence identical before and after each deploy |

## 2. The featured experiment (audience names: **Larkspur Community College · Before · After · Agent Readiness**)

| Audience name | Internal snapshot | sha256 | Module |
|---|---|---|---|
| Before | `larkspur@polishedoriginal` | `2ee4a7be2bd0…` | `sites/larkspur/polished_original.py`: Original's pages, links and facts, visually redesigned only |
| After | `larkspur@modifiedpolished` | `2a16c38be474…` | `sites/larkspur/modified_polished.py`: Before + the Before report's 3 recommendations (facts on cards, dead-end redirect, JSON-LD) |

**Genuine live runs** (muse-spark-1.3, `larkspur-core@v3`, 14 requests and 14 steps per agent, US$0.044 per request):

| Run | What | Result | Settled |
|---|---|---|---|
| `eval-ea13944e8ba5c08e8893426b2f8b1c8f` | Before alone | 0/3 correct, 36 requests, 311 s | US$0.521494 |
| `eval-5cf934b372942da74f5157c5fca39fd6` | After alone | 3/3 correct, 15 requests, 121 s | US$0.204389 |
| `eval-1cf64d5eae90bcaeab531b4886140c14` | **Paired Before vs After** (owner-launched from the Workspace) | Before 0/3, 39 requests, 326 s → After 3/3 (1/3 exact), 10 requests, 57 s | US$0.704994 |

- **Showcase and Home** show the two separate 4 Nov runs (static export in `dashboard/src/site/showcase/larkspur.json`, keys `before`/`after`).
- **Workspace and Live report** (`#/reports/latest`) open the latest completed live **paired** run, so currently `eval-1cf64d5e`.
- **Superseded, kept as records, never public:**
  - `polished`/`polished2` (built on Improved by mistake; runs `eval-abc5fc83`, `eval-11ee8a1e`);
  - Original vs Improved (`eval-c04fdb10`);
  - Original vs Modified (`eval-e529db2a`);
  - Ironbark.

  Their URLs show a "not part of this experiment" notice (reports have an audit-only reveal). Lineage findings: report header of `polished-larkspur-evaluations.md`.

## 3. Public product (frontend `dashboard/src/site/`)

| Route | What | Code |
|---|---|---|
| `#/` | Home: purpose, Before/After result card, hero band | `Home.tsx`, `LatestLive.tsx` |
| `#/showcase` | Cinematic Before → After story (scroll engine `demo/engine.tsx`) | `story/Story.tsx`, `story.css` |
| `#/lifecycle` (= `#/demo`) | Journey, 8 steps on the Before/After evidence; chapter bar follows scroll | `lifecycle/Lifecycle.tsx` |
| `#/run`, `#/run/<id>` | Workspace: code → Run (6 agents) → live grid and agent viewer → report | `workspace/HostedEvaluation.tsx`, `History.tsx`, `LiveAgent.tsx` |
| `#/reports/latest`, `#/reports/<id>[/tasks/n]` | Live report (latest paired run, or the two separate runs labelled as such); reports; trace replay | `lifecycle/Report.tsx`, `Trace.tsx` |

**Public-scope rules:**
- `lib/lifecycleApi.ts` defines `PUBLIC_SCOPE`, `inPublicScope`, `latestPaired`, `VARIANT_LABEL`, `audienceText` and `displayTitle`.
- Only the Before and After versions are listed, selected or rendered. Internal names never reach the audience.
- Unscoped component tests set `PUBLIC_SCOPE.versions = null`.
- **Regression tests:** `site/public-scope.test.tsx`, `story/story.test.tsx`, `lifecycle/lifecycle.test.tsx`, `site.test.tsx`.
- **Old routes:** `#/studio`, `#/demo/<scene>` and the archive pages open Home.

## 4. Backend changes in this phase (all tested, backward-compatible)

- **Single-version budget evaluations:**
  - `lifecycle/arming.plan(_pool=True)` accepts one or two versions; judge armings stay paired.
  - `hosted/budget evaluation-add --variants` takes 1..2 versions.
  - Job status may have one arm; per-version diagnostics.
- **Delegated, audited record and select** (no forged owner attestation): `hosted/budget evaluation-add|evaluation-use --delegated "<authorization>"`.
  - Run `--dry-run` first; it prints the terms and their sha256. Then record with `--expect-sha256`.
  - The record says the agent recorded it; every action is appended to `budget-pools/DELEGATIONS.jsonl`.
  - Opening budgets, allocations and settlements stay owner-typed.
- **Display names:** `hosted/stageb.DISPLAY` maps snapshot names to audience names.
- **Snapshots:** new immutable Larkspur variants registered in `sites/larkspur/render.py` and `framework/site.py` (`releases`). Every earlier hash is pinned in `tests/test_larkspur_before_after.py` and `tests/test_larkspur_polished.py`.

## 5. Operations

**SSH**
- Command: `SSH_AUTH_SOCK=~/.ssh/readiness-agent.sock ssh root@209.38.84.72`.
- After a WSL crash the socket is stale ("Connection refused"). The owner runs `rm -f ~/.ssh/readiness-agent.sock && ssh-agent -a ~/.ssh/readiness-agent.sock && SSH_AUTH_SOCK=~/.ssh/readiness-agent.sock ssh-add ~/.ssh/readiness_key_new`.
- The key also expires; the owner runs the `ssh-add` again.

**Deploy (image only, A0–A5)**
- Push to `origin/final-showcase`, then `ssh … "C=<commit> TAG=<name> bash -s" < deploy/scripts/image-deploy.sh`.
- It backs up, verifies, clean-builds, checks snapshot hashes, refuses unless idle, switches, then checks health, tracebacks, 403 without a code and that evidence is identical. It appends to `DEPLOYED.txt`.
- Then run `uv run python scripts/showcase/public_sweep.py https://209-38-84-72.sslip.io/` (expect `FAILS []`).

**Roll back**
- `docker tag agent-readiness-app:rollback-before-<tag> agent-readiness-app:latest && docker compose up -d --no-build --no-deps app` (in `/root/agent-readiness/deploy`).

**Select another evaluation**
- `ssh … "ID=<new-id> VARIANTS='<v1> [<v2>]' AUTH='<cite owner instruction>' bash -s" < deploy/scripts/register-evaluation.sh`.
- Ids are write-once; the per-run maximum must be ≤ US$3.740.

**Judge access code**
- On the VM: `deploy/secrets/judge_token`. Never print, log or commit it.
- The owner reads it in their own terminal. Copy-ready text for judges: [docs/JUDGE_ACCESS_MESSAGE.md](../../docs/JUDGE_ACCESS_MESSAGE.md).

**Tests**
- `cd dashboard && npx tsc --noEmit -p . && npx vitest run && npm run build` (235 pass; build ends `CHECK PASSED`).
- `scripts/critical-tests.sh`.
- Browser end-to-end, run alone after a build: `uv run pytest -q tests/test_judge_experience_browser.py -m "browser or slow or not browser"`, about 12 min. It is a zero-cost paired rehearsal.

**No paid call** without owner approval. A paired run reserves A$5.61; recent runs settle at about US$0.70.

## 6. Known issues and open points

- **Main page caching:** the server sends `index.html` without `Cache-Control`. After a deploy a browser may show the previous version until a hard refresh. Not changed; fixing it is a Caddy config change and needs approval.
- **Report wording:** recommendations still name "schema.org JSON-LD"; that is the actual fix.
- **Old evaluations** are reachable only by exact URL, behind a notice. The `/api/ironbark/jobs` API still lists every job for audit; the UI filters them.
- **Pending owner actions** (checklist §6):
  - read the Official Rules and the submission form fields (not public);
  - choose track and theme;
  - record the video ([storyboard](../../docs/FINAL_VIDEO_SCRIPT.md));
  - give judges the access code privately;
  - decide whether to link the branch or merge it to `main`;
  - submit and keep the confirmation.
- **Optional:** feature the paired run in the Showcase and Home instead of the two separate runs. It needs a showcase export (`scripts/showcase/export_larkspur_showcase.py`, add a `paired` run) and copy updates.

## 7. Never modify

Historical snapshots and their hashes; frozen suites; job records, ledgers, launch claims, authorisations, `armings/`, `budget-pools/*.json` (and `DELEGATIONS.jsonl` except by appending); `admission.sqlite` settlements and budgets; the write-once lifecycle store; `collaboration/budget/programme-ledger.json`; recorded showcase exports of earlier runs; the owner's untracked `src/agent_readiness/investigate/prototype/` and `tests/test_termvalue_prototype.py`.
