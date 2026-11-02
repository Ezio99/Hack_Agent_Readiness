# Deploying the hosted Ironbark evaluation

**Currently deployed (2026-11-02 ~23:00 UTC = 2026-11-03 Sydney, owner-approved): `m9-release-readiness` @ `b563a33`** at https://209-38-84-72.sslip.io.

Image `agent-readiness-app:latest` = `m9-b563a33` (`cc97e0049042`). The engine is the lifecycle Stage B runner. Mode live, access **operator-only**,
**US$10.736 ceiling** (owner-approved migration 2026-11-02 23:26:49 UTC, audit row #1; US$3.30 reserved, US$7.436 remaining; `.env` `AR_HOSTED_CEILING_USD=10.736`), **paid arming `larkspur-live-1` ACTIVE** (2026-11-02 23:36:11 UTC; 1 launch, US$7.436; not launched; cancel with `arming disarm`). Lifecycle store at `/data/hosted/lifecycle/store`.
Verified: pre-flights A/B, a candidate smoke test on a volume copy, production health/history/lifecycle/browser checks, all 1 398 authoritative
files byte-identical, and a zero-cost VM rehearsal (12/12, US$0; rehearsal arming used up and disarmed). Pre-deploy backup
`/root/backups/predeploy-m9-20261102T224342Z.tgz` (+ `.sha256`, `env-predeploy-m9-…`).
**Rollback:** `docker tag agent-readiness-app:rollback-140a4e8 agent-readiness-app:latest && docker compose up -d --no-build --no-deps app`, with
`AR_HOSTED_CEILING_USD=10` (older: `rollback-b3121a8`, `rollback-60fcbc6`). Record:
[collaboration/reports/m9-release-readiness.md §9](../collaboration/reports/m9-release-readiness.md).

**Previously deployed (2026-11-02 07:12 UTC): `evaluation-v2` @ `140a4e8`.** Image `evalv2-140a4e8d0bf8` (`sha256:de3edfef…`), now tagged `rollback-140a4e8`.

Changes from `b3121a8`:
- a grader_v2 post-hoc view beside the official grader_v1 results;
- the export reports the enforced ledger ceiling with its basis;
- the operator-token field is visible and held in memory only;
- derived caches live under `/data/hosted/live/derived/` (versioned, disposable, rebuilt from runs).

Executor, admission, jail, budgets and access are unchanged.

Verified:
- candidate smoke test, disabled, on loopback with a data copy: 23/23 browser checks;
- after deploy: jail self-test ok; admission policy and jobs unchanged; all 1399 authoritative data files and 308 source-run files byte-identical (the only new files are the four derived caches; the pre-fix `<run>.public.json` caches are untouched and no longer read);
- 403/403/422/422/405 refusals, no job created;
- HTTPS 308 redirect, TLS 1.3, HSTS/CSP/nosniff/no-referrer;
- served frontend hashes equal the reviewed build;
- uid 10001 with CapEff 0; no secrets in logs;
- 29/29 production browser checks (homepage, demo, workspace v1/v2 on desktop and mobile, token UX, reload recovery, exports at US$2.50, no console errors, no failed or non-GET requests).

Pre-deploy backup: `/root/backups/predeploy-evalv2-20261102T070923Z` on the VM. Build worktree: `/root/agent-readiness-build-evalv2`.

**Rollback** to the previous production image `agent-readiness-app:rollback-b3121a8` (= `8e0e2378`). Volumes, `.env` and secrets are not touched by either direction. The older `rollback-60fcbc6` is also kept. The `derived/` caches are ignored by the older image.

```sh
cd /root/agent-readiness && git checkout -q --detach b3121a8 \
  && docker tag agent-readiness-app:rollback-b3121a8 agent-readiness-app:latest \
  && cd deploy && docker compose up -d --no-build --no-deps app
```

**App-image updates** (how the last two deployments were done): build a tagged candidate from a separate worktree (`git worktree add --detach /root/agent-readiness-build <sha>`; `docker build -f deploy/Dockerfile -t agent-readiness-app:redesign-<sha> .`), smoke-test it disabled on loopback against a copy of the data volume, tag it `latest`, then `docker compose up -d --no-build --no-deps app`. Caddy and the volumes are not recreated.

**First deployed (operator-only) on 2026-11-02 at https://209-38-84-72.sslip.io (DigitalOcean, Ubuntu 24.04, 2 vCPU/4 GB + 2 GB swap); steps A–C passed on the VM.** One Linux VM runs everything: Caddy (automatic HTTPS) in front of a single app container (API, job worker, jailed Chromium). Status: the image builds and, in Docker Desktop (WSL2), passed the in-container isolation self-test, a rehearsal and restart recovery, and completed the first genuine Muse Spark evaluation. **The cloud VM must repeat step 4 because its kernel and AppArmor settings differ.** Public deployment, public paid execution and any ceiling change need explicit owner approval.

## M8 release candidate (branch `m8-product-integration`; NOT deployed)

The hosted evaluation's engine becomes the lifecycle Stage B runner; the launch API, operator token, admission (US$10 ceiling), slot, jail and
recovery are unchanged. Evaluations need the lifecycle store at `/data/hosted/lifecycle/store` (else `lifecycle_store_missing`; the site stays up)
and an owner arming (`docker compose exec -it app python -m agent_readiness.lifecycle.arming arm …`; else `not_armed`). No `.env`, secret, ceiling or
access change for the deploy itself. A paid `larkspur-core@v2` evaluation (reserves US$7.436) needs the owner's ceiling migration first:
`docker compose stop app && docker compose run --rm --no-deps -it app python -m agent_readiness.hosted.ceiling migrate --db /data/hosted/live/admission.sqlite --to 10.736 --expect-ceiling 10 --expect-reserved 3.3 --reason "…"`,
then `AR_HOSTED_CEILING_USD=10.736` in `.env` and `docker compose up -d --no-build --no-deps app` (a mismatch keeps evaluations disabled: fix `.env`, never the
database). Rolling back the image keeps the migrated ceiling and every reservation; the old image needs `AR_HOSTED_CEILING_USD=10.736` to admit, or
stays fail-closed. **M9: after a ceiling migration, roll back with `AR_HOSTED_CEILING_USD=10` (fail-closed, history viewable).** With 10.736 and no
Stage B launch yet, the retired paired engine would be live again and could reserve 4 × US$1.65 = US$6.60 of the capacity meant for the Stage B
evaluation (verified against the deployed `140a4e8` admission code). Full sequence (backup, deploy, verify, migrate, arm, launch, monitor, rollback):
[collaboration/reports/lifecycle-m8-product-integration.md §8–§11](../collaboration/reports/lifecycle-m8-product-integration.md); M9 verification,
pre-flight checks and the corrected runbook: [collaboration/reports/m9-release-readiness.md](../collaboration/reports/m9-release-readiness.md).

## VM requirements

| | Minimum | Recommended |
|---|---|---|
| OS | Ubuntu 22.04 LTS, amd64 | **Ubuntu 24.04 LTS, amd64 (x86_64)**; arm64 is untested |
| CPU / RAM | 2 vCPU / 4 GB | 2 vCPU / 8 GB (headroom for Chromium + build) |
| Disk | 30 GB SSD | 50 GB SSD (image 2.2 GB, build cache ~3 GB, about 60 MB per live repetition) |
| Kernel | ≥ 5.15 with user namespaces (`CONFIG_USER_NS`, `user.max_user_namespaces` > 0), the stock Ubuntu kernel | same |
| AppArmor | Ubuntu 24.04: `kernel.apparmor_restrict_unprivileged_userns=0`. 22.04 needs no change. The bootstrap script sets it. | same |
| Docker | Docker Engine ≥ 24 + Compose v2 (`get.docker.com`) | same |
| Inbound | TCP 22 (SSH), 80 (certificate challenge, redirect), 443 | same; restrict 22 to your IP |
| Outbound | 443 to `api.meta.ai` (live runs), plus registries during build (Docker Hub, PyPI, npm, Playwright CDN), Let's Encrypt | same |
| DNS | An A record for your hostname → VM public IPv4. Without a domain, `<ip-with-dashes>.sslip.io` works with Let's Encrypt. | your own subdomain |

Any provider with these specifications works (e.g. a 2 vCPU / 4–8 GB VM from DigitalOcean, Hetzner, Lightsail, EC2 or GCE). No GPU and no managed services are needed. Only one evaluation runs at a time, so the VM size does not change with traffic.

## What you need to do

1. Create the VM (Ubuntu 24.04 amd64, specifications above) and point the DNS name at it. Tell me the hostname.
2. Either give me SSH access, or run the commands below yourself (about 20 minutes, mostly the image build).
3. Approve **public access** after step 4 passes on the VM (the US$10 ceiling and the operator token stay as they are).

## Commands

**A. On this machine: package the private inputs** (they never go into Git; transfer them only with `scp`/`rsync`):

```sh
cd ~/Projects/Hack_Agent_Readiness
tar czf /tmp/live-2d58a80e14.tgz -C scanner-data/live live-2d58a80e14
# Live history and the persisted US$10 admission policy (first live run already reserved).
# Stop the local container first; it must stay stopped, so the two hosts never spend against two copies of the ceiling.
docker stop agent-readiness-app-1
docker run --rm -v agent-readiness_data:/data -v /tmp:/out alpine tar czf /out/hosted-live.tgz -C /data hosted/live
scp /tmp/live-2d58a80e14.tgz /tmp/hosted-live.tgz deploy/secrets/operator_token <user>@<host>:/tmp/
```

**B. On the VM:**

```sh
git clone https://github.com/<owner>/Hack_Agent_Readiness.git ~/agent-readiness && cd ~/agent-readiness
git checkout hosted-ironbark-evaluation
bash deploy/bootstrap-host.sh && exit                 # installs Docker, sets the userns sysctl, firewall; log in again

cd ~/agent-readiness
sudo tar xzf /tmp/live-2d58a80e14.tgz -C /srv/agent-readiness && sudo chown -R 10001:10001 /srv/agent-readiness/live-2d58a80e14
docker volume create agent-readiness_data
docker run --rm -v agent-readiness_data:/data -v /tmp:/in alpine sh -c 'tar xzf /in/hosted-live.tgz -C /data && chown -R 10001:10001 /data'
mkdir -p deploy/secrets
sudo install -o 10001 -g 10001 -m 400 /tmp/operator_token deploy/secrets/operator_token
read -rsp 'Meta model API key: ' K && printf %s "$K" | sudo tee deploy/secrets/meta_model_api_key >/dev/null && unset K && echo
sudo chown 10001:10001 deploy/secrets/meta_model_api_key && sudo chmod 400 deploy/secrets/meta_model_api_key
cat > deploy/.env <<'ENV'
SITE_ADDRESS=readiness.example.com
AR_SOURCE_RUN=/srv/agent-readiness/live-2d58a80e14
AR_HOSTED_MODE=live
AR_HOSTED_ACCESS=operator
AR_HOSTED_CEILING_USD=10
ENV
cd deploy && docker compose up -d --build
```

`AR_HOSTED_CEILING_USD=10` must match the persisted policy in the migrated volume; any other value disables evaluations (`budget_policy_mismatch`) rather than changing the ceiling.

**C. Verify on the VM (required before public access):**

```sh
docker compose logs app | grep 'hosted service'        # mode=live access=operator evaluations=enabled jail=verified
docker compose exec app python -c "from agent_readiness.hosted import jail; print(jail.selftest())"
#   {'ok': True, 'mirror_reachable': True, 'escapes_blocked': True, 'filesystem_hidden': True}
curl -s https://$SITE/api/health                       # "evaluations":"enabled","access":"operator"
curl -s -o /dev/null -w '%{http_code}\n' -XPOST https://$SITE/api/ironbark/jobs -H 'content-type: application/json' -d '{}'           # 403
curl -s -o /dev/null -w '%{http_code}\n' -XPOST https://$SITE/api/ironbark/jobs -H 'content-type: application/json' -d '{"url":"x"}'  # 422
```

Open `https://$SITE/#/run`. History shows the first Muse Spark evaluation, and the worker banner reads "Worker available". Optional private live check (US$1.65 reserved, about 9 minutes): `docker compose exec app python -m agent_readiness.hosted.admin start --repetitions 1 --watch`.

**D. Open to judges (only after owner approval):**

```sh
sed -i 's/^AR_HOSTED_ACCESS=.*/AR_HOSTED_ACCESS=public/' .env && docker compose up -d
```

Public starts are limited to one evaluation at a time (others see "Worker busy" and can watch it or browse completed results), one start per client every 120 s, and the US$10 ceiling: 5 more repetitions at US$1.65 each, never released. To stop new runs at once: set `AR_HOSTED_ACCESS=operator` (or `AR_HOSTED_MODE=disabled`), then `docker compose up -d`. History stays visible.

## Troubleshooting

`docker compose logs app | grep 'evaluations disabled'` gives a reason code:

| Code | Fix |
|---|---|
| `isolation_check_failed`, `isolation_policy_invalid` | Namespaces blocked: run `unshare -Urn true` on the host; re-run the bootstrap; check the `security_opt` lines in compose.yaml. |
| `source_run_missing`, `source_run_unreadable` | Path in `.env` or ownership: `sudo chown -R 10001:10001 /srv/agent-readiness/live-2d58a80e14`. |
| `missing_provider_key`, `missing_operator_token` | Secret file empty, or not owned/readable by 10001. |
| `budget_policy_mismatch`, `ceiling_*` | `.env` ceiling differs from the persisted policy. Set it to the persisted value (`python -m agent_readiness.hosted.ceiling status`); change the persisted value only with `ceiling migrate` (owner); never edit the database. |

The site and history stay up in every case. Private operation without Caddy: `docker compose -f compose.yaml -f compose.private.yaml up -d app` and `ssh -L 8080:127.0.0.1:8080 <host>`. Operations: `docker compose exec app python -m agent_readiness.hosted.admin list|watch <id>|health`.
