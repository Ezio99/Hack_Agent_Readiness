# Deploying the hosted Ironbark evaluation

One Linux host (Docker Engine + Compose v2). Caddy terminates TLS; one app container holds the API, the job worker and the jailed Chromium. **Status (2026-11-02): the image builds, and steps 3–5 passed in Docker Desktop (WSL2) with the private override: the in-container self-test passed, a rehearsal completed 8/8, a restart marked the run interrupted, and the first private live run was made. The cloud host still needs steps 3–4 repeated, because its kernel and AppArmor settings differ.** Owner authorization is required for the public deployment (step 6), for live mode (step 5) and for the ceiling value.

## 1. Host (once)

```sh
# Ubuntu 22.04/24.04 or Debian 12 · 2+ vCPU · 4+ GB RAM · DNS A record → host · ports 80/443 open
curl -fsSL https://get.docker.com | sh
# The jail needs unprivileged user namespaces (the container runs apparmor=unconfined):
echo 'kernel.apparmor_restrict_unprivileged_userns=0' | sudo tee /etc/sysctl.d/60-userns.conf   # Ubuntu 23.10+
echo 'kernel.unprivileged_userns_clone=1'             | sudo tee -a /etc/sysctl.d/60-userns.conf # Debian
sudo sysctl --system
```

## 2. Code, private data, secrets

```sh
git clone https://github.com/<owner>/Hack_Agent_Readiness.git && cd Hack_Agent_Readiness && git checkout hosted-ironbark-evaluation
# Private source run (26 MB, never in Git), copied from the operator machine:
#   rsync -a scanner-data/live/live-2d58a80e14/ host:/srv/agent-readiness/live-2d58a80e14/
sudo chown -R 10001:10001 /srv/agent-readiness/live-2d58a80e14       # container user; the preflight refuses unreadable files
mkdir -p deploy/secrets
openssl rand -base64 32 > deploy/secrets/operator_token               # keep a copy: it starts evaluations
: > deploy/secrets/meta_model_api_key                                 # stays EMPTY until live is authorized
sudo chown 10001:10001 deploy/secrets/* && sudo chmod 400 deploy/secrets/*
cat > deploy/.env <<'ENV'
SITE_ADDRESS=readiness.example.com
AR_SOURCE_RUN=/srv/agent-readiness/live-2d58a80e14
AR_HOSTED_MODE=rehearsal
AR_HOSTED_ACCESS=operator
AR_HOSTED_CEILING_USD=<owner-approved value>
ENV
```

`AR_HOSTED_CEILING_USD` is a hard global limit. Every evaluation reserves **US$1.65 per repetition** (the US$1.60 arm caps plus one US$0.05 request bound), and reservations are never released. The value is persisted at first start; a different value later disables evaluations (`budget_policy_mismatch`) until the owner reconciles deliberately.

Rehearsal and live keep separate data (`/data/hosted/rehearsal` and `/data/hosted/live`, each with its own admission database), so rehearsals never consume the live ceiling or appear in the live history.

To operate privately (no Caddy, nothing public): `docker compose -f compose.yaml -f compose.private.yaml up -d app`, then `ssh -L 8080:127.0.0.1:8080 <host>` and open `http://127.0.0.1:8080/#/run`.

## 3. Build and start (rehearsal, operator-only)

```sh
cd deploy
docker compose build
docker compose up -d
docker compose logs app | grep 'hosted service'        # expect: mode=rehearsal access=operator evaluations=enabled jail=verified
docker compose exec app python -m agent_readiness.hosted.admin health
```

If `evaluations=disabled`, the log line gives the reason code: `isolation_check_failed` / `isolation_policy_invalid` (namespaces blocked: re-check step 1 and the `security_opt` lines), `source_run_missing` / `source_run_unreadable` (mount path or ownership), `missing_operator_token`, `missing_provider_key` (live only), `ceiling_not_configured` / `ceiling_invalid` / `budget_policy_mismatch`. The site and past results stay up in every case.

## 4. Verify the boundary inside the container (required before live)

```sh
docker compose exec app python -c "from agent_readiness.hosted import jail; print(jail.selftest())"
#   expect {'ok': True, 'mirror_reachable': True, 'escapes_blocked': True, 'filesystem_hidden': True}
docker compose exec app python -m agent_readiness.hosted.admin start --repetitions 1 --watch   # scripted rehearsal, no provider
curl -s -o /dev/null -w '%{http_code}\n' -XPOST https://$SITE_ADDRESS/api/ironbark/jobs -H 'content-type: application/json' -d '{}'               # 403 (operator-only)
curl -s -o /dev/null -w '%{http_code}\n' -XPOST https://$SITE_ADDRESS/api/ironbark/jobs -H 'content-type: application/json' -d '{"url":"x"}'      # 422
```

Open `https://$SITE_ADDRESS/#/run`: the rehearsal is labelled as scripted, Watch shows the jailed browser's screenshots, and the run is listed in history after a reload. `docker compose restart app` during a run marks it `interrupted` and keeps its reservation.

## 5. First genuine Muse Spark run (private; needs owner authorization)

```sh
sudo sh -c 'printf %s "<key>" > deploy/secrets/meta_model_api_key' && sudo chown 10001:10001 deploy/secrets/meta_model_api_key && sudo chmod 400 deploy/secrets/meta_model_api_key
sed -i 's/^AR_HOSTED_MODE=.*/AR_HOSTED_MODE=live/' .env && docker compose up -d
docker compose logs app | grep 'hosted service'        # mode=live access=operator evaluations=enabled jail=verified
docker compose exec app python -m agent_readiness.hosted.admin start --repetitions 1 --watch
```

Expected: 8 runs, about 10–30 minutes; at most US$1.65 reserved. Check the result at `#/run/<id>` (badge “Live · Meta Muse Spark”, evidence `real model`). The operator can also start runs from the web UI under *Operator access*.

## 6. Open to judges (needs owner authorization)

```sh
sed -i 's/^AR_HOSTED_ACCESS=.*/AR_HOSTED_ACCESS=public/' .env && docker compose up -d
```

Public starts are limited to one evaluation at a time, one start per client every `AR_HOSTED_MIN_INTERVAL` seconds (default 120), and the ceiling. To stop new runs immediately: set `AR_HOSTED_ACCESS=operator` (or `AR_HOSTED_MODE=disabled`) and `docker compose up -d`.

## Operations

`docker compose exec app python -m agent_readiness.hosted.admin list` · `... watch <id>` · logs: `docker compose logs -f app` · data: volume `agent-readiness_data` (`/data/hosted`: admission DB, job files, per-repetition runs). Back it up before changing the ceiling.
