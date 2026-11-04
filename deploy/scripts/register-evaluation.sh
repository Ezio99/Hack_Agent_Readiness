#!/usr/bin/env bash
# Record AND select a budget evaluation non-interactively under the owner's written authorization (hosted.budget --delegated; audited in
# budget-pools/DELEGATIONS.jsonl). Runs ON THE VM, fed over SSH; never launches a run. Example (the current selection):
#   SSH_AUTH_SOCK=~/.ssh/readiness-agent.sock ssh root@209.38.84.72 \
#     "ID=ar-a20-pair VARIANTS='polishedoriginal modifiedpolished' AUTH='<cite the owner instruction>' bash -s" < deploy/scripts/register-evaluation.sh
# Refuses if the id exists (write-once), if a version is unregistered, if the suite is not owner-frozen, or if the per-run maximum exceeds the
# budget's one-run allowance (US$3.740). Prints the exact terms and their sha256 first; the record is bound to that sha256.
set -e
cd /root/agent-readiness/deploy; DB=/data/hosted/live/admission.sqlite
test -n "$ID" && test -n "$VARIANTS" && test ${#AUTH} -ge 20
T=$(date -u +%Y%m%dT%H%M%SZ); docker run --rm -v agent-readiness_data:/data:ro -v /root/backups:/out alpine sh -c "cp /data/hosted/live/admission.sqlite /out/admission-pre-$ID-$T.sqlite && tar czf /out/stage-b-pre-$ID-$T.tgz -C /data/hosted/lifecycle stage-b" && echo "backup $T"
OUT=$(docker compose exec -T app python -m agent_readiness.hosted.budget evaluation-add --db $DB --budget ar-a20-2026-11 --id $ID --frozen larkspur-core@v3 --variants $VARIANTS --delegated dry-run-only-authorization-text --dry-run </dev/null)
echo "$OUT"
TS=$(echo "$OUT" | sed -n 's/^sha256 //p'); test -n "$TS"
docker compose exec -T app python -m agent_readiness.hosted.budget evaluation-add --db $DB --budget ar-a20-2026-11 --id $ID --frozen larkspur-core@v3 --variants $VARIANTS --delegated "$AUTH" --expect-sha256 $TS </dev/null
docker compose exec -T app python -m agent_readiness.hosted.budget evaluation-use --db $DB --budget ar-a20-2026-11 --id $ID --delegated "$AUTH" </dev/null
docker compose exec -T app python -m agent_readiness.hosted.budget status --db $DB </dev/null | grep -E "selected|budget  "
