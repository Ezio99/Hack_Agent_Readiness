# A$20 operator budget: deployment readiness, deployment and one-time budget opening (NOT executed)

**Date:** 2026-11-04 (Sydney). **Release:** code `f60fcbf` + documentation `418a971` + this readiness commit (tests and documentation only; `git diff f60fcbf HEAD -- src dashboard/src deploy` is empty). Build the readiness commit (`C` below).
**Production now:** `dde7e22` (image `d40199ef…`). Every step below needs separate owner approval. Cost of this check: US$0.

## 1. Readiness checks (all zero cost)

| Area | Evidence |
|---|---|
| **Session security** | `tests/test_operator_session.py` (10, in `critical-tests.sh`):<br>• **Sign-in:** needs the CSRF header; a wrong token, the judge code or a missing header → 403; 10 failures in 10 min → 429.<br>• **Cookie:** `__Host-ar_operator`, HttpOnly, Secure, SameSite=Strict, Path=/, Max-Age 604 800; `no-store`. Only a SHA-256 of the session id is stored; the token never is.<br>• **Expiry:** at 7 days + 1 s the session is refused (403, nothing reserved); expired rows are purged at the next sign-in.<br>• **Sign-out:** revokes server-side; a replayed cookie → 403.<br>• **Secrecy:** the token and cookie appear in no response, file or output |
| **CSRF** | A cookie launch without `X-Agent-Readiness: 1` → 403. With a foreign `Origin` → 403, nothing reserved. Same origin → 202. No CORS is granted |
| **Idempotency** | 4 identical concurrent clicks → one job, one reservation; a later retry returns the same job (`duplicate: true`); a malformed key → 422. The page sends one request on a double-click (vitest) |
| **A$20 under concurrency** | 8 waves of 5 concurrent operator clicks (distinct keys) through the API: at most 1 admitted per wave (single slot); A$ committed ≤ A$20 after every wave; the launch that would exceed it → 429 "remaining budget", reserving nothing.<br>Admission level: 10 concurrent allocations → exactly A$18 of A$20; exact µA$ limit (+1 µUS$ refused).<br>Production copy: 16 consecutive one-click runs settle automatically from their ledgers, then the budget refuses |
| **Judge/operator isolation** | Operator (session or Bearer) → budget pool only; judge code → arming only. With no budget open, an operator launch → 409 and the judge pool is untouched. The judge code cannot sign in. `armings/ACTIVE` is never changed by the budget or its runs.<br>Browser e2e (alone): a judge run, then an operator one-click run on the same service (real jail, worker re-check of the pool claim, automatic settlement), judge pool still 2 left |
| **Production state** (read-only, 2026-11-04) | image `d40199ef…` healthy; `.env` live/operator/21.956; secrets 10001:10001 0400; `compose.yaml` `63f81a9c…` and `Caddyfile` `273b130d…` = repository (no compose change in this release); `admission.sqlite` `6868bc95…` (1 settlement); Stage B tree (11 files) identical to the local copy; `ACTIVE` = `larkspur-judge-1` (`71a26471…`, 2 left, problems []); worker idle; evidence 2 421 files identical to the post-settlement manifest; no `budget-pools/`, no session file; 66 GB free |
| **New code on a fresh copy of that state** | Startup:<br>• adds five empty tables (+ `sqlite_sequence`);<br>• job rows and migrations unchanged;<br>• reconciles nothing;<br>• ceiling's scope available US$10.588249;<br>• no global cap;<br>• `larkspur-judge-1` verifies, 2 left;<br>• operator pool: none (`no_budget`) |
| **Rollback (real `dde7e22` code on a copy with the budget open, its pool, a session and an operator run)** | Starts; ignores the budget tables, pool and sessions; counts the budget job against the ceiling (available US$3.74 instead of US$10.59: more conservative). The session cookie → 403. **The bare operator token → 202 and consumes a judge launch (claims 1 → 2): the legacy permission returns.** Budget rows remain. Mitigation in §4: rotate the operator token at rollback |
| Suites | critical 264; dev 1 742 (+2 known Task-015); dashboard 224 + build; hosted set 94; paid judge path with the network blocked unchanged |

## 2. Deployment (owner approval 1)

