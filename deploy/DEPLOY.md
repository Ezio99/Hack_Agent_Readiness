# Deploying the hosted Ironbark evaluation

One Linux host with Docker Engine and Compose v2. Caddy terminates TLS and proxies to a single app container that holds the API, the job worker and the jailed Chromium. **A public deployment, and the `live` mode in particular, need explicit owner authorization.**

## What runs where

| Component | Boundary |
|---|---|
| Caddy (`caddy`) | Only published service (80/443). Overwrites `X-Forwarded-For`; caps request bodies at 4 KB. |
| API (`agent_readiness.hosted.serve`) | Fixed target; the only request field is `repetitions` ∈ {1, 3, 5}. Durable SQLite admission: one evaluation at a time, a per-client interval, and a global ceiling reserved before any work (US$1.60 per repetition, never released). |
| Worker (`agent_readiness.hosted.paired`, one per evaluation) | Runs the unchanged paired driver once per repetition: fresh fork, the frozen tasks, the snapshots, the profile and the caps checked against the reservation, the existing spend gate and ledger, the independent grader, and the sanitized export. Dies with the service (parent-death signal); a restarted service marks unfinished jobs `interrupted` and keeps their reservations. |
| Chromium (`agent_readiness.hosted.jail`) | Own user/network/PID/mount namespaces. The network namespace has loopback only; only the snapshot mirror port and the CDP port are bridged, over Unix sockets. Fresh `/proc` (the worker's environment is not visible); `/app`, `/data`, `/run/secrets` and `/home` are hidden. The service refuses to start evaluations unless its isolation self-test passes at boot. |
| Provider key | Docker secret file, read by the worker after exec (not in any process environment block) and scrubbed from the browser's environment. |

## Prerequisites

* A Linux host (Ubuntu 22.04/24.04 or Debian 12) with 2+ vCPU, 4+ GB RAM and a DNS name pointing at it, with ports 80/443 open.
* Unprivileged user namespaces: `sysctl kernel.unprivileged_userns_clone` (Debian) must be 1. On Ubuntu 23.10+, `sudo sysctl -w kernel.apparmor_restrict_unprivileged_userns=0` (persist it in `/etc/sysctl.d/`) because the container runs with `apparmor=unconfined`.
* The private source run `scanner-data/live/live-2d58a80e14` (about 26 MB, not in Git) copied to the host, e.g. `/srv/agent-readiness/live-2d58a80e14`. It is mounted read-only.

## Steps

```sh
git clone … && cd Hack_Agent_Readiness && git checkout hosted-ironbark-evaluation
mkdir -p deploy/secrets && install -m 600 /dev/null deploy/secrets/meta_model_api_key   # empty unless live is authorized
export SITE_ADDRESS=readiness.example.com AR_SOURCE_RUN=/srv/agent-readiness/live-2d58a80e14
docker compose -f deploy/compose.yaml build

# 1. Disabled: Replay Studio only, the Run button explains that evaluations are unavailable.
docker compose -f deploy/compose.yaml up -d
# 2. Rehearsal: real jailed browsers and grading, scripted agent, no provider, labelled in the UI.
AR_HOSTED_MODE=rehearsal AR_HOSTED_CEILING_USD=<owner value> docker compose -f deploy/compose.yaml up -d
docker compose -f deploy/compose.yaml logs app | grep 'hosted service'   # expect jail=verified
# 3. Live (only after owner approval of the ceiling and spending): put the key in deploy/secrets/meta_model_api_key, then
AR_HOSTED_MODE=live AR_HOSTED_CEILING_USD=<owner value> docker compose -f deploy/compose.yaml up -d
```

`AR_HOSTED_CEILING_USD` is persisted at first use in `/data/hosted/admission.sqlite`. Starting with a different value is refused until the owner reconciles it deliberately. The ceiling is a hard global limit: every evaluation reserves 1.60 × repetitions against it.

## Checks after deploy

* `curl https://$SITE_ADDRESS/api/ironbark/config` returns `available` and the mode.
* `curl -XPOST https://$SITE_ADDRESS/api/ironbark/jobs -d '{"url":"x"}' -H 'content-type: application/json'` returns 422.
* Start one rehearsal repetition from the browser and watch the progress until it completes; reload the page and it comes back (`#/run/<id>`).
* `docker compose restart app` during a run: the job shows `Interrupted` and its reservation remains.
