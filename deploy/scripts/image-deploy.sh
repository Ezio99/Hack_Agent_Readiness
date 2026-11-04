#!/usr/bin/env bash
# Image-only deploy with the A0-A5 procedure (collaboration/reports/evaluation-launch-final.md §5). Runs ON THE VM, fed over SSH:
#   SSH_AUTH_SOCK=~/.ssh/readiness-agent.sock ssh root@209.38.84.72 "C=<commit> TAG=<short-name> bash -s" < deploy/scripts/image-deploy.sh
# The commit must be pushed to origin/final-showcase. Refuses unless the worker is idle. Never prints secrets. Needs owner approval (or standing authorization).
set -e
cd /root/agent-readiness/deploy; DB=/data/hosted/live/admission.sqlite; S=https://209-38-84-72.sslip.io
CUR=$(docker inspect --format "{{.Image}}" $(docker compose ps -q app)); echo "A0 current image $CUR"
curl -s $S/api/ironbark/config | python3 -c "import json,sys;c=json.load(sys.stdin);print('A0 worker',c['worker']['state'],c.get('active'),c['evaluation']['variants'],[(b['available_aud'],b['spent_aud'],b['jobs']) for b in c['spending']['budgets']])"
T=$(date -u +%Y%m%dT%H%M%SZ); echo "A1 T=$T"
docker run --rm -v agent-readiness_data:/data:ro -v /root/backups:/out alpine tar czf /out/predeploy-$TAG-$T.tgz -C /data .
docker run --rm -v agent-readiness_data:/data:ro alpine sh -c 'cd /data && find . -type f ! -path "*/derived/*" | sort | xargs sha256sum' > /root/backups/predeploy-$TAG-$T.sha256
cp .env /root/backups/env-predeploy-$TAG-$T && chmod 600 /root/backups/env-predeploy-$TAG-$T
gzip -t /root/backups/predeploy-$TAG-$T.tgz && rm -rf /root/backups/v && mkdir /root/backups/v && tar xzf /root/backups/predeploy-$TAG-$T.tgz -C /root/backups/v && (cd /root/backups/v && sha256sum -c --quiet /root/backups/predeploy-$TAG-$T.sha256) && rm -rf /root/backups/v && echo "A1 backup verified $(wc -l < /root/backups/predeploy-$TAG-$T.sha256)"
git -C /root/agent-readiness fetch -q origin final-showcase
rm -rf /root/agent-readiness-build-$TAG; git -C /root/agent-readiness worktree prune
git -C /root/agent-readiness worktree add -q --detach /root/agent-readiness-build-$TAG $C
cd /root/agent-readiness-build-$TAG && test "$(git status --porcelain | wc -l)" = 0 && diff -q deploy/compose.yaml /root/agent-readiness/deploy/compose.yaml && echo "A2 compose identical, clean $C"
docker build -q -f deploy/Dockerfile -t agent-readiness-app:$TAG-$C . ; cd /root/agent-readiness/deploy
docker run --rm agent-readiness-app:$TAG-$C python -c "from agent_readiness.sites.larkspur import render as r; print('A3', [(v, r.snapshot(v).sha256[:12]) for v in r.VARIANTS])"
W=$(curl -s $S/api/ironbark/config | python3 -c "import json,sys;c=json.load(sys.stdin);print(c['worker']['state'], c.get('active'))"); test "$W" = "idle None"
PREV=$(docker image inspect --format '{{.Id}}' agent-readiness-app:latest)
docker tag agent-readiness-app:latest agent-readiness-app:rollback-before-$TAG && docker tag agent-readiness-app:$TAG-$C agent-readiness-app:latest
docker compose up -d --no-build --no-deps app 2>&1 | tail -1
for i in $(seq 1 60); do s=$(docker inspect --format '{{.State.Health.Status}}' $(docker compose ps -q app)); [ "$s" = healthy ] && break; sleep 3; done; echo "A4 health: $s; image $(docker inspect --format '{{.Image}}' $(docker compose ps -q app)); rollback-before-$TAG = $PREV"
echo "A5 tracebacks: $(docker compose logs app 2>&1 | grep -c Traceback || true)"
echo "A5 POST no code: $(curl -s -o /dev/null -w '%{http_code}' -X POST -H 'content-type: application/json' -H 'idempotency-key: abcdefghijklmnop1234' -d '{"repetitions":1}' $S/api/ironbark/jobs)"
docker run --rm -v agent-readiness_data:/data:ro alpine sh -c 'cd /data && find . -type f ! -path "*/derived/*" | sort | xargs sha256sum' > /tmp/post-$TAG.sha256
diff /root/backups/predeploy-$TAG-$T.sha256 /tmp/post-$TAG.sha256 && echo "A5 evidence identical $(wc -l < /tmp/post-$TAG.sha256)"
printf '%s deployed %s image %s (rollback-before-%s = %s) by agent under owner instruction\n' "$(date -u +%FT%TZ)" "$C" "$(docker inspect --format '{{.Image}}' $(docker compose ps -q app))" "$TAG" "$PREV" >> DEPLOYED.txt