```sh
ssh root@209.38.84.72
cd /root/agent-readiness/deploy; SITE=209-38-84-72.sslip.io; C=<readiness commit>
# 0 PRE-FLIGHT (read-only). Expect: image d40199ef…, healthy; ceiling 21.956, reserved 14.476, settled 0.631751, available 10.588249; worker idle;
#   larkspur-judge-1 2 left, problems []; admission.sqlite 6868bc95… (any difference: STOP and report)
docker compose exec -T app python -m agent_readiness.hosted.ceiling status --db /data/hosted/live/admission.sqlite
docker compose exec -T app python -m agent_readiness.lifecycle.arming status | head -30
docker run --rm -v agent-readiness_data:/data:ro alpine sha256sum /data/hosted/live/admission.sqlite
# 1 BACKUP (outside the volume) + manifest + .env + compose
T=$(date -u +%Y%m%dT%H%M%SZ); echo $T > /root/backups/LAST-BUDGET
docker run --rm -v agent-readiness_data:/data:ro -v /root/backups:/out alpine tar czf /out/predeploy-budget-$T.tgz -C /data .
docker run --rm -v agent-readiness_data:/data:ro alpine sh -c 'cd /data && find . -type f ! -path "*/derived/*" | sort | xargs sha256sum' > /root/backups/predeploy-budget-$T.sha256
cp .env /root/backups/env-predeploy-budget-$T && chmod 600 /root/backups/env-predeploy-budget-$T && cp compose.yaml /root/backups/compose-predeploy-budget-$T
sha256sum /root/backups/predeploy-budget-$T.tgz > /root/backups/predeploy-budget-$T.tgz.sha256 && gzip -t /root/backups/predeploy-budget-$T.tgz
mkdir /root/backups/verify && tar xzf /root/backups/predeploy-budget-$T.tgz -C /root/backups/verify && (cd /root/backups/verify && sha256sum -c --quiet /root/backups/predeploy-budget-$T.sha256) && rm -rf /root/backups/verify
# 2 BUILD from a clean worktree
git -C /root/agent-readiness fetch -q origin final-showcase && git -C /root/agent-readiness worktree add --detach /root/agent-readiness-build-budget $C
cd /root/agent-readiness-build-budget && git status --porcelain | wc -l      # 0
diff -q deploy/compose.yaml /root/agent-readiness/deploy/compose.yaml          # identical
docker build -q -f deploy/Dockerfile -t agent-readiness-app:budget-$C . && cd /root/agent-readiness/deploy
docker run --rm agent-readiness-app:budget-$C sh -c 'ls /srv/studio/assets | grep "^index-.*js$"; sha256sum /app/budget/programme-ledger.json'   # bundle = local build; ledger 1f0c42cc…
# 3 READ-ONLY with the new image (volume :ro): ceiling status as in 0; budget status "none open"; programme check ok; settlement audit
#   (Ironbark now shows eligible under fork-prefix-1: information only, owner-only, nothing settles)
for m in "hosted.ceiling status" "hosted.budget status" "hosted.settlement audit"; do
  docker run --rm -v agent-readiness_data:/data:ro agent-readiness-app:budget-$C python -m agent_readiness.$m --db /data/hosted/live/admission.sqlite; done
docker run --rm agent-readiness-app:budget-$C python -m agent_readiness.hosted.programme check --ledger /app/budget/programme-ledger.json
#    smoke (disabled, loopback, VOLUME COPY, as in hosted-settlement.md §6.2): config spending budgets [] / global null / programme spent_aud 29.13,
#    worst_case_aud 45.01; GET /api/operator/session signed_in false; POST /api/ironbark/jobs without auth 403; 0 tracebacks; remove the copy
# 4 SWITCH (worker idle)
docker tag agent-readiness-app:latest agent-readiness-app:rollback-dde7e22 && docker tag agent-readiness-app:budget-$C agent-readiness-app:latest
docker compose up -d --no-build --no-deps app
# 5 VERIFY
docker compose logs app | grep 'hosted service' | tail -5
#   budget: ceiling US$21.956000, settled US$0.631751, outstanding US$10.736000, available US$10.588249
#   operator budget evaluation: none (no_budget)
#   mode=live access=operator evaluations=enabled jail=verified engine=stage-b armed=larkspur-judge-1 (paid, larkspur-core v3, launches left 2) judge_access=on
curl -s https://$SITE/api/ironbark/config | python3 -c "import json,sys;c=json.load(sys.stdin);s=c['spending'];print(c['launch']['launches_left'],s['available'],s['budgets'],s['global'],s['programme']['spent_aud'],s['programme']['worst_case_aud'],c['budget_launch']['reason'],c['operator'])"
#   2 10.588249 [] None 29.13 45.01 no_budget {'signed_in': False, 'sign_in_available': True}
curl -s -o /dev/null -w '%{http_code}\n' -X POST -H 'content-type: application/json' -d '{"repetitions":1}' https://$SITE/api/ironbark/jobs                       # 403
curl -s -o /dev/null -w '%{http_code}\n' -X POST -H 'x-agent-readiness: 1' -H 'authorization: Bearer wrong-wrong-wrong-wrong-wrong' https://$SITE/api/operator/session   # 403
curl -s -o /dev/null -w '%{http_code}\n' -X POST -H 'authorization: Bearer wrong-wrong-wrong-wrong-wrong' https://$SITE/api/operator/session                             # 403 (no CSRF header)
docker run --rm -v agent-readiness_data:/data:ro alpine sh -c 'cd /data && find . -type f ! -path "*/derived/*" | sort | xargs sha256sum' > /tmp/post.sha256
diff /root/backups/predeploy-budget-$(cat /root/backups/LAST-BUDGET).sha256 /tmp/post.sha256     # only admission.sqlite (new empty tables)
#   + browser (GET only): Home, journey, workspace (no operator panel until sign-in; judge flow unchanged), live report; 0 console errors
```
Record in `deploy/DEPLOYED.txt`. No compose, secret, `.env`, ceiling or arming change.

