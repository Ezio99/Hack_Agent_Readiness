# Final evaluation launch model: one access code, one flow, a fresh A$20 soft-capped budget (release candidate; NOT deployed)

**Date:** 2026-11-04 (Sydney). **Branch:** `final-showcase`. **Production:** `dde7e22` (image `d40199ef…`), unchanged. **Cost:** US$0. Nothing deployed, no budget opened, no paid call.
Supersedes the operator-session and budget-arming designs in [budget-a20-implementation.md](budget-a20-implementation.md) and the procedures in [budget-a20-deployment.md](budget-a20-deployment.md).

## 1. The rule (owner, 2026-11-04)

A launch is authorised when **exactly two conditions** hold:
1. the access code is valid;
2. the fresh A$20 budget's actual spending is **below A$20**.

The next run's worst case is not compared with what remains, and an admitted run may finish above A$20. Once A$20 is reached, new launches are refused. Historical evaluations (including `eval-c04…`) are excluded. Durable actual-cost accounting and the per-request and per-run limits are unchanged. One evaluation runs at a time, and duplicate clicks start one run.

## 2. What the code does

| Piece | Behaviour |
|---|---|
| Access code | Any valid code: the code in `secrets/judge_token`, or the operator token. Both behave identically.<br>The page holds the code in memory and sends it once per launch as a Bearer header; it is never stored, logged or returned.<br>The operator sessions, cookies, CSRF header and sign-in UI are **removed** |
| The evaluation that runs | Fixed **once** by the owner when the budget is activated: `budget open … --frozen larkspur-core@v3 --variants original improved` records the budget's evaluation (exact manifest, model, per-request and per-run caps), with no launch count.<br>No task generation is on this path |
| Admission (one `BEGIN IMMEDIATE` transaction) | • **Slot:** free (one evaluation at a time).<br>• **Budget:** the pool's commitments are below A$20, counting settled actual costs plus the full reservation of any run not yet reconciled.<br>• **Then:** the run reserves its maximum, is assigned to the budget, and is marked for automatic settlement.<br>• **Global cap:** opening raises it by the limit + one run's maximum: US$21.956 + 13.333333 + 3.740 = **US$39.029333**. It cannot refuse an under-budget launch (proof in §3) and stays as a hard backstop.<br>• **Charging:** while the budget is open, **every** new reservation is charged to it, whatever path made it |
| Removed or bypassed | • the judge arming and its launch counter (not consulted once the budget is open; its record is unchanged);<br>• the per-client 120 s interval for budget launches;<br>• the hosted-ceiling check for new launches (the ceiling now covers historical jobs only);<br>• the worst-case-versus-remaining comparison;<br>• the operator/judge distinction;<br>• sessions.<br>The invalid-code limiter (10 per 10 min) now counts and refuses **invalid** codes only: a valid code always passes |
| Completion | Automatic settlement at the verified actual cost; the unused reservation is released. Failed or interrupted runs keep their full reservation until reconciled |
| Concurrency and duplicates | A second launch while one runs → **409** "An evaluation is already running (eval-…). You can watch it live…": the page then opens that run instead of showing an error. A per-click `Idempotency-Key` makes a double-click or retry return the same run |
| Workspace | One code field and one **Run** button for everyone.<br>"A$x of A$20.00 evaluation budget left · spent A$y", plus the explicit soft-cap line: "A new evaluation starts while less than A$20 is committed. Each run can cost at most A$5.61, so the last one can take the total to at most A$25.61."; no launch counts.<br>The job bar shows "Reserved up to US$3.74 until settled", then "Actual cost US$… · ar-a20-2026-11".<br>When the budget is used, Run is disabled with "The A$20 evaluation budget has been used. Completed evaluations, their results and traces remain available." |

## 3. Backend launch-path audit: every condition between a valid code and a running evaluation

