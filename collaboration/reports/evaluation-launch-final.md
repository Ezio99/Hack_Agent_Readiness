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
| Workspace | One code field and one **Run** button for everyone.<br>"A$x of A$20.00 evaluation budget left · spent A$y · new evaluations start while less than A$20 has been used"; no launch counts.<br>The job bar shows "Reserved up to US$3.74 until settled", then "Actual cost US$… · ar-a20-2026-11".<br>When the budget is used, Run is disabled with "The A$20 evaluation budget has been used. Completed evaluations, their results and traces remain available." |

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

## 5. Deployment and activation (each step needs owner approval; do them in one window)

- **Deploy:** as in [budget-a20-deployment.md](budget-a20-deployment.md) §2: preflight, backup and manifest, clean-worktree build of the release commit, read-only checks, disabled smoke test on a volume copy, tag `rollback-dde7e22`, switch, verify.
  - The launch-state check now shows `launches_left 2` until activation (the judge arming).
  - New files after the first launch: `live/launch-requests.sqlite` (idempotency keys, hashed per caller).
- **Activate** (owner terminal) immediately after verifying the deploy:
  1. Back up `admission.sqlite` and the Stage B tree, as in that document's §3.
  2. Run `docker compose exec -it app python -m agent_readiness.hosted.budget open --db /data/hosted/live/admission.sqlite --id ar-a20-2026-11 --limit-aud 20 --rate 1.50 --frozen larkspur-core@v3 --variants original improved`.
  3. Type the printed line. It states that the shared budget takes every new evaluation, starts runs while actual spending is below A$20, and that the global cap becomes US$39.029333.
  4. Verify:
     - `budget status`: A$20.000000 left, global cap 39.029333;
     - `/api/ironbark/config`: `launch.authorized` true, `launches_left` null, `spending.charged_to` `ar-a20-2026-11`;
     - `larkspur-judge-1` unchanged (2 left, not used);
     - the Workspace shows "A$20.00 of A$20.00 evaluation budget left".
- **Code to give judges:** the existing judge code (`secrets/judge_token`). No change is needed.
- **Rollback:** as in the deployment document §4: rotate the operator token, then tag `rollback-dde7e22` and start.
  - The old image ignores the budget and returns to the judge arming (2 launches, hosted ceiling, the A$50 programme).
  - Budget runs count against its ceiling, so it is more conservative.

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

Not run: the 33-minute CI suite; nothing on production.