## 3. One-time budget opening (owner approval 2; owner terminal)

```sh
cd /root/agent-readiness/deploy; DB=/data/hosted/live/admission.sqlite
# 0 worker idle; budget status "none open"
docker compose exec -T app python -m agent_readiness.hosted.budget status --db $DB
# 1 BACKUP the two things opening writes: the admission database and the Stage B tree (the pool file goes there)
T=$(date -u +%Y%m%dT%H%M%SZ)
docker run --rm -v agent-readiness_data:/data:ro -v /root/backups:/out alpine sh -c "cp /data/hosted/live/admission.sqlite /out/admission-pre-budget-$T.sqlite && tar czf /out/stage-b-pre-budget-$T.tgz -C /data/hosted/lifecycle stage-b"
docker run --rm -v agent-readiness_data:/data:ro alpine sha256sum /data/hosted/live/admission.sqlite; sha256sum /root/backups/admission-pre-budget-$T.sqlite   # equal
# 2 OPEN (prints one line naming the A$20 limit, 1.50, the global cap US$35.289333 and the pool: larkspur-core@v3, original vs improved, reserve
#   US$3.740 per run, no launch count). Type it exactly (paste is fine). Nothing is launched.
docker compose exec -it app python -m agent_readiness.hosted.budget open --db $DB --id ar-a20-2026-11 --limit-aud 20 --rate 1.50 \
  --frozen larkspur-core@v3 --variants original improved
# 3 VERIFY (no restart needed)
docker compose exec -T app python -m agent_readiness.hosted.budget status --db $DB
#   budget ar-a20-2026-11: limit A$20.000000 (US$13.333333 at 3/2); spent 0; outstanding 0; available A$20.000000; global cap US$35.289333
docker compose exec -T app python -m agent_readiness.hosted.ceiling status --db $DB | sed -n 5p      # available US$10.588249 (unchanged)
docker compose exec -T app python -m agent_readiness.lifecycle.arming status | head -12              # larkspur-judge-1, 2 left, problems []
curl -s https://209-38-84-72.sslip.io/api/ironbark/config | python3 -c "import json,sys;c=json.load(sys.stdin);print(c['budget_launch'],c['budget_evaluation']['options'],c['launch']['launches_left'])"
#   authorized True; reservation 3.74, covered 3; judge launches left 2
# 4 SIGN IN ONCE (browser, Workspace -> "Operator sign-in", paste the operator token): "Signed in as operator", "A$20.00 of A$20.00 left",
#   "Run evaluation" enabled. Do NOT click Run until a paid run is approved.
```
**Undo (only before any operator run):**
1. `docker compose stop app`.
2. Restore `admission-pre-budget-<T>.sqlite`.
3. Remove `stage-b/budget-pools/ar-a20-2026-11.json`.
4. `docker compose up -d --no-build --no-deps app`.

## 4. Rollback of the image (if ever needed)

Rotate the operator token as part of the rollback. The previous image accepts the operator token as a launch credential for the **judge arming**, and nobody needs that after this release (the operator uses sessions):
```sh
cd /root/agent-readiness/deploy; T=$(date -u +%Y%m%dT%H%M%SZ)
cp secrets/operator_token /root/backups/operator_token-pre-rollback-$T && chmod 400 /root/backups/operator_token-pre-rollback-$T
umask 077; head -c 48 /dev/urandom | base64 | tr -dc 'A-Za-z0-9' | head -c 40 > secrets/operator_token.new
chown 10001:10001 secrets/operator_token.new && chmod 400 secrets/operator_token.new && mv secrets/operator_token.new secrets/operator_token   # never printed
docker tag agent-readiness-app:rollback-dde7e22 agent-readiness-app:latest && docker compose up -d --no-build --no-deps app
```
**What the older image does:**
- it ignores the budget tables, pool and sessions;
- it counts budget runs against the ceiling (more conservative);
- the judge path is unchanged.

**Rolling forward later:**
- tag the budget image back and start it;
- restore the saved token file if the operator should sign in with the old token;
- existing sessions remain valid.

## 5. Not done
No deployment, no budget opening, no sign-in on production, no launch, no change to production; the c04 programme-ledger append and the Ironbark settlements remain separate decisions.