| Step | Condition | Can it block a valid-code, under-budget launch? |
|---|---|---|
| `POST /api/ironbark/jobs` | Service enabled. At start, the service must have: the `.env` ceiling equal to the DB ceiling, the provider key file, the lifecycle store, and a jail self-test pass | **Operational only.** If any fails, evaluations are disabled for everyone and the Workspace says so. Verified on production today |
| | Client identity (the address via Caddy) | Operational (missing proxy header → 403); not seen in practice |
| | Code valid | Condition 1 |
| | `Idempotency-Key` well-formed (if sent) | The page always sends a valid one |
| Budget launch (`_admit_budget`) | A budget is open with its evaluation; that evaluation's mode equals the service mode; it still verifies (suite approval and frozen hash, registered snapshot hashes, manifest, pinned agent) | **Integrity, not authorisation.** These are fixed at opening and do not change. **Before the budget is opened**, launches use the owner's earlier arming exactly as production does today (`larkspur-judge-1`, 2 launches): open the budget in the same window as the deploy |
| | Repetitions = 1 (the evaluation's only option) | The page sends 1 |
| Admission | Slot free | **One at a time (kept).** A second visitor gets 409 and is shown the running evaluation |
| | Pool commitments < A$20 | Condition 2. **A run that fails without a verifiable ledger keeps its A$5.61 reservation until reconciled**, so it counts toward the A$20 (see §6) |
| | Global cap | Cannot bind. While the budget admits, budget commitments are < A$20, i.e. ≤ US$13.333333 (µA$ rounding is upward); + the new run ≤ US$3.740; historical commitments are ≤ the ceiling and no longer grow. Total ≤ US$39.029333 = the cap. The test asserts this at the edge |
| Launch record | Claim (exclusive create; no count); paid authorisation (`AU.verify`: trials ≤ 64, cap ≤ US$50: v3 is 6 trials, US$3.696); unused ledger | Integrity; a conflict needs two simultaneous admissions, which the slot prevents |
| Worker | Re-checks the claim, the budget's evaluation and the reservation; provider key; jail; per-trial and per-request caps | Execution safety (unchanged). A failure ends the run as failed/void; it does not affect the next launch except through §6 |

## 4. Tests (zero cost)

Results are in §7, filled in after the runs. Coverage:
- **Admission:** two conditions; no cooldown; near-limit admission (A$19.99999); finishing above A$20; refusal at A$20 or more; the global cap never refuses.
- **Repeated launches:** 6 API launches beyond the arming's count; 22 settled runs on a production copy.
- **Unreconciled runs:** 4 failed ones count at their reservation.
- **Concurrency:** waves of 5 simultaneous clicks with the run held open admit exactly one; the others get 409. Identical clicks start one run, and a retry returns it.
- **Codes:** invalid codes are limited and a valid one still passes; codes appear in no response or file.
- **Isolation:** historical jobs stay outside the budget; launches before opening are unchanged; the judge arming's files and hashes are unchanged.
- **Rollback:** the real `dde7e22` code on a database with the budget open.
- **Real browser, clean profile:** open the site → see the budget → enter the code → double-click Run (one run) → a second visitor watches the running evaluation → progress → report and trace → launches 2, 3 and 4 with the same code → near-limit launch 5 at A$19.99 spent → after A$20, a clean browser sees Run disabled with the reason, and history remains.

## 5. Final deployment and budget opening (each step needs owner approval; do both in one window)

Build the release commit `C` (this branch's HEAD at approval time). Expected production state before starting:
- image `d40199ef…`, healthy;
- `admission.sqlite` `6868bc95…` (1 settlement);
- ceiling 21.956, reserved 14.476, settled 0.631751, available 10.588249;
- `larkspur-judge-1` 2 left, problems [];
- worker idle;
- 2 421 evidence files.

If anything differs, stop.

```sh
ssh root@209.38.84.72; cd /root/agent-readiness/deploy; SITE=209-38-84-72.sslip.io; C=<release commit>; DB=/data/hosted/live/admission.sqlite
# A0 PRE-FLIGHT (read-only)
docker compose exec -T app python -m agent_readiness.hosted.ceiling status --db $DB
docker compose exec -T app python -m agent_readiness.lifecycle.arming status | head -30
docker run --rm -v agent-readiness_data:/data:ro alpine sha256sum /data/hosted/live/admission.sqlite
# A1 BACKUP (outside the volume; verified)
T=$(date -u +%Y%m%dT%H%M%SZ); echo $T > /root/backups/LAST-FINAL
docker run --rm -v agent-readiness_data:/data:ro -v /root/backups:/out alpine tar czf /out/predeploy-final-$T.tgz -C /data .
docker run --rm -v agent-readiness_data:/data:ro alpine sh -c 'cd /data && find . -type f ! -path "*/derived/*" | sort | xargs sha256sum' > /root/backups/predeploy-final-$T.sha256
cp .env /root/backups/env-predeploy-final-$T && chmod 600 /root/backups/env-predeploy-final-$T && cp compose.yaml /root/backups/compose-predeploy-final-$T
gzip -t /root/backups/predeploy-final-$T.tgz && mkdir /root/backups/v && tar xzf /root/backups/predeploy-final-$T.tgz -C /root/backups/v \
  && (cd /root/backups/v && sha256sum -c --quiet /root/backups/predeploy-final-$T.sha256) && rm -rf /root/backups/v && echo "backup verified"
# A2 BUILD (clean worktree; compose.yaml must be identical: no compose, secret or .env change in this release)
git -C /root/agent-readiness fetch -q origin final-showcase && git -C /root/agent-readiness worktree add --detach /root/agent-readiness-build-final $C
cd /root/agent-readiness-build-final && test "$(git status --porcelain | wc -l)" = 0 && diff -q deploy/compose.yaml /root/agent-readiness/deploy/compose.yaml \
  && docker build -q -f deploy/Dockerfile -t agent-readiness-app:final-$C . && cd /root/agent-readiness/deploy
# A3 READ-ONLY WITH THE NEW IMAGE + disabled smoke on a VOLUME COPY (as in hosted-settlement.md §6.2): config launch_left 2 (judge arming until opening),
#    spending budgets [], programme spent_aud 29.13; POST without a code 403; 0 tracebacks; remove the copy
docker run --rm -v agent-readiness_data:/data:ro agent-readiness-app:final-$C python -m agent_readiness.hosted.budget status --db $DB      # none open
# A4 SWITCH (worker idle)
docker tag agent-readiness-app:latest agent-readiness-app:rollback-dde7e22 && docker tag agent-readiness-app:final-$C agent-readiness-app:latest
docker compose up -d --no-build --no-deps app
docker compose logs app | grep 'hosted service' | tail -5      # budget line unchanged; "shared budget evaluation: none (no_budget)"; armed=larkspur-judge-1 ... left 2
# A5 VERIFY: health; POST without/with a wrong code 403; ceiling and arming status unchanged; evidence vs the manifest: only admission.sqlite changed
#    (five new empty tables); browser (GET only): Home, journey, Workspace, live report, 0 console errors

# B OPEN THE SHARED BUDGET (owner terminal, typed once; right after A5)
docker run --rm -v agent-readiness_data:/data:ro -v /root/backups:/out alpine sh -c \
  "cp /data/hosted/live/admission.sqlite /out/admission-pre-budget-$T.sqlite && tar czf /out/stage-b-pre-budget-$T.tgz -C /data/hosted/lifecycle stage-b"
docker compose exec -it app python -m agent_readiness.hosted.budget open --db $DB --id ar-a20-2026-11 --limit-aud 20 --rate 1.50 \
  --frozen larkspur-core@v3 --variants original improved
#   The printed line names: A$20.000000 at 3/2 (US$13.333333); every evaluation from now on, by anyone, is charged to it; historical ones are not;
#   new evaluations start while spending (plus any unreconciled run) is below A$20 and the last one may finish above it; the global cap becomes
#   US$39.029333 (21.956 + 13.333333 + one run's maximum 3.740); then the evaluation: larkspur-core@v3 original vs improved, 6 trials, at most
#   US$3.740 per run, no launch count. Type it exactly (paste is fine).
# C VERIFY THE OPENING (no restart needed; nothing is launched)
docker compose exec -T app python -m agent_readiness.hosted.budget status --db $DB
#   ar-a20-2026-11: limit A$20.000000; spent 0; outstanding 0; available A$20.000000; global cap US$39.029333; evaluation ar-a20-2026-11 <- selected
docker compose exec -T app python -m agent_readiness.hosted.ceiling status --db $DB | sed -n 5p     # historical scope unchanged: available US$10.588249
curl -s https://$SITE/api/ironbark/config | python3 -c "import json,sys;c=json.load(sys.stdin);print(c['launch'],c['spending']['charged_to'],c['evaluation']['variants'])"
#   authorized True, launches_left None; ar-a20-2026-11; ['original', 'improved']
#   Workspace (browser): "A$20.00 of A$20.00 evaluation budget left" and the soft-cap line "...at most A$5.61 ... at most A$25.61"; Run waits for a code.
```
- **Code for judges:** the existing judge code (`secrets/judge_token`), unchanged.
- **First paid run:** separately approved.
- **Undo opening (only before any launch):**
  1. Stop the app.
  2. Restore `admission-pre-budget-$T.sqlite` and the Stage B tar.
  3. Start the app.
- **Rollback of the image:** rotate the operator token, then tag `rollback-dde7e22` and start, as in [budget-a20-deployment.md](budget-a20-deployment.md) §4. The old image ignores the budget and returns to the judge arming (2 launches).

### 5a. Later: evaluate another approved version (e.g. Polished Larkspur)
1. **Ship the version in a reviewed release.** It becomes a registered, content-hashed, immutable snapshot (`SiteDefinition.releases`, like `improved`), then deploy as above. Nothing else can be selected: an unregistered version, mutable content or an arbitrary URL is refused.
2. **Record the evaluation (owner terminal):**
   ```sh
   python -m agent_readiness.hosted.budget evaluation-add --db $DB --budget ar-a20-2026-11 --id ar-a20-polished --frozen larkspur-core@v3 --variants original polished
   ```
   - The suite must be owner-approved and frozen; a new suite goes through the existing revise → decide → freeze.
   - Its per-run maximum may not exceed the US$3.740 allowance (so the bound stays A$20 + one run).
   - Type the printed line.
3. **Select it:** `budget evaluation-use --budget ar-a20-2026-11 --id ar-a20-polished` (typed). The next launch runs it.
   - Judges see the new pair in the same Workspace: code → Run → progress → report.
   - The same A$20 pool and launch counter continue; earlier runs and records are unchanged.
   - Switching back is the same command.

## 6. Remaining ways a valid-code, under-budget launch can be blocked, and how to remove or explain each

| Condition | Effect | Removal / explanation |
|---|---|---|
| An evaluation is already running | The second launch gets 409, and the page shows the running evaluation with a clear message | Inherent to one-at-a-time; a run takes about 6 minutes |
| A failed or interrupted run without a verifiable ledger | Its A$5.61 reservation counts toward A$20 until reconciled; 3–4 such runs could exhaust the pool early | Reconcile with `settlement apply --allow-open-requests` (owner terminal; commits open requests at their bound, typically far less), or accept. Completed and cleanly failed runs settle automatically |
| The budget is not yet opened | Launches use `larkspur-judge-1` (2 left), then "all live runs used" | Open the budget in the deploy window |
| The service is unavailable (provider key, jail self-test, `.env`/DB ceiling mismatch, lifecycle store) | Everyone sees "Evaluations are currently unavailable" | Operational; checked at deploy. Do not change `.env` without the matching DB migration |
| A provider outage or model errors during a run | The run ends void or failed; its reservation is held per the second row | Operational |
| Too many invalid codes from one address (10 in 10 min) | 429 for further **invalid** codes; a valid code still passes | — |
| A reload clears the code from the page | The judge re-enters it | By design: the code is never stored in the browser |

## 7. Test results (2026-11-04, zero cost)

| Check | Result |
|---|---|
| `tests/test_judge_experience_browser.py` (real browser, real website build and API, run alone) | **1 passed (9 min 42 s):** every step of §4's browser walk-through works. Every page write was the single POST carrying the code; 0 console errors; automatic settlement; the code in no file. Screenshots in the session scratchpad (not committed) |
| `tests/test_showcase_judge_browser.py` (alone) | 1 passed: a judge run under the arming before activation, then the same code after activation runs the budget's evaluation (real jail, worker re-check), with no cooldown; the arming's count not used; `ACTIVE` unchanged |
| `tests/test_unified_launch.py` (8, in critical) and `tests/test_budget.py` (21, in critical) | all pass: the two conditions; no cooldown; A$19.99999 admitted, finishing above A$20, refused at A$20; the global cap never refuses; 6 launches beyond the arming's 4; 22 settled runs on a production copy; 4 unreconciled runs counted in full; overlapping clicks → 1 run + 409; identical clicks → 1 run; invalid codes limited and a valid code still passes; codes in no response or file; historical isolation; arming files and hashes unchanged |
| Older tests updated for the intended behaviour | "already running" is now 409 (not 429): `test_hosted_api`, `test_hosted_service`; the launch state gained a `covers` field: `test_m9_launch_state`; judge-access tests drop the session routes |
| `scripts/critical-tests.sh` | 261 passed |
| `scripts/dev-tests.sh` | 1 741 passed, 2 failed (the known Task-015 ledger-total tests) |
| Dashboard vitest / build | 224 passed / CHECK PASSED |
| Rollback (real `dde7e22` code on a database with the budget open and a budget run) | Starts; counts the budget run against its ceiling (available US$6.85 instead of US$10.59: more conservative); admits 1 judge launch; changes no budget row. Back on the new code, its launch is a historical (non-budget) job |

**Re-run after the soft-cap wording and approved-pair selection (2026-11-04):**
- real-browser judge experience: 1 passed (9 min 04 s);
- `test_budget` adds the version switch on a production copy: an unregistered version (e.g. `polished` before it ships), an unknown suite and an unopened budget are refused; a typed confirmation is required; the next launch runs the selected pair with the same launch counter, the worker re-check accepts it, and earlier records are unchanged;
- critical 262; dev 1 742 passed (+2 known Task-015); dashboard 224 + build.
- The opening confirmation and global cap (US$39.029333 = 21.956 + 13.333333 + 3.740) were checked on a copy of production.

Not run: the 33-minute CI suite; nothing on production.
